# Observability

Модуль наблюдаемости предоставляет три компонента: **Tracer** для трассировки запросов,
**CostTracker** для учёта стоимости API-вызовов и **SemanticCache** для кэширования
ответов с экономией токенов.

---

## Tracer

Трассировщик в стиле OpenTelemetry для отслеживания цепочек вызовов LLM, инструментов
и других операций.

### Базовое использование

```python
from pulsar_ai.observability import get_tracer

tracer = get_tracer("my-app")

# Создание трейса
with tracer.start_trace("user-request") as trace:
    # Span для предобработки
    with trace.start_span("preprocessing") as span:
        span.set_attribute("input_length", len(user_input))
        processed = preprocess(user_input)

    # Span для вызова LLM
    with trace.start_span("llm_call") as span:
        response = model.generate(processed)
        span.record_llm_call(
            model="gpt-4o-mini",
            input_tokens=150,
            output_tokens=320,
            latency_ms=1250
        )

    # Span для постобработки
    with trace.start_span("postprocessing") as span:
        result = postprocess(response)
```

### Структура трейса

```json
{
  "trace_id": "tr_abc123",
  "name": "user-request",
  "duration_ms": 1580,
  "spans": [
    {
      "span_id": "sp_001",
      "name": "preprocessing",
      "duration_ms": 12,
      "attributes": {"input_length": 245}
    },
    {
      "span_id": "sp_002",
      "name": "llm_call",
      "duration_ms": 1250,
      "llm_call": {
        "model": "gpt-4o-mini",
        "input_tokens": 150,
        "output_tokens": 320
      }
    },
    {
      "span_id": "sp_003",
      "name": "postprocessing",
      "duration_ms": 8
    }
  ]
}
```

!!! tip "Вложенные span'ы"
    Span'ы могут быть вложенными для отслеживания сложных цепочек:

    ```python
    with trace.start_span("agent_loop") as parent:
        for i in range(iterations):
            with parent.start_span(f"iteration_{i}") as child:
                child.record_llm_call(...)
    ```

---

## CostTracker

Отслеживание стоимости API-вызовов с встроенными ценами для популярных моделей.

### Встроенные цены

| Модель            | Input ($/1M токенов) | Output ($/1M токенов) |
|-------------------|---------------------:|----------------------:|
| `gpt-4o`          |                 2.50 |                 10.00 |
| `gpt-4o-mini`     |                 0.15 |                  0.60 |
| `claude-3-5-sonnet` |               3.00 |                 15.00 |
| `claude-3-haiku`  |                 0.25 |                  1.25 |
| `llama-3-8b`      |                 0.05 |                  0.05 |
| `mistral-7b`      |                 0.05 |                  0.05 |
| `local`           |                 0.00 |                  0.00 |

### Использование

```python
from pulsar_ai.observability import CostTracker

tracker = CostTracker()

# Записать вызов
tracker.record(
    model="gpt-4o-mini",
    input_tokens=500,
    output_tokens=1200
)

# Ещё один вызов
tracker.record(
    model="gpt-4o",
    input_tokens=1000,
    output_tokens=2000
)

# Оценка стоимости одного вызова
cost = tracker.estimate_cost(
    model="gpt-4o",
    input_tokens=5000,
    output_tokens=10000
)
print(f"Оценка: ${cost:.4f}")  # $0.1125

# Сводка по всем вызовам
summary = tracker.get_summary()
```

### Структура сводки

```json
{
  "total_cost": 0.0245,
  "total_input_tokens": 1500,
  "total_output_tokens": 3200,
  "calls_count": 2,
  "by_model": {
    "gpt-4o-mini": {
      "cost": 0.0008,
      "input_tokens": 500,
      "output_tokens": 1200,
      "calls": 1
    },
    "gpt-4o": {
      "cost": 0.0225,
      "input_tokens": 1000,
      "output_tokens": 2000,
      "calls": 1
    }
  }
}
```

### Бюджетный лимит

```python
tracker = CostTracker(budget_limit=10.0)  # $10 лимит

tracker.record(model="gpt-4o", input_tokens=1000, output_tokens=2000)

if tracker.is_over_budget():
    print("Бюджет превышен!")
```

!!! warning "Бюджетный контроль"
    При превышении `budget_limit` трекер не блокирует вызовы автоматически.
    Используйте `is_over_budget()` для проверки и реализации своей логики ограничения.

---

## SemanticCache

LRU-кэш с TTL для семантически похожих запросов. Экономит токены и снижает задержку
при повторяющихся запросах.

### Использование

```python
from pulsar_ai.observability import SemanticCache

cache = SemanticCache(
    max_size=1000,      # максимум записей
    ttl_seconds=3600    # время жизни: 1 час
)

# Паттерн get/set
prompt = "Какая столица Франции?"

# Проверить кэш
cached = cache.get(prompt)
if cached:
    response = cached
else:
    response = model.generate(prompt)
    cache.set(prompt, response, tokens_used=45)
```

### Статистика кэша

```python
stats = cache.stats()
```

```json
{
  "size": 342,
  "max_size": 1000,
  "hits": 1247,
  "misses": 891,
  "hit_rate": 0.583,
  "tokens_saved": 56120,
  "evictions": 15
}
```

| Метрика        | Описание                                  |
|----------------|-------------------------------------------|
| `size`         | Текущее количество записей в кэше         |
| `max_size`     | Максимальная ёмкость                      |
| `hits`         | Количество попаданий в кэш               |
| `misses`       | Количество промахов                       |
| `hit_rate`     | Процент попаданий (hits / total)          |
| `tokens_saved` | Сколько токенов сэкономлено               |
| `evictions`    | Количество вытесненных записей (LRU)      |

!!! info "Семантическое сравнение"
    Кэш использует нормализацию текста (lowercase, удаление лишних пробелов)
    для сопоставления запросов. Запросы «Какая столица Франции?» и
    «какая столица франции?» будут считаться одинаковыми.

### Полный пример

```python
from pulsar_ai.observability import get_tracer, CostTracker, SemanticCache

tracer = get_tracer("chatbot")
tracker = CostTracker(budget_limit=50.0)
cache = SemanticCache(max_size=500, ttl_seconds=1800)

def smart_generate(prompt: str) -> str:
    with tracer.start_trace("generate") as trace:
        # 1. Проверить кэш
        with trace.start_span("cache_lookup"):
            cached = cache.get(prompt)
            if cached:
                return cached

        # 2. Вызвать модель
        with trace.start_span("llm_call") as span:
            response = model.generate(prompt)
            input_tokens = count_tokens(prompt)
            output_tokens = count_tokens(response)

            span.record_llm_call(
                model="gpt-4o-mini",
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            # 3. Записать стоимость
            tracker.record("gpt-4o-mini", input_tokens, output_tokens)

        # 4. Сохранить в кэш
        cache.set(prompt, response, tokens_used=output_tokens)

        return response
```
