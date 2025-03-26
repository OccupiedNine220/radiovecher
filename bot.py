import os
import sys
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from music_player import MusicPlayer

# 🌐 ИМПОРТ ВЕБ-СЕРВЕРА - БЕЗ НЕГО НИЧЕГО НЕ РАБОТАЕТ!!! 🌐
try:
    from web.server import initialize_web_server, get_web_url
    WEB_ENABLED = True
except ImportError:
    print("⚠️ ВЕБ-СЕРВЕР НЕ ЗАГРУЖЕН!!! ПРОВЕРЬТЕ НАЛИЧИЕ ДИРЕКТОРИИ 'web' И ЗАВИСИМОСТЕЙ!!! ⚠️")
    WEB_ENABLED = False

# 📝 НАСТРОЙКА ЛОГИРОВАНИЯ - ВАЖНО ДЛЯ ОТСЛЕЖИВАНИЯ СОБЫТИЙ!!! 📝
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot')

# 🔑 ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ - БЕЗ ЭТОГО БОТ НЕ ЗАПУСТИТСЯ!!! 🔑
load_dotenv()

# 🎯 ПОЛУЧЕНИЕ ТОКЕНА БОТА - КРИТИЧЕСКИ ВАЖНО!!! 🎯
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    TOKEN = os.getenv('DISCORD_TOKEN')  # Пробуем альтернативное имя переменной
    
# 🆔 ПОЛУЧЕНИЕ ID ПРИЛОЖЕНИЯ - ДЛЯ СЛЭШ-КОМАНД!!! 🆔
APP_ID = os.getenv('APPLICATION_ID')
if not APP_ID:
    logger.warning("⚠️ ID ПРИЛОЖЕНИЯ НЕ НАЙДЕН В .env ФАЙЛЕ!!! СЛЭШ-КОМАНДЫ МОГУТ НЕ РАБОТАТЬ!!! ⚠️")
    APP_ID = None  # Явно устанавливаем None
    
# 🔍 ПРОВЕРКА ТОКЕНА - ЖИЗНЕННО НЕОБХОДИМО!!! 🔍
if not TOKEN:
    logger.error("❌ ОШИБКА: ТОКЕН БОТА НЕ НАЙДЕН В .env ФАЙЛЕ!!! НЕМЕДЛЕННО ИСПРАВЬТЕ!!! ❌")
    sys.exit(1)

# ⚙️ НАСТРОЙКА LAVALINK - ДЛЯ ИДЕАЛЬНОГО КАЧЕСТВА ЗВУКА!!! ⚙️
USE_LAVALINK = os.getenv('USE_LAVALINK', 'false').lower() == 'true'
DEFAULT_VOLUME = int(os.getenv('DEFAULT_VOLUME', '50'))
DEFAULT_RADIO = os.getenv('DEFAULT_RADIO', 'relax')

# 🎵 ИМПОРТ КОНФИГУРАЦИИ РАДИОСТАНЦИЙ!!! 🎵
try:
    from config import radios
except ImportError:
    logger.error("❌ ОШИБКА: ФАЙЛ КОНФИГУРАЦИИ РАДИОСТАНЦИЙ НЕ НАЙДЕН!!! ❌")
    radios = {}
    sys.exit(1)

# 🎛️ УСЛОВНЫЙ ИМПОРТ LAVALINK ПЛЕЕРА - ТОЛЬКО ЕСЛИ НУЖЕН!!! 🎛️
if USE_LAVALINK:
    try:
        from lavalink_player import LavalinkPlayer, download_and_start_lavalink
        LAVALINK_AVAILABLE = True
        logger.info("✅ LAVALINK ИМПОРТИРОВАН УСПЕШНО!!! БУДЕТ ИСПОЛЬЗОВАН ДЛЯ ВОСПРОИЗВЕДЕНИЯ!!! ✅")
    except ImportError as e:
        logger.error(f"❌ ОШИБКА ИМПОРТА LAVALINK: {e}!!! БУДЕТ ИСПОЛЬЗОВАН ОБЫЧНЫЙ ПЛЕЕР!!! ❌")
        USE_LAVALINK = False
        LAVALINK_AVAILABLE = False
else:
    LAVALINK_AVAILABLE = False
    logger.info("ℹ️ LAVALINK ОТКЛЮЧЕН В НАСТРОЙКАХ!!! БУДЕТ ИСПОЛЬЗОВАН ОБЫЧНЫЙ ПЛЕЕР!!! ℹ️")

# 🧠 НАСТРОЙКА ИНТЕНТОВ БОТА - ВСЕ ДОЛЖНЫ БЫТЬ ВКЛЮЧЕНЫ!!! 🧠
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

