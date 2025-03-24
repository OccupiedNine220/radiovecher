import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from music_player import MusicPlayer
import wavelink
from lavalink_player import LAVALINK_HOST, LAVALINK_PORT, LAVALINK_PASSWORD, LAVALINK_SECURE, USE_INTERNAL_LAVALINK, download_and_start_lavalink
import datetime
import asyncio

# Импорт веб-сервера
try:
    from web.server import initialize_web_server, get_web_url
    WEB_ENABLED = True
except ImportError:
    print("Веб-сервер не загружен. Проверьте наличие директории 'web' и необходимых зависимостей.")
    WEB_ENABLED = False

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')
RETRO_FM_NAME = os.getenv('RETRO_FM_NAME', 'Ретро FM')

# Настройка Flask порта
FLASK_PORT = os.getenv('FLASK_PORT', '5000')
os.environ['FLASK_PORT'] = FLASK_PORT

# Глобальная переменная для использования Lavalink
USE_LAVALINK = os.getenv('USE_LAVALINK', 'true').lower() == 'true'

# Процесс Lavalink сервера
lavalink_process = None

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
        self.current_radio = {
            'name': RADIO_NAME,
            'url': os.getenv('RADIO_STREAM_URL', 'https://rusradio.hostingradio.ru/rusradio96.aacp'),
            'thumbnail': os.getenv('RADIO_THUMBNAIL', 'https://rusradio.ru/design/images/share.jpg')
        }
        
        # Доступные радиостанции
        self.available_radios = {
            'русское': {
                'name': RADIO_NAME,
                'url': os.getenv('RADIO_STREAM_URL', 'https://rusradio.hostingradio.ru/rusradio96.aacp'),
                'thumbnail': os.getenv('RADIO_THUMBNAIL', 'https://rusradio.ru/design/images/share.jpg')
            },
            'ретро': {
                'name': RETRO_FM_NAME,
                'url': os.getenv('RETRO_FM_STREAM_URL', 'https://retro.hostingradio.ru:8043/retro256.mp3'),
                'thumbnail': os.getenv('RETRO_FM_THUMBNAIL', 'https://retrofm.ru/retrosite/upload/cache/b1-logo-retro-fm-240x240-crop-ffffff.webp')
            }
        }
        
        # Флаг, указывающий, инициализирован ли уже веб-сервер
        self.web_server_initialized = False
        
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
        global lavalink_process
        
        try:
            # Проверка USE_LAVALINK из .env
            if not USE_LAVALINK:
                print("Lavalink отключен в настройках .env (USE_LAVALINK=false)")
                return
            
            # Если включен внутренний Lavalink и мы на Windows
            if USE_INTERNAL_LAVALINK and os.name == 'nt':
                print("Запуск встроенного Lavalink сервера...")
                lavalink_process = await download_and_start_lavalink()
                
                if not lavalink_process:
                    print("Не удалось запустить встроенный Lavalink сервер.")
                    print("Будет использован стандартный плеер без поддержки Lavalink.")
                    return
                
                # Даем время на запуск серверу
                await asyncio.sleep(5)
                
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
        
        # Инициализация веб-сервера (только один раз)
        if WEB_ENABLED and not self.web_server_initialized:
            try:
                initialize_web_server(self)
                self.web_server_initialized = True
                print(f"Веб-интерфейс запущен на http://localhost:{FLASK_PORT}")
            except Exception as e:
                print(f"Ошибка при инициализации веб-сервера: {e}")
        
    async def update_presence(self, status=None):
        """Обновляет статус бота"""
        if status:
            activity_name = status
        else:
            activity_name = self.current_radio['name']
            
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, 
                name=activity_name
            )
        )
        
    def switch_radio(self, radio_key):
        """Переключает текущую радиостанцию

        Args:
            radio_key: Ключ радиостанции в словаре available_radios

        Returns:
            dict: Информация о выбранной радиостанции или None, если не найдена
        """
        radio_key = radio_key.lower()
        if radio_key in self.available_radios:
            self.current_radio = self.available_radios[radio_key]
            return self.current_radio
        return None
        
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
            web_url = get_web_url()
            queue_url = f"{web_url}/queue/{guild.id}" if web_url else None
            
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
                value=f"`/play` - добавить трек\n`/skip` - пропустить трек\n`/pause` - пауза\n`/resume` - продолжить\n`/radio` - вернуться к радио\n`/switch_radio` - сменить радиостанцию",
                inline=False
            )
            
            embed.add_field(
                name="Умные плейлисты",
                value="Используйте `/smart_playlist` для создания плейлиста на основе трека.",
                inline=False
            )
            
            if web_url:
                embed.add_field(
                    name="Веб-интерфейс",
                    value=f"Используйте команду `/webpanel` для получения ссылки на веб-интерфейс или перейдите по адресу: [Панель управления]({queue_url})",
                    inline=False
                )
            
            embed.set_footer(text=f"Радио Вечер v2.0 • {datetime.datetime.now().year}")
            
            await general_channel.send(embed=embed)
            
    @property
    def web_url(self):
        """Возвращает URL веб-интерфейса"""
        return f"http://localhost:{FLASK_PORT}" if WEB_ENABLED else None

    async def close(self):
        """Закрывает бота и останавливает Lavalink, если он был запущен"""
        global lavalink_process
        
        # Останавливаем Lavalink сервер, если он запущен
        if lavalink_process:
            try:
                print("Останавливаю Lavalink сервер...")
                # Для Windows
                if os.name == 'nt':
                    import subprocess
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(lavalink_process.pid)])
                else:
                    lavalink_process.terminate()
                    lavalink_process.wait()
                print("Lavalink сервер остановлен.")
            except Exception as e:
                print(f"Ошибка при остановке Lavalink сервера: {e}")
        
        # Вызываем оригинальный метод close
        await super().close()

# Запуск бота
if __name__ == "__main__":
    try:
        bot = RadioVecherBot()
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Программа была остановлена пользователем")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        # Делаем дополнительную очистку при завершении
        if lavalink_process:
            try:
                # Для Windows
                if os.name == 'nt':
                    import subprocess
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(lavalink_process.pid)])
                else:
                    lavalink_process.terminate()
            except:
                pass 