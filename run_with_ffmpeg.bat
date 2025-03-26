@echo off
echo === ЗАПУСК РАДИО ВЕЧЕР С FFMPEG ===
echo Проверка зависимостей...

REM Проверка наличия Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден! Установите Python 3.8 или новее.
    pause
    exit /b 1
)

REM Проверка наличия файла .env
if not exist .env (
    echo ПРЕДУПРЕЖДЕНИЕ: Файл .env не найден. Копирую из .env.example...
    copy .env.example .env > nul 2>&1
    if %errorlevel% neq 0 (
        echo ОШИБКА: Не удалось создать файл .env!
        pause
        exit /b 1
    )
    echo Файл .env создан! Откройте его и укажите токен бота и ID приложения.
    notepad .env
    pause
    exit /b 0
)

REM Отключаем Lavalink в конфигурации
echo Настройка FFMPEG в .env...
powershell -Command "(Get-Content .env) -replace 'USE_LAVALINK=true', 'USE_LAVALINK=false' | Set-Content .env"

echo Проверка установленных библиотек...
pip install -r requirements.txt > nul 2>&1

echo Запуск Радио Вечер с FFMPEG...
python bot.py

pause 