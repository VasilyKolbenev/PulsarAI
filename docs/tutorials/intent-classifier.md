# Intent Classifier (End-to-End)

Полный цикл создания классификатора интентов: от подготовки данных до деплоя модели как API.

---

## Цель

Обучить компактную модель (Qwen3.5-0.8B) классифицировать пользовательские сообщения в структурированный JSON с полями `domain` и `skill`. На выходе -- работающий API, принимающий текст и возвращающий JSON-классификацию.

```mermaid
graph LR
    A[CSV-датасет] --> B[SFT-обучение]
    B --> C[Оценка]
    C --> D[Экспорт GGUF]
    D --> E[Сервинг API]

    style A fill:#4051b5,color:#fff
    style B fill:#4051b5,color:#fff
    style C fill:#4051b5,color:#fff
    style D fill:#4051b5,color:#fff
    style E fill:#4051b5,color:#fff
```

---

## 1. Подготовка датасета

Создайте CSV-файл `data/cam_intents.csv` с тремя колонками: `phrase`, `domain`, `skill`.

```csv title="data/cam_intents.csv"
phrase,domain,skill
Оплатить коммуналку,HOUSE,utility_bill
Какая погода завтра,WEATHER,forecast
Поставь будильник на 7 утра,DEVICE,alarm_set
Переведи 500 рублей маме,FINANCE,money_transfer
Включи музыку,MEDIA,music_play
Забронируй столик на вечер,FOOD,restaurant_booking
```

!!! tip "Рекомендации по данным"
    - Минимум **500 примеров** для базового качества, **1000+** для продакшена.
    - Баланс между классами: не более 5x разницы между самым частым и самым редким классом.
    - Включайте вариации формулировок для каждого интента.
    - Разделите данные на train/test (85/15) заранее или укажите `test_split` в конфиге.

Подготовьте также тестовый файл `data/cam_intents_test.csv` с теми же колонками (примерно 15% от общего объёма).

---

## 2. Системный промпт

Системный промпт задаёт формат ответа модели. Он будет включён в каждый обучающий пример.

```text title="Системный промпт"
You are an intent classifier. Given a user message, respond with JSON:
{"domain": "<DOMAIN>", "skill": "<SKILL>"}
Do not include any other text in your response.
```

!!! warning "Формат ответа"
    Промпт должен **точно** описывать ожидаемый формат. Модель будет генерировать ответ
    в том формате, который видела при обучении. Если в данных JSON без пробелов --
    промпт тоже должен показывать JSON без пробелов.

---

## 3. Создание конфига

Конфиг использует систему наследования (`inherit`) для переиспользования базовых настроек.

```yaml title="configs/examples/cam-sft-qwen3.5-0.8b.yaml"
# Наследуем базовый конфиг и конфиг модели
inherit:
  - configs/base.yaml
  - configs/models/qwen3.5-0.8b.yaml

# Задача
task: sft

# Датасет
dataset:
  path: data/cam_intents.csv
  format: csv
  columns:
    input: phrase
    output: '{"domain": "${domain}", "skill": "${skill}"}'
  system_prompt: >
    You are an intent classifier. Given a user message, respond with JSON:
    {"domain": "<DOMAIN>", "skill": "<SKILL>"}
    Do not include any other text in your response.
  test_split: 0.15

# Обучение
epochs: 5
learning_rate: 3e-4
batch_size: 2
gradient_accumulation_steps: 8
max_seq_length: 256

# Выход
output_dir: outputs/cam-sft-qwen3.5-0.8b
```

!!! info "Наследование конфигов"
    Файл `configs/base.yaml` содержит общие настройки (seed, logging, hardware auto-detection).
    Файл `configs/models/qwen3.5-0.8b.yaml` задаёт `model_name`, `lora_r`, `lora_alpha`,
    `target_modules` и другие параметры, специфичные для модели.

---

## 4. Запуск обучения

```bash
pulsar train configs/examples/cam-sft-qwen3.5-0.8b.yaml
```

Ожидаемый вывод:

```
Loading model Qwen/Qwen3.5-0.8B...
Applying QLoRA: r=16, alpha=32, modules=['q_proj', 'k_proj', 'v_proj', 'o_proj']
Dataset: 1234 rows (train: 1049, test: 185)
Training started: 5 epochs, lr=3e-4, batch=2, grad_accum=8

Step 100/660 | Loss: 1.842 | LR: 2.7e-4 | GPU: 2.1 GB
Step 200/660 | Loss: 0.934 | LR: 2.1e-4 | GPU: 2.1 GB
Step 300/660 | Loss: 0.487 | LR: 1.5e-4 | GPU: 2.1 GB
Step 400/660 | Loss: 0.231 | LR: 9.1e-5 | GPU: 2.1 GB
Step 500/660 | Loss: 0.142 | LR: 3.6e-5 | GPU: 2.1 GB
Step 660/660 | Loss: 0.098 | LR: 0.0e+0 | GPU: 2.1 GB

Training complete! Adapter saved to outputs/cam-sft-qwen3.5-0.8b/lora
```

!!! note "Время обучения"
    | GPU | VRAM | Время (~1000 примеров, 5 эпох) |
    |-----|------|-------------------------------|
    | RTX 3060 | 12 GB | ~15 минут |
    | RTX 4060 | 8 GB | ~12 минут |
    | RTX 4090 | 24 GB | ~5 минут |

