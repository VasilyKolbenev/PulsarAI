# Pipeline Execution

## Обзор

Pipeline -- это декларативное описание многошагового процесса (обучение, оценка, экспорт, регистрация) в YAML-файле. Pipeline Executor выполняет шаги в правильном порядке (по зависимостям), поддерживает подстановку переменных между шагами и условное выполнение.

---

## Структура YAML-конфига

```yaml
# configs/pipelines/my-pipeline.yaml

pipeline:
  name: "my-full-pipeline"       # имя пайплайна

steps:
  - name: train_sft               # уникальное имя шага
    type: training                 # тип шага
    config:                        # конфигурация, специфичная для типа
      task: sft
      model:
        name: "Qwen/Qwen3.5-2B"
      dataset:
        path: "data/train.csv"
      training:
        epochs: 3
        learning_rate: 2e-4
      output:
        dir: "./outputs/sft"

  - name: eval_sft
    type: evaluation
    depends_on: [train_sft]        # зависимость от шага train_sft
    config:
      model_path: "${train_sft.adapter_dir}"    # переменная подстановка
      test_data_path: "data/test.csv"

  - name: export_model
    type: export
    depends_on: [train_sft, eval_sft]
    condition:                      # условное выполнение
      metric: "${eval_sft.overall_accuracy}"
      operator: gte
      value: 0.85
    config:
      model_path: "${train_sft.adapter_dir}"
      export:
        format: gguf
        quantization: q4_k_m
```

---

## Поля шага (step)

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `name` | str | Да | Уникальное имя шага |
| `type` | str | Да | Тип шага (см. таблицу ниже) |
| `config` | dict | Да | Конфигурация для шага |
| `depends_on` | list[str] | Нет | Список имён шагов-зависимостей |
| `condition` | dict | Нет | Условие для выполнения шага |

---

## Встроенные типы шагов

| Тип | Описание | Ключевые поля config |
|---|---|---|
| `training` | Обучение модели (SFT или DPO) | `task`, `model`, `dataset`, `training`, `output` |
| `evaluation` | Оценка на тестовых данных | `model_path`, `test_data_path`, `evaluation` |
| `export` | Экспорт в GGUF/merged/hub | `model_path`, `export.format`, `export.quantization` |
| `register` | Регистрация модели в реестре | `name`, `model_path`, `task`, `base_model` |
| `fingerprint` | Вычисление хеша датасета | `dataset.path` |

---

## Подстановка переменных

Между шагами можно передавать значения с помощью синтаксиса `${step_name.output_key}`:

```yaml
steps:
  - name: train
    type: training
    config:
      output:
        dir: "./outputs/sft"
    # Результат: {"adapter_dir": "./outputs/sft/lora", "training_loss": 0.45, ...}

  - name: eval
    type: evaluation
    depends_on: [train]
    config:
      model_path: "${train.adapter_dir}"     # -> "./outputs/sft/lora"
      test_data_path: "data/test.csv"
    # Результат: {"overall_accuracy": 0.91, "f1_weighted": {...}, ...}

  - name: export
    type: export
    depends_on: [train]
    config:
      model_path: "${train.adapter_dir}"     # -> "./outputs/sft/lora"
      export:
        format: gguf
```

### Доступные output-ключи по типу шага

| Тип шага | Ключи output |
|---|---|
| `training` | `adapter_dir`, `output_dir`, `training_loss`, `global_steps`, `vram_peak_gb` |
| `evaluation` | `overall_accuracy`, `json_parse_rate`, `results_path`, `report_path` |
| `export` | `output_path`, `format`, `size_mb` |
| `register` | `model_id`, `model_path` |
| `fingerprint` | `fingerprint`, `dataset_path` |

---

## Условное выполнение

Шаг выполняется только если его `condition` истинно:

```yaml
- name: export_model
  type: export
  depends_on: [eval]
  condition:
    metric: "${eval.overall_accuracy}"    # ссылка на метрику
    operator: gte                          # оператор сравнения
    value: 0.85                            # пороговое значение
  config:
    model_path: "${train.adapter_dir}"
    export:
      format: gguf
```

### Операторы сравнения

| Оператор | Описание | Пример |
|---|---|---|
| `gt` | Строго больше | accuracy > 0.9 |
| `gte` | Больше или равно | accuracy >= 0.85 |
| `lt` | Строго меньше | loss < 0.5 |
| `lte` | Меньше или равно | loss <= 0.3 |
| `eq` | Равно | status == 1 |
| `neq` | Не равно | error != 1 |

Если условие не выполнено, шаг получает статус `skipped` и его output содержит `{"_skipped": true}`.

---

## Запуск из CLI

```bash
# Запуск пайплайна
pulsar pipeline run configs/pipelines/my-pipeline.yaml

# Список прошлых запусков
pulsar pipeline list

# Фильтр по имени
pulsar pipeline list --name full-pipeline
```

Вывод после успешного запуска:

