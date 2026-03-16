# Model Registry

Model Registry -- централизованное хранилище обученных моделей с управлением жизненным
циклом, версионированием и метаданными. Позволяет отслеживать путь модели от регистрации
до продакшена.

---

## Жизненный цикл модели

Каждая модель проходит через четыре стадии:

```
registered  →  staging  →  production  →  archived
```

| Стадия        | Описание                                               |
|---------------|--------------------------------------------------------|
| `registered`  | Модель зарегистрирована, доступна для тестирования     |
| `staging`     | Проходит валидацию перед продакшеном                   |
| `production`  | Активно используется в боевой среде                    |
| `archived`    | Снята с продакшена, сохранена для истории               |

!!! info "Правила перехода"
    Переходы возможны только в указанном порядке. Нельзя перевести модель из `registered`
    сразу в `production` -- она должна пройти через `staging`.

---

## Автоматическое версионирование

При регистрации модели с уже существующим именем система автоматически создаёт новую версию:

```
my-chatbot-v1  →  первая регистрация
my-chatbot-v2  →  обновлённая модель (новые данные)
my-chatbot-v3  →  после HPO sweep
```

Все версии сохраняются и доступны для сравнения.

---

## CLI-команды

=== "Регистрация"

    ```bash
    pulsar registry register \
      --name my-chatbot \
      --path ./output/sft-llama3-v2 \
      --base-model meta-llama/Llama-3-8B \
      --task chat \
      --tags "sft,llama3,production-ready" \
      --metrics '{"eval_loss": 0.58, "accuracy": 0.87}'
    ```

=== "Список моделей"

    ```bash
    # Все модели
    pulsar registry list

    # Фильтр по стадии
    pulsar registry list --stage production

    # Фильтр по тегу
    pulsar registry list --tag sft
    ```

=== "Продвижение стадии"

    ```bash
    # registered → staging
    pulsar registry promote my-chatbot-v2 staging

    # staging → production
    pulsar registry promote my-chatbot-v2 production

    # production → archived
    pulsar registry promote my-chatbot-v1 archived
    ```

---

## API

### Регистрация модели

```bash
curl -X POST http://localhost:8000/registry/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-chatbot",
    "path": "./output/sft-llama3-v2",
    "base_model": "meta-llama/Llama-3-8B",
    "task": "chat",
    "tags": ["sft", "llama3"],
    "metrics": {
      "eval_loss": 0.58,
      "accuracy": 0.87
    },
    "dataset_fingerprint": "abc123def456",
    "serving_format": "safetensors"
  }'
```

### Список моделей

```bash
# Все модели
curl http://localhost:8000/registry/models

# Фильтрация
curl "http://localhost:8000/registry/models?stage=production&tag=sft"
```

### Получение модели

```bash
curl http://localhost:8000/registry/models/my-chatbot-v2
```

### Продвижение стадии

```bash
curl -X POST http://localhost:8000/registry/models/my-chatbot-v2/promote \
  -H "Content-Type: application/json" \
  -d '{"stage": "staging"}'
```

### Обновление метаданных

```bash
curl -X PATCH http://localhost:8000/registry/models/my-chatbot-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["sft", "llama3", "validated"],
    "metrics": {
      "eval_loss": 0.58,
      "accuracy": 0.87,
      "human_eval": 0.91
    }
  }'
```

### Удаление модели

```bash
curl -X DELETE http://localhost:8000/registry/models/my-chatbot-v1
```

---

## Метаданные модели

Каждая модель хранит полный набор метаданных:

| Поле                  | Тип      | Описание                                    |
|-----------------------|----------|---------------------------------------------|
| `name`                | `str`    | Имя с версией (`my-chatbot-v2`)             |
| `base_model`          | `str`    | Базовая модель (HuggingFace ID)             |
| `task`                | `str`    | Задача: `chat`, `completion`, `classification` |
| `tags`                | `list`   | Теги для поиска и фильтрации               |
| `metrics`             | `dict`   | Метрики: loss, accuracy, perplexity и др.   |
| `dataset_fingerprint` | `str`    | Хеш датасета для воспроизводимости          |
| `serving_format`      | `str`    | Формат: `safetensors`, `gguf`, `onnx`       |
| `stage`               | `str`    | Текущая стадия жизненного цикла             |
| `created_at`          | `str`    | Дата регистрации (ISO 8601)                 |
| `path`                | `str`    | Путь к артефактам модели                    |

---

## Сравнение моделей

Сравнение двух или более моделей по метрикам и конфигурации:

=== "CLI"

    ```bash
    pulsar registry compare my-chatbot-v1 my-chatbot-v2 my-chatbot-v3
    ```

    Вывод:

    ```
    ┌──────────────────┬───────────────┬───────────────┬───────────────┐
    │ Metric           │ my-chatbot-v1 │ my-chatbot-v2 │ my-chatbot-v3 │
    ├──────────────────┼───────────────┼───────────────┼───────────────┤
    │ eval_loss        │ 0.69          │ 0.58          │ 0.52          │
    │ accuracy         │ 0.82          │ 0.87          │ 0.91          │
    │ stage            │ archived      │ production    │ staging       │
    │ base_model       │ Llama-3-8B    │ Llama-3-8B    │ Llama-3-8B    │
    │ serving_format   │ safetensors   │ safetensors   │ safetensors   │
    └──────────────────┴───────────────┴───────────────┴───────────────┘
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/registry/models/compare \
      -H "Content-Type: application/json" \
      -d '{
        "model_ids": ["my-chatbot-v1", "my-chatbot-v2", "my-chatbot-v3"],
        "metrics": ["eval_loss", "accuracy"]
      }'
    ```

!!! tip "Автосравнение при продвижении"
    При продвижении модели в `staging` система автоматически сравнивает её с текущей
    `production`-моделью и выводит разницу в метриках.

!!! warning "Уникальность production"
    В стадии `production` может находиться только одна версия модели с данным именем.
    При продвижении новой версии предыдущая автоматически перемещается в `archived`.
