# DPO (Direct Preference Optimization)

## Что такое DPO

Direct Preference Optimization (DPO) -- метод выравнивания модели на основе предпочтений. В отличие от SFT, где модель учится на единственном "правильном" ответе, DPO учит модель **предпочитать** лучший ответ (chosen) плохому (rejected). DPO применяется **после SFT** для улучшения качества генерации: уменьшения галлюцинаций, повышения точности и соответствия формату.

---

## Когда использовать DPO

DPO полезен, когда:

- SFT-модель часто ошибается в формате ответа (невалидный JSON, лишние поля)
- Нужно подавить конкретные ошибочные паттерны
- Есть возможность собрать пары "хороший/плохой" ответ
- Нужно повысить accuracy после SFT без дополнительных данных

!!! note "DPO всегда после SFT"
    DPO работает поверх уже обученной SFT-модели. Сначала обучите SFT, затем используйте её адаптер как базу для DPO.

---

## Формат DPO-пар

DPO требует файл в формате **JSONL** с тремя полями: `prompt`, `chosen`, `rejected`.

```json
{"prompt": "Привет, как дела?", "chosen": "{\"intent\": \"greeting\"}", "rejected": "{\"intnt\": \"greetin\"}"}
{"prompt": "Закажи пиццу", "chosen": "{\"intent\": \"order_food\"}", "rejected": "{\"intent\": \"unknown\"}"}
{"prompt": "Какая погода?", "chosen": "{\"intent\": \"weather\"}", "rejected": "Я не знаю"}
```

!!! warning "Формат chosen/rejected ДОЛЖЕН совпадать с форматом SFT"
    Поле `chosen` должно содержать ответ **точно в том формате**, который модель училась генерировать при SFT. Если SFT обучен выдавать JSON вида `{"domain": "X", "skill": "Y"}`, то и `chosen` в DPO-парах должен быть в таком же формате.

    Поле `rejected` -- это реальный неправильный ответ модели или намеренно искажённый вариант.

---

## Конфиг DPO

```yaml
# configs/experiments/my-classifier-dpo.yaml

inherit:
  - base                    # базовые дефолты
  - models/qwen3.5-0.8b    # параметры модели
  - tasks/dpo               # дефолты DPO (beta, epochs, lr)

task: dpo

# Путь к SFT-адаптеру (обязательно)
sft_adapter_path: ./outputs/my-classifier-sft/lora

# ── DPO-специфичные параметры ────────────────────────────
dpo:
  pairs_path: ./outputs/my-classifier-sft/dpo_pairs.jsonl  # файл с парами
  beta: 0.1          # коэффициент KL-дивергенции (0.05-0.5)
  max_length: 512     # макс. длина последовательности для DPO

# ── Параметры обучения (переопределяют base) ─────────────
training:
  epochs: 2                  # DPO обычно требует меньше эпох
  learning_rate: 5e-5        # LR для DPO ниже, чем для SFT
  batch_size: 1
  gradient_accumulation: 8
  optimizer: adamw_8bit

# ── Датасет (системный промпт для форматирования) ────────
dataset:
  system_prompt_file: prompts/cam_taxonomy.txt

output:
  dir: ./outputs/my-classifier-dpo
```

### Параметры DPO

| Параметр | Тип | По умолчанию | Описание |
|---|---|---|---|
| `sft_adapter_path` | str | -- | Путь к LoRA-адаптеру после SFT (обязательно) |
| `dpo.pairs_path` | str | -- | Путь к JSONL-файлу с DPO-парами (обязательно) |
| `dpo.beta` | float | `0.1` | Коэффициент KL-штрафа. Меньше = агрессивнее оптимизация |
| `dpo.max_length` | int | `512` | Макс. длина последовательности |
| `training.learning_rate` | float | `5e-5` | LR для DPO (обычно в 4-10x ниже SFT) |
| `training.epochs` | int | `2` | Количество эпох (1-3 для DPO) |

---

## Запуск DPO

=== "CLI"

    ```bash
    # Стандартный запуск
    pulsar train configs/experiments/my-classifier-dpo.yaml --task dpo

    # С явным указанием SFT-адаптера
    pulsar train configs/experiments/my-classifier-dpo.yaml \
      --task dpo \
      --base-model ./outputs/my-classifier-sft/lora

    # С переопределением параметров
    pulsar train configs/experiments/my-classifier-dpo.yaml \
      --task dpo \
      dpo.beta=0.2 training.epochs=3
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8888/api/training/start \
      -H "Content-Type: application/json" \
      -d '{
        "config_path": "configs/experiments/my-classifier-dpo.yaml",
        "task": "dpo",
        "overrides": {
          "sft_adapter_path": "./outputs/my-classifier-sft/lora",
          "dpo.beta": 0.2
        }
      }'
    ```

=== "UI"

    1. Откройте **Experiments** в Web UI
    2. Нажмите **New Experiment**, выберите задачу **DPO**
    3. Укажите путь к SFT-адаптеру и файлу с DPO-парами
    4. Настройте `beta` и другие параметры
    5. Нажмите **Start Training**

---

## Генерация DPO-пар из ошибок eval

Самый эффективный способ создать DPO-пары -- собрать ошибки SFT-модели на eval:

1. **Обучите SFT-модель** и запустите оценку
2. **Соберите ошибки**: предсказания, где модель ответила неправильно
3. **Сформируйте пары**: правильный ответ (из ground truth) = `chosen`, ошибочный ответ модели = `rejected`

```python
import json
import pandas as pd

# Загрузить результаты eval
eval_results = pd.read_json("outputs/eval/predictions.jsonl", lines=True)

dpo_pairs = []
for _, row in eval_results.iterrows():
    if not row["correct"]:
        dpo_pairs.append({
            "prompt": row["input"],
            "chosen": row["expected"],   # правильный ответ
            "rejected": row["predicted"] # ошибочный ответ модели
        })

# Сохранить
with open("outputs/dpo_pairs.jsonl", "w") as f:
    for pair in dpo_pairs:
        f.write(json.dumps(pair, ensure_ascii=False) + "\n")

print(f"Сгенерировано {len(dpo_pairs)} DPO-пар")
```

!!! tip "Количество DPO-пар"
    Для заметного улучшения обычно достаточно 100-500 DPO-пар. Качество пар важнее количества.

---

## Сравнение: SFT vs SFT+DPO

Типичные результаты при добавлении DPO поверх SFT:

| Метрика | SFT only | SFT + DPO | Улучшение |
|---|---|---|---|
| Accuracy | 85.2% | 91.4% | +6.2% |
| JSON parse rate | 92.1% | 98.7% | +6.6% |
| F1 weighted | 0.843 | 0.908 | +0.065 |
| Ошибки формата | 7.9% | 1.3% | -6.6% |

!!! tip "Когда DPO даёт максимальный эффект"
    DPO особенно эффективен, когда основная проблема SFT -- это **формат ответа** (невалидный JSON, лишние поля, неправильные ключи). Для ошибок в **содержании** может потребоваться больше тренировочных данных для SFT.

---

## Результаты DPO

После завершения DPO создаётся:

```
outputs/my-classifier-dpo/
├── lora/                      # DPO LoRA адаптер (наложен поверх SFT)
│   ├── adapter_config.json
│   ├── adapter_model.safetensors
│   └── tokenizer.json
└── training_results.json
```

Этот адаптер можно использовать для eval и export так же, как SFT-адаптер.
