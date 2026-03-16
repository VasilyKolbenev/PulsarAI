# pulsar-ai: Полное руководство

Пошаговая инструкция по установке и использованию платформы pulsar-ai для файнтюнинга LLM.

## Требования

### Hardware
- **GPU**: NVIDIA с поддержкой CUDA (минимум 6 GB VRAM для моделей 0.8-2B)
- **RAM**: 16+ GB (рекомендуется 32 GB)
- **Диск**: 50+ GB свободного места (модели, датасеты, адаптеры)

### Software
- **Python** 3.10+ (рекомендуется 3.12-3.14)
- **Node.js** 18+ (для Web UI)
- **Git**
- **CUDA Toolkit** (совместимый с вашей версией PyTorch)
- Драйверы NVIDIA последней версии

---

## 1. Клонирование репозитория

```bash
git clone https://github.com/<your-org>/pulsar-ai.git
cd pulsar-ai
```

---

## 2. Установка Python-зависимостей

### Рекомендуемый вариант (с UI и eval):

```bash
# Создаём виртуальное окружение
python -m venv .venv

# Активируем (Linux/Mac)
source .venv/bin/activate

# Активируем (Windows)
.venv\Scripts\activate

# Устанавливаем пакет с зависимостями
pip install -e ".[ui,eval]"
```

### Варианты установки:

| Команда | Что включает |
|---------|-------------|
| `pip install -e .` | Базовый CLI (train, eval, export) |
| `pip install -e ".[ui]"` | + Web UI (FastAPI, uvicorn) |
| `pip install -e ".[eval]"` | + Графики eval (seaborn, matplotlib) |
| `pip install -e ".[unsloth]"` | + Unsloth (2-5x ускорение, Linux only) |
| `pip install -e ".[hpo]"` | + HPO/Optuna (поиск гиперпараметров) |
| `pip install -e ".[vllm]"` | + vLLM serving backend |
| `pip install -e ".[llamacpp]"` | + llama.cpp serving backend |
| `pip install -e ".[deepspeed]"` | + DeepSpeed (multi-GPU) |
| `pip install -e ".[agent-serve]"` | + Agent REST server |
| `pip install -e ".[agent-memory]"` | + Agent memory backends |
| `pip install -e ".[tracking-clearml]"` | + ClearML tracking |
| `pip install -e ".[tracking-wandb]"` | + W&B tracking |
| `pip install -e ".[all]"` | Все зависимости |

### Дополнительно (для UI):

```bash
pip install python-dotenv openai slowapi
```

---

## 3. Установка UI (Web Dashboard)

```bash
cd ui
npm install
cd ..
```

---

## 4. Настройка окружения

Создайте файл `.env` в корне проекта:

```bash
# .env

# (Опционально) OpenAI API ключ для Co-pilot чата в UI
OPENAI_API_KEY=sk-your-key-here

# (Опционально) Кастомные CORS origins
# PULSAR_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# (Опционально) Включить аутентификацию API
# PULSAR_AUTH_ENABLED=true

# (Опционально) HuggingFace токен для gated-моделей (Llama и др.)
# HF_TOKEN=hf_your_token_here
```

---

## 5. Запуск платформы

### 5.1 Backend (API сервер)

```bash
python -c "from pulsar_ai.ui.app import create_app; import uvicorn; uvicorn.run(create_app(), host='0.0.0.0', port=8888)"
```

Или короче:
```bash
python -m pulsar_ai.ui.app
```

Или через CLI:
```bash
pulsar ui
```

Backend доступен на `http://localhost:8888`.
Swagger/OpenAPI документация: `http://localhost:8888/docs`.

### 5.2 Frontend (Web UI)

В отдельном терминале:

```bash
cd ui
npm run dev
```

UI доступен на `http://localhost:5173`.

### 5.3 Проверка

Откройте в браузере `http://localhost:5173` — должен загрузиться дашборд.
Проверьте API: `curl http://localhost:8888/api/v1/health` — ответ `{"status": "ok"}`.

---

## 6. Подготовка данных

### Формат датасета

pulsar-ai поддерживает CSV, JSONL, JSON, Parquet, Excel. Минимальный CSV:

```csv
phrase,domain,skill
"Оплатить коммуналку",HOUSE,utility_bill
"Когда придёт посылка",DELIVERY,tracking
"Привет!",BOLTALKA,greeting
```

Поместите файл в директорию `data/`:

```bash
cp your_dataset.csv data/my_intents.csv
```

### Загрузка через UI

1. Откройте страницу **Datasets**
2. Нажмите **Upload** и выберите файл (CSV, JSONL, Parquet, Excel)
3. Платформа автоматически определит формат, колонки и количество строк
4. Используйте **Preview** для просмотра первых N строк

### Загрузка через API

```bash
curl -X POST http://localhost:8888/api/v1/datasets/upload \
  -F "file=@data/my_intents.csv"
```

Ответ: `{"id": "...", "columns": [...], "num_rows": 1234, "size": "..."}`.

### System Prompt (опционально)

Если нужен system prompt для модели, создайте текстовый файл:

