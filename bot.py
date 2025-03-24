import os
import sys
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from music_player import MusicPlayer
from lavalink_player import LavalinkPlayer
from config import radios

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
    logger.error("❌ ТОКЕН БОТА НЕ НАЙДЕН!!! ПРОВЕРЬТЕ ФАЙЛ .env!!! ❌")
    sys.exit(1)

# ⚙️ НАСТРОЙКА LAVALINK - ДЛЯ ИДЕАЛЬНОГО КАЧЕСТВА ЗВУКА!!! ⚙️
USE_LAVALINK = os.getenv('USE_LAVALINK', 'false').lower() == 'true'
DEFAULT_VOLUME = int(os.getenv('DEFAULT_VOLUME', '50'))
DEFAULT_RADIO = os.getenv('DEFAULT_RADIO', 'relax')

# 🔍 ПРОВЕРКА ТОКЕНА - ЖИЗНЕННО НЕОБХОДИМО!!! 🔍
if not TOKEN:
    print("❌ ОШИБКА: ТОКЕН БОТА НЕ НАЙДЕН В .env ФАЙЛЕ!!! НЕМЕДЛЕННО ИСПРАВЬТЕ!!! ❌")
    sys.exit(1)

# 🧠 НАСТРОЙКА ИНТЕНТОВ БОТА - ВСЕ ДОЛЖНЫ БЫТЬ ВКЛЮЧЕНЫ!!! 🧠
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

# 🤖 СОЗДАНИЕ ЭКЗЕМПЛЯРА БОТА - ОСНОВА ВСЕГО ПРОЕКТА!!! 🤖
bot = commands.Bot(command_prefix=os.getenv('COMMAND_PREFIX', '/'), intents=intents)

# 🎵 СЛОВАРЬ ДЛЯ ХРАНЕНИЯ МУЗЫКАЛЬНЫХ ПЛЕЕРОВ - КАЖДОМУ СЕРВЕРУ СВОЙ!!! 🎵
bot.players = {}

# 📻 НАСТРОЙКА ДОСТУПНЫХ РАДИОСТАНЦИЙ - ТОЛЬКО ЛУЧШИЕ СТАНЦИИ!!! 📻
bot.available_radios = radios
bot.current_radio = bot.available_radios.get(DEFAULT_RADIO, list(bot.available_radios.values())[0])

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
    
    # 🎭 УСТАНАВЛИВАЕМ СТАТУС - ПУСТЬ ВСЕ ВИДЯТ, ЧТО БОТ КРУТОЙ!!! 🎭
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name=f"/help | {bot.current_radio['name']}"
        )
    )

    # 🌐 ЗАПУСК ВЕБ-СЕРВЕРА - ДЛЯ УДОБНОГО УПРАВЛЕНИЯ!!! 🌐
    server.initialize_web_server(bot)
    
    logger.info(f'🌐 ВЕБ-СЕРВЕР ЗАПУЩЕН ПО АДРЕСУ: {server.get_web_url()}!!! ОТКРОЙ В БРАУЗЕРЕ!!! 🌐')

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
    if USE_LAVALINK:
        logger.info(f'🎵 СОЗДАНИЕ LavalinkPlayer ДЛЯ СЕРВЕРА {guild.name} (id: {guild_id})!!! ИДЕАЛЬНОЕ КАЧЕСТВО ЗВУКА!!! 🎵')
        player = LavalinkPlayer(bot, guild)
    else:
        logger.info(f'🎵 СОЗДАНИЕ MusicPlayer ДЛЯ СЕРВЕРА {guild.name} (id: {guild_id})!!! ВЕЛИКОЛЕПНОЕ ЗВУЧАНИЕ!!! 🎵')
        player = MusicPlayer(bot, guild)
    
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
    # 📥 ЗАГРУЗКА МОДУЛЕЙ С КОМАНДАМИ!!! 📥
    await load_extensions()
    
    # 🚀 ЗАПУСК БОТА - ПОЕХАЛИ!!! 🚀
    async with bot:
        await bot.start(TOKEN)

# 🏁 ЗАПУСК БОТА - ПОЕХАЛИ!!! 🏁
if __name__ == "__main__":
    try:
        # 🔄 ЗАПУСК В АСИНХРОННОМ РЕЖИМЕ - СОВРЕМЕННЫЕ ТЕХНОЛОГИИ!!! 🔄
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ БОТ ОСТАНОВЛЕН ВРУЧНУЮ!!! ДО НОВЫХ ВСТРЕЧ!!! ⛔")
    except Exception as e:
        logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {e}!!! СРОЧНО ИСПРАВЬТЕ!!! 💥")
        sys.exit(1) 