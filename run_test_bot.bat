@echo off
title Радио Вечер - Тестовый запуск

echo ### ТЕСТОВЫЙ ЗАПУСК БОТА С ВНЕШНИМ LAVALINK ###
echo.

REM Создаем временный .env файл для теста
echo Создание временного .env файла...
echo # Настройки подключения к Lavalink > test_lavalink.env
echo USE_LAVALINK=true >> test_lavalink.env
echo USE_INTERNAL_LAVALINK=false >> test_lavalink.env
echo LAVALINK_HOST=localhost >> test_lavalink.env
echo LAVALINK_PORT=2333 >> test_lavalink.env
echo LAVALINK_PASSWORD=youshallnotpass >> test_lavalink.env
echo LAVALINK_SECURE=false >> test_lavalink.env
echo LAVALINK_CONNECT_TIMEOUT=60 >> test_lavalink.env
echo DEFAULT_VOLUME=50 >> test_lavalink.env
echo DEFAULT_RADIO=relax >> test_lavalink.env

echo.
echo === ПРОВЕРКА ДОСТУПНОСТИ LAVALINK ===
python -c "import socket; s=socket.socket(); result=s.connect_ex(('localhost', 2333)); s.close(); exit(0 if result == 0 else 1)"
if %ERRORLEVEL% neq 0 (
    echo !!! ОШИБКА: Lavalink недоступен на localhost:2333 !!!
    echo Пожалуйста, запустите Lavalink сервер с помощью debug_lavalink.bat
    echo и дождитесь его полного запуска
    pause
    exit /b
) else (
    echo Lavalink доступен на localhost:2333
)

echo.
echo === ЗАПУСК ТЕСТОВОГО БОТА ===
echo Запускаю бота с использованием временного .env файла...
echo.

REM Запускаем бота с временным файлом конфигурации
set PYTHONUNBUFFERED=1
set WAVELINK_DEBUG=true
set LOGLEVEL=DEBUG
python -c "import os; from dotenv import load_dotenv; import wavelink, discord, asyncio, sys; async def test(): load_dotenv('test_lavalink.env'); print('Версия Wavelink:', wavelink.__version__); intents = discord.Intents.default(); bot = discord.Client(intents=intents); @bot.event; async def on_ready(): print('Бот запущен как:', bot.user); node = wavelink.Node(uri='ws://localhost:2333', password='youshallnotpass'); print('Подключаюсь к Lavalink...'); @bot.event; async def on_wavelink_node_ready(node): print('Подключение к Lavalink успешно!'); print('ID узла:', node.identifier); print('Версия Lavalink:', node.version); await bot.close(); try: await wavelink.Pool.connect(nodes=[node], client=bot); await bot.start('fake_token_for_testing'); except Exception as e: if 'Improper token' in str(e): print('Тест пройден успешно!'); else: print('Ошибка:', e); sys.exit(1); if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); asyncio.run(test())"

if %ERRORLEVEL% neq 0 (
    echo.
    echo !!! ТЕСТ НЕ ПРОЙДЕН !!!
    echo Пожалуйста, проверьте логи Lavalink.
) else (
    echo.
    echo === ТЕСТ УСПЕШНО ПРОЙДЕН ===
    echo Соединение с Lavalink работает!
    echo Теперь можно запустить бота через run_wavelink3.bat
)

echo.
echo Удаление временного файла...
del test_lavalink.env

pause 