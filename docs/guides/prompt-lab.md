# Prompt Lab

Prompt Lab -- встроенный инструмент для создания, версионирования и тестирования промптов.
Все промпты хранятся централизованно, каждое изменение автоматически получает новую версию,
а тестовая панель позволяет мгновенно проверить результат с реальными переменными.

---

## Создание промпта

Каждый промпт содержит четыре обязательных поля:

| Поле            | Тип      | Описание                                      |
|-----------------|----------|-----------------------------------------------|
| `name`          | `str`    | Уникальное имя промпта                        |
| `system_prompt` | `str`    | Системный промпт (поддерживает шаблонизацию)  |
| `description`   | `str`    | Краткое описание назначения                    |
| `tags`          | `list`   | Теги для поиска и фильтрации                  |

=== "CLI"

    ```bash
    pulsar prompt create \
      --name "customer-support" \
      --system-prompt "Ты — помощник службы поддержки компании {{company}}." \
      --description "Промпт для бота поддержки" \
      --tags support,chatbot
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/prompts \
      -H "Content-Type: application/json" \
      -d '{
        "name": "customer-support",
        "system_prompt": "Ты — помощник службы поддержки компании {{company}}.",
        "description": "Промпт для бота поддержки",
        "tags": ["support", "chatbot"]
      }'
    ```

!!! tip "Именование промптов"
    Используйте kebab-case для имён: `customer-support`, `code-review`, `data-analyst`.
    Это упрощает работу через CLI и API.

---

## Автоматическое версионирование

При каждом обновлении промпта система автоматически создаёт новую версию:

```
customer-support v1  →  первоначальная версия
customer-support v2  →  изменён system_prompt
customer-support v3  →  добавлены параметры модели
```

Версии иммутабельны -- старые версии не удаляются и не изменяются.

=== "CLI"

    ```bash
    # Обновить промпт (автоматически создаст v2)
    pulsar prompt update customer-support \
      --system-prompt "Ты — вежливый помощник компании {{company}}. Отвечай на {{language}}."

    # Список версий
    pulsar prompt versions customer-support
    ```

=== "API"

    ```bash
    # Обновить промпт
    curl -X PUT http://localhost:8000/prompts/customer-support \
      -H "Content-Type: application/json" \
      -d '{
        "system_prompt": "Ты — вежливый помощник компании {{company}}. Отвечай на {{language}}."
      }'

    # Список версий
    curl http://localhost:8000/prompts/customer-support/versions
    ```

---

## Шаблонные переменные

Промпты поддерживают синтаксис `{{variable}}` для динамической подстановки значений:

```text
Ты — помощник компании {{company}}.
Отвечай на языке {{language}}.
Максимальная длина ответа: {{max_length}} слов.
```

При рендеринге переменные заменяются на переданные значения:

```python
from pulsar_ai.prompts import PromptRegistry

registry = PromptRegistry()
prompt = registry.get("customer-support", version=2)

rendered = prompt.render(
    company="Pulsar AI Inc.",
    language="русский",
    max_length=200
)
```

!!! warning "Отсутствующие переменные"
    Если при рендеринге не указана хотя бы одна переменная, будет вызвано исключение
    `MissingVariableError`. Используйте тестовую панель для проверки перед деплоем.

---

## Тестовая панель

Тестовая панель позволяет заполнить все переменные и увидеть отрендеренный результат
прямо в UI или через API.

=== "CLI"

    ```bash
    pulsar prompt test customer-support \
      --var company="Pulsar AI Inc." \
      --var language="русский" \
      --var max_length=200
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/prompts/customer-support/test \
      -H "Content-Type: application/json" \
      -d '{
        "variables": {
          "company": "Pulsar AI Inc.",
          "language": "русский",
          "max_length": "200"
        },
        "version": 2
      }'
    ```

Ответ:

