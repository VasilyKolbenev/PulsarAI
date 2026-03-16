# Архитектура

Обзор компонентов pulsar-ai, их взаимосвязей и потоков данных.

---

## Общая схема

```mermaid
graph TB
    subgraph CLI["CLI (Click + Rich)"]
        C1[pulsar train]
        C2[pulsar eval]
        C3[pulsar export]
        C4[pulsar serve]
        C5[pulsar agent]
        C6[pulsar pipeline]
    end

    subgraph Core["Core Engine"]
        CL[Config Loader<br/>YAML inheritance]
        TE[Training Engine<br/>SFT / DPO]
        EV[Evaluator]
        EX[Exporter<br/>GGUF / Merged / Hub]
        PE[Pipeline Executor<br/>DAG + conditions]
        AR[Agent Runtime<br/>ReAct / Native tools]
    end

    subgraph Backend["FastAPI Backend"]
        API[REST API<br/>17 routers]
        SSE[SSE Streams<br/>real-time metrics]
        WS[WebSocket<br/>pipelines]
    end

    subgraph Frontend["React Frontend"]
        UI[React 19 + Vite]
        CH[Recharts<br/>графики метрик]
        RF[React Flow<br/>Workflow Builder]
    end

    subgraph Infra["Инфраструктура"]
        HF[HuggingFace<br/>модели + датасеты]
        GPU[NVIDIA GPU<br/>CUDA / cuDNN]
        LC[llama.cpp / vLLM<br/>serving]
    end

    C1 --> CL
    C2 --> CL
    C3 --> CL
    C4 --> LC
    C5 --> AR
    C6 --> PE

    CL --> TE
    CL --> EV
    CL --> EX

    TE --> GPU
    TE --> HF
    EV --> GPU
    EX --> HF

    PE --> TE
    PE --> EV
    PE --> EX

    API --> TE
    API --> EV
    API --> EX
    API --> PE
    API --> AR
    SSE --> TE
    WS --> PE

    UI --> API
    UI --> SSE
    UI --> WS
    CH --> SSE
    RF --> API

    style CLI fill:#4051b5,color:#fff
    style Core fill:#1a237e,color:#fff
    style Backend fill:#283593,color:#fff
    style Frontend fill:#3949ab,color:#fff
    style Infra fill:#757575,color:#fff
```

---

## Компоненты

### CLI

