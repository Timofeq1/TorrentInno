import asyncio
import json
import os
import threading
import time
import logging
from pathlib import Path

# Импортируем реальный функционал из torrentInno
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from torrentInno import TorrentInno, create_resource_json, create_resource_from_json
from core.common.resource import Resource

# Путь к файлу для сохранения состояния торрентов
TORRENT_STATE_FILE = 'torrent_state.json'

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Глобальные переменные
_active_torrents = []
_torrent_inno = None
_loop = None
_background_thread = None

# Словарь для хранения путей к файлам
_file_paths = {}

def _run_event_loop(loop):
    """Запускает цикл событий asyncio в отдельном потоке"""
    asyncio.set_event_loop(loop)
    loop.run_forever()

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
    global _active_torrents, _torrent_inno, _loop, _background_thread
    
    # Создаем экземпляр TorrentInno
    _torrent_inno = TorrentInno()
    
    # Создаем и запускаем цикл событий в отдельном потоке
    _loop = asyncio.new_event_loop()
    _background_thread = threading.Thread(target=_run_event_loop, args=(_loop,))
    _background_thread.daemon = True  # Поток завершится при завершении основного потока
    _background_thread.start()
    
    # Загружаем сохраненное состояние
    saved_state = _load_torrent_state()
    if saved_state:
        _active_torrents = saved_state
    else:
        _active_torrents = []

def shutdown():
    """Завершает работу менеджера торрентов, сохраняя текущее состояние"""
    _save_torrent_state()
    
    # Останавливаем цикл событий
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(_loop.stop)
    
    # Ждем завершения потока
    if _background_thread and _background_thread.is_alive():
        _background_thread.join(timeout=1.0)

def get_files():
    """Возвращает список всех торрент-файлов
    
    Returns:
        list: Список словарей с информацией о торрент-файлах
    """
    return [file.copy() for file in _active_torrents]

def _convert_state_to_file_info(state, file_path):
    """Конвертирует состояние TorrentInno.State в формат файла для GUI
    
    Args:
        state (TorrentInno.State): Состояние файла
        file_path (str): Путь к файлу
        
    Returns:
        dict: Словарь с информацией о файле для GUI
    """
    # Получаем имя файла из пути
    file_name = os.path.basename(file_path)
    
    # Определяем тип файла по расширению
    file_ext = file_name.split('.')[-1] if '.' in file_name else 'unknown'
    
    # Вычисляем общий размер файла
    total_size = sum(piece.size for piece in state.piece_status)
    
    # Форматируем размер файла
    if total_size < 1024:
        size_str = f"{total_size} B"
    elif total_size < 1024 * 1024:
        size_str = f"{total_size / 1024:.2f} KB"
    elif total_size < 1024 * 1024 * 1024:
        size_str = f"{total_size / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
    
    # Конвертируем скорость в удобный формат
    download_speed = state.download_speed_bytes_per_sec
    upload_speed = state.upload_speed_bytes_per_sec
    
    if download_speed < 1024:
        download_speed_str = f"{download_speed}B/s"
    elif download_speed < 1024 * 1024:
        download_speed_str = f"{download_speed / 1024:.1f}KB/s"
    else:
        download_speed_str = f"{download_speed / (1024 * 1024):.1f}MB/s"
    
    if upload_speed < 1024:
        upload_speed_str = f"{upload_speed}B/s"
    elif upload_speed < 1024 * 1024:
        upload_speed_str = f"{upload_speed / 1024:.1f}KB/s"
    else:
        upload_speed_str = f"{upload_speed / (1024 * 1024):.1f}MB/s"
    
    # Создаем блоки для отображения прогресса
    blocks = [1 if piece else 0 for piece in state.piece_status]
    
    # Если блоков слишком много, уменьшаем их количество до 20
    if len(blocks) > 20:
        # Группируем блоки
        group_size = len(blocks) // 20
        grouped_blocks = []
        for i in range(0, len(blocks), group_size):
            group = blocks[i:i+group_size]
            # Если хотя бы половина блоков в группе загружена, считаем группу загруженной
            grouped_blocks.append(1 if sum(group) >= len(group) / 2 else 0)
        blocks = grouped_blocks[:20]  # Берем только первые 20 групп
    
    # Если блоков меньше 20, дополняем до 20
    while len(blocks) < 20:
        blocks.append(0)
    
    return {
        'name': file_name,
        'size': size_str,
        'type': file_ext,
        'download_speed': download_speed_str,
        'upload_speed': upload_speed_str,
        'blocks': blocks
    }

async def _get_all_states():
    """Получает состояние всех файлов
    
    Returns:
        list: Список состояний файлов
    """
    if not _torrent_inno:
        return []
    
    try:
        states = await _torrent_inno.get_all_files_state()
        return states
    except Exception as e:
        logging.error(f"Ошибка при получении состояния файлов: {e}")
        return []

def update_files():
    """Обновляет информацию о всех торрент-файлах
    
    Returns:
        list: Список обновленных торрент-файлов
    """
    global _active_torrents
    
    try:
        # Получаем состояние всех файлов
        states_future = asyncio.run_coroutine_threadsafe(_get_all_states(), _loop)
        states = states_future.result(timeout=5.0)  # Ждем результат не более 5 секунд
        
        # Обновляем информацию о файлах
        updated_files = []
        for file_path, state in states:
            file_info = _convert_state_to_file_info(state, file_path)
            updated_files.append(file_info)
            # Сохраняем путь к файлу
            _file_paths[file_info['name']] = file_path
        
        _active_torrents = updated_files
        _save_torrent_state()
        
    except Exception as e:
        logging.error(f"Ошибка при обновлении файлов: {e}")
    
    return get_files()

