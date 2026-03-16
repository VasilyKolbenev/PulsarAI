# Agent Framework

Pulsar Agent Framework позволяет создавать, тестировать и деплоить AI-агентов с поддержкой
инструментов, памяти и guardrails. Агенты работают в режиме ReAct или с нативным
tool calling.

---

## Создание агента

Инициализация нового агента создаёт директорию с шаблоном конфигурации:

```bash
pulsar agent init my-assistant
```

Структура:

```
my-assistant/
  config.yaml       # конфигурация агента
  tools/             # пользовательские инструменты
  tests/             # тесты
```

---

## Конфигурация агента

Файл `config.yaml` описывает все параметры агента:

```yaml
agent:
  name: my-assistant
  system_prompt: |
    Ты — полезный ассистент. Отвечай кратко и по существу.
    Используй инструменты когда нужно найти или прочитать файлы.

model:
  base_url: http://localhost:8000/v1    # OpenAI-compatible endpoint
  name: meta-llama/Llama-3-8B          # или gpt-4o, claude-3-5-sonnet

tools:
  - search_files
  - read_file
  - list_directory
  - calculate

memory:
  strategy: sliding_window
  max_tokens: 4096

guardrails:
  max_iterations: 10
  max_tokens: 2048
```

### Параметры конфигурации

| Секция        | Параметр         | Тип    | Описание                              |
|---------------|------------------|--------|---------------------------------------|
| `agent`       | `name`           | `str`  | Имя агента                            |
| `agent`       | `system_prompt`  | `str`  | Системный промпт                      |
| `model`       | `base_url`       | `str`  | URL OpenAI-совместимого API           |
| `model`       | `name`           | `str`  | Имя модели                            |
| `tools`       | —                | `list` | Список доступных инструментов         |
| `memory`      | `strategy`       | `str`  | Стратегия памяти                      |
| `memory`      | `max_tokens`     | `int`  | Лимит токенов в контексте             |
| `guardrails`  | `max_iterations` | `int`  | Максимум итераций ReAct-цикла         |
| `guardrails`  | `max_tokens`     | `int`  | Максимум токенов ответа               |

---

## Встроенные инструменты

| Инструмент       | Описание                                          |
|-------------------|---------------------------------------------------|
| `search_files`    | Поиск файлов по имени или glob-паттерну           |
| `read_file`       | Чтение содержимого файла                          |
| `list_directory`  | Список файлов и директорий                        |
| `calculate`       | Математические вычисления                         |

!!! tip "Пользовательские инструменты"
    Добавляйте свои инструменты в директорию `tools/`. Каждый инструмент --
    Python-функция с декоратором `@tool`:

    ```python
    from pulsar_ai.agents import tool

    @tool(description="Поиск в базе данных по запросу")
    def search_database(query: str, limit: int = 10) -> list[dict]:
        """Ищет записи в БД по текстовому запросу."""
        # ваша логика
        return results
    ```

---

## Тестирование

### Интерактивный REPL

```bash
pulsar agent test config.yaml
```

Запускает интерактивную сессию для тестирования агента:

```
Agent: my-assistant (Llama-3-8B)
Tools: search_files, read_file, list_directory, calculate
Type /quit to exit

> Найди все Python-файлы в текущей директории

[tool: search_files("*.py")]
Найдено 12 файлов:
  - main.py
  - config.py
  - utils/helpers.py
  ...

> Прочитай main.py

[tool: read_file("main.py")]
Файл main.py содержит точку входа приложения...
```

### Нативный tool calling

Для моделей с поддержкой нативного tool calling (GPT-4o, Claude, Llama 3.1+):

```bash
pulsar agent test config.yaml --native-tools
```

!!! info "ReAct vs Native Tool Calling"

    | Режим         | Описание                                          | Модели                    |
    |---------------|---------------------------------------------------|---------------------------|
    | ReAct         | Модель пишет Thought/Action/Observation           | Любая текстовая модель    |
    | Native Tools  | Модель использует встроенный function calling      | GPT-4o, Claude, Llama 3.1+|

    Native tool calling обычно точнее и быстрее, но требует поддержки со стороны модели.

---

## Деплой

Запуск агента как HTTP-сервиса:

```bash
pulsar agent serve config.yaml --port 8081
```

Сервер предоставляет два эндпоинта:

### POST /v1/agent/chat

Основной эндпоинт для взаимодействия с агентом:

```bash
curl -X POST http://localhost:8081/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Найди все TODO в проекте"}
    ],
    "session_id": "session-123"
  }'
```

Ответ:

```json
{
  "response": "Найдено 5 TODO в проекте:\n1. main.py:42 — TODO: add error handling\n...",
  "tool_calls": [
    {"tool": "search_files", "args": {"pattern": "*.py"}, "result": "..."}
  ],
  "tokens_used": 1247,
  "iterations": 3
}
```

### GET /v1/agent/health

```bash
curl http://localhost:8081/v1/agent/health
```

```json
{
  "status": "healthy",
  "agent": "my-assistant",
  "model": "meta-llama/Llama-3-8B",
  "tools": ["search_files", "read_file", "list_directory", "calculate"],
  "uptime_seconds": 3421
}
```

---

## Память

Стратегия `sliding_window` сохраняет последние N токенов контекста:

```yaml
memory:
  strategy: sliding_window
  max_tokens: 4096        # максимум токенов в окне
```

При превышении лимита старые сообщения удаляются, начиная с самых ранних,
сохраняя системный промпт и последние сообщения.

!!! warning "Потеря контекста"
    При длинных сессиях агент может «забыть» ранние сообщения. Для задач, требующих
    полного контекста, увеличьте `max_tokens` или используйте явные ссылки на предыдущие
    действия в промпте.