# 🤖 СОЗДАНИЕ ЭКЗЕМПЛЯРА БОТА - ОСНОВА ВСЕГО ПРОЕКТА!!! 🤖
bot = commands.Bot(
    command_prefix=os.getenv('COMMAND_PREFIX', '/'),
    intents=intents,
    application_id=APP_ID  # Используем переменную вместо прямого обращения к os.getenv
)

# 🎵 СЛОВАРЬ ДЛЯ ХРАНЕНИЯ МУЗЫКАЛЬНЫХ ПЛЕЕРОВ - КАЖДОМУ СЕРВЕРУ СВОЙ!!! 🎵
bot.players = {}

# 📻 НАСТРОЙКА ДОСТУПНЫХ РАДИОСТАНЦИЙ - ТОЛЬКО ЛУЧШИЕ СТАНЦИИ!!! 📻
bot.available_radios = radios
bot.current_radio = bot.available_radios.get(DEFAULT_RADIO, list(bot.available_radios.values())[0])

# 🚀 СОХРАНЯЕМ СОСТОЯНИЕ LAVALINK ДЛЯ ИСПОЛЬЗОВАНИЯ В ДРУГИХ МОДУЛЯХ!!! 🚀
bot.use_lavalink = USE_LAVALINK
bot.lavalink_available = LAVALINK_AVAILABLE
bot.wavelink_node = None  # Будет установлен если Lavalink запустится успешно

# 🔄 ПЕРЕКЛЮЧЕНИЕ НА ДРУГУЮ РАДИОСТАНЦИЮ - МГНОВЕННАЯ СМЕНА НАСТРОЕНИЯ!!! 🔄
def switch_radio(radio_key):
    """🔀 ПЕРЕКЛЮЧЕНИЕ НА ДРУГУЮ РАДИОСТАНЦИЮ - ВЫБИРАЙ ЛЮБИМУЮ МУЗЫКУ!!! 🔀"""
    if radio_key in bot.available_radios:
        bot.current_radio = bot.available_radios[radio_key]
        return bot.current_radio
    return None

# 💾 СОХРАНЕНИЕ ФУНКЦИИ ПЕРЕКЛЮЧЕНИЯ РАДИОСТАНЦИЙ В ЭКЗЕМПЛЯРЕ БОТА!!! 💾
bot.switch_radio = switch_radio

@bot.event
async def on_ready():
    """✅ ВЫЗЫВАЕТСЯ ПРИ УСПЕШНОМ ЗАПУСКЕ БОТА - САМЫЙ ВАЖНЫЙ МОМЕНТ!!! ✅"""
    logger.info(f'🚀 БОТ ЗАПУЩЕН КАК {bot.user.name}#{bot.user.discriminator}!!! РАДУЙСЯ!!! 🚀')
    logger.info(f'🆔 ID БОТА: {bot.user.id}!!! ЗАПОМНИ ЕГО НА ВСЯКИЙ СЛУЧАЙ!!! 🆔')
    logger.info(f'🌍 КОЛ-ВО СЕРВЕРОВ: {len(bot.guilds)}!!! СКОРО БУДЕТ БОЛЬШЕ!!! 🌍')
    
    # 📢 ВЫВОДИМ ССЫЛКУ ДЛЯ ПРИГЛАШЕНИЯ - ПРИГЛАСИ БОТА НА ДРУГИЕ СЕРВЕРЫ!!! 📢
    invite_url = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot+applications.commands&permissions=139623525440"
    logger.info(f"🔗 ССЫЛКА ДЛЯ ПРИГЛАШЕНИЯ БОТА: {invite_url}!!! ПОДЕЛИСЬ С ДРУЗЬЯМИ!!! 🔗")
    
    # 🎭 УСТАНАВЛИВАЕМ СТАТУС - ПУСТЬ ВСЕ ВИДЯТ, ЧТО БОТ КРУТОЙ!!! 🎭
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name=f"/help | {bot.current_radio['name']}"
        )
    )

    # 🌐 ЗАПУСК ВЕБ-СЕРВЕРА - ДЛЯ УДОБНОГО УПРАВЛЕНИЯ!!! 🌐
    if WEB_ENABLED:
        initialize_web_server(bot)
        logger.info(f'🌐 ВЕБ-СЕРВЕР ЗАПУЩЕН ПО АДРЕСУ: {get_web_url()}!!! ОТКРОЙ В БРАУЗЕРЕ!!! 🌐')
    else:
        logger.warning("⚠️ ВЕБ-СЕРВЕР ОТКЛЮЧЕН!!! НЕКОТОРЫЕ ФУНКЦИИ БУДУТ НЕДОСТУПНЫ!!! ⚠️")

