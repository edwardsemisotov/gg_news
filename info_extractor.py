import httpx
import urllib.parse
import asyncpg
import config
import logging
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

async def process_article(pool, link_id, url):
    try:
        async with pool.acquire() as conn:
            logger.info(f"Updating status to 'in progress' for link_id: {link_id}")
            await conn.execute("UPDATE links SET status = 'in progress' WHERE id = $1", link_id)

            api_token = config.diffbot_api
            encoded_url = urllib.parse.quote(url)
            api_url = f"https://api.diffbot.com/v3/analyze?url={encoded_url}&token={api_token}"

            headers = {
                "accept": "application/json"
            }
            response = await http_client.get(api_url, headers=headers)
            data = response.json()

            article_title = data.get('objects', [{}])[0].get('title', '')
            article_text = data.get('objects', [{}])[0].get('text', '')

            images = data.get('objects', [{}])[0].get('images', [])
            image_urls = [image['url'] for image in images]

            await conn.execute("""
                INSERT INTO article_details (link_id, summary, content) VALUES ($1, $2, $3)
                ON CONFLICT (link_id) DO NOTHING
            """, link_id, article_title, article_text)

            for image_url in image_urls:
                await conn.execute("INSERT INTO image_links (link_id, image_url) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                                   link_id, image_url)

            await conn.execute("UPDATE links SET status = 'ready' WHERE id = $1", link_id)
    except Exception as e:
        logger.error(f"Error processing article {url}: {e}")
        async with pool.acquire() as conn:
            await conn.execute("UPDATE links SET status = 'error_article' WHERE id = $1", link_id)

async def main():
    try:
        # Использование пула соединений
        pool = await asyncpg.create_pool(
            database=config.core_dbname,
            user=config.core_user,
            password=config.core_password,
            host=config.core_host,
            port=config.core_port
        )
        global http_client
        http_client = httpx.AsyncClient()

        rows = await pool.fetch("SELECT id, url FROM links WHERE status='error_article' or status='pending'")
        tasks = [process_article(pool, row['id'], row['url']) for row in rows if not "youtube.com" in row['url']]
        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if http_client:
            await http_client.aclose()
        await pool.close()
        logger.info("Database connection and HTTP client closed.")

if __name__ == "__main__":
    asyncio.run(main())
