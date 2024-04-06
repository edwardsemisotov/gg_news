import requests
from newspaper import Article
from requests.exceptions import SSLError
import psycopg2
import config

conn = psycopg2.connect(
    dbname=config.core_dbname,
    user=config.core_user,
    password=config.core_password,
    host=config.core_host,
    port=config.core_port
)

cur = conn.cursor()
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

try:
    cur.execute("SELECT id, url FROM links WHERE status != 'ready' AND status != 'error' AND status != 'send_error' AND status != 'done'")
    urls = cur.fetchall()

    for link_id, url in urls:
        # Проверяем, является ли ссылка ссылкой на YouTube
        if "youtube.com" in url:
            # Обновляем статус на 'ready' для YouTube ссылок и переходим к следующей итерации
            cur.execute("UPDATE links SET status = 'ready' WHERE id = %s", (link_id,))
            conn.commit()
            continue  # Пропускаем оставшуюся часть цикла для YouTube ссылок

        try:
            cur.execute("UPDATE links SET status = 'in progress' WHERE id = %s", (link_id,))
            conn.commit()

            article = Article(url)
            article.download()
            article.parse()
            article.nlp()

            cur.execute("""
                INSERT INTO article_details (link_id, summary, content) VALUES (%s, %s, %s)
                ON CONFLICT (link_id) DO NOTHING
            """, (link_id, article.summary, article.text))

            # Фильтрация и добавление изображений
            for image in article.images:
                if not any(substring in image for substring in ['.png', 'data', 'yandex', 'telega-b']):
                    cur.execute("INSERT INTO image_links (link_id, image_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                (link_id, image))

            # Добавление видео
            for video in article.movies:
                cur.execute("INSERT INTO video_links (link_id, video_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (link_id, video))

            # Обновляем статус на 'ready'
            cur.execute("UPDATE links SET status = 'ready' WHERE id = %s", (link_id,))
            conn.commit()
        except (requests.exceptions.RequestException, SSLError) as e:
            print(f"Произошла ошибка при загрузке {url}: {e}")
            conn.rollback()
            cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
            conn.commit()
        except Exception as e:
            print(f"Произошла ошибка при обработке статьи {url}: {e}")
            conn.rollback()
            cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
            conn.commit()
finally:
    cur.close()
    conn.close()
