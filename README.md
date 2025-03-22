# Радио Вечер - Discord Бот для Киновечера

Бот для Discord, который работает как музыкальный плеер в голосовом канале. По умолчанию воспроизводит радио, но также позволяет добавлять треки из Spotify и других источников.

## Особенности

- Автоматическое воспроизведение радио в голосовом канале
- Интерактивный плеер с кнопками управления в текстовом канале
- Поддержка добавления треков из Spotify
- Автоматическое восстановление соединения при сбоях
- Простой и понятный интерфейс с использованием слэш-команд
- Гибкая система разрешений
- Настраиваемый источник радио

## Требования

- Python 3.8 или выше
- FFmpeg (установленный и доступный в PATH)
- Токен Discord бота
- Учетные данные Spotify API (опционально, для поддержки Spotify)

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/radiovecher.git
cd radiovecher
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Установите FFmpeg:
   - **Windows**: Скачайте с [официального сайта](https://ffmpeg.org/download.html) и добавьте в PATH
   - **Linux**: `sudo apt-get install ffmpeg`
   - **macOS**: `brew install ffmpeg`

4. Настройте файл `.env`:
```
# Discord Bot Token
DISCORD_TOKEN=ваш_токен_бота_здесь

# Spotify API Credentials
SPOTIFY_CLIENT_ID=ваш_spotify_client_id_здесь
SPOTIFY_CLIENT_SECRET=ваш_spotify_client_secret_здесь
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# Настройки радио
RADIO_STREAM_URL=https://rusradio.hostingradio.ru/rusradio96.aacp
RADIO_NAME=Русское Радио
RADIO_THUMBNAIL=https://rusradio.ru/design/images/share.jpg

# Настройки Lavalink сервера
LAVALINK_HOST=localhost
LAVALINK_PORT=2333
LAVALINK_PASSWORD=youshallnotpass
LAVALINK_SECURE=false
```

5. Настройте ID каналов:
   Откройте файл `cogs/music_commands.py` и измените следующие константы:
   ```python
   # ID голосового канала для киновечера
   VOICE_CHANNEL_ID = 1329935439628341289
   # ID текстового канала для плеера
   TEXT_CHANNEL_ID = 123456789
   ```

## Настройка радио

Вы можете настроить любой радиопоток, изменив следующие параметры в файле `.env`:

- `RADIO_STREAM_URL` - URL прямого потока радио (например, `https://rusradio.hostingradio.ru/rusradio96.aacp`)
- `RADIO_NAME` - Название радио, которое будет отображаться в плеере (например, `Русское Радио`)
- `RADIO_THUMBNAIL` - URL изображения для радио (например, `https://rusradio.ru/design/images/share.jpg`)

Примеры популярных радиостанций:
```
# Русское Радио
RADIO_STREAM_URL=https://rusradio.hostingradio.ru/rusradio96.aacp
RADIO_NAME=Русское Радио
RADIO_THUMBNAIL=https://rusradio.ru/design/images/share.jpg

# Европа Плюс
RADIO_STREAM_URL=https://ep128.hostingradio.ru:8030/ep128
RADIO_NAME=Европа Плюс
RADIO_THUMBNAIL=https://europaplus.ru/media/mtime_image/2019/10/24/5a7d4a5c-f5f0-11e9-a84f-005056a23d3a.jpg

# Радио Рекорд
RADIO_STREAM_URL=https://radiorecord.hostingradio.ru/rr_main96.aacp
RADIO_NAME=Радио Рекорд
RADIO_THUMBNAIL=https://radiorecord.ru/upload/stations_images/record_image600_white_fill.png
```

## Настройка Lavalink

Бот поддерживает воспроизведение музыки через Lavalink - мощный сервер для обработки аудио, который обеспечивает высокое качество и поддержку большого количества сервисов.

### Настройка Lavalink сервера

1. Загрузите последнюю версию Lavalink с [официального репозитория](https://github.com/lavalink-devs/Lavalink/releases)

2. Создайте файл `application.yml` рядом с jar-файлом со следующим содержимым:
```yaml
server:
  port: 2333
  address: 0.0.0.0
lavalink:
  server:
    password: "youshallnotpass"
    sources:
      youtube: true
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      http: true
      local: false
    bufferDurationMs: 400
    youtubePlaylistLoadLimit: 6
    playerUpdateInterval: 5
    youtubeSearchEnabled: true
    soundcloudSearchEnabled: true
    gc-warnings: true

metrics:
  prometheus:
    enabled: false
    endpoint: /metrics

sentry:
  dsn: ""
  environment: ""

logging:
  file:
    max-history: 30
    max-size: 1GB
  path: ./logs/

  level:
    root: INFO
    lavalink: INFO
```

3. Запустите Lavalink сервер:
```bash
java -jar Lavalink.jar
```

> ⚠️ **Примечание**: Для работы Lavalink требуется Java 11 или выше.

### Настройка бота для работы с Lavalink

1. Убедитесь, что в файле `.env` указаны правильные настройки Lavalink:
```
LAVALINK_HOST=localhost  # Хост сервера Lavalink
LAVALINK_PORT=2333       # Порт сервера Lavalink
LAVALINK_PASSWORD=youshallnotpass  # Пароль, указанный в application.yml
LAVALINK_SECURE=false    # Использовать ли SSL (wss) вместо ws
```

2. В файле `cogs/music_commands.py` убедитесь, что опция `USE_LAVALINK` включена:
```python
# Настройка использования Lavalink
USE_LAVALINK = True  # Установите True для использования Lavalink
```

### Преимущества Lavalink

- Поддержка большего количества источников аудио (YouTube, SoundCloud, Bandcamp, Twitch и др.)
- Лучшее качество звука и стабильность воспроизведения
- Более быстрая буферизация и меньшая задержка при воспроизведении
- Возможность загружать целые плейлисты
- Поддержка прямых эфиров и стримов
- Меньшая нагрузка на бота и Discord API

## Запуск

```bash
python bot.py
```

## Команды

Бот использует слэш-команды Discord для удобства использования:

- `/start` - Запуск музыкального плеера (требуется право "Управление сервером")
- `/stop` - Остановка музыкального плеера (требуется право "Управление сервером")
- `/skip` - Пропуск текущего трека
- `/radio` - Возврат к воспроизведению радио
- `/play <запрос>` - Добавление трека в очередь воспроизведения
- `/invite` - Получить ссылку для приглашения бота на сервер

## Необходимые разрешения для бота

При добавлении бота на сервер, ему необходимы следующие разрешения:

- **Основные разрешения**:
  - Просмотр каналов
  - Отправка сообщений
  - Встраивание ссылок
  - Прикрепление файлов
  - Чтение истории сообщений
  - Добавление реакций
  - Управление сообщениями (для закрепления)
  - Использование внешних эмодзи
  - Использование внешних стикеров
  - Использование слэш-команд

- **Разрешения для голосовых каналов**:
  - Подключение
  - Говорить
  - Использовать голосовую активацию

Бот автоматически создает ссылку для приглашения с нужными разрешениями, которую можно получить с помощью команды `/invite`.

## Интерактивный плеер

Бот создает интерактивный плеер в указанном текстовом канале с кнопками:
- ⏭️ Пропустить - пропуск текущего трека
- ⏹️ Стоп - остановка воспроизведения и возврат к радио
- 🎵 Добавить трек - открытие модального окна для добавления трека

## Устранение неполадок

### Проблемы с FFmpeg

Если возникают проблемы с воспроизведением аудио:
1. Убедитесь, что FFmpeg правильно установлен и доступен в PATH
2. Проверьте, что у бота есть права на подключение к голосовому каналу
3. Бот автоматически пытается переподключиться при сбоях FFmpeg

### Проблемы с Spotify

Если не работает добавление треков из Spotify:
1. Проверьте правильность учетных данных Spotify API в файле `.env`
2. Убедитесь, что ваше приложение Spotify имеет правильные разрешения

### Проблемы с разрешениями

Если у пользователей возникают проблемы с использованием команд:
1. Убедитесь, что у бота есть все необходимые разрешения на сервере
2. Для команд `/start` и `/stop` пользователям требуется право "Управление сервером" или "Администратор"
3. Проверьте настройки интеграций на сервере, чтобы убедиться, что слэш-команды бота разрешены