```
┌──── Pipeline Run ────┐
│ Pipeline: my-full-pipeline
│ Steps: 3
└──────────────────────┘

Running step: train_sft (type=training)
Step 'train_sft' completed in 342.5s
Running step: eval_sft (type=evaluation)
Step 'eval_sft' completed in 45.2s
Condition: eval_sft.overall_accuracy (0.91) gte 0.85 → True
Running step: export_model (type=export)
Step 'export_model' completed in 120.3s

Pipeline 'my-full-pipeline' completed successfully!

┌───────── Step Results ─────────┐
│ Step          │ Status    │ Key Outputs
│ train_sft     │ completed │ training_loss=0.45
│ eval_sft      │ completed │ overall_accuracy=0.91
│ export_model  │ completed │ output_path=./exports/model.gguf
└───────────────┴───────────┴──────────────────────────────┘
```

---

## WebSocket Real-Time Protocol

При запуске пайплайна через UI используется WebSocket для получения обновлений в реальном времени.

### Подключение

```
ws://localhost:8888/api/v1/pipeline/run
```

### Протокол

**Клиент отправляет** конфиг пайплайна:

```json
{
  "pipeline_config": {
    "pipeline": {"name": "my-pipeline"},
    "steps": [...]
  }
}
```

**Сервер отправляет** события:

1. Начало пайплайна:
```json
{
  "type": "pipeline_start",
  "name": "my-pipeline",
  "steps": ["train_sft", "eval_sft", "export_model"],
  "total": 3
}
```

2. Обновление шага (running):
```json
{
  "type": "step_update",
  "step": "train_sft",
  "index": 0,
  "status": "running",
  "step_type": "training"
}
```

3. Обновление шага (completed):
```json
{
  "type": "step_update",
  "step": "train_sft",
  "index": 0,
  "status": "completed",
  "duration_s": 342.5,
  "result_keys": ["adapter_dir", "training_loss", "global_steps"]
}
```

4. Обновление шага (skipped):
```json
{
  "type": "step_update",
  "step": "export_model",
  "index": 2,
  "status": "skipped",
  "reason": "condition not met"
}
```

5. Ошибка шага:
```json
{
  "type": "step_update",
  "step": "train_sft",
  "index": 0,
  "status": "failed",
  "error": "CUDA out of memory",
  "duration_s": 12.3
}
```

6. Завершение пайплайна:
```json
{
  "type": "pipeline_complete",
  "name": "my-pipeline",
  "steps_completed": 3,
  "output_keys": {
    "train_sft": ["adapter_dir", "training_loss"],
    "eval_sft": ["overall_accuracy"],
    "export_model": ["output_path"]
  }
}
```

7. Ошибка пайплайна (критическая):
```json
{
  "type": "pipeline_error",
  "step": "train_sft",
  "error": "Pipeline step 'train_sft' failed: CUDA out of memory"
}
```

---

## Полный пример пайплайна

```yaml
# configs/pipelines/full-e2e.yaml

pipeline:
  name: "full-e2e-pipeline"

steps:
  # 1. Вычислить отпечаток датасета (для версионирования)
  - name: fingerprint
    type: fingerprint
    config:
      dataset:
        path: "data/cam_intents.csv"

  # 2. SFT-обучение
  - name: train_sft
    type: training
    depends_on: [fingerprint]
    config:
      inherit: [base, models/qwen3.5-2b]
      task: sft
      dataset:
        path: "data/cam_intents.csv"
        format: csv
        text_column: phrase
        label_columns: [domain, skill]
        system_prompt_file: prompts/cam_taxonomy.txt
        test_size: 0.15
      training:
        epochs: 3
        learning_rate: 2e-4
        batch_size: 1
        gradient_accumulation: 16
        max_seq_length: 512
      output:
        dir: "./outputs/pipeline-sft"

  # 3. Оценка SFT-модели
  - name: eval_sft
    type: evaluation
    depends_on: [train_sft]
    config:
      model_path: "${train_sft.adapter_dir}"
      test_data_path: "data/test.csv"
      dataset:
        text_column: phrase
        label_columns: [domain, skill]
        system_prompt_file: prompts/cam_taxonomy.txt
      evaluation:
        batch_size: 8
        max_new_tokens: 128
      output:
        eval_dir: "./outputs/pipeline-eval"

  # 4. Экспорт в GGUF (только если accuracy >= 85%)
  - name: export_gguf
    type: export
    depends_on: [train_sft, eval_sft]
    condition:
      metric: "${eval_sft.overall_accuracy}"
      operator: gte
      value: 0.85
    config:
      model_path: "${train_sft.adapter_dir}"
      export:
        format: gguf
        quantization: q4_k_m
        output_path: "./exports/cam-model.gguf"

  # 5. Регистрация модели (только если экспорт выполнен)
  - name: register
    type: register
    depends_on: [export_gguf]
    config:
      name: "cam-classifier"
      model_path: "${train_sft.adapter_dir}"
      task: sft
      model:
        name: "Qwen/Qwen3.5-2B"
      _dataset_fingerprint: "${fingerprint.fingerprint}"
```

Запуск:

```bash
pulsar pipeline run configs/pipelines/full-e2e.yaml
```

!!! tip "Идемпотентность"
    Шаг `fingerprint` позволяет отслеживать, изменился ли датасет между запусками. Используйте его для автоматизации CI/CD пайплайнов: если fingerprint не изменился, можно пропустить обучение.
