import requests
from bs4 import BeautifulSoup
import config
import urllib3
from urllib.parse import urljoin
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
links_result = {}

for key, info in config.link_dikt.items():
    url = info['url']
    patterns = info['patterns']
    print(url)
    response = requests.get(url, verify=False)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    found_links = []

    for link in links:
        if any(pattern in link['href'] for pattern in patterns):
            absolute_url = urljoin(url, link['href'])
            print(absolute_url)
            found_links.append(absolute_url)

    links_result[key] = found_links


with open('links.json', 'w', encoding='utf-8') as file:
    json.dump(links_result, file, ensure_ascii=False, indent=4)