/**
 * Радио Вечер - Основной JavaScript файл
 * Содержит общие функции для веб-интерфейса
 */

// Состояние приложения
const appState = {
    socket: null,
    currentGuildId: null,
    isPlaying: true
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация Socket.IO
    initializeSocketIO();
    
    // Получение ID текущей гильдии из URL, если на странице очереди
    const queueMatch = window.location.pathname.match(/\/queue\/(\d+)/);
    if (queueMatch && queueMatch[1]) {
        appState.currentGuildId = queueMatch[1];
        
        // Загрузить данные для этого сервера
        loadGuildData(appState.currentGuildId);
    } else {
        // На главной странице загружаем список серверов
        loadServerList();
        
        // Загружаем последние заказы
        loadRecentOrders();
    }
    
    // Обработчик отправки формы добавления трека
    const addTrackForm = document.getElementById('addTrackForm');
    const submitTrackButton = document.getElementById('submitTrack');
    
    if (addTrackForm && submitTrackButton) {
        submitTrackButton.addEventListener('click', function() {
            const trackQuery = document.getElementById('trackQuery');
            if (trackQuery && trackQuery.value.trim() !== '' && appState.currentGuildId) {
                addTrackToQueue(appState.currentGuildId, trackQuery.value.trim());
                trackQuery.value = '';
                
                // Закрыть модальное окно
                const modal = bootstrap.Modal.getInstance(document.getElementById('addTrackModal'));
                if (modal) {
                    modal.hide();
                }
            }
        });
        
        // Добавление обработчика клавиши Enter для формы
        addTrackForm.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitTrackButton.click();
            }
        });
    }
    
    // Загрузка радиостанций
    loadRadioStations();
});

/**
 * Инициализация Socket.IO для обновления в реальном времени
 */
function initializeSocketIO() {
    // Получаем хост из текущего URL
    const host = window.location.hostname;
    const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // Создаем URL для подключения к Socket.IO
    const socketURL = `${protocol}//${host}:${port}`;
    
    appState.socket = io(socketURL);
    
    appState.socket.on('connect', function() {
        console.log('Соединение с сервером установлено');
    });
    
    appState.socket.on('disconnect', function() {
        console.log('Соединение с сервером разорвано');
    });
    
    // Настройка обработчиков для разных типов событий
    setupQueueUpdates();
    setupCurrentTrackUpdates();
}

/**
 * Настройка обновлений очереди треков
 */
function setupQueueUpdates() {
    if (!appState.socket) return;
    
    appState.socket.on('queue_update', function(data) {
        if (appState.currentGuildId && data && data[appState.currentGuildId]) {
            updateQueue(data[appState.currentGuildId]);
        }
    });
}

/**
 * Настройка обновлений текущего трека
 */
function setupCurrentTrackUpdates() {
    if (!appState.socket) return;
    
    appState.socket.on('current_track_update', function(data) {
        if (appState.currentGuildId && data && data[appState.currentGuildId]) {
            updateCurrentTrack(data[appState.currentGuildId]);
        }
    });
}

/**
 * Обновление списка серверов на главной странице
 */
function updateServerList(servers) {
    const serverListContainer = document.getElementById('serverList');
    if (!serverListContainer) return;
    
    if (!servers || Object.keys(servers).length === 0) {
        serverListContainer.innerHTML = `
            <div class="text-center py-4">
                <i class="bi bi-exclamation-circle display-4 text-muted"></i>
                <h3 class="h5 mt-3">Нет активных серверов</h3>
                <p class="mb-0 text-light-emphasis">Бот не подключен ни к одному серверу Discord.</p>
            </div>
        `;
        return;
    }
    
    let serverListHTML = '';
    
    for (const [guildId, guild] of Object.entries(servers)) {
        serverListHTML += `
            <a href="/queue/${guildId}" class="card bg-dark-subtle text-light border-0 shadow-sm mb-3 server-card">
                <div class="card-body p-3">
                    <div class="d-flex align-items-center">
                        <div class="server-icon me-3">
                            ${guild.icon ? 
                                `<img src="${guild.icon}" alt="${guild.name}" class="rounded-circle shadow-sm">` : 
                                `<div class="d-flex align-items-center justify-content-center bg-primary rounded-circle" style="width: 50px; height: 50px;">
                                    <i class="bi bi-discord fs-4"></i>
                                </div>`
                            }
                        </div>
                        <div class="flex-grow-1">
                            <h5 class="mb-1">${guild.name}</h5>
                            <p class="mb-0 text-light-emphasis">
                                <span class="server-status ${guild.status === 'Подключен' ? 'status-connected' : 'status-disconnected'}"></span>
                                ${guild.status}
                                ${guild.channel ? ` • ${guild.channel}` : ''}
                            </p>
                        </div>
                        <div class="ms-auto">
                            <i class="bi bi-chevron-right"></i>
                        </div>
                    </div>
                </div>
            </a>
        `;
    }
    
    serverListContainer.innerHTML = serverListHTML;
}

