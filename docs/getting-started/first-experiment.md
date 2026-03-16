# Первый эксперимент

Пошаговое руководство: от CSV-датасета до работающей модели.
Предполагается, что [установка](installation.md) уже выполнена.

---

## 1. Подготовка датасета

pulsar-ai принимает CSV, JSONL, JSON, Parquet и Excel. Минимальный формат -- CSV с колонками
для текста и меток:

```csv title="data/my_intents.csv"
phrase,domain,skill
"Оплатить коммуналку",HOUSE,utility_bill
"Когда придёт посылка",DELIVERY,tracking
"Привет!",BOLTALKA,greeting
"Какой курс доллара",FINANCE,exchange_rate
"Заказать такси",TRANSPORT,taxi_order
"Выключи свет в спальне",SMART_HOME,light_control
"Поставь будильник на 7 утра",SMART_HOME,alarm_set
"Переведи деньги маме",FINANCE,money_transfer
```

Поместите файл в директорию `data/`:

```bash
cp your_dataset.csv data/my_intents.csv
```

!!! warning "Частая ошибка: неверное имя колонки"
    Параметр `text_column` в конфиге должен **точно совпадать** с именем колонки в CSV.
    Если в вашем файле колонка называется `text`, а в конфиге указано `phrase` --
    обучение упадёт с ошибкой `KeyError`.

!!! tip "Загрузка через UI"
    Можно загрузить датасет через Web UI: откройте страницу **Datasets**,
    нажмите **Upload** и выберите файл. Платформа автоматически определит
    формат и колонки.

---

## 2. Создание system prompt

System prompt определяет формат ответа модели. Создайте текстовый файл:

```text title="prompts/my_classifier.txt"
You are an intent classifier. Given a user message, respond with JSON:
{"domain": "<DOMAIN>", "skill": "<SKILL>"}

Respond ONLY with valid JSON object. No explanations.
```

!!! note "Зачем нужен system prompt?"
    System prompt задаёт модели роль и формат ответа. Без него модель будет отвечать
    в свободной форме, что затрудняет парсинг результатов и оценку метрик.

---

## 3. Создание конфига эксперимента

=== "Через CLI (рекомендуется)"

    ```bash
    pulsar init my-experiment --task sft --model qwen3.5-0.8b
    ```

    Команда создаст файл `configs/examples/my-experiment.yaml` с настройками по умолчанию.
    Отредактируйте его под свои данные.

=== "Вручную"

    Создайте файл `configs/examples/my-experiment.yaml`:

    ```yaml title="configs/examples/my-experiment.yaml"
    inherit:
      - base
      - models/qwen3.5-0.8b

    task: sft

    dataset:
      path: data/my_intents.csv
      format: csv
      text_column: phrase
      label_columns:
        - domain
        - skill
      system_prompt_file: prompts/my_classifier.txt
      test_size: 0.15

    training:
      epochs: 3
      learning_rate: 2e-4
      batch_size: 1
      gradient_accumulation: 16
      max_seq_length: 512

    output:
      dir: ./outputs/my-experiment
      save_adapter: true
    ```

### Ключевые поля конфига

| Поле | Описание | Рекомендации |
|------|----------|-------------|
| `inherit` | Наследование базовых конфигов | `base` + конфиг модели |
| `task` | Тип задачи | `sft` для первого обучения, `dpo` для preference tuning |
| `dataset.text_column` | Колонка с текстом в CSV | Должна точно совпадать с именем в файле |
| `dataset.label_columns` | Колонки с метками | Список строк |
| `dataset.test_size` | Доля тестовой выборки | 0.1--0.2 |
| `training.epochs` | Количество эпох | 3--5 для маленьких датасетов |
| `training.learning_rate` | Скорость обучения | 2e-4 (0.8B), 1e-4 (2--4B), 5e-5 (7B+) |
| `training.batch_size` | Размер батча | 1--2 (8 GB), 2--4 (16 GB), 4--8 (24+ GB) |
| `training.gradient_accumulation` | Шаги накопления градиента | Эффективный batch = batch_size x grad_accum |

!!! tip "Наследование конфигов"
    `inherit: [base, models/qwen3.5-0.8b]` подгружает базовые настройки (optimizer, seed,
    gradient checkpointing) и параметры модели (LoRA targets, quantization).
    Вы переопределяете только то, что нужно изменить.

---

## 4. Настройка LoRA

LoRA-параметры задаются в конфиге модели, но их можно переопределить:

```yaml title="Добавьте в configs/examples/my-experiment.yaml"
lora:
  r: 16              # Rank: 8 (быстро), 16 (баланс), 32 (качество)
  lora_alpha: 16     # Обычно равен r
  lora_dropout: 0    # 0 для маленьких датасетов
```

