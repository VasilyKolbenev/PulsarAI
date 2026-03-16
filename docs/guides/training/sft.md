# SFT (Supervised Fine-Tuning)

## Что такое SFT

Supervised Fine-Tuning (SFT) -- основной метод дообучения языковых моделей на размеченных данных. Модель учится генерировать ожидаемые ответы на заданные инструкции, используя пары "вход-выход" из вашего датасета. В pulsar-ai SFT поддерживает два бэкенда: **Unsloth** (ускорение до 5x на одном GPU) и **HuggingFace SFTTrainer** (мульти-GPU через Accelerate/FSDP).

---

## Структура конфига

Полный YAML-конфиг для SFT-эксперимента:

```yaml
# configs/experiments/my-classifier.yaml

# Наследование: base → модель → (стратегия определяется автоматически)
inherit:
  - base                    # базовые дефолты (lr, epochs, seed, ...)
  - models/qwen3.5-0.8b    # параметры конкретной модели

task: sft                   # тип задачи: sft или dpo

# ── Датасет ──────────────────────────────────────────────
dataset:
  path: data/my_dataset.csv           # путь к файлу данных
  format: csv                         # csv | jsonl | parquet | excel
  text_column: text                   # колонка с входным текстом
  label_columns:                      # колонки с метками (ответами)
    - label
  system_prompt_file: prompts/sys.txt # файл с системным промптом
  test_size: 0.15                     # доля тестовой выборки (15%)
  output_format: json                 # формат ответа модели

# ── Параметры обучения ───────────────────────────────────
training:
  epochs: 3                    # количество эпох
  learning_rate: 2e-4          # скорость обучения
  batch_size: 1                # размер батча на GPU
  gradient_accumulation: 16    # шаги аккумуляции градиентов
  max_seq_length: 512          # максимальная длина последовательности
  warmup_steps: 10             # шаги разогрева LR
  logging_steps: 20            # логирование каждые N шагов
  save_steps: 200              # сохранение чекпоинта каждые N шагов
  save_total_limit: 2          # максимум хранимых чекпоинтов
  optimizer: adamw_8bit        # оптимизатор
  seed: 42                     # seed для воспроизводимости
  packing: true                # упаковка коротких примеров в одну последовательность

# ── LoRA параметры ───────────────────────────────────────
lora:
  r: 16                        # ранг LoRA (размерность адаптера)
  lora_alpha: 32               # масштабирование LoRA
  lora_dropout: 0              # dropout в LoRA слоях
  target_modules:              # целевые модули для адаптации
    - q_proj
    - k_proj
    - v_proj
    - o_proj
    - gate_proj
    - up_proj
    - down_proj
  bias: none                   # адаптация bias: none | all | lora_only

# ── Стратегия (auto = определяется по железу) ────────────
strategy: auto

# ── Выходные данные ──────────────────────────────────────
output:
  dir: ./outputs/my-classifier  # директория для результатов
  save_adapter: true            # сохранять LoRA адаптер
  export_gguf: true             # экспортировать в GGUF после обучения
  quantization: q4_k_m          # квантизация для GGUF

# ── Логирование ──────────────────────────────────────────
logging:
  level: INFO
  report_to: none              # none | wandb | tensorboard
```

---

## Ключевые параметры

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `training.epochs` | int | `3` | Количество эпох обучения |
| `training.learning_rate` | float | `2e-4` | Скорость обучения (LR). Для QLoRA обычно 1e-4 -- 5e-4 |
| `training.batch_size` | int | `1` | Размер батча на одном GPU |
| `training.gradient_accumulation` | int | `16` | Шаги аккумуляции. Эффективный батч = batch_size x grad_accum |
| `training.max_seq_length` | int | `512` | Макс. длина токенизированной последовательности |
| `lora.r` | int | `16` | Ранг LoRA. Больше = больше параметров = лучше качество, но больше VRAM |
| `lora.lora_alpha` | int | `32` | Масштабирование. Обычно `lora_alpha = 2 * r` |
| `training.optimizer` | str | `adamw_8bit` | Оптимизатор. `adamw_8bit` экономит VRAM |
| `training.packing` | bool | `true` | Упаковка коротких примеров для ускорения |
| `training.warmup_steps` | int | `10` | Шаги линейного разогрева LR |

---

## Запуск обучения

