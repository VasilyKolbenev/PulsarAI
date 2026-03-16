# Быстрый старт

Запустите полный цикл файнтюнинга за 5 минут: установка, обучение, оценка, экспорт, сервинг.

---

## 1. Установка

```bash
git clone https://github.com/your-org/pulsar-ai.git
cd pulsar-ai

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[ui,eval]"
```

```bash
cd ui && npm install && cd ..
```

!!! tip "Ускорение обучения на Linux"
    Установите Unsloth для 2--5x ускорения:

    ```bash
    pip install -e ".[unsloth]"
    ```

---

## 2. Запуск backend

```bash
pulsar ui
```

Ожидаемый вывод:

```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8888
```

Swagger-документация: [http://localhost:8888/docs](http://localhost:8888/docs)

---

## 3. Запуск frontend

В **отдельном терминале**:

```bash
cd ui
npm run dev
```

Ожидаемый вывод:

```
VITE v6.x.x  ready in 500 ms
➜  Local:   http://localhost:5173/
```

Откройте [http://localhost:5173](http://localhost:5173) в браузере.

---

## 4. Обучение модели

```bash
pulsar train configs/examples/cam-sft-qwen3.5-0.8b.yaml
```

Ожидаемый вывод:

```
Loading model Qwen/Qwen3.5-0.8B...
Dataset: 1234 rows (train: 1049, test: 185)
Training started: 5 epochs, lr=3e-4, batch=2, grad_accum=8
Step 100/500 | Loss: 1.234 | GPU: 2.1 GB
...
Training complete! Adapter saved to outputs/cam-sft-qwen3.5-0.8b/lora
```

!!! note "Время обучения"
    На GPU с 8 GB VRAM (RTX 3060/4060) обучение модели 0.8B занимает ~15 минут.
    Прогресс также виден в Web UI на странице **Experiments**.

---

## 5. Оценка модели

```bash
pulsar eval \
  --model outputs/cam-sft-qwen3.5-0.8b/lora \
  --test-data data/cam_intents_test.csv
```

Ожидаемый вывод:

```
Evaluating 185 samples...
━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Results:
  Accuracy:        87.5%
  F1 (weighted):   0.891
  JSON Parse Rate: 98.4%
```

---

## 6. Экспорт в GGUF

```bash
pulsar export \
  --model outputs/cam-sft-qwen3.5-0.8b/lora \
  --format gguf \
  --quant q4_k_m
```

Ожидаемый вывод:

```
Merging LoRA adapter with base model...
Converting to GGUF (q4_k_m)...
Exported: outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf (530 MB)
```

!!! tip "Другие форматы экспорта"

    === "Merged (полная модель)"

        ```bash
        pulsar export --model outputs/cam-sft-qwen3.5-0.8b/lora --format merged
        ```

    === "HuggingFace Hub"

        ```bash
        pulsar export --model outputs/cam-sft-qwen3.5-0.8b/lora --format hub
        ```

---

## 7. Запуск модели как API

```bash
pulsar serve \
  --model outputs/cam-sft-qwen3.5-0.8b-q4_k_m.gguf \
  --port 8080
```

Ожидаемый вывод:

```
Loading model: cam-sft-qwen3.5-0.8b-q4_k_m.gguf
Server running on http://localhost:8080
OpenAI-compatible API: POST /v1/chat/completions
```

Проверка:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [
      {"role": "system", "content": "You are an intent classifier."},
      {"role": "user", "content": "Оплатить коммуналку"}
    ]
  }'
```

Ожидаемый ответ:

```json
{
  "choices": [{
    "message": {
      "content": "{\"domain\": \"HOUSE\", \"skill\": \"utility_bill\"}"
    }
  }]
}
```

---

## Что дальше?

- [Первый эксперимент](first-experiment.md) -- подробное пошаговое руководство
- [Установка](installation.md) -- полная настройка с extras и .env
- [CLI справочник](../reference/cli.md) -- все команды `pulsar`