| Параметр | Влияние | Малый датасет (<1K) | Большой датасет (>10K) |
|----------|---------|---------------------|------------------------|
| `r=8` | Быстрое обучение, меньше параметров | Хороший выбор | Может не хватить ёмкости |
| `r=16` | Баланс скорости и качества | Рекомендуется | Рекомендуется |
| `r=32` | Больше параметров, медленнее | Риск переобучения | Хороший выбор |

---

## 5. Запуск обучения

```bash
pulsar train configs/examples/my-experiment.yaml
```

Вы увидите прогресс обучения:

```
Loading model Qwen/Qwen3.5-0.8B (4-bit)...
Dataset: 850 rows (train: 722, test: 128)
LoRA: r=16, alpha=16, params=2.1M (0.26% of base)

Epoch 1/3
Step  50/270 | Loss: 2.341 | LR: 1.8e-4 | GPU: 2.3 GB
Step 100/270 | Loss: 0.892 | LR: 1.5e-4 | GPU: 2.3 GB
...
Epoch 3/3
Step 270/270 | Loss: 0.124 | LR: 0.0e+0 | GPU: 2.3 GB

Training complete!
Adapter saved: outputs/my-experiment/lora
```

С переопределением параметров на лету:

```bash
pulsar train configs/examples/my-experiment.yaml epochs=5 learning_rate=1e-4
```

!!! warning "CUDA Out of Memory"
    Если возникает ошибка OOM:

    1. Уменьшите `batch_size` до 1
    2. Увеличьте `gradient_accumulation` (чтобы эффективный batch остался прежним)
    3. Уменьшите `max_seq_length` (например, 256 вместо 512)
    4. Попробуйте модель поменьше (0.8B вместо 2B)

---

## 6. Оценка модели

```bash
pulsar eval \
  --model outputs/my-experiment/lora \
  --test-data data/my_intents_test.csv
```

Результат:

```
Evaluating 128 samples...
━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Results:
  Accuracy:          87.5%
  F1 (weighted):     0.891
  JSON Parse Rate:   98.4%
  Confusion Matrix:  saved to outputs/my-experiment/confusion_matrix.png
```

### Что означают метрики

| Метрика | Описание | Хороший результат |
|---------|----------|-------------------|
| **Accuracy** | Доля правильных ответов | >85% |
| **F1 (weighted)** | Взвешенная F1-мера по всем классам | >0.85 |
| **JSON Parse Rate** | Процент ответов, которые парсятся как валидный JSON | >95% |

!!! note "Низкий JSON Parse Rate?"
    Если JSON Parse Rate ниже 90%:

    - Проверьте system prompt -- он должен явно требовать JSON-формат
    - Увеличьте количество эпох (модель ещё не выучила формат)
    - Убедитесь, что `max_seq_length` достаточен для ответа

---

## 7. Просмотр результатов в Web UI

Убедитесь, что backend и frontend запущены ([шаги из quickstart](quickstart.md#2-запуск-backend)).

1. Откройте [http://localhost:5173](http://localhost:5173)
2. Перейдите на страницу **Experiments**
3. Найдите свой эксперимент в списке
4. Просмотрите:
    - **Config** -- параметры обучения
    - **Metrics** -- accuracy, F1, loss
    - **Eval Results** -- детальные результаты оценки
    - **Loss Curve** -- график потерь по шагам

---

## 8. Следующие шаги

### Экспорт и сервинг

Экспортируйте модель и запустите как API:

```bash
# Экспорт в GGUF
pulsar export --model outputs/my-experiment/lora --format gguf --quant q4_k_m

# Запуск сервера
pulsar serve --model outputs/my-experiment-q4_k_m.gguf --port 8080
```

### DPO (улучшение через предпочтения)

После SFT можно улучшить модель через DPO:

```bash
pulsar train configs/examples/cam-dpo-qwen3.5-0.8b.yaml
```

Подробнее: [Руководство по DPO](../guides/training/dpo.md)

### HPO (автоматический подбор гиперпараметров)

```bash
pip install -e ".[hpo]"
pulsar sweep configs/examples/my-experiment.yaml configs/sweeps/lr-sweep.yaml
```

Подробнее: [HPO / Sweep](../guides/hpo.md)

### Workflow Builder

Соберите полный пайплайн визуально: Data -> Train -> Eval -> Export -> Serve.
Откройте страницу **Workflows** в Web UI.

Подробнее: [Workflow Builder](../guides/workflow-builder.md)
