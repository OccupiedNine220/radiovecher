import os
import json
import time
import threading
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO
from dotenv import load_dotenv
import sys
import logging

# Добавление пути родительской директории
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Глобальная переменная для хранения экземпляра бота
BOT_INSTANCE = None

# Создание Flask приложения и SocketIO
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'radio_vecher_secret')
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные переменные для хранения состояния
current_guild_players = {}
queue_cache = {}
current_track_cache = {}

# Интервал обновления кеша (в секундах)
CACHE_UPDATE_INTERVAL = 3


def initialize_web_server(bot):
    """Инициализирует и запускает веб-сервер в отдельном потоке
    
    Args:
        bot: Экземпляр бота Discord
    """
    global BOT_INSTANCE
    BOT_INSTANCE = bot
    
    # Запуск потока обновления кеша
    threading.Thread(
        target=update_cache_thread,
        daemon=True
    ).start()
    
    # Запуск веб-сервера в отдельном потоке
    port = int(os.getenv('FLASK_PORT', 5000))
    threading.Thread(
        target=lambda: socketio.run(app, debug=False, host='0.0.0.0', port=port),
        daemon=True
    ).start()


def update_cache_thread():
    """Фоновый поток для обновления кеша данных"""
    while True:
        try:
            if BOT_INSTANCE:
                update_players_cache()
                update_queue_cache()
                
                # Отправка обновлений через Socket.IO
                socketio.emit('queue_update', queue_cache)
                socketio.emit('current_track_update', current_track_cache)
        except Exception as e:
            logger.error(f"Ошибка при обновлении кеша: {e}")
        
        time.sleep(CACHE_UPDATE_INTERVAL)


def update_players_cache():
    """Обновление кеша плееров"""
    global current_guild_players
    
    if not BOT_INSTANCE:
        return
    
    current_guild_players = {}
    
    for guild_id, players in BOT_INSTANCE.players.items():
        try:
            guild = BOT_INSTANCE.get_guild(guild_id)
            if guild:
                guild_name = guild.name
                current_guild_players[guild_id] = {
                    'id': guild_id,
                    'name': guild_name,
                    'connected': players.is_connected if hasattr(players, 'is_connected') else False
                }
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных гильдии {guild_id}: {e}")


def update_queue_cache():
    """Обновление кеша очереди и текущего трека"""
    global queue_cache, current_track_cache
    
    if not BOT_INSTANCE or not current_guild_players:
        return
    
    queue_cache = {}
    current_track_cache = {}
    
    for guild_id, guild_info in current_guild_players.items():
        try:
            # Получаем плеер для этой гильдии
            player = BOT_INSTANCE.players.get(guild_id)
            
            if player:
                # Собираем информацию о текущем треке
                current_track = None
                if hasattr(player, 'current_track') and player.current_track:
                    current_track = {
                        'title': player.current_track.get('title', 'Неизвестный трек'),
                        'artist': player.current_track.get('artist', ''),
                        'thumbnail': player.current_track.get('thumbnail', ''),
                        'source': player.current_track.get('source', ''),
                        'is_radio': player.current_track.get('source') == 'stream'
                    }
                elif hasattr(player, 'player') and player.player and hasattr(player.player, 'current'):
                    track = player.player.current
                    if track:
                        current_track = {
                            'title': track.title if hasattr(track, 'title') else 'Неизвестный трек',
                            'artist': track.author if hasattr(track, 'author') else '',
                            'thumbnail': getattr(track, 'artwork', None) or getattr(track, 'thumbnail', ''),
                            'source': 'wavelink',
                            'is_radio': getattr(track, 'is_radio', False)
                        }
                
                # Собираем информацию об очереди
                queue = []
                if hasattr(player, 'queue'):
                    queue_tracks = player.queue if isinstance(player.queue, list) else getattr(player.queue, '_queue', [])
                    
                    for i, track in enumerate(queue_tracks):
                        # Преобразуем объект трека в словарь
                        track_data = {}
                        if isinstance(track, dict):
                            track_data = {
                                'id': i + 1,
                                'title': track.get('title', 'Неизвестный трек'),
                                'artist': track.get('artist', ''),
                                'thumbnail': track.get('thumbnail', ''),
                                'source': track.get('source', '')
                            }
                        else:
                            track_data = {
                                'id': i + 1,
                                'title': track.title if hasattr(track, 'title') else 'Неизвестный трек',
                                'artist': track.author if hasattr(track, 'author') else '',
                                'thumbnail': getattr(track, 'artwork', None) or getattr(track, 'thumbnail', ''),
                                'source': 'wavelink'
                            }
                        
                        queue.append(track_data)
                
                # Сохраняем в кеш
                queue_cache[guild_id] = queue
                current_track_cache[guild_id] = current_track
        except Exception as e:
            logger.error(f"Ошибка при обновлении кеша для гильдии {guild_id}: {e}")


