@echo off
title Радио Вечер - Отладка Lavalink

echo ### ЗАПУСК LAVALINK В РЕЖИМЕ ОТЛАДКИ ###
echo.

REM Завершаем все процессы Java, которые могут использовать порт 2333
echo Завершение всех процессов Java...
taskkill /F /IM java.exe /T >nul 2>nul

REM Проверяем, используется ли порт 2333
echo Проверка порта 2333...
netstat -ano | findstr ":2333" >nul
if %ERRORLEVEL% equ 0 (
    echo Порт 2333 занят, пытаюсь освободить...
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":2333"') do (
        echo Завершение процесса с PID: %%p
        taskkill /F /PID %%p >nul 2>nul
    )
)

REM Проверяем наличие application.yml
if not exist application.yml (
    echo !!! ОШИБКА: Файл application.yml не найден !!!
    echo Создаю файл application.yml...
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
        echo     root: DEBUG
        echo     lavalink: DEBUG
    ) > application.yml
    echo Файл application.yml создан
) else (
    echo Файл application.yml найден
    echo Изменяю уровень логирования на DEBUG...
    powershell -Command "& {$content = Get-Content -Path 'application.yml' -Raw; $content = $content -replace 'level:\s*root:\s*INFO', 'level:\r\n    root: DEBUG'; $content = $content -replace 'lavalink:\s*INFO', 'lavalink: DEBUG'; Set-Content -Path 'application.yml' -Value $content }"
)

REM Проверяем наличие Java
echo Проверка Java...
java -version
if %ERRORLEVEL% neq 0 (
    echo !!! ОШИБКА: Java не установлена !!!
    echo Пожалуйста, установите Java 11 или более новую версию
    pause
    exit /b
)

REM Проверяем наличие Lavalink.jar
if not exist Lavalink.jar (
    echo !!! ОШИБКА: Файл Lavalink.jar не найден !!!
    echo Скачиваем Lavalink.jar версии 3.7.5...
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/lavalink-devs/Lavalink/releases/download/3.7.5/Lavalink.jar' -OutFile 'Lavalink.jar'}"
    if %ERRORLEVEL% neq 0 (
        echo !!! ОШИБКА: Не удалось скачать Lavalink.jar !!!
        pause
        exit /b
    )
    echo Lavalink.jar успешно скачан
) else (
    echo Файл Lavalink.jar найден
    echo Размер файла:
    dir Lavalink.jar
)

echo.
echo === ПОДРОБНАЯ ИНФОРМАЦИЯ О СИСТЕМЕ ===
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
echo.

echo === JAVA ВЕРСИЯ ===
java -version
echo.

echo === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ JAVA ===
echo JAVA_HOME = %JAVA_HOME%
echo PATH = %PATH%
echo.

echo === ЗАПУСК LAVALINK С ОТЛАДОЧНОЙ ИНФОРМАЦИЕЙ ===
echo Для остановки сервера нажмите Ctrl+C
echo.

REM Запускаем Lavalink с дополнительными параметрами для отладки
java -Xmx1G -jar Lavalink.jar --trace

pause 