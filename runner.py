import subprocess
import time

intervals = {
    "youtube_link_collector.py": 7200,
    "news_link_collector.py": 60,
    "info_extractor.py": 60,
    "tg.py": 60
}

last_run = {script: 0 for script in intervals}

while True:
    current_time = time.time()
    for script, interval in intervals.items():
        if current_time - last_run[script] >= interval:
            print(f"Запуск {script}...")
            subprocess.run(["python", script], check=True)
            last_run[script] = current_time
    time.sleep(1)
