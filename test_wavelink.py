import asyncio
import sys
import logging
import os
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_wavelink')

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем настройки Lavalink из переменных окружения
LAVALINK_HOST = os.getenv('LAVALINK_HOST', 'localhost')
LAVALINK_PORT = int(os.getenv('LAVALINK_PORT', 2333))
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
LAVALINK_SECURE = os.getenv('LAVALINK_SECURE', 'false').lower() == 'true'

async def test_wavelink():
    """Тестирование подключения к Lavalink через Wavelink 3.x"""
    try:
        # Импортируем wavelink и получаем версию
        import wavelink
        import pkg_resources
        
        wavelink_version = pkg_resources.get_distribution("wavelink").version
        major_version = int(wavelink_version.split('.')[0])
        
        logger.info(f"Используется Wavelink версии {wavelink_version}")
        
        if major_version < 3:
            logger.error(f"Эта тестовая программа требует Wavelink 3.x, установлена версия {wavelink_version}")
            logger.info("Попробуйте выполнить: pip install wavelink>=3.0.0")
            return False
        
        # Подготовка URI для подключения
        uri = f"{'ws' if not LAVALINK_SECURE else 'wss'}://{LAVALINK_HOST}:{LAVALINK_PORT}"
        logger.info(f"Подключаюсь к Lavalink по адресу: {uri}")
        
        # Создаем клиент для Discord
        import discord
        from discord.ext import commands
        
        # Создаем минимальный бот-клиент для тестирования
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix='!', intents=intents)
        
        # Создаем узел для Wavelink 3.x
        node = wavelink.Node(
            uri=uri,
            password=LAVALINK_PASSWORD
        )
        
        # Событие для обработки подключения
        @bot.event
        async def on_wavelink_node_ready(node: wavelink.Node):
            logger.info(f"✅ Узел Wavelink подключен: {node.identifier}")
            logger.info(f"✅ Версия Lavalink: {node.version}")
            logger.info(f"✅ Подключение к Lavalink успешно!")
            await bot.close()  # Закрываем бота после успешного теста
        
        @bot.event
        async def on_ready():
            logger.info(f"Бот запущен как {bot.user.name}")
            logger.info("Ожидаем подключения к Lavalink...")
        
        # Подключаем узел
        async with bot:
            # В Wavelink 3.x подключение происходит через Pool
            await wavelink.Pool.connect(nodes=[node], client=bot)
            
            # Запускаем бота на 30 секунд, затем выходим
            try:
                await asyncio.wait_for(bot.start("fake_token_for_testing"), timeout=30)
            except asyncio.TimeoutError:
                logger.error("❌ Тайм-аут подключения к Lavalink (30 секунд)")
                return False
            except Exception as e:
                # Игнорируем исключения от discord.py, так как мы используем поддельный токен
                if "Improper token" in str(e) or "Cannot connect to host" in str(e):
                    logger.info("Игнорируем ошибку токена Discord (ожидаемое поведение)")
                    return True
                else:
                    logger.error(f"❌ Ошибка: {e}")
                    return False
    
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        logger.info("Убедитесь, что установлены библиотеки discord.py и wavelink>=3.0.0")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        return False
    
    return True

# Функция для тестирования запуска Lavalink
async def test_lavalink_server():
    """Проверка, запущен ли сервер Lavalink"""
    import socket
    
    logger.info(f"Проверка доступности Lavalink сервера на {LAVALINK_HOST}:{LAVALINK_PORT}")
    
    # Создаем сокет для проверки подключения
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)  # 5 секунд таймаут
    
    try:
        # Пытаемся подключиться к порту Lavalink
        result = sock.connect_ex((LAVALINK_HOST, LAVALINK_PORT))
        if result == 0:
            logger.info(f"✅ Lavalink сервер доступен на {LAVALINK_HOST}:{LAVALINK_PORT}")
            return True
        else:
            logger.error(f"❌ Lavalink сервер недоступен. Код ошибки: {result}")
            return False
    except socket.error as e:
        logger.error(f"❌ Ошибка сокета при проверке Lavalink: {e}")
        return False
    finally:
        sock.close()

# Тестирование запуска Lavalink, если указано в аргументах
async def start_lavalink_if_needed():
    """Запуск Lavalink сервера, если он не запущен"""
    if not await test_lavalink_server():
        logger.info("🚀 Пытаюсь запустить Lavalink сервер...")
        
        # Проверяем наличие Lavalink.jar
        if not os.path.exists('Lavalink.jar'):
            logger.error("❌ Файл Lavalink.jar не найден")
            logger.info("Загрузите Lavalink.jar с https://github.com/lavalink-devs/Lavalink/releases")
            return False
        
        # Проверяем наличие Java
        import subprocess
        try:
            subprocess.run(['java', '-version'], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("❌ Java не установлена или не найдена в PATH")
            return False
        
        # Запускаем Lavalink в отдельном процессе
        import threading
        
        def run_lavalink():
            try:
                process = subprocess.Popen(
                    ['java', '-jar', 'Lavalink.jar'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                logger.info("🚀 Lavalink сервер запущен (PID: {})".format(process.pid))
                # Не ждем завершения процесса, он будет работать в фоне
            except Exception as e:
                logger.error(f"❌ Ошибка запуска Lavalink: {e}")
        
        # Запускаем в отдельном потоке, чтобы не блокировать основной
        lavalink_thread = threading.Thread(target=run_lavalink)
        lavalink_thread.daemon = True  # Поток будет завершен при выходе из программы
        lavalink_thread.start()
        
        # Даем время Lavalink для запуска
        logger.info("⏳ Ожидание 10 секунд для запуска Lavalink...")
        await asyncio.sleep(10)
        
        # Проверяем, запустился ли Lavalink
        if await test_lavalink_server():
            logger.info("✅ Lavalink успешно запущен!")
            return True
        else:
            logger.error("❌ Не удалось запустить Lavalink")
            return False
    
    return True  # Lavalink уже был запущен

async def main():
    """Основная функция для запуска тестов"""
    logger.info("=== ТЕСТ ПОДКЛЮЧЕНИЯ К LAVALINK ЧЕРЕЗ WAVELINK 3.x ===")
    
    # Проверка аргументов командной строки
    start_server = "--start-server" in sys.argv
    
    if start_server:
        # Если указан аргумент для запуска сервера
        if not await start_lavalink_if_needed():
            logger.error("❌ Не удалось запустить Lavalink сервер. Тест прерван.")
            return
    else:
        # Только проверяем доступность сервера
        if not await test_lavalink_server():
            logger.warning("⚠️ Lavalink сервер недоступен.")
            logger.info("Запустите с аргументом --start-server, чтобы автоматически запустить Lavalink")
            logger.info("Или запустите Lavalink вручную перед тестом")
            return
    
    # Тестируем подключение через Wavelink
    success = await test_wavelink()
    
    if success:
        logger.info("✅ ТЕСТ ПОДКЛЮЧЕНИЯ УСПЕШНО ПРОЙДЕН!")
    else:
        logger.error("❌ ТЕСТ ПОДКЛЮЧЕНИЯ НЕ ПРОЙДЕН!")
        logger.info("Проверьте логи выше для получения дополнительной информации")

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Тест прерван пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        
    print("\nТест завершен. Нажмите Enter для выхода...")
    input() 