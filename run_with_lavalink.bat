@echo off
echo === ЗАПУСК РАДИО ВЕЧЕР С LAVALINK ===
echo Проверка зависимостей...

REM Проверка наличия Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден! Установите Python 3.8 или новее.
    pause
    exit /b 1
)

REM Проверка наличия Java (для Lavalink)
java -version > nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Java не найдена! Для работы Lavalink необходима Java 13 или новее.
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

REM Включаем Lavalink в конфигурации
echo Настройка Lavalink в .env...
powershell -Command "(Get-Content .env) -replace 'USE_LAVALINK=false', 'USE_LAVALINK=true' | Set-Content .env"

echo Проверка установленных библиотек...
pip install -r requirements.txt > nul 2>&1

echo Запуск Радио Вечер с Lavalink...
echo Примечание: первый запуск может занять некоторое время, так как бот скачает Lavalink сервер.
python bot.py

pause 