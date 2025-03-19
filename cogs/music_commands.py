import discord
from discord.ext import commands
from discord import app_commands
from music_player import MusicPlayer
import os
from dotenv import load_dotenv
import asyncio

# Загрузка переменных окружения
load_dotenv()
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')

# ID каналов
VOICE_CHANNEL_ID = 1329935439628341289  # ID голосового канала для киновечера
TEXT_CHANNEL_ID = 1351254192282669269   # ID текстового канала для плеера
ADMIN_CHANNEL_ID = 1327691078899335218  # ID канала для админ-панели

# ID роли администратора
ADMIN_ROLE_ID = 1280772929822658600     # ID роли, которая считается администратором

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
        self.admin_panel_message = None
        
        # Ссылка для приглашения бота с нужными разрешениями
        self.invite_link = discord.utils.oauth_url(
            bot.user.id if bot.user else "YOUR_CLIENT_ID",
            permissions=BOT_PERMISSIONS,
            scopes=("bot", "applications.commands")
        )
    
    def has_admin_role(self, user):
        """Проверка наличия роли администратора у пользователя"""
        if user.guild_permissions.administrator or user.guild_permissions.manage_guild:
            return True
            
        # Проверка наличия роли администратора
        for role in user.roles:
            if role.id == ADMIN_ROLE_ID:
                return True
                
        return False
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Инициализация при запуске бота"""
        print("Музыкальный модуль загружен!")
        print(f"Ссылка для приглашения бота: {self.invite_link}")
        
        # Создание админ-панели при запуске
        await self.create_admin_panel()
    
    async def create_admin_panel(self):
        """Создание админ-панели в указанном канале"""
        admin_channel = self.bot.get_channel(ADMIN_CHANNEL_ID)
        if not admin_channel:
            print(f"Канал для админ-панели с ID {ADMIN_CHANNEL_ID} не найден")
            return
            
        # Удаление предыдущих сообщений бота в канале админ-панели
        try:
            async for message in admin_channel.history(limit=50):
                if message.author == self.bot.user:
                    await message.delete()
        except Exception as e:
            print(f"Ошибка при очистке канала админ-панели: {e}")
            
        # Создание эмбеда с информацией
        embed = discord.Embed(
            title="Админ-панель Радио Вечер",
            description=f"Панель управления ботом для киновечера.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Статус",
            value="⏸️ Остановлен",
            inline=False
        )
        
        embed.add_field(
            name="Голосовой канал",
            value=f"<#{VOICE_CHANNEL_ID}>",
            inline=True
        )
        
        embed.add_field(
            name="Текстовый канал плеера",
            value=f"<#{TEXT_CHANNEL_ID}>",
            inline=True
        )
        
        embed.add_field(
            name="Настройки радио",
            value=f"Станция: {RADIO_NAME}\nУправление доступно через кнопки ниже.",
            inline=False
        )
        
        # Создание кнопок для управления
        view = AdminPanelView(self)
        
        # Отправка сообщения и сохранение ссылки на него
        try:
            self.admin_panel_message = await admin_channel.send(embed=embed, view=view)
            print(f"Админ-панель создана в канале {admin_channel.name}")
        except Exception as e:
            print(f"Ошибка при создании админ-панели: {e}")
    
    async def update_admin_panel(self, guild_id=None, status="⏸️ Остановлен"):
        """Обновление админ-панели с актуальной информацией"""
        if not self.admin_panel_message:
            return await self.create_admin_panel()
            
        try:
            # Обновление эмбеда
            embed = discord.Embed(
                title="Админ-панель Радио Вечер",
                description=f"Панель управления ботом для киновечера.",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="Статус",
                value=status,
                inline=False
            )
            
            embed.add_field(
                name="Голосовой канал",
                value=f"<#{VOICE_CHANNEL_ID}>",
                inline=True
            )
            
            embed.add_field(
                name="Текстовый канал плеера",
                value=f"<#{TEXT_CHANNEL_ID}>",
                inline=True
            )
            
            # Добавление информации о текущем треке, если бот активен
            if guild_id and guild_id in self.players:
                player = self.players[guild_id]
                if player.current_track:
                    track_info = player.current_track['title']
                    if 'artist' in player.current_track:
                        track_info += f" - {player.current_track['artist']}"
                    
                    embed.add_field(
                        name="Сейчас играет",
                        value=track_info,
                        inline=False
                    )
            
            embed.add_field(
                name="Настройки радио",
                value=f"Станция: {RADIO_NAME}\nУправление доступно через кнопки ниже.",
                inline=False
            )
            
            # Обновление сообщения с новой информацией
            await self.admin_panel_message.edit(embed=embed)
        except Exception as e:
            print(f"Ошибка при обновлении админ-панели: {e}")
            # При ошибке пробуем создать панель заново
            self.admin_panel_message = None
            await self.create_admin_panel()
    
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
        if not self.has_admin_role(interaction.user):
            await interaction.response.send_message("У вас недостаточно прав для использования этой команды. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
            return
            
        player = await self.get_player(interaction.guild_id)
        
        # Подключение к голосовому каналу и начало воспроизведения
        await interaction.response.defer(ephemeral=True)
        success = await player.connect()
        if success:
            await player.play_default_radio()
            await interaction.followup.send(f"Музыкальный плеер запущен! Воспроизводится {RADIO_NAME}.", ephemeral=True)
            
            # Обновление админ-панели
            await self.update_admin_panel(interaction.guild_id, f"▶️ Активен - {RADIO_NAME}")
        else:
            await interaction.followup.send("Не удалось подключиться к голосовому каналу.", ephemeral=True)
    
    @app_commands.command(name="stop", description="Остановка музыкального плеера")
    @app_commands.default_permissions(manage_guild=True)
    async def stop_player(self, interaction: discord.Interaction):
        """Остановка музыкального плеера"""
        # Проверка прав пользователя
        if not self.has_admin_role(interaction.user):
            await interaction.response.send_message("У вас недостаточно прав для использования этой команды. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
            return
            
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            await interaction.response.defer(ephemeral=True)
            await player.disconnect()
            del self.players[interaction.guild_id]
            await interaction.followup.send("Музыкальный плеер остановлен.", ephemeral=True)
            
            # Обновление админ-панели
            await self.update_admin_panel(status="⏸️ Остановлен")
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
                
                # Обновление админ-панели через небольшую задержку, чтобы успел установиться новый трек
                await asyncio.sleep(1)
                await self.update_admin_panel(interaction.guild_id)
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
                
                # Обновление админ-панели
                await self.update_admin_panel(interaction.guild_id, f"▶️ Активен - {RADIO_NAME}")
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
        
        # Обновление админ-панели
        if success:
            await asyncio.sleep(1)  # Задержка, чтобы успел загрузиться трек
            await self.update_admin_panel(interaction.guild_id)
    
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
                        
                        # Обновление админ-панели
                        await self.update_admin_panel(guild_id, f"▶️ Активен - {RADIO_NAME}")
                    else:
                        print(f"Не удалось переподключиться к голосовому каналу в гильдии {guild_id}")
                        
                        # Обновление админ-панели
                        await self.update_admin_panel(status="⚠️ Ошибка подключения")

# Класс для кнопок админ-панели
class AdminPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(label="▶️ Запустить", style=discord.ButtonStyle.success, custom_id="admin_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверка прав администратора
        if not self.cog.has_admin_role(interaction.user):
            return await interaction.response.send_message("У вас недостаточно прав для использования админ-панели. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
        
        # Получаем плеер и запускаем его
        player = await self.cog.get_player(interaction.guild_id)
        
        await interaction.response.defer(ephemeral=True)
        success = await player.connect()
        if success:
            await player.play_default_radio()
            await interaction.followup.send(f"Музыкальный плеер запущен! Воспроизводится {RADIO_NAME}.", ephemeral=True)
            
            # Обновление админ-панели
            await self.cog.update_admin_panel(interaction.guild_id, f"▶️ Активен - {RADIO_NAME}")
        else:
            await interaction.followup.send("Не удалось подключиться к голосовому каналу.", ephemeral=True)
            
            # Обновление админ-панели с ошибкой
            await self.cog.update_admin_panel(status="⚠️ Ошибка подключения")
    
    @discord.ui.button(label="⏹️ Остановить", style=discord.ButtonStyle.danger, custom_id="admin_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверка прав администратора
        if not self.cog.has_admin_role(interaction.user):
            return await interaction.response.send_message("У вас недостаточно прав для использования админ-панели. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
        
        if interaction.guild_id in self.cog.players:
            player = self.cog.players[interaction.guild_id]
            
            await interaction.response.defer(ephemeral=True)
            await player.disconnect()
            del self.cog.players[interaction.guild_id]
            await interaction.followup.send("Музыкальный плеер остановлен.", ephemeral=True)
            
            # Обновление админ-панели
            await self.cog.update_admin_panel(status="⏸️ Остановлен")
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @discord.ui.button(label="⏭️ Пропустить", style=discord.ButtonStyle.primary, custom_id="admin_skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверка прав администратора
        if not self.cog.has_admin_role(interaction.user):
            return await interaction.response.send_message("У вас недостаточно прав для использования админ-панели. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
        
        if interaction.guild_id in self.cog.players:
            player = self.cog.players[interaction.guild_id]
            
            await interaction.response.defer(ephemeral=True)
            success = await player.skip()
            if success:
                await interaction.followup.send("Трек пропущен.", ephemeral=True)
                
                # Обновление админ-панели через небольшую задержку
                await asyncio.sleep(1)
                await self.cog.update_admin_panel(interaction.guild_id)
            else:
                await interaction.followup.send("Нечего пропускать.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @discord.ui.button(label="🔄 Обновить", style=discord.ButtonStyle.secondary, custom_id="admin_refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # Определяем текущий статус
        status = "⏸️ Остановлен"
        guild_id = interaction.guild_id
        
        if guild_id in self.cog.players:
            player = self.cog.players[guild_id]
            if player.is_playing:
                if player.current_track:
                    track_name = player.current_track['title']
                    status = f"▶️ Активен - {track_name}"
                else:
                    status = f"▶️ Активен - {RADIO_NAME}"
        
        # Обновление админ-панели
        await self.cog.update_admin_panel(guild_id, status)
        await interaction.followup.send("Админ-панель обновлена.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))
    
    # Синхронизация слэш-команд
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слэш-команд")
    except Exception as e:
        print(f"Ошибка при синхронизации слэш-команд: {e}") 