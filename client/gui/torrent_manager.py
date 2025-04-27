import random
import json
import os

# Путь к файлу для сохранения состояния торрентов
TORRENT_STATE_FILE = 'torrent_state.json'

# Тестовые данные для торрент-файлов
_MOCK_FILES = [
    {
        'name': 'example.txt',
        'size': '1.23 kb',
        'type': 'txt',
        'download_speed': '1kb/s',
        'upload_speed': '0kb/s',
        'blocks': [0] * 20  # 0 означает не загружено, 1 означает загружено
    },
    {
        'name': 'music.mp3',
        'size': '2.03 mb',
        'type': 'mp3',
        'download_speed': '2mb/s',
        'upload_speed': '1mb/s',
        'blocks': [0] * 20
    },
    {
        'name': 'video.mp4',
        'size': '12.7 mb',
        'type': 'mp4',
        'download_speed': '1mb/s',
        'upload_speed': '1mb/s',
        'blocks': [0] * 20
    },
    {
        'name': 'unknown',
        'size': '1.097 Gb',
        'type': 'unknown',
        'download_speed': '3mb/s',
        'upload_speed': '2 mb/s',
        'blocks': [0] * 20
    }
]

# Список активных торрентов
_active_torrents = []

def _load_torrent_state():
    """Загружает состояние торрентов из файла"""
    if os.path.exists(TORRENT_STATE_FILE):
        try:
            with open(TORRENT_STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке состояния торрентов: {e}")
    return []

def _save_torrent_state():
    """Сохраняет состояние торрентов в файл"""
    try:
        with open(TORRENT_STATE_FILE, 'w') as f:
            json.dump(_active_torrents, f)
    except Exception as e:
        print(f"Ошибка при сохранении состояния торрентов: {e}")

def initialize():
    """Инициализирует менеджер торрентов, загружая сохраненное состояние"""
    global _active_torrents
    saved_state = _load_torrent_state()
    if saved_state:
        _active_torrents = saved_state
    else:
        # Если нет сохраненного состояния, используем тестовые данные
        _active_torrents = []
        for file in _MOCK_FILES:
            _active_torrents.append(file.copy())

def shutdown():
    """Завершает работу менеджера торрентов, сохраняя текущее состояние"""
    _save_torrent_state()

def get_files():
    """Возвращает список всех торрент-файлов
    
    Returns:
        list: Список словарей с информацией о торрент-файлах
    """
    return [file.copy() for file in _active_torrents]

def update_file(file_name):
    """Обновляет информацию о конкретном торрент-файле
    
    Args:
        file_name (str): Имя файла для обновления
        
    Returns:
        dict: Словарь с обновленной информацией о скорости и блоках,
              или None если файл не найден
    """
    for file in _active_torrents:
        if file['name'] == file_name:
            # Обновляем скорость загрузки и выгрузки
            _update_file_speeds(file)
            # Обновляем блоки загрузки
            _update_file_blocks(file)
            
            # Возвращаем только нужные поля
            return {
                'download_speed': file['download_speed'],
                'upload_speed': file['upload_speed'],
                'blocks': file['blocks'].copy()
            }
    return None

def _update_file_speeds(file):
    """Обновляет скорость загрузки и выгрузки для файла
    
    Args:
        file (dict): Словарь с информацией о файле
    """
    # Извлекаем текущие значения скорости
    download_value = float(file['download_speed'].split('mb/s')[0].split('kb/s')[0].strip())
    upload_value = float(file['upload_speed'].split('mb/s')[0].split('kb/s')[0].strip())
    
    # Случайно изменяем скорость
    download_value += random.uniform(-0.5, 0.5)
    upload_value += random.uniform(-0.3, 0.3)
    
    # Убеждаемся, что скорость не опускается ниже 0.1
    download_value = max(0.1, download_value)
    upload_value = max(0.1, upload_value)
    
    # Обновляем значения скорости
    if 'kb/s' in file['download_speed']:
        file['download_speed'] = f"{download_value:.1f}kb/s"
    else:
        file['download_speed'] = f"{download_value:.1f}mb/s"
        
    if 'kb/s' in file['upload_speed']:
        file['upload_speed'] = f"{upload_value:.1f}kb/s"
    else:
        file['upload_speed'] = f"{upload_value:.1f}mb/s"

def _update_file_blocks(file):
    """Обновляет блоки загрузки для файла
    
    Args:
        file (dict): Словарь с информацией о файле
    """
    # Случайно выбираем блок для отметки как загруженный
    if 0 in file['blocks']:  # Если есть еще блоки для загрузки
        zero_indices = [i for i, x in enumerate(file['blocks']) if x == 0]
        if zero_indices:  # Если есть блоки, которые еще не загружены
            # Случайно выбираем 1-3 блока для отметки как загруженные
            num_blocks = min(random.randint(1, 3), len(zero_indices))
            for _ in range(num_blocks):
                if zero_indices:  # Проверяем снова, на случай если мы использовали все индексы
                    idx = random.choice(zero_indices)
                    file['blocks'][idx] = 1
                    zero_indices.remove(idx)

def update_files():
    """Обновляет информацию о всех торрент-файлах
    
    Returns:
        list: Список обновленных торрент-файлов
    """
    for file in _active_torrents:
        _update_file_speeds(file)
        _update_file_blocks(file)
    
    return get_files()

def get_file_info(url):
    """Получает информацию о торрент-файле по URL
    
    Args:
        url (str): URL торрент-файла или magnet-ссылка
        
    Returns:
        dict: Словарь с информацией о торрент-файле
    """
    # В реальном приложении здесь был бы код для получения информации о торренте
    # Сейчас просто возвращаем тестовые данные
    
    # Генерируем случайное имя файла на основе URL
    import hashlib
    name_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    
    # Создаем новый файл с тестовыми данными
    new_file = {
        'name': f'torrent_{name_hash}',
        'size': '1.097 Gb',
        'type': 'unknown',
        'download_speed': '0mb/s',
        'upload_speed': '0mb/s',
        'blocks': [0] * 20
    }
    
    # Добавляем файл в список активных торрентов
    _active_torrents.append(new_file)
    
    return new_file.copy()

def add_torrent(file_info):
    """Добавляет новый торрент в список активных
    
    Args:
        file_info (dict): Информация о торрент-файле
        
    Returns:
        bool: True если торрент успешно добавлен, иначе False
    """
    if not file_info or 'name' not in file_info:
        return False
    
    # Проверяем, не существует ли уже торрент с таким именем
    for file in _active_torrents:
        if file['name'] == file_info['name']:
            return False
    
    # Добавляем новый торрент
    _active_torrents.append(file_info.copy())
    return True

def remove_torrent(file_name):
    """Удаляет торрент из списка активных
    
    Args:
        file_name (str): Имя файла для удаления
        
    Returns:
        bool: True если торрент успешно удален, иначе False
    """
    for i, file in enumerate(_active_torrents):
        if file['name'] == file_name:
            del _active_torrents[i]
            return True
    return False

def get_mock_content(source):
    """Возвращает тестовый список файлов в торренте
    
    Args:
        source (str): URL или путь к торрент-файлу
        
    Returns:
        list: Список словарей с информацией о файлах в торренте
    """
    # Тестовые данные для содержимого торрента
    return [
        {"name": "file1.mp4", "size": "1.2 GB", "selected": True},
        {"name": "file2.txt", "size": "15 KB", "selected": True},
        {"name": "file3.mp3", "size": "5.7 MB", "selected": True}
    ]