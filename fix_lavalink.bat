@echo off
title Радио Вечер - Исправление Lavalink

echo ### УТИЛИТА ИСПРАВЛЕНИЯ LAVALINK ДЛЯ РАДИО ВЕЧЕР ###
echo ### Эта утилита поможет диагностировать и исправить проблемы с Lavalink ###
echo.

REM Проверка Java
echo ### Проверка Java ###
where java >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! ОШИБКА: Java не установлена! Lavalink требует Java 11-21 !!!
    echo !!! Пожалуйста, установите Java с сайта https://adoptium.net/ !!!
    pause
    exit /b
)

REM Проверка версии Java
java -version 2>&1 | findstr /i "version" | findstr /i "11\|17\|21" >nul
if %ERRORLEVEL% neq 0 (
    echo !!! ВНИМАНИЕ: Lavalink лучше всего работает с Java 11, 17 или 21 !!!
    echo !!! У вас может быть установлена несовместимая версия Java !!!
    echo.
) else (
    echo ### Версия Java совместима с Lavalink ###
    echo.
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

REM Удаление старого Lavalink.jar
echo ### Проверка Lavalink.jar ###
if exist Lavalink.jar (
    echo Найден существующий Lavalink.jar
    echo Размер файла:
    dir Lavalink.jar | findstr "Lavalink.jar"
    
    choice /C YN /M "Хотите заменить существующий Lavalink.jar новой версией?"
    if %ERRORLEVEL% equ 1 (
        echo Удаляю существующий Lavalink.jar...
        del /f Lavalink.jar
        echo Файл удален.
    ) else (
        echo Сохраняю существующий Lavalink.jar.
    )
) else (
    echo Lavalink.jar не найден. Будет загружена новая версия.
)
echo.

REM Загрузка нового Lavalink.jar, если нужно
if not exist Lavalink.jar (
    echo ### Загрузка Lavalink.jar ###
    echo Загружаю последнюю стабильную версию Lavalink...
    
    powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/lavalink-devs/Lavalink/releases/download/3.7.8/Lavalink.jar' -OutFile 'Lavalink.jar'}"
    
    if exist Lavalink.jar (
        echo Загрузка успешно завершена!
        echo Размер файла:
        dir Lavalink.jar | findstr "Lavalink.jar"
    ) else (
        echo !!! ОШИБКА: Не удалось загрузить Lavalink.jar !!!
        echo Пожалуйста, проверьте подключение к интернету и попробуйте снова.
    )
)
echo.

REM Создание application.yml для Lavalink, если его нет
if not exist application.yml (
    echo ### Создание файла конфигурации application.yml ###
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
    echo Файл application.yml создан.
) else (
    echo Файл application.yml уже существует.
)
echo.

REM Проверка Wavelink
echo ### Проверка библиотеки Wavelink ###
pip show wavelink | findstr "Version"
if %ERRORLEVEL% neq 0 (
    echo Wavelink не установлен. Устанавливаю версию 3.x...
    pip install "wavelink>=3.0.0"
) else (
    echo Wavelink установлен. Проверка версии:
    python -c "import wavelink; import pkg_resources; print(f'Wavelink версия: {pkg_resources.get_distribution(\"wavelink\").version}')"
    
    REM Проверяем, что версия 3.x
    python -c "import wavelink; import pkg_resources; version = pkg_resources.get_distribution('wavelink').version; major = int(version.split('.')[0]); exit(0 if major >= 3 else 1)"
    
    if %ERRORLEVEL% neq 0 (
        echo !!! У вас установлена устаревшая версия Wavelink !!!
        echo Обновляю до версии 3.x...
        pip install --upgrade "wavelink>=3.0.0"
    ) else (
        echo Установлена совместимая версия Wavelink.
    )
)
echo.

REM Проверка параметров .env файла
echo ### Проверка .env файла ###
if exist .env (
    echo .env файл найден.
    
    REM Проверяем и исправляем параметры Lavalink
    powershell -Command "& {$content = Get-Content -Path '.env' -Raw; if ($content -match 'USE_LAVALINK=false') { $content = $content -replace 'USE_LAVALINK=false', 'USE_LAVALINK=true'; Set-Content -Path '.env' -Value $content; Write-Host 'Параметр USE_LAVALINK установлен в true.' } else { Write-Host 'Параметр USE_LAVALINK уже установлен правильно.' }}"
    
    powershell -Command "& {$content = Get-Content -Path '.env' -Raw; if ($content -match 'USE_INTERNAL_LAVALINK=false') { $content = $content -replace 'USE_INTERNAL_LAVALINK=false', 'USE_INTERNAL_LAVALINK=true'; Set-Content -Path '.env' -Value $content; Write-Host 'Параметр USE_INTERNAL_LAVALINK установлен в true.' } else { Write-Host 'Параметр USE_INTERNAL_LAVALINK уже установлен правильно или отсутствует.' }}"
    
    echo Настройки Lavalink из .env:
    type .env | findstr "LAVALINK" | findstr /V "PASSWORD"
) else (
    echo !!! .env файл не найден !!!
    echo Создаю базовый .env файл...
    (
        echo # НАСТРОЙКИ LAVALINK
        echo USE_LAVALINK=true
        echo USE_INTERNAL_LAVALINK=true
        echo LAVALINK_HOST=localhost
        echo LAVALINK_PORT=2333
        echo LAVALINK_PASSWORD=youshallnotpass
        echo LAVALINK_SECURE=false
        echo LAVALINK_JAR_PATH=./Lavalink.jar
    ) > .env
    echo Базовый .env файл создан. Добавьте токен бота и другие настройки.
)
echo.

echo ### Тестовый запуск Lavalink ###
echo Запускаю Lavalink для проверки...
echo Это может занять несколько секунд...

REM Запускаем Lavalink в фоновом режиме на 10 секунд
start /B cmd /c "java -jar Lavalink.jar & timeout /t 10 > nul & taskkill /f /im java.exe /fi "WINDOWTITLE eq Lavalink""

REM Ждем немного, чтобы Lavalink успел запуститься
timeout /t 5 > nul

REM Проверяем, запустился ли Lavalink
netstat -ano | findstr ":2333" >nul
if %ERRORLEVEL% equ 0 (
    echo Lavalink успешно запущен на порту 2333!
) else (
    echo !!! Lavalink не удалось запустить на порту 2333 !!!
    echo Проверьте логи на наличие ошибок.
)

echo.
echo ### ДИАГНОСТИКА ЗАВЕРШЕНА ###
echo.
echo Для запуска бота с Lavalink используйте скрипт run_wavelink3.bat
echo Для отладки используйте debug.bat
echo.
pause 