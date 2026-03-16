# Разделение стендов: Demo и Product Dev

Этот документ разделяет два независимых контура:

- `Demo stand` - стабильный сценарий для инвестора с детерминированными данными.
- `Product dev stand` - реальный контур разработки под `prod-ready` требования.

## Важно по ссылкам

Причина падений вида `ERR_CONNECTION_REFUSED` была в том, что открывался порт, на котором процесс не запущен, или запускался старый `pulsar ui` из другого окружения.

Теперь UI всегда поднимается через `scripts/run_ui_server.py` из текущего репозитория.

## 1) Demo stand (инвестор)

Старт (стабильный, с перезапуском старого процесса):

```powershell
cd C:\Users\User\Desktop\pulsar-ai
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_investor_demo.ps1 -ForceRestart
```

Открывать:

```text
http://127.0.0.1:18088/experiments
```

Проверка статуса:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\status_ui_persistent.ps1 -Port 18088
```

Остановка:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_ui_persistent.ps1 -Port 18088
```

## 2) Product Dev stand (prod-ready разработка)

Старт:

```powershell
cd C:\Users\User\Desktop\pulsar-ai
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_prod_ready_dev.ps1 -ForceRestart
```

Открывать:

```text
http://127.0.0.1:18888/experiments
```

Что делает скрипт:

1. Загружает профиль `.env.prod-ready.example`.
2. Включает `PULSAR_AUTH_ENABLED=true`.
3. Генерирует API-ключ `prod-dev-admin`.
4. Сохраняет ключ в `outputs/access/prod-dev-admin.key`.
5. Печатает ссылку входа вида `http://127.0.0.1:18888/?api_key=<KEY>`.
6. Поднимает UI в фоновом режиме через `start_ui_persistent.ps1`.

## 3) Реальная модель (DPO) для dev контура

Запуск DPO (пример Qwen3.5-2B):

```powershell
cd C:\Users\User\Desktop\pulsar-ai
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_dpo_qwen35_2b.ps1
```

## 4) Минимальный чеклист prod-ready

1. Auth включен (`PULSAR_AUTH_ENABLED=true`).
2. CORS ограничен только нужными origin.
3. API-ключи выдаются по ролям, ротация и revoke протестированы.
4. Логи и артефакты тренировок сохраняются в `outputs/`.
5. Экспорт модели и eval повторяемы из CI/CD сценария.
6. Demo и product окружения разделены по портам, профилям и данным.
