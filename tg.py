import asyncio
from telegram import Bot, error as telegram_error
import psycopg2
import psycopg2.extras
from telegram.ext import Application
import config

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
            return True
        except telegram_error.TelegramError as e:
            if "Timed out" in str(e):
                print(f"Ошибка тайм-аута, повторная попытка {retry_count + 1}/{max_retries}")
                retry_count += 1
                await asyncio.sleep(10)  # Ожидаем перед повторной попыткой
            else:
                print(f"Ошибка при отправке сообщения в Telegram: {e}")
                return False
    return False


async def send_articles(bot, channel_id):
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_params, cursor_factory=psycopg2.extras.DictCursor)
        cur = conn.cursor()

        cur.execute("SELECT id, url FROM links WHERE status = 'ready';")
        links = cur.fetchall()

        for link in links:
            link_id, url = link['id'], link['url']
            if 'youtube' in url:
                message = f"Пройдите по ссылке для подробностей: {url}"

                success = await send_with_retry(bot, channel_id, message)

                if success:
                    cur.execute("UPDATE links SET status = 'done' WHERE id = %s", (link_id,))
                else:
                    cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
                conn.commit()

            else:
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

                    summary, image_url = article['summary'], article['image_url']
                    if len(summary) > 1024:
                        summary = summary[:950] + "..."

                    message = f"{summary}\nПройдите по ссылке для подробностей: {url}"

                    success = await send_with_retry(bot, channel_id, message, image_url)

                    if success:
                        cur.execute("UPDATE links SET status = 'done' WHERE id = %s", (link_id,))
                    else:
                        cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
                    conn.commit()

            await asyncio.sleep(10)

    except Exception as e:
        print(f"Ошибка: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()


if __name__ == "__main__":
    bot_token = config.tg_bot_token
    application = Application.builder().token(bot_token).build()
    bot = application.bot
    channel_id = config.channel_id

    asyncio.run(send_articles(bot, channel_id))
