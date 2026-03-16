# Guardrails

Guardrails -- система защитных правил для фильтрации входных и выходных данных AI-моделей.
Поддерживает обнаружение PII, инъекций, токсичного контента, валидацию JSON-схем
и пользовательские regex-правила.

---

## Типы правил

| Тип            | Описание                                   | Детектируемые паттерны                           |
|----------------|--------------------------------------------|-------------------------------------------------|
| `pii`          | Персональные данные                        | email, phone, SSN, credit card, IP, api_key      |
| `injection`    | Prompt injection                           | 7 паттернов (ignore instructions, system prompt и др.) |
| `toxicity`     | Токсичный контент                          | Блоклист ключевых слов                           |
| `regex`        | Пользовательские регулярные выражения      | Любые regex-паттерны                             |
| `json_schema`  | Валидация JSON                             | Проверка по JSON Schema                          |
| `length`       | Ограничение длины                          | min/max количество символов                      |

---

## Действия (Actions)

При срабатывании правила выполняется одно из действий:

| Действие | Описание                                            |
|----------|-----------------------------------------------------|
| `block`  | Блокировать запрос/ответ полностью                  |
| `mask`   | Заменить обнаруженные данные масками                |
| `warn`   | Пропустить, но выдать предупреждение                |
| `log`    | Пропустить, только записать в лог                   |

---

## PII-маскирование

При действии `mask` обнаруженные PII заменяются на типизированные маски:

| Тип PII        | Маска                    | Пример                                    |
|----------------|--------------------------|--------------------------------------------|
| Email          | `[EMAIL_REDACTED]`       | `user@mail.com` → `[EMAIL_REDACTED]`       |
| Телефон        | `[PHONE_REDACTED]`       | `+7-999-123-4567` → `[PHONE_REDACTED]`     |
| SSN            | `[SSN_REDACTED]`         | `123-45-6789` → `[SSN_REDACTED]`           |
| Кредитная карта| `[CC_REDACTED]`          | `4111-1111-1111-1111` → `[CC_REDACTED]`    |
| IP-адрес       | `[IP_REDACTED]`          | `192.168.1.1` → `[IP_REDACTED]`            |
| API-ключ       | `[API_KEY_REDACTED]`     | `sk-abc123...` → `[API_KEY_REDACTED]`      |

---

## Использование в Python

### Фабричные функции

```python
from pulsar_ai.guardrails import create_input_guard, create_output_guard

# Входной guardrail: блокировать инъекции, маскировать PII
input_guard = create_input_guard(
    rules=[
        {"type": "injection", "action": "block"},
        {"type": "pii", "action": "mask", "categories": ["email", "phone", "cc"]},
        {"type": "length", "action": "block", "max": 10000},
    ]
)

# Выходной guardrail: маскировать PII, валидировать JSON
output_guard = create_output_guard(
    rules=[
        {"type": "pii", "action": "mask"},
        {"type": "toxicity", "action": "block"},
        {"type": "json_schema", "action": "warn", "schema": {
            "type": "object",
            "required": ["answer", "confidence"]
        }},
    ]
)
```

### Применение к тексту

```python
# Проверка входного текста
result = input_guard.check("Мой email: user@mail.com, позвони +7-999-123-4567")

if result.blocked:
    print(f"Заблокировано: {result.reason}")
else:
    safe_text = result.text
    # "Мой email: [EMAIL_REDACTED], позвони [PHONE_REDACTED]"
    print(safe_text)

# Проверка выходного текста
output_result = output_guard.check(model_response)

if output_result.warnings:
    for warning in output_result.warnings:
        print(f"Предупреждение: {warning}")
```

### Полный пример с моделью

```python
from pulsar_ai.guardrails import create_input_guard, create_output_guard

input_guard = create_input_guard(
    rules=[
        {"type": "injection", "action": "block"},
        {"type": "pii", "action": "mask"},
    ]
)

output_guard = create_output_guard(
    rules=[
        {"type": "pii", "action": "mask"},
        {"type": "toxicity", "action": "block"},
    ]
)

def safe_chat(user_message: str) -> str:
    # 1. Проверить вход
    input_result = input_guard.check(user_message)
    if input_result.blocked:
        return f"Запрос заблокирован: {input_result.reason}"

    # 2. Отправить безопасный текст модели
    response = model.generate(input_result.text)

    # 3. Проверить выход
    output_result = output_guard.check(response)
    if output_result.blocked:
        return "Ответ заблокирован системой безопасности."

    return output_result.text
```

---

## Использование в Workflow Builder

В визуальном редакторе workflow используйте ноды `inputGuard` и `outputGuard`:

```yaml
workflow:
  name: safe-chatbot
  nodes:
    - id: input_guard
      type: inputGuard
      config:
        rules:
          - type: injection
            action: block
          - type: pii
            action: mask

    - id: llm
      type: llm
      config:
        model: gpt-4o-mini
        system_prompt: "Ты — полезный ассистент."

    - id: output_guard
      type: outputGuard
      config:
        rules:
          - type: pii
            action: mask
          - type: toxicity
            action: block

  edges:
    - from: input_guard
      to: llm
    - from: llm
      to: output_guard
```

!!! tip "Порядок нод"
    Размещайте `inputGuard` **перед** нодой LLM, а `outputGuard` -- **после**.
    Это обеспечивает фильтрацию как входных данных, так и ответа модели.

---

## Guardrails в агентах

Агенты поддерживают два дополнительных ограничения:

```yaml
guardrails:
  max_iterations: 10    # максимум итераций ReAct-цикла
  max_tokens: 2048      # максимум токенов в ответе
```

| Параметр          | По умолчанию | Описание                                         |
|-------------------|--------------|--------------------------------------------------|
| `max_iterations`  | `10`         | Предотвращает бесконечные циклы вызова инструментов |
| `max_tokens`      | `2048`       | Ограничивает длину генерируемого ответа           |

!!! warning "Бесконечные циклы"
    Без `max_iterations` агент может застрять в цикле повторных вызовов инструментов.
    Всегда устанавливайте разумный лимит (5-20 в зависимости от сложности задачи).

---

## Пользовательские regex-правила

Создавайте собственные правила с помощью регулярных выражений:

```python
input_guard = create_input_guard(
    rules=[
        {
            "type": "regex",
            "action": "block",
            "patterns": [
                r"DROP\s+TABLE",
                r"DELETE\s+FROM",
                r"<script>.*</script>",
            ],
            "message": "Обнаружен потенциально опасный паттерн"
        },
    ]
)
```

!!! note "Комбинирование правил"
    Правила применяются последовательно. Если любое правило с действием `block`
    срабатывает, обработка прекращается. Правила с `mask` применяются к тексту,
    и результат передаётся следующему правилу.
