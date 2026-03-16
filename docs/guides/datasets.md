# Датасеты

## Обзор

pulsar-ai поддерживает загрузку данных из локальных файлов, API и HuggingFace Hub. Данные автоматически очищаются (удаление дубликатов, пустых строк) и разбиваются на train/test.

---

## Поддерживаемые форматы

| Формат | Расширение | Авто-определение | Описание |
|---|---|---|---|
| CSV | `.csv` | Да | Текстовый файл с разделителем-запятой |
| JSONL | `.jsonl` | Да | Одна JSON-запись на строку |
| JSON | `.json` | Да | JSON-массив записей |
| Parquet | `.parquet` | Да | Колоночный бинарный формат (Apache Arrow) |
| Excel | `.xlsx`, `.xls` | Да | Microsoft Excel |

Формат определяется автоматически по расширению файла. Можно указать явно:

```yaml
dataset:
  path: data/my_data.txt
  format: csv   # явное указание
```

---

## Минимальная схема CSV

Для обучения необходимы как минимум **один текстовый столбец** (вход) и **один или несколько столбцов с метками** (выход):

```csv
text,label
"Закажи такси",transport
"Какая погода завтра",weather
"Включи музыку",entertainment
"Переведи 100 долларов",finance
```

Для многолейбовой классификации:

```csv
phrase,domain,skill
"Закажи такси до аэропорта",transport,taxi
"Какая погода в Москве",info,weather
"Поставь будильник на 7 утра",productivity,alarm
```

Укажите соответствие в конфиге:

```yaml
dataset:
  path: data/my_data.csv
  text_column: phrase          # столбец с входным текстом
  label_columns:               # столбцы с метками
    - domain
    - skill
```

---

## Загрузка данных

### Через UI

1. Откройте **Datasets** в Web UI
2. Нажмите **Upload Dataset**
3. Выберите файл (CSV, JSONL, Parquet, Excel)
4. Система автоматически определит столбцы и покажет превью

### Через API

```bash
curl -X POST http://localhost:8888/api/datasets/upload \
  -F "file=@data/my_dataset.csv" \
  -F "name=my-intent-dataset"
```

Ответ:

```json
{
  "id": "ds_abc123",
  "name": "my-intent-dataset",
  "format": "csv",
  "rows": 5000,
  "columns": ["phrase", "domain", "skill"],
  "size_mb": 1.2,
  "created_at": "2026-03-03T10:30:00"
}
```

### Прямое копирование файлов

Поместите файл в директорию `data/`:

```bash
cp ~/Downloads/my_dataset.csv data/my_dataset.csv
```

Укажите путь в конфиге эксперимента:

```yaml
dataset:
  path: data/my_dataset.csv
```

---

## Превью датасета

Перед обучением полезно проверить данные:

=== "API"

    ```bash
    curl http://localhost:8888/api/datasets/ds_abc123/preview?rows=5
    ```

    Ответ:

    ```json
    {
      "id": "ds_abc123",
      "name": "my-intent-dataset",
      "columns": ["phrase", "domain", "skill"],
      "total_rows": 5000,
      "preview": [
        {"phrase": "Закажи такси", "domain": "transport", "skill": "taxi"},
        {"phrase": "Какая погода", "domain": "info", "skill": "weather"}
      ],
      "stats": {
        "domain": {"unique": 12, "top": [["transport", 850], ["info", 720]]},
        "skill":  {"unique": 45, "top": [["taxi", 210], ["weather", 180]]}
      }
    }
    ```

=== "UI"

    1. Откройте **Datasets** в Web UI
    2. Выберите датасет из списка
    3. Увидите таблицу с данными, статистику по столбцам и распределение меток

---

## Системные промпты

Системный промпт задаёт инструкции для модели (роль, формат ответа, допустимые значения). Хранится в директории `prompts/`:

```text
# prompts/cam_taxonomy.txt

Ты классификатор пользовательских запросов.
Проанализируй фразу и верни JSON с полями:
- domain: один из [transport, info, finance, entertainment, productivity]
- skill: конкретный навык в рамках домена

Отвечай только JSON, без пояснений.
```

Указание в конфиге:

```yaml
dataset:
  system_prompt_file: prompts/cam_taxonomy.txt
  # или inline:
  # system_prompt: "Ты классификатор. Верни JSON с полями domain и skill."
```

!!! tip "Файл vs inline"
    Используйте `system_prompt_file` для длинных промптов (таксономии, списки допустимых значений). Для коротких инструкций подходит `system_prompt` прямо в YAML.

---

## Советы по качеству данных

!!! warning "Кодировка файлов"
    Все файлы данных **должны** быть в кодировке **UTF-8**. Файлы в Windows-1251, CP1252 или других кодировках вызовут ошибки парсинга или искажение данных.

    Проверьте кодировку:

    ```bash
    file -i data/my_dataset.csv
    # должно быть: charset=utf-8
    ```

    Конвертация:

    ```bash
    iconv -f windows-1251 -t utf-8 data/old.csv > data/new.csv
    ```

### Рекомендации

1. **Баланс классов**: старайтесь, чтобы каждый класс имел не менее 50 примеров. При сильном дисбалансе используйте `stratify_column` для стратифицированного разбиения.

2. **Дедупликация**: pulsar-ai автоматически удаляет дубликаты, но лучше проверить данные заранее.

3. **Длина примеров**: очень длинные примеры (> `max_seq_length` токенов) будут обрезаны. Проверьте распределение длин.

4. **Разделитель CSV**: используйте запятую (`,`). Для данных с запятыми внутри текста -- экранируйте кавычками.

5. **Пропущенные значения**: строки с пустым `text_column` автоматически удаляются. Пустые метки могут вызвать проблемы -- заполните или удалите их.

```yaml
dataset:
  path: data/my_data.csv
  text_column: phrase
  label_columns: [domain, skill]
  test_size: 0.15
  stratify_column: domain    # стратификация по домену
```

---

## Загрузка с HuggingFace Hub

pulsar-ai поддерживает загрузку датасетов напрямую с HuggingFace:

```yaml
dataset:
  source: huggingface
  hub_name: "imdb"           # имя датасета на HF Hub
  hub_split: "train"         # split: train, test, validation
  hub_subset: null            # subset/config (если есть)
  hub_columns:                # какие столбцы оставить
    - text
    - label
  text_column: text
  label_columns: [label]
```

!!! note "Размер данных"
    Большие датасеты с HuggingFace Hub могут занять значительное время при первой загрузке. Данные кэшируются локально.
