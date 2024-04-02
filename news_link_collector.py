import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import psycopg2

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)


conn = psycopg2.connect(
    dbname="coredb",
    user="postgres",
    password="mysecretpassword",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

cur.execute("SELECT s.name, s.url, p.pattern FROM sources s JOIN patterns p ON s.id = p.source_id;")
rows = cur.fetchall()

for row in rows:
    source_name, url, pattern = row
    print(f"Processing: {url} with pattern: {pattern}")

    try:
        response = session.get(url, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        found_links = set()
        for link in soup.find_all('a', href=True):
            if pattern in link['href']:
                absolute_url = urljoin(url, link['href'])
                print(absolute_url)
                found_links.add(absolute_url)

                cur.execute(
                    "INSERT INTO links (source_id, url, status) VALUES ((SELECT id FROM sources WHERE url = %s), %s, 'pending') ON CONFLICT (url) DO NOTHING;",
                    (url, absolute_url)
                )
        conn.commit()

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при обработке {url}: {e}")

cur.close()
conn.close()
