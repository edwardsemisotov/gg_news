import requests
from bs4 import BeautifulSoup
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
with open('links.json', 'r', encoding='utf-8') as file:
    links = json.load(file)

news_content = {}

for key, urls in links.items():
    for url in urls:
        try:
            response = requests.get(url, verify=False)

            soup = BeautifulSoup(response.content, 'html.parser')

            content = soup.get_text(strip=True)
            if key not in news_content:
                news_content[key] = []
            news_content[key].append({'url': url, 'content': content})
        except Exception as e:
            print(f"Error retrieving content from {url}: {e}")


with open('news_content.json', 'w', encoding='utf-8') as file:
    json.dump(news_content, file, ensure_ascii=False, indent=4)
