import requests
from newspaper import Article
from requests.exceptions import SSLError
import psycopg2

conn = psycopg2.connect(
    dbname="coredb",
    user="postgres",
    password="mysecretpassword",
    host="localhost",
    port="5432"
)

cur = conn.cursor()
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

try:
    cur.execute("SELECT id, url FROM links WHERE status != 'ready' AND status != 'error' AND status != 'send_error'")
    urls = cur.fetchall()

    for link_id, url in urls:
        try:
            cur.execute("UPDATE links SET status = 'in progress' WHERE id = %s", (link_id,))
            conn.commit()

            article = Article(url)
            article.download()
            article.parse()
            article.nlp()

            cur.execute("""
                INSERT INTO article_details (link_id, summary, content) VALUES (%s, %s, %s)
                ON CONFLICT (link_id) DO UPDATE SET summary = EXCLUDED.summary, content = EXCLUDED.content
            """, (link_id, article.summary, article.text))

            # Фильтрация и добавление изображений
            for image in article.images:
                if not any(substring in image for substring in ['.png', 'data', 'yandex']):
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
