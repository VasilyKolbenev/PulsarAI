# HPO / Sweep

## Что такое HPO

**Hyperparameter Optimization (HPO)** -- автоматический поиск оптимальных гиперпараметров
обучения. Вместо ручного перебора значений learning rate, batch size и других параметров,
HPO систематически исследует пространство поиска, используя алгоритмы Bayesian Optimization,
Random Search или Grid Search, и находит комбинацию параметров, дающую лучшую метрику
на валидационном наборе.

---

## Установка

HPO-модуль устанавливается как опциональная зависимость:

```bash
pip install -e ".[hpo]"
```

!!! note "Зависимости"
    Пакет `.[hpo]` устанавливает [Optuna](https://optuna.org/) в качестве бэкенда
    оптимизации. Optuna поддерживает эффективный Bayesian Search (TPE) из коробки.

---

## Структура конфигурации Sweep

Sweep-конфигурация -- это YAML-файл, описывающий метод поиска, целевую метрику
и пространство параметров:

```yaml
hpo:
  method: bayesian        # bayesian | random | grid
  metric: eval_loss       # целевая метрика
  direction: minimize     # minimize | maximize
  n_trials: 20            # количество испытаний

search_space:
  learning_rate:
    type: log-float
    min: 1.0e-5
    max: 1.0e-3

  weight_decay:
    type: linear-float
    min: 0.0
    max: 0.3

  num_train_epochs:
    type: integer
    min: 1
    max: 5

  warmup_strategy:
    type: categorical
    values: ["linear", "cosine", "constant"]

  per_device_train_batch_size:
    type: categorical
    values: [4, 8, 16]
```

---

## Типы пространства поиска

| Тип            | Формат              | Описание                                    | Пример                            |
|----------------|---------------------|---------------------------------------------|------------------------------------|
| `log-float`    | `[min, max, log]`   | Логарифмическая шкала для дробных чисел     | learning_rate: `1e-5` ... `1e-3`  |
| `linear-float` | `[min, max]`       | Линейная шкала для дробных чисел            | weight_decay: `0.0` ... `0.3`     |
| `integer`      | `[min, max, int]`  | Целочисленный диапазон                      | epochs: `1` ... `5`               |
| `categorical`  | `[val1, val2, ...]`| Выбор из фиксированного набора значений     | scheduler: `linear`, `cosine`     |

!!! tip "Когда использовать log-float"
    Используйте `log-float` для параметров, которые варьируются на несколько порядков,
    например learning rate (`1e-5` ... `1e-3`). Это обеспечивает равномерное исследование
    каждого порядка величины.

---

## Запуск Sweep

=== "CLI"

    ```bash
    # Базовый запуск
    pulsar sweep configs/sft_config.yaml sweep_config.yaml

    # С параметрами
    pulsar sweep configs/sft_config.yaml sweep_config.yaml \
      --n-trials 20 \
      --name my-lr-search

    # С ограничением GPU
    pulsar sweep configs/sft_config.yaml sweep_config.yaml \
      --n-trials 30 \
      --name full-search \
      --gpu 0
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/sweep \
      -H "Content-Type: application/json" \
      -d '{
        "base_config": "configs/sft_config.yaml",
        "sweep_config": "sweep_config.yaml",
        "n_trials": 20,
        "name": "my-lr-search"
      }'
    ```

!!! warning "Ресурсы"
    Каждое испытание -- это полный цикл обучения. Sweep из 20 испытаний с 3 эпохами
    каждое потребует ресурсов на 60 эпох обучения. Начинайте с малого числа `n_trials`
    и коротких тренировок для калибровки.

---

## Результаты

Результаты сохраняются в `./data/sweeps/NAME.json`:

```json
{
  "name": "my-lr-search",
  "method": "bayesian",
  "metric": "eval_loss",
  "direction": "minimize",
  "n_trials": 20,
  "best_trial": {
    "number": 14,
    "value": 0.847,
    "params": {
      "learning_rate": 2.3e-4,
      "weight_decay": 0.05,
      "num_train_epochs": 3,
      "warmup_strategy": "cosine",
      "per_device_train_batch_size": 8
    }
  },
  "trials": [
    {
      "number": 0,
      "value": 1.234,
      "params": {"learning_rate": 5.1e-5, "...": "..."}
    }
  ]
}
```

Просмотр результатов:

=== "CLI"

    ```bash
    # Лучшие параметры
    pulsar sweep results my-lr-search

    # Топ-5 испытаний
    pulsar sweep results my-lr-search --top 5

    # Таблица всех испытаний
    pulsar sweep results my-lr-search --all
    ```

=== "API"

    ```bash
    curl http://localhost:8000/sweeps/my-lr-search
    ```

---

## Использование лучших параметров

После завершения sweep примените лучшие параметры к следующему обучению:

```bash
# Автоматически подставить лучшие параметры из sweep
pulsar train configs/sft_config.yaml \
  --from-sweep my-lr-search
```

Или вручную обновите конфигурацию:

```yaml
# configs/sft_config.yaml (обновлённый)
training:
  learning_rate: 2.3e-4        # из sweep
  weight_decay: 0.05           # из sweep
  num_train_epochs: 3          # из sweep
  warmup_strategy: cosine      # из sweep
  per_device_train_batch_size: 8  # из sweep
```

!!! info "Итеративный процесс"
    HPO можно запускать итеративно: сначала грубый поиск с широким диапазоном и малым
    числом trials, затем уточняющий поиск с сужённым диапазоном вокруг лучших значений.

    ```bash
    # Шаг 1: грубый поиск
    pulsar sweep config.yaml sweep_coarse.yaml --n-trials 10 --name coarse

    # Шаг 2: уточняющий поиск
    pulsar sweep config.yaml sweep_fine.yaml --n-trials 20 --name fine
    ```
