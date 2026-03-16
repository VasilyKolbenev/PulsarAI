# Monitoring

Мониторинг в Pulsar AI предоставляет наблюдение за аппаратными ресурсами в реальном
времени: загрузка GPU/CPU, использование памяти, температура и энергопотребление.

---

## UI: страница мониторинга

Страница мониторинга (`/monitoring`) отображает интерактивные графики, обновляющиеся
в реальном времени:

- **GPU Utilization** -- загрузка каждого GPU в процентах
- **VRAM Usage** -- использование видеопамяти (used / total)
- **GPU Temperature** -- температура GPU в градусах Цельсия
- **GPU Power** -- энергопотребление в ваттах
- **CPU Usage** -- загрузка процессора
- **RAM Usage** -- использование оперативной памяти

!!! tip "Автообновление"
    Графики обновляются каждые 2 секунды через SSE (Server-Sent Events).
    Никакого ручного обновления страницы не требуется.

---

## Отслеживаемые метрики

| Метрика              | Поле                  | Единица | Описание                        |
|----------------------|-----------------------|---------|---------------------------------|
| CPU                  | `cpu_percent`         | %       | Загрузка процессора             |
| RAM (использовано)   | `ram_used_gb`         | GB      | Занятая оперативная память      |
| RAM (всего)          | `ram_total_gb`        | GB      | Общий объём RAM                 |
| RAM (процент)        | `ram_percent`         | %       | Процент использования RAM       |
| GPU загрузка         | `gpus[].utilization`  | %       | Загрузка GPU ядер               |
| VRAM (использовано)  | `gpus[].vram_used_gb` | GB      | Занятая видеопамять             |
| VRAM (всего)         | `gpus[].vram_total_gb`| GB      | Общий объём VRAM                |
| Температура GPU      | `gpus[].temperature`  | C       | Температура GPU                 |
| Мощность GPU         | `gpus[].power_draw`   | W       | Текущее энергопотребление       |

---

## SSE-эндпоинт: реальное время

Подключение к потоку метрик в реальном времени:

```bash
curl -N http://localhost:8000/metrics/live
```

Данные приходят каждые 2 секунды в формате SSE:

```
data: {
data:   "timestamp": "2026-03-01T14:30:52.123",
data:   "cpu_percent": 45.2,
data:   "ram_used_gb": 12.4,
data:   "ram_total_gb": 32.0,
data:   "ram_percent": 38.8,
data:   "gpus": [
data:     {
data:       "index": 0,
data:       "name": "NVIDIA RTX 4090",
data:       "utilization": 87,
data:       "vram_used_gb": 18.2,
data:       "vram_total_gb": 24.0,
data:       "temperature": 72,
data:       "power_draw": 320
data:     }
data:   ]
data: }
```

!!! info "SSE в JavaScript"
    ```javascript
    const source = new EventSource("/metrics/live");
    source.onmessage = (event) => {
      const metrics = JSON.parse(event.data);
      updateCharts(metrics);
    };
    ```

---

## Snapshot-эндпоинт

Для получения текущего снимка метрик (без подписки на поток):

```bash
curl http://localhost:8000/metrics/snapshot
```

Ответ:

```json
{
  "timestamp": "2026-03-01T14:30:52.123",
  "cpu_percent": 45.2,
  "ram_used_gb": 12.4,
  "ram_total_gb": 32.0,
  "ram_percent": 38.8,
  "gpus": [
    {
      "index": 0,
      "name": "NVIDIA RTX 4090",
      "utilization": 87,
      "vram_used_gb": 18.2,
      "vram_total_gb": 24.0,
      "temperature": 72,
      "power_draw": 320
    }
  ]
}
```

---

## Структура данных

Полная структура объекта метрик:

```python
@dataclass
class GpuMetrics:
    index: int              # индекс GPU (0, 1, 2...)
    name: str               # название GPU
    utilization: int        # загрузка в %
    vram_used_gb: float     # используемая VRAM в GB
    vram_total_gb: float    # общая VRAM в GB
    temperature: int        # температура в °C
    power_draw: int         # мощность в W

@dataclass
class SystemMetrics:
    timestamp: str          # ISO 8601
    cpu_percent: float      # загрузка CPU в %
    ram_used_gb: float      # использованная RAM в GB
    ram_total_gb: float     # общая RAM в GB
    ram_percent: float      # процент RAM
    gpus: list[GpuMetrics]  # список GPU
```

---

## Multi-GPU отображение

При наличии нескольких GPU каждый отображается отдельной строкой в таблице:

| GPU   | Модель           | Загрузка | VRAM          | Температура | Мощность |
|-------|------------------|----------|---------------|-------------|----------|
| GPU 0 | NVIDIA RTX 4090  | 87%      | 18.2 / 24.0 GB | 72 C       | 320 W    |
| GPU 1 | NVIDIA RTX 4090  | 92%      | 20.1 / 24.0 GB | 75 C       | 335 W    |
| GPU 2 | NVIDIA A100      | 65%      | 52.3 / 80.0 GB | 58 C       | 250 W    |

!!! warning "Пороговые значения"
    Система выделяет метрики цветом в UI:

    - **Температура** > 80 C -- жёлтый, > 90 C -- красный
    - **VRAM** > 90% -- жёлтый, > 95% -- красный
    - **GPU загрузка** < 10% -- серый (возможно, GPU простаивает)

!!! note "Без GPU"
    Если GPU не обнаружен, раздел `gpus` будет пустым массивом.
    Метрики CPU и RAM по-прежнему доступны.
