# Система наследования конфигов

## Как работает наследование

В pulsar-ai конфиги строятся по принципу **слоёв**: базовые дефолты переопределяются более специфичными конфигами, а конкретный эксперимент переопределяет всё.

Ключ `inherit` принимает список имён конфигов, которые загружаются и мержатся последовательно:

```yaml
inherit:
  - base                    # 1. Базовые дефолты (lr, epochs, seed, ...)
  - models/qwen3.5-0.8b    # 2. Параметры модели (name, lora, max_seq_length)
  - strategies/qlora        # 3. Стратегия (load_in_4bit, lora_r, ...)
  - tasks/dpo               # 4. Тип задачи (dpo.beta, epochs для DPO)
```

---

## Порядок слияния

Конфиги мержатся **слева направо** с глубоким слиянием (deep merge). Более поздний конфиг переопределяет более ранний. Экспериментальный конфиг (сам файл) переопределяет всё наследуемое.

```
base.yaml          →  { training: { epochs: 3, lr: 2e-4 }, strategy: auto }
models/qwen3.5.yaml →  { model: { name: "Qwen/Qwen3.5-0.8B" }, lora: { r: 8 } }
strategies/qlora   →  { load_in_4bit: true, lora_r: 16 }
experiment.yaml    →  { training: { epochs: 5 } }          # <-- финальный
────────────────────────────────────────────────────────────
Результат:           { training: { epochs: 5, lr: 2e-4 },  # epochs из experiment
                       model: { name: "Qwen/Qwen3.5-0.8B" },
                       lora: { r: 8 },
                       load_in_4bit: true,
                       strategy: auto }
```

!!! note "Глубокое слияние"
    Вложенные словари мержатся рекурсивно. Например, если `base.yaml` задаёт `training.epochs: 3`, а эксперимент задаёт `training.learning_rate: 1e-4`, оба значения сохранятся. Непосредственное значение ключа перезаписывается только если оно задано в более позднем конфиге.

---

## CLI-переопределения

Переопределения через CLI имеют **высший приоритет** и перезаписывают всё:

```bash
pulsar train configs/experiments/my-sft.yaml \
  learning_rate=1e-4 \
  training.epochs=5 \
  lora.r=32
```

Поддержка вложенных ключей через точку:

```bash
pulsar train config.yaml training.learning_rate=1e-4 dpo.beta=0.2
```

Приоритет (от низшего к высшему):

1. `base.yaml`
2. `models/...`
3. `strategies/...`
4. `tasks/...`
5. **Экспериментальный конфиг** (сам файл)
6. **CLI overrides** (высший приоритет)

---

## Доступные базовые конфиги

### Базовый конфиг

| Файл | Описание |
|---|---|
| `configs/base.yaml` | Общие дефолты: epochs=3, lr=2e-4, strategy=auto, seed=42 |

### Модели (`configs/models/`)

| Файл | Модель | Семейство | Особенности |
|---|---|---|---|
| `models/qwen3.5-0.8b.yaml` | Qwen 3.5 0.8B | Qwen 3 | ~3 GB VRAM, быстрое прототипирование |
| `models/qwen3.5-2b.yaml` | Qwen 3.5 2B | Qwen 3 | Баланс скорости и качества |
| `models/qwen3.5-4b.yaml` | Qwen 3.5 4B | Qwen 3 | Хорошее качество, ~8 GB VRAM |
| `models/qwen2.5-3b.yaml` | Qwen 2.5 3B | Qwen 2 | Проверенная модель |
| `models/llama3.2-1b.yaml` | Llama 3.2 1B | Llama | Лёгкая модель от Meta |
| `models/mistral-7b.yaml` | Mistral 7B | Mistral | Сильная 7B модель |

### Стратегии (`configs/strategies/`)