def get_formatted_guilds():
    """Возвращает список серверов с текущим статусом подключения

    Returns:
        list: Список серверов
    """
    if not BOT_INSTANCE:
        return []
    
    guilds = []
    for guild in BOT_INSTANCE.guilds:
        player = BOT_INSTANCE.players.get(guild.id)
        status = "Не подключен"
        channel_name = None
        
        if player and player.voice_client and player.voice_client.is_connected():
            status = "Подключен"
            channel_name = player.voice_client.channel.name
        
        guilds.append({
            "id": str(guild.id),
            "name": guild.name,
            "status": status,
            "channel": channel_name,
            "member_count": guild.member_count,
            "icon": str(guild.icon.url) if guild.icon else None
        })
    
    return guilds


def get_player_status(guild_id):
    """Получение текущего статуса плеера для сервера Discord
    
    Args:
        guild_id (int): ID сервера Discord
    
    Returns:
        dict: Словарь с информацией о статусе плеера или None в случае ошибки
    """
    try:
        # Проверяем, инициализирован ли бот и плеер
        if not BOT_INSTANCE or not hasattr(BOT_INSTANCE, 'players'):
            return {
                'status': 'not_initialized',
                'connected': False,
                'current_track': None,
                'queue': [],
                'radio_mode': False,
                'volume': 100
            }
        
        # Проверяем, существует ли плеер для данного сервера
        if guild_id not in BOT_INSTANCE.players:
            return {
                'status': 'not_found',
                'connected': False,
                'current_track': None, 
                'queue': [],
                'radio_mode': False,
                'volume': 100
            }
        
        player = BOT_INSTANCE.players[guild_id]
        
        # Проверка подключения плеера (работает как для MusicPlayer, так и для LavalinkPlayer)
        is_connected = False
        
        # Проверка для MusicPlayer
        if hasattr(player, 'voice_client'):
            is_connected = player.voice_client and player.voice_client.is_connected()
        # Проверка для LavalinkPlayer
        elif hasattr(player, 'player'):
            is_connected = player.player and player.player.is_connected()
        
        # Если не подключен, возвращаем статус disconnected
        if not is_connected:
            return {
                'status': 'disconnected',
                'connected': False,
                'current_track': None,
                'queue': [],
                'radio_mode': False,
                'volume': 100
            }
        
        # Получаем данные текущего трека
        current_track = None
        if player.current_track:
            current_track = {
                'title': player.current_track.get('title', 'Неизвестный трек'),
                'thumbnail': player.current_track.get('thumbnail', '/static/img/default-music.png'),
                'source': player.current_track.get('source', 'unknown')
            }
        
        # Проверяем статус воспроизведения
        is_playing = player.is_playing
        is_paused = player.is_paused
        
        status = 'idle'
        if is_playing:
            status = 'paused' if is_paused else 'playing'
        
        # Получаем очередь воспроизведения
        queue = []
        if hasattr(player, 'queue'):
            if isinstance(player.queue, list):
                queue = player.queue
            elif hasattr(player.queue, 'get_queue') and callable(player.queue.get_queue):
                queue = player.queue.get_queue()
        
        # Определяем, находится ли плеер в режиме радио
        radio_mode = False
        if current_track and current_track.get('source') == 'stream':
            radio_mode = True
        
        # Получаем громкость
        volume = 100
        if hasattr(player, 'volume'):
            volume = player.volume
        elif hasattr(player, 'player') and hasattr(player.player, 'volume'):
            volume = player.player.volume * 100  # Wavelink использует значения от 0 до 1
        
        return {
            'status': status,
            'connected': is_connected,
            'current_track': current_track,
            'queue': queue,
            'radio_mode': radio_mode,
            'volume': volume
        }
    except Exception as e:
        print(f"Ошибка при получении статуса плеера: {e}")
        return {
            'status': 'error',
            'connected': False,
            'current_track': None,
            'queue': [],
            'radio_mode': False,
            'volume': 100,
            'error': str(e)
        }