@bot.event
async def on_voice_state_update(member, before, after):
    """👂 ОБРАБОТЧИК ИЗМЕНЕНИЙ СОСТОЯНИЯ ГОЛОСОВЫХ КАНАЛОВ - СЛЕДИМ ЗА ВСЕМ!!! 👂"""
    # 🔍 ПРОВЕРЯЕМ, ОТНОСИТСЯ ЛИ ЭТО ИЗМЕНЕНИЕ К БОТУ!!! 🔍
    if member.id == bot.user.id:
        # 🔌 ЕСЛИ БОТ ОТКЛЮЧИЛСЯ ОТ ГОЛОСОВОГО КАНАЛА!!! 🔌
        if before.channel and not after.channel:
            guild_id = before.channel.guild.id
            # 🗑️ УДАЛЯЕМ ПЛЕЕР ДЛЯ ЭТОЙ ГИЛЬДИИ, ЕСЛИ ОН СУЩЕСТВУЕТ!!! 🗑️
            if guild_id in bot.players:
                player = bot.players[guild_id]
                await player.cleanup()
                del bot.players[guild_id]
                logger.info(f'🧹 ПЛЕЕР УДАЛЕН ДЛЯ СЕРВЕРА {guild_id} ПОСЛЕ ОТКЛЮЧЕНИЯ ОТ КАНАЛА!!! 🧹')

# 📚 ЗАГРУЗКА КОГОВ С КОМАНДАМИ - МНОЖЕСТВО УДОБНЫХ ФУНКЦИЙ!!! 📚
async def load_extensions():
    """📥 ЗАГРУЗКА МОДУЛЕЙ С КОМАНДАМИ - РАСШИРЯЕМ ВОЗМОЖНОСТИ БОТА!!! 📥"""
    try:
        # 📂 ЗАГРУЗКА ВСЕХ КОГОВ ИЗ ПАПКИ COGS!!! 📂
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'📦 ЗАГРУЖЕН МОДУЛЬ: cogs.{filename[:-3]}!!! ЕЩЕ БОЛЬШЕ ФУНКЦИЙ!!! 📦')
    except Exception as e:
        logger.error(f'❌ ОШИБКА ПРИ ЗАГРУЗКЕ МОДУЛЕЙ: {e}!!! СРОЧНО ИСПРАВЬТЕ!!! ❌')

# 🎮 ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ПОДХОДЯЩЕГО ПЛЕЕРА ДЛЯ ГИЛЬДИИ!!! 🎮
async def get_player(guild):
    """🎧 ВОЗВРАЩАЕТ ЭКЗЕМПЛЯР ПЛЕЕРА ДЛЯ ГИЛЬДИИ - УНИКАЛЬНЫЙ ДЛЯ КАЖДОГО СЕРВЕРА!!! 🎧"""
    guild_id = guild.id
    
    # 🔍 ЕСЛИ ПЛЕЕР УЖЕ СУЩЕСТВУЕТ, ВОЗВРАЩАЕМ ЕГО!!! 🔍
    if guild_id in bot.players:
        return bot.players[guild_id]
    
    # 🆕 ИНАЧЕ СОЗДАЕМ НОВЫЙ ПЛЕЕР - САМЫЙ ЛУЧШИЙ В МИРЕ!!! 🆕
    if bot.use_lavalink and bot.lavalink_available and bot.wavelink_node and bot.wavelink_node.is_connected:
        logger.info(f'🎵 СОЗДАНИЕ LavalinkPlayer ДЛЯ СЕРВЕРА {guild.name} (id: {guild_id})!!! ИДЕАЛЬНОЕ КАЧЕСТВО ЗВУКА!!! 🎵')
        player = LavalinkPlayer(bot, guild_id)
    else:
        logger.info(f'🎵 СОЗДАНИЕ MusicPlayer ДЛЯ СЕРВЕРА {guild.name} (id: {guild_id})!!! ВЕЛИКОЛЕПНОЕ ЗВУЧАНИЕ!!! 🎵')
        player = MusicPlayer(bot, guild_id)
    
    # 🔊 УСТАНАВЛИВАЕМ ГРОМКОСТЬ - В САМЫЙ РАЗ!!! 🔊
    await player.set_volume(DEFAULT_VOLUME)
    
    # 💾 СОХРАНЯЕМ ПЛЕЕР - ДЛЯ БУДУЩЕГО ИСПОЛЬЗОВАНИЯ!!! 💾
    bot.players[guild_id] = player
    return player