/**
 * Обновление очереди треков на странице очереди
 */
function updateQueue(queueData) {
    const queueList = document.getElementById('queueList');
    const emptyQueue = document.getElementById('emptyQueue');
    const queueCount = document.getElementById('queueCount');
    
    if (!queueList || !emptyQueue || !queueCount) return;
    
    // Обновляем счетчик треков
    queueCount.textContent = queueData ? queueData.length : '0';
    
    if (!queueData || queueData.length === 0) {
        queueList.classList.add('d-none');
        emptyQueue.classList.remove('d-none');
        return;
    }
    
    queueList.classList.remove('d-none');
    emptyQueue.classList.add('d-none');
    
    // Создаем список треков в очереди
    let queueItemsHTML = '<div class="list-group list-group-flush">';
    
    queueData.forEach((track, index) => {
        // Формируем HTML для элемента очереди
        let itemHTML = `
            <div class="list-group-item bg-dark-subtle text-light border-0 border-bottom border-secondary d-flex align-items-center queue-item" data-index="${index}">
                <div class="me-3 track-number">${index + 1}</div>
                <div class="me-3">
                    <img src="${track.thumbnail || '/static/img/default-music.png'}" alt="${escapeHTML(track.title || 'Неизвестный трек')}" class="rounded" width="50" height="50">
                </div>
                <div class="flex-fill">
                    <h6 class="mb-0">${escapeHTML(track.title || 'Неизвестный трек')}</h6>
                    <small class="text-light-emphasis">${escapeHTML(track.author || track.artist || 'Неизвестный исполнитель')}</small>
                </div>
                <div class="text-end">
                    <small class="text-light-emphasis me-3">${formatDuration(track.length || 0)}</small>
                    <button class="btn btn-sm btn-outline-danger remove-track" data-index="${index}">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        `;
        
        queueItemsHTML += itemHTML;
    });
    
    queueItemsHTML += '</div>';
    queueList.innerHTML = queueItemsHTML;
    
    // Добавляем обработчики событий для кнопок удаления
    const removeButtons = queueList.querySelectorAll('.remove-track');
    removeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const index = this.getAttribute('data-index');
            if (appState.currentGuildId && index !== null) {
                removeTrackFromQueue(appState.currentGuildId, index);
            }
        });
    });
}

/**
 * Обновление информации о текущем треке
 */
