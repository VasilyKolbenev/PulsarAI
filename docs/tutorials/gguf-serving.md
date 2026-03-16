# Train -> GGUF -> Serve

Полный путь от обученного адаптера до работающего API: экспорт в GGUF, выбор квантизации, запуск сервера, интеграция через OpenAI SDK.

---

## Обзор

```mermaid
graph LR
    A[LoRA-адаптер] --> B[Merge с базовой моделью]
    B --> C[Конвертация в GGUF]
    C --> D[Квантизация]
    D --> E[llama.cpp сервер]
    E --> F[OpenAI-совместимый API]

    style A fill:#4051b5,color:#fff
    style B fill:#4051b5,color:#fff
    style C fill:#4051b5,color:#fff
    style D fill:#4051b5,color:#fff
    style E fill:#4051b5,color:#fff
    style F fill:#4051b5,color:#fff
```

---

## 1. Подготовка адаптера

Убедитесь, что у вас есть обученный LoRA-адаптер:

```bash
ls outputs/cam-sft-qwen3.5-0.8b/lora/
```

```
adapter_config.json
adapter_model.safetensors
tokenizer.json
tokenizer_config.json
special_tokens_map.json
```

!!! tip "Нет адаптера?"
    Обучите модель по туториалу [Intent Classifier](intent-classifier.md) или используйте
    любой другой обученный адаптер.

---

## 2. Экспорт в GGUF

```bash
pulsar export \
  --model outputs/cam-sft-qwen3.5-0.8b/lora \
  --format gguf \
  --quant q4_k_m
```

Ожидаемый вывод:

```
Step 1/3: Loading base model Qwen/Qwen3.5-0.8B...
Step 2/3: Merging LoRA adapter...
Step 3/3: Converting to GGUF (q4_k_m)...

Exported: outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf
Size: 530 MB
Quantization: Q4_K_M (4-bit, k-quant medium)
```

---

## 3. Сравнение квантизаций

| Квантизация | Биты | Размер (0.8B) | Размер (2B) | Размер (7B) | Качество | Скорость | Когда использовать |
|-------------|------|---------------|-------------|-------------|----------|----------|-------------------|
| `q4_k_m` | 4 | ~530 MB | ~1.3 GB | ~4.4 GB | Хорошее | Быстро | Продакшен, edge-устройства |
| `q8_0` | 8 | ~900 MB | ~2.2 GB | ~7.5 GB | Отличное | Средне | Баланс качество/размер |
| `f16` | 16 | ~1.6 GB | ~4.0 GB | ~14 GB | Максимальное | Медленно | Бенчмарки, исследования |

!!! info "Как выбрать квантизацию"
    - **q4_k_m** -- лучший выбор для большинства задач. Потеря качества 1--2% при 3x сжатии.
    - **q8_0** -- если нужно максимальное качество при разумном размере.
    - **f16** -- для валидации: сравните с q4_k_m, чтобы измерить реальную потерю от квантизации.

Экспорт во все форматы для сравнения:

=== "q4_k_m"

    ```bash
    pulsar export \
      --model outputs/cam-sft-qwen3.5-0.8b/lora \
      --format gguf \
      --quant q4_k_m
    ```

=== "q8_0"

    ```bash
    pulsar export \
      --model outputs/cam-sft-qwen3.5-0.8b/lora \
      --format gguf \
      --quant q8_0
    ```

=== "f16"

    ```bash
    pulsar export \
      --model outputs/cam-sft-qwen3.5-0.8b/lora \
      --format gguf \
      --quant f16
    ```

---

## 4. Запуск сервера

```bash
pulsar serve \
  --model outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf \
  --port 8080 \
  --backend llamacpp
```

Ожидаемый вывод:

```
Loading model: cam-sft-qwen3.5-0.8b-q4_k_m.gguf (530 MB)
Backend: llama.cpp
Context size: 2048 tokens
Threads: 8

Server running on http://localhost:8080
Endpoints:
  POST /v1/chat/completions   (OpenAI-compatible)
  GET  /health                (Health check)
  GET  /metrics               (Prometheus metrics)
```

---

