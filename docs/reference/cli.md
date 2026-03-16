# CLI Reference

Все команды pulsar-ai доступны через точку входа `pulsar`. CLI построен на [Click](https://click.palletsprojects.com/) с подсветкой через [Rich](https://rich.readthedocs.io/).

## Глобальные опции

```
pulsar [--verbose/-v] [--version] <command>
```

| Опция | Тип | Описание |
|-------|-----|----------|
| `--verbose`, `-v` | flag | Включить отладочный вывод (DEBUG-уровень логирования) |
| `--version` | flag | Показать версию пакета и выйти |

---

## pulsar train

Запуск обучения модели (SFT или DPO).

```bash
pulsar train <config.yaml> [overrides...] [--task sft|dpo|auto] [--base-model PATH] [--resume PATH]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `config.yaml` | PATH (аргумент) | -- | Путь к YAML-конфигу эксперимента |
| `overrides` | key=value... | -- | CLI-переопределения параметров конфига |
| `--task` | `sft` / `dpo` / `auto` | `auto` | Тип задачи обучения. `auto` определяет по конфигу |
| `--base-model` | PATH | `None` | Путь к SFT-адаптеру (для DPO-обучения) |
| `--resume` | PATH | `None` | Возобновить обучение из директории чекпоинта |

!!! tip "CLI-переопределения"
    Любой параметр конфига можно переопределить через `key=value` аргументы.
    Они имеют наивысший приоритет и применяются поверх всех `inherit`-конфигов.

**Примеры:**

=== "SFT-обучение"

    ```bash
    pulsar train experiments/cam-sft.yaml
    ```

=== "DPO-обучение"

    ```bash
    pulsar train experiments/cam-dpo.yaml \
      --task dpo \
      --base-model ./outputs/cam-sft
    ```

=== "С переопределениями"

    ```bash
    pulsar train experiments/cam-sft.yaml \
      learning_rate=1e-4 \
      epochs=5 \
      batch_size=4
    ```

---

## pulsar eval

Оценка обученной модели на тестовых данных.

```bash
pulsar eval --model PATH --test-data PATH [--config PATH] [--batch-size N] [--output PATH]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--model` | PATH | **обязательный** | Путь к модели или директории с адаптером |
| `--test-data` | PATH | **обязательный** | Путь к тестовому датасету |
| `--config` | PATH | `None` | Конфиг с настройками оценки |
| `--batch-size` | int | `8` | Размер батча для инференса |
| `--output` | PATH | `None` | Директория для отчёта об оценке |

**Примеры:**

=== "Базовая оценка"

    ```bash
    pulsar eval \
      --model ./outputs/cam-sft/lora \
      --test-data data/test.csv
    ```

=== "С отчётом"

    ```bash
    pulsar eval \
      --model ./outputs/cam-sft/lora \
      --test-data data/test.csv \
      --output reports/ \
      --batch-size 16
    ```

---

## pulsar export

Экспорт модели в продакшен-формат.

```bash
pulsar export --model PATH [--format gguf|merged|hub] [--quant q4_k_m|q8_0|f16] [--output PATH] [--config PATH]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--model` | PATH | **обязательный** | Путь к модели или директории с адаптером |
| `--format` | `gguf` / `merged` / `hub` | `gguf` | Формат экспорта |
| `--quant` | `q4_k_m` / `q8_0` / `f16` | `q4_k_m` | Уровень квантизации для GGUF |
| `--output` | PATH | `None` | Путь для экспортированной модели |
| `--config` | PATH | `None` | Конфиг с настройками экспорта |

!!! info "Форматы экспорта"
    - **gguf** -- квантизированный формат для llama.cpp и Ollama
    - **merged** -- полная модель с вмёрженным LoRA-адаптером
    - **hub** -- публикация на HuggingFace Hub (требует `HF_TOKEN`)

**Примеры:**

=== "GGUF q4_k_m"

    ```bash
    pulsar export \
      --model ./outputs/cam-sft/lora \
      --format gguf \
      --quant q4_k_m
    ```

=== "Merged модель"

    ```bash
    pulsar export \
      --model ./outputs/cam-sft/lora \
      --format merged \
      --output ./merged/
    ```

=== "Push to Hub"

    ```bash
    pulsar export \
      --model ./outputs/cam-sft/lora \
      --format hub
    ```

---

## pulsar serve

Запуск сервера для инференса модели.

```bash
pulsar serve --model PATH [--port 8080] [--backend llamacpp|vllm] [--host 0.0.0.0]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--model` | PATH | **обязательный** | Путь к файлу модели (GGUF) или директории |
| `--port` | int | `8080` | Порт сервера |
| `--backend` | `llamacpp` / `vllm` | `llamacpp` | Бэкенд для сервинга |
| `--host` | string | `0.0.0.0` | Хост сервера |

**Примеры:**

=== "llama.cpp"

    ```bash
    pulsar serve \
      --model ./outputs/model.gguf \
      --port 8080
    ```

=== "vLLM"

    ```bash
    pulsar serve \
      --model ./outputs/cam-sft \
      --backend vllm \
      --port 8000
    ```

---

## pulsar init

Создание нового конфига эксперимента.

```bash
pulsar init <name> [--task sft|dpo] [--model qwen2.5-3b|llama3.2-1b|mistral-7b] [--output-dir PATH]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `name` | string (аргумент) | -- | Имя эксперимента |
| `--task` | `sft` / `dpo` | `sft` | Тип задачи обучения |
| `--model` | `qwen2.5-3b` / `llama3.2-1b` / `mistral-7b` | `qwen2.5-3b` | Базовая модель |
| `--output-dir` | PATH | `./outputs/<name>` | Директория для результатов |

!!! note "Генерируемые файлы"
    Конфиг создаётся в `configs/experiments/<name>.yaml` и наследует
    базовые настройки через механизм `inherit`.

**Примеры:**

=== "SFT-классификатор"

    ```bash
    pulsar init my-classifier
    ```

=== "DPO-чатбот"

    ```bash
    pulsar init my-chatbot \
      --task dpo \
      --model llama3.2-1b
    ```

---

## pulsar info

Показать информацию об обнаруженном оборудовании и рекомендуемую стратегию обучения.

```bash
pulsar info
```

Команда не принимает аргументов. Выводит таблицу с данными GPU: имя, VRAM, compute capability, поддержка BF16, рекомендуемая стратегия, batch size и gradient accumulation.

**Пример:**

```bash
pulsar info
```

```
┌───────────────────────────────────┐
│         Hardware Info             │
├─────────────────────┬─────────────┤
│ GPUs                │ 1           │
│ GPU Name            │ RTX 4090    │
│ VRAM per GPU        │ 24.0 GB     │
│ Compute Capability  │ 8.9         │
│ BF16 Supported      │ True        │
│ Recommended Strategy│ unsloth     │
│ Recommended Batch   │ 4           │
│ Recommended Grad Ac │ 4           │
└─────────────────────┴─────────────┘
```

---

## pulsar ui

Запуск веб-интерфейса (Dashboard).

```bash
pulsar ui [--host 0.0.0.0] [--port 8888]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--host` | string | `0.0.0.0` | Хост сервера |
| `--port` | int | `8888` | Порт сервера |

**Примеры:**

=== "По умолчанию"

    ```bash
    pulsar ui
    ```

=== "Кастомный порт"

    ```bash
    pulsar ui --port 9000
    ```

После запуска: Dashboard -- `http://localhost:8888`, API docs -- `http://localhost:8888/docs`.

---

## pulsar sweep

Запуск оптимизации гиперпараметров (HPO) через Optuna.

```bash
pulsar sweep <config.yaml> <sweep_config.yaml> [--n-trials N] [--name NAME]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `config.yaml` | PATH (аргумент) | -- | Базовый конфиг эксперимента |
| `sweep_config.yaml` | PATH (аргумент) | -- | Конфиг поиска гиперпараметров |
| `--n-trials` | int | из конфига | Количество триалов (переопределяет конфиг) |
| `--name` | string | `None` | Имя Optuna-study |

**Примеры:**

=== "Базовый sweep"

    ```bash
    pulsar sweep \
      configs/experiments/sft.yaml \
      configs/sweeps/lr-search.yaml
    ```

=== "30 триалов"

    ```bash
    pulsar sweep \
      configs/experiments/sft.yaml \
      configs/sweeps/full.yaml \
      --n-trials 30 \
      --name lr-and-epochs
    ```

---

## pulsar agent

Подсистема агентов: создание, тестирование и деплой AI-агентов с инструментами.

### pulsar agent init

Создать конфиг нового агента.

```bash
pulsar agent init <name> [--model-url URL] [--model-name NAME]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `name` | string (аргумент) | -- | Имя агента |
| `--model-url` | string | `http://localhost:8080/v1` | URL сервера модели |
| `--model-name` | string | `default` | Имя модели на сервере |

**Примеры:**

=== "Базовый агент"

    ```bash
    pulsar agent init my-assistant
    ```

=== "С Ollama"

    ```bash
    pulsar agent init code-helper \
      --model-url http://localhost:11434/v1
    ```

### pulsar agent test

Интерактивный REPL для тестирования агента.

```bash
pulsar agent test <config.yaml> [--native-tools]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `config.yaml` | PATH (аргумент) | -- | Путь к конфигу агента |
| `--native-tools` | flag | `False` | Использовать native tool calling вместо ReAct |

**Примеры:**

=== "ReAct-режим"

    ```bash
    pulsar agent test configs/agents/my-assistant.yaml
    ```

=== "Native tools"

    ```bash
    pulsar agent test configs/agents/my-assistant.yaml \
      --native-tools
    ```

### pulsar agent serve

Запуск REST API-сервера агента.

```bash
pulsar agent serve <config.yaml> [--host 0.0.0.0] [--port 8081]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `config.yaml` | PATH (аргумент) | -- | Путь к конфигу агента |
| `--host` | string | `0.0.0.0` | Хост сервера |
| `--port` | int | `8081` | Порт сервера |

**Примеры:**

=== "По умолчанию"

    ```bash
    pulsar agent serve configs/agents/my-assistant.yaml
    ```

=== "Кастомный порт"

    ```bash
    pulsar agent serve configs/agents/my-assistant.yaml \
      --port 9000
    ```

!!! info "Эндпоинты агента"
    После запуска доступны:

    - `POST /v1/agent/chat` -- отправка сообщения
    - `GET /v1/agent/health` -- проверка состояния

---

## pulsar pipeline

Оркестратор многоэтапных пайплайнов.

### pulsar pipeline run

Запуск пайплайна из YAML-конфига.

```bash
pulsar pipeline run <config.yaml>
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `config.yaml` | PATH (аргумент) | -- | Путь к YAML-конфигу пайплайна |

**Примеры:**

```bash
pulsar pipeline run configs/pipelines/example.yaml
```

### pulsar pipeline list

Список прошлых запусков пайплайнов.

```bash
pulsar pipeline list [--name NAME]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--name` | string | `None` | Фильтр по имени пайплайна |

**Примеры:**

=== "Все запуски"

    ```bash
    pulsar pipeline list
    ```

=== "По имени"

    ```bash
    pulsar pipeline list --name full-pipeline
    ```

---

## pulsar runs

Управление записями экспериментов.

### pulsar runs list

Список записей экспериментов.

```bash
pulsar runs list [--project X] [--status Y] [--limit N]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--project` | string | `None` | Фильтр по имени проекта |
| `--status` | string | `None` | Фильтр по статусу (`completed`, `failed`, `running`) |
| `--limit` | int | `20` | Максимальное количество записей |

**Примеры:**

=== "Последние 10 завершённых"

    ```bash
    pulsar runs list --status completed --limit 10
    ```

=== "По проекту"

    ```bash
    pulsar runs list --project customer-intent
    ```

### pulsar runs show

Детали конкретного запуска.

```bash
pulsar runs show <run_id>
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `run_id` | string (аргумент) | -- | Идентификатор запуска |

**Пример:**

```bash
pulsar runs show abc123def456
```

### pulsar runs compare

Сравнение нескольких запусков.

```bash
pulsar runs compare <run_id1> <run_id2> ...
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `run_ids` | string... (аргументы) | -- | Два или более ID запусков для сравнения |

**Примеры:**

=== "Два запуска"

    ```bash
    pulsar runs compare abc123 def456
    ```

=== "Три запуска"

    ```bash
    pulsar runs compare run1 run2 run3
    ```

---

## pulsar registry

Реестр моделей: регистрация, продвижение по стадиям, листинг.

### pulsar registry list

Список зарегистрированных моделей.

```bash
pulsar registry list [--name X] [--status Y]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--name` | string | `None` | Фильтр по имени модели |
| `--status` | string | `None` | Фильтр по статусу (`staging`, `production`, `archived`) |

**Примеры:**

=== "Все модели"

    ```bash
    pulsar registry list
    ```

=== "Продакшен-модели"

    ```bash
    pulsar registry list \
      --name customer-intent \
      --status production
    ```

### pulsar registry register

Регистрация модели в реестре.

```bash
pulsar registry register <name> --model-path PATH [--task sft] [--base-model NAME] [--tag TAG...]
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `name` | string (аргумент) | -- | Имя модели |
| `--model-path` | PATH | **обязательный** | Путь к модели/адаптеру |
| `--task` | string | `sft` | Тип задачи обучения |
| `--base-model` | string | `""` | Имя базовой модели |
| `--tag` | string (повторяемая) | -- | Теги (можно указывать несколько раз) |

**Пример:**

```bash
pulsar registry register customer-intent \
  --model-path ./outputs/sft/lora \
  --base-model qwen2.5-3b \
  --tag v1 \
  --tag production-ready
```

### pulsar registry promote

Продвижение модели по стадиям жизненного цикла.

```bash
pulsar registry promote <model_id> staging|production|archived
```

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `model_id` | string (аргумент) | -- | ID модели в реестре |
| `status` | `staging` / `production` / `archived` | -- | Целевой статус |

!!! warning "Необратимое действие"
    Перевод в `archived` означает, что модель больше не используется в продакшене.
    Перед этим убедитесь, что другая модель уже в `production`.

**Примеры:**

=== "В staging"

    ```bash
    pulsar registry promote customer-intent-v2 staging
    ```

=== "В production"

    ```bash
    pulsar registry promote customer-intent-v2 production
    ```