Точка входа для всех операций. Построен на [Click](https://click.palletsprojects.com/) с подсветкой через [Rich](https://rich.readthedocs.io/). Каждая команда (`train`, `eval`, `export`, `serve`, `agent`, `pipeline`) маршрутизирует запрос к соответствующему компоненту Core Engine.

### Config System

Система конфигурации на основе YAML с поддержкой наследования (`inherit`). Позволяет переиспользовать настройки через цепочку конфигов и переопределять любой параметр через CLI.

```mermaid
graph LR
    A[base.yaml] --> D[experiment.yaml]
    B[models/qwen3.5-0.8b.yaml] --> D
    C[tasks/sft.yaml] --> D
    D --> E[CLI overrides]
    E --> F[Final Config]

    style F fill:#2e7d32,color:#fff
```

Приоритет (от низшего к высшему):

| Приоритет | Источник | Пример |
|-----------|---------|--------|
| 1 (низший) | `base.yaml` | seed, logging |
| 2 | Конфиг модели | model_name, lora_r |
| 3 | Конфиг задачи | task-specific параметры |
| 4 | Конфиг эксперимента | dataset, epochs |
| 5 (высший) | CLI overrides | `learning_rate=1e-4` |

Автодетекция hardware: при загрузке конфига система определяет GPU, VRAM, compute capability и автоматически подбирает стратегию обучения (`qlora`, `lora`, `full`, `unsloth`), batch size и gradient accumulation.

### Training Engine

Два режима обучения:

- **SFT** (Supervised Fine-Tuning) -- через HuggingFace `Trainer`. Поддержка LoRA/QLoRA через `peft` и `bitsandbytes`.
- **DPO** (Direct Preference Optimization) -- через TRL `DPOTrainer`. Требует предварительно обученный SFT-адаптер.

Ускорение через [Unsloth](https://github.com/unslothai/unsloth) (2--5x, только Linux).

### Evaluator

Автоматическая оценка обученных моделей:

- Метрики: accuracy, F1, precision, recall
- JSON Parse Rate (для структурированного вывода)
- Confusion matrix
- LLM-as-Judge (для открытых задач)
- Отчёты с per-class анализом ошибок

### Exporter

Три формата экспорта:

| Формат | Описание | Использование |
|--------|----------|---------------|
| **GGUF** | Квантизированный формат | llama.cpp, Ollama |
| **Merged** | Полная модель с вмёрженным LoRA | HuggingFace, vLLM |
| **Hub** | Публикация на HuggingFace Hub | Шаринг, дистрибуция |

### FastAPI Backend

REST API сервер с 17 роутерами, покрывающими все функции платформы. Поддержка SSE (Server-Sent Events) для real-time стримов метрик обучения и WebSocket для мониторинга пайплайнов.

### React Frontend

Single-page application на React 19 + Vite:

- **Recharts** -- графики метрик обучения (loss, lr, GPU memory)
- **React Flow** -- визуальный Workflow Builder с 26 типами нод
- Страницы: Experiments, Eval, Export, Datasets, Workflows, Agents, Settings и др.

### Pipeline Executor

Оркестратор многоэтапных пайплайнов:

- DAG (Directed Acyclic Graph) с топологической сортировкой
- Подстановка переменных (`${step.output}`)
- Условное выполнение шагов (`condition`)
- Параллельное выполнение независимых шагов

### Agent Runtime

Фреймворк для создания AI-агентов:

- Базовый класс `BaseAgent` с циклом Thought -> Action -> Observation
- Два режима tool calling: ReAct (текстовый) и Native (JSON function calling)
- Подключаемая память: buffer, summary, vector
- Guardrails: prompt injection, PII masking, toxicity filtering

---

## Потоки данных

### Жизненный цикл обучения

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Config
    participant Trainer
    participant GPU
    participant UI

    User->>CLI: pulsar train config.yaml
    CLI->>Config: Загрузка + inheritance
    Config->>Config: Auto-detect hardware
    Config-->>CLI: Final config
    CLI->>Trainer: Запуск обучения
    Trainer->>GPU: Загрузка модели (QLoRA 4-bit)
    Trainer->>GPU: Загрузка датасета
    loop Каждый шаг
        Trainer->>GPU: Forward + backward pass
        Trainer-->>UI: SSE: метрики (loss, lr, GPU)
    end
    Trainer-->>CLI: Адаптер сохранён
    CLI-->>User: Training complete!
```

### Выполнение пайплайна

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Executor
    participant Steps
    participant WS as WebSocket

    User->>CLI: pulsar pipeline run pipeline.yaml
    CLI->>Executor: Парсинг DAG
    Executor->>Executor: Топологическая сортировка
    loop Каждый шаг
        Executor->>Executor: Подстановка переменных
        Executor->>Executor: Проверка condition
        alt Condition = true
            Executor->>Steps: Выполнение шага
            Steps-->>Executor: Результат + метрики
            Executor-->>WS: step_completed
        else Condition = false
            Executor-->>WS: step_skipped
        end
    end
    Executor-->>CLI: Pipeline завершён
    Executor-->>WS: pipeline_completed
    CLI-->>User: Результаты
```

---

## Технологический стек

| Слой | Технологии |
|------|-----------|
| **CLI** | Click, Rich, PyYAML |
| **Training** | PyTorch, HuggingFace Transformers, TRL, PEFT, bitsandbytes |
| **Acceleration** | Unsloth (Linux), Flash Attention 2 |
| **Backend** | FastAPI, Uvicorn, SSE-Starlette, WebSockets |
| **Frontend** | React 19, Vite 6, TypeScript, Recharts, React Flow |
| **Serving** | llama.cpp (llama-cpp-python), vLLM |
| **Export** | llama.cpp (convert), HuggingFace Hub |
| **HPO** | Optuna |
| **Tracking** | Встроенный, ClearML, Weights & Biases |
| **Agents** | OpenAI SDK, LangChain-совместимые tools |
