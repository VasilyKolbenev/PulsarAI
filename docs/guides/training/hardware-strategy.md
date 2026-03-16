# Стратегии обучения и оборудование

## Диагностика оборудования

Команда `pulsar info` показывает обнаруженное оборудование и рекомендуемую стратегию:

```bash
pulsar info
```

Пример вывода:

```
┌──────────────── Hardware Info ─────────────────┐
│ Property                │ Value                │
│─────────────────────────┼──────────────────────│
│ GPUs                    │ 1                    │
│ GPU Name                │ NVIDIA GeForce RTX   │
│                         │ 4090                 │
│ VRAM per GPU            │ 24.0 GB              │
│ Total VRAM              │ 24.0 GB              │
│ Compute Capability      │ 8.9                  │
│ BF16 Supported          │ True                 │
│ Recommended Strategy    │ lora                 │
│ Recommended Batch Size  │ 2                    │
│ Recommended Grad Accum  │ 8                    │
└─────────────────────────┴──────────────────────┘
```

---

## Автоматический выбор стратегии

При `strategy: auto` (по умолчанию в `base.yaml`) pulsar-ai автоматически определяет оптимальную стратегию по VRAM и количеству GPU:

### Один GPU

| VRAM | Стратегия | Batch Size | Grad Accum | Пример GPU |
|---|---|---|---|---|
| < 12 GB | `qlora` | 1 | 16 | RTX 3060, RTX 4060, RTX 5070 Laptop |
| 12-24 GB | `lora` | 2 | 8 | RTX 3090, RTX 4090 |
| 24-48 GB | `full` | 4 | 4 | A6000, L40 |
| >= 48 GB | `full` | 8 | 2 | A100 80GB, H100 |

### Несколько GPU (2-4)

| VRAM/GPU | Стратегия | Batch Size | Grad Accum |
|---|---|---|---|
| < 24 GB | `fsdp_qlora` | 1 | 8 |
| >= 24 GB | `fsdp_lora` | 2 | 4 |

### Много GPU (8+)

| VRAM/GPU | Стратегия | Batch Size | Grad Accum |
|---|---|---|---|
| >= 40 GB | `fsdp_full` | 4 | 2 |
| < 40 GB | `deepspeed_zero3` | 2 | 4 |

---

## Ручное указание стратегии

Если автоматический выбор не подходит, укажите стратегию вручную в конфиге:

```yaml
# Прямое указание стратегии (отключает автоопределение)
strategy: qlora

# Или через наследование стратегии
inherit:
  - base
  - models/qwen3.5-2b
  - strategies/qlora          # <-- явная стратегия
```

Доступные конфиги стратегий:

| Файл | Стратегия | Описание |
|---|---|---|
| `strategies/qlora.yaml` | QLoRA | 4-bit квантизация + LoRA. Минимум VRAM |
| `strategies/lora.yaml` | LoRA | LoRA без квантизации. Лучше качество |
| `strategies/fsdp_qlora.yaml` | FSDP + QLoRA | Распределённый QLoRA на нескольких GPU |
| `strategies/fsdp_full.yaml` | FSDP Full | Полный файнтюнинг с FSDP |

---

## Требования к VRAM по размеру модели

Минимальный VRAM для обучения с **QLoRA** (4-bit, batch_size=1):

| Модель | Параметры | VRAM (QLoRA) | VRAM (LoRA) | VRAM (Full) |
|---|---|---|---|---|
| Qwen 3.5 0.8B | 0.8B | ~3 GB | ~5 GB | ~8 GB |
| Qwen 3.5 2B | 2B | ~5 GB | ~10 GB | ~16 GB |
| Qwen 3.5 4B | 4B | ~8 GB | ~18 GB | ~32 GB |
| Mistral 7B | 7B | ~12 GB | ~24 GB | ~56 GB |
| Llama 13B | 13B | ~18 GB | ~40 GB | ~104 GB |
| Llama 70B | 70B | ~48 GB | ~140 GB | ~560 GB |

!!! note "VRAM -- приблизительные значения"
    Реальное потребление зависит от `max_seq_length`, `batch_size`, `gradient_accumulation` и длины примеров в датасете. Значения указаны для `max_seq_length=512`, `batch_size=1`.

---

## Рекомендуемые batch_size и gradient_accumulation

| VRAM | batch_size | gradient_accumulation | Эффективный батч |
|---|---|---|---|
| 6-8 GB | 1 | 16 | 16 |
| 10-12 GB | 1 | 16 | 16 |
| 16 GB | 2 | 8 | 16 |
| 24 GB | 2-4 | 8-4 | 16 |
| 48 GB | 4-8 | 4-2 | 16-32 |
| 80 GB | 8-16 | 2-1 | 16-32 |

!!! tip "Эффективный батч"
    Эффективный размер батча = `batch_size` x `gradient_accumulation`. Старайтесь поддерживать эффективный батч в диапазоне **16-32** для стабильного обучения.

---

## bf16 vs fp16

| Параметр | bf16 | fp16 |
|---|---|---|
| **Поддержка** | Ampere+ (RTX 30xx, A100, H100) | Все CUDA GPU |
| **Динамический диапазон** | Широкий (как fp32) | Узкий (риск overflow) |
| **Точность мантиссы** | Ниже (8 бит) | Выше (11 бит) |
| **Стабильность обучения** | Высокая | Может потребовать loss scaling |
| **Рекомендация** | Используйте при Compute Capability >= 8.0 | Fallback для старых GPU |

pulsar-ai автоматически определяет поддержку bf16 по Compute Capability GPU.

```yaml
# Автоматически устанавливается при strategy: auto
# Для ручного управления:
training:
  bf16: true   # или false для fp16
```

!!! warning "NaN на старых GPU"
    Если вы видите NaN loss на GPU с Compute Capability < 8.0 (RTX 20xx, GTX), убедитесь, что `bf16: false`. Используйте `fp16` с `loss_scale: dynamic`.

---

## DeepSpeed vs FSDP

| Характеристика | FSDP | DeepSpeed ZeRO-3 |
|---|---|---|
| **Реализация** | PyTorch native | Microsoft DeepSpeed |
| **Шардинг модели** | Полный (FULL_SHARD) | ZeRO Stage 3 |
| **CPU Offload** | Поддерживается | Поддерживается (параметры + оптимизатор) |
| **Совместимость с QLoRA** | Да (fsdp_qlora) | Ограниченная |
| **Простота настройки** | Проще (нет JSON-конфига) | Требует ds_config.json |
| **Рекомендация** | 2-4 GPU | 8+ GPU, большие модели (70B+) |

### FSDP в pulsar-ai

```yaml
strategy: fsdp_qlora   # или fsdp_lora, fsdp_full

# Автоматически устанавливает:
fsdp_enabled: true
fsdp_sharding_strategy: FULL_SHARD
fsdp_cpu_offload: true  # для fsdp_qlora
```

### DeepSpeed в pulsar-ai

```yaml
strategy: deepspeed_zero3

# Автоматически устанавливает:
deepspeed_enabled: true
deepspeed_stage: 3
deepspeed_offload_optimizer: true
deepspeed_offload_params: true
```

!!! tip "Выбор между FSDP и DeepSpeed"
    - **2-4 GPU**: используйте FSDP -- проще настройка, нативная поддержка PyTorch
    - **8+ GPU, модель 70B+**: DeepSpeed ZeRO-3 с CPU offload
    - **Один GPU**: не нужны ни FSDP, ни DeepSpeed -- используйте `qlora` или `lora`
