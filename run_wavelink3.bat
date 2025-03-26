@echo off
title Радио Вечер | Wavelink 3.x

echo ### Запуск Радио Вечер с поддержкой Wavelink 3.x ###
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
        echo # НАСТРОЙКИ LAVALINK
        echo USE_LAVALINK=true
        echo LAVALINK_HOST=localhost
        echo LAVALINK_PORT=2333
        echo LAVALINK_PASSWORD=youshallnotpass
        echo USE_INTERNAL_LAVALINK=true
        echo.
        echo # НАСТРОЙКИ РАДИО
        echo DEFAULT_VOLUME=50
        echo DEFAULT_RADIO=relax
    ) > .env
    echo ### Создан новый .env файл. Пожалуйста, добавьте ваш токен бота ###
    echo.
)

REM Проверка наличия Java (необходимо для Lavalink)
where java >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! ВНИМАНИЕ: Java не установлена. Lavalink требует Java 11 или выше !!!
    set USE_LAVALINK=false
    echo ### Отключаю Lavalink в настройках ###
    
    REM Заменяем настройку Lavalink в .env
    powershell -Command "(Get-Content -path .env -Raw) -replace 'USE_LAVALINK=true', 'USE_LAVALINK=false' | Set-Content -Path .env"
) else (
    REM Проверяем версию Java
    java -version 2>&1 | findstr /i "version" | findstr /r "11\|12\|13\|14\|15\|16\|17\|18\|19" >nul
    if %ERRORLEVEL% neq 0 (
        echo !!! ВНИМАНИЕ: Lavalink требует Java 11 или выше !!!
    ) else (
        echo ### Java установлена и соответствует требованиям ###
    )
)

echo ### Запуск бота ###
echo ### Первый запуск может занять больше времени из-за настройки Lavalink ###
echo ### Консоль откроется с выводом логов бота ###
echo.

python bot.py
pause 