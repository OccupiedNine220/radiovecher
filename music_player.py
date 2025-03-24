import asyncio
import discord
import yt_dlp
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка Spotify API
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Настройки радио из .env
RADIO_STREAM_URL = os.getenv('RADIO_STREAM_URL', 'https://rusradio.hostingradio.ru/rusradio96.aacp')
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')
RADIO_THUMBNAIL = os.getenv('RADIO_THUMBNAIL', 'https://rusradio.ru/design/images/share.jpg')

# Настройки для yt-dlp
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

# Настройки для FFmpeg
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

class MusicPlayer:
    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id
        self.voice_channel_id = None
        self.text_channel_id = None
        self.voice_client = None
        self.current_track = None
        self.queue = []
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self.is_playing = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.is_paused = False
        self.skip_votes = set()  # Множество ID пользователей, проголосовавших за пропуск
        self.votes_required = 3  # Количество голосов, необходимое для пропуска
        
        # Настройка Spotify клиента
        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
            self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET
            ))
        else:
            self.sp = None
    
    async def connect(self):
        """Подключение к голосовому каналу"""
        try:
            # Проверяем, указан ли ID голосового канала
            if not self.voice_channel_id:
                print(f"Ошибка: ID голосового канала не указан для сервера {self.guild_id}")
                return False
                
            channel = self.bot.get_channel(self.voice_channel_id)
            if not channel:
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    channel = guild.get_channel(self.voice_channel_id)
            
            if not channel:
                raise ValueError(f"Не удалось найти голосовой канал с ID {self.voice_channel_id}")
            
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.move_to(channel)
            else:
                self.voice_client = await channel.connect()
            
            self.reconnect_attempts = 0
            return True
        except Exception as e:
            print(f"Ошибка при подключении к голосовому каналу: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от голосового канала"""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None
    
    async def play_default_radio(self):
        """Воспроизведение радио по умолчанию"""
        if not self.voice_client or not self.voice_client.is_connected():
            success = await self.connect()
            if not success:
                return False
        
        try:
            self.current_track = {
                'title': RADIO_NAME,
                'url': RADIO_STREAM_URL,
                'thumbnail': RADIO_THUMBNAIL,
                'source': 'stream'
            }
            
            # Сбрасываем голоса при возврате к радио
            self.skip_votes.clear()
            
            source = discord.FFmpegPCMAudio(RADIO_STREAM_URL, **FFMPEG_OPTIONS)
            self.voice_client.play(source, after=self._play_next_or_radio)
            self.is_playing = True
            self.is_paused = False
            
            # Отправка информации о текущем треке
            await self.send_now_playing_embed()
            return True
        except Exception as e:
            print(f"Ошибка при воспроизведении радио: {e}")
            self.reconnect_attempts += 1
            if self.reconnect_attempts < self.max_reconnect_attempts:
                await asyncio.sleep(2)
                return await self.play_default_radio()
            return False
    
    def _play_next_or_radio(self, error=None):
        """Callback для воспроизведения следующего трека или возврата к радио"""
        if error:
            print(f"Ошибка воспроизведения: {error}")
            self.reconnect_attempts += 1
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                print("Превышено максимальное количество попыток переподключения")
                return
            
            # Попытка переподключения и воспроизведения
            asyncio.run_coroutine_threadsafe(self._handle_playback_error(), self.bot.loop)
            return
        
        self.is_playing = False
        
        if self.queue:
            # Воспроизведение следующего трека из очереди
            next_track = self.queue.pop(0)
            asyncio.run_coroutine_threadsafe(self.play_track(next_track), self.bot.loop)
        else:
            # Возврат к радио по умолчанию
            asyncio.run_coroutine_threadsafe(self.play_default_radio(), self.bot.loop)
    
    async def _handle_playback_error(self):
        """Обработка ошибок воспроизведения"""
        try:
            # Переподключение к голосовому каналу
            await self.disconnect()
            await asyncio.sleep(2)
            success = await self.connect()
            
            if success:
                # Повторная попытка воспроизведения
                if self.current_track:
                    if self.current_track['source'] == 'stream':
                        await self.play_default_radio()
                    else:
                        await self.play_track(self.current_track)
                else:
                    await self.play_default_radio()
        except Exception as e:
            print(f"Ошибка при обработке ошибки воспроизведения: {e}")
    
    async def play_track(self, track_info):
        """Воспроизведение трека"""
        if not self.voice_client or not self.voice_client.is_connected():
            success = await self.connect()
            if not success:
                return False
        
        try:
            self.current_track = track_info
            
            if self.voice_client.is_playing():
                self.voice_client.stop()
            
            # Сбрасываем голоса при смене трека
            self.skip_votes.clear()
            
            source = discord.FFmpegPCMAudio(track_info['url'], **FFMPEG_OPTIONS)
            self.voice_client.play(source, after=self._play_next_or_radio)
            self.is_playing = True
            self.is_paused = False
            
            # Отправка информации о текущем треке
            await self.send_now_playing_embed()
            return True
        except Exception as e:
            print(f"Ошибка при воспроизведении трека: {e}")
            return False
    
    async def add_to_queue(self, query):
        """Добавление трека в очередь"""
        try:
            # Проверка, является ли запрос Spotify URL
            if 'spotify.com' in query:
                if not self.sp:
                    return False, "Spotify API не настроен. Проверьте ваши учетные данные Spotify."
                
                track_info = await self._get_spotify_track_info(query)
                if not track_info:
                    return False, "Не удалось получить информацию о треке Spotify."
                
                # Поиск трека на YouTube для воспроизведения
                search_query = f"{track_info['title']} {track_info['artist']}"
                youtube_info = await self._get_youtube_track_info(search_query)
                
                if not youtube_info:
                    return False, "Не удалось найти трек на YouTube."
                
                # Объединение информации
                track_info.update({
                    'url': youtube_info['url'],
                    'source': 'youtube'
                })
                
                self.queue.append(track_info)
                
                # Если ничего не воспроизводится, начать воспроизведение
                if not self.is_playing:
                    await self.play_track(self.queue.pop(0))
                
                return True, f"Трек {track_info['title']} добавлен в очередь."
            else:
                # Обработка обычного запроса (YouTube, прямая ссылка и т.д.)
                track_info = await self._get_youtube_track_info(query)
                
                if not track_info:
                    return False, "Не удалось найти трек."
                
                self.queue.append(track_info)
                
                # Если ничего не воспроизводится, начать воспроизведение
                if not self.is_playing:
                    await self.play_track(self.queue.pop(0))
                
                return True, f"Трек {track_info['title']} добавлен в очередь."
        except Exception as e:
            print(f"Ошибка при добавлении трека в очередь: {e}")
            return False, f"Произошла ошибка: {str(e)}"
    
    async def _get_spotify_track_info(self, spotify_url):
        """Получение информации о треке Spotify"""
        try:
            # Извлечение ID трека из URL
            if 'track' in spotify_url:
                track_id = spotify_url.split('track/')[1].split('?')[0]
                track = self.sp.track(track_id)
                
                return {
                    'title': track['name'],
                    'artist': track['artists'][0]['name'],
                    'thumbnail': track['album']['images'][0]['url'] if track['album']['images'] else None,
                    'source': 'spotify'
                }
            return None
        except Exception as e:
            print(f"Ошибка при получении информации о треке Spotify: {e}")
            return None
    
    async def _get_youtube_track_info(self, query):
        """Получение информации о треке с YouTube"""
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(query, download=False))
            
            if 'entries' in data:
                # Берем первый результат из плейлиста
                data = data['entries'][0]
            
            return {
                'title': data['title'],
                'url': data['url'],
                'thumbnail': data['thumbnail'] if 'thumbnail' in data else None,
                'source': 'youtube'
            }
        except Exception as e:
            print(f"Ошибка при получении информации о треке с YouTube: {e}")
            return None
    
    async def skip(self):
        """Пропуск текущего трека"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            return True
        return False
    
    async def vote_skip(self, user_id):
        """Голосование за пропуск трека"""
        if not self.is_playing:
            return False, "Сейчас ничего не воспроизводится."
        
        # Проверка, голосовал ли уже пользователь
        if user_id in self.skip_votes:
            return False, "Вы уже проголосовали за пропуск трека."
        
        # Добавление голоса
        self.skip_votes.add(user_id)
        
        # Получаем количество людей в голосовом канале (не считая ботов)
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return False, "Не удалось получить информацию о сервере."
        
        voice_channel = guild.get_channel(self.voice_channel_id)
        if not voice_channel:
            return False, "Не удалось получить информацию о голосовом канале."
        
        members_count = sum(1 for member in voice_channel.members if not member.bot)
        
        # Вычисляем необходимое количество голосов (половина присутствующих, минимум 2)
        required_votes = max(2, members_count // 2)
        
        current_votes = len(self.skip_votes)
        
        if current_votes >= required_votes:
            # Достаточно голосов для пропуска
            self.skip_votes.clear()  # Сбрасываем голоса
            success = await self.skip()
            return success, "Трек пропущен по результатам голосования."
        else:
            # Недостаточно голосов
            return False, f"Голос учтён. Необходимо ещё {required_votes - current_votes} голосов для пропуска трека ({current_votes}/{required_votes})."
    
    async def pause(self):
        """Приостановка воспроизведения"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.is_paused = True
            return True
        return False
    
    async def resume(self):
        """Возобновление воспроизведения"""
        if self.voice_client and self.is_paused:
            self.voice_client.resume()
            self.is_paused = False
            return True
        return False
    
    async def stop(self):
        """Остановка воспроизведения и очистка очереди"""
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.is_playing():
                self.voice_client.stop()
            self.queue = []
            self.is_playing = False
            self.is_paused = False
            self.skip_votes.clear()  # Сбрасываем голоса при остановке
            return True
        return False
    
    async def send_now_playing_embed(self):
        """Отправка эмбеда с информацией о текущем треке"""
        if not self.current_track:
            return
        
        text_channel = self.bot.get_channel(self.text_channel_id)
        if not text_channel:
            return
        
        embed = discord.Embed(
            title="Сейчас играет",
            description=self.current_track['title'],
            color=discord.Color.blue()
        )
        
        if 'thumbnail' in self.current_track and self.current_track['thumbnail']:
            embed.set_thumbnail(url=self.current_track['thumbnail'])
        
        if 'artist' in self.current_track:
            embed.add_field(name="Исполнитель", value=self.current_track['artist'], inline=True)
        
        source_name = "Радио"
        if self.current_track['source'] == 'youtube':
            source_name = "YouTube"
        elif self.current_track['source'] == 'spotify':
            source_name = "Spotify"
        
        embed.add_field(name="Источник", value=source_name, inline=True)
        
        # Создание кнопок управления
        view = MusicControlView(self)
        
        # Отправка сообщения и закрепление его
        try:
            # Проверка наличия закрепленных сообщений
            pins = await text_channel.pins()
            for pin in pins:
                if pin.author == self.bot.user and "Сейчас играет" in pin.content:
                    await pin.unpin()
                    await pin.delete()
            
            message = await text_channel.send(embed=embed, view=view)
            await message.pin()
        except Exception as e:
            print(f"Ошибка при отправке эмбеда: {e}")
            await text_channel.send(embed=embed, view=view)

