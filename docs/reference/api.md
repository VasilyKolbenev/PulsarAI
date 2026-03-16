# REST API Reference

REST API pulsar-ai запускается через `pulsar ui` и доступен по умолчанию на `http://localhost:8888`. Все эндпоинты имеют префикс `/api/v1/`.

!!! info "Swagger UI"
    Интерактивная документация автоматически доступна по адресу `/docs` (Swagger UI)
    и `/redoc` (ReDoc) при запущенном сервере.

!!! tip "Аутентификация"
    Когда `PULSAR_AUTH_ENABLED=true`, все запросы должны содержать заголовок
    `X-API-Key` с валидным ключом. Ключи управляются через эндпоинты Settings.

---

## Health

### GET /api/v1/health

Проверка состояния сервера.

**Ответ** `200 OK`:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 3600
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/health
```

---

## Training

### POST /api/v1/training/start

Запуск задачи обучения.

**Тело запроса:**

```json
{
  "config_path": "configs/experiments/sft.yaml",
  "task": "sft",
  "overrides": {
    "learning_rate": 1e-4,
    "epochs": 5
  }
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `config_path` | string | да | Путь к YAML-конфигу |
| `task` | string | нет | `sft`, `dpo`, `auto` (по умолчанию `auto`) |
| `overrides` | object | нет | Переопределения параметров конфига |

**Ответ** `200 OK`:

```json
{
  "job_id": "job_abc123",
  "status": "running",
  "message": "Training started"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/training/start \
  -H "Content-Type: application/json" \
  -d '{"config_path": "configs/experiments/sft.yaml", "task": "sft"}'
```

### GET /api/v1/training/progress/{job_id}

Получение прогресса обучения в реальном времени через Server-Sent Events (SSE).

| Параметр | Тип | Описание |
|----------|-----|----------|
| `job_id` | string (path) | Идентификатор задачи обучения |

!!! note "SSE-формат"
    Эндпоинт возвращает поток SSE-событий. Каждое событие содержит JSON с метриками.

**Поток SSE:**

```
data: {"step": 10, "loss": 2.34, "learning_rate": 0.0002, "epoch": 0.5}
data: {"step": 20, "loss": 1.87, "learning_rate": 0.0002, "epoch": 1.0}
data: {"status": "completed", "results": {"training_loss": 0.95}}
```

**Пример:**

```bash
curl -N http://localhost:8888/api/v1/training/progress/job_abc123
```

### GET /api/v1/training/jobs

Список всех задач обучения.

**Ответ** `200 OK`:

```json
[
  {
    "job_id": "job_abc123",
    "config_path": "configs/experiments/sft.yaml",
    "status": "completed",
    "started_at": "2026-03-01T10:00:00Z",
    "duration_s": 1234.5
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/training/jobs
```

### GET /api/v1/training/jobs/{job_id}

Детали конкретной задачи обучения.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `job_id` | string (path) | Идентификатор задачи |

**Ответ** `200 OK`:

```json
{
  "job_id": "job_abc123",
  "config_path": "configs/experiments/sft.yaml",
  "status": "completed",
  "started_at": "2026-03-01T10:00:00Z",
  "finished_at": "2026-03-01T10:20:34Z",
  "duration_s": 1234.5,
  "results": {
    "training_loss": 0.95,
    "eval_loss": 1.12
  }
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/training/jobs/job_abc123
```

### DELETE /api/v1/training/jobs/{job_id}

Остановка или удаление задачи обучения.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `job_id` | string (path) | Идентификатор задачи |

**Ответ** `200 OK`:

```json
{
  "status": "cancelled",
  "job_id": "job_abc123"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/training/jobs/job_abc123
```

---

## Datasets

### POST /api/v1/datasets/upload

Загрузка датасета (multipart/form-data).

**Тело запроса** (`multipart/form-data`):

| Поле | Тип | Описание |
|------|-----|----------|
| `file` | file | Файл датасета (CSV, JSONL, JSON, Parquet, XLSX) |

**Ответ** `200 OK`:

```json
{
  "id": "ds_abc123",
  "filename": "customer-intent.csv",
  "rows": 5000,
  "columns": ["text", "intent"],
  "size_mb": 1.2
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/datasets/upload \
  -F "file=@data/customer-intent.csv"
```

### GET /api/v1/datasets

Список загруженных датасетов.

**Ответ** `200 OK`:

```json
[
  {
    "id": "ds_abc123",
    "filename": "customer-intent.csv",
    "rows": 5000,
    "size_mb": 1.2,
    "uploaded_at": "2026-03-01T10:00:00Z"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/datasets
```

### GET /api/v1/datasets/{id}/preview

Предпросмотр первых строк датасета.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID датасета |

**Ответ** `200 OK`:

```json
{
  "columns": ["text", "intent"],
  "rows": [
    {"text": "Как отменить заказ?", "intent": "cancel_order"},
    {"text": "Статус доставки", "intent": "delivery_status"}
  ],
  "total_rows": 5000
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/datasets/ds_abc123/preview
```

### DELETE /api/v1/datasets/{id}

Удаление датасета.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID датасета |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "id": "ds_abc123"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/datasets/ds_abc123
```

---

## Experiments

### GET /api/v1/experiments

Список экспериментов.

**Ответ** `200 OK`:

```json
[
  {
    "id": "exp_001",
    "name": "customer-intent-sft",
    "status": "completed",
    "created_at": "2026-03-01T10:00:00Z",
    "metrics": {"training_loss": 0.95}
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/experiments
```

### GET /api/v1/experiments/{id}

Детали эксперимента.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID эксперимента |

**Ответ** `200 OK`:

```json
{
  "id": "exp_001",
  "name": "customer-intent-sft",
  "status": "completed",
  "config": {},
  "metrics": {"training_loss": 0.95},
  "created_at": "2026-03-01T10:00:00Z"
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/experiments/exp_001
```

### PUT /api/v1/experiments/{id}

Обновление метаданных эксперимента.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID эксперимента |

**Тело запроса:**

```json
{
  "name": "customer-intent-sft-v2",
  "notes": "Увеличен learning rate"
}
```

**Ответ** `200 OK`:

```json
{
  "id": "exp_001",
  "name": "customer-intent-sft-v2",
  "notes": "Увеличен learning rate"
}
```

**Пример:**

```bash
curl -X PUT http://localhost:8888/api/v1/experiments/exp_001 \
  -H "Content-Type: application/json" \
  -d '{"name": "customer-intent-sft-v2"}'
```

### DELETE /api/v1/experiments/{id}

Удаление эксперимента.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID эксперимента |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "id": "exp_001"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/experiments/exp_001
```

---

## Evaluation

### POST /api/v1/evaluation/run

Запуск оценки модели.

**Тело запроса:**

```json
{
  "model_path": "./outputs/cam-sft/lora",
  "test_data_path": "data/test.csv",
  "batch_size": 8
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `model_path` | string | да | Путь к модели/адаптеру |
| `test_data_path` | string | да | Путь к тестовым данным |
| `batch_size` | int | нет | Размер батча (по умолчанию `8`) |

**Ответ** `200 OK`:

```json
{
  "id": "eval_abc123",
  "status": "running"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{"model_path": "./outputs/sft/lora", "test_data_path": "data/test.csv"}'
```

### GET /api/v1/evaluation/{id}

Результаты оценки.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID задачи оценки |

**Ответ** `200 OK`:

```json
{
  "id": "eval_abc123",
  "status": "completed",
  "metrics": {
    "accuracy": 0.92,
    "f1": 0.89,
    "precision": 0.91,
    "recall": 0.87
  }
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/evaluation/eval_abc123
```

---

## Export

### POST /api/v1/export

Экспорт модели в продакшен-формат.

**Тело запроса:**

```json
{
  "model_path": "./outputs/cam-sft/lora",
  "format": "gguf",
  "quantization": "q4_k_m",
  "output_path": "./exports/"
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `model_path` | string | да | Путь к модели/адаптеру |
| `format` | string | нет | `gguf`, `merged`, `hub` (по умолчанию `gguf`) |
| `quantization` | string | нет | `q4_k_m`, `q8_0`, `f16` (по умолчанию `q4_k_m`) |
| `output_path` | string | нет | Путь для результата |

**Ответ** `200 OK`:

```json
{
  "status": "completed",
  "output_path": "./exports/model-q4_k_m.gguf",
  "size_mb": 1800
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/export \
  -H "Content-Type: application/json" \
  -d '{"model_path": "./outputs/sft/lora", "format": "gguf"}'
```

---

## Hardware

### GET /api/v1/hardware

Информация об оборудовании сервера.

**Ответ** `200 OK`:

```json
{
  "num_gpus": 1,
  "gpu_name": "NVIDIA RTX 4090",
  "vram_per_gpu_gb": 24.0,
  "total_vram_gb": 24.0,
  "compute_capability": [8, 9],
  "bf16_supported": true,
  "strategy": "unsloth",
  "recommended_batch_size": 4,
  "recommended_gradient_accumulation": 4
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/hardware
```

---

## Metrics

### GET /api/v1/metrics/live

Метрики обучения в реальном времени (SSE).

!!! note "Server-Sent Events"
    Эндпоинт возвращает поток SSE-событий с метриками текущего обучения.

**Поток SSE:**

```
data: {"step": 42, "loss": 1.23, "lr": 0.0002, "epoch": 1.5, "gpu_util": 95}
```

**Пример:**

```bash
curl -N http://localhost:8888/api/v1/metrics/live
```

### GET /api/v1/metrics/snapshot

Снимок текущих метрик (не SSE).

**Ответ** `200 OK`:

```json
{
  "active_job": "job_abc123",
  "step": 42,
  "loss": 1.23,
  "learning_rate": 0.0002,
  "epoch": 1.5,
  "gpu_utilization": 95,
  "vram_used_gb": 18.2
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/metrics/snapshot
```

---

## Serving

### GET /api/v1/serving/metrics

Метрики сервинга (latency, throughput, errors).

**Ответ** `200 OK`:

```json
{
  "total_requests": 1500,
  "avg_latency_ms": 120,
  "p95_latency_ms": 250,
  "errors": 3,
  "tokens_per_second": 45.2
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/serving/metrics
```

### POST /api/v1/serving/metrics/reset

Сброс счётчиков метрик сервинга.

**Ответ** `200 OK`:

```json
{
  "status": "reset"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/serving/metrics/reset
```

---

## Workflows

### GET /api/v1/workflows

Список workflow.

**Ответ** `200 OK`:

```json
[
  {
    "id": "wf_001",
    "name": "Train and Export",
    "steps": 3,
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/workflows
```

### POST /api/v1/workflows

Создание нового workflow.

**Тело запроса:**

```json
{
  "name": "Train and Export",
  "steps": [
    {"type": "train", "config_path": "configs/experiments/sft.yaml"},
    {"type": "eval", "test_data": "data/test.csv"},
    {"type": "export", "format": "gguf"}
  ]
}
```

**Ответ** `201 Created`:

```json
{
  "id": "wf_002",
  "name": "Train and Export",
  "steps": 3
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Train and Export", "steps": [{"type": "train", "config_path": "configs/experiments/sft.yaml"}]}'
```

### GET /api/v1/workflows/{id}

Детали workflow.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID workflow |

**Ответ** `200 OK`:

```json
{
  "id": "wf_001",
  "name": "Train and Export",
  "steps": [
    {"type": "train", "status": "completed"},
    {"type": "eval", "status": "running"},
    {"type": "export", "status": "pending"}
  ]
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/workflows/wf_001
```

### DELETE /api/v1/workflows/{id}

Удаление workflow.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID workflow |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "id": "wf_001"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/workflows/wf_001
```

### POST /api/v1/workflows/{id}/run

Запуск workflow.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID workflow |

**Ответ** `200 OK`:

```json
{
  "id": "wf_001",
  "status": "running",
  "run_id": "wfr_abc123"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/workflows/wf_001/run
```

### GET /api/v1/workflows/{id}/config

Получение конфигурации workflow.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID workflow |

**Ответ** `200 OK`:

```json
{
  "id": "wf_001",
  "name": "Train and Export",
  "config": {
    "steps": [
      {"type": "train", "config_path": "configs/experiments/sft.yaml"},
      {"type": "eval", "test_data": "data/test.csv"},
      {"type": "export", "format": "gguf"}
    ]
  }
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/workflows/wf_001/config
```

---

## Prompts

### GET /api/v1/prompts

Список промптов.

**Ответ** `200 OK`:

```json
[
  {
    "id": "pmt_001",
    "name": "intent-classifier",
    "version": 3,
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/prompts
```

### POST /api/v1/prompts

Создание нового промпта.

**Тело запроса:**

```json
{
  "name": "intent-classifier",
  "content": "Classify the user message into one of the following intents: ...",
  "metadata": {"task": "classification"}
}
```

**Ответ** `201 Created`:

```json
{
  "id": "pmt_002",
  "name": "intent-classifier",
  "version": 1
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{"name": "intent-classifier", "content": "Classify the user message..."}'
```

### GET /api/v1/prompts/{id}

Получение промпта по ID.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |

**Ответ** `200 OK`:

```json
{
  "id": "pmt_001",
  "name": "intent-classifier",
  "content": "Classify the user message...",
  "version": 3,
  "metadata": {"task": "classification"}
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/prompts/pmt_001
```

### PUT /api/v1/prompts/{id}

Обновление промпта (создаёт новую версию).

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |

**Тело запроса:**

```json
{
  "content": "Updated prompt content...",
  "metadata": {"task": "classification", "updated": true}
}
```

**Ответ** `200 OK`:

```json
{
  "id": "pmt_001",
  "version": 4
}
```

**Пример:**

```bash
curl -X PUT http://localhost:8888/api/v1/prompts/pmt_001 \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated prompt content..."}'
```

### DELETE /api/v1/prompts/{id}

Удаление промпта.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "id": "pmt_001"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/prompts/pmt_001
```

### POST /api/v1/prompts/{id}/versions

Создание новой версии промпта.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |

**Тело запроса:**

```json
{
  "content": "New version of the prompt...",
  "changelog": "Added few-shot examples"
}
```

**Ответ** `201 Created`:

```json
{
  "id": "pmt_001",
  "version": 5,
  "changelog": "Added few-shot examples"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/prompts/pmt_001/versions \
  -H "Content-Type: application/json" \
  -d '{"content": "New version...", "changelog": "Added few-shot examples"}'
```

### GET /api/v1/prompts/{id}/versions/{v}

Получение конкретной версии промпта.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |
| `v` | int (path) | Номер версии |

**Ответ** `200 OK`:

```json
{
  "id": "pmt_001",
  "version": 2,
  "content": "Prompt content at version 2...",
  "created_at": "2026-02-15T10:00:00Z"
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/prompts/pmt_001/versions/2
```

### GET /api/v1/prompts/{id}/diff

Diff между версиями промпта.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |

**Query-параметры:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `v1` | int | предпоследняя | Первая версия |
| `v2` | int | последняя | Вторая версия |

**Ответ** `200 OK`:

```json
{
  "v1": 2,
  "v2": 3,
  "diff": "--- v2\n+++ v3\n@@ -1,3 +1,5 @@\n Classify the user message...\n+Use the following examples:\n+..."
}
```

**Пример:**

```bash
curl "http://localhost:8888/api/v1/prompts/pmt_001/diff?v1=2&v2=3"
```

### POST /api/v1/prompts/{id}/test

Тестирование промпта с входными данными.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID промпта |

**Тело запроса:**

```json
{
  "input": "Как отменить заказ?",
  "model_path": "./outputs/sft/lora"
}
```

**Ответ** `200 OK`:

```json
{
  "output": "cancel_order",
  "latency_ms": 120,
  "tokens_used": 45
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/prompts/pmt_001/test \
  -H "Content-Type: application/json" \
  -d '{"input": "Как отменить заказ?", "model_path": "./outputs/sft/lora"}'
```

---

## Runs

### GET /api/v1/runs

Список запусков экспериментов.

**Query-параметры:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `project` | string | -- | Фильтр по проекту |
| `status` | string | -- | Фильтр по статусу |
| `limit` | int | `20` | Лимит записей |

**Ответ** `200 OK`:

```json
[
  {
    "run_id": "run_abc123",
    "name": "customer-intent-sft",
    "status": "completed",
    "duration_s": 1234.5,
    "results": {"training_loss": 0.95}
  }
]
```

**Пример:**

```bash
curl "http://localhost:8888/api/v1/runs?status=completed&limit=10"
```

### GET /api/v1/runs/{id}

Детали запуска.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID запуска |

**Ответ** `200 OK`:

```json
{
  "run_id": "run_abc123",
  "name": "customer-intent-sft",
  "status": "completed",
  "config": {},
  "results": {"training_loss": 0.95},
  "environment": {"gpu": "RTX 4090", "python": "3.11"}
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/runs/run_abc123
```

### POST /api/v1/runs/compare

Сравнение нескольких запусков.

**Тело запроса:**

```json
{
  "run_ids": ["run_abc123", "run_def456"]
}
```

**Ответ** `200 OK`:

```json
{
  "run_names": ["sft-v1", "sft-v2"],
  "config_diff": {
    "learning_rate": [0.0002, 0.0001],
    "epochs": [3, 5]
  },
  "metrics_comparison": {
    "training_loss": [0.95, 0.82],
    "eval_accuracy": [0.89, 0.93]
  }
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/runs/compare \
  -H "Content-Type: application/json" \
  -d '{"run_ids": ["run_abc123", "run_def456"]}'
```

---

## Registry

### GET /api/v1/registry

Список моделей в реестре.

**Query-параметры:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `name` | string | -- | Фильтр по имени |
| `status` | string | -- | Фильтр по статусу |

**Ответ** `200 OK`:

```json
[
  {
    "id": "mdl_001",
    "name": "customer-intent",
    "version": 2,
    "status": "production",
    "base_model": "qwen2.5-3b",
    "task": "sft"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/registry
```

### POST /api/v1/registry

Регистрация новой модели.

**Тело запроса:**

```json
{
  "name": "customer-intent",
  "model_path": "./outputs/sft/lora",
  "task": "sft",
  "base_model": "qwen2.5-3b",
  "tags": ["v1", "production-ready"]
}
```

**Ответ** `201 Created`:

```json
{
  "id": "mdl_002",
  "name": "customer-intent",
  "version": 1,
  "status": "registered"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/registry \
  -H "Content-Type: application/json" \
  -d '{"name": "customer-intent", "model_path": "./outputs/sft/lora", "base_model": "qwen2.5-3b"}'
```

### GET /api/v1/registry/{id}

Детали модели.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID модели |

**Ответ** `200 OK`:

```json
{
  "id": "mdl_001",
  "name": "customer-intent",
  "version": 2,
  "status": "production",
  "model_path": "./outputs/sft/lora",
  "base_model": "qwen2.5-3b",
  "metrics": {"accuracy": 0.92},
  "tags": ["v2"],
  "created_at": "2026-03-01T10:00:00Z"
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/registry/mdl_001
```

### PUT /api/v1/registry/{id}/status

Обновление статуса модели.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID модели |

**Тело запроса:**

```json
{
  "status": "production"
}
```

**Ответ** `200 OK`:

```json
{
  "id": "mdl_001",
  "status": "production"
}
```

**Пример:**

```bash
curl -X PUT http://localhost:8888/api/v1/registry/mdl_001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "production"}'
```

### PUT /api/v1/registry/{id}/metrics

Обновление метрик модели.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID модели |

**Тело запроса:**

```json
{
  "accuracy": 0.93,
  "f1": 0.91,
  "latency_ms": 85
}
```

**Ответ** `200 OK`:

```json
{
  "id": "mdl_001",
  "metrics": {"accuracy": 0.93, "f1": 0.91, "latency_ms": 85}
}
```

**Пример:**

```bash
curl -X PUT http://localhost:8888/api/v1/registry/mdl_001/metrics \
  -H "Content-Type: application/json" \
  -d '{"accuracy": 0.93, "f1": 0.91}'
```

### DELETE /api/v1/registry/{id}

Удаление модели из реестра.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID модели |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "id": "mdl_001"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/registry/mdl_001
```

### POST /api/v1/registry/compare

Сравнение моделей.

**Тело запроса:**

```json
{
  "model_ids": ["mdl_001", "mdl_002"]
}
```

**Ответ** `200 OK`:

```json
{
  "models": [
    {"id": "mdl_001", "name": "intent-v1", "metrics": {"accuracy": 0.89}},
    {"id": "mdl_002", "name": "intent-v2", "metrics": {"accuracy": 0.93}}
  ],
  "diff": {
    "accuracy": [0.89, 0.93],
    "f1": [0.85, 0.91]
  }
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/registry/compare \
  -H "Content-Type: application/json" \
  -d '{"model_ids": ["mdl_001", "mdl_002"]}'
```

---

## Compute

### GET /api/v1/compute/targets

Список compute-целей (GPU-серверы, облачные инстансы).

**Ответ** `200 OK`:

```json
[
  {
    "id": "ct_001",
    "name": "local-gpu",
    "type": "local",
    "status": "online",
    "gpu": "RTX 4090"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/compute/targets
```

### POST /api/v1/compute/targets

Добавление compute-цели.

**Тело запроса:**

```json
{
  "name": "remote-a100",
  "type": "ssh",
  "host": "gpu-server.example.com",
  "port": 22,
  "username": "user"
}
```

**Ответ** `201 Created`:

```json
{
  "id": "ct_002",
  "name": "remote-a100",
  "status": "pending"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/compute/targets \
  -H "Content-Type: application/json" \
  -d '{"name": "remote-a100", "type": "ssh", "host": "gpu-server.example.com"}'
```

### DELETE /api/v1/compute/targets/{id}

Удаление compute-цели.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID compute-цели |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "id": "ct_002"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/compute/targets/ct_002
```

### POST /api/v1/compute/targets/{id}/test

Тестирование подключения к compute-цели.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID compute-цели |

**Ответ** `200 OK`:

```json
{
  "id": "ct_001",
  "status": "online",
  "latency_ms": 12,
  "gpu_available": true
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/compute/targets/ct_001/test
```

### POST /api/v1/compute/targets/{id}/detect

Автоматическое определение GPU на compute-цели.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `id` | string (path) | ID compute-цели |

**Ответ** `200 OK`:

```json
{
  "id": "ct_001",
  "gpus": [
    {"name": "NVIDIA A100", "vram_gb": 80, "compute_capability": "8.0"}
  ]
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/compute/targets/ct_001/detect
```

---

## Settings

### GET /api/v1/settings

Получение текущих настроек.

**Ответ** `200 OK`:

```json
{
  "auth_enabled": false,
  "cors_origins": ["http://localhost:3000", "http://localhost:8888"],
  "default_strategy": "auto"
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/settings
```

### GET /api/v1/settings/keys

Список API-ключей (только имена, не значения).

**Ответ** `200 OK`:

```json
[
  {
    "name": "default",
    "created_at": "2026-03-01T10:00:00Z",
    "last_used": "2026-03-03T14:30:00Z"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/settings/keys
```

### POST /api/v1/settings/keys

Создание нового API-ключа.

**Тело запроса:**

```json
{
  "name": "ci-pipeline"
}
```

**Ответ** `201 Created`:

```json
{
  "name": "ci-pipeline",
  "key": "pulsar_key_xxxxxxxxxxxx",
  "created_at": "2026-03-03T15:00:00Z"
}
```

!!! warning "Сохраните ключ"
    Значение ключа отображается только при создании.
    Сохраните его сразу -- повторно получить нельзя.

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/settings/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "ci-pipeline"}'
```

### DELETE /api/v1/settings/keys/{name}

Удаление API-ключа.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `name` | string (path) | Имя ключа |

**Ответ** `200 OK`:

```json
{
  "status": "deleted",
  "name": "ci-pipeline"
}
```

**Пример:**

```bash
curl -X DELETE http://localhost:8888/api/v1/settings/keys/ci-pipeline
```

---

## Protocols

### GET /api/v1/protocols/mcp/status

Статус MCP (Model Context Protocol).

**Ответ** `200 OK`:

```json
{
  "enabled": true,
  "connected_clients": 2,
  "tools_registered": 5
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/protocols/mcp/status
```

### POST /api/v1/protocols/mcp/configure

Настройка MCP-сервера.

**Тело запроса:**

```json
{
  "enabled": true,
  "tools": ["train", "eval", "export"],
  "auth_required": true
}
```

**Ответ** `200 OK`:

```json
{
  "status": "configured",
  "tools_registered": 3
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/protocols/mcp/configure \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "tools": ["train", "eval", "export"]}'
```

### GET /api/v1/protocols/a2a/agent-card

Получение Agent Card (Agent-to-Agent protocol).

**Ответ** `200 OK`:

```json
{
  "name": "pulsar-ai",
  "description": "Universal LLM Fine-tuning Pipeline",
  "capabilities": ["train", "eval", "export", "serve"],
  "endpoint": "http://localhost:8888/api/v1/protocols/a2a"
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/protocols/a2a/agent-card
```

### POST /api/v1/protocols/a2a/configure

Настройка A2A-протокола.

**Тело запроса:**

```json
{
  "enabled": true,
  "capabilities": ["train", "eval"]
}
```

**Ответ** `200 OK`:

```json
{
  "status": "configured"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/protocols/a2a/configure \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### GET /api/v1/protocols/gateway/status

Статус API Gateway.

**Ответ** `200 OK`:

```json
{
  "enabled": false,
  "routes": 0
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/protocols/gateway/status
```

### POST /api/v1/protocols/gateway/configure

Настройка API Gateway.

**Тело запроса:**

```json
{
  "enabled": true,
  "routes": [
    {"path": "/v1/chat/completions", "target": "http://localhost:8080"}
  ]
}
```

**Ответ** `200 OK`:

```json
{
  "status": "configured",
  "routes": 1
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/protocols/gateway/configure \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "routes": [{"path": "/v1/chat/completions", "target": "http://localhost:8080"}]}'
```

### GET /api/v1/protocols/summary

Сводка состояния всех протоколов.

**Ответ** `200 OK`:

```json
{
  "mcp": {"enabled": true, "tools": 5},
  "a2a": {"enabled": false},
  "gateway": {"enabled": false, "routes": 0}
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/protocols/summary
```

---

## Pipeline

### WebSocket /api/v1/pipeline/run

Запуск пайплайна с потоковой передачей прогресса через WebSocket.

!!! note "WebSocket-протокол"
    Подключение через `ws://localhost:8888/api/v1/pipeline/run`.
    Клиент отправляет конфиг, сервер стримит прогресс.

**Отправка:**

```json
{
  "config_path": "configs/pipelines/example.yaml"
}
```

**Получение (поток):**

```json
{"step": "train", "status": "running", "progress": 0.45}
{"step": "train", "status": "completed"}
{"step": "eval", "status": "running", "progress": 0.10}
```

### POST /api/v1/pipeline/run/sync

Синхронный запуск пайплайна (ждёт завершения).

**Тело запроса:**

```json
{
  "config_path": "configs/pipelines/example.yaml"
}
```

**Ответ** `200 OK`:

```json
{
  "status": "completed",
  "steps": {
    "train": {"status": "completed", "duration_s": 1200},
    "eval": {"status": "completed", "duration_s": 60},
    "export": {"status": "completed", "duration_s": 300}
  }
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/pipeline/run/sync \
  -H "Content-Type: application/json" \
  -d '{"config_path": "configs/pipelines/example.yaml"}'
```

### GET /api/v1/pipeline/runs

Список запусков пайплайнов.

**Ответ** `200 OK`:

```json
[
  {
    "run_id": "plr_abc123",
    "pipeline": "train-eval-export",
    "status": "completed",
    "started_at": "2026-03-01T10:00:00Z"
  }
]
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/pipeline/runs
```

---

## Assistant

### POST /api/v1/assistant/chat

Отправка сообщения Co-pilot ассистенту.

!!! tip "Требования"
    Требуется установленная переменная `OPENAI_API_KEY`.

**Тело запроса:**

```json
{
  "message": "Какой learning rate лучше для QLoRA?",
  "context": {
    "current_config": "configs/experiments/sft.yaml"
  }
}
```

**Ответ** `200 OK`:

```json
{
  "response": "Для QLoRA рекомендуется learning rate в диапазоне 1e-4 -- 5e-4...",
  "tool_calls": [],
  "tokens_used": 250
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Какой learning rate лучше для QLoRA?"}'
```

### GET /api/v1/assistant/status

Статус Co-pilot ассистента.

**Ответ** `200 OK`:

```json
{
  "available": true,
  "model": "gpt-4o-mini",
  "tools_count": 14
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/assistant/status
```

---

## Site Chat

### POST /api/v1/site/chat

Чат на лендинге (публичный, без аутентификации).

**Тело запроса:**

```json
{
  "message": "Что такое pulsar-ai?",
  "session_id": "sess_xyz"
}
```

**Ответ** `200 OK`:

```json
{
  "response": "pulsar-ai -- это платформа для файнтюнинга LLM...",
  "session_id": "sess_xyz"
}
```

**Пример:**

```bash
curl -X POST http://localhost:8888/api/v1/site/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Что такое pulsar-ai?"}'
```

### GET /api/v1/site/chat/status

Статус чата лендинга.

**Ответ** `200 OK`:

```json
{
  "available": true,
  "active_sessions": 3
}
```

**Пример:**

```bash
curl http://localhost:8888/api/v1/site/chat/status
```
