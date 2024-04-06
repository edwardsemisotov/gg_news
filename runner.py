import subprocess
import time

# Список скриптов для выполнения
scripts = [
    "news_link_collector.py",
    "info_extractor.py",
    "tg.py"
]

# Основной цикл
while True:
    for script in scripts:
        # Запускаем скрипт
        print(f"Запуск {script}...")
        subprocess.run(["python", script], check=True)

        # Ждем 10 минут перед запуском следующего скрипта
        time.sleep(600)
