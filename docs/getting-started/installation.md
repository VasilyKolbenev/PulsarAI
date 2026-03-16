# Установка

Полное руководство по установке и настройке pulsar-ai.

---

## Системные требования

### Hardware

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| **GPU** | NVIDIA, 6 GB VRAM | NVIDIA, 16+ GB VRAM |
| **RAM** | 16 GB | 32 GB |
| **Диск** | 50 GB | 100+ GB |

### Требования VRAM по размеру модели (QLoRA, 4-bit)

| Модель | Параметры | VRAM |
|--------|-----------|------|
| Qwen3.5-0.8B | 0.8B | ~2--3 GB |
| Llama-3.2-1B | 1B | ~3--4 GB |
| Qwen3.5-2B | 2B | ~4--5 GB |
| Qwen2.5-3B | 3B | ~4--5 GB |
| Qwen3.5-4B | 4B | ~6--7 GB |
| Mistral-7B | 7B | ~8--10 GB |

### Software

| Компонент | Версия |
|-----------|--------|
| Python | 3.10+ (рекомендуется 3.12--3.14) |
| Node.js | 18+ (для Web UI) |
| CUDA Toolkit | 11.8+ или 12.x |
| Драйверы NVIDIA | Совместимые с CUDA |
| Git | Любая актуальная версия |

---

## Клонирование репозитория

```bash
git clone https://github.com/your-org/pulsar-ai.git
cd pulsar-ai
```

---

## Python-окружение

=== "Linux / macOS"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    ```

=== "Windows"

    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
    pip install --upgrade pip
    ```

### Базовая установка

```bash
pip install -e ".[ui,eval]"
```

### Таблица extras

Установите только то, что нужно, через `pip install -e ".[extra1,extra2]"`:

| Extra | Описание | Пример |
|-------|----------|--------|
| *(base)* | CLI: train, eval, export. Устанавливается всегда | `pip install -e .` |
| `ui` | Web UI (FastAPI, uvicorn) | `pip install -e ".[ui]"` |
| `eval` | Графики eval (seaborn, matplotlib) | `pip install -e ".[eval]"` |
| `unsloth` | Unsloth: 2--5x ускорение (Linux only) | `pip install -e ".[unsloth]"` |
| `hpo` | HPO через Optuna | `pip install -e ".[hpo]"` |
| `vllm` | vLLM serving backend | `pip install -e ".[vllm]"` |
| `llamacpp` | llama.cpp serving backend | `pip install -e ".[llamacpp]"` |
| `deepspeed` | DeepSpeed multi-GPU | `pip install -e ".[deepspeed]"` |
| `agent-serve` | Agent REST server | `pip install -e ".[agent-serve]"` |
| `agent-memory` | Agent memory backends | `pip install -e ".[agent-memory]"` |
| `tracking-clearml` | ClearML experiment tracking | `pip install -e ".[tracking-clearml]"` |
| `tracking-wandb` | Weights & Biases tracking | `pip install -e ".[tracking-wandb]"` |
| `docs` | MkDocs + Material для документации | `pip install -e ".[docs]"` |
| `dev` | Тесты, линтеры, типы | `pip install -e ".[dev]"` |
| `all` | Все зависимости | `pip install -e ".[all]"` |

!!! tip "Рекомендация для начала"
    Для первого знакомства достаточно `pip install -e ".[ui,eval]"`.
    Остальные extras добавляйте по мере необходимости.

---

## Установка UI

```bash
cd ui
npm install
cd ..
```

!!! note "Node.js"
    Убедитесь, что установлен Node.js 18+. Проверка: `node --version`.

---

## Настройка окружения (.env)

Создайте файл `.env` в корне проекта:

```bash title=".env"
# OpenAI API ключ для Co-pilot чата в UI (опционально)
OPENAI_API_KEY=sk-your-key-here

# Аутентификация API (опционально)
PULSAR_AUTH_ENABLED=false

# CORS origins для frontend (опционально)
PULSAR_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# HuggingFace токен для gated-моделей: Llama и др. (опционально)
HF_TOKEN=hf_your_token_here
```

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `OPENAI_API_KEY` | -- | Ключ для Co-pilot (LLM-режим) и Site Chat |
| `PULSAR_AUTH_ENABLED` | `false` | Включить аутентификацию API |
| `PULSAR_CORS_ORIGINS` | `localhost:3000,8888` | Разрешённые CORS origins |
| `HF_TOKEN` | -- | HuggingFace токен для gated-моделей |

!!! warning "Безопасность"
    Файл `.env` содержит секреты. Убедитесь, что он добавлен в `.gitignore`
    и **никогда** не коммитится в репозиторий.

---

## Проверка установки

### CLI

```bash
pulsar info
```

Ожидаемый вывод:

```
pulsar-ai v0.x.x
Python:  3.12.x
PyTorch: 2.x.x (CUDA 12.x)
GPU:     NVIDIA RTX 4060 (8 GB)
Extras:  ui, eval
```

### Backend API

Запустите backend:

```bash
pulsar ui
```

В отдельном терминале:

```bash
curl http://localhost:8888/api/v1/health
```

Ожидаемый ответ:

```json
{"status": "ok"}
```

### Frontend

В отдельном терминале:

```bash
cd ui && npm run dev
```

Откройте [http://localhost:5173](http://localhost:5173) -- должен загрузиться дашборд.

---

## Troubleshooting

### CUDA не найдена

```
RuntimeError: No CUDA GPUs are available
```

**Решение:**

1. Проверьте драйверы: `nvidia-smi`
2. Проверьте CUDA: `nvcc --version`
3. Убедитесь, что PyTorch установлен с CUDA:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

Если `False` -- переустановите PyTorch с нужной версией CUDA:

=== "CUDA 12.x"

    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cu124
    ```

=== "CUDA 11.8"

    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cu118
    ```

### npm install падает

```
npm ERR! code ERESOLVE
```

**Решение:**

```bash
cd ui
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

### UI не подключается к backend

**Проверьте:**

1. Backend запущен на порту 8888: `curl http://localhost:8888/api/v1/health`
2. CORS настроен в `.env`: `PULSAR_CORS_ORIGINS=http://localhost:5173`
3. Перезапустите backend после изменения `.env`

### Модель не скачивается (gated model)

```
OSError: Access to model is restricted
```

**Решение:**

1. Примите условия модели на HuggingFace (для Llama и др.)
2. Добавьте токен в `.env`:

```bash
HF_TOKEN=hf_your_token_here
```

### Import ошибки после установки

```
ModuleNotFoundError: No module named 'pulsar_ai'
```

**Решение:**

```bash
# Убедитесь, что виртуальное окружение активно
source .venv/bin/activate  # или .venv\Scripts\activate на Windows

# Переустановите пакет
pip install -e ".[ui,eval]"
```
