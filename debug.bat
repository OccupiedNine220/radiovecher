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

echo ### Версия Java ###
java -version 2>&1
echo.

echo ### Проверка наличия FFMPEG ###
where ffmpeg 2>nul
if %ERRORLEVEL% neq 0 (
    echo FFMPEG не найден в системном пути
) else (
    echo FFMPEG найден
)
echo.

echo ### Проверка .env файла ###
if exist .env (
    echo .env файл найден
    echo Содержимое файла .env:
    type .env | findstr /V "TOKEN" | findstr /V "SECRET"
) else (
    echo .env файл не найден
)
echo.

echo ### Запуск бота в режиме отладки ###
echo.
set PYTHONUNBUFFERED=1
python -u bot.py
pause 