```bash
# prompts/my_system_prompt.txt
You are an intent classifier. Given a user message, respond with JSON:
{"domain": "<DOMAIN>", "skill": "<SKILL>"}
```

---

## 7. Скачивание модели

Модели скачиваются автоматически с HuggingFace при первом запуске.
Убедитесь, что есть доступ к интернету.

### Предустановленные конфиги моделей:

| Конфиг | Модель | VRAM (QLoRA) |
|--------|--------|-------------|
| `models/qwen3.5-0.8b` | Qwen/Qwen3.5-0.8B | ~2-3 GB |
| `models/qwen3.5-2b` | Qwen/Qwen3.5-2B | ~4-5 GB |
| `models/qwen3.5-4b` | Qwen/Qwen3.5-4B | ~6-7 GB |
| `models/llama3.2-1b` | meta-llama/Llama-3.2-1B-Instruct | ~3-4 GB |
| `models/qwen2.5-3b` | Qwen/Qwen2.5-3B-Instruct | ~4-5 GB |
| `models/mistral-7b` | mistralai/Mistral-7B-Instruct-v0.3 | ~8-10 GB |

### Использование своей модели

Создайте конфиг `configs/models/my-model.yaml`:

```yaml
model:
  name: your-org/your-model-name  # HuggingFace model ID
  family: llama  # или qwen3, mistral
  max_seq_length: 4096
  chat_template: chatml  # или llama3, mistral

load_in_4bit: true
gradient_checkpointing: true

lora:
  r: 16
  lora_alpha: 16
  target_modules:
    - q_proj
    - k_proj
    - v_proj
    - o_proj
    - gate_proj
    - up_proj
    - down_proj
  lora_dropout: 0
  bias: none
```

---

## 8. Создание конфига эксперимента

Создайте YAML файл в `configs/examples/`:

```yaml
# configs/examples/my-experiment.yaml

inherit:
  - base                   # Базовые настройки (optimizer, seed, etc.)
  - models/qwen3.5-0.8b   # Модель (можно заменить на свою)

task: sft  # sft или dpo

dataset:
  path: data/my_intents.csv
  format: csv
  text_column: phrase              # Колонка с текстом
  label_columns:                   # Колонки с метками
    - domain
    - skill
  system_prompt_file: prompts/my_system_prompt.txt
  test_size: 0.15                  # 15% данных на тест

training:
  epochs: 3          # Кол-во эпох
  learning_rate: 2e-4  # Learning rate
  batch_size: 1        # Размер батча (увеличить если хватает VRAM)
  gradient_accumulation: 16  # Эффективный batch = batch_size * grad_accum

output:
  dir: ./outputs/my-experiment
  save_adapter: true
```

### Быстрое создание конфига через CLI:

```bash
pulsar init my-experiment --task sft --model qwen3.5-0.8b
```

Это создаст готовый YAML в `configs/examples/`.

### Ключевые параметры:

| Параметр | Описание | Рекомендация |
|----------|----------|-------------|
| `epochs` | Количество эпох | 3-5 для маленьких датасетов |
| `learning_rate` | Скорость обучения | 2e-4 (0.8B), 1e-4 (2-4B), 5e-5 (7B+) |
| `batch_size` | Размер батча | 1-2 (8GB), 2-4 (16GB), 4-8 (24GB+) |
| `gradient_accumulation` | Шаги накопления | 16 при batch_size=1 |
| `lora.r` | LoRA rank | 8 (быстро), 16 (баланс), 32 (качество) |

---

## 9. Запуск обучения

### Через CLI:

```bash
pulsar train configs/examples/my-experiment.yaml
```

С переопределением параметров:
```bash
pulsar train configs/examples/my-experiment.yaml epochs=5 learning_rate=1e-4
```

Возобновление с чекпоинта:
```bash
pulsar train configs/examples/my-experiment.yaml --resume outputs/my-experiment/checkpoint-500
```

### Через Web UI:

1. Откройте `http://localhost:5173`
2. Перейдите в **New Experiment**
3. Выберите модель, загрузите датасет, настройте параметры
4. Нажмите **Start Training**

### Через API:

```python
import requests
from pulsar_ai.config import load_config

config = load_config('configs/examples/my-experiment.yaml')
resp = requests.post('http://localhost:8888/api/v1/training/start', json={
    'name': 'my-experiment',
    'config': config,
    'task': 'sft'
})
print(resp.json())  # {"job_id": "...", "experiment_id": "...", "status": "running"}
```

Тренировка идёт в фоне. Прогресс виден в UI на странице **Experiments**.

### Отслеживание прогресса (SSE):

```bash
curl -N http://localhost:8888/api/v1/training/progress/<job_id>
```

Поток отдаёт события: `step`, `loss`, `epoch`, `gpu_mem_gb`.

---

## 10. Оценка модели (Eval)

После обучения запустите eval:

```bash
python scripts/run_eval.py \
  --model Qwen/Qwen3.5-0.8B \
  --adapter outputs/my-experiment/lora \
  --test-data data/my_intents_test.csv \
  --experiment-id <ID из UI>
```

