# Canary + A/B Testing

Инструменты для безопасного развёртывания моделей: **Canary Deployer** для постепенного
переключения трафика с автоматическим откатом, и **A/B Tester** для сравнения вариантов
с статистической значимостью.

---

## CanaryDeployer

Канареечный деплой направляет небольшой процент трафика на новую модель (canary),
а остальной -- на текущую (primary). При обнаружении проблем происходит автоматический
откат.

### Параметры

| Параметр            | Тип     | По умолчанию | Описание                                  |
|---------------------|---------|--------------|-------------------------------------------|
| `primary`           | `str`   | —            | URL основной модели                       |
| `canary`            | `str`   | —            | URL канареечной модели                    |
| `canary_weight`     | `float` | `0.1` (10%)  | Доля трафика на canary                    |
| `error_threshold`   | `float` | `0.05` (5%)  | Порог ошибок для автоотката               |
| `promote_after`     | `int`   | `1000`       | Кол-во запросов для автопродвижения       |

### Использование

```python
from pulsar_ai.deployment import CanaryDeployer

deployer = CanaryDeployer(
    primary="http://localhost:8081/v1/chat",
    canary="http://localhost:8082/v1/chat",
    canary_weight=0.1,          # 10% трафика на canary
    error_threshold=0.05,       # откат при >5% ошибок
    promote_after=1000           # продвижение после 1000 успешных запросов
)

# Маршрутизация запроса
response = deployer.route(request)

# Запись результата
deployer.record(
    request_id="req-001",
    target="canary",             # куда ушёл запрос
    success=True,
    latency_ms=245
)
```

### Автоматический откат

Если процент ошибок canary превышает `error_threshold`, происходит автооткат:

```python
# Проверка состояния
status = deployer.status()
```

```json
{
  "state": "canary_active",
  "primary_requests": 900,
  "canary_requests": 100,
  "canary_errors": 2,
  "canary_error_rate": 0.02,
  "progress": "100/1000 (10%)"
}
```

!!! warning "Автооткат"
    При срабатывании автоотката весь трафик возвращается на primary, а в логе
    появляется запись с причиной отката. Canary не удаляется -- можно исправить
    проблему и запустить деплой заново.

### Автопродвижение

Если canary обработал `promote_after` запросов с ошибками ниже порога,
происходит автоматическое продвижение -- canary становится новым primary:

```json
{
  "state": "promoted",
  "message": "Canary promoted to primary after 1000 successful requests",
  "canary_error_rate": 0.018
}
```

---

## ABTester

A/B-тестирование для сравнения двух и более вариантов модели с определением победителя
на основе метрик.

### Параметры

| Параметр        | Тип    | По умолчанию | Описание                              |
|-----------------|--------|--------------|---------------------------------------|
| `variants`      | `dict` | —            | Варианты с весами                     |
| `min_samples`   | `int`  | `100`        | Минимум запросов для определения победителя |

### Использование

```python
from pulsar_ai.deployment import ABTester

tester = ABTester(
    variants={
        "model-a": {"weight": 0.5, "endpoint": "http://localhost:8081/v1/chat"},
        "model-b": {"weight": 0.5, "endpoint": "http://localhost:8082/v1/chat"},
    },
    min_samples=100
)

# Получить вариант для запроса
variant = tester.assign(user_id="user-123")
# variant = "model-a" или "model-b"

# Записать метрику
tester.record_metric(
    variant="model-a",
    metric_name="satisfaction",
    value=4.5
)

tester.record_metric(
    variant="model-a",
    metric_name="latency_ms",
    value=230
)
```

### Результаты

```python
results = tester.get_results()
```

```json
{
  "variants": {
    "model-a": {
      "samples": 156,
      "metrics": {
        "satisfaction": {"mean": 4.2, "std": 0.8, "count": 156},
        "latency_ms": {"mean": 245, "std": 52, "count": 156}
      }
    },
    "model-b": {
      "samples": 144,
      "metrics": {
        "satisfaction": {"mean": 4.5, "std": 0.7, "count": 144},
        "latency_ms": {"mean": 312, "std": 78, "count": 144}
      }
    }
  },
  "winner": {
    "variant": "model-b",
    "metric": "satisfaction",
    "confidence": 0.95,
    "improvement": "+7.1%"
  },
  "sufficient_samples": true
}
```

!!! info "Определение победителя"
    Победитель определяется при достижении `min_samples` для каждого варианта.
    Используется статистический тест для проверки значимости разницы (p < 0.05).

---

## Canary vs A/B: когда что использовать

| Сценарий                                   | Рекомендация   |
|--------------------------------------------|----------------|
| Обновление модели в продакшене              | Canary         |
| Сравнение двух архитектур                   | A/B            |
| Минимизация риска при деплое                | Canary         |
| Выбор лучшего промпта                       | A/B            |
| Постепенная миграция на новую версию        | Canary         |
| Оптимизация UX-метрик                       | A/B            |

!!! tip "Комбинирование подходов"
    Типичный workflow:

    1. **A/B-тест** -- сравните варианты на ограниченной аудитории
    2. **Canary** -- деплойте победителя A/B-теста через канареечный деплой
    3. **Promote** -- после успешного canary продвиньте модель в production

    ```python
    # 1. A/B определил победителя: model-b
    winner = tester.get_results()["winner"]["variant"]

    # 2. Канареечный деплой победителя
    deployer = CanaryDeployer(
        primary="http://current-production:8081/v1/chat",
        canary=f"http://{winner}:8082/v1/chat",
        canary_weight=0.1,
        promote_after=1000
    )
    ```
