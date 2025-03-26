@echo off
title Радио Вечер - Установка FFMPEG

echo ### УСТАНОВКА FFMPEG ДЛЯ РАДИО ВЕЧЕР ###
echo.

REM Проверка наличия FFMPEG
where ffmpeg >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo FFMPEG уже установлен:
    ffmpeg -version | findstr "version"
    echo.
    echo Нажмите любую клавишу, чтобы выйти...
    pause
    exit /b
)

echo FFMPEG не найден, начинаю установку...
echo.

REM Создаем временную папку
if not exist temp mkdir temp
cd temp

echo Загрузка FFMPEG...
powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'ffmpeg.zip'}"

if not exist ffmpeg.zip (
    echo !!! ОШИБКА: Не удалось загрузить FFMPEG !!!
    cd ..
    pause
    exit /b
)

echo Распаковка FFMPEG...
powershell -Command "& {Expand-Archive -Path 'ffmpeg.zip' -DestinationPath '.' -Force}"

if not exist ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe (
    echo !!! ОШИБКА: Архив FFMPEG поврежден или имеет неверную структуру !!!
    cd ..
    pause
    exit /b
)

echo Копирование FFMPEG в корневую папку бота...
copy ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe ..\ /Y
copy ffmpeg-master-latest-win64-gpl\bin\ffplay.exe ..\ /Y
copy ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe ..\ /Y

cd ..

echo Проверка установки FFMPEG...
if exist ffmpeg.exe (
    echo FFMPEG успешно установлен!
) else (
    echo !!! ОШИБКА: Не удалось установить FFMPEG !!!
    pause
    exit /b
)

echo.
echo Изменение .env для использования FFMPEG вместо Lavalink...
powershell -Command "& {$content = Get-Content -Path '.env' -Raw; if ($content -match 'USE_LAVALINK=true') { $content = $content -replace 'USE_LAVALINK=true', 'USE_LAVALINK=false'; Set-Content -Path '.env' -Value $content; Write-Host 'USE_LAVALINK установлен в false в файле .env' } else { Write-Host '.env уже настроен для использования FFMPEG или не найден' }}"

echo.
echo Очистка временных файлов...
rmdir /S /Q temp

echo.
echo === УСТАНОВКА ЗАВЕРШЕНА ===
echo Теперь бот будет использовать FFMPEG вместо Lavalink.
echo Запустите бота с помощью run_ffmpeg.bat
echo.
pause 