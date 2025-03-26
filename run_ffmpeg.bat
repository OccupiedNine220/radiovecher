@echo off
title Радио Вечер | FFMPEG Режим

echo ### Запуск Радио Вечер с использованием FFMPEG ###
echo.

REM Проверка наличия Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! ОШИБКА: Python не установлен. Установите Python 3.8 или выше !!!
    pause
    exit /b
)

REM Проверка версии Python
python --version | findstr /r "3\.[8-9]\|3\.1[0-9]" >nul
if %ERRORLEVEL% neq 0 (
    echo !!! ВНИМАНИЕ: Возможно установлена неподдерживаемая версия Python. Рекомендуется Python 3.8 или выше !!!
)

echo ### Проверка наличия необходимых библиотек ###
pip install -r requirements.txt
echo.

REM Проверка наличия .env файла
if not exist .env (
    echo ### .env файл не найден. Создаю новый .env файл ###
    (
        echo # ТОКЕН DISCORD БОТА - НЕОБХОДИМО ЗАПОЛНИТЬ!
        echo BOT_TOKEN=
        echo.
        echo # ОТКЛЮЧЕНИЕ LAVALINK - ИСПОЛЬЗУЕМ FFMPEG
        echo USE_LAVALINK=false
        echo.
        echo # НАСТРОЙКИ РАДИО
        echo DEFAULT_VOLUME=50
        echo DEFAULT_RADIO=relax
    ) > .env
    echo ### Создан новый .env файл. Пожалуйста, добавьте ваш токен бота ###
    echo.
) else (
    echo ### Настройка .env для использования FFMPEG ###
    powershell -Command "(Get-Content -path .env -Raw) -replace 'USE_LAVALINK=true', 'USE_LAVALINK=false' | Set-Content -Path .env"
)

REM Поиск и уведомление о наличии FFMPEG
where ffmpeg >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! ВНИМАНИЕ: FFMPEG не найден в системном пути !!!
    echo !!! Для работы с аудио требуется FFMPEG !!!
    echo !!! Скачайте его с https://ffmpeg.org/download.html !!!
    echo !!! Или установите через команду: pip install ffmpeg-python !!!
    echo.
) else (
    echo ### FFMPEG найден, аудио будет работать корректно ###
)

echo ### Запуск бота ###
echo ### Бот запускается в режиме FFMPEG (без Lavalink) ###
echo.

python bot.py
pause 