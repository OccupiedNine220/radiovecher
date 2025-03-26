@echo off
title Радио Вечер - Lavalink Сервер

echo ### ЗАПУСК LAVALINK СЕРВЕРА ###
echo ### Этот скрипт запускает только Lavalink сервер (без бота) ###
echo.

REM Проверка наличия Java
where java >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! ОШИБКА: Java не установлена. Lavalink требует Java 11-21 !!!
    echo !!! Пожалуйста, установите Java с сайта https://adoptium.net/ !!!
    pause
    exit /b
)

REM Проверка наличия Lavalink.jar
if not exist Lavalink.jar (
    echo Lavalink.jar не найден. Загружаю последнюю версию...
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/lavalink-devs/Lavalink/releases/download/3.7.8/Lavalink.jar' -OutFile 'Lavalink.jar'}"
    
    if exist Lavalink.jar (
        echo Lavalink.jar успешно загружен
    ) else (
        echo !!! ОШИБКА: Не удалось загрузить Lavalink.jar !!!
        echo Пожалуйста, скачайте вручную с https://github.com/lavalink-devs/Lavalink/releases
        pause
        exit /b
    )
)

REM Проверка наличия application.yml
if not exist application.yml (
    echo application.yml не найден. Создаю новый файл конфигурации...
    (
        echo server:
        echo   port: 2333
        echo   address: 127.0.0.1
        echo.
        echo lavalink:
        echo   server:
        echo     password: "youshallnotpass"
        echo     sources:
        echo       youtube: true
        echo       bandcamp: true
        echo       soundcloud: true
        echo       twitch: true
        echo       vimeo: true
        echo       http: true
        echo       local: false
        echo     bufferDurationMs: 400
        echo     youtubePlaylistLoadLimit: 6
        echo     playerUpdateInterval: 5
        echo     youtubeSearchEnabled: true
        echo     soundcloudSearchEnabled: true
        echo     ratelimit:
        echo       ipBlocks: []
        echo       excludedIps: []
        echo       strategy: "RotateOnBan"
        echo       searchTriggersFail: true
        echo       retryLimit: -1
        echo.
        echo logging:
        echo   file:
        echo     max-history: 30
        echo     max-size: 1GB
        echo   path: ./logs/
        echo.
        echo   level:
        echo     root: INFO
        echo     lavalink: INFO
    ) > application.yml
    echo Файл application.yml создан с настройками по умолчанию
)

REM Освобождение порта 2333, если он занят
echo ### Проверка порта 2333 ###
netstat -ano | findstr ":2333" >nul
if %ERRORLEVEL% equ 0 (
    echo Порт 2333 уже используется. Пытаюсь освободить...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":2333"') do (
        echo Завершение процесса с PID: %%a
        taskkill /f /pid %%a >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            echo Процесс успешно завершен.
        ) else (
            echo Не удалось завершить процесс. Возможно, требуются права администратора.
        )
    )
) else (
    echo Порт 2333 свободен.
)
echo.

echo ### Запуск Lavalink сервера ###
echo Сервер запускается... Для остановки нажмите Ctrl+C в этом окне
echo.

REM Запуск Lavalink сервера
java -jar Lavalink.jar
echo.

echo Сервер остановлен. Нажмите любую клавишу для выхода...
pause 