=== "CLI"

    ```bash
    # Базовый запуск
    pulsar train configs/experiments/my-classifier.yaml

    # С переопределением параметров
    pulsar train configs/experiments/my-classifier.yaml learning_rate=1e-4 epochs=5

    # Указание задачи явно
    pulsar train configs/experiments/my-classifier.yaml --task sft
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8888/api/training/start \
      -H "Content-Type: application/json" \
      -d '{
        "config_path": "configs/experiments/my-classifier.yaml",
        "overrides": {
          "training.learning_rate": 1e-4,
          "training.epochs": 5
        }
      }'
    ```

    Ответ:

    ```json
    {
      "job_id": "abc123",
      "status": "running",
      "config": { "..." }
    }
    ```

=== "UI"

    1. Откройте **Experiments** в Web UI (`pulsar ui`)
    2. Нажмите **New Experiment**
    3. Выберите модель, загрузите датасет, настройте параметры
    4. Нажмите **Start Training**
    5. Следите за прогрессом в реальном времени на странице эксперимента

---

## Прогресс в реальном времени (SSE)

Во время обучения через API доступен Server-Sent Events (SSE) поток с метриками:

```bash
curl -N http://localhost:8888/api/training/progress/abc123
```

Формат событий:

```
data: {"step": 20, "loss": 1.234, "learning_rate": 0.0002, "epoch": 0.5}
data: {"step": 40, "loss": 0.891, "learning_rate": 0.0002, "epoch": 1.0}
data: {"step": 60, "loss": 0.456, "learning_rate": 0.00015, "epoch": 1.5}
```

В Web UI график loss обновляется автоматически.

---

## Чекпоинты и возобновление обучения

pulsar-ai автоматически сохраняет чекпоинты каждые `save_steps` шагов (по умолчанию 200). Для возобновления прерванного обучения используйте флаг `--resume`:

=== "CLI"

    ```bash
    pulsar train configs/experiments/my-classifier.yaml \
      --resume ./outputs/my-classifier/checkpoint-400
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8888/api/training/start \
      -H "Content-Type: application/json" \
      -d '{
        "config_path": "configs/experiments/my-classifier.yaml",
        "resume_from_checkpoint": "./outputs/my-classifier/checkpoint-400"
      }'
    ```

!!! note "Ограничение чекпоинтов"
    Параметр `save_total_limit: 2` ограничивает количество хранимых чекпоинтов. Старые чекпоинты удаляются автоматически. Увеличьте, если хотите хранить больше.

---

## Распространённые проблемы

!!! warning "Out of Memory (OOM)"
    Если обучение падает с ошибкой CUDA Out of Memory:

    - Уменьшите `batch_size` до **1**
    - Уменьшите `max_seq_length` (например, 256 вместо 512)
    - Уменьшите `lora.r` (8 вместо 16)
    - Включите `gradient_checkpointing: true`
    - Используйте `load_in_4bit: true` (QLoRA)
    - Переключитесь на меньшую модель (0.8B вместо 2B)

!!! warning "NaN Loss"
    Если loss становится `NaN` во время обучения:

    - Уменьшите `learning_rate` (попробуйте 5e-5 или 1e-5)
    - Увеличьте `warmup_steps` (20-50)
    - Проверьте данные: нет ли пустых строк или невалидных символов
    - Убедитесь, что `bf16: true` поддерживается вашим GPU (Ampere+)
    - Попробуйте `fp16` вместо `bf16` на старых GPU

---

## Рекомендуемые параметры по размеру модели

!!! tip "Рекомендации"

    | Модель | `lora.r` | `learning_rate` | `batch_size` | `max_seq_length` | VRAM (QLoRA) |
    |---|---|---|---|---|---|
    | 0.8B | 8 | 2e-4 -- 5e-4 | 2-4 | 512-1024 | ~3 GB |
    | 2B | 16 | 2e-4 | 1-2 | 512 | ~5 GB |
    | 4B | 16 | 1e-4 -- 2e-4 | 1 | 512 | ~8 GB |
    | 7B | 16-32 | 1e-4 | 1 | 512 | ~12 GB |
    | 13B | 16 | 5e-5 -- 1e-4 | 1 | 512 | ~18 GB |
    | 70B | 16 | 5e-5 | 1 | 256 | ~48 GB |

    Для моделей 70B+ рекомендуется multi-GPU с FSDP или DeepSpeed.

---

## Результаты обучения

После завершения SFT создаётся:

```
outputs/my-classifier/
├── lora/                      # LoRA адаптер
│   ├── adapter_config.json
│   ├── adapter_model.safetensors
│   └── tokenizer.json
├── checkpoint-200/            # промежуточный чекпоинт
├── checkpoint-400/            # промежуточный чекпоинт
└── training_results.json      # метрики обучения
```

Если в конфиге `test_size > 0`, автоматически запускается оценка на тестовой выборке (auto-eval) с вычислением accuracy и F1.