# Маршруты Flask
@app.route('/')
def index():
    """Главная страница с очередью заказов"""
    return render_template('index.html')


@app.route('/queue/<guild_id>')
def queue_page(guild_id):
    """Страница управления очередью для конкретного сервера (для совместимости)"""
    return redirect(url_for('index'))


@app.route('/queue')
def queue_redirect():
    """Перенаправление на страницу очереди"""
    return redirect(url_for('index'))


# API маршруты
@app.route('/api/guilds')
def get_guilds():
    """API-эндпоинт для получения списка серверов"""
    guilds = get_formatted_guilds()
    return jsonify({"guilds": guilds})


@app.route('/api/player/<guild_id>')
def get_player(guild_id):
    """API-эндпоинт для получения информации о плеере"""
    info = get_player_status(guild_id)
    return jsonify(info)


@app.route('/api/radios')
def get_radios():
    """API-эндпоинт для получения списка доступных радиостанций"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    radios = {}
    for key, radio in BOT_INSTANCE.available_radios.items():
        radios[key] = {
            "name": radio["name"],
            "url": radio["url"],
            "thumbnail": radio["thumbnail"]
        }
    
    return jsonify({"radios": radios})


@app.route('/api/orders')
def get_orders():
    """API для получения списка последних заказов для всех серверов"""
    try:
        # Создаем список заказов
        orders = []
        
        # Получаем данные обо всех серверах и их плеерах
        if BOT_INSTANCE and hasattr(BOT_INSTANCE, 'players'):
            for guild_id, player in BOT_INSTANCE.players.items():
                guild = BOT_INSTANCE.get_guild(int(guild_id))
                guild_name = guild.name if guild else "Неизвестный сервер"
                
                # Добавляем текущий трек, если он есть
                if hasattr(player, 'current_track') and player.current_track:
                    # Пропускаем радио
                    if player.current_track.get('source') == 'stream':
                        continue
                        
                    order = {
                        'title': player.current_track.get('title', 'Неизвестный трек'),
                        'customer': f"{guild_name}",
                        'thumbnail': player.current_track.get('thumbnail', '/static/img/default-music.png'),
                        'date': 'Сейчас играет'
                    }
                    orders.append(order)
                
                # Добавляем треки из очереди
                if hasattr(player, 'queue'):
                    queue_tracks = []
                    if isinstance(player.queue, list):
                        queue_tracks = player.queue
                    
                    for track in queue_tracks:
                        if isinstance(track, dict):
                            # Пропускаем радио
                            if track.get('source') == 'stream':
                                continue
                                
                            order = {
                                'title': track.get('title', 'Неизвестный трек'),
                                'customer': f"{guild_name}",
                                'thumbnail': track.get('thumbnail', '/static/img/default-music.png'),
                                'date': 'В очереди'
                            }
                            orders.append(order)
        
        # Возвращаем результат
        return jsonify({
            'success': True,
            'orders': orders
        })
    except Exception as e:
        print(f"Ошибка при получении заказов: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


# API для управления плеером
@app.route('/api/player/<guild_id>/play', methods=['POST'])
def play_track(guild_id):
    """API для добавления трека в очередь"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({"error": "Отсутствует запрос"}), 400
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player or not player.voice_client or not player.voice_client.is_connected():
        return jsonify({"error": "Плеер не подключен"}), 400
    
    # Добавление задачи в очередь запросов бота
    BOT_INSTANCE.loop.create_task(player.add_track(query))
    
    return jsonify({"success": True, "message": f"Добавление трека: {query}"}), 200


