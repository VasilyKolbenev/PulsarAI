# Compute Management

Управление вычислительными ресурсами позволяет запускать обучение не только на локальной
машине, но и на удалённых серверах через SSH. Pulsar AI автоматически определяет доступные GPU
и управляет подключениями.

---

## Локальная машина

Локальная машина добавляется автоматически при первом запуске Pulsar AI:

```json
{
  "id": "local",
  "name": "Local Machine",
  "type": "local",
  "status": "online",
  "gpus": [
    {
      "index": 0,
      "name": "NVIDIA RTX 4090",
      "vram_gb": 24.0
    }
  ]
}
```

!!! note "Авто-определение"
    GPU обнаруживаются через `nvidia-smi`. Если NVIDIA-драйверы не установлены,
    раздел `gpus` будет пустым, и обучение будет выполняться на CPU.

---

## Добавление SSH-серверов

=== "CLI"

    ```bash
    pulsar compute add \
      --name "gpu-server-1" \
      --host 192.168.1.100 \
      --user ubuntu \
      --port 22 \
      --key-path ~/.ssh/id_rsa
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/compute/targets \
      -H "Content-Type: application/json" \
      -d '{
        "name": "gpu-server-1",
        "host": "192.168.1.100",
        "user": "ubuntu",
        "port": 22,
        "key_path": "~/.ssh/id_rsa"
      }'
    ```

=== "UI"

    В веб-интерфейсе нажмите **Add Target** на странице Compute.
    Заполните поля в модальном окне:

    | Поле       | Описание                         | Пример             |
    |------------|----------------------------------|---------------------|
    | Name       | Понятное имя сервера             | `gpu-server-1`      |
    | Host       | IP-адрес или hostname            | `192.168.1.100`     |
    | User       | SSH-пользователь                 | `ubuntu`            |
    | Port       | SSH-порт                         | `22`                |
    | Key Path   | Путь к SSH-ключу                 | `~/.ssh/id_rsa`     |

---

## Тест подключения

После добавления сервера проверьте SSH-соединение:

=== "CLI"

    ```bash
    pulsar compute test gpu-server-1
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/compute/targets/gpu-server-1/test
    ```

Ответ:

```json
{
  "target_id": "gpu-server-1",
  "status": "ok",
  "latency_ms": 23,
  "message": "Connection successful"
}
```

!!! warning "Ошибки подключения"
    Частые причины ошибок:

    - **Connection refused** -- SSH-сервер не запущен или указан неверный порт
    - **Authentication failed** -- неверный ключ или пользователь
    - **Timeout** -- сервер недоступен, проверьте сеть и файрвол

---

## Обнаружение GPU

После успешного подключения определите GPU на удалённом сервере:

=== "CLI"

    ```bash
    pulsar compute detect gpu-server-1
    ```

=== "API"

    ```bash
    curl -X POST http://localhost:8000/compute/targets/gpu-server-1/detect
    ```

Ответ:

```json
{
  "target_id": "gpu-server-1",
  "gpu_count": 4,
  "gpu_type": "NVIDIA A100",
  "vram_gb": 80.0,
  "driver_version": "535.129.03",
  "cuda_version": "12.2",
  "gpus": [
    {"index": 0, "name": "NVIDIA A100-SXM4-80GB", "vram_gb": 80.0},
    {"index": 1, "name": "NVIDIA A100-SXM4-80GB", "vram_gb": 80.0},
    {"index": 2, "name": "NVIDIA A100-SXM4-80GB", "vram_gb": 80.0},
    {"index": 3, "name": "NVIDIA A100-SXM4-80GB", "vram_gb": 80.0}
  ]
}
```

---

## Требования к удалённой машине

Перед добавлением удалённого сервера убедитесь, что выполнены все требования:

| Требование            | Описание                                          |
|-----------------------|---------------------------------------------------|
| SSH-доступ            | Открытый SSH-порт, авторизация по ключу           |
| NVIDIA-драйверы       | Установлены и обновлены                           |
| `nvidia-smi`          | Доступен в `$PATH`                                |
| CUDA Toolkit          | Версия, совместимая с PyTorch                     |
| Python 3.10+          | Установлен на удалённой машине                    |
| Свободное место       | Достаточно для модели, датасета и чекпоинтов      |

!!! tip "Быстрая проверка"
    Подключитесь к серверу и выполните:

    ```bash
    ssh ubuntu@192.168.1.100 "nvidia-smi && python3 --version"
    ```

    Если обе команды выполняются успешно, сервер готов к работе.

---

## Управление серверами

### Список серверов

=== "CLI"

    ```bash
    pulsar compute list
    ```

=== "API"

    ```bash
    curl http://localhost:8000/compute/targets
    ```

### Удаление сервера

=== "CLI"

    ```bash
    pulsar compute remove gpu-server-1
    ```

=== "API"

    ```bash
    curl -X DELETE http://localhost:8000/compute/targets/gpu-server-1
    ```

### Выбор сервера для обучения

```bash
pulsar train configs/sft_config.yaml --target gpu-server-1
```

!!! info "Автовыбор"
    Если `--target` не указан, обучение запускается на локальной машине.
    В будущих версиях планируется автоматический выбор сервера с наибольшим
    количеством свободной VRAM.
