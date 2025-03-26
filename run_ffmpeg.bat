@echo off
title Радио Вечер - Режим FFMPEG

echo ### ЗАПУСК БОТА В РЕЖИМЕ FFMPEG ###
echo ### Без использования Lavalink ###
echo.

REM Проверка наличия FFMPEG
where ffmpeg >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo !!! FFMPEG не найден !!!
    echo Запуск установки FFMPEG...
    call install_ffmpeg.bat
)

REM Изменение настроек в .env
echo Настройка .env для использования FFMPEG...
powershell -Command "& {$content = Get-Content -Path '.env' -Raw; if ($content -match 'USE_LAVALINK=true') { $content = $content -replace 'USE_LAVALINK=true', 'USE_LAVALINK=false'; Set-Content -Path '.env' -Value $content; Write-Host 'USE_LAVALINK установлен в false в файле .env' } else { Write-Host '.env уже настроен для использования FFMPEG или не найден' }}"

echo.
echo === ЗАПУСК БОТА В РЕЖИМЕ FFMPEG ===
echo.

set PYTHONUNBUFFERED=1
python bot.py

pause 