import json
import os
import asyncio
import time
from typing import Dict, List, Any, Tuple, Optional

class PlaylistManager:
    """Класс для управления плейлистами с хранением в JSON"""
    
    def __init__(self, playlists_file: str = "playlists.json"):
        """Инициализация менеджера плейлистов
        
        Args:
            playlists_file: Путь к файлу с плейлистами
        """
        self.playlists_file = playlists_file
        self.playlists: Dict[str, Dict[str, Any]] = {}
        self.voting_status: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        
        # Загружаем плейлисты из файла при инициализации
        self.load_playlists()
    
    def load_playlists(self):
        """Загружает плейлисты из JSON-файла"""
        try:
            if os.path.exists(self.playlists_file):
                with open(self.playlists_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.playlists = data.get('playlists', {})
                    self.voting_status = data.get('voting_status', {})
        except Exception as e:
            print(f"Ошибка при загрузке плейлистов: {e}")
            # Создаем пустые структуры данных в случае ошибки
            self.playlists = {}
            self.voting_status = {}
    
    async def save_playlists(self):
        """Сохраняет плейлисты в JSON-файл"""
        try:
            async with self.lock:
                with open(self.playlists_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'playlists': self.playlists,
                        'voting_status': self.voting_status
                    }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка при сохранении плейлистов: {e}")
    
    def _get_guild_key(self, guild_id: int) -> str:
        """Получение ключа для гильдии
        
        Args:
            guild_id: ID сервера
        
        Returns:
            Строковое представление ID сервера
        """
        return str(guild_id)
    
    def get_playlist(self, guild_id: int, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Получение плейлиста по имени
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
        
        Returns:
            Словарь с информацией о плейлисте или None, если плейлист не найден
        """
        guild_key = self._get_guild_key(guild_id)
        
        if guild_key not in self.playlists:
            return None
        
        return next((p for p in self.playlists[guild_key] if p['name'].lower() == playlist_name.lower()), None)
    
    def get_all_playlists(self, guild_id: int) -> List[Dict[str, Any]]:
        """Получение всех плейлистов для сервера
        
        Args:
            guild_id: ID сервера
        
        Returns:
            Список плейлистов
        """
        guild_key = self._get_guild_key(guild_id)
        
        if guild_key not in self.playlists:
            return []
        
        return self.playlists[guild_key]
    
    def get_approved_playlists(self, guild_id: int) -> List[Dict[str, Any]]:
        """Получение одобренных плейлистов для сервера
        
        Args:
            guild_id: ID сервера
        
        Returns:
            Список одобренных плейлистов
        """
        guild_key = self._get_guild_key(guild_id)
        
        if guild_key not in self.playlists:
            return []
        
        return [p for p in self.playlists[guild_key] if p['votes']['approved']]
    
    async def create_playlist(self, guild_id: int, name: str, author_id: int) -> Tuple[bool, str]:
        """Создание нового плейлиста
        
        Args:
            guild_id: ID сервера
            name: Название плейлиста
            author_id: ID автора плейлиста
        
        Returns:
            Кортеж (успех, сообщение)
        """
        guild_key = self._get_guild_key(guild_id)
        
        # Проверяем, существует ли секция для сервера
        if guild_key not in self.playlists:
            self.playlists[guild_key] = []
        
        # Проверяем, существует ли уже плейлист с таким именем
        if any(p['name'].lower() == name.lower() for p in self.playlists[guild_key]):
            return False, f"Плейлист с названием '{name}' уже существует"
        
        # Создаем новый плейлист
        new_playlist = {
            'name': name,
            'author_id': str(author_id),
            'tracks': [],
            'votes': {
                'up': [],
                'down': [],
                'approved': False
            }
        }
        
        # Добавляем плейлист в список
        self.playlists[guild_key].append(new_playlist)
        
        # Сохраняем изменения
        await self.save_playlists()
        
        return True, f"Плейлист '{name}' успешно создан"
    
    async def delete_playlist(self, guild_id: int, playlist_name: str) -> Tuple[bool, str]:
        """Удаление плейлиста
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
        
        Returns:
            Кортеж (успех, сообщение)
        """
        guild_key = self._get_guild_key(guild_id)
        
        # Проверяем, существует ли секция для сервера
        if guild_key not in self.playlists:
            return False, "На сервере нет плейлистов"
        
        # Ищем плейлист
        playlist_index = next((i for i, p in enumerate(self.playlists[guild_key]) 
                              if p['name'].lower() == playlist_name.lower()), -1)
        
        if playlist_index == -1:
            return False, f"Плейлист '{playlist_name}' не найден"
        
        # Удаляем плейлист
        del self.playlists[guild_key][playlist_index]
        
        # Удаляем информацию о голосовании, если есть
        voting_key = f"{guild_key}:{playlist_name.lower()}"
        if voting_key in self.voting_status:
            del self.voting_status[voting_key]
        
        # Сохраняем изменения
        await self.save_playlists()
        
        return True, f"Плейлист '{playlist_name}' успешно удален"
    
    async def add_track(self, guild_id: int, playlist_name: str, track: Dict[str, str]) -> Tuple[bool, str]:
        """Добавление трека в плейлист
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
            track: Информация о треке (url, title, author)
        
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем плейлист
        playlist = self.get_playlist(guild_id, playlist_name)
        
        if not playlist:
            return False, f"Плейлист '{playlist_name}' не найден"
        
        # Проверяем, есть ли уже трек с таким URL
        if any(t['url'] == track['url'] for t in playlist['tracks']):
            return False, "Этот трек уже есть в плейлисте"
        
        # Добавляем трек
        playlist['tracks'].append(track)
        
        # Сохраняем изменения
        await self.save_playlists()
        
        return True, f"Трек '{track['title']}' добавлен в плейлист '{playlist_name}'"
    
    async def remove_track(self, guild_id: int, playlist_name: str, index: int) -> Tuple[bool, str]:
        """Удаление трека из плейлиста по индексу
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
            index: Индекс трека (начиная с 0)
        
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем плейлист
        playlist = self.get_playlist(guild_id, playlist_name)
        
        if not playlist:
            return False, f"Плейлист '{playlist_name}' не найден"
        
        # Проверяем валидность индекса
        if index < 0 or index >= len(playlist['tracks']):
            return False, f"Неверный индекс трека. Доступны индексы от 0 до {len(playlist['tracks']) - 1}"
        
        # Получаем информацию о треке
        track_title = playlist['tracks'][index]['title']
        
        # Удаляем трек
        del playlist['tracks'][index]
        
        # Сохраняем изменения
        await self.save_playlists()
        
        return True, f"Трек '{track_title}' удален из плейлиста '{playlist_name}'"
    
    async def start_voting(self, guild_id: int, playlist_name: str, duration: int = 86400) -> Tuple[bool, str]:
        """Начало голосования за плейлист
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
            duration: Продолжительность голосования в секундах (по умолчанию 24 часа)
        
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем плейлист
        playlist = self.get_playlist(guild_id, playlist_name)
        
        if not playlist:
            return False, f"Плейлист '{playlist_name}' не найден"
        
        # Создаем ключ для голосования
        guild_key = self._get_guild_key(guild_id)
        voting_key = f"{guild_key}:{playlist_name.lower()}"
        
        # Проверяем, идет ли уже голосование
        if voting_key in self.voting_status and not self.voting_status[voting_key]["finished"]:
            return False, "Голосование за этот плейлист уже идет"
        
        # Начинаем голосование
        self.voting_status[voting_key] = {
            "start_time": time.time(),
            "end_time": time.time() + duration,
            "up_votes": 0,
            "down_votes": 0,
            "voted_users": [],
            "finished": False
        }
        
        # Сбрасываем предыдущие голоса в плейлисте
        playlist["votes"]["up"] = []
        playlist["votes"]["down"] = []
        
        # Сохраняем изменения
        await self.save_playlists()
        
        return True, f"Голосование за плейлист '{playlist_name}' начато"
    
    async def vote(self, guild_id: int, playlist_name: str, user_id: str, vote_type: str) -> Tuple[bool, str]:
        """Голосование за плейлист
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
            user_id: ID пользователя, который голосует
            vote_type: Тип голоса ('up' или 'down')
        
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем плейлист
        playlist = self.get_playlist(guild_id, playlist_name)
        
        if not playlist:
            return False, f"Плейлист '{playlist_name}' не найден"
        
        # Создаем ключ для голосования
        guild_key = self._get_guild_key(guild_id)
        voting_key = f"{guild_key}:{playlist_name.lower()}"
        
        # Проверяем, идет ли голосование
        if voting_key not in self.voting_status or self.voting_status[voting_key]["finished"]:
            return False, "Голосование за этот плейлист не активно"
        
        # Проверяем, не голосовал ли пользователь уже
        if user_id in self.voting_status[voting_key]["voted_users"]:
            return False, "Вы уже проголосовали за этот плейлист"
        
        # Регистрируем голос
        if vote_type == "up":
            playlist["votes"]["up"].append(user_id)
            self.voting_status[voting_key]["up_votes"] += 1
            message = "Вы проголосовали ЗА этот плейлист"
        else:
            playlist["votes"]["down"].append(user_id)
            self.voting_status[voting_key]["down_votes"] += 1
            message = "Вы проголосовали ПРОТИВ этого плейлиста"
        
        # Добавляем пользователя в список проголосовавших
        self.voting_status[voting_key]["voted_users"].append(user_id)
        
        # Проверяем условия окончания голосования
        up_votes = self.voting_status[voting_key]["up_votes"]
        down_votes = self.voting_status[voting_key]["down_votes"]
        
        # Плейлист одобрен, если за него проголосовало минимум 3 человека и голосов "за" больше чем "против"
        if up_votes >= 3 and up_votes > down_votes:
            playlist["votes"]["approved"] = True
            self.voting_status[voting_key]["finished"] = True
            message += ". Плейлист был одобрен!"
        # Плейлист отклонен, если против него проголосовало минимум 3 человека и голосов "против" больше чем "за"
        elif down_votes >= 3 and down_votes > up_votes:
            playlist["votes"]["approved"] = False
            self.voting_status[voting_key]["finished"] = True
            message += ". Плейлист был отклонен."
        
        # Сохраняем изменения
        await self.save_playlists()
        
        return True, message
    
    def get_voting_status(self, guild_id: int, playlist_name: str) -> Tuple[bool, Dict[str, Any]]:
        """Получение статуса голосования за плейлист
        
        Args:
            guild_id: ID сервера
            playlist_name: Название плейлиста
        
        Returns:
            Кортеж (успех, статус голосования)
        """
        # Создаем ключ для голосования
        guild_key = self._get_guild_key(guild_id)
        voting_key = f"{guild_key}:{playlist_name.lower()}"
        
        # Проверяем, есть ли информация о голосовании
        if voting_key not in self.voting_status:
            return False, {"error": "Голосование не найдено"}
        
        # Проверяем, не истекло ли время голосования
        if not self.voting_status[voting_key]["finished"]:
            current_time = time.time()
            end_time = self.voting_status[voting_key]["end_time"]
            
            if current_time > end_time:
                # Завершаем голосование по истечении времени
                self.voting_status[voting_key]["finished"] = True
                
                # Определяем результат голосования
                up_votes = self.voting_status[voting_key]["up_votes"]
                down_votes = self.voting_status[voting_key]["down_votes"]
                
                # Получаем плейлист
                playlist = self.get_playlist(guild_id, playlist_name)
                if playlist:
                    # Плейлист одобрен, если голосов "за" больше чем "против"
                    if up_votes > down_votes:
                        playlist["votes"]["approved"] = True
                    else:
                        playlist["votes"]["approved"] = False
                
                # Асинхронно сохраняем изменения
                asyncio.create_task(self.save_playlists())
        
        return True, self.voting_status[voting_key]
    
    async def check_expired_votings(self) -> None:
        """Проверка и завершение устаревших голосований"""
        current_time = time.time()
        changed = False
        
        for voting_key, voting in self.voting_status.items():
            if not voting["finished"] and current_time > voting.get("end_time", 0):
                # Завершаем голосование
                voting["finished"] = True
                changed = True
                
                # Получаем информацию о сервере и плейлисте
                guild_id, playlist_name = voting_key.split(":", 1)
                
                # Получаем плейлист
                playlist = self.get_playlist(int(guild_id), playlist_name)
                if playlist:
                    # Определяем результат голосования
                    up_votes = voting["up_votes"]
                    down_votes = voting["down_votes"]
                    
                    # Плейлист одобрен, если голосов "за" больше чем "против"
                    if up_votes > down_votes:
                        playlist["votes"]["approved"] = True
                    else:
                        playlist["votes"]["approved"] = False
        
        # Сохраняем изменения, если были завершены голосования
        if changed:
            await self.save_playlists() 