@echo off
title Радио Вечер - Тест Wavelink 3.x

echo ### ТЕСТ ПОДКЛЮЧЕНИЯ К LAVALINK ЧЕРЕЗ WAVELINK 3.x ###
echo.

REM Проверка наличия Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! ОШИБКА: Python не установлен. Установите Python 3.8 или выше !!!
    pause
    exit /b
)

REM Проверка наличия требуемых библиотек
echo ### Проверка библиотек ###
pip show wavelink >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Wavelink не установлен. Устанавливаю...
    pip install wavelink>=3.0.0
    if %ERRORLEVEL% neq 0 (
        echo !!! ОШИБКА: Не удалось установить Wavelink !!!
        pause
        exit /b
    )
)
echo.

REM Запуск теста
echo ### Запуск теста подключения ###
echo.

REM Выбор режима запуска
echo Выберите режим запуска:
echo 1 - Только тестирование подключения (предполагается, что Lavalink уже запущен)
echo 2 - Автоматический запуск Lavalink и тестирование подключения
echo.
set /p choice="Введите номер (1 или 2): "

if "%choice%"=="1" (
    echo Запуск теста без запуска Lavalink...
    python test_wavelink.py
)
if "%choice%"=="2" (
    echo Запуск теста с автоматическим запуском Lavalink...
    python test_wavelink.py --start-server
)

echo.
pause 