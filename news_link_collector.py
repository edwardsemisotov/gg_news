import logging
import aiohttp
import asyncio
import asyncpg
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()


async def fetch(url, session):
    async with session.get(url, ssl=False) as response:
        return await response.text()


async def process_source(row, session, pool):
    source_name, url, pattern = row
    logger.info(f"Processing: {url} with pattern: {pattern}")

    try:
        html = await fetch(url, session)
        soup = BeautifulSoup(html, 'html.parser')
        links = [urljoin(url, link['href']) for link in soup.find_all('a', href=True) if pattern in link['href']]

        if links:
            for link in links:
                logger.info(f"Adding to DB: {link}")

            async with pool.acquire() as conn:
                await conn.executemany(
                    "INSERT INTO BelarusCatholicDigest.links (source_id, url, status) VALUES ((SELECT id FROM sources WHERE url = $1), $2, 'pending') ON CONFLICT (url) DO NOTHING;",
                    [(url, link) for link in links]
                )
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")


async def main():
    conn_info = {
        'database': config.core_dbname,
        'user': config.core_user,
        'password': config.core_password,
        'host': config.core_host,
        'port': config.core_port
    }

    pool = await asyncpg.create_pool(**conn_info)
    logger.info("Successfully created database pool.")

    async with aiohttp.ClientSession() as session, pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT s.name, s.url, p.pattern FROM BelarusCatholicDigest.sources s JOIN BelarusCatholicDigest.patterns p ON s.id = p.source_id WHERE s.url NOT LIKE '%youtube.com%';"
        )
        tasks = [process_source(row, session, pool) for row in rows]
        await asyncio.gather(*tasks)

    logger.info("Completed processing.")


if __name__ == '__main__':
    asyncio.run(main())