## 5. Тестирование через curl

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
        "content": "Какая погода будет в пятницу?"
      }
    ],
    "temperature": 0.0,
    "max_tokens": 64
  }'
```

Ожидаемый ответ:

```json
{
  "id": "chatcmpl-xyz789",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"domain\": \"WEATHER\", \"skill\": \"forecast\"}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 52,
    "completion_tokens": 10,
    "total_tokens": 62
  }
}
```

---

## 6. Python-клиент через OpenAI SDK

Сервер pulsar-ai полностью совместим с OpenAI Python SDK:

```python title="client.py"
import json

from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",  # Локальный сервер не требует ключа
)

SYSTEM_PROMPT = (
    'You are an intent classifier. Given a user message, '
    'respond with JSON: {"domain": "<DOMAIN>", "skill": "<SKILL>"}'
)


def classify_intent(text: str) -> dict:
    """Классифицирует пользовательский интент."""
    response = client.chat.completions.create(
        model="default",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
        max_tokens=64,
    )
    return json.loads(response.choices[0].message.content)


# Использование
result = classify_intent("Переведи 1000 рублей Саше")
print(result)
# {"domain": "FINANCE", "skill": "money_transfer"}

# Batch-обработка
messages = [
    "Включи свет в спальне",
    "Какой курс биткоина",
    "Закажи суши на двоих",
]

for msg in messages:
    intent = classify_intent(msg)
    print(f"{msg:30s} -> {intent}")
```

Вывод:

```
Включи свет в спальне          -> {'domain': 'DEVICE', 'skill': 'light_control'}
Какой курс биткоина             -> {'domain': 'FINANCE', 'skill': 'exchange_rate'}
Закажи суши на двоих            -> {'domain': 'FOOD', 'skill': 'food_delivery'}
```

---

## 7. Создание Ollama Modelfile

Для запуска модели через Ollama создайте Modelfile:

```dockerfile title="Modelfile"
FROM ./outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf

PARAMETER temperature 0.0
PARAMETER num_predict 64
PARAMETER stop "<|endoftext|>"

SYSTEM """You are an intent classifier. Given a user message, respond with JSON: {"domain": "<DOMAIN>", "skill": "<SKILL>"}"""
```

Сборка и запуск:

```bash
# Создание модели в Ollama
ollama create cam-intent -f Modelfile

# Тест
ollama run cam-intent "Поставь будильник на 6 утра"
# {"domain": "DEVICE", "skill": "alarm_set"}
```

---

## 8. Мониторинг сервинга

Сервер экспортирует метрики в формате Prometheus:

```bash
curl http://localhost:8080/metrics
```

```
# HELP llm_requests_total Total number of requests
llm_requests_total 142

# HELP llm_request_duration_seconds Request duration in seconds
llm_request_duration_seconds_avg 0.045

# HELP llm_tokens_per_second Token generation speed
llm_tokens_per_second 285.3

# HELP llm_active_requests Currently processing requests
llm_active_requests 0
```

Ключевые метрики для мониторинга:

| Метрика | Описание | Нормальное значение (0.8B q4_k_m) |
|---------|----------|----------------------------------|
| `request_duration_avg` | Среднее время ответа | 30--80ms |
| `tokens_per_second` | Скорость генерации | 200--400 t/s |
| `active_requests` | Текущие запросы | 0--10 |
| `error_rate` | Процент ошибок | < 0.1% |

!!! tip "Нагрузочное тестирование"
    Для проверки под нагрузкой используйте `hey` или `wrk`:

    ```bash
    hey -n 1000 -c 10 -m POST \
      -H "Content-Type: application/json" \
      -d '{"model":"default","messages":[{"role":"user","content":"test"}]}' \
      http://localhost:8080/v1/chat/completions
    ```

---

## Что дальше?

- **Автоматизация** -- объедините train, eval, export и serve в один pipeline.
  См. [Полный Pipeline](full-pipeline.md).
- **vLLM** -- для высоконагруженных сценариев используйте бэкенд vLLM.
- **Model Registry** -- зарегистрируйте модель для версионирования и продвижения
  по стадиям (staging -> production).