function updateCurrentTrack(trackData) {
    const playerArea = document.getElementById('playerArea');
    if (!playerArea) return;
    
    if (!trackData) {
        // Показываем шаблон отключенного плеера
        playerArea.innerHTML = `
            <div class="col-12 text-center py-4">
                <i class="bi bi-plug display-1 text-danger"></i>
                <h5 class="mt-3">Бот не подключен к голосовому каналу</h5>
                <p class="text-light-emphasis">Используйте команду <code>/start</code> на сервере Discord для подключения бота.</p>
            </div>
        `;
        return;
    }
    
    // Определяем, это радио или обычный трек
    if (trackData.is_radio) {
        // Шаблон для радио
        playerArea.innerHTML = `
            <div class="col-md-3 text-center">
                <img src="${trackData.thumbnail || '/static/img/default-radio.png'}" alt="${escapeHTML(trackData.title)}" class="img-fluid rounded shadow track-thumbnail" style="max-height: 150px;">
                <div class="mt-2">
                    <span class="badge bg-danger">LIVE</span>
                </div>
            </div>
            <div class="col-md-6">
                <h5 class="track-title">${escapeHTML(trackData.title)}</h5>
                <p class="track-author text-light-emphasis">Прямой эфир</p>
                <div class="d-flex align-items-center mt-4">
                    <div class="me-2">
                        <div class="radio-wave">
                            <span></span><span></span><span></span><span></span><span></span>
                        </div>
                    </div>
                    <div class="text-light-emphasis">Вещание в прямом эфире</div>
                </div>
            </div>
            <div class="col-md-3 text-center">
                <div class="btn-group mb-3">
                    <button class="btn btn-primary" id="playPauseButton">
                        <i class="bi ${appState.isPlaying ? 'bi-pause-fill' : 'bi-play-fill'}"></i>
                    </button>
                    <button class="btn btn-primary" id="trackModeButton">
                        <i class="bi bi-music-note"></i>
                    </button>
                </div>
                <div class="volume-control">
                    <label for="volumeRange" class="form-label d-flex justify-content-between">
                        <span><i class="bi bi-volume-down"></i></span>
                        <span id="volumeValue">80%</span>
                    </label>
                    <input type="range" class="form-range" id="volumeRange" min="0" max="100" value="80">
                </div>
            </div>
        `;
    } else {
        // Шаблон для обычного трека
        playerArea.innerHTML = `
            <div class="col-md-3 text-center">
                <img src="${trackData.thumbnail || '/static/img/default-music.png'}" alt="${escapeHTML(trackData.title)}" class="img-fluid rounded shadow track-thumbnail" style="max-height: 150px;">
            </div>
            <div class="col-md-6">
                <h5 class="track-title">${escapeHTML(trackData.title)}</h5>
                <p class="track-author text-light-emphasis mb-2">${escapeHTML(trackData.artist || 'Неизвестный исполнитель')}</p>
                <div class="progress mb-2" style="height: 6px;">
                    <div class="progress-bar bg-primary" role="progressbar" style="width: 50%"></div>
                </div>
                <div class="d-flex justify-content-between">
                    <small class="text-light-emphasis" id="currentTime">0:00</small>
                    <small class="text-light-emphasis" id="totalTime">${formatDuration(trackData.length || 0)}</small>
                </div>
            </div>
            <div class="col-md-3 text-center">
                <div class="btn-group mb-3">
                    <button class="btn btn-primary" id="playPauseButton">
                        <i class="bi ${appState.isPlaying ? 'bi-pause-fill' : 'bi-play-fill'}"></i>
                    </button>
                    <button class="btn btn-primary" id="skipButton">
                        <i class="bi bi-skip-forward"></i>
                    </button>
                    <button class="btn btn-primary" id="radioToggleButton">
                        <i class="bi bi-broadcast"></i>
                    </button>
                </div>
                <div class="volume-control">
                    <label for="volumeRange" class="form-label d-flex justify-content-between">
                        <span><i class="bi bi-volume-down"></i></span>
                        <span id="volumeValue">80%</span>
                    </label>
                    <input type="range" class="form-range" id="volumeRange" min="0" max="100" value="80">
                </div>
            </div>
        `;
    }
    
    // Добавляем обработчики событий
    setupPlayerControls();
}

/**
 * Настройка элементов управления плеером
 */
function setupPlayerControls() {
    // Кнопка Play/Pause
    const playPauseButton = document.getElementById('playPauseButton');
    if (playPauseButton) {
        playPauseButton.addEventListener('click', function() {
            if (appState.isPlaying) {
                pausePlayback();
            } else {
                resumePlayback();
            }
        });
    }
    
    // Кнопка Skip
    const skipButton = document.getElementById('skipButton');
    if (skipButton) {
        skipButton.addEventListener('click', function() {
            skipTrack();
        });
    }
    
    // Кнопка переключения на радио
    const radioToggleButton = document.getElementById('radioToggleButton');
    if (radioToggleButton) {
        radioToggleButton.addEventListener('click', function() {
            switchToRadio();
        });
    }
    
    // Кнопка переключения на трек-режим
    const trackModeButton = document.getElementById('trackModeButton');
    if (trackModeButton) {
        trackModeButton.addEventListener('click', function() {
            // Открывает модальное окно добавления трека
            const modal = new bootstrap.Modal(document.getElementById('addTrackModal'));
            if (modal) {
                modal.show();
            }
        });
    }
    
    // Регулятор громкости
    const volumeRange = document.getElementById('volumeRange');
    const volumeValue = document.getElementById('volumeValue');
    if (volumeRange && volumeValue) {
        volumeRange.addEventListener('input', function() {
            volumeValue.textContent = this.value + '%';
        });
        
        volumeRange.addEventListener('change', function() {
            setVolume(appState.currentGuildId, this.value);
        });
    }
}

