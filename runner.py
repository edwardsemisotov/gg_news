import subprocess
import time

intervals = {
    "youtube_link_collector.py": 3600,  # каждый час
    "news_link_collector.py": 300,  # каждые 5 минут
    "info_extractor.py": 60,  # каждую минуту
    "tg.py": 60  # каждую минуту
}

last_run = {script: 0 for script in intervals}

while True:
    current_time = time.time()
    for script, interval in intervals.items():
        # Проверяем, прошло ли достаточно времени с момента последнего запуска
        if current_time - last_run[script] >= interval:
            print(f"Запуск {script}...")
            subprocess.run(["python", script], check=True)
            last_run[script] = current_time
    time.sleep(1)
