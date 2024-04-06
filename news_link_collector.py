import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import psycopg2
import googleapiclient.discovery
from googleapiclient.errors import HttpError
import config
import time


requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

def get_channel_videos(channel_id):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=config.youtube_api)
    request = youtube.channels().list(part="contentDetails", id=channel_id)
    response = request.execute()
    uploads_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    videos = []
    next_page_token = None
    while True:
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()
        videos += [{
            'title': item['snippet']['title'],
            'description': item['snippet']['description'],
            'video_url': f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
        } for item in response['items']]
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    return videos

conn = psycopg2.connect(
    dbname=config.core_dbname,
    user=config.core_user,
    password=config.core_password,
    host=config.core_host,
    port=config.core_port
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

    if "youtube.com" in url:
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                videos = get_channel_videos(pattern)
                for video in videos:
                    print(f"Title: {video['title']}\nDescription: {video['description']}\nURL: {video['video_url']}\n")
                    cur.execute(
                        "INSERT INTO links (source_id, url, status) VALUES ((SELECT id FROM sources WHERE url = %s), %s, 'pending') ON CONFLICT (url) DO NOTHING RETURNING id;",
                        (url, video['video_url'])
                    )
                    result = cur.fetchone()
                    if result:
                        link_id = result[0]
                        cur.execute("""
                            INSERT INTO article_details (link_id, summary, content) VALUES (%s, %s, %s)
                            ON CONFLICT (link_id) DO UPDATE SET summary = EXCLUDED.summary, content = EXCLUDED.content
                        """, (link_id, video['title'], video['description']))
                    else:
                        print(f"Link already exists: {video['video_url']}")

                conn.commit()
                break
            except HttpError as e:
                if e.resp.status in [408, 504]:
                    print(
                        f"Attempt {attempt + 1} of {max_attempts}: HTTP timeout error occurred. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
                    break
    else:
        try:
            response = session.get(url, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                if pattern in link['href']:
                    absolute_url = urljoin(url, link['href'])
                    print(absolute_url)
                    cur.execute(
                        "INSERT INTO links (source_id, url, status) VALUES ((SELECT id FROM sources WHERE url = %s), %s, 'pending') ON CONFLICT (url) DO NOTHING;",
                        (url, absolute_url)
                    )
            conn.commit()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при обработке {url}: {e}")

cur.close()
conn.close()
