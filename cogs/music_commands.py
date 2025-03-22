import discord
from discord.ext import commands
from discord import app_commands
from music_player import MusicPlayer
from lavalink_player import LavalinkPlayer
from playlist_manager import PlaylistManager
import os
from dotenv import load_dotenv
import asyncio
import time
import wavelink

# Загрузка переменных окружения
load_dotenv()
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')

# ID каналов
VOICE_CHANNEL_ID = 1329935439628341289  # ID голосового канала для киновечера
TEXT_CHANNEL_ID = 123456789             # ID текстового канала для плеера (обновлен)
ADMIN_CHANNEL_ID = 1327691078899335218  # ID канала для админ-панели

# ID роли администратора
ADMIN_ROLE_ID = 1280772929822658600     # ID роли, которая считается администратором

# Настройка анти-спама (в секундах)
PANEL_UPDATE_COOLDOWN = 5  # Минимальное время между обновлениями админ-панели

# Настройка использования Lavalink
USE_LAVALINK = True  # Установите False для использования стандартного плеера

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
        self.last_panel_update = 0  # Время последнего обновления панели
        self.panel_update_lock = asyncio.Lock()  # Блокировка для предотвращения одновременных обновлений
        self.pending_update = False  # Флаг ожидающего обновления
        self.last_status = "⏸️ Остановлен"  # Последний известный статус
        self.playlist_manager = PlaylistManager()  # Менеджер плейлистов
        
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
                    if message.pinned:
                        await message.unpin()
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
            value=self.last_status,
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
            await self.admin_panel_message.pin()  # Закрепляем сообщение
            self.last_panel_update = time.time()
            print(f"Админ-панель создана в канале {admin_channel.name} и закреплена")
        except Exception as e:
            print(f"Ошибка при создании админ-панели: {e}")
    
    async def schedule_update_admin_panel(self, guild_id=None, status=None):
        """Планирование обновления админ-панели с антиспам защитой"""
        if status:
            self.last_status = status
            # Обновляем статус бота
            await self.bot.update_presence(status)
            
        # Запускаем таймер отложенного обновления
        if not self.pending_update:
            self.pending_update = True
            # Запускаем задачу обновления с задержкой
            self.bot.loop.create_task(self._delayed_panel_update(guild_id))
    
    async def _delayed_panel_update(self, guild_id=None):
        """Выполняет отложенное обновление админ-панели"""
        try:
            # Проверяем, нужно ли ждать перед обновлением
            current_time = time.time()
            time_since_last_update = current_time - self.last_panel_update
            
            if time_since_last_update < PANEL_UPDATE_COOLDOWN:
                # Ждем оставшееся время кулдауна
                await asyncio.sleep(PANEL_UPDATE_COOLDOWN - time_since_last_update)
            
            # Получаем блокировку для безопасного обновления
            async with self.panel_update_lock:
                await self.update_admin_panel(guild_id, self.last_status)
                self.pending_update = False
                self.last_panel_update = time.time()
        except Exception as e:
            print(f"Ошибка при отложенном обновлении админ-панели: {e}")
            self.pending_update = False
    
    async def update_admin_panel(self, guild_id=None, status=None):
        """Обновление админ-панели с актуальной информацией"""
        if status:
            self.last_status = status
            
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
                value=self.last_status,
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
        """Получение или создание экземпляра плеера для указанного сервера"""
        if guild_id in self.players:
            return self.players[guild_id]
            
        # Создание нового экземпляра плеера
        if USE_LAVALINK and hasattr(self.bot, 'wavelink_node') and self.bot.wavelink_node:
            # Используем Lavalink, если доступен
            player = LavalinkPlayer(self.bot, guild_id, VOICE_CHANNEL_ID, TEXT_CHANNEL_ID)
            print(f"Создан новый плеер с Lavalink для сервера {guild_id}")
        else:
            # Используем стандартный плеер
            player = MusicPlayer(self.bot, guild_id, VOICE_CHANNEL_ID, TEXT_CHANNEL_ID)
            print(f"Создан новый плеер для сервера {guild_id}")
            
        self.players[guild_id] = player
        return player
    
    @app_commands.command(name="start", description="Запуск музыкального плеера в голосовом канале")
    @app_commands.default_permissions(manage_guild=True)
    async def start_player(self, interaction: discord.Interaction):
        """Запуск музыкального плеера в указанном голосовом канале"""
        # Проверка прав пользователя
        if not self.has_admin_role(interaction.user):
            await interaction.response.send_message("У вас недостаточно прав для использования этой команды. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
            return
            
        player = await self.get_player(interaction.guild_id)
        
        await interaction.response.defer(ephemeral=True)
        success = await player.connect()
        
        if success:
            # Воспроизведение радио по умолчанию
            radio_success = await player.play_default_radio()
            
            if radio_success:
                await interaction.followup.send("Музыкальный плеер запущен!", ephemeral=True)
                await self.schedule_update_admin_panel(interaction.guild_id, status="▶️ Воспроизведение")
            else:
                await interaction.followup.send("Не удалось начать воспроизведение радио.", ephemeral=True)
                await self.schedule_update_admin_panel(interaction.guild_id, status="⚠️ Ошибка воспроизведения")
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
            await player.stop()
            await player.disconnect()
            
            await interaction.followup.send("Музыкальный плеер остановлен.", ephemeral=True)
            await self.schedule_update_admin_panel(interaction.guild_id, status="⏹️ Остановлен")
            
            # Удаляем плеер для данного сервера
            del self.players[interaction.guild_id]
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @app_commands.command(name="skip", description="Пропуск текущего трека")
    async def skip_track(self, interaction: discord.Interaction):
        """Пропуск текущего трека"""
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            await interaction.response.defer(ephemeral=True)
            
            # Проверка прав администратора
            if self.has_admin_role(interaction.user):
                # Админы могут пропускать напрямую
                success = await player.skip()
                if success:
                    await interaction.followup.send("Трек пропущен администратором.", ephemeral=True)
                    
                    # Планируем обновление админ-панели через некоторое время,
                    # чтобы успел установиться новый трек
                    await asyncio.sleep(1)
                    await self.schedule_update_admin_panel(interaction.guild_id)
                else:
                    await interaction.followup.send("Нечего пропускать.", ephemeral=True)
            else:
                # Обычные пользователи используют голосование
                success, message = await player.vote_skip(interaction.user.id)
                await interaction.followup.send(message, ephemeral=True)
                
                if success:
                    # Если трек был пропущен, обновляем админ-панель
                    await asyncio.sleep(1)
                    await self.schedule_update_admin_panel(interaction.guild_id)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
            
    @app_commands.command(name="pause", description="Приостановить воспроизведение")
    async def pause_playback(self, interaction: discord.Interaction):
        """Приостановка воспроизведения"""
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            success = await player.pause()
            if success:
                await interaction.response.send_message("Воспроизведение приостановлено.", ephemeral=True)
                await self.schedule_update_admin_panel(interaction.guild_id, status="⏸️ На паузе")
            else:
                await interaction.response.send_message("Нечего приостанавливать.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
            
    @app_commands.command(name="resume", description="Возобновить воспроизведение")
    async def resume_playback(self, interaction: discord.Interaction):
        """Возобновление воспроизведения"""
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            success = await player.resume()
            if success:
                await interaction.response.send_message("Воспроизведение возобновлено.", ephemeral=True)
                await self.schedule_update_admin_panel(interaction.guild_id, status="▶️ Воспроизведение")
            else:
                await interaction.response.send_message("Нечего возобновлять.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен.", ephemeral=True)
    
    @app_commands.command(name="radio", description=f"Возврат к воспроизведению {RADIO_NAME}")
    async def play_radio(self, interaction: discord.Interaction):
        """Возврат к воспроизведению радио по умолчанию"""
        if interaction.guild_id in self.players:
            player = self.players[interaction.guild_id]
            
            await interaction.response.defer(ephemeral=True)
            success = await player.play_default_radio()
            
            if success:
                await interaction.followup.send(f"Воспроизведение {RADIO_NAME}.", ephemeral=True)
                await self.schedule_update_admin_panel(interaction.guild_id, status="▶️ Воспроизведение радио")
            else:
                await interaction.followup.send("Не удалось воспроизвести радио.", ephemeral=True)
        else:
            await interaction.response.send_message("Музыкальный плеер не запущен. Используйте команду `/start` для запуска.", ephemeral=True)
            
    @app_commands.command(name="play", description="Добавление трека в очередь воспроизведения")
    @app_commands.describe(query="Ссылка на трек или поисковый запрос")
    async def play_track(self, interaction: discord.Interaction, query: str):
        """Добавление трека в очередь воспроизведения"""
        if interaction.guild_id not in self.players:
            # Автоматический запуск плеера при использовании команды play
            player = await self.get_player(interaction.guild_id)
            await player.connect()
        else:
            player = self.players[interaction.guild_id]
        
        await interaction.response.defer(ephemeral=True)
        success, message = await player.add_to_queue(query)
        
        if success:
            await interaction.followup.send(message, ephemeral=True)
            await self.schedule_update_admin_panel(interaction.guild_id, status="▶️ Воспроизведение")
        else:
            await interaction.followup.send(message, ephemeral=True)
    
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
                        await self.schedule_update_admin_panel(guild_id, f"▶️ Активен - {RADIO_NAME}")
                    else:
                        print(f"Не удалось переподключиться к голосовому каналу в гильдии {guild_id}")
                        
                        # Обновление админ-панели
                        await self.schedule_update_admin_panel(status="⚠️ Ошибка подключения")

    @app_commands.command(name="playlist_create", description="Создать новый плейлист")
    @app_commands.describe(name="Название плейлиста")
    async def create_playlist(self, interaction: discord.Interaction, name: str):
        """Создание нового плейлиста"""
        await interaction.response.defer(ephemeral=True)
        
        success, message = await self.playlist_manager.create_playlist(
            guild_id=interaction.guild_id,
            name=name,
            author_id=interaction.user.id
        )
        
        # Создаем и отправляем эмбед с результатом
        embed = discord.Embed(
            title="Создание плейлиста",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        if success:
            embed.add_field(name="Дальнейшие действия", value="Используйте команду `/playlist_add` чтобы добавить треки в плейлист, а затем `/playlist_vote_start` для начала голосования.")
            
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="playlist_list", description="Показать список плейлистов")
    @app_commands.describe(show_all="Показать все плейлисты, включая неодобренные")
    async def list_playlists(self, interaction: discord.Interaction, show_all: bool = False):
        """Отображение списка плейлистов"""
        await interaction.response.defer(ephemeral=True)
        
        if show_all and self.has_admin_role(interaction.user):
            playlists = self.playlist_manager.get_all_playlists(interaction.guild_id)
        else:
            playlists = self.playlist_manager.get_approved_playlists(interaction.guild_id)
        
        if not playlists:
            embed = discord.Embed(
                title="Плейлисты",
                description="На этом сервере ещё нет плейлистов" if show_all else "На этом сервере ещё нет одобренных плейлистов",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Создаем эмбед со списком плейлистов
        embed = discord.Embed(
            title="Плейлисты",
            description=f"Доступные плейлисты на сервере ({len(playlists)})",
            color=discord.Color.blue()
        )
        
        for i, playlist in enumerate(playlists):
            author = interaction.guild.get_member(int(playlist["author_id"]))
            author_name = author.display_name if author else "Неизвестно"
            track_count = len(playlist["tracks"])
            status = "✅ Одобрен" if playlist["votes"]["approved"] else "❌ Не одобрен"
            
            value = f"Автор: {author_name}\nТреков: {track_count}\nСтатус: {status}"
            embed.add_field(
                name=f"{i+1}. {playlist['name']}",
                value=value,
                inline=False
            )
        
        # Добавляем подсказку по использованию команд
        embed.set_footer(text="Используйте /playlist_play <название> для воспроизведения плейлиста")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="playlist_info", description="Показать информацию о плейлисте")
    @app_commands.describe(name="Название плейлиста")
    async def playlist_info(self, interaction: discord.Interaction, name: str):
        """Отображение информации о плейлисте"""
        await interaction.response.defer(ephemeral=True)
        
        playlist = self.playlist_manager.get_playlist(interaction.guild_id, name)
        
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Получение информации о голосовании
        success, voting = self.playlist_manager.get_voting_status(interaction.guild_id, name)
        
        # Создаем эмбед с информацией о плейлисте
        embed = discord.Embed(
            title=f"Плейлист: {playlist['name']}",
            color=discord.Color.blue()
        )
        
        # Добавляем информацию об авторе
        author = interaction.guild.get_member(int(playlist["author_id"]))
        author_name = author.display_name if author else "Неизвестно"
        embed.add_field(name="Автор", value=author_name, inline=True)
        
        # Добавляем информацию о статусе одобрения
        status = "✅ Одобрен" if playlist["votes"]["approved"] else "❌ Не одобрен"
        embed.add_field(name="Статус", value=status, inline=True)
        
        # Добавляем информацию о голосовании, если оно идет
        if success and "finished" in voting and not voting["finished"]:
            embed.add_field(
                name="Голосование",
                value=f"Идет голосование\n👍 За: {voting['up_votes']}\n👎 Против: {voting['down_votes']}",
                inline=False
            )
        
        # Список треков
        tracks = playlist["tracks"]
        if tracks:
            tracks_text = ""
            for i, track in enumerate(tracks[:10]):  # Показываем первые 10 треков
                tracks_text += f"{i+1}. {track['title']}\n"
            
            if len(tracks) > 10:
                tracks_text += f"...и ещё {len(tracks) - 10} трек(ов)"
                
            embed.add_field(name=f"Треки ({len(tracks)})", value=tracks_text, inline=False)
        else:
            embed.add_field(name="Треки", value="В плейлисте нет треков", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="playlist_add", description="Добавить трек в плейлист")
    @app_commands.describe(
        name="Название плейлиста",
        url="URL трека (YouTube, Spotify и др.)"
    )
    async def add_to_playlist(self, interaction: discord.Interaction, name: str, url: str):
        """Добавление трека в плейлист"""
        await interaction.response.defer(ephemeral=True)
        
        # Проверяем существование плейлиста
        playlist = self.playlist_manager.get_playlist(interaction.guild_id, name)
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, имеет ли пользователь право изменять плейлист
        if str(interaction.user.id) != playlist["author_id"] and not self.has_admin_role(interaction.user):
            embed = discord.Embed(
                title="Доступ запрещен",
                description="Вы не можете изменять чужие плейлисты",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем URL на валидность и получаем информацию о треке
        try:
            result = await self.wavelink.get_tracks(url)
            if not result:
                embed = discord.Embed(
                    title="Ошибка",
                    description="Не удалось найти трек по указанному URL",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Если результат - плейлист, берем первый трек
            if isinstance(result, wavelink.Playlist):
                track = result.tracks[0]
            else:
                track = result[0]
            
            # Добавляем трек в плейлист
            track_info = {
                "url": url,
                "title": track.title,
                "author": track.author
            }
            
            success, message = await self.playlist_manager.add_track(
                guild_id=interaction.guild_id,
                playlist_name=name,
                track=track_info
            )
            
            # Создаем эмбед с результатом
            embed = discord.Embed(
                title="Добавление трека",
                description=message,
                color=discord.Color.green() if success else discord.Color.red()
            )
            
            if success:
                embed.add_field(
                    name="Информация о треке", 
                    value=f"**Название:** {track.title}\n**Автор:** {track.author}"
                )
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Произошла ошибка при обработке URL: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="playlist_remove", description="Удалить трек из плейлиста")
    @app_commands.describe(
        name="Название плейлиста",
        index="Номер трека в плейлисте (начиная с 1)"
    )
    async def remove_from_playlist(self, interaction: discord.Interaction, name: str, index: int):
        """Удаление трека из плейлиста"""
        await interaction.response.defer(ephemeral=True)
        
        # Проверяем существование плейлиста
        playlist = self.playlist_manager.get_playlist(interaction.guild_id, name)
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, имеет ли пользователь право изменять плейлист
        if str(interaction.user.id) != playlist["author_id"] and not self.has_admin_role(interaction.user):
            embed = discord.Embed(
                title="Доступ запрещен",
                description="Вы не можете изменять чужие плейлисты",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем валидность индекса
        if index < 1 or index > len(playlist["tracks"]):
            embed = discord.Embed(
                title="Ошибка",
                description=f"Неверный номер трека. Доступны треки с 1 по {len(playlist['tracks'])}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Получаем информацию о треке перед удалением
        track_to_remove = playlist["tracks"][index-1]["title"]
        
        # Удаляем трек из плейлиста
        success, message = await self.playlist_manager.remove_track(
            guild_id=interaction.guild_id,
            playlist_name=name,
            index=index-1  # Внутри используем 0-индексацию
        )
        
        # Создаем эмбед с результатом
        embed = discord.Embed(
            title="Удаление трека",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        if success:
            embed.add_field(name="Удаленный трек", value=track_to_remove)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="playlist_delete", description="Удалить плейлист")
    @app_commands.describe(name="Название плейлиста")
    async def delete_playlist(self, interaction: discord.Interaction, name: str):
        """Удаление плейлиста"""
        await interaction.response.defer(ephemeral=True)
        
        # Проверяем существование плейлиста
        playlist = self.playlist_manager.get_playlist(interaction.guild_id, name)
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, имеет ли пользователь право удалять плейлист
        if str(interaction.user.id) != playlist["author_id"] and not self.has_admin_role(interaction.user):
            embed = discord.Embed(
                title="Доступ запрещен",
                description="Вы не можете удалять чужие плейлисты",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Удаляем плейлист
        success, message = await self.playlist_manager.delete_playlist(
            guild_id=interaction.guild_id,
            playlist_name=name
        )
        
        # Создаем эмбед с результатом
        embed = discord.Embed(
            title="Удаление плейлиста",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="playlist_vote_start", description="Начать голосование за плейлист")
    @app_commands.describe(name="Название плейлиста")
    async def start_playlist_voting(self, interaction: discord.Interaction, name: str):
        """Начало голосования за плейлист"""
        await interaction.response.defer(ephemeral=False)  # Видно всем участникам
        
        # Проверяем существование плейлиста
        playlist = self.playlist_manager.get_playlist(interaction.guild_id, name)
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, что автор или админ начинает голосование
        if str(interaction.user.id) != playlist["author_id"] and not self.has_admin_role(interaction.user):
            embed = discord.Embed(
                title="Доступ запрещен",
                description="Только автор плейлиста или администратор может начать голосование",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, что плейлист не пустой
        if not playlist["tracks"]:
            embed = discord.Embed(
                title="Ошибка",
                description="Нельзя начать голосование за пустой плейлист. Добавьте треки с помощью /playlist_add",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, что плейлист еще не одобрен
        if playlist["votes"]["approved"]:
            embed = discord.Embed(
                title="Информация",
                description=f"Плейлист '{name}' уже одобрен",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Начинаем голосование
        success, message = await self.playlist_manager.start_voting(
            guild_id=interaction.guild_id,
            playlist_name=name,
            duration=86400  # 24 часа
        )
        
        if not success:
            embed = discord.Embed(
                title="Ошибка",
                description=message,
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Создаем эмбед для голосования
        embed = discord.Embed(
            title=f"Голосование за плейлист: {name}",
            description="Решите, должен ли этот плейлист быть добавлен в общую коллекцию",
            color=discord.Color.gold()
        )
        
        # Добавляем информацию об авторе
        author = interaction.guild.get_member(int(playlist["author_id"]))
        author_name = author.display_name if author else "Неизвестно"
        embed.add_field(name="Автор", value=author_name, inline=True)
        
        # Добавляем информацию о количестве треков
        tracks_count = len(playlist["tracks"])
        embed.add_field(name="Количество треков", value=str(tracks_count), inline=True)
        
        # Добавляем список треков
        tracks_text = ""
        for i, track in enumerate(playlist["tracks"][:5]):  # Показываем первые 5 треков
            tracks_text += f"{i+1}. {track['title']}\n"
        
        if tracks_count > 5:
            tracks_text += f"...и ещё {tracks_count - 5} трек(ов)"
            
        embed.add_field(name="Треки", value=tracks_text, inline=False)
        
        # Добавляем информацию о голосовании
        embed.add_field(
            name="Голосование",
            value="Голосование продлится 24 часа\nНажмите на кнопки ниже, чтобы проголосовать",
            inline=False
        )
        
        # Создаем кнопки для голосования
        view = PlaylistVotingView(
            playlist_manager=self.playlist_manager,
            guild_id=interaction.guild_id,
            playlist_name=name
        )
        
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="playlist_play", description="Воспроизвести плейлист")
    @app_commands.describe(name="Название плейлиста")
    async def play_playlist(self, interaction: discord.Interaction, name: str):
        """Воспроизведение плейлиста"""
        await interaction.response.defer(ephemeral=False)  # Видно всем участникам
        
        # Проверяем существование плейлиста
        playlist = self.playlist_manager.get_playlist(interaction.guild_id, name)
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, что плейлист одобрен
        if not playlist["votes"]["approved"] and not self.has_admin_role(interaction.user):
            embed = discord.Embed(
                title="Доступ запрещен",
                description="Этот плейлист ещё не одобрен. Только администраторы могут воспроизводить неодобренные плейлисты.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, что плейлист не пустой
        if not playlist["tracks"]:
            embed = discord.Embed(
                title="Ошибка",
                description="Этот плейлист пуст и не может быть воспроизведен",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Проверяем, что пользователь находится в голосовом канале
        if not interaction.user.voice:
            embed = discord.Embed(
                title="Ошибка",
                description="Вы должны находиться в голосовом канале, чтобы воспроизвести плейлист",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Получаем или создаем плеер
        player = await self.get_player(interaction.guild.id)
        if not player:
            embed = discord.Embed(
                title="Ошибка",
                description="Не удалось подключиться к голосовому каналу",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Подключаемся к голосовому каналу
        if not player.is_connected:
            await player.connect(interaction.user.voice.channel.id)
        
        # Добавляем треки из плейлиста в очередь
        added_tracks = 0
        for track_info in playlist["tracks"]:
            try:
                result = await self.wavelink.get_tracks(track_info["url"])
                if not result:
                    continue
                    
                # Если результат - плейлист, берем первый трек
                if isinstance(result, wavelink.Playlist):
                    track = result.tracks[0]
                else:
                    track = result[0]
                
                # Добавляем трек в очередь плеера
                await player.queue.put_wait(track)
                added_tracks += 1
                
            except Exception:
                # Если трек не удалось добавить, пропускаем его
                continue
        
        # Если ни один трек не был добавлен, сообщаем об ошибке
        if added_tracks == 0:
            embed = discord.Embed(
                title="Ошибка",
                description="Не удалось добавить ни один трек из плейлиста в очередь",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Создаем эмбед с информацией о воспроизведении
        embed = discord.Embed(
            title=f"Воспроизведение плейлиста: {name}",
            description=f"Добавлено {added_tracks} из {len(playlist['tracks'])} треков в очередь",
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed)
        
        # Если плеер не воспроизводит музыку, начинаем воспроизведение
        if not player.is_playing():
            await player.play(await player.queue.get_wait())

# Класс для кнопок голосования за плейлист
class PlaylistVotingView(discord.ui.View):
    def __init__(self, playlist_manager, guild_id, playlist_name):
        super().__init__(timeout=None)  # Кнопки работают до перезапуска бота
        self.playlist_manager = playlist_manager
        self.guild_id = guild_id
        self.playlist_name = playlist_name
    
    @discord.ui.button(label="👍 За", style=discord.ButtonStyle.green, custom_id="playlist_vote_up")
    async def vote_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для голосования 'за'"""
        await interaction.response.defer(ephemeral=True)
        
        # Регистрируем голос "за"
        success, message = await self.playlist_manager.vote(
            guild_id=self.guild_id,
            playlist_name=self.playlist_name,
            user_id=str(interaction.user.id),
            vote_type="up"
        )
        
        # Создаем эмбед с результатом
        embed = discord.Embed(
            title="Голосование за плейлист",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="👎 Против", style=discord.ButtonStyle.red, custom_id="playlist_vote_down")
    async def vote_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для голосования 'против'"""
        await interaction.response.defer(ephemeral=True)
        
        # Регистрируем голос "против"
        success, message = await self.playlist_manager.vote(
            guild_id=self.guild_id,
            playlist_name=self.playlist_name,
            user_id=str(interaction.user.id),
            vote_type="down"
        )
        
        # Создаем эмбед с результатом
        embed = discord.Embed(
            title="Голосование за плейлист",
            description=message,
            color=discord.Color.green() if success else discord.Color.red()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="ℹ️ Информация", style=discord.ButtonStyle.blurple, custom_id="playlist_info")
    async def playlist_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка для просмотра информации о плейлисте"""
        await interaction.response.defer(ephemeral=True)
        
        # Получаем информацию о плейлисте
        playlist = self.playlist_manager.get_playlist(self.guild_id, self.playlist_name)
        if not playlist:
            embed = discord.Embed(
                title="Ошибка",
                description=f"Плейлист '{self.playlist_name}' не найден",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Получаем статус голосования
        success, voting = self.playlist_manager.get_voting_status(self.guild_id, self.playlist_name)
        
        # Создаем эмбед с информацией о плейлисте и голосовании
        embed = discord.Embed(
            title=f"Плейлист: {playlist['name']}",
            color=discord.Color.blue()
        )
        
        # Добавляем информацию об авторе
        author = interaction.guild.get_member(int(playlist["author_id"]))
        author_name = author.display_name if author else "Неизвестно"
        embed.add_field(name="Автор", value=author_name, inline=True)
        
        # Добавляем информацию о статусе одобрения
        status = "✅ Одобрен" if playlist["votes"]["approved"] else "❌ Не одобрен"
        embed.add_field(name="Статус", value=status, inline=True)
        
        # Добавляем информацию о голосовании
        if success and not voting["finished"]:
            embed.add_field(
                name="Голосование",
                value=f"👍 За: {voting['up_votes']}\n👎 Против: {voting['down_votes']}",
                inline=True
            )
            
            # Рассчитываем оставшееся время
            if "end_time" in voting:
                remaining_time = max(0, voting["end_time"] - time.time())
                hours = int(remaining_time // 3600)
                minutes = int((remaining_time % 3600) // 60)
                embed.add_field(
                    name="Осталось времени",
                    value=f"{hours} ч {minutes} мин",
                    inline=True
                )
        
        # Добавляем список треков
        tracks = playlist["tracks"]
        if tracks:
            tracks_text = ""
            for i, track in enumerate(tracks[:10]):  # Показываем первые 10 треков
                tracks_text += f"{i+1}. {track['title']}\n"
            
            if len(tracks) > 10:
                tracks_text += f"...и ещё {len(tracks) - 10} трек(ов)"
                
            embed.add_field(name=f"Треки ({len(tracks)})", value=tracks_text, inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))
    
    # Синхронизация слэш-команд
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слэш-команд")
    except Exception as e:
        print(f"Ошибка при синхронизации слэш-команд: {e}") 