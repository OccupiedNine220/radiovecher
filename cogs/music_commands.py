import discord
from discord.ext import commands
from discord import app_commands
from music_player import MusicPlayer
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')

# ID голосового канала для киновечера
VOICE_CHANNEL_ID = 1329935439628341289
# ID текстового канала для плеера
TEXT_CHANNEL_ID = 1351254192282669269

# Необходимые разрешения для бота
BOT_PERMISSIONS = discord.Permissions(
    connect=True,  # Подключение к голосовым каналам
    speak=True,    # Говорить в голосовых каналах
    use_voice_activation=True,  # Использовать голосовую активацию
    view_channel=True,  # Видеть каналы
    send_messages=True,  # Отправлять сообщения
    embed_links=True,    # Встраивать ссылки
    attach_files=True,   # Прикреплять файлы
    read_message_history=True,  # Читать историю сообщений
    add_reactions=True,  # Добавлять реакции
    manage_messages=True,  # Управлять сообщениями (для закрепления)
    external_emojis=True,  # Использовать внешние эмодзи
    use_external_stickers=True,  # Использовать внешние стикеры
    use_application_commands=True,  # Использовать слэш-команды
)

class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        
        # Ссылка для приглашения бота с нужными разрешениями
        self.invite_link = discord.utils.oauth_url(
            bot.user.id if bot.user else "YOUR_CLIENT_ID",
            permissions=BOT_PERMISSIONS,
            scopes=("bot", "applications.commands")
        )
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Инициализация при запуске бота"""
        print("Музыкальный модуль загружен!")
        print(f"Ссылка для приглашения бота: {self.invite_link}")
    
    async def get_player(self, guild_id):
        """Получение или создание экземпляра плеера для сервера"""
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer(
                self.bot, 
                guild_id, 
                VOICE_CHANNEL_ID, 
                TEXT_CHANNEL_ID
            )
        return self.players[guild_id]
    
    @app_commands.command(name="start", description="Запуск музыкального плеера в голосовом канале")
    @app_commands.default_permissions(manage_guild=True)
    async def start_player(self, interaction: discord.Interaction):
        """Запуск музыкального плеера в указанном голосовом канале"""
        # Проверка прав пользователя
        if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("У вас недостаточно прав для использования этой команды. Требуется право 'Управление сервером'.", ephemeral=True)
            return
            
        player = await self.get_player(interaction.guild_id)
        
        # Подключение к голосовому каналу и начало воспроизведения
        await interaction.response.defer(ephemeral=True)
        success = await player.connect()
        if success:
            await player.play_default_radio()
            await interaction.followup.send(f"Музыкальный плеер запущен! Воспроизводится {RADIO_NAME}.", ephemeral=True)
        else:
            await interaction.followup.send("Не удалось подключиться к голосовому каналу.", ephemeral=True)
    
    @app_commands.command(name="stop", description="Остановка музыкального плеера")
    @app_commands.default_permissions(manage_guild=True)
    async def stop_player(self, interaction: discord.Interaction):
        """Остановка музыкального плеера"""
        # Проверка прав пользователя
        if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("У вас недостаточно прав для использования этой команды. Требуется право 'Управление сервером'.", ephemeral=True)
            return
            
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            await interaction.response.defer(ephemeral=True)
            await player.disconnect()
            del self.players[interaction.guild_id]
            await interaction.followup.send("Музыкальный плеер остановлен.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @app_commands.command(name="skip", description="Пропуск текущего трека")
    async def skip_track(self, interaction: discord.Interaction):
        """Пропуск текущего трека"""
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            await interaction.response.defer(ephemeral=True)
            success = await player.skip()
            if success:
                await interaction.followup.send("Трек пропущен.", ephemeral=True)
            else:
                await interaction.followup.send("Нечего пропускать.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @app_commands.command(name="radio", description=f"Возврат к воспроизведению {RADIO_NAME}")
    async def play_radio(self, interaction: discord.Interaction):
        """Возврат к воспроизведению радио по умолчанию"""
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            await interaction.response.defer(ephemeral=True)
            await player.stop()
            success = await player.play_default_radio()
            if success:
                await interaction.followup.send(f"Воспроизводится {RADIO_NAME}.", ephemeral=True)
            else:
                await interaction.followup.send(f"Не удалось воспроизвести {RADIO_NAME}.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @app_commands.command(name="play", description="Добавление трека в очередь воспроизведения")
    @app_commands.describe(query="Ссылка на трек или поисковый запрос")
    async def play_track(self, interaction: discord.Interaction, query: str):
        """Добавление трека в очередь воспроизведения"""
        player = await self.get_player(interaction.guild_id)
        
        # Если плеер не подключен, подключаем его
        await interaction.response.defer(ephemeral=True)
        if not player.voice_client or not player.voice_client.is_connected():
            success = await player.connect()
            if not success:
                await interaction.followup.send("Не удалось подключиться к голосовому каналу.", ephemeral=True)
                return
        
        # Добавление трека в очередь
        success, message = await player.add_to_queue(query)
        await interaction.followup.send(message, ephemeral=True)
    
    @app_commands.command(name="invite", description="Получить ссылку для приглашения бота на сервер")
    async def invite_bot(self, interaction: discord.Interaction):
        """Получить ссылку для приглашения бота на сервер"""
        embed = discord.Embed(
            title="Пригласить бота",
            description="Нажмите на кнопку ниже, чтобы пригласить бота на свой сервер.",
            color=discord.Color.blue()
        )
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Пригласить бота", 
            url=self.invite_link,
            style=discord.ButtonStyle.url
        ))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Обработка изменений состояния голосового канала"""
        # Проверка, является ли участник ботом
        if member.id == self.bot.user.id:
            # Если бот был отключен от голосового канала
            if before.channel and not after.channel:
                guild_id = before.channel.guild.id
                if guild_id in self.players:
                    player = self.players[guild_id]
                    # Попытка переподключения
                    await player.disconnect()  # Сначала отключаемся полностью
                    success = await player.connect()
                    if success:
                        await player.play_default_radio()
                        print(f"Бот переподключился к голосовому каналу в гильдии {guild_id}")
                    else:
                        print(f"Не удалось переподключиться к голосовому каналу в гильдии {guild_id}")

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))
    
    # Синхронизация слэш-команд
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слэш-команд")
    except Exception as e:
        print(f"Ошибка при синхронизации слэш-команд: {e}") 