def create_resource_from_file(file_path, comment="", name=None):
    """Создает ресурс JSON из файла
    
    Args:
        file_path (str): Путь к файлу
        comment (str): Комментарий к файлу
        name (str): Имя файла (если не указано, используется имя исходного файла)
        
    Returns:
        dict: JSON с метаданными торрента
    """
    # Если имя не указано, используем имя исходного файла
    if name is None:
        name = os.path.basename(file_path)
    
    # Используем реальную функцию из torrentInno
    return create_resource_json(
        name=name,
        comment=comment,
        file_path=Path(file_path),
        min_piece_size=1000 * 1000,  # 1MB
        max_pieces=10000
    )

def start_sharing_file(file_path, resource_json):
    """Начинает раздачу файла
    
    Args:
        file_path (str): Путь к файлу
        resource_json (dict): JSON с метаданными торрента
        
    Returns:
        dict: Информация о добавленном торренте
    """
    # Создаем ресурс из JSON
    resource = create_resource_from_json(resource_json)
    
    # Запускаем раздачу файла
    asyncio.run_coroutine_threadsafe(
        _torrent_inno.start_share_file(Path(file_path).resolve(), resource),
        _loop
    )
    
    # Создаем информацию о торренте для GUI
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    file_ext = file_name.split('.')[-1] if '.' in file_name else 'unknown'
    
    # Форматируем размер файла
    if file_size < 1024:
        size_str = f"{file_size} B"
    elif file_size < 1024 * 1024:
        size_str = f"{file_size / 1024:.2f} KB"
    elif file_size < 1024 * 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
    
    # Создаем новый торрент с полностью загруженными блоками
    new_file = {
        'name': file_name,
        'size': size_str,
        'type': file_ext,
        'download_speed': '0MB/s',
        'upload_speed': '0.5MB/s',  # Начальная скорость раздачи
        'blocks': [1] * 20  # Все блоки загружены
    }
    
    # Добавляем файл в список активных торрентов
    _active_torrents.append(new_file)
    _file_paths[file_name] = file_path
    _save_torrent_state()
    
    return new_file.copy()

def start_download_file(destination_path, resource_json):
    """Начинает загрузку файла
    
    Args:
        destination_path (str): Путь для сохранения файла
        resource_json (dict): JSON с метаданными торрента
        
    Returns:
        dict: Информация о добавленном торренте
    """
    # Создаем ресурс из JSON
    resource = create_resource_from_json(resource_json)
    
    # Запускаем загрузку файла
    asyncio.run_coroutine_threadsafe(
        _torrent_inno.start_download_file(Path(destination_path).resolve(), resource),
        _loop
    )
    
    # Получаем имя файла из пути назначения
    file_name = os.path.basename(destination_path)
    
    # Определяем тип файла по расширению
    file_ext = file_name.split('.')[-1] if '.' in file_name else 'unknown'
    
    # Вычисляем общий размер файла из ресурса
    total_size = sum(piece['size'] for piece in resource_json['pieces'])
    
    # Форматируем размер файла
    if total_size < 1024:
        size_str = f"{total_size} B"
    elif total_size < 1024 * 1024:
        size_str = f"{total_size / 1024:.2f} KB"
    elif total_size < 1024 * 1024 * 1024:
        size_str = f"{total_size / (1024 * 1024):.2f} MB"
    else:
        size_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
    
    # Создаем новый торрент с незагруженными блоками
    new_file = {
        'name': file_name,
        'size': size_str,
        'type': file_ext,
        'download_speed': '1MB/s',  # Начальная скорость загрузки
        'upload_speed': '0MB/s',
        'blocks': [0] * 20  # Все блоки не загружены
    }
    
    # Добавляем файл в список активных торрентов
    _active_torrents.append(new_file)
    _file_paths[file_name] = destination_path
    _save_torrent_state()
    
    return new_file.copy()

def remove_torrent(index):
    """Удаляет торрент из списка активных по индексу
    
    Args:
        index (int): Индекс файла в списке
        
    Returns:
        bool: True если торрент успешно удален, иначе False
    """
    try:
        if 0 <= index < len(_active_torrents):
            file_name = _active_torrents[index]['name']
            file_path = _file_paths.get(file_name)
            
            # Если есть путь к файлу, останавливаем раздачу/загрузку
            if file_path and _torrent_inno:
                try:
                    # Пытаемся остановить раздачу файла
                    asyncio.run_coroutine_threadsafe(
                        _torrent_inno.stop_share_file(Path(file_path).resolve()),
                        _loop
                    ).result(timeout=5.0)
                except Exception as e:
                    logging.error(f"Ошибка при остановке раздачи файла: {e}")
            
            # Удаляем файл из списка активных торрентов
            del _active_torrents[index]
            if file_name in _file_paths:
                del _file_paths[file_name]
            
            _save_torrent_state()
            return True
    except Exception as e:
        logging.error(f"Ошибка при удалении торрента: {e}")
    
    return False