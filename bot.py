import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from music_player import MusicPlayer
import wavelink
from lavalink_player import LAVALINK_HOST, LAVALINK_PORT, LAVALINK_PASSWORD, LAVALINK_SECURE

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')

# Настройка интентов Discord
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

# Создание бота
class RadioVecherBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',  # Префикс для обычных команд (для обратной совместимости)
            intents=intents,
            help_command=None,  # Отключаем стандартную команду помощи
            activity=discord.Activity(
                type=discord.ActivityType.listening, 
                name=RADIO_NAME
            )
        )
        self.players = {}
        self.wavelink_node = None
        
    async def setup_hook(self):
        """Хук настройки, вызываемый при запуске бота"""
        # Инициализация Wavelink
        await self._init_wavelink()
        
        # Загрузка когов
        await self.load_extension('cogs.music_commands')
        
        # Синхронизация слэш-команд
        await self.tree.sync()
        
    async def _init_wavelink(self):
        """Инициализация Wavelink и подключение к Lavalink серверу"""
        try:
            # Инициализация клиента Wavelink
            # Создание и подключение узла
            self.wavelink_node = wavelink.Node(
                uri=f'{"wss" if LAVALINK_SECURE else "ws"}://{LAVALINK_HOST}:{LAVALINK_PORT}',
                password=LAVALINK_PASSWORD
            )
            
            await wavelink.Pool.connect(nodes=[self.wavelink_node], client=self)
            
            print(f"Подключен к Lavalink серверу: {LAVALINK_HOST}:{LAVALINK_PORT}")
        except Exception as e:
            print(f"Ошибка при подключении к Lavalink серверу: {e}")
            print("Будет использован стандартный плеер без поддержки Lavalink.")
        
    async def on_ready(self):
        """Вызывается, когда бот готов к работе"""
        print(f'{self.user} подключен к Discord!')
        print(f'Бот работает на {len(self.guilds)} серверах')
        print("Бот готов к работе!")
        
    async def update_presence(self, status=None):
        """Обновляет статус бота"""
        if status:
            activity_name = status
        else:
            activity_name = RADIO_NAME
            
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, 
                name=activity_name
            )
        )
        
    async def on_guild_join(self, guild):
        """Вызывается, когда бот присоединяется к новому серверу"""
        print(f"Бот присоединился к серверу: {guild.name} (ID: {guild.id})")
        
        # Поиск текстового канала для отправки приветственного сообщения
        general_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                general_channel = channel
                break
                
        if general_channel:
            embed = discord.Embed(
                title="Спасибо за добавление Радио Вечер!",
                description="Бот для проведения киновечеров с музыкой в голосовом канале.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Начало работы",
                value="Используйте команду `/start` для запуска музыкального плеера в голосовом канале.",
                inline=False
            )
            
            embed.add_field(
                name="Основные команды",
                value=f"`/play` - добавить трек\n`/skip` - пропустить трек\n`/pause` - пауза\n`/resume` - продолжить\n`/radio` - вернуться к {RADIO_NAME}",
                inline=False
            )
            
            embed.add_field(
                name="Настройка",
                value="Для настройки каналов отредактируйте файл `cogs/music_commands.py`.",
                inline=False
            )
            
            await general_channel.send(embed=embed)

# Запуск бота
if __name__ == "__main__":
    bot = RadioVecherBot()
    bot.run(TOKEN) 