@app.route('/api/player/<guild_id>/skip', methods=['POST'])
def skip_track(guild_id):
    """API для пропуска текущего трека"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player or not player.voice_client or not player.voice_client.is_connected():
        return jsonify({"error": "Плеер не подключен"}), 400
    
    # Пропуск трека
    BOT_INSTANCE.loop.create_task(player.skip())
    
    return jsonify({"success": True, "message": "Трек пропущен"}), 200


@app.route('/api/player/<guild_id>/pause', methods=['POST'])
def pause_playback(guild_id):
    """API для приостановки воспроизведения"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player or not player.voice_client or not player.voice_client.is_connected():
        return jsonify({"error": "Плеер не подключен"}), 400
    
    # Приостановка воспроизведения
    BOT_INSTANCE.loop.create_task(player.pause())
    
    return jsonify({"success": True, "message": "Воспроизведение приостановлено"}), 200


@app.route('/api/player/<guild_id>/resume', methods=['POST'])
def resume_playback(guild_id):
    """API для возобновления воспроизведения"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player or not player.voice_client or not player.voice_client.is_connected():
        return jsonify({"error": "Плеер не подключен"}), 400
    
    # Возобновление воспроизведения
    BOT_INSTANCE.loop.create_task(player.resume())
    
    return jsonify({"success": True, "message": "Воспроизведение возобновлено"}), 200


@app.route('/api/player/<guild_id>/radio', methods=['POST'])
def switch_to_radio(guild_id):
    """API для переключения на режим радио"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player or not player.voice_client or not player.voice_client.is_connected():
        return jsonify({"error": "Плеер не подключен"}), 400
    
    # Переключение на радио
    BOT_INSTANCE.loop.create_task(player.play_radio())
    
    return jsonify({"success": True, "message": f"Переключение на радиостанцию: {BOT_INSTANCE.current_radio['name']}"}), 200


