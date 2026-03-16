---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# pulsar-ai

**Универсальный пайплайн файнтюнинга LLM**

Платформа полного цикла для файнтюнинга языковых моделей: от подготовки данных до продакшн-деплоя.
Web UI, CLI, REST API -- один инструмент для обучения, оценки, экспорта и сервинга моделей
с поддержкой агентов, workflow, guardrails и протоколов интеграции.

</div>

---

## Возможности

<div class="grid" markdown>

<div class="card" markdown>

### :material-school: Training

SFT и DPO файнтюнинг с LoRA/QLoRA.
Поддержка Qwen, Llama, Mistral.
Real-time метрики в Web UI.

</div>

<div class="card" markdown>

### :material-chart-bar: Eval

Автоматическая оценка: accuracy, F1,
JSON parse rate, confusion matrix.
LLM-as-Judge для открытых задач.

</div>

<div class="card" markdown>

### :material-export: Export

GGUF (q4_k_m, q8_0, f16), merged LoRA,
push на HuggingFace Hub.
Одна команда -- готовый артефакт.

</div>

<div class="card" markdown>

### :material-server: Serving

llama.cpp и vLLM бэкенды.
OpenAI-совместимый API (`/v1/chat/completions`).
Метрики latency, RPS, tokens/sec.

</div>

<div class="card" markdown>

### :material-sitemap: Workflow Builder

Визуальный конструктор ML-пайплайнов.
26 типов нод: data, training, eval,
export, agent, protocols, guardrails.

</div>

<div class="card" markdown>

### :material-robot: Agent Framework

Создание AI-агентов с инструментами и памятью.
Native function calling и ReAct.
Деплой агента как REST API.

</div>

<div class="card" markdown>

### :material-monitor-dashboard: Monitoring

Real-time мониторинг GPU, CPU, RAM.
Температура, потребление энергии.
SSE-поток метрик каждые 2 секунды.

</div>

<div class="card" markdown>

### :material-database: Model Registry

Версионирование моделей с жизненным циклом:
registered -> staging -> production -> archived.
Сравнение метрик между версиями.

</div>

<div class="card" markdown>

### :material-tune: HPO

Автоматический поиск гиперпараметров
через Optuna. Log-uniform, categorical,
integer search spaces.

</div>

<div class="card" markdown>

### :material-text-box-edit: Prompt Lab

Версионирование промптов, шаблоны
с переменными, diff между версиями,
тестовая панель.

</div>

<div class="card" markdown>

### :material-protocol: Protocols (MCP / A2A)

Model Context Protocol, Google A2A,
API Gateway. Интеграция с внешними
системами через стандартные протоколы.

</div>

<div class="card" markdown>

### :material-shield-check: Guardrails

Защита входа и выхода модели: PII,
prompt injection, toxicity, regex,
JSON schema, length validation.

</div>

</div>

---

## Архитектура

```mermaid
graph LR
    A[Data] --> B[Training<br/>SFT / DPO]
    B --> C[Eval<br/>Accuracy, F1]
    C --> D[Export<br/>GGUF / Merged / Hub]
    D --> E[Serve<br/>llama.cpp / vLLM]

    style A fill:#4051b5,color:#fff
    style B fill:#4051b5,color:#fff
    style C fill:#4051b5,color:#fff
    style D fill:#4051b5,color:#fff
    style E fill:#4051b5,color:#fff
```

---

## Быстрые ссылки

<div class="grid" markdown>

<div class="card" markdown>

### [:material-rocket-launch: Быстрый старт](getting-started/quickstart.md)

Запустите первый эксперимент за 5 минут.

</div>

<div class="card" markdown>

### [:material-download: Установка](getting-started/installation.md)

Полное руководство по установке и настройке.

</div>

<div class="card" markdown>

### [:material-console: CLI справочник](reference/cli.md)

Все команды `pulsar` с примерами.

</div>

<div class="card" markdown>

### [:material-api: API Reference](reference/api.md)

REST API эндпоинты и Swagger-документация.

</div>

</div>
