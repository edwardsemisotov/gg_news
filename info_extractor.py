import asyncio
import httpx
import urllib.parse
import asyncpg
import config
import logging
from slugify import slugify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

request_semaphore = asyncio.Semaphore(1)
article_processing_semaphore = asyncio.Semaphore(10)


async def generate_unique_slug(conn, base_slug):
    iteration = 0
    max_slug_length = 255
    while True:
        suffix = f"-{iteration}" if iteration > 0 else ""
        unique_slug = f"{base_slug[:max_slug_length - len(suffix)]}{suffix}"
        exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM news.article_details WHERE slug = $1)", unique_slug)
        if not exists:
            return unique_slug
        iteration += 1


async def generate_review_with_gpt(text, retry_count=3):
    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.openai_api_key}"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system",
             "content": "You are a highly skilled journalist. Your task is to process the incoming text as a top-tier journalist would, ensuring it is well-structured, coherent, and engaging. Make sure to use appropriate formatting, including clear paragraph separation using the '\\n' symbol and a professional journalistic tone.."},
            {"role": "user", "content": text}
        ]
    }
    timeout_config = httpx.Timeout(10.0, read=60.0)
    async with httpx.AsyncClient() as client:
        for attempt in range(retry_count):
            try:
                response = await client.post(api_url, json=payload, headers=headers, timeout=timeout_config)
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content']
                else:
                    logger.error(f"Failed to generate review with GPT: {response.text}")
                    if response.status_code == 500:
                        continue
                    return None
            except httpx.ReadTimeout:
                logger.error(
                    f"Read timeout occurred while generating review for text, attempt {attempt + 1} of {retry_count}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                return None
    logger.error(f"All retries failed for text: {text}")
    return None


async def translate_with_gpt(text, target_language='ru', retry_count=3):
    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.openai_api_key}"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system",
             "content": f"You are a translator. Please translate the following text to {target_language}."},
            {"role": "user", "content": text}
        ]
    }
    timeout_config = httpx.Timeout(10.0, read=60.0)
    async with httpx.AsyncClient() as client:
        for attempt in range(retry_count):
            try:
                response = await client.post(api_url, json=payload, headers=headers, timeout=timeout_config)
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content']
                else:
                    logger.error(f"Failed to translate text with GPT: {response.text}")
            except httpx.ReadTimeout:
                logger.error(f"Read timeout occurred on attempt {attempt + 1}/{retry_count}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
            except httpx.RequestError as e:
                logger.error(f"HTTP request failed: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
    logger.error("All retries failed for translation.")
    return None


async def guarded_process_article(pool, link_id, url):
    async with article_processing_semaphore:
        await process_article(pool, link_id, url)


async def process_article(pool, link_id, url):
    max_retries = 3
    retry_delay = 2

    try:
        async with pool.acquire() as conn:
            logger.info(f"Updating status to 'in progress' for link_id: {link_id}")
            await conn.execute("UPDATE news.links SET status = 'in progress' WHERE id = $1", link_id)

            api_token = config.diffbot_api
            encoded_url = urllib.parse.quote(url)
            api_url = f"https://api.diffbot.com/v3/analyze?url={encoded_url}&token={api_token}"
            headers = {"accept": "application/json"}
            timeout_config = httpx.Timeout(10.0, read=60.0)

            response = None
            for attempt in range(max_retries):
                async with request_semaphore:
                    response = await http_client.get(api_url, headers=headers, timeout=timeout_config)
                if response.status_code == 200:
                    break
                elif response.status_code == 429:
                    logger.error("API request failed due to quota limits: setting status to 'quota_limit_diffbot'")
                    await conn.execute("UPDATE news.links SET status = 'quota_limit_diffbot' WHERE id = $1", link_id)
                    return
                await asyncio.sleep(retry_delay * (2 ** attempt))

            if response is None or response.status_code != 200:
                logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                await conn.execute("UPDATE news.links SET status = 'fetch_error' WHERE id = $1", link_id)
                return

            data = response.json()
            if 'error' in data or not data.get('objects'):
                logger.error(f"No objects found in API response for {url}")
                await conn.execute("UPDATE news.links SET status = 'no_objects' WHERE id = $1", link_id)
                return

            objects = data.get('objects', [])
            if not objects:
                logger.error(f"No objects found in API response for {url}")
                await conn.execute("UPDATE news.links SET status = 'no_objects' WHERE id = $1", link_id)
                return

            article_title = objects[0].get('title', '')
            article_text = objects[0].get('text', '')
            article_lang = objects[0].get('lang', 'pl')

            if not article_text:
                logger.info("No content found for article, setting status to 'no_objects'")
                await conn.execute("UPDATE news.links SET status = 'no_content' WHERE id = $1", link_id)
                return

            review = await generate_review_with_gpt(article_text)
            if review is None:
                logger.error(f"Failed to generate review for article {url}")
                await conn.execute("UPDATE news.links SET status = 'error_review' WHERE id = $1", link_id)
                return

            base_slug = slugify(article_title)
            article_slug = await generate_unique_slug(conn, base_slug)

            await insert_article_details(conn, link_id, article_title, article_text, article_slug, review, 'pl')

            for target_language in ['ru', 'en', 'uk', 'be']:
                translated_title = await translate_with_gpt(article_title, target_language)
                translated_text = await translate_with_gpt(article_text, target_language)
                translated_review = await translate_with_gpt(review, target_language)

                if translated_title and translated_text and translated_review:
                    base_slug = slugify(translated_title)
                    article_slug = await generate_unique_slug(conn, base_slug)
                    await insert_article_details(conn, link_id, translated_title, translated_text, article_slug,
                                                 translated_review, target_language)

            await conn.execute("UPDATE news.links SET status = 'done' WHERE id = $1", link_id)

    except Exception as e:
        logger.error(f"Error processing article {url}: {e}", exc_info=True)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE news.links SET status = 'error_article' WHERE id = $1", link_id)


async def insert_article_details(conn, link_id, title, text, slug, review, lang):
    result = await conn.execute("""
        INSERT INTO news.article_details (link_id, summary, content, slug, journalist_gpt, lang) 
        VALUES ($1, $2, $3, $4, $5, $6)
    """, link_id, title, text, slug, review, lang)
    logger.info(f"Inserted article in {lang}: {result}")


async def main():
    try:
        pool = await asyncpg.create_pool(
            database=config.core_dbname,
            user=config.core_user,
            password=config.core_password,
            host=config.core_host,
            port=config.core_port
        )
        global http_client
        http_client = httpx.AsyncClient()

        while True:
            rows = await pool.fetch("SELECT id, url FROM news.links WHERE status='error_article' or status='pending'")
            tasks = [guarded_process_article(pool, row['id'], row['url']) for row in rows if
                     not "youtube.com" in row['url']]
            await asyncio.gather(*tasks)
            await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if http_client:
            await http_client.aclose()
        await pool.close()
        logger.info("Database connection and HTTP client closed.")


if __name__ == "__main__":
    asyncio.run(main())
