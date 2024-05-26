import asyncio
import logging
from telegram import Bot, error as telegram_error
import asyncpg
from telegram.ext import Application
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def send_with_retry(bot, channel_id, message, image_url=None, max_retries=3):
    retry_count = 0
    while retry_count < max_retries:
        try:
            if image_url:
                await bot.send_photo(chat_id=channel_id, photo=image_url, caption=message, parse_mode='Markdown')
            else:
                await bot.send_message(chat_id=channel_id, text=message, parse_mode='Markdown')
            return True
        except telegram_error.TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            error_message = str(e)
            if "Wrong file identifier/http url specified" in error_message or \
                    "Wrong remote file identifier specified: wrong character in the string" in error_message:
                logger.warning(f"Invalid image URL, trying to send message without image: {image_url}")
                image_url = None
                continue
            elif "Timed out" in error_message:
                logger.warning(f"Timeout error, retrying {retry_count + 1}/{max_retries}")
                retry_count += 1
                await asyncio.sleep(10)
            else:
                return False
        except Exception as general_error:
            logger.error(f"Unexpected error occurred: {general_error}")
            return False
    return False


async def send_articles(bot, channel_id):
    try:
        pool = await asyncpg.create_pool(
            database=config.core_dbname,
            user=config.core_user,
            password=config.core_password,
            host=config.core_host,
            port=config.core_port
        )

        while True:
            async with pool.acquire() as conn:
                links = await conn.fetch("SELECT id FROM news.links WHERE status = 'send_error' or status = 'ready';")
                if not links:
                    logger.info("No tasks available. Waiting...")
                    await asyncio.sleep(60)
                    continue

                for link in links:
                    link_id = link['id']
                    articles = await conn.fetch("""
                        SELECT ad.summary, ad.lang, ad.slug, il.image_url
                        FROM news.article_details ad
                        LEFT JOIN news.image_links il ON ad.link_id = il.link_id
                        WHERE ad.link_id = $1
                        ORDER BY il.id DESC;
                    """, link_id)

                    if articles:
                        summary = articles[0]['summary']  # We assume the summary is the same across all versions
                        image_url = articles[0]['image_url']  # Use the first image URL found

                        message = f"📰 *{summary}*\n\n"
                        for article in articles:
                            lang = article['lang']
                            slug = article['slug']
                            custom_url = f"https://warszaw.infocore.news/{lang}/{slug}"
                            message += f"[Read more ({lang.upper()})]({custom_url})\n"

                        if len(message) > 1024:
                            max_summary_length = 1024 - len(message) + len(summary) - 3
                            summary = summary[:max_summary_length] + '...'
                            message = f"📰 *{summary}*\n\n" + message

                        success = await send_with_retry(bot, channel_id, message, image_url)

                        new_status = 'done' if success else 'send_error'
                        await conn.execute("UPDATE news.links SET status = $2 WHERE id = $1", link_id, new_status)

                await asyncio.sleep(10)

    except Exception as e:
        logger.error(f"An error occurred while processing articles: {e}")
    finally:
        if pool:
            await pool.close()


if __name__ == "__main__":
    bot_token = config.tg_bot_token
    application = Application.builder().token(bot_token).build()
    bot = application.bot
    channel_id = config.channel_id

    asyncio.run(send_articles(bot, channel_id))
