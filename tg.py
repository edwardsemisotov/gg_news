import asyncio
import logging
from telegram import Bot, error as telegram_error
import psycopg2
import psycopg2.extras
from telegram.ext import Application
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db_params = {
    "dbname": config.core_dbname,
    "user": config.core_user,
    "password": config.core_password,
    "host": config.core_host,
    "port": config.core_port
}

async def send_with_retry(bot, channel_id, message, image_url=None, max_retries=3):
    retry_count = 0
    while retry_count < max_retries:
        try:
            if image_url:
                await bot.send_photo(chat_id=channel_id, photo=image_url, caption=message)
            else:
                await bot.send_message(chat_id=channel_id, text=message)
            return True  # Возвращаем True при успешной отправке
        except telegram_error.TelegramError as e:
            if "Wrong file identifier/http url specified" in str(e):
                logger.warning(f"Invalid image URL, sending message without image: {image_url}")
                image_url = None  # Удаляем изображение из сообщения
                continue  # Продолжаем попытки без изображения
            elif "Timed out" in str(e):
                logger.warning(f"Timeout error, retrying {retry_count + 1}/{max_retries}")
                retry_count += 1
                await asyncio.sleep(10)
            else:
                logger.error(f"Error sending message to Telegram: {e}")
                return False  # Возвращаем False, если ошибка не связана с изображением или таймаутом
    return False

async def send_articles(bot, channel_id):
    conn = None
    try:
        conn = psycopg2.connect(**db_params)
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT id, url FROM links WHERE status = 'send_error' or status = 'ready';")
                links = cur.fetchall()

                for link in links:
                    link_id, url = link['id'], link['url']
                    cur.execute("""
                        SELECT ad.summary, il.image_url
                        FROM article_details ad
                        LEFT JOIN image_links il ON ad.link_id = il.link_id
                        WHERE ad.link_id = %s
                        ORDER BY il.id DESC
                        LIMIT 1;
                    """, (link_id,))
                    article = cur.fetchone()

                    if article:
                        summary = article['summary']
                        image_url = article['image_url']

                        message = f"{summary}\n\nMore details: {url}"
                        if len(message) > 1024:
                            max_summary_length = 1024 - len(f"\n\nMore details: {url}") - 3
                            summary = summary[:max_summary_length] + '...'
                            message = f"{summary}\n\nMore details: {url}"

                        success = await send_with_retry(bot, channel_id, message, image_url)

                        if success:
                            cur.execute("UPDATE links SET status = 'done' WHERE id = %s", (link_id,))
                        else:
                            cur.execute("UPDATE links SET status = 'send_error' WHERE id = %s", (link_id,))

                    conn.commit()
                    await asyncio.sleep(10)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    bot_token = config.tg_bot_token
    application = Application.builder().token(bot_token).build()
    bot = application.bot
    channel_id = config.channel_id

    asyncio.run(send_articles(bot, channel_id))