@app.route('/api/player/<guild_id>/switch_radio', methods=['POST'])
def switch_radio_station(guild_id):
    """API для переключения радиостанции"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    data = request.json
    radio_key = data.get('station')
    
    if not radio_key:
        return jsonify({"error": "Не указан ключ радиостанции"}), 400
    
    # Переключение на указанную радиостанцию
    radio_info = BOT_INSTANCE.switch_radio(radio_key)
    
    if not radio_info:
        return jsonify({"error": f"Радиостанция '{radio_key}' не найдена"}), 400
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if player and player.voice_client and player.voice_client.is_connected() and player.is_radio_mode:
        # Если плеер подключен и в режиме радио, переключаем радиостанцию
        BOT_INSTANCE.loop.create_task(player.play_radio())
    
    return jsonify({
        "success": True, 
        "message": f"Радиостанция изменена на: {radio_info['name']}",
        "radio_name": radio_info['name']
    }), 200


@app.route('/api/player/<guild_id>/volume', methods=['POST'])
def set_volume(guild_id):
    """API для изменения громкости"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    data = request.json
    volume = data.get('volume')
    
    try:
        volume = int(volume)
        if volume < 0 or volume > 100:
            return jsonify({"error": "Громкость должна быть от 0 до 100"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Некорректное значение громкости"}), 400
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player or not player.voice_client or not player.voice_client.is_connected():
        return jsonify({"error": "Плеер не подключен"}), 400
    
    # Изменение громкости
    BOT_INSTANCE.loop.create_task(player.set_volume(volume))
    
    return jsonify({"success": True, "message": f"Громкость установлена: {volume}%"}), 200


@app.route('/api/player/<guild_id>/queue/<track_index>/remove', methods=['POST'])
def remove_from_queue(guild_id, track_index):
    """API для удаления трека из очереди"""
    if not BOT_INSTANCE:
        return jsonify({"error": "Бот не инициализирован"}), 500
    
    try:
        track_index = int(track_index)
    except ValueError:
        return jsonify({"error": "Некорректный индекс трека"}), 400
    
    guild_id = int(guild_id)
    player = BOT_INSTANCE.players.get(guild_id)
    
    if not player:
        return jsonify({"error": "Плеер не найден"}), 400
    
    if track_index < 0 or track_index >= len(player.queue):
        return jsonify({"error": "Трек с указанным индексом не найден"}), 400
    
    # Удаление трека из очереди
    removed_track = player.queue.pop(track_index)
    
    # Отправка обновленного статуса через WebSocket
    socketio.emit('queue_update', {
        'guild_id': str(guild_id),
        'status': get_player_status(guild_id)
    })
    
    return jsonify({
        "success": True, 
        "message": f"Трек '{removed_track.title}' удален из очереди"
    }), 200


# SocketIO события
@socketio.on('connect')
def handle_connect():
    """Обработка подключения клиента"""
    print('Клиент подключен')


@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения клиента"""
    print('Клиент отключен')


# Функция для отправки обновления статуса плеера через WebSocket
def send_player_update(guild_id):
    """Отправляет обновление статуса плеера всем подключенным клиентам
    
    Args:
        guild_id: ID сервера Discord
    """
    if not BOT_INSTANCE:
        return
    
    guild_id = int(guild_id)
    status = get_player_status(guild_id)
    
    socketio.emit('player_update', {
        'guild_id': str(guild_id),
        'status': status
    })


# Функция для отправки обновления текущего трека через WebSocket
def send_current_track_update(guild_id):
    """Отправляет обновление текущего трека всем подключенным клиентам
    
    Args:
        guild_id: ID сервера Discord
    """
    if not BOT_INSTANCE:
        return
    
    guild_id = int(guild_id)
    status = get_player_status(guild_id)
    
    socketio.emit('current_track_update', {
        'guild_id': str(guild_id),
        'current_track': status.get('current_track'),
        'is_radio': status.get('is_radio'),
        'radio_info': status.get('radio_info')
    })


# Функция для отправки обновления очереди треков через WebSocket
def send_queue_update(guild_id):
    """Отправляет обновление очереди треков всем подключенным клиентам
    
    Args:
        guild_id: ID сервера Discord
    """
    if not BOT_INSTANCE:
        return
    
    guild_id = int(guild_id)
    status = get_player_status(guild_id)
    
    socketio.emit('queue_update', {
        'guild_id': str(guild_id),
        'queue': status.get('queue')
    })


def get_web_url():
    """Возвращает URL для доступа к веб-интерфейсу
    
    Returns:
        str: URL веб-интерфейса
    """
    host = os.getenv('WEB_HOST', 'localhost')
    port = os.getenv('FLASK_PORT', '5000')
    protocol = 'https' if os.getenv('WEB_SECURE', 'false').lower() == 'true' else 'http'
    
    return f"{protocol}://{host}:{port}"


if __name__ == '__main__':
    # Запуск для тестирования (обычно сервер запускается через initialize_web_server)
    socketio.run(app, debug=True, host='0.0.0.0', port=int(os.getenv('FLASK_PORT', 5000))) 