---

## 5. Мониторинг в Web UI

Во время обучения запустите Web UI для мониторинга в реальном времени:

=== "Терминал 1: Backend"

    ```bash
    pulsar ui
    ```

=== "Терминал 2: Frontend"

    ```bash
    cd ui && npm run dev
    ```

Откройте [http://localhost:5173](http://localhost:5173) и перейдите на страницу **Experiments**.
Графики обновляются в реальном времени через SSE-стримы:

- **Loss** -- снижение функции потерь по шагам
- **Learning Rate** -- расписание lr (cosine decay)
- **GPU Memory** -- потребление VRAM
- **Throughput** -- токены в секунду

---

## 6. Оценка модели

```bash
pulsar eval \
  --model outputs/cam-sft-qwen3.5-0.8b/lora \
  --test-data data/cam_intents_test.csv
```

Ожидаемый вывод:

```
Evaluating 185 samples...
━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Results:
  Accuracy:         87.5%
  F1 (weighted):    0.894
  JSON Parse Rate:  100.0%
  Avg Latency:      42ms/sample

Per-class metrics:
  HOUSE      | Precision: 0.91 | Recall: 0.88 | F1: 0.89
  WEATHER    | Precision: 0.95 | Recall: 0.93 | F1: 0.94
  DEVICE     | Precision: 0.84 | Recall: 0.86 | F1: 0.85
  FINANCE    | Precision: 0.88 | Recall: 0.85 | F1: 0.86
  MEDIA      | Precision: 0.92 | Recall: 0.90 | F1: 0.91
  FOOD       | Precision: 0.81 | Recall: 0.83 | F1: 0.82
```

!!! success "Анализ результатов"
    - **Accuracy 87.5%** -- хороший результат для модели 0.8B на первой итерации.
    - **JSON Parse Rate 100%** -- модель всегда генерирует валидный JSON.
    - **F1 89.4%** (weighted) -- сбалансированная метрика с учётом частоты классов.
    - Слабые места: классы DEVICE и FOOD -- можно улучшить добавлением данных или DPO.

---

## 7. Экспорт в GGUF

```bash
pulsar export \
  --model outputs/cam-sft-qwen3.5-0.8b/lora \
  --format gguf \
  --quant q4_k_m
```

Ожидаемый вывод:

```
Merging LoRA adapter with base model...
Converting to GGUF (q4_k_m)...
Exported: outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf (530 MB)
```

!!! tip "Выбор квантизации"
    | Квантизация | Размер (0.8B) | Качество | Скорость |
    |-------------|---------------|----------|----------|
    | `q4_k_m` | ~530 MB | Хорошее | Быстро |
    | `q8_0` | ~900 MB | Отличное | Средне |
    | `f16` | ~1.6 GB | Максимальное | Медленно |

    Для задач классификации `q4_k_m` достаточно -- потеря качества минимальна.

---

## 8. Запуск сервера

```bash
pulsar serve \
  --model outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf \
  --port 8080 \
  --backend llamacpp
```

Ожидаемый вывод:

```
Loading model: cam-sft-qwen3.5-0.8b-q4_k_m.gguf
Backend: llama.cpp
Server running on http://localhost:8080
OpenAI-compatible API: POST /v1/chat/completions
```

---

## 9. Тестирование API

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [
      {
        "role": "system",
        "content": "You are an intent classifier. Given a user message, respond with JSON: {\"domain\": \"<DOMAIN>\", \"skill\": \"<SKILL>\"}"
      },
      {
        "role": "user",
        "content": "Закажи пиццу на дом"
      }
    ],
    "temperature": 0.0,
    "max_tokens": 64
  }'
```

Ожидаемый ответ:

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"domain\": \"FOOD\", \"skill\": \"food_delivery\"}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 58,
    "completion_tokens": 12,
    "total_tokens": 70
  }
}
```

Тестирование через Python:

```python title="test_classifier.py"
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",
)

messages = [
    {
        "role": "system",
        "content": (
            'You are an intent classifier. Given a user message, '
            'respond with JSON: {"domain": "<DOMAIN>", "skill": "<SKILL>"}'
        ),
    },
    {"role": "user", "content": "Переведи деньги на карту"},
]

response = client.chat.completions.create(
    model="default",
    messages=messages,
    temperature=0.0,
    max_tokens=64,
)

print(response.choices[0].message.content)
# {"domain": "FINANCE", "skill": "money_transfer"}
```

---

## 10. Что дальше?

- **DPO для улучшения** -- соберите пары chosen/rejected из ошибок eval и обучите DPO-модель.
  См. [Чатбот с DPO](chatbot-dpo.md).
- **Больше данных** -- увеличьте датасет до 2000+ примеров для классов с низким F1.
- **Модель побольше** -- попробуйте Qwen3.5-2B или Qwen3.5-4B для сложных интентов.
- **Pipeline** -- автоматизируйте цикл train-eval-export.
  См. [Полный Pipeline](full-pipeline.md).
- **Агент** -- используйте классификатор как инструмент агента.
  См. [Агент с инструментами](agent-with-tools.md).
