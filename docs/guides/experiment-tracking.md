# Experiment Tracking

Отслеживание экспериментов позволяет фиксировать конфигурации, метрики и результаты
каждого запуска обучения. Pulsar AI предоставляет встроенный трекер, а также интеграции
с ClearML и Weights & Biases.

---

## Встроенный трекинг

Все эксперименты автоматически сохраняются в `data/experiments.json`. Каждый запуск
фиксирует полную конфигурацию, метрики по эпохам и итоговые результаты.

```json
{
  "id": "exp_20260301_143052",
  "name": "sft-llama3-v1",
  "status": "completed",
  "config": {
    "model": "meta-llama/Llama-3-8B",
    "learning_rate": 2e-4,
    "epochs": 3,
    "batch_size": 8
  },
  "metrics": {
    "train_loss": [1.45, 0.98, 0.72],
    "eval_loss": [1.38, 0.91, 0.69],
    "eval_accuracy": [0.61, 0.74, 0.82]
  },
  "started_at": "2026-03-01T14:30:52",
  "completed_at": "2026-03-01T16:45:10"
}
```

---

## CLI-команды

=== "Список экспериментов"

    ```bash
    # Все эксперименты
    pulsar runs list

    # С фильтрацией по статусу
    pulsar runs list --status completed

    # Последние 5
    pulsar runs list --limit 5
    ```

=== "Детали эксперимента"

    ```bash
    pulsar runs show exp_20260301_143052
    ```

=== "Сравнение экспериментов"

    ```bash
    pulsar runs compare exp_20260301_143052 exp_20260302_091015
    ```

    Вывод:

    ```
    ┌─────────────────────┬──────────────────────┬──────────────────────┐
    │ Parameter           │ exp_20260301_143052  │ exp_20260302_091015  │
    ├─────────────────────┼──────────────────────┼──────────────────────┤
    │ model               │ Llama-3-8B           │ Llama-3-8B           │
    │ learning_rate       │ 2e-4                 │ 5e-5                 │
    │ epochs              │ 3                    │ 5                    │
    │ eval_loss (final)   │ 0.69                 │ 0.58                 │
    │ eval_accuracy       │ 0.82                 │ 0.87                 │
    └─────────────────────┴──────────────────────┴──────────────────────┘
    ```

---

## API

### Список экспериментов

```bash
curl http://localhost:8000/runs
```

### Детали эксперимента

```bash
curl http://localhost:8000/runs/exp_20260301_143052
```

### Сравнение экспериментов

```bash
curl -X POST http://localhost:8000/runs/compare \
  -H "Content-Type: application/json" \
  -d '{
    "run_ids": ["exp_20260301_143052", "exp_20260302_091015"],
    "metrics": ["eval_loss", "eval_accuracy"]
  }'
```

Ответ:

```json
{
  "runs": [
    {
      "id": "exp_20260301_143052",
      "config_diff": {"learning_rate": 2e-4, "epochs": 3},
      "metrics": {"eval_loss": 0.69, "eval_accuracy": 0.82}
    },
    {
      "id": "exp_20260302_091015",
      "config_diff": {"learning_rate": 5e-5, "epochs": 5},
      "metrics": {"eval_loss": 0.58, "eval_accuracy": 0.87}
    }
  ],
  "config_differences": ["learning_rate", "epochs"],
  "best_run": {
    "by_eval_loss": "exp_20260302_091015",
    "by_eval_accuracy": "exp_20260302_091015"
  }
}
```

!!! info "Config Diff"
    При сравнении система автоматически выделяет только различающиеся параметры
    конфигурации, что упрощает анализ влияния каждого изменения.

---

## Интеграция с ClearML

[ClearML](https://clear.ml/) -- open-source платформа для ML-экспериментов с веб-интерфейсом.

### Установка

```bash
pip install -e ".[tracking-clearml]"
```

### Настройка

Задайте переменные окружения:

```bash
export CLEARML_WEB_HOST=https://app.clear.ml
export CLEARML_API_HOST=https://api.clear.ml
export CLEARML_FILES_HOST=https://files.clear.ml
export CLEARML_API_ACCESS_KEY=your_access_key
export CLEARML_API_SECRET_KEY=your_secret_key
```

Или создайте файл `~/clearml.conf` через:

```bash
clearml-init
```

### Использование

Добавьте трекер в конфигурацию обучения:

```yaml
tracking:
  backend: clearml
  project: "Pulsar AI"
  task_name: "sft-llama3-experiment"
```

!!! tip "ClearML Dashboard"
    После запуска обучения метрики появятся в ClearML Web UI. Можно сравнивать
    эксперименты, просматривать графики и скачивать артефакты.

---

## Интеграция с Weights & Biases

[W&B](https://wandb.ai/) -- популярная платформа для трекинга ML-экспериментов.

### Установка

```bash
pip install -e ".[tracking-wandb]"
```

### Настройка

```bash
export WANDB_API_KEY=your_api_key
export WANDB_PROJECT=pulsar-ai     # опционально
export WANDB_ENTITY=your-team      # опционально
```

Или авторизуйтесь интерактивно:

```bash
wandb login
```

### Использование

```yaml
tracking:
  backend: wandb
  project: "pulsar-ai"
  run_name: "sft-llama3-v2"
  tags: ["sft", "llama3", "production"]
```

!!! warning "Приватность"
    W&B по умолчанию отправляет данные в облако. Для чувствительных данных
    используйте [W&B Server](https://docs.wandb.ai/guides/hosting) (self-hosted)
    или параметр `WANDB_MODE=offline` для локального логирования.

---

## Сравнение бэкендов

| Возможность           | Встроенный     | ClearML         | W&B              |
|-----------------------|---------------|-----------------|-------------------|
| Установка             | Включён       | `.[tracking-clearml]` | `.[tracking-wandb]` |
| Хранение              | Локальный JSON | Сервер ClearML  | Облако / self-host |
| Веб-интерфейс         | Pulsar UI      | ClearML UI      | W&B Dashboard     |
| Сравнение экспериментов| CLI + API    | Есть            | Есть              |
| Артефакты             | Нет           | Есть            | Есть              |
| Командная работа      | Нет           | Есть            | Есть              |
| Стоимость             | Бесплатно     | Open-source     | Бесплатный тир    |
