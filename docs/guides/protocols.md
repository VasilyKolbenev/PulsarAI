# Protocols (MCP, A2A, API Gateway)

Pulsar AI поддерживает три протокола интеграции: **MCP** (Model Context Protocol) для
подключения инструментов, **A2A** (Agent-to-Agent) для межагентной коммуникации
и **API Gateway** для маршрутизации и балансировки нагрузки.

---

## MCP (Model Context Protocol)

Model Context Protocol -- стандарт Anthropic для подключения внешних инструментов
и источников данных к AI-моделям.

### Транспорты

| Транспорт           | Описание                              | Используется для            |
|---------------------|---------------------------------------|-----------------------------|
| `stdio`             | Стандартный ввод/вывод                | Локальные инструменты       |
| `sse`               | Server-Sent Events                    | Веб-серверы (однонаправленный поток) |
| `streamable_http`   | HTTP с поддержкой стриминга           | Универсальный транспорт     |

### Конфигурация

=== "API"

    ```bash
    curl -X POST http://localhost:8000/protocols/mcp/configure \
      -H "Content-Type: application/json" \
      -d '{
        "transport": "streamable_http",
        "port": 8090,
        "tools": [
          {
            "name": "search_docs",
            "description": "Search documentation by query",
            "parameters": {
              "type": "object",
              "properties": {
                "query": {"type": "string"}
              },
              "required": ["query"]
            }
          }
        ]
      }'
    ```

=== "CLI"

    ```bash
    pulsar protocol mcp configure \
      --transport streamable_http \
      --port 8090 \
      --config mcp_tools.yaml
    ```

### JSON-RPC методы

MCP использует JSON-RPC 2.0 для обмена сообщениями:

| Метод            | Описание                           | Направление       |
|------------------|------------------------------------|--------------------|
| `initialize`     | Инициализация соединения           | Client → Server    |
| `tools/list`     | Список доступных инструментов      | Client → Server    |
| `tools/call`     | Вызов инструмента                  | Client → Server    |

Пример вызова `tools/list`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

Ответ:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "search_docs",
        "description": "Search documentation by query",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string"}
          }
        }
      }
    ]
  }
}
```

---

## A2A (Agent-to-Agent)

Протокол Google для взаимодействия между AI-агентами. Позволяет агентам обнаруживать
друг друга и делегировать задачи.

### Agent Card

Каждый агент публикует карточку по адресу `/.well-known/agent.json`:

```json
{
  "name": "research-assistant",
  "description": "Agent for research and analysis tasks",
  "url": "http://localhost:8081",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "search",
      "name": "Web Search",
      "description": "Search the web for information"
    }
  ]
}
```

### Состояния задач

```
submitted → working → completed
                   → failed
                   → canceled
```

| Состояние    | Описание                              |
|-------------|---------------------------------------|
| `submitted` | Задача принята, ожидает обработки     |
| `working`   | Агент обрабатывает задачу             |
| `completed` | Задача успешно выполнена              |
| `failed`    | Задача завершилась с ошибкой          |
| `canceled`  | Задача отменена                       |

### A2A методы

| Метод             | Описание                       |
|-------------------|--------------------------------|
| `tasks/send`      | Отправить задачу агенту        |
| `tasks/get`       | Получить статус задачи         |
| `tasks/cancel`    | Отменить задачу                |

Пример отправки задачи:

```bash
curl -X POST http://localhost:8081/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tasks/send",
    "params": {
      "id": "task-001",
      "message": {
        "role": "user",
        "parts": [
          {"type": "text", "text": "Найди информацию о трансформерах"}
        ]
      }
    }
  }'
```

### Конфигурация A2A

```bash
curl -X POST http://localhost:8000/protocols/a2a/configure \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "research-assistant",
    "description": "Agent for research tasks",
    "skills": ["search", "summarize"],
    "port": 8081
  }'
```

---

## API Gateway

API Gateway обеспечивает маршрутизацию запросов, аутентификацию,
rate limiting и балансировку нагрузки между агентами.

### Регистрация агента в Gateway

```bash
curl -X POST http://localhost:8000/protocols/gateway/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "assistant-1",
    "endpoint": "http://localhost:8081",
    "auth_method": "api_key",
    "rate_limit": 100,
    "load_balancer": "round_robin"
  }'
```

### Параметры Gateway

| Параметр         | Тип    | Описание                                   |
|------------------|--------|--------------------------------------------|
| `agent_id`       | `str`  | Уникальный идентификатор агента            |
| `endpoint`       | `str`  | URL эндпоинта агента                       |
| `auth_method`    | `str`  | Метод аутентификации: `api_key`, `oauth`, `none` |
| `rate_limit`     | `int`  | Максимум запросов в минуту                 |
| `load_balancer`  | `str`  | Стратегия балансировки: `round_robin`      |

### Маршрутизация

Gateway автоматически маршрутизирует запросы к зарегистрированным агентам:

```bash
# Запрос через Gateway
curl -X POST http://localhost:8000/gateway/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer pulsar_xxxxx" \
  -d '{
    "agent_id": "assistant-1",
    "messages": [
      {"role": "user", "content": "Привет!"}
    ]
  }'
```

!!! tip "Балансировка нагрузки"
    При регистрации нескольких экземпляров одного агента Gateway распределяет
    запросы между ними по стратегии `round_robin`.

---

## Сводка протоколов

Общая информация по всем настроенным протоколам:

```bash
curl http://localhost:8000/protocols/summary
```

```json
{
  "mcp": {
    "enabled": true,
    "transport": "streamable_http",
    "port": 8090,
    "tools_count": 5
  },
  "a2a": {
    "enabled": true,
    "agent_name": "research-assistant",
    "skills": ["search", "summarize"],
    "port": 8081
  },
  "gateway": {
    "enabled": true,
    "registered_agents": 3,
    "total_requests": 1247
  }
}
```

!!! info "Независимость протоколов"
    Каждый протокол настраивается и работает независимо. Можно использовать только MCP
    без A2A, или только Gateway -- любую комбинацию по необходимости.
