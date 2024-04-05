import asyncio
import re
from telegram import Bot, error as telegram_error
import psycopg2
import psycopg2.extras
from telegram.ext import Application
from googleapiclient.discovery import build
import config

# Функция для определения, является ли URL ссылкой на видео YouTube.
def is_youtube_url(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match.group(6)
    return None

# Функция для получения информации о видео YouTube.
def get_youtube_video_info(video_id):
    youtube = build('youtube', 'v3', developerKey=config.youtube_api_key)
    request = youtube.videos().list(part='snippet', id=video_id)
    response = request.execute()

    if response['items']:
        video_info = response['items'][0]['snippet']
        title = video_info['title']
        description = video_info['description']
        return title, description
    return None, None

# Ваша асинхронная функция отправки
async def send_with_retry(...):
    # Тело функции остается без изменений

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
            video_id = is_youtube_url(url)

            if video_id:
                title, description = get_youtube_video_info(video_id)
                if title and description:
                    message = f"{title}\n{description}\nСмотреть видео: {url}"
                    if len(message) > 1024:
                        message = message[:1021] + "..."
                    await send_with_retry(bot, channel_id, message, None)
                    cur.execute("UPDATE links SET status = 'done' WHERE id = %s", (link_id,))
                else:
                    cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
            else:
                # Оставшаяся часть обработки для не-YouTube ссылок
                ...

            conn.commit()
            await asyncio.sleep(10)  # Пауза перед отправкой следующего сообщения

    except Exception as e:
        print(f"Ошибка: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()

# Основная часть кода для запуска бота и отправки сообщений
if __name__ == "__main__":
    # Конфигурация и запуск бота
