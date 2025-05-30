## Функции

### initialize()

```python
def initialize()
```

Инициализирует менеджер торрентов, загружая сохраненное состояние из файла. Если сохраненное состояние отсутствует, используются тестовые данные.

**Возвращаемое значение:** Нет

### shutdown()

```python
def shutdown()
```

Завершает работу менеджера торрентов, сохраняя текущее состояние в файл.

**Возвращаемое значение:** Нет

### get_files()

```python
def get_files()
```

Возвращает список всех активных торрент-файлов.

**Возвращаемое значение:** Список словарей с информацией о торрент-файлах. Каждый словарь содержит следующие ключи:
- `name`: Имя файла
- `size`: Размер файла (строка с единицами измерения)
- `type`: Тип файла
- `download_speed`: Скорость загрузки (строка с единицами измерения)
- `upload_speed`: Скорость выгрузки (строка с единицами измерения)
- `blocks`: Список блоков файла (0 - не загружен, 1 - загружен)

### update_file(file_name)

```python
def update_file(file_name)
```

Обновляет информацию о конкретном торрент-файле.

**Параметры:**
- `file_name`: Имя файла для обновления

**Возвращаемое значение:** Словарь с обновленной информацией о скорости и блоках, или None если файл не найден. Словарь содержит следующие ключи:
- `download_speed`: Скорость загрузки
- `upload_speed`: Скорость выгрузки
- `blocks`: Список блоков файла

### update_files()

```python
def update_files()
```

Обновляет информацию о всех торрент-файлах.

**Возвращаемое значение:** Список обновленных торрент-файлов (аналогично `get_files()`)

### get_file_info(url)

```python
def get_file_info(url)
```

Получает информацию о торрент-файле по URL.

**Параметры:**
- `url`: URL торрент-файла или magnet-ссылка

**Возвращаемое значение:** Словарь с информацией о торрент-файле, содержащий следующие ключи:
- `name`: Имя файла
- `size`: Размер файла
- `type`: Тип файла
- `download_speed`: Скорость загрузки (начальное значение)
- `upload_speed`: Скорость выгрузки (начальное значение)
- `blocks`: Список блоков файла (все блоки изначально не загружены)

### add_torrent(file_info)

```python
def add_torrent(file_info)
```

Добавляет новый торрент в список активных.

**Параметры:**
- `file_info`: Словарь с информацией о торрент-файле

**Возвращаемое значение:** `True` если торрент успешно добавлен, иначе `False`

### remove_torrent(file_name)

```python
def remove_torrent(file_name)
```

Удаляет торрент из списка активных.

**Параметры:**
- `file_name`: Имя файла для удаления

**Возвращаемое значение:** `True` если торрент успешно удален, иначе `False`

### get_mock_content(source)

```python
def get_mock_content(source)
```

Возвращает тестовый список файлов в торренте.

**Параметры:**
- `source`: URL или путь к торрент-файлу

**Возвращаемое значение:** Список словарей с информацией о файлах в торренте. Каждый словарь содержит следующие ключи:
- `name`: Имя файла
- `size`: Размер файла
- `selected`: Флаг выбора файла для загрузки

## Внутренние функции

### _load_torrent_state()

Загружает состояние торрентов из файла.

### _save_torrent_state()

Сохраняет состояние торрентов в файл.

### _update_file_speeds(file)

Обновляет скорость загрузки и выгрузки для файла.

### _update_file_blocks(file)

Обновляет блоки загрузки для файла.