class MusicControlView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player
    
    @discord.ui.button(label="⏭️ Пропустить", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверяем через голосование
        success, message = await self.player.vote_skip(interaction.user.id)
        await interaction.response.send_message(message, ephemeral=True)
    
    @discord.ui.button(label="⏹️ Стоп", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.stop()
        await self.player.play_default_radio()
        await interaction.response.send_message(f"Воспроизведение остановлено. Возврат к {RADIO_NAME}.", ephemeral=True)
    
    @discord.ui.button(label="⏯️ Пауза/Продолжить", style=discord.ButtonStyle.secondary)
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.is_paused:
            success = await self.player.resume()
            if success:
                await interaction.response.send_message("Воспроизведение возобновлено.", ephemeral=True)
            else:
                await interaction.response.send_message("Нечего возобновлять.", ephemeral=True)
        else:
            success = await self.player.pause()
            if success:
                await interaction.response.send_message("Воспроизведение приостановлено.", ephemeral=True)
            else:
                await interaction.response.send_message("Нечего приостанавливать.", ephemeral=True)
    
    @discord.ui.button(label="🎵 Добавить трек", style=discord.ButtonStyle.success)
    async def add_track_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Открытие модального окна для добавления трека
        modal = AddTrackModal(self.player)
        await interaction.response.send_modal(modal)

class AddTrackModal(discord.ui.Modal, title="Добавить трек"):
    def __init__(self, player):
        super().__init__()
        self.player = player
    
    track_input = discord.ui.TextInput(
        label="Ссылка на трек или поисковый запрос",
        placeholder="Введите ссылку на Spotify или поисковый запрос",
        required=True,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        query = self.track_input.value
        success, message = await self.player.add_to_queue(query)
        
        if success:
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.response.send_message(f"Ошибка: {message}", ephemeral=True) 