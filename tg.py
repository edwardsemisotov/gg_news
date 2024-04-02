import asyncio
from telegram import Bot, error as telegram_error
import psycopg2
import psycopg2.extras
from telegram.ext import Application

db_params = {
    "dbname": "coredb",
    "user": "postgres",
    "password": "mysecretpassword",
    "host": "localhost",
    "port": "5432"
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
    try:
        conn = psycopg2.connect(**db_params, cursor_factory=psycopg2.extras.DictCursor)
        cur = conn.cursor()

        cur.execute("SELECT id, url FROM links WHERE status = 'ready';")
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
                summary, image_url = article['summary'], article['image_url']
                message = f"{summary}\nЧитать далее: {url}"

                if len(message) > 1024:
                    message = message[:1021] + "..."

                success = await send_with_retry(bot, channel_id, message, image_url)

                if success:
                    cur.execute("UPDATE links SET status = 'done' WHERE id = %s", (link_id,))
                else:
                    cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
                conn.commit()

            await asyncio.sleep(10)  # Пауза перед отправкой следующего сообщения

    except Exception as e:
        print(f"Ошибка: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()


if __name__ == "__main__":
    bot_token = '6967417073:AAGkkgVcyc7i5uReF1ceWZEeB2LvtKzUDTk'
    application = Application.builder().token(bot_token).build()
    bot = application.bot
    channel_id = '@BelarusCatholicDigest'

    asyncio.run(send_articles(bot, channel_id))
