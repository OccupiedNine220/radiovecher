import os
import json
import time
import threading
import secrets
import requests
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
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

# Настройки Discord OAuth2
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '123456789012345678')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', 'your-client-secret')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
DISCORD_API_ENDPOINT = 'https://discord.com/api/v10'

# ID сервера и роли для проверки
REQUIRED_GUILD_ID = '1129361333129838603'
REQUIRED_ROLE_ID = '1280772929822658600'

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
    """Поток для периодического обновления кеша состояния плееров"""
    global current_guild_players, queue_cache, current_track_cache
    
    while True:
        try:
            if BOT_INSTANCE:
                for guild_id, player in BOT_INSTANCE.players.items():
                    # Обновление статуса плеера
                    current_guild_players[guild_id] = {
                        "is_playing": player.is_playing,
                        "is_paused": player.is_paused,
                        "connected": player.voice_client is not None if hasattr(player, 'voice_client') else player.player is not None,
                        "current_radio": BOT_INSTANCE.current_radio
                    }
                    
                    # Обновление текущего трека
                    if player.current_track:
                        current_track_cache[guild_id] = player.current_track
                    
                    # Обновление очереди
                    queue_cache[guild_id] = player.queue
        except Exception as e:
            logger.error(f"Ошибка при обновлении кеша: {e}")
        
        time.sleep(CACHE_UPDATE_INTERVAL)


def get_oauth_url():
    """Генерирует URL для OAuth2 авторизации через Discord
    
    Returns:
        str: URL для авторизации
    """
    scope = "identify guilds"
    state = secrets.token_urlsafe(16)
    session['oauth2_state'] = state
    
    return f"{DISCORD_API_ENDPOINT}/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope={scope}&state={state}"


