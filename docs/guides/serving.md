# Сервинг модели

## Обзор

pulsar-ai поддерживает два бэкенда для запуска обученных моделей как API-сервиса:

- **llama.cpp** -- для GGUF-файлов, оптимальный для одиночного GPU и CPU
- **vLLM** -- для полных моделей, высокопроизводительный batch-инференс

Оба бэкенда предоставляют **OpenAI-совместимый API** (`/v1/chat/completions`).

---

## Запуск сервера

### llama.cpp (GGUF)

```bash
pulsar serve \
  --model ./exports/cam-model.gguf \
  --backend llamacpp \
  --port 8080 \
  --host 0.0.0.0
```

### vLLM (полная модель)

```bash
pulsar serve \
  --model ./outputs/cam-sft \
  --backend vllm \
  --port 8000 \
  --host 0.0.0.0
```

---

## Сравнение бэкендов

| Характеристика | llama.cpp | vLLM |
|---|---|---|
| **Формат модели** | GGUF (квантизированный) | Полная модель (safetensors) |
| **Поддержка CPU** | Да | Нет (только GPU) |
| **Batch-инференс** | Ограниченный | Высокопроизводительный (continuous batching) |
| **VRAM** | Минимальный (зависит от quant) | Полный размер модели |
| **Скорость (1 запрос)** | Быстро | Быстро |
| **Скорость (100 RPS)** | Средне | Очень быстро |
| **PagedAttention** | Нет | Да |
| **Установка** | Простая | Требует CUDA toolkit |
| **Рекомендация** | Локальная разработка, edge | Продакшен, высокая нагрузка |

---

## OpenAI-совместимый API

Оба бэкенда предоставляют endpoint `/v1/chat/completions`, совместимый с OpenAI SDK:

### curl

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [
      {"role": "system", "content": "Ты классификатор интентов. Верни JSON."},
      {"role": "user", "content": "Закажи такси до аэропорта"}
    ],
    "temperature": 0.1,
    "max_tokens": 128
  }'
```

Ответ:

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "default",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"domain\": \"transport\", \"skill\": \"taxi\"}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 15,
    "total_tokens": 57
  }
}
```

### Python (OpenAI SDK)

```python
from openai import OpenAI

# Подключение к локальному серверу pulsar-ai
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",  # для локального сервера ключ не требуется
)

response = client.chat.completions.create(
    model="default",
    messages=[
        {"role": "system", "content": "Ты классификатор интентов. Верни JSON."},
        {"role": "user", "content": "Закажи такси до аэропорта"},
    ],
    temperature=0.1,
    max_tokens=128,
)

answer = response.choices[0].message.content
print(answer)
# {"domain": "transport", "skill": "taxi"}
```

!!! tip "Совместимость"
    Благодаря OpenAI-совместимому API можно использовать любую библиотеку, которая поддерживает OpenAI SDK: LangChain, LlamaIndex, Instructor и другие. Достаточно указать `base_url` на ваш сервер.

---

## Метрики сервинга

pulsar-ai собирает метрики производительности в реальном времени:

| Метрика | Описание |
|---|---|
| `latency_p50_ms` | Медианная задержка запроса |
| `latency_p95_ms` | 95-й перцентиль задержки |
| `latency_p99_ms` | 99-й перцентиль задержки |
| `latency_avg_ms` | Средняя задержка |
| `rps` | Запросов в секунду (throughput) |
| `tokens_per_second` | Выходных токенов в секунду |
| `error_rate` | Доля ошибочных запросов |
| `total_requests` | Всего обработано запросов |
| `uptime_seconds` | Время работы сервера |

### Получение метрик

=== "CLI"

    ```bash
    curl http://localhost:8080/metrics
    ```

=== "API"

    ```bash
    curl http://localhost:8080/v1/metrics?window_seconds=60
    ```

Пример ответа:

```json
{
  "window_seconds": 60,
  "total_requests": 1523,
  "requests_in_window": 45,
  "rps": 0.75,
  "latency_p50_ms": 124.5,
  "latency_p95_ms": 342.1,
  "latency_p99_ms": 567.8,
  "latency_avg_ms": 156.3,
  "tokens_per_second": 28.4,
  "error_rate": 0.0022,
  "uptime_seconds": 3600.5
}
```

!!! note "Окно метрик"
    По умолчанию метрики рассчитываются за последние 60 секунд. Используйте параметр `window_seconds` для изменения окна.

---

## Рекомендации по выбору бэкенда

| Сценарий | Рекомендация |
|---|---|
| Локальная разработка на ноутбуке | llama.cpp + GGUF q4_k_m |
| Продакшен, < 10 RPS | llama.cpp + GGUF q8_0 |
| Продакшен, > 10 RPS | vLLM + полная модель |
| Мобильные/edge устройства | llama.cpp + GGUF q4_k_m |
| Максимальное качество | vLLM + полная модель (f16) |
| Ограниченная VRAM (< 8 GB) | llama.cpp + GGUF q4_k_m |
