@echo off
title Радио Вечер - Режим отладки

echo ### РЕЖИМ ОТЛАДКИ РАДИО ВЕЧЕР ###
echo ### Сбор информации о системе ###
echo.

echo ### Информация о системе ###
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
echo.

echo ### Версия Python ###
python --version
echo.

echo ### Установленные библиотеки ###
pip list | findstr "discord wavelink python-dotenv Flask spotipy"
echo.

REM Добавлена проверка точной версии wavelink
echo ### Детальная информация о Wavelink ###
python -c "import wavelink; import pkg_resources; print(f'Wavelink версия: {pkg_resources.get_distribution(\"wavelink\").version}')"
python -c "import wavelink; print(f'Доступные классы Wavelink: {dir(wavelink)}')"
echo.

echo ### Версия Java ###
java -version 2>&1
echo.

echo ### Проверка наличия Lavalink.jar ###
if exist Lavalink.jar (
    echo Lavalink.jar найден
    echo Размер файла:
    dir Lavalink.jar | findstr "Lavalink.jar"
) else (
    echo Lavalink.jar не найден в корневой директории
)
echo.

echo ### Проверка портов Lavalink ###
netstat -ano | findstr ":2333"
echo.

echo ### Проверка наличия FFMPEG ###
where ffmpeg 2>nul
if %ERRORLEVEL% neq 0 (
    echo FFMPEG не найден в системном пути
) else (
    echo FFMPEG найден
    ffmpeg -version | findstr "version"
)
echo.

echo ### Проверка .env файла ###
if exist .env (
    echo .env файл найден
    echo Содержимое файла .env:
    type .env | findstr /V "TOKEN" | findstr /V "SECRET"
    
    REM Проверка конфигурации Lavalink в .env
    echo.
    echo ### Настройки Lavalink из .env ###
    type .env | findstr "LAVALINK" | findstr /V "PASSWORD"
) else (
    echo .env файл не найден
)
echo.

echo ### Проверка файла config.py ###
if exist config.py (
    echo config.py найден
    echo Список радиостанций:
    python -c "import config; print('\n'.join([f'{key}: {value.get(\"name\", \"Без имени\")}' for key, value in config.radios.items()]))"
) else (
    echo config.py не найден
)
echo.

echo ### Запуск бота в режиме отладки с расширенным логированием ###
echo.
set PYTHONUNBUFFERED=1
set WAVELINK_DEBUG=true
set LOGLEVEL=DEBUG
python -u bot.py
pause 