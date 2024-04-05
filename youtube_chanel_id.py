import googleapiclient.discovery
from googleapiclient.errors import HttpError
import config  # Убедитесь, что ваш API ключ находится здесь

def search_channel_by_name(channel_name):
    # Создаем клиент API YouTube
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", developerKey=config.youtube_api)

    try:
        # Выполняем поиск канала по названию
        request = youtube.search().list(
            part="snippet",
            type="channel",
            q=channel_name,
            maxResults=1  # Ограничиваем результаты, чтобы получить наиболее релевантный канал
        )
        response = request.execute()

        # Проверяем, есть ли результаты
        if 'items' in response and response['items']:
            # Возвращаем информацию о первом найденном канале
            channel_info = response['items'][0]
            return {
                'channelId': channel_info['snippet']['channelId'],
                'title': channel_info['snippet']['title'],
                'description': channel_info['snippet']['description']
            }
        else:
            return None
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None

channel_name = 'studnia_jakuba'
channel_info = search_channel_by_name(channel_name)
if channel_info:
    print(f"Найден канал: {channel_info['title']}")
    print(f"ID канала: {channel_info['channelId']}")
    print(f"Описание: {channel_info['description']}")
else:
    print("Канал не найден.")
