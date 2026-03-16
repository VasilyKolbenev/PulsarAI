# Оценка модели (Evaluation)

## Обзор

Evaluation в pulsar-ai -- это автоматическая оценка качества обученной модели на тестовых данных. Система запускает batch-инференс, парсит ответы модели (JSON), сравнивает с ground truth и вычисляет метрики: accuracy, F1, JSON parse rate, confusion matrix.

---

## Запуск оценки

=== "CLI"

    ```bash
    # Базовый запуск
    pulsar eval \
      --model ./outputs/cam-sft/lora \
      --test-data data/test.csv

    # С указанием конфига и выходной директории
    pulsar eval \
      --model ./outputs/cam-sft/lora \
      --test-data data/test.csv \
      --config configs/tasks/eval.yaml \
      --output reports/cam-eval/ \
      --batch-size 8
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8888/api/evaluation/run \
      -H "Content-Type: application/json" \
      -d '{
        "model_path": "./outputs/cam-sft/lora",
        "test_data_path": "data/test.csv",
        "dataset": {
          "text_column": "phrase",
          "label_columns": ["domain", "skill"],
          "system_prompt_file": "prompts/cam_taxonomy.txt"
        },
        "evaluation": {
          "batch_size": 8,
          "max_new_tokens": 128
        }
      }'
    ```

=== "Скрипт"

    ```python
    from pulsar_ai.evaluation.runner import run_evaluation

    config = {
        "model_path": "./outputs/cam-sft/lora",
        "test_data_path": "data/test.csv",
        "dataset": {
            "text_column": "phrase",
            "label_columns": ["domain", "skill"],
            "system_prompt_file": "prompts/cam_taxonomy.txt",
        },
        "evaluation": {
            "batch_size": 8,
            "max_new_tokens": 128,
        },
        "output": {
            "eval_dir": "./outputs/eval",
        },
    }

    results = run_evaluation(config)
    print(f"Accuracy: {results['overall_accuracy']:.2%}")
    print(f"F1: {results.get('f1_weighted', {}).get('f1', 0):.4f}")
    ```

---

## Метрики

### Основные метрики

| Метрика | Описание | Формула |
|---|---|---|
| `overall_accuracy` | Доля полностью правильных ответов (все label_columns совпали) | correct / total |
| `json_parse_rate` | Доля ответов, успешно распарсенных как JSON | parsed / total |
| `f1_weighted` | Взвешенный F1 по классам (учитывает дисбаланс) | sklearn weighted F1 |
| `precision` | Точность (доля корректных среди предсказанных) | TP / (TP + FP) |
| `recall` | Полнота (доля найденных среди всех реальных) | TP / (TP + FN) |

### Per-column метрики

Для каждого столбца из `label_columns` вычисляется отдельная accuracy и per-class breakdown:

```json
{
  "per_column": {
    "domain": {
      "accuracy": 0.92,
      "correct": 460,
      "total": 500,
      "per_class": {
        "finance": {"accuracy": 0.95, "correct": 38, "count": 40},
        "health":  {"accuracy": 0.88, "correct": 44, "count": 50}
      }
    }
  }
}
```

### Confusion Matrix

Матрица ошибок для основного столбца (первый в `label_columns`):

```json
{
  "confusion_matrix": {
    "labels": ["finance", "health", "tech", "PARSE_ERROR"],
    "matrix": [
      [38, 1, 0, 1],
      [2, 44, 3, 1],
      [0, 1, 47, 2],
      [0, 0, 0, 0]
    ]
  }
}
```

!!! note "PARSE_ERROR"
    Метка `PARSE_ERROR` появляется, когда модель выдала невалидный JSON или JSON без нужного поля. Высокая доля PARSE_ERROR -- сигнал к DPO-обучению.

---

## LLM-as-Judge

Помимо автоматических метрик, pulsar-ai поддерживает оценку с помощью другой LLM (LLM-as-Judge). Судья оценивает ответы по нескольким критериям:

| Критерий | Описание | Шкала |
|---|---|---|
| `helpfulness` | Насколько ответ полезен для пользователя | 1-5 |
| `accuracy` | Фактическая точность ответа | 1-5 |
| `coherence` | Структурированность и связность | 1-5 |
| `safety` | Отсутствие вредного контента | 1-5 |

Пример использования:

```python
from pulsar_ai.evaluation.llm_judge import LLMJudge, JudgeCriterion

# Инициализация с кастомными критериями
judge = LLMJudge(criteria=[
    JudgeCriterion("format_compliance", "Ответ в правильном JSON формате", weight=2.0),
    JudgeCriterion("accuracy", "Правильность классификации", weight=1.5),
    JudgeCriterion("completeness", "Все обязательные поля заполнены", weight=1.0),
])

# Построить промпт для судьи
prompt = judge.build_prompt(
    instruction="Классифицируй: 'Закажи такси'",
    response='{"domain": "transport", "skill": "taxi"}',
)

# Отправить промпт судье (через ваш LLM API), получить ответ
judge_output = "format_compliance: 5 | Валидный JSON\naccuracy: 4 | Правильный домен\n..."

# Распарсить результаты
result = judge.evaluate(
    instruction="Классифицируй: 'Закажи такси'",
    response='{"domain": "transport", "skill": "taxi"}',
    judge_output=judge_output,
)
print(f"Overall score: {result.overall_score}")
```

Судья также поддерживает **попарное сравнение** (pairwise comparison) для A/B тестирования двух моделей:

```python
comparison_prompt = judge.build_comparison_prompt(
    instruction="Классифицируй: 'Закажи такси'",
    response_a='{"domain": "transport"}',
    response_b='{"domain": "transport", "skill": "taxi"}',
)
```

---

## Хранение результатов

Результаты оценки сохраняются в experiment store и привязываются к эксперименту:

```
outputs/eval/
├── eval_results.json       # все метрики в JSON
├── eval_report.html        # HTML отчёт с графиками
└── predictions.jsonl       # все предсказания с input/output/parsed
```

При автоматической оценке после SFT (auto-eval) результаты записываются в `results.eval_results` эксперимента.

---

## Просмотр в UI

1. Откройте **Experiments** в Web UI
2. Выберите завершённый эксперимент
3. Вкладка **Evaluation** показывает:
    - Общие метрики (accuracy, F1, parse rate)
    - Per-class accuracy с цветовой кодировкой
    - Confusion matrix (heatmap)
    - Таблицу предсказаний с фильтрацией по правильности

---

## Сравнение экспериментов

Для сравнения нескольких обученных моделей:

=== "CLI"

    ```bash
    pulsar runs compare run_abc123 run_def456 run_ghi789
    ```

    Выводит таблицу с отличиями конфигов и метрик side-by-side.

=== "UI"

    1. На странице **Experiments** выберите 2+ эксперимента (чекбоксы)
    2. Нажмите **Compare**
    3. Увидите сравнительную таблицу:
        - Различия в конфигурации (lr, epochs, model, ...)
        - Сравнение метрик (accuracy, F1, loss)
        - Графики loss по шагам на одном графике

!!! tip "Быстрое сравнение SFT vs DPO"
    Обучите SFT, затем DPO, и сравните оба эксперимента. Типичное улучшение DPO: +5-10% accuracy и +5-8% parse rate.