/**
 * Форматирование длительности трека
 */
function formatDuration(ms) {
    if (!ms) return '--:--';
    
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

/**
 * Экранирование HTML
 */
function escapeHTML(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Запрос на паузу воспроизведения
 */
function pausePlayback() {
    if (!appState.currentGuildId) return;
    
    fetch(`/api/player/${appState.currentGuildId}/pause`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            appState.isPlaying = false;
            updatePlayPauseButton();
            showToast('Воспроизведение приостановлено', 'info');
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось приостановить воспроизведение'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при запросе паузы:', error);
        showToast('Ошибка сети при запросе паузы', 'danger');
    });
}

/**
 * Запрос на продолжение воспроизведения
 */
function resumePlayback() {
    if (!appState.currentGuildId) return;
    
    fetch(`/api/player/${appState.currentGuildId}/resume`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            appState.isPlaying = true;
            updatePlayPauseButton();
            showToast('Воспроизведение продолжено', 'info');
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось продолжить воспроизведение'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при запросе продолжения:', error);
        showToast('Ошибка сети при запросе продолжения', 'danger');
    });
}

/**
 * Обновление иконки кнопки Play/Pause
 */
function updatePlayPauseButton() {
    const playPauseButton = document.getElementById('playPauseButton');
    if (!playPauseButton) return;
    
    const icon = playPauseButton.querySelector('i');
    if (icon) {
        icon.className = appState.isPlaying ? 'bi bi-pause-fill' : 'bi bi-play-fill';
    }
}

/**
 * Запрос на пропуск трека
 */
function skipTrack() {
    if (!appState.currentGuildId) return;
    
    fetch(`/api/player/${appState.currentGuildId}/skip`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Трек пропущен', 'info');
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось пропустить трек'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при запросе пропуска трека:', error);
        showToast('Ошибка сети при запросе пропуска трека', 'danger');
    });
}

/**
 * Запрос на переключение на радио
 */
function switchToRadio() {
    if (!appState.currentGuildId) return;
    
    fetch(`/api/player/${appState.currentGuildId}/radio`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Переключено на радио', 'info');
            // Перезагружаем данные плеера
            setTimeout(() => loadGuildData(appState.currentGuildId), 1000);
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось переключиться на радио'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при запросе на переключение на радио:', error);
        showToast('Ошибка сети при запросе переключения на радио', 'danger');
    });
}

/**
 * Запрос на удаление трека из очереди
 */
function removeTrackFromQueue(guildId, index) {
    if (!guildId) return;
    
    fetch(`/api/player/${guildId}/queue/${index}/remove`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Трек удален из очереди', 'info');
            // Перезагружаем данные плеера
            setTimeout(() => loadGuildData(guildId), 500);
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось удалить трек из очереди'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при запросе удаления трека:', error);
        showToast('Ошибка сети при запросе удаления трека', 'danger');
    });
}

/**
 * Запрос на установку громкости
 */