Или через CLI:
```bash
pulsar eval --model outputs/my-experiment/lora --test-data data/my_intents_test.csv
```

Результаты:
- **Accuracy** — общая точность
- **JSON Parse Rate** — % корректных JSON ответов
- **F1 (weighted)** — взвешенный F1
- **Confusion Matrix** — матрица ошибок по классам

Результаты автоматически сохраняются в experiment store и видны в UI.

---

## 11. DPO (опционально)

DPO (Direct Preference Optimization) — второй этап после SFT.
Нужны пары "предпочтительный/непредпочтительный" ответы.

### Формат DPO пар (JSONL):

```jsonl
{"prompt": "Оплатить газ", "chosen": "{\"domain\": \"HOUSE\", \"skill\": \"utility_bill\"}", "rejected": "{\"domain\": \"PAYMENTS\", \"skill\": \"payment_status\"}"}
```

**Важно:** Формат `chosen` и `rejected` должен точно совпадать с форматом, на который натренирована SFT-модель. Лишние поля приводят к деградации JSON parse rate.

### Конфиг DPO:

```yaml
# configs/examples/my-dpo.yaml
inherit:
  - base
  - models/qwen3.5-0.8b
  - tasks/dpo

sft_adapter_path: ./outputs/my-sft/lora  # Путь к SFT адаптеру

dpo:
  beta: 0.1
  max_length: 512
  pairs_path: ./data/my_dpo_pairs.jsonl

output:
  dir: ./outputs/my-dpo
```

```bash
pulsar train configs/examples/my-dpo.yaml
```

---

## 12. Экспорт модели

### GGUF (для llama.cpp, Ollama):

```bash
pulsar export --model ./outputs/my-experiment/lora --format gguf --quant q4_k_m
```

### Merge LoRA + Base:

```bash
pulsar export --model ./outputs/my-experiment/lora --format merged
```

### Push на HuggingFace Hub:

```bash
pulsar export --model ./outputs/my-experiment/lora --format hub
```

### Через API:

```bash
curl -X POST http://localhost:8888/api/v1/export -H "Content-Type: application/json" \
  -d '{"experiment_id": "...", "format": "gguf", "quantization": "q4_k_m"}'
```

Доступные квантизации: `q4_k_m`, `q8_0`, `f16`.

---

## 13. Serving (запуск модели как API)

### llama.cpp (GGUF файлы):

```bash
pulsar serve --model ./outputs/model-q4_k_m.gguf --port 8080 --backend llamacpp
```

### vLLM (полные модели):

```bash
pulsar serve --model ./outputs/my-merged-model --port 8080 --backend vllm
```

API совместим с форматом OpenAI (`/v1/chat/completions`).

### Метрики serving:

```bash
# Получить метрики за последние 60 секунд
curl http://localhost:8888/api/v1/serving/metrics?window=60
```

Ответ содержит: `latency_p50`, `latency_p95`, `latency_p99`, `rps`, `tokens_per_sec`, `error_rate`.

---

## 14. Workflow Builder (визуальный конструктор пайплайнов)

Workflow Builder позволяет собирать сложные ML-пайплайны визуально в стиле drag-and-drop.

### Открытие

Перейдите на страницу **Workflows** в UI (или `/workflows`).

### Создание workflow

1. Перетащите ноды из палитры (левая панель) на канвас
2. Соедините ноды стрелками (от выхода одного к входу другого)
3. Кликните на ноду правой кнопкой для настройки параметров
4. Нажмите **Save** для сохранения
5. Нажмите **Run** для запуска

### Доступные типы нод (26 штук):

| Группа | Ноды | Описание |
|--------|------|----------|
| **Data** | `dataSource`, `model`, `prompt`, `splitter` | Источники данных, выбор модели, промпт, разбиение датасета |
| **Training** | `training` | SFT/DPO обучение |
| **Evaluation** | `eval`, `conditional`, `llmJudge`, `abTest` | Eval, условное ветвление, LLM-as-Judge, A/B тест |
| **Export** | `export`, `serve` | Экспорт в GGUF/merged, деплой как API |
| **Agent** | `agent`, `rag`, `router`, `inference`, `dataGen` | Агентские шаги, RAG, роутинг, инференс, генерация данных |
| **Protocols** | `mcp`, `a2a`, `gateway` | MCP/A2A/Gateway интеграция |
| **Safety** | `inputGuard`, `outputGuard` | Guardrails на входе и выходе |
| **Ops** | `cache`, `canary`, `feedback`, `tracer` | Кэш, canary деплой, фидбэк, трейсинг |
| **Structure** | `group` | Группировка нод |

### Пример: типичный пайплайн

```
dataSource → training → eval → conditional → export → serve
                                    ↓ (если accuracy < 85%)
                                  training (retry с другими params)
```

### API workflow:

