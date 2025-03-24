@echo off
setlocal

echo *******************************
echo *    ЗАПУСК РАДИО ВЕЧЕР    *
echo *******************************
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не установлен!
    echo Установите Python 3.10 или 3.11 с сайта python.org
    echo.
    echo Нажмите любую клавишу для выхода.
    pause >nul
    exit /b 1
)

for /f "tokens=2" %%I in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%I"
echo Обнаружен Python %PYTHON_VERSION%

REM Проверка файла .env
if not exist .env (
    echo ОШИБКА: Файл .env не найден!
    echo Создайте файл .env и заполните все параметры.
    echo.
    echo Нажмите любую клавишу для выхода.
    pause >nul
    exit /b 1
)

REM Проверка наличия Java для Lavalink
java -version >nul 2>&1
if %errorlevel% neq 0 (
    echo ВНИМАНИЕ: Java не установлена!
    echo Для работы с Lavalink нужна Java 11 или выше.
    set "USE_LAVALINK=false"
) else (
    echo Обнаружена Java, Lavalink может быть использован.
    set "USE_LAVALINK=true"
)

REM Установка зависимостей
echo Установка библиотек...
pip install -r requirements.txt

REM Запуск бота
echo.
echo Запуск РАДИО ВЕЧЕР...
echo.
python bot.py

echo.
echo Нажмите любую клавишу для выхода.
pause >nul