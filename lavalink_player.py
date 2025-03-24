import asyncio
import discord
import wavelink
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from typing import Optional, Dict, List, Union, Set

# Загрузка переменных окружения
load_dotenv()

# Настройка Spotify API
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Настройки радио из .env
RADIO_STREAM_URL = os.getenv('RADIO_STREAM_URL', 'https://rusradio.hostingradio.ru/rusradio96.aacp')
RADIO_NAME = os.getenv('RADIO_NAME', 'Русское Радио')
RADIO_THUMBNAIL = os.getenv('RADIO_THUMBNAIL', 'https://rusradio.ru/design/images/share.jpg')

# Настройки Lavalink
LAVALINK_HOST = os.getenv('LAVALINK_HOST', 'localhost')
LAVALINK_PORT = int(os.getenv('LAVALINK_PORT', '2333'))
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
LAVALINK_SECURE = os.getenv('LAVALINK_SECURE', 'false').lower() == 'true'

class LavalinkPlayer:
    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id
        self.voice_channel_id = None
        self.text_channel_id = None
        self.player = None
        self.current_track = None
        self.queue = []
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
            
            # Подключение через Wavelink
            self.player = await channel.connect(cls=wavelink.Player)
            
            # Установка обработчика событий
            self.player.autoplay = wavelink.AutoPlayMode.disabled
            
            # Добавляем обработчики событий
            self.player.queue.set_player(self.player)
            
            # Регистрируем хук для отслеживания окончания треков
            self.player.queue.callback = self._on_track_end
            
            self.reconnect_attempts = 0
            return True
        except Exception as e:
            print(f"Ошибка при подключении к голосовому каналу: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от голосового канала"""
        if self.player and self.player.is_connected():
            await self.player.disconnect()
            self.player = None
    
    async def play_default_radio(self):
        """Воспроизведение радио по умолчанию"""
        if not self.player or not self.player.is_connected():
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
            
            # Воспроизводим поток через Lavalink
            track = await wavelink.Playable.search(RADIO_STREAM_URL)
            if isinstance(track, wavelink.Playlist):
                track = track.tracks[0]
            
            await self.player.play(track)
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
    
    async def _on_track_end(self, event: wavelink.TrackEndEventPayload):
        """Обработчик окончания трека"""
        if self.queue:
            # Воспроизведение следующего трека из очереди
            next_track = self.queue.pop(0)
            await self.play_track(next_track)
        else:
            # Возврат к радио по умолчанию
            await self.play_default_radio()
    
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
        if not self.player or not self.player.is_connected():
            success = await self.connect()
            if not success:
                return False
        
        try:
            self.current_track = track_info
            
            # Сбрасываем голоса при смене трека
            self.skip_votes.clear()
            
            # Если URL уже есть, используем его, иначе ищем через Wavelink
            if 'wavelink_track' in track_info:
                track = track_info['wavelink_track']
            else:
                track = await wavelink.Playable.search(track_info['url'])
                if isinstance(track, wavelink.Playlist):
                    track = track.tracks[0]
                elif isinstance(track, list) and track:
                    track = track[0]
            
            # Обновляем информацию о треке
            if hasattr(track, 'uri'):
                self.current_track['url'] = track.uri
            
            # Воспроизводим трек
            await self.player.play(track)
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
                
                # Поиск трека через Lavalink (Wavelink)
                search_query = f"{track_info['title']} {track_info['artist']}"
                wavelink_tracks = await wavelink.Playable.search(search_query)
                
                if not wavelink_tracks:
                    return False, "Не удалось найти трек."
                
                if isinstance(wavelink_tracks, wavelink.Playlist):
                    wavelink_track = wavelink_tracks.tracks[0]
                elif isinstance(wavelink_tracks, list) and wavelink_tracks:
                    wavelink_track = wavelink_tracks[0]
                else:
                    wavelink_track = wavelink_tracks
                
                # Объединение информации
                track_info.update({
                    'wavelink_track': wavelink_track,
                    'url': wavelink_track.uri if hasattr(wavelink_track, 'uri') else search_query,
                    'source': 'spotify'
                })
                
                self.queue.append(track_info)
                
                # Если ничего не воспроизводится, начать воспроизведение
                if not self.is_playing:
                    await self.play_track(self.queue.pop(0))
                
                return True, f"Трек {track_info['title']} добавлен в очередь."
            
            elif 'youtube.com' in query or 'youtu.be' in query or 'soundcloud.com' in query:
                # Поиск через Lavalink
                wavelink_tracks = await wavelink.Playable.search(query)
                
                if not wavelink_tracks:
                    return False, "Не удалось найти трек."
                
                if isinstance(wavelink_tracks, wavelink.Playlist):
                    # Это плейлист, добавляем все треки
                    for wavelink_track in wavelink_tracks.tracks:
                        track_info = {
                            'title': wavelink_track.title,
                            'url': wavelink_track.uri if hasattr(wavelink_track, 'uri') else query,
                            'thumbnail': getattr(wavelink_track, 'artwork', None) or 'https://i.ytimg.com/vi/default/hqdefault.jpg',
                            'wavelink_track': wavelink_track,
                            'source': 'youtube' if 'youtube' in query else 'soundcloud'
                        }
                        self.queue.append(track_info)
                    
                    # Если ничего не воспроизводится, начать воспроизведение
                    if not self.is_playing and self.queue:
                        await self.play_track(self.queue.pop(0))
                    
                    return True, f"Плейлист с {len(wavelink_tracks.tracks)} треками добавлен в очередь."
                
                elif isinstance(wavelink_tracks, list) and wavelink_tracks:
                    wavelink_track = wavelink_tracks[0]
                else:
                    wavelink_track = wavelink_tracks
                
                track_info = {
                    'title': wavelink_track.title,
                    'url': wavelink_track.uri if hasattr(wavelink_track, 'uri') else query,
                    'thumbnail': getattr(wavelink_track, 'artwork', None) or 'https://i.ytimg.com/vi/default/hqdefault.jpg',
                    'wavelink_track': wavelink_track,
                    'source': 'youtube' if 'youtube' in query else 'soundcloud'
                }
                
                self.queue.append(track_info)
                
                # Если ничего не воспроизводится, начать воспроизведение
                if not self.is_playing:
                    await self.play_track(self.queue.pop(0))
                
                return True, f"Трек {track_info['title']} добавлен в очередь."
            
            else:
                # Обработка поискового запроса
                wavelink_tracks = await wavelink.Playable.search(query)
                
                if not wavelink_tracks:
                    return False, "Не удалось найти трек."
                
                if isinstance(wavelink_tracks, list) and wavelink_tracks:
                    wavelink_track = wavelink_tracks[0]
                else:
                    wavelink_track = wavelink_tracks
                
                track_info = {
                    'title': wavelink_track.title,
                    'url': wavelink_track.uri if hasattr(wavelink_track, 'uri') else query,
                    'thumbnail': getattr(wavelink_track, 'artwork', None) or 'https://i.ytimg.com/vi/default/hqdefault.jpg',
                    'wavelink_track': wavelink_track,
                    'source': 'youtube'  # По умолчанию предполагаем, что это YouTube
                }
                
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
            track_id = spotify_url.split('/')[-1].split('?')[0]
            
            # Получение информации о треке через API Spotify
            track = self.sp.track(track_id)
            
            # Формирование информации о треке
            return {
                'title': track['name'],
                'artist': ', '.join([artist['name'] for artist in track['artists']]),
                'thumbnail': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'duration': track['duration_ms'] / 1000  # Конвертация в секунды
            }
        except Exception as e:
            print(f"Ошибка при получении информации о треке Spotify: {e}")
            return None
    
    async def skip(self):
        """Пропуск текущего трека"""
        if self.player and self.is_playing:
            await self.player.stop()
            return True
        return False
    
    async def vote_skip(self, user_id):
        """Голосование за пропуск трека"""
        if not self.is_playing:
            return False, "Сейчас ничего не воспроизводится."
        
        # Получение информации о текущем голосовом канале
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return False, "Не удалось найти сервер."
        
        voice_channel = guild.get_channel(self.voice_channel_id)
        if not voice_channel:
            return False, "Не удалось найти голосовой канал."
        
        # Подсчет пользователей в голосовом канале (исключая ботов)
        members_count = sum(1 for member in voice_channel.members if not member.bot)
        
        # Если только один человек в канале или это радио, пропускаем без голосования
        if members_count <= 1 or self.current_track.get('source') == 'stream':
            await self.skip()
            return True, "Трек пропущен."
        
        # Иначе голосование
        self.skip_votes.add(user_id)
        
        # Вычисляем необходимое количество голосов (половина участников, округленная вверх)
        required_votes = max(2, round(members_count / 2))
        self.votes_required = required_votes
        
        # Проверка, достаточно ли голосов
        if len(self.skip_votes) >= required_votes:
            await self.skip()
            return True, f"Трек пропущен. Голосов: {len(self.skip_votes)}/{required_votes}"
        else:
            return False, f"Голосов за пропуск: {len(self.skip_votes)}/{required_votes}"
    
    async def pause(self):
        """Приостановка воспроизведения"""
        if self.player and self.is_playing and not self.is_paused:
            await self.player.pause()
            self.is_paused = True
            return True
        return False
    
    async def resume(self):
        """Возобновление воспроизведения"""
        if self.player and self.is_playing and self.is_paused:
            await self.player.resume()
            self.is_paused = False
            return True
        return False
    
    async def stop(self):
        """Остановка плеера и отключение от голосового канала"""
        if self.player:
            self.is_playing = False
            self.is_paused = False
            self.queue.clear()
            await self.player.disconnect()
            self.player = None
            return True
        return False
    
    async def send_now_playing_embed(self):
        """Отправка эмбеда с информацией о текущем треке"""
        try:
            text_channel = self.bot.get_channel(self.text_channel_id)
            if not text_channel:
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    text_channel = guild.get_channel(self.text_channel_id)
            
            if not text_channel:
                print(f"Не удалось найти текстовый канал с ID {self.text_channel_id}")
                return
            
            embed = discord.Embed(
                title="Сейчас играет:",
                description=f"**{self.current_track['title']}**",
                color=discord.Color.blue()
            )
            
            if 'artist' in self.current_track:
                embed.add_field(name="Исполнитель", value=self.current_track['artist'], inline=True)
            
            if 'source' in self.current_track:
                if self.current_track['source'] == 'stream':
                    embed.add_field(name="Источник", value="📻 Радиостанция", inline=True)
                elif self.current_track['source'] == 'spotify':
                    embed.add_field(name="Источник", value="<:spotify:1234567890> Spotify", inline=True)
                elif self.current_track['source'] == 'youtube':
                    embed.add_field(name="Источник", value="<:youtube:1234567890> YouTube", inline=True)
                elif self.current_track['source'] == 'soundcloud':
                    embed.add_field(name="Источник", value="<:soundcloud:1234567890> SoundCloud", inline=True)
            
            if 'thumbnail' in self.current_track and self.current_track['thumbnail']:
                embed.set_thumbnail(url=self.current_track['thumbnail'])
            
            # Добавление информации о следующих треках в очереди
            if self.queue:
                next_tracks = "\n".join([f"{i+1}. {track['title']}" for i, track in enumerate(self.queue[:3])])
                if len(self.queue) > 3:
                    next_tracks += f"\n...и еще {len(self.queue) - 3} трек(ов)"
                embed.add_field(name="В очереди:", value=next_tracks, inline=False)
            
            # Добавление кнопок управления
            view = MusicControlView(self)
            
            # Отправка или обновление сообщения
            try:
                # Попытка очистить предыдущие сообщения бота в канале
                async for message in text_channel.history(limit=10):
                    if message.author == self.bot.user and message.embeds:
                        await message.delete()
            except Exception as e:
                print(f"Ошибка при очистке предыдущих сообщений: {e}")
            
            await text_channel.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"Ошибка при отправке информации о текущем треке: {e}")
    
    async def play_radio(self, radio_url, radio_name, radio_thumbnail=None):
        """Воспроизведение радиостанции

        Args:
            radio_url: URL потока радиостанции
            radio_name: Название радиостанции
            radio_thumbnail: URL изображения радиостанции

        Returns:
            bool: Успешность операции
        """
        try:
            # Останавливаем текущее воспроизведение
            await self.stop()
            
            # Получаем трек для воспроизведения
            search_result = await wavelink.Playable.search(radio_url)
            
            if not search_result:
                print(f"Не удалось найти поток для {radio_name}")
                return False
                
            track = search_result[0]
            
            # Добавляем метаданные радиостанции
            track.title = f"Радиостанция: {radio_name}"
            track.author = "Прямой эфир"
            track.is_radio = True
            track.radio_name = radio_name
            track.radio_thumbnail = radio_thumbnail
            
            # Воспроизводим поток
            await self.player.play(track)
            
            # Обновляем состояние и интерфейс
            await self.update_player_state()
            await self.update_player_message()
            
            return True
            
        except Exception as e:
            print(f"Ошибка при воспроизведении радио {radio_name}: {e}")
            return False
            
    async def search_similar_tracks(self, query, limit=10):
        """Поиск треков, похожих на запрос

        Args:
            query: Поисковый запрос или URL трека
            limit: Максимальное количество треков

        Returns:
            list: Список похожих треков
        """
        try:
            # Сначала ищем по запросу
            search_result = await wavelink.Playable.search(query)
            
            if not search_result:
                return []
                
            # Берем первый трек из результатов поиска
            base_track = search_result[0]
            
            # Если это URL трека, используем его для поиска рекомендаций
            if "youtube.com" in query or "youtu.be" in query:
                # Для YouTube можно использовать рекомендации API
                recommendations = await wavelink.Playable.search(f"ytsearch:{base_track.title} {base_track.author} mix")
            elif "spotify.com" in query:
                # Для Spotify можно использовать поиск по артисту
                recommendations = await wavelink.Playable.search(f"spsearch:{base_track.author} top tracks")
            else:
                # Для обычного поиска используем похожие треки
                recommendations = await wavelink.Playable.search(f"{base_track.title} {base_track.author} similar")
            
            # Фильтруем результаты, чтобы избежать дубликатов
            unique_tracks = []
            seen_titles = set()
            
            # Добавляем базовый трек в начало
            unique_tracks.append(base_track)
            seen_titles.add(base_track.title.lower())
            
            # Добавляем уникальные рекомендации
            for track in recommendations:
                if track.title.lower() not in seen_titles and len(unique_tracks) < limit:
                    unique_tracks.append(track)
                    seen_titles.add(track.title.lower())
            
            return unique_tracks[:limit]
            
        except Exception as e:
            print(f"Ошибка при поиске похожих треков: {e}")
            return []
            
    async def search_track(self, query):
        """Поиск треков по запросу

        Args:
            query: Поисковый запрос или URL

        Returns:
            list: Список найденных треков
        """
        try:
            # Ищем треки по запросу
            search_result = await wavelink.Playable.search(query)
            return search_result
        except Exception as e:
            print(f"Ошибка при поиске трека: {e}")
            return []
            
    def get_queue(self):
        """Получение текущей очереди воспроизведения

        Returns:
            list: Список треков в очереди
        """
        return list(self.queue)
        
    def is_playing(self):
        """Проверка, воспроизводится ли музыка

        Returns:
            bool: True, если музыка играет, иначе False
        """
        return self.player is not None and self.player.is_playing()

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
        # Только администраторы могут полностью останавить плеер
        if interaction.user.guild_permissions.administrator:
            await self.player.stop()
            await interaction.response.send_message("Плеер остановлен", ephemeral=True)
        else:
            await interaction.response.send_message("У вас нет прав на остановку плеера", ephemeral=True)
    
    @discord.ui.button(label="⏯️ Пауза/Продолжить", style=discord.ButtonStyle.secondary)
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.is_paused:
            success = await self.player.resume()
            if success:
                await interaction.response.send_message("Воспроизведение возобновлено", ephemeral=True)
            else:
                await interaction.response.send_message("Не удалось возобновить воспроизведение", ephemeral=True)
        else:
            success = await self.player.pause()
            if success:
                await interaction.response.send_message("Воспроизведение приостановлено", ephemeral=True)
            else:
                await interaction.response.send_message("Не удалось приостановить воспроизведение", ephemeral=True)
    
    @discord.ui.button(label="🎵 Добавить трек", style=discord.ButtonStyle.success)
    async def add_track_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Открытие модального окна для добавления трека
        await interaction.response.send_modal(AddTrackModal(self.player))

class AddTrackModal(discord.ui.Modal, title="Добавить трек"):
    def __init__(self, player):
        super().__init__()
        self.player = player
    
    track_input = discord.ui.TextInput(
        label="Ссылка на трек или поисковый запрос",
        placeholder="Введите ссылку на YouTube/Spotify или название трека...",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        success, message = await self.player.add_to_queue(self.track_input.value)
        await interaction.response.send_message(message, ephemeral=True) 