function setVolume(guildId, volume) {
    if (!guildId) return;
    
    fetch(`/api/player/${guildId}/volume`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ volume: parseInt(volume) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Громкость установлена: ${volume}%`, 'info');
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось установить громкость'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при запросе установки громкости:', error);
        showToast('Ошибка сети при запросе установки громкости', 'danger');
    });
}

/**
 * Добавление трека в очередь
 */
function addTrackToQueue(guildId, query) {
    if (!guildId || !query) return;
    
    fetch(`/api/player/${guildId}/play`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: query })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Трек добавлен в очередь', 'success');
            // Перезагружаем данные плеера
            setTimeout(() => loadGuildData(guildId), 1000);
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось добавить трек в очередь'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при добавлении трека:', error);
        showToast('Ошибка сети при добавлении трека', 'danger');
    });
}

/**
 * Загрузка радиостанций
 */
function loadRadioStations() {
    const radioStations = document.getElementById('radioStations');
    if (!radioStations) return;
    
    fetch('/api/radios')
        .then(response => response.json())
        .then(data => {
            if (data && data.radios) {
                let stationsHTML = '';
                
                for (const [key, station] of Object.entries(data.radios)) {
                    stationsHTML += `
                        <div class="radio-card mb-2" data-station="${key}">
                            <div class="d-flex align-items-center">
                                <img src="${station.thumbnail}" alt="${station.name}" class="me-2 rounded" width="40" height="40">
                                <div class="radio-info">
                                    <p class="mb-0 fw-medium">${station.name}</p>
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                radioStations.innerHTML = stationsHTML;
                
                // Добавляем обработчики событий
                const radioCards = radioStations.querySelectorAll('.radio-card');
                radioCards.forEach(card => {
                    card.addEventListener('click', function() {
                        const station = this.getAttribute('data-station');
                        if (appState.currentGuildId && station) {
                            switchRadioStation(appState.currentGuildId, station);
                        }
                    });
                });
            } else {
                radioStations.innerHTML = '<p class="text-center text-light-emphasis small mb-0">Нет доступных радиостанций</p>';
            }
        })
        .catch(error => {
            console.error('Ошибка при загрузке радиостанций:', error);
            radioStations.innerHTML = '<p class="text-center text-light-emphasis small mb-0">Ошибка при загрузке радиостанций</p>';
        });
}

/**
 * Переключение радиостанции
 */
function switchRadioStation(guildId, station) {
    if (!guildId || !station) return;
    
    fetch(`/api/player/${guildId}/switch_radio`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ station: station })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Переключено на станцию: ${data.radio_name || station}`, 'success');
            // Перезагружаем данные плеера
            setTimeout(() => loadGuildData(guildId), 1000);
        } else {
            showToast('Ошибка: ' + (data.error || 'Не удалось переключить радиостанцию'), 'danger');
        }
    })
    .catch(error => {
        console.error('Ошибка при переключении радиостанции:', error);
        showToast('Ошибка сети при переключении радиостанции', 'danger');
    });
}

/**
 * Показывает уведомление
 * @param {string} message - Текст уведомления
 * @param {string} type - Тип уведомления (success, error, info)
 */
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    
    // Создаем элемент уведомления
    const toast = document.createElement('div');
    toast.className = `toast toast-${type} show`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    // Заголовок уведомления
    let title = 'Информация';
    if (type === 'success') title = 'Успешно';
    if (type === 'error') title = 'Ошибка';
    
    // Наполнение уведомления
    toast.innerHTML = `
        <div class="toast-header">
            <strong class="me-auto">${title}</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Закрыть"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    // Добавляем уведомление в контейнер
    toastContainer.appendChild(toast);
    
    // Настраиваем автоматическое скрытие
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
    
    // Обработчик для кнопки закрытия
    const closeButton = toast.querySelector('.btn-close');
    if (closeButton) {
        closeButton.addEventListener('click', () => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        });
    }
}

/**
 * Загрузка последних заказов
 */
function loadRecentOrders() {
    const ordersList = document.getElementById('ordersList');
    if (!ordersList) return;
    
    fetch('/api/orders')
        .then(response => response.json())
        .then(data => {
            if (data && data.orders && data.orders.length > 0) {
                let ordersHTML = '';
                
                data.orders.forEach(order => {
                    ordersHTML += `
                        <div class="order-item">
                            <div class="d-flex align-items-center">
                                <div class="me-3">
                                    <img src="${order.thumbnail}" alt="${order.title}" class="rounded">
                                </div>
                                <div class="flex-grow-1">
                                    <h6 class="order-title">${order.title}</h6>
                                    <div class="d-flex align-items-center">
                                        <div class="user-icon">${order.username.charAt(0).toUpperCase()}</div>
                                        <span class="order-date">${order.date}</span>
                                    </div>
                </div>
            </div>
        </div>
    `;
                });
                
                ordersList.innerHTML = ordersHTML;
            } else {
                ordersList.innerHTML = `
                    <div class="text-center py-4">
                        <i class="bi bi-music-note-list display-4 text-muted"></i>
                        <p class="mt-2">Нет заказанных треков</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Ошибка при загрузке заказов:', error);
            ordersList.innerHTML = `
                <div class="text-center py-4">
                    <i class="bi bi-exclamation-triangle display-4 text-danger"></i>
                    <p class="mt-2">Ошибка при загрузке заказов</p>
                </div>
            `;
    });
} 