```bash
# Список всех workflow
curl http://localhost:8888/api/v1/workflows

# Сохранить workflow
curl -X POST http://localhost:8888/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "my-pipeline", "nodes": [...], "edges": [...]}'

# Запустить workflow
curl -X POST http://localhost:8888/api/v1/workflows/<workflow_id>/run

# Получить pipeline-конфиг без запуска
curl http://localhost:8888/api/v1/workflows/<workflow_id>/config
```

---

## 15. Pipeline Execution (программное выполнение пайплайнов)

Pipeline — это YAML-конфигурация для последовательного/параллельного выполнения шагов без UI.

### Конфиг pipeline:

```yaml
# configs/pipelines/full-training.yaml
steps:
  - name: fingerprint
    type: fingerprint
    config:
      path: data/my_intents.csv

  - name: train
    type: training
    depends_on: [fingerprint]
    config:
      task: sft
      inherit: [base, models/qwen3.5-0.8b]
      dataset:
        path: data/my_intents.csv

  - name: eval
    type: evaluation
    depends_on: [train]
    config:
      adapter_path: ${train.adapter_path}

  - name: export
    type: export
    depends_on: [eval]
    condition:
      metric: ${eval.accuracy}
      operator: gte
      value: 0.85
    config:
      format: gguf
      quantization: q4_k_m

  - name: register
    type: register
    depends_on: [export]
    config:
      name: my-intent-classifier
      tags: [production, v1]
```

### Запуск:

```bash
# CLI
pulsar pipeline run configs/pipelines/full-training.yaml

# Просмотр прошлых запусков
pulsar pipeline list
```

### Переменные между шагами

Шаги передают результаты дальше через синтаксис `${step_name.output_key}`. Например, `${train.adapter_path}` содержит путь к адаптеру из шага `train`.

### Условное выполнение

Шаг с `condition` выполняется только если условие истинно. Операторы: `gte`, `lte`, `gt`, `lt`, `eq`.

### WebSocket (реалтайм):

```javascript
const ws = new WebSocket('ws://localhost:8888/api/v1/pipeline/run');
ws.send(JSON.stringify({ pipeline_config: config }));
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: "step_update" | "pipeline_complete" | "pipeline_error"
  // data.step_name, data.status, data.duration_s
};
```

---

## 16. Prompt Lab (управление промптами)

Prompt Lab позволяет версионировать, тестировать и сравнивать system prompts.

### UI

Откройте страницу **Prompt Lab** (или `/prompts`).

Возможности:
- Создание промпта с названием, описанием и тегами
- Редактирование с автоматическим версионированием (v1, v2, v3...)
- Шаблоны с переменными: `{{variable}}`
- Тестовая панель: заполняете переменные → видите результат рендеринга
- Diff между версиями (визуальное сравнение)
- Привязка модели и параметров к каждой версии

### Пример промпта с переменными:

```
You are a {{task_type}} for {{domain}}.
Given a user message, respond with JSON:
{"domain": "{{expected_domain}}", "skill": "<SKILL>"}
```

### API промптов:

```bash
# Создать промпт
curl -X POST http://localhost:8888/api/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "intent-classifier",
    "system_prompt": "You are an intent classifier...",
    "description": "Классификатор интентов",
    "tags": ["classifier", "production"]
  }'

# Список промптов (фильтр по тегу)
curl "http://localhost:8888/api/v1/prompts?tag=classifier"

# Добавить новую версию
curl -X POST http://localhost:8888/api/v1/prompts/<prompt_id>/versions \
  -d '{"system_prompt": "Updated prompt text...", "model": "qwen3.5-2b"}'

# Diff между версиями
curl "http://localhost:8888/api/v1/prompts/<prompt_id>/diff?v1=1&v2=3"

# Тест промпта с переменными
curl -X POST http://localhost:8888/api/v1/prompts/<prompt_id>/test \
  -d '{"variables": {"task_type": "classifier", "domain": "banking"}}'
```

---

## 17. Monitoring (мониторинг системы)

Реалтайм-мониторинг GPU, CPU и RAM.

### UI

Откройте страницу **Monitoring** (или `/monitoring`). Графики обновляются каждые 2 секунды:
- **GPU Utilization** — загрузка GPU (%)
- **VRAM** — использование видеопамяти (GB)
- **GPU Temperature** — температура (°C)
- **GPU Power** — потребление энергии (W)
- **CPU** — загрузка процессора (%)
- **RAM** — использование оперативной памяти (GB)

При наличии нескольких GPU отображается таблица по каждому.

### API:

```bash
# SSE поток (обновления каждые 2 сек)
curl -N http://localhost:8888/api/v1/metrics/live

# Разовый снимок
curl http://localhost:8888/api/v1/metrics/snapshot
```

Данные: `cpu_percent`, `ram_used_gb`, `ram_total_gb`, а для каждого GPU: `name`, `utilization_percent`, `memory_used_gb`, `memory_total_gb`, `temperature_c`, `power_watts`.

---

## 18. Compute Management (управление вычислительными ресурсами)

Позволяет добавлять удалённые GPU-серверы через SSH.

### UI