# 🔗 ДОБАВЛЯЕМ ФУНКЦИЮ ПОЛУЧЕНИЯ ПЛЕЕРА В ЭКЗЕМПЛЯР БОТА!!! 🔗
bot.get_player = get_player

# 🚀 ФУНКЦИЯ ЗАПУСКА БОТА - ГЛАВНЫЙ ЗАПУСКАТОР!!! 🚀
async def main():
    """🏁 ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА БОТА - ВСЁ НАЧИНАЕТСЯ ЗДЕСЬ!!! 🏁"""
    # 🔄 ИНИЦИАЛИЗАЦИЯ LAVALINK, ЕСЛИ ВКЛЮЧЕН!!! 🔄
    if bot.use_lavalink and bot.lavalink_available:
        try:
            # 🚀 ИМПОРТИРУЕМ И ИНИЦИАЛИЗИРУЕМ WAVELINK!!! 🚀
            import wavelink
            import pkg_resources
            
            # Получаем версию wavelink
            wavelink_version = pkg_resources.get_distribution("wavelink").version
            logger.info(f"📊 ВЕРСИЯ WAVELINK: {wavelink_version}!!! ПРОВЕРЯЕМ СОВМЕСТИМОСТЬ!!! 📊")
            
            # 🏁 ЗАПУСКАЕМ LAVALINK СЕРВЕР, ЕСЛИ ТРЕБУЕТСЯ!!! 🏁
            use_internal_lavalink = os.getenv('USE_INTERNAL_LAVALINK', 'true').lower() == 'true'
            if use_internal_lavalink:
                logger.info("🚀 ЗАПУСК ВСТРОЕННОГО LAVALINK СЕРВЕРА!!! ПОДОЖДИТЕ!!! 🚀")
                await download_and_start_lavalink()
                
            # 🔌 НАСТРОЙКИ ПОДКЛЮЧЕНИЯ К LAVALINK!!! 🔌
            lavalink_host = os.getenv('LAVALINK_HOST', 'localhost')
            lavalink_port = int(os.getenv('LAVALINK_PORT', 2333))
            lavalink_password = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
            lavalink_secure = os.getenv('LAVALINK_SECURE', 'false').lower() == 'true'
            
            # ⏱️ ПОДОЖДЕМ НЕМНОГО ДЛЯ ЗАПУСКА СЕРВЕРА!!! ⏱️
            if use_internal_lavalink:
                await asyncio.sleep(5)
                
            # 🔗 СОЗДАЕМ НОДУ WAVELINK В ЗАВИСИМОСТИ ОТ ВЕРСИИ!!! 🔗
            major_version = int(wavelink_version.split('.')[0])
            
            if major_version >= 2:
                # Используем новый API из wavelink 2.x
                bot.wavelink_node = await wavelink.NodePool.create_node(
                    bot=bot,
                    host=lavalink_host,
                    port=lavalink_port,
                    password=lavalink_password,
                    secure=lavalink_secure
                )
            else:
                # Используем старый API из wavelink 1.x
                bot.wavelink_node = await wavelink.connect(
                    client=bot,
                    host=lavalink_host,
                    port=lavalink_port,
                    password=lavalink_password,
                    secure=lavalink_secure
                )
            
            logger.info(f"✅ ПОДКЛЮЧЕНИЕ К LAVALINK СЕРВЕРУ УСПЕШНО!!! ГОТОВЫ К РАБОТЕ!!! ✅")
        except Exception as e:
            logger.error(f"❌ ОШИБКА ПРИ ИНИЦИАЛИЗАЦИИ LAVALINK: {e}!!! БУДЕТ ИСПОЛЬЗОВАН ОБЫЧНЫЙ ПЛЕЕР!!! ❌")
            bot.use_lavalink = False
            bot.lavalink_available = False
            bot.wavelink_node = None
    
    # 📥 ЗАГРУЗКА МОДУЛЕЙ С КОМАНДАМИ!!! 📥
    await load_extensions()
    
    # 🚀 ЗАПУСК БОТА - ПОЕХАЛИ!!! 🚀
    async with bot:
        await bot.start(TOKEN)

# 🏁 ЗАПУСК БОТА - ПОЕХАЛИ!!! 🏁
if __name__ == "__main__":
    try:
        # 🔄 ЗАПУСК В АСИНХРОННОМ РЕЖИМЕ - СОВРЕМЕННЫЕ ТЕХНОЛОГИИ!!! 🔄
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ БОТ ОСТАНОВЛЕН ВРУЧНУЮ!!! ДО НОВЫХ ВСТРЕЧ!!! ⛔")
    except Exception as e:
        logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}!!! СРОЧНО ИСПРАВЬТЕ!!! 💥")
        sys.exit(1) 