| Файл | Стратегия | VRAM | Описание |
|---|---|---|---|
| `strategies/qlora.yaml` | QLoRA | Минимум | 4-bit + LoRA, gradient checkpointing |
| `strategies/lora.yaml` | LoRA | Средний | LoRA без квантизации, lora_r=64 |
| `strategies/fsdp_qlora.yaml` | FSDP + QLoRA | Multi-GPU | Распределённый QLoRA |
| `strategies/fsdp_full.yaml` | FSDP Full | Multi-GPU | Полный файнтюнинг с FSDP |

### Задачи (`configs/tasks/`)

| Файл | Задача | Описание |
|---|---|---|
| `tasks/sft.yaml` | SFT | Дефолты для Supervised Fine-Tuning |
| `tasks/dpo.yaml` | DPO | beta=0.1, epochs=2, lr=5e-5 |
| `tasks/eval.yaml` | Evaluation | Дефолты для оценки |

---

## Создание своего конфига модели

Если вы работаете с моделью, для которой нет готового конфига:

```yaml
# configs/models/my-custom-model.yaml

model:
  name: "my-org/my-custom-7b"     # HuggingFace Hub ID или локальный путь
  family: llama                     # семейство (для выбора target_modules)
  max_seq_length: 4096              # макс. контекст модели
  chat_template: chatml             # шаблон чата

# Настройка LoRA target_modules для этой архитектуры
lora:
  r: 16
  lora_alpha: 32
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

use_unsloth: false
load_in_4bit: true
gradient_checkpointing: true
```

Использование:

```yaml
# configs/experiments/my-experiment.yaml
inherit:
  - base
  - models/my-custom-model    # <-- ваш конфиг модели
```

---

## Создание своей стратегии

```yaml
# configs/strategies/my-strategy.yaml

load_in_4bit: false
use_lora: true
lora_r: 128
lora_alpha: 256
lora_dropout: 0.1
gradient_checkpointing: true

# Кастомные настройки FSDP
fsdp_enabled: true
fsdp_sharding_strategy: SHARD_GRAD_OP    # менее агрессивный шардинг
fsdp_cpu_offload: false
```

---

## Пример полностью разрешённого конфига

Для понимания, как выглядит финальный конфиг после слияния всех слоёв:

```yaml
# inherit: [base, models/qwen3.5-0.8b]
# + experiment overrides
# + strategy: auto (detected: qlora)
# + CLI: learning_rate=1e-4

# ── Результат слияния ────────────────────────────────────
task: sft
strategy: auto
_detected_strategy: qlora          # определено автоматически

model:
  name: Qwen/Qwen3.5-0.8B
  family: qwen3
  max_seq_length: 32768
  chat_template: chatml

training:
  epochs: 3                        # из base.yaml
  learning_rate: 1e-4              # из CLI override
  batch_size: 1                    # из hardware auto-detection
  gradient_accumulation: 16        # из hardware auto-detection
  max_seq_length: 512              # из base.yaml
  warmup_steps: 10
  logging_steps: 20
  seed: 42
  optimizer: adamw_8bit
  packing: true

lora:
  r: 8                             # из models/qwen3.5-0.8b
  lora_alpha: 8
  target_modules: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]
  lora_dropout: 0
  bias: none

load_in_4bit: true                 # из стратегии qlora
gradient_checkpointing: true
use_unsloth: false                 # из models/qwen3.5-0.8b

dataset:
  path: data/my_dataset.csv
  format: csv
  text_column: text
  label_columns: [label]
  test_size: 0.15

output:
  dir: ./outputs/my-experiment
  save_adapter: true

logging:
  level: INFO
  report_to: none

_hardware:                          # добавлено автоматически
  num_gpus: 1
  gpu_name: NVIDIA GeForce RTX 4060
  vram_per_gpu_gb: 8.0
  bf16_supported: true
```

!!! tip "Отладка конфига"
    Запустите обучение с флагом `-v` (verbose), чтобы увидеть все шаги слияния и итоговый конфиг:

    ```bash
    pulsar -v train configs/experiments/my-sft.yaml
    ```
