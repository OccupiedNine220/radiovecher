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
import datetime

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
        
        # Импортируем PlaylistManager только если он существует
        try:
            from playlist_manager import PlaylistManager
            self.playlist_manager = PlaylistManager()  # Менеджер плейлистов
        except ImportError:
            self.playlist_manager = None
            print("⚠️ PlaylistManager не найден, функциональность плейлистов недоступна!")
        
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
        """🎮 ПОЛУЧЕНИЕ ИЛИ СОЗДАНИЕ ПЛЕЕРА ДЛЯ СЕРВЕРА - УМНЫЙ ВЫБОР!!! 🎮"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            print(f"⚠️ Гильдия с ID {guild_id} не найдена!!! ⚠️")
            return None
            
        # Если плеер уже существует, возвращаем его
        if guild_id in self.bot.players:
            return self.bot.players[guild_id]
        
        # Иначе создаем новый плеер через функцию бота
        try:
            player = await self.bot.get_player(guild)
            
            # Настройка каналов для плеера
            player.voice_channel_id = VOICE_CHANNEL_ID
            player.text_channel_id = TEXT_CHANNEL_ID
            
            return player
        except Exception as e:
            print(f"❌ ОШИБКА ПРИ СОЗДАНИИ ПЛЕЕРА: {e}!!! ПРОВЕРЬТЕ НАСТРОЙКИ!!! ❌")
            return None
    
    @app_commands.command(name="start", description="Запуск музыкального плеера в голосовом канале")
    @app_commands.default_permissions(manage_guild=True)
    async def start_player(self, interaction: discord.Interaction):
        """Запуск музыкального плеера в указанном голосовом канале"""
        # Проверка прав пользователя
        if not self.has_admin_role(interaction.user):
            await interaction.response.send_message("У вас недостаточно прав для использования этой команды. Требуется право 'Управление сервером' или роль администратора.", ephemeral=True)
            return
        
        # Проверяем, находится ли пользователь в голосовом канале
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("Вы должны находиться в голосовом канале для использования этой команды.", ephemeral=True)
            return
            
        player = await self.get_player(interaction.guild_id)
        
        # Сохраняем ID голосового и текстового каналов
        player.voice_channel_id = interaction.user.voice.channel.id
        player.text_channel_id = interaction.channel_id
        
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
    
    @app_commands.command(name="radio", description="Включить радио")
    async def radio_command(self, interaction: discord.Interaction):
        """Переключение плеера в режим радио"""
        # Получаем или создаем плеер
        player = await self.get_player(interaction.guild_id)
        
        if not player:
            await interaction.response.send_message("Бот не подключен к голосовому каналу. Используйте команду `/start`.", ephemeral=True)
            return
        
        # Проверяем, находится ли пользователь в том же голосовом канале, что и бот
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.channel and interaction.user.voice and interaction.user.voice.channel:
            if voice_client.channel != interaction.user.voice.channel:
                await interaction.response.send_message(f"Вы должны быть в том же голосовом канале, что и бот ({voice_client.channel.mention}).", ephemeral=True)
                return
        
        await interaction.response.defer()
        
        # Переключаемся на радио
        await player.play_radio()
        
        # Отправляем подтверждение
        await interaction.followup.send(f"🎵 Переключено на радио: **{self.bot.current_radio['name']}**")
        
        # Обновляем админ-панель
        await self.schedule_update_admin_panel(interaction.guild_id)
    
    @app_commands.command(name="switch_radio", description="Переключить радиостанцию")
    async def switch_radio_command(self, interaction: discord.Interaction, станция: str):
        """Переключает текущую радиостанцию на выбранную"""
        guild_id = interaction.guild_id
        
        # Проверка, есть ли музыкальный плеер для этого сервера
        if guild_id not in self.players:
            await interaction.response.send_message(
                "Сначала необходимо запустить бота с помощью команды `/start`", 
                ephemeral=True
            )
            return
        
        # Пытаемся переключить радиостанцию
        radio_info = self.bot.switch_radio(станция)
        
        if not radio_info:
            # Если радиостанция не найдена, показываем список доступных
            available_radios = ", ".join([f"**{key}**" for key in self.bot.available_radios.keys()])
            await interaction.response.send_message(
                f"Радиостанция не найдена. Доступные станции: {available_radios}",
                ephemeral=True
            )
            return
            
        await interaction.response.defer()
        
        player = self.players[guild_id]
        
        # Играем выбранную радиостанцию
        success = await player.play_radio(
            radio_info['url'], 
            radio_info['name'],
            radio_info['thumbnail']
        )
        
        if success:
            embed = discord.Embed(
                title="Радиостанция изменена",
                description=f"🎵 Переключаюсь на **{radio_info['name']}**",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=radio_info['thumbnail'])
            
            await interaction.followup.send(embed=embed)
        
            # Обновление статуса бота
            await self.bot.update_presence(f"{radio_info['name']}")
            await self.schedule_update_admin_panel(guild_id, f"▶️ Играет {radio_info['name']}")
        else:
            await interaction.followup.send(
                "Произошла ошибка при переключении радиостанции", 
                ephemeral=True
            )
    
    @app_commands.command(name="webpanel", description="Получить ссылку на веб-панель управления ботом")
    async def webpanel(self, interaction: discord.Interaction):
        """Отправляет ссылку на веб-панель управления ботом"""
        # Получаем URL веб-панели из web/server.py
        from web.server import get_web_url
        
        web_url = get_web_url()
        
        if not web_url:
            await interaction.response.send_message("Веб-панель недоступна. Проверьте настройки бота.", ephemeral=True)
            return
        
        # Создаем ссылку на страницу очереди для текущего сервера
        queue_url = f"{web_url}/queue/{interaction.guild_id}"
        
        embed = discord.Embed(
            title="Веб-панель Радио Вечер",
            description="Используйте эти ссылки для управления ботом через веб-интерфейс:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Главная панель",
            value=f"[Открыть в браузере]({web_url})",
            inline=False
        )
        
        embed.add_field(
            name="Управление этим сервером",
            value=f"[Открыть в браузере]({queue_url})",
            inline=False
        )
        
        embed.set_footer(text=f"Радио Вечер • {datetime.datetime.now().year}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="play", description="Добавить трек в очередь")
    async def play_command(self, interaction: discord.Interaction, запрос: str):
        """Добавление трека в очередь воспроизведения"""
        # ... existing code ...

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