Откройте страницу **Compute** (или `/compute`):
- Локальная машина отображается автоматически
- Нажмите **Add Target** для добавления удалённого сервера
- Для каждого таргета доступны кнопки: **Test** (проверка SSH), **Detect** (определение GPU), **Remove**

### Добавление удалённого GPU-сервера:

```bash
# Добавить таргет
curl -X POST http://localhost:8888/api/v1/compute/targets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpu-server-1",
    "host": "192.168.1.100",
    "user": "ml-user",
    "port": 22,
    "key_path": "~/.ssh/id_rsa"
  }'

# Проверить SSH-соединение
curl -X POST http://localhost:8888/api/v1/compute/targets/<target_id>/test

# Определить GPU на удалённой машине
curl -X POST http://localhost:8888/api/v1/compute/targets/<target_id>/detect
```

Detect возвращает: `gpu_count`, `gpu_type`, `vram_gb`.

---

## 19. Model Registry (реестр моделей)

Реестр для версионирования и управления жизненным циклом обученных моделей.

### Жизненный цикл модели:

```
registered → staging → production → archived
```

### Регистрация через CLI:

```bash
# Зарегистрировать модель
pulsar registry register my-classifier \
  --model-path outputs/my-experiment/lora \
  --task sft \
  --base-model Qwen/Qwen3.5-0.8B \
  --tag production

# Список моделей
pulsar registry list
pulsar registry list --status production

# Повышение статуса
pulsar registry promote my-classifier-v1 staging
pulsar registry promote my-classifier-v1 production
```

### API:

```bash
# Зарегистрировать
curl -X POST http://localhost:8888/api/v1/registry \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-classifier",
    "model_path": "outputs/my-experiment/lora",
    "task": "sft",
    "base_model": "Qwen/Qwen3.5-0.8B",
    "metrics": {"accuracy": 0.875, "f1": 0.903},
    "tags": ["intent", "v1"]
  }'

# Список (с фильтрами)
curl "http://localhost:8888/api/v1/registry?status=production&tag=intent"

# Сравнить модели
curl -X POST http://localhost:8888/api/v1/registry/compare \
  -d '{"model_ids": ["my-classifier-v1", "my-classifier-v2"]}'

# Обновить статус
curl -X PUT http://localhost:8888/api/v1/registry/my-classifier-v1/status \
  -d '{"status": "production"}'
```

Версионирование автоматическое: `my-classifier-v1`, `my-classifier-v2`, ...

---

## 20. HPO (поиск гиперпараметров)

Автоматический поиск оптимальных гиперпараметров через Optuna.

### Установка:

```bash
pip install -e ".[hpo]"
```

### Конфиг sweep:

```yaml
# configs/sweeps/lr-sweep.yaml
hpo:
  method: optuna
  metric: training_loss
  direction: minimize
  n_trials: 20
  search_space:
    training.learning_rate: [1e-5, 5e-4, log]     # log-uniform
    lora.r: [8, 64, int]                            # целое число
    lora.lora_alpha: [16, 128, int]
    training.epochs: [1, 5, int]
    training.batch_size: [1, 2, 4, 8]              # категориальный
```

### Типы search space:

| Формат | Тип | Пример |
|--------|-----|--------|
| `[min, max, log]` | Log-uniform float | `[1e-5, 5e-4, log]` |
| `[min, max]` | Linear float | `[0.01, 0.5]` |
| `[min, max, int]` | Integer range | `[8, 64, int]` |
| `[val1, val2, ...]` | Categorical | `[1, 2, 4, 8]` |

### Запуск:

```bash
pulsar sweep configs/examples/my-experiment.yaml configs/sweeps/lr-sweep.yaml \
  --n-trials 20 \
  --name my-lr-search
```

Результаты сохраняются в `./data/sweeps/my-lr-search.json` с лучшими параметрами и всеми trial'ами.

---

## 21. Co-pilot / Assistant (AI-помощник)

Встроенный AI-помощник доступен на каждой странице UI в правой панели.

### Команды (всегда доступны, без OpenAI ключа):

| Команда | Описание |
|---------|----------|
| `/status` | Текущие задания и статус системы |
| `/datasets` | Список загруженных датасетов |
| `/train name=X model=Y dataset=Z` | Запуск обучения |
| `/recommend model=3B rows=1000` | Рекомендации по гиперпараметрам для модели/данных |
| `/hardware` | Информация о GPU/CPU/RAM |
| `/experiments` | Список экспериментов |
| `/workflows` | Список сохранённых workflow |
| `/estimate model=3B rows=1000 epochs=3` | Оценка времени и стоимости обучения |
| `/cancel job_id=X` | Отменить задание |
| `/preview id=X` | Превью эксперимента |
| `/help` | Справка по командам |

### LLM-режим (требует OPENAI_API_KEY):

Если задан `OPENAI_API_KEY` в `.env`, помощник использует GPT-4o-mini с доступом к 14 инструментам платформы:
- Управление экспериментами и обучением
- Просмотр и анализ датасетов
- Рекомендации параметров с учётом вашего GPU
- Оценка стоимости обучения
- Подбор конфигурации под задачу (chatbot, classifier, summarizer и др.)

Просто пишите на естественном языке: _"Запусти обучение qwen 0.8b на датасете cam_intents.csv с 5 эпохами"_.

---

## 22. Agent Framework (создание AI-агентов)

Фреймворк для создания и деплоя AI-агентов с инструментами, памятью и guardrails.

### Создание агента:

```bash
pulsar agent init my-assistant
```

Создаёт конфиг `configs/agents/my-assistant.yaml`:

```yaml
agent:
  name: my-assistant
  system_prompt: "You are a helpful assistant..."

model:
  base_url: http://localhost:8080/v1   # Ваш LLM-сервер
  name: default
  timeout: 120

tools:
  - search_files
  - read_file
  - list_directory
  - calculate

memory:
  max_tokens: 4096
  strategy: sliding_window

guardrails:
  max_iterations: 15
  max_tokens: 8192
```

### Встроенные инструменты:

| Инструмент | Описание |
|------------|----------|
| `search_files` | Поиск файлов по glob-паттерну |
| `read_file` | Чтение файла (до 200 строк) |
| `list_directory` | Список файлов в директории |
| `calculate` | Безопасные математические вычисления |

### Тестирование (интерактивный REPL):

```bash
pulsar agent test configs/agents/my-assistant.yaml
```

### Деплой агента как API:

```bash
pulsar agent serve configs/agents/my-assistant.yaml --port 8081
```

API: `POST /v1/agent/chat` с телом `{"message": "..."}`.

Два режима вызова инструментов:
- **Native** — function calling (OpenAI-совместимый)
- **ReAct** — текстовый цикл Thought/Action/Observation

---

## 23. Protocols (MCP, A2A, API Gateway)

### MCP (Model Context Protocol)

Позволяет модели взаимодействовать с внешними инструментами через стандартный протокол.

```bash
curl -X POST http://localhost:8888/api/v1/protocols/mcp/configure \
  -d '{
    "name": "pulsar-mcp",
    "transport": "sse",
    "host": "localhost",
    "port": 8890,
    "tools": ["train", "eval", "export"],
    "auth_token_env": "MCP_TOKEN"
  }'
```

Транспорты: `stdio`, `sse`, `streamable_http`.

### A2A (Agent-to-Agent)

Google Agent-to-Agent протокол для взаимодействия между агентами.

```bash
# Получить карточку агента
curl http://localhost:8888/api/v1/protocols/a2a/agent-card

# Настроить
curl -X POST http://localhost:8888/api/v1/protocols/a2a/configure \
  -d '{
    "agent_card": {
      "name": "pulsar-agent",
      "description": "LLM training agent",
      "url": "http://localhost:8888",
      "skills": ["training", "evaluation", "export"],
      "capabilities": {"streaming": true, "pushNotifications": false}
    }
  }'
```

Состояния задач: `submitted` → `working` → `completed` / `failed` / `canceled`.

### API Gateway

Маршрутизация запросов к нескольким агентам через единую точку входа.

```bash
curl -X POST http://localhost:8888/api/v1/protocols/gateway/configure \
  -d '{
    "name": "pulsar-gateway",
    "host": "0.0.0.0",
    "port": 9000,
    "protocols": ["rest"],
    "auth_method": "api_key",
    "rate_limit": 100,
    "cors_origins": ["*"],
    "load_balancer": "round_robin"
  }'
```

### Сводка:

```bash
curl http://localhost:8888/api/v1/protocols/summary
```

---

## 24. Guardrails (защитные механизмы)

Guardrails защищают вход и выход модели от нежелательного контента.

### Типы правил:

| Тип | Описание | Действия |
|-----|----------|----------|
| `pii` | Детекция email, телефонов, SSN, кредитных карт, IP, API-ключей | block, mask, warn, log |
| `injection` | Детекция prompt injection (7 паттернов) | block, warn, log |
| `toxicity` | Блокировка по списку запрещённых слов | block, warn, log |
| `regex` | Кастомный regex-паттерн (whitelist/blacklist) | block, warn, log |
| `json_schema` | Валидация JSON-формата с обязательными ключами | block, warn |
| `length` | Проверка min/max длины ответа | block, warn |

### Использование в workflow:

Добавьте ноды `inputGuard` и `outputGuard` в Workflow Builder для фильтрации на входе и выходе.

### Использование в агенте:

```yaml
# В конфиге агента
guardrails:
  max_iterations: 15
  max_tokens: 8192
```

### Программное использование:

```python
from pulsar_ai.guardrails.engine import create_input_guard, create_output_guard

input_guard = create_input_guard(pii=True, injection=True, toxicity=True, pii_action="mask")
output_guard = create_output_guard(pii=True, json_schema=True, required_keys=["domain", "skill"])

result = input_guard.check("my input text")
# result.passed, result.violations, result.modified_text
```

При `pii_action="mask"` PII заменяется на `[EMAIL_REDACTED]`, `[PHONE_REDACTED]` и т.д.

---

## 25. Experiment Tracking (отслеживание экспериментов)

### Управление через CLI:

```bash
# Список прошлых запусков
pulsar runs list
pulsar runs list --project my-project --status completed --limit 20

# Детали запуска
pulsar runs show <run_id>

# Сравнение нескольких запусков
pulsar runs compare <run_id_1> <run_id_2> <run_id_3>
```

### API:

```bash
# Список
curl "http://localhost:8888/api/v1/runs?project=my-project&status=completed&limit=20"

# Детали
curl http://localhost:8888/api/v1/runs/<run_id>

# Сравнение (config diff + metrics)
curl -X POST http://localhost:8888/api/v1/runs/compare \
  -d '{"run_ids": ["run1", "run2"]}'
```

### Интеграции:

- **ClearML**: `pip install -e ".[tracking-clearml]"` — автоматический логгинг в ClearML
- **W&B**: `pip install -e ".[tracking-wandb]"` — автоматический логгинг в Weights & Biases

---

## 26. Observability (наблюдаемость)

### Трейсинг

Встроенный трейсер в стиле OpenTelemetry для отслеживания LLM-вызовов:

```python
from pulsar_ai.observability.tracer import get_tracer

tracer = get_tracer()
with tracer.start_trace("my-pipeline") as trace:
    with tracer.start_span(trace, "preprocessing"):
        # ...
        pass
    with tracer.start_span(trace, "inference"):
        tracer.record_llm_call(trace, model="qwen3.5-0.8b",
                               input_tokens=100, output_tokens=50, latency_ms=230)
```

### Cost Tracking

Отслеживание стоимости LLM-вызовов:

```python
from pulsar_ai.cost import CostTracker

tracker = CostTracker(budget_usd=10.0)
tracker.record(model="gpt-4o", input_tokens=1000, output_tokens=500, operation="eval")

summary = tracker.get_summary()
# {"total_cost": 0.0075, "budget_remaining": 9.9925, "by_model": {...}}
```

Встроенные цены: GPT-4o, GPT-4o-mini, Claude Sonnet/Opus/Haiku, Llama, Mistral, local (бесплатно).

### Semantic Cache

LRU-кэш LLM-ответов для экономии токенов:

```python
from pulsar_ai.cache import SemanticCache

cache = SemanticCache(max_entries=10000, ttl=3600)
cached = cache.get(model="qwen", prompt="classify: hello")
if not cached:
    result = model.generate(...)
    cache.set(model="qwen", prompt="classify: hello", response=result)
```

---

## 27. Canary Deploy и A/B Testing

### Canary (постепенный деплой):

```python
from pulsar_ai.deployment.canary import CanaryDeployer

deployer = CanaryDeployer(
    primary_endpoint="http://model-v1:8080",
    canary_endpoint="http://model-v2:8080",
    canary_weight=0.1,         # 10% трафика на canary
    error_threshold=0.05,      # откат при >5% ошибок
    promote_after=1000          # автопромоут после 1000 запросов
)

target = deployer.route()  # "primary" или "canary"
```

### A/B Testing:

```python
from pulsar_ai.deployment.canary import ABTester

tester = ABTester(variants={"model-a": 0.5, "model-b": 0.5})
variant = tester.route()
# ... получить результат ...
tester.record_metric(variant, accuracy)

results = tester.get_results()
# {"model-a": {"mean": 0.87, "samples": 500}, "model-b": {"mean": 0.91, ...}, "winner": "model-b"}
```

---

## 28. Human Feedback (обратная связь)

Сбор фидбэка от пользователей (thumbs up/down) с автоматической генерацией DPO-пар:

```python
from pulsar_ai.feedback import FeedbackCollector

collector = FeedbackCollector()
collector.record(prompt="...", response="...", rating="positive")  # или "negative"

# Экспорт в DPO-пары для дообучения
dpo_pairs = collector.export_dpo_pairs()
```

Замкнутый цикл: feedback → DPO pairs → DPO training → улучшенная модель.

---

## 29. Settings и Authentication

### UI

Откройте страницу **Settings** (или `/settings`):
- Информация о сервере (версия, auth status)
- Управление API-ключами (создание, отзыв)
- Информация о hardware

### Включение аутентификации:

1. Установите в `.env`:
   ```bash
   PULSAR_AUTH_ENABLED=true
   ```

2. Перезапустите backend

3. Сгенерируйте API-ключ:
   ```bash
   curl -X POST http://localhost:8888/api/v1/settings/keys \
     -d '{"name": "my-key"}'
   ```
   Ответ содержит plaintext ключ (показывается только раз): `pulsar_<32-символа>`.

4. Используйте ключ в запросах:
   ```bash
   curl -H "Authorization: Bearer pulsar_xxxxx" http://localhost:8888/api/v1/experiments
   ```

Публичные эндпоинты (не требуют ключа): `/api/v1/health`, `/docs`, `/openapi.json`, `/redoc`.

### Rate Limiting:

Встроенный rate limiter: 60 запросов/минуту на IP (через `slowapi`).

---

## Полный справочник CLI

```
pulsar train <config.yaml> [key=val ...]     Обучение (SFT/DPO)
  --task sft|dpo|auto                        Тип задачи
  --base-model PATH                          Базовая модель
  --resume PATH                              Продолжить с чекпоинта

pulsar eval --model PATH --test-data PATH    Оценка модели
  --batch-size N                             Размер батча
  --output PATH                              Путь для результатов

pulsar export --model PATH --format FMT      Экспорт модели
  --format gguf|merged|hub                   Формат экспорта
  --quant q4_k_m|q8_0|f16                    Квантизация (для GGUF)

pulsar serve --model PATH --port PORT        Запуск inference API
  --backend llamacpp|vllm                    Бэкенд

pulsar init <name>                           Создать конфиг эксперимента
  --task sft|dpo                              Тип задачи
  --model qwen3.5-0.8b|llama3.2-1b|...       Модель

pulsar info                                  Информация о hardware
pulsar ui [--port 8888]                      Запуск Web UI

pulsar sweep <config> <sweep_config>         HPO sweep
  --n-trials N                               Кол-во trials
  --name NAME                                Имя study

pulsar agent init <name>                     Создать конфиг агента
pulsar agent test <config.yaml>              Тест агента (REPL)
pulsar agent serve <config.yaml>             Деплой агента как API

pulsar pipeline run <config.yaml>            Запуск pipeline
pulsar pipeline list                         Список прошлых pipeline-запусков

pulsar runs list [--project X] [--status Y]  Список запусков
pulsar runs show <run_id>                    Детали запуска
pulsar runs compare <id1> <id2> ...          Сравнение запусков

pulsar registry list [--status X]            Список моделей в реестре
pulsar registry register <name> --model-path Зарегистрировать модель
pulsar registry promote <id> <status>        Изменить статус модели
```

---

## Структура проекта

```
pulsar-ai/
  configs/
    base.yaml              # Дефолтные настройки
    models/                # Конфиги моделей (qwen, llama, mistral)
    tasks/                 # Конфиги задач (sft, dpo, eval)
    examples/              # Готовые эксперименты
    agents/                # Конфиги агентов
    pipelines/             # Конфиги pipeline
  data/
    uploads/               # Загруженные датасеты
    workflows.json         # Сохранённые workflow
    model_registry.json    # Реестр моделей
    api_keys.json          # Хешированные API-ключи
    sweeps/                # Результаты HPO
    experiments.json       # Хранилище экспериментов
  prompts/                 # System prompts
  outputs/                 # Результаты обучения (адаптеры, модели, чекпоинты)
  src/pulsar_ai/
    training/              # SFT, DPO тренеры
    evaluation/            # Eval + LLM-as-Judge
    export/                # GGUF, merged, hub
    serving/               # vLLM, llama.cpp
    agent/                 # Агентский фреймворк
    protocols/             # MCP, A2A, Gateway
    guardrails/            # Защитные механизмы
    deployment/            # Canary, A/B testing
    hpo/                   # Optuna sweeps
    pipeline/              # Pipeline executor
    observability/         # Трейсинг
    compute/               # SSH, remote targets
    ui/                    # FastAPI routes, middleware
    cli.py                 # CLI entry point
  ui/                      # React frontend
  scripts/                 # Утилиты (run_eval.py и др.)
  docs/                    # Документация
  .env                     # Переменные окружения (не в git!)
```

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `OPENAI_API_KEY` | — | Ключ для Co-pilot (LLM-режим) и Site Chat |
| `PULSAR_AUTH_ENABLED` | `false` | Включить аутентификацию API |
| `PULSAR_CORS_ORIGINS` | `localhost:3000,8888` | Разрешённые CORS origins |
| `HF_TOKEN` | — | HuggingFace токен (для gated-моделей) |

---

## Troubleshooting

### CUDA Out of Memory
- Уменьшите `batch_size` до 1
- Увеличьте `gradient_accumulation`
- Используйте модель поменьше
- Убедитесь что `load_in_4bit: true`

### Модель не скачивается
- Проверьте интернет-соединение
- Для gated моделей (Llama) нужен `HF_TOKEN`:
  ```bash
  export HF_TOKEN=hf_your_token_here
  ```

### UI не подключается к backend
- Убедитесь что backend запущен на порту 8888
- Проверьте CORS: `PULSAR_CORS_ORIGINS=http://localhost:5173`

### Тренировка зависает
- Проверьте `nvidia-smi` — GPU должен быть загружен
- Проверьте логи backend: `tail -f backend.log`

### Pipeline шаг пропущен
- Проверьте `condition` в конфиге шага — возможно метрика не достигла порога
- Проверьте `depends_on` — все зависимости должны завершиться успешно

### API возвращает 401 Unauthorized
- Проверьте что `PULSAR_AUTH_ENABLED=true` в `.env`
- Убедитесь что передаёте заголовок `Authorization: Bearer pulsar_xxxxx`
- Сгенерируйте новый ключ если старый утерян

### HPO sweep не запускается
- Установите зависимость: `pip install -e ".[hpo]"`
- Проверьте формат `search_space` в sweep конфиге
