import requests
from bs4 import BeautifulSoup
import re

# URL статьи
url = 'https://polskieradio24.pl/artykul/3356033'

# Отправка HTTP-запроса
response = requests.get(url)

# Проверка успешности запроса
if response.status_code == 200:
    # Парсинг HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Поиск всех интересующих тегов
    content_elements = soup.find_all(['p', 'h2', 'a'])

    # Обработка найденных элементов
    for element in content_elements:
        # Если элемент - ссылка и содержит YouTube URL
        if element.name == 'a' and 'href' in element.attrs:
            href = element['href']
            if 'youtube.com' in href or 'youtu.be' in href:
                print(f'YouTube ссылка: {href}')
        else:
            # Для всех других случаев, выводим текст элемента
            print(element.get_text())
else:
    print(f'Ошибка при запросе к {url}: Статус {response.status_code}')
