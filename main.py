import json
import g4f


def ask_gpt(messages: list) -> str:
    response = g4f.ChatCompletion.create(
        model=g4f.models.gpt_35_turbo,
        messages=messages)
    return response


def load_article_content(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as file:
        articles = json.load(file)
    return articles


def process_articles(articles, output_json_file):
    results = []
    print(1)
    for article in articles:
        text = article['text']
        article_result = {
            "website": article['website'],
            "url": article['url'],
            "title": article['title']
        }
        print(2)
        article_result['translation_ru'] = ask_gpt([
            {"role": "system", "content": "Выполнить перевод текста на русский язык."},
            {"role": "user", "content": text}
        ])
        print(3)
        article_result['translation_ua'] = ask_gpt([
            {"role": "system", "content": "Выполнить перевод текста на украинский язык."},
            {"role": "user", "content": text}
        ])
        print(4)
        article_result['translation_by'] = ask_gpt([
            {"role": "system", "content": "Выполнить перевод текста на белорусский язык."},
            {"role": "user", "content": text}
        ])
        print(5)
        article_result['opinion'] = ask_gpt([
            {"role": "system", "content": "Представь, что ты журналист. Вырази своё мнение о данной статье."},
            {"role": "user", "content": text}
        ])
        print(6)
        results.append(article_result)

    with open(output_json_file, 'w', encoding='utf-8') as file:
        json.dump(results, file, ensure_ascii=False, indent=4)


output_json_file = "processed_articles_results.json"

articles = load_article_content("articles_info.json")
process_articles(articles, output_json_file)

print(f"Результаты обработки статей сохранены в файл '{output_json_file}'.")
