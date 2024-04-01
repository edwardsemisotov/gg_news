import json
import requests
from newspaper import Article
from requests.exceptions import SSLError

with open('links.json', 'r') as file:
    data = json.load(file)
articles_info = []

for website, urls in data.items():
    print("Сайт:", website)
    for url in urls:
        try:
            response = requests.get(url, verify=False)
            article = Article(url)
            article.download(input_html=response.text)
            article.parse()
            article.nlp()
            images = list(article.images)
            movies = list(article.movies)
            article_info = {
                "website": website,
                "url": url,
                "title": article.title,
                "text": article.text,
                "summary": article.summary,  #
                "images": images,
                "videos": movies
            }
            articles_info.append(article_info)
            print("Link:", url)
            print("Заголовок статьи:", article.title)
            print("Текст статьи:", article.text)
            print("Резюме статьи:", article.summary)  # Вывод резюме статьи
            print("Изображения:", images)
            print("Видео:", movies)
            print("----------------------------------------")
        except SSLError as e:
            print(f"Произошла ошибка SSL при загрузке {url}: {e}")
        except Exception as e:
            print(f"Произошла ошибка при обработке статьи {url}: {e}")

with open('articles_info.json', 'w') as file:
    json.dump(articles_info, file, indent=4)
