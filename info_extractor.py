import requests
from newspaper import Article
from requests.exceptions import RequestException, SSLError
from newspaper.article import ArticleException
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
        logger.info(f"Updating status to 'in progress' for link_id: {link_id}")
        cur.execute("UPDATE links SET status = 'in progress' WHERE id = %s", (link_id,))
        cur.connection.commit()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        article = Article(url, keep_article_html=True, browser_user_agent=headers['User-Agent'])

        try:
            article.download()
            article.parse()
        except ArticleException as e:
            logger.error(f"Failed to download or parse article {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error during downloading or parsing {url}: {e}")
            raise

        try:
            article.nlp()
        except ArticleException as e:
            logger.error(f"Failed to perform NLP on article {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error during NLP processing {url}: {e}")
            raise

        cur.execute("""
            INSERT INTO article_details (link_id, summary, content) VALUES (%s, %s, %s)
            ON CONFLICT (link_id) DO NOTHING
        """, (link_id, article.summary, article.text))
        cur.connection.commit()

        for image in article.images:
            if not any(substring in image for substring in ['.png', 'data', 'yandex', 'telega-b']):
                cur.execute("INSERT INTO image_links (link_id, image_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (link_id, image))
                cur.connection.commit()

        for video in article.movies:
            cur.execute("INSERT INTO video_links (link_id, video_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (link_id, video))
            cur.connection.commit()

        cur.execute("UPDATE links SET status = 'ready' WHERE id = %s", (link_id,))
        cur.connection.commit()
    except (RequestException, SSLError, ArticleException) as e:
        logger.error(f"Error processing article {url}: {e}")
        cur.execute("UPDATE links SET status = 'error_article' WHERE id = %s", (link_id,))
        cur.connection.commit()
    except Exception as e:
        logger.error(f"Unexpected error while processing article {url}: {e}")
        cur.execute("UPDATE links SET status = 'error_article' WHERE id = %s", (link_id,))
        cur.connection.commit()


def main():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=config.core_dbname,
            user=config.core_user,
            password=config.core_password,
            host=config.core_host,
            port=config.core_port
        )
        cur = conn.cursor()

        cur.execute("SELECT id, url FROM links WHERE status='pending'")
        urls = cur.fetchall()

        for link_id, url in urls:
            if "youtube.com" in url:
                cur.execute("UPDATE links SET status = 'ready' WHERE id = %s", (link_id,))
                cur.connection.commit()
                continue

            process_article(cur, link_id, url)

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