def exchange_code(code):
    """Обменивает код авторизации на токен доступа
    
    Args:
        code (str): Код авторизации от Discord
        
    Returns:
        dict: Данные токена или None при ошибке
    """
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    response = requests.post(f'{DISCORD_API_ENDPOINT}/oauth2/token', data=data, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Ошибка при обмене кода на токен: {response.text}")
        return None


def get_user_info(access_token):
    """Получает информацию о пользователе Discord
    
    Args:
        access_token (str): Токен доступа
        
    Returns:
        dict: Информация о пользователе или None при ошибке
    """
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    response = requests.get(f'{DISCORD_API_ENDPOINT}/users/@me', headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Ошибка при получении информации о пользователе: {response.text}")
        return None


def get_user_guilds(access_token):
    """Получает список серверов пользователя Discord
    
    Args:
        access_token (str): Токен доступа
        
    Returns:
        list: Список серверов или пустой список при ошибке
    """
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    response = requests.get(f'{DISCORD_API_ENDPOINT}/users/@me/guilds', headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Ошибка при получении списка серверов пользователя: {response.text}")
        return []


def get_guild_member(guild_id, user_id, access_token):
    """Получает информацию о пользователе на конкретном сервере
    
    Args:
        guild_id (str): ID сервера
        user_id (str): ID пользователя
        access_token (str): Токен доступа
        
    Returns:
        dict: Информация о пользователе на сервере или None при ошибке
    """
    # Для этого нужен бот-токен, поэтому используем BOT_INSTANCE
    if not BOT_INSTANCE:
        return None
    
    guild = BOT_INSTANCE.get_guild(int(guild_id))
    if not guild:
        return None
    
    member = guild.get_member(int(user_id))
    if not member:
        return None
    
    return {
        'id': str(member.id),
        'roles': [str(role.id) for role in member.roles]
    }


def has_required_role(user_id, access_token):
    """Проверяет, имеет ли пользователь требуемую роль на требуемом сервере
    
    Args:
        user_id (str): ID пользователя
        access_token (str): Токен доступа
        
    Returns:
        bool: True если пользователь имеет требуемую роль, иначе False
    """
    member_info = get_guild_member(REQUIRED_GUILD_ID, user_id, access_token)
    
    if not member_info:
        return False
    
    return REQUIRED_ROLE_ID in member_info['roles']


def login_required(f):
    """Декоратор для проверки авторизации пользователя
    
    Args:
        f (function): Функция-представление
        
    Returns:
        function: Обернутая функция
    """
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    
    # Сохраняем имя функции и другие атрибуты
    decorated_function.__name__ = f.__name__
    return decorated_function


# Маршруты Flask
@app.route('/')
def index():
    """Главная страница"""
    if 'user' in session:
        return render_template('new_index.html', user=session['user'], guilds=get_formatted_guilds())
    else:
        return render_template('new_index.html', guilds=None)


@app.route('/login')
def login():
    """Страница авторизации через Discord"""
    next_url = request.args.get('next', url_for('index'))
    session['next_url'] = next_url
    
    oauth_url = get_oauth_url()
    return render_template('login.html', oauth_url=oauth_url)


@app.route('/callback')
def callback():
    """Обработчик ответа от Discord OAuth2"""
    error = request.args.get('error')
    if error:
        return render_template('login.html', error=f"Ошибка авторизации: {error}", oauth_url=get_oauth_url())
    
    code = request.args.get('code')
    state = request.args.get('state')
    stored_state = session.pop('oauth2_state', None)
    
    if not code:
        return render_template('login.html', error="Не получен код авторизации", oauth_url=get_oauth_url())
    
    if state != stored_state:
        return render_template('login.html', error="Недействительное состояние OAuth", oauth_url=get_oauth_url())
    
    token_data = exchange_code(code)
    if not token_data:
        return render_template('login.html', error="Не удалось получить токен доступа", oauth_url=get_oauth_url())
    
    access_token = token_data['access_token']
    
    user_info = get_user_info(access_token)
    if not user_info:
        return render_template('login.html', error="Не удалось получить информацию о пользователе", oauth_url=get_oauth_url())
    
    # Проверка наличия требуемой роли
    if not has_required_role(user_info['id'], access_token):
        return render_template('login.html', error="У вас нет необходимых прав для доступа к панели управления", oauth_url=get_oauth_url())
    
    # Сохранение информации о пользователе в сессии
    session['user'] = {
        'id': user_info['id'],
        'username': user_info['username'],
        'discriminator': user_info.get('discriminator', '0000'),
        'avatar_url': f"https://cdn.discordapp.com/avatars/{user_info['id']}/{user_info['avatar']}.png" if user_info.get('avatar') else f"https://cdn.discordapp.com/embed/avatars/{int(user_info.get('discriminator', '0000')) % 5}.png",
        'access_token': access_token
    }
    
    next_url = session.pop('next_url', url_for('index'))
    return redirect(next_url)


@app.route('/logout')
def logout():
    """Выход из системы"""
    session.pop('user', None)
    return redirect(url_for('index'))


@app.route('/queue/<guild_id>')
@login_required
def queue_page(guild_id):
    """Страница управления очередью для конкретного сервера"""
    guild = None
    
    if BOT_INSTANCE:
        guild = BOT_INSTANCE.get_guild(int(guild_id))
    
    if not guild:
        return redirect(url_for('index'))
    
    return render_template('queue_new.html', guild_id=guild_id, guild_name=guild.name, user=session.get('user'))


@app.route('/queue')
def queue_redirect():
    """Перенаправление на страницу очереди"""
    return redirect(url_for('index'))


# API маршруты
@app.route('/api/guilds')
@login_required
def get_guilds():
    """API-эндпоинт для получения списка серверов"""
    guilds = get_formatted_guilds()
    return jsonify({"guilds": guilds})


@app.route('/api/player/<guild_id>')
@login_required
def get_player(guild_id):
    """API-эндпоинт для получения информации о плеере"""
    info = get_player_status(guild_id)
    return jsonify(info)


@app.route('/api/queue/<guild_id>')
@login_required
def get_queue(guild_id):
    """API-эндпоинт для получения очереди треков"""
    guild_id = str(guild_id)
    
    if guild_id in queue_cache:
        return jsonify({"queue": queue_cache[guild_id]})
    else:
        return jsonify({"queue": []})


@app.route('/api/add_track/<guild_id>', methods=['POST'])
@login_required
def add_track(guild_id):
    """API-эндпоинт для добавления трека в очередь"""
    if not BOT_INSTANCE:
        return jsonify({"success": False, "error": "Бот не инициализирован"}), 500
    
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"success": False, "error": "URL не указан"}), 400
    
    try:
        guild_id = int(guild_id)
        guild = BOT_INSTANCE.get_guild(guild_id)
        
        if not guild:
            return jsonify({"success": False, "error": "Сервер не найден"}), 404
        
        player = BOT_INSTANCE.players.get(guild_id)
        
        if not player:
            return jsonify({"success": False, "error": "Плеер не найден"}), 404
        
        # Добавление трека через корутину
        # Эта часть сложна для работы через API, так как Flask не асинхронный
        # Используем асинхронную очередь или другой механизм
        track_info = {
            "title": "Добавление трека...",
            "url": url,
            "thumbnail": "",
            "source": "queue"
        }
        
        # Временно добавляем в кеш очереди
        if str(guild_id) not in queue_cache:
            queue_cache[str(guild_id)] = []
        
        queue_cache[str(guild_id)].append(track_info)
        
        # Trigger player to add track (выполнение асинхронно)
        BOT_INSTANCE.loop.create_task(player.add_track(url, from_web=True))
        
        return jsonify({
            "success": True, 
            "track_title": "Трек добавлен в очередь"
        })
    except Exception as e:
        logger.error(f"Ошибка при добавлении трека: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/remove_track/<guild_id>/<int:index>', methods=['POST'])
@login_required
def remove_track(guild_id, index):
    """API-эндпоинт для удаления трека из очереди"""
    if not BOT_INSTANCE:
        return jsonify({"success": False, "error": "Бот не инициализирован"}), 500
    
    try:
        guild_id = int(guild_id)
        guild = BOT_INSTANCE.get_guild(guild_id)
        
        if not guild:
            return jsonify({"success": False, "error": "Сервер не найден"}), 404
        
        player = BOT_INSTANCE.players.get(guild_id)
        
        if not player:
            return jsonify({"success": False, "error": "Плеер не найден"}), 404
        
        if index < 0 or index >= len(player.queue):
            return jsonify({"success": False, "error": "Недопустимый индекс трека"}), 400
        
        # Trigger player to remove track (выполнение асинхронно)
        BOT_INSTANCE.loop.create_task(player.remove_track(index, from_web=True))
        
        # Обновляем кеш (временное решение)
        if str(guild_id) in queue_cache and index < len(queue_cache[str(guild_id)]):
            queue_cache[str(guild_id)].pop(index)
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Ошибка при удалении трека: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/switch_radio/<guild_id>', methods=['POST'])
@login_required
def switch_radio(guild_id):
    """API-эндпоинт для переключения радиостанции"""
    if not BOT_INSTANCE:
        return jsonify({"success": False, "error": "Бот не инициализирован"}), 500
    
    data = request.json
    radio_key = data.get('radio_key')
    
    if not radio_key:
        return jsonify({"success": False, "error": "Ключ радиостанции не указан"}), 400
    
    try:
        guild_id = int(guild_id)
        guild = BOT_INSTANCE.get_guild(guild_id)
        
        if not guild:
            return jsonify({"success": False, "error": "Сервер не найден"}), 404
        
        player = BOT_INSTANCE.players.get(guild_id)
        
        if not player:
            return jsonify({"success": False, "error": "Плеер не найден"}), 404
        
        # Переключение радиостанции
        new_radio = BOT_INSTANCE.switch_radio(radio_key)
        
        if not new_radio:
            return jsonify({"success": False, "error": "Радиостанция не найдена"}), 404
        
        # Trigger player to play radio (выполнение асинхронно)
        BOT_INSTANCE.loop.create_task(player.play_radio())
        
        return jsonify({"success": True, "radio": new_radio})
    except Exception as e:
        logger.error(f"Ошибка при переключении радиостанции: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/control/<guild_id>/<action>', methods=['POST'])
@login_required
def control_player(guild_id, action):
    """API-эндпоинт для управления плеером"""
    if not BOT_INSTANCE:
        return jsonify({"success": False, "error": "Бот не инициализирован"}), 500
    
    try:
        guild_id = int(guild_id)
        guild = BOT_INSTANCE.get_guild(guild_id)
        
        if not guild:
            return jsonify({"success": False, "error": "Сервер не найден"}), 404
        
        player = BOT_INSTANCE.players.get(guild_id)
        
        if not player:
            return jsonify({"success": False, "error": "Плеер не найден"}), 404
        
        # Выполнение действия
        if action == 'pause':
            BOT_INSTANCE.loop.create_task(player.pause())
        elif action == 'resume':
            BOT_INSTANCE.loop.create_task(player.resume())
        elif action == 'skip':
            BOT_INSTANCE.loop.create_task(player.skip())
        elif action == 'stop':
            BOT_INSTANCE.loop.create_task(player.stop())
        elif action == 'radio':
            BOT_INSTANCE.loop.create_task(player.play_radio())
        else:
            return jsonify({"success": False, "error": "Неизвестное действие"}), 400
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Ошибка при управлении плеером: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Вспомогательные функции
def get_formatted_guilds():
    """Получает форматированный список серверов, на которых есть бот
    
    Returns:
        list: Список словарей с информацией о серверах
    """
    if not BOT_INSTANCE:
        return []
    
    guilds = []
    
    for guild in BOT_INSTANCE.guilds:
        guild_id = guild.id
        
        # Проверка подключения к голосовому каналу
        connected = False
        if guild_id in current_guild_players:
            connected = current_guild_players[guild_id]["connected"]
        
        guilds.append({
            "id": str(guild_id),
            "name": guild.name,
            "icon_url": guild.icon.url if guild.icon else None,
            "connected": connected
        })
    
    return guilds


def get_player_status(guild_id):
    """Получает статус плеера для указанного сервера
    
    Args:
        guild_id (str): ID сервера
    
    Returns:
        dict: Информация о состоянии плеера
    """
    guild_id = str(guild_id)
    
    # Значения по умолчанию
    status = {
        "connected": False,
        "is_playing": False,
        "is_paused": False,
        "current_track": None,
        "current_radio": None
    }
    
    # Обновление из кеша
    if guild_id in current_guild_players:
        status.update(current_guild_players[guild_id])
    
    # Добавление информации о текущем треке
    if guild_id in current_track_cache:
        status["current_track"] = current_track_cache[guild_id]
    
    return status


# SocketIO события
@socketio.on('connect')
def handle_connect():
    """Обработка подключения клиента"""
    print('Клиент подключен')


@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения клиента"""
    print('Клиент отключен')


@socketio.on('join_guild')
def handle_join_guild(data):
    """Обработка подключения клиента к комнате сервера"""
    guild_id = data.get('guild_id')
    if guild_id:
        print(f'Клиент присоединился к комнате сервера {guild_id}')


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