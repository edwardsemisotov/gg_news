import requests
from newspaper import Article
from requests.exceptions import SSLError
import psycopg2
import psycopg2.extras
import config
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)


def process_article(cur, link_id, url):
    try:
        cur.execute("UPDATE links SET status = 'in progress' WHERE id = %s", (link_id,))

        article = Article(url)
        article.download()
        article.parse()
        article.nlp()

        cur.execute("""
            INSERT INTO article_details (link_id, summary, content) VALUES (%s, %s, %s)
            ON CONFLICT (link_id) DO NOTHING
        """, (link_id, article.summary, article.text))

        for image in article.images:
            if not any(substring in image for substring in ['.png', 'data', 'yandex', 'telega-b']):
                cur.execute("INSERT INTO image_links (link_id, image_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (link_id, image))

        for video in article.movies:
            cur.execute("INSERT INTO video_links (link_id, video_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (link_id, video))

        cur.execute("UPDATE links SET status = 'ready' WHERE id = %s", (link_id,))
    except (requests.exceptions.RequestException, SSLError) as e:
        logger.error(f"Error downloading {url}: {e}")
        cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))
    except Exception as e:
        logger.error(f"Error processing article {url}: {e}")
        cur.execute("UPDATE links SET status = 'error' WHERE id = %s", (link_id,))


def main():
    try:
        conn = psycopg2.connect(
            dbname=config.core_dbname,
            user=config.core_user,
            password=config.core_password,
            host=config.core_host,
            port=config.core_port
        )
        cur = conn.cursor()

        cur.execute("SELECT id, url FROM links WHERE status NOT IN ('ready', 'error', 'send_error', 'done')")
        urls = cur.fetchall()

        for link_id, url in urls:
            if "youtube.com" in url:
                cur.execute("UPDATE links SET status = 'ready' WHERE id = %s", (link_id,))
                continue

            process_article(cur, link_id, url)

        conn.commit()
    except psycopg2.DatabaseError as e:
        logger.error(f"Database error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
            logger.info("Database connection closed.")


if __name__ == "__main__":
    main()
