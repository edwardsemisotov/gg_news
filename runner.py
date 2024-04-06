import subprocess
import time

scripts = [
    "news_link_collector.py",
    "info_extractor.py",
    "tg.py"
]

while True:
    for script in scripts:
        # Запускаем скрипт
        print(f"Запуск {script}...")
        subprocess.run(["python", script], check=True)

        # Ждем 10 минут перед запуском следующего скрипта
        time.sleep(600)
