# Переменные окружения

pulsar-ai использует переменные окружения для конфигурации секретов, интеграций и рантайм-поведения. Рекомендуется хранить их в файле `.env` в корне проекта.

!!! warning "Безопасность"
    Файл `.env` **не должен** попадать в git. Убедитесь, что он добавлен в `.gitignore`.

---

## Справочная таблица

| Переменная | Тип | По умолчанию | Описание |
|------------|-----|-------------|----------|
| `OPENAI_API_KEY` | string | -- | API-ключ OpenAI. Включает режим Co-pilot (LLM-ассистент в UI) и чат на сайте |
| `PULSAR_AUTH_ENABLED` | bool | `false` | Включить аутентификацию по API-ключам для REST API |
| `PULSAR_CORS_ORIGINS` | string | `http://localhost:3000,http://localhost:8888` | Разрешённые CORS-источники (через запятую) |
| `HF_TOKEN` | string | -- | Токен HuggingFace Hub. Требуется для гейтовых моделей (Llama, Gemma) и публикации через `pulsar export --format hub` |
| `WANDB_API_KEY` | string | -- | API-ключ Weights & Biases для трекинга экспериментов |
| `CLEARML_WEB_HOST` | string | -- | URL веб-интерфейса ClearML (включает ClearML-трекинг) |

---

## Детали по каждой переменной

### OPENAI_API_KEY

Ключ для OpenAI API. Используется двумя компонентами:

- **Co-pilot** -- LLM-ассистент в веб-интерфейсе, который помогает с конфигурацией, отладкой и анализом результатов
- **Site Chat** -- виджет чата на лендинге

!!! note "Совместимые провайдеры"
    Поддерживается любой OpenAI-совместимый API (OpenRouter, Anthropic через proxy и т.д.).
    URL эндпоинта настраивается в коде.

```bash
OPENAI_API_KEY=sk-proj-...
```

### PULSAR_AUTH_ENABLED

Когда `true`, все REST API эндпоинты требуют заголовок `X-API-Key`. API-ключи управляются через:

- CLI: `pulsar ui` -> раздел Settings
- REST API: `POST /api/v1/settings/keys`

```bash
PULSAR_AUTH_ENABLED=true
```

### PULSAR_CORS_ORIGINS

Список допустимых CORS-origins через запятую. Необходим, если фронтенд и бэкенд работают на разных портах или доменах.

```bash
PULSAR_CORS_ORIGINS=http://localhost:3000,http://localhost:8888,https://my-domain.com
```

### HF_TOKEN

Токен HuggingFace для доступа к гейтовым моделям и публикации. Получить можно на [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

!!! tip "Гейтовые модели"
    Модели Llama, Gemma и некоторые другие требуют принятия лицензии на HuggingFace
    и передачи токена при загрузке.

```bash
HF_TOKEN=hf_...
```

### WANDB_API_KEY

Ключ для Weights & Biases. Когда задан и `logging.report_to: wandb` в конфиге, метрики обучения автоматически отправляются в W&B.

```bash
WANDB_API_KEY=...
```

### CLEARML_WEB_HOST

URL веб-интерфейса ClearML. Когда задан и `logging.report_to: clearml` в конфиге, метрики обучения отправляются в ClearML.

```bash
CLEARML_WEB_HOST=https://app.clear.ml
```

---

## Пример файла .env

```bash
# ──────────────────────────────────────────────
# pulsar-ai Environment Configuration
# ──────────────────────────────────────────────

# OpenAI API (Co-pilot и Site Chat)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx

# Аутентификация REST API
PULSAR_AUTH_ENABLED=false

# CORS (фронтенд-источники через запятую)
PULSAR_CORS_ORIGINS=http://localhost:3000,http://localhost:8888

# HuggingFace Hub (для гейтовых моделей и публикации)
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx

# Weights & Biases (опционально)
# WANDB_API_KEY=

# ClearML (опционально)
# CLEARML_WEB_HOST=https://app.clear.ml
```

!!! info "Загрузка .env"
    pulsar-ai автоматически загружает `.env` из текущей рабочей директории
    при запуске `pulsar ui`. Для CLI-команд (`pulsar train`, `pulsar eval` и т.д.)
    можно использовать `dotenv` или экспортировать переменные вручную:

    === "Linux / macOS"

        ```bash
        export HF_TOKEN=hf_...
        pulsar train config.yaml
        ```

    === "Windows (PowerShell)"

        ```powershell
        $env:HF_TOKEN = "hf_..."
        pulsar train config.yaml
        ```

    === "Windows (cmd)"

        ```cmd
        set HF_TOKEN=hf_...
        pulsar train config.yaml
        ```