```json
{
  "rendered": "Ты — вежливый помощник компании Pulsar AI Inc. Отвечай на русский.",
  "variables_used": ["company", "language", "max_length"],
  "version": 2
}
```

---

## Сравнение версий (Diff)

Для сравнения двух версий используется эндпоинт diff:

```bash
curl "http://localhost:8000/prompts/customer-support/diff?v1=1&v2=3"
```

Ответ содержит построчные отличия:

```json
{
  "prompt_name": "customer-support",
  "v1": 1,
  "v2": 3,
  "diff": {
    "system_prompt": {
      "v1": "Ты — помощник службы поддержки компании {{company}}.",
      "v2": "Ты — вежливый помощник компании {{company}}. Отвечай на {{language}}.",
      "changes": [
        {"type": "modified", "field": "system_prompt"}
      ]
    },
    "model": {
      "v1": null,
      "v2": "gpt-4o-mini",
      "changes": [
        {"type": "added", "field": "model"}
      ]
    }
  }
}
```

!!! info "Diff в UI"
    В веб-интерфейсе diff отображается в формате side-by-side с подсветкой изменений
    (зелёный -- добавлено, красный -- удалено).

---

## Привязка модели и параметров

К каждой версии промпта можно привязать конкретную модель и параметры генерации:

=== "CLI"

    ```bash
    pulsar prompt update customer-support \
      --model gpt-4o-mini \
      --temperature 0.7 \
      --max-tokens 1024 \
      --top-p 0.9
    ```

=== "API"

    ```bash
    curl -X PUT http://localhost:8000/prompts/customer-support \
      -H "Content-Type: application/json" \
      -d '{
        "model": "gpt-4o-mini",
        "parameters": {
          "temperature": 0.7,
          "max_tokens": 1024,
          "top_p": 0.9
        }
      }'
    ```

| Параметр        | Тип     | По умолчанию | Описание                         |
|-----------------|---------|--------------|----------------------------------|
| `model`         | `str`   | —            | Идентификатор модели             |
| `temperature`   | `float` | `0.7`        | Температура сэмплирования       |
| `max_tokens`    | `int`   | `1024`       | Максимальное число токенов       |
| `top_p`         | `float` | `1.0`        | Nucleus sampling                 |
| `stop`          | `list`  | `[]`         | Стоп-последовательности          |

---

## Полные примеры API

### Создание промпта

```bash
curl -X POST http://localhost:8000/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "code-reviewer",
    "system_prompt": "Review the following {{language}} code. Focus on: {{focus_areas}}.",
    "description": "Промпт для code review",
    "tags": ["code", "review"]
  }'
```

### Получение промпта

```bash
# Последняя версия
curl http://localhost:8000/prompts/code-reviewer

# Конкретная версия
curl http://localhost:8000/prompts/code-reviewer?version=2
```

### Список всех промптов

```bash
# Все промпты
curl http://localhost:8000/prompts

# Фильтр по тегу
curl "http://localhost:8000/prompts?tag=code"
```

### Обновление (создаёт новую версию)

```bash
curl -X PUT http://localhost:8000/prompts/code-reviewer \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "Review {{language}} code. Focus: {{focus_areas}}. Severity: {{severity}}.",
    "model": "gpt-4o",
    "parameters": {"temperature": 0.3}
  }'
```

### Тестирование

```bash
curl -X POST http://localhost:8000/prompts/code-reviewer/test \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "language": "Python",
      "focus_areas": "security, performance",
      "severity": "high"
    }
  }'
```

### Сравнение версий

```bash
curl "http://localhost:8000/prompts/code-reviewer/diff?v1=1&v2=2"
```

### Удаление промпта

```bash
curl -X DELETE http://localhost:8000/prompts/code-reviewer
```

!!! note "Мягкое удаление"
    Удаление помечает промпт как архивный. Все версии сохраняются и могут быть
    восстановлены через API: `POST /prompts/code-reviewer/restore`.
