# Экспорт модели

## Обзор

После обучения модель существует в виде LoRA-адаптера. Для использования в продакшене её нужно экспортировать в один из поддерживаемых форматов.

---

## Форматы экспорта

| Формат | Команда | Описание | Применение |
|---|---|---|---|
| **GGUF** | `--format gguf` | Квантизированный формат для llama.cpp | Ollama, llama.cpp, локальный инференс |
| **Merged** | `--format merged` | Полная модель (адаптер + база, слитые) | HuggingFace Transformers, vLLM |
| **Hub** | `--format hub` | Публикация на HuggingFace Hub | Шеринг и версионирование на HF |

---

## Уровни квантизации (GGUF)

| Квантизация | Размер (7B) | Качество | Скорость | Когда использовать |
|---|---|---|---|---|
| `q4_k_m` | ~4.1 GB | Хорошее | Быстро | **Рекомендуется** для большинства задач |
| `q8_0` | ~7.2 GB | Отличное | Средне | Максимальное качество при квантизации |
| `f16` | ~14.0 GB | Без потерь | Медленно | Эталон, сравнение качества |

!!! tip "Выбор квантизации"
    Для продакшена рекомендуется `q4_k_m` -- лучший баланс размера и качества. Используйте `q8_0` если ресурсы позволяют. `f16` полезен только для бенчмарков.

---

## Экспорт через CLI

### GGUF (для Ollama / llama.cpp)

```bash
# Квантизация q4_k_m (рекомендуется)
pulsar export \
  --model ./outputs/cam-sft/lora \
  --format gguf \
  --quant q4_k_m \
  --output ./exports/cam-model.gguf

# Квантизация q8_0 (более высокое качество)
pulsar export \
  --model ./outputs/cam-sft/lora \
  --format gguf \
  --quant q8_0

# Без квантизации (f16)
pulsar export \
  --model ./outputs/cam-sft/lora \
  --format gguf \
  --quant f16
```

### Merged (полная модель)

```bash
pulsar export \
  --model ./outputs/cam-sft/lora \
  --format merged \
  --output ./exports/cam-merged/
```

### Hub (HuggingFace)

```bash
pulsar export \
  --model ./outputs/cam-sft/lora \
  --format hub
```

!!! note "HuggingFace Auth"
    Для публикации на HuggingFace Hub необходимо предварительно авторизоваться:
    ```bash
    huggingface-cli login
    ```

---

## Экспорт через API

```bash
curl -X POST http://localhost:8888/api/export \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "./outputs/cam-sft/lora",
    "export": {
      "format": "gguf",
      "quantization": "q4_k_m",
      "output_path": "./exports/cam-model.gguf"
    }
  }'
```

Ответ:

```json
{
  "status": "completed",
  "output_path": "./exports/cam-model.gguf",
  "format": "gguf",
  "quantization": "q4_k_m",
  "size_mb": 512.3
}
```

---

## Использование GGUF с Ollama

После экспорта в GGUF модель можно запустить через Ollama:

### 1. Создайте Modelfile

```dockerfile
# Modelfile
FROM ./exports/cam-model.gguf

TEMPLATE """<|im_start|>system
{{ .System }}<|im_end|>
<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""

PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER stop "<|im_end|>"

SYSTEM """Ты классификатор интентов. Верни JSON с полями domain и skill."""
```

### 2. Создайте модель в Ollama

```bash
ollama create cam-classifier -f Modelfile
```

### 3. Запустите

```bash
ollama run cam-classifier "Закажи такси до аэропорта"
```

Ответ:

```json
{"domain": "transport", "skill": "taxi"}
```

!!! tip "Автоматический экспорт"
    Добавьте `export_gguf: true` и `quantization: q4_k_m` в секцию `output` конфига эксперимента, чтобы GGUF автоматически создавался после обучения.

---

## Структура выходных файлов

### GGUF

```
exports/
└── cam-model.gguf              # один файл, готов к использованию
```

### Merged

```
exports/cam-merged/
├── config.json
├── model.safetensors
├── tokenizer.json
├── tokenizer_config.json
└── special_tokens_map.json
```

### Hub

Модель публикуется на HuggingFace Hub с автоматическим model card.
