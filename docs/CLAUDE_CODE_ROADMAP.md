# Claude Code Roadmap

## Цель

Этот документ нужен как прямой рабочий backlog для Claude Code. Нужно не переписывать проект целиком, а последовательно довести его от `demo-ready / dev-ready` до более устойчивого `production-capable` состояния.

Главный принцип: работать фазами, не смешивать инфраструктурные изменения с UX-полировкой, после каждой фазы оставлять код в рабочем состоянии.

## Как работать по этому документу

1. Брать в работу одну фазу за раз.
2. Перед изменениями читать перечисленные файлы-ориентиры.
3. После каждой фазы запускать релевантные тесты и фиксировать, что именно проверено.
4. Не делать широких рефакторингов вне текущей фазы без явной причины.
5. Если в процессе найдется новый риск, дополнять этот документ, а не держать знания только в чате.

## Текущее состояние проекта

Проект уже выглядит как сильная demo/platform-база:

- есть крупный Python backend и React UI;
- есть много документации;
- есть заметный набор unit-тестов;
- фронтенд собирается успешно.

Но на текущем этапе это еще не полноценное production-ready решение. Основные ограничения связаны с persistence, runtime state, безопасностью, устойчивостью remote execution, тестовой инфраструктурой и масштабируемостью UI.

## Подтвержденные слабые места

### 1. JSON stores как основное хранилище

Это самый важный технический долг во всем проекте.

Сейчас несколько критичных подсистем используют схему `load -> mutate -> save` поверх JSON-файлов. В таком виде нет транзакций, блокировок, нормальной конкурентной записи и уверенного восстановления после падения процесса.

Файлы-ориентиры:

- `src/pulsar_ai/ui/experiment_store.py`
- `src/pulsar_ai/ui/workflow_store.py`
- `src/pulsar_ai/prompts/store.py`
- `src/pulsar_ai/tracking.py`
- `src/pulsar_ai/ui/auth.py`
- `src/pulsar_ai/compute/manager.py`

### 2. Runtime state живет только в памяти процесса

Jobs, assistant sessions, site chat sessions, protocol state и часть run-метаданных хранятся в module-level памяти. После рестарта процесса состояние теряется. В multi-worker или service-режиме это станет источником рассинхрона.

Файлы-ориентиры:

- `src/pulsar_ai/ui/jobs.py`
- `src/pulsar_ai/ui/assistant.py`
- `src/pulsar_ai/ui/routes/site_chat.py`
- `src/pulsar_ai/ui/routes/pipeline_run.py`
- `src/pulsar_ai/ui/routes/protocols.py`

### 3. Security debt вокруг API keys и auth flow

Есть удобные для демо решения, которые не стоит тащить дальше без ужесточения:

- bootstrap ключа через URL/query string;
- сохранение ключа в `localStorage`;
- логирование plaintext default key в bootstrap-сценариях;
- неравномерная строгость между public/demo и authenticated flow.

Файлы-ориентиры:

- `src/pulsar_ai/ui/app.py`
- `src/pulsar_ai/ui/auth.py`
- `ui/src/api/client.ts`

### 4. Дублирование логики pipeline execution

Часть исполнения pipeline уже оформлена в executor, но WebSocket path все еще исполняет шаги отдельной логикой. Это риск дрейфа поведения, статусов, логирования и обработки ошибок.

Файлы-ориентиры:

- `src/pulsar_ai/pipeline/executor.py`
- `src/pulsar_ai/ui/routes/pipeline_run.py`

### 5. Remote compute еще не production-hardened

Удаленное выполнение по SSH уже полезно, но пока недостаточно жесткое по lifecycle и error handling:

- команды собираются строками;
- quoting и shell safety хрупкие;
- heartbeat и recovery ограничены;
- remote bootstrap и capture exit status не доведены до зрелого состояния.

Файлы-ориентиры:

- `src/pulsar_ai/compute/ssh.py`
- `src/pulsar_ai/compute/remote_runner.py`
- `src/pulsar_ai/compute/manager.py`

### 6. Frontend быстро растет в монолит

Крупные страницы и хуки уже начали ухудшать сопровождаемость. Кроме того, у UI пока нет нормального frontend test stack, а сборка уже предупреждает о тяжелом основном bundle.

Файлы-ориентиры:

- `ui/src/pages/Experiments.tsx`
- `ui/src/pages/PromptLab.tsx`
- `ui/src/hooks/useWorkflow.ts`
- `ui/package.json`

### 7. Тестовая инфраструктура на Windows нестабильна

В локальной проверке заметны проблемы с `pytest` temp/cache каталогами и `PermissionError`, из-за чего часть сбоев относится не к бизнес-логике, а к harness/окружению. Это мешает честно мерить качество изменений.

Файлы-ориентиры:

- `pyproject.toml`
- `tests/`

## Общая стратегия

Разработка должна идти в такой последовательности:

1. Сначала вынести в порядок persistence и durable state.
2. Потом закрыть security и execution consistency.
3. Затем укрепить remote compute.
4. После этого разрезать фронтенд, улучшить UX и добавить frontend tests.
5. Отдельной фазой стабилизировать test harness и CI.

Не надо начинать с косметических UI-улучшений, пока базовая надежность хранения и исполнения не решена.

## Фаза 1. Единый persistence layer

### Цель

Уйти от разрозненных JSON store к единому устойчивому слою хранения.

### Что сделать

- Ввести SQLite как базовое локальное хранилище.
- Добавить schema bootstrap и migrations.
- Сделать repository layer для experiments, prompts, workflows, API keys, compute targets и run tracking.
- Добавить миграцию данных из существующих JSON-файлов.
- Сохранить обратную совместимость на период миграции, если это возможно без лишней сложности.

### Критерии готовности

- Создание, чтение, обновление и удаление всех ключевых сущностей работают через единый слой.
- Нет прямых `load -> mutate -> save` в runtime-критичных местах.
- Есть тесты на конкурентные обновления и на восстановление после рестарта процесса.
- Существующие данные можно автоматически поднять из старого формата.

### Файлы-ориентиры

- `src/pulsar_ai/ui/experiment_store.py`
- `src/pulsar_ai/ui/workflow_store.py`
- `src/pulsar_ai/prompts/store.py`
- `src/pulsar_ai/tracking.py`
- `src/pulsar_ai/ui/auth.py`
- `src/pulsar_ai/compute/manager.py`

## Фаза 2. Durable jobs, sessions и recovery

### Цель

Сделать runtime state переживающим рестарты и не зависящим только от памяти одного процесса.

### Что сделать

- Вынести job registry в storage-backed слой.
- Сохранять assistant/site sessions в durable store.
- Добавить restart reconciliation для зависших runs и jobs.
- Ввести cleanup policy, TTL и фоновую уборку старых сессий.

### Критерии готовности

- После рестарта приложения статусы jobs и runs восстанавливаются или корректно переводятся в terminal state.
- Сессии не исчезают просто из-за перезапуска процесса.
- Есть явный reconcile path для stale/incomplete runs.

### Файлы-ориентиры

- `src/pulsar_ai/ui/jobs.py`
- `src/pulsar_ai/ui/assistant.py`
- `src/pulsar_ai/ui/routes/site_chat.py`
- `src/pulsar_ai/ui/routes/pipeline_run.py`
- `src/pulsar_ai/tracking.py`

## Фаза 3. Security hardening

### Цель

Убрать демо-упрощения из безопасности и сделать auth/key flow предсказуемым.

### Что сделать

- Убрать bootstrap API key через URL.
- Перестать логировать plaintext keys.
- Пересмотреть хранение ключей на клиенте.
- Добавить audit trail для key creation/revocation.
- Ужесточить public/demo route policy.
- Добавить security regression tests.

### Критерии готовности

- Ключи не передаются через query string.
- В логах нет plaintext секретов.
- Есть тесты на auth, forbidden access и key lifecycle.
- Поведение demo-режима и protected-режима явно разделено.

### Файлы-ориентиры

- `src/pulsar_ai/ui/app.py`
- `src/pulsar_ai/ui/auth.py`
- `ui/src/api/client.ts`
- `tests/test_auth.py`
- `tests/test_security.py`

## Фаза 4. Единый execution engine для pipeline

### Цель

Убрать дублирование исполнения и свести sync/WebSocket сценарии к одному движку.

### Что сделать

- Вынести всю бизнес-логику pipeline run в один service/executor path.
- Перевести WebSocket stream на использование того же execution engine.
- Унифицировать статусы, ошибки, events и tracking.
- Сохранить совместимость API, если это не мешает надежности.

### Критерии готовности

- Оба режима исполнения используют один и тот же engine.
- Нет ручного дублирования step loop в route handler.
- Ошибки и terminal states совпадают независимо от транспорта.

### Файлы-ориентиры

- `src/pulsar_ai/pipeline/executor.py`
- `src/pulsar_ai/ui/routes/pipeline_run.py`
- `tests/test_pipeline_executor.py`

## Фаза 5. Remote compute hardening

### Цель

Сделать удаленное выполнение более надежным, безопасным и наблюдаемым.

### Что сделать

- Ввести безопасный command builder вместо свободной сборки строк.
- Добавить remote bootstrap script с предсказуемым окружением.
- Захватывать exit code, stderr, heartbeat и timeout reason.
- Явно оформлять артефакты, логи и remote metadata.
- Добавить retry policy там, где она реально оправдана.

### Критерии готовности

- Удаленные задачи корректно завершаются и оставляют понятный terminal state.
- Ошибки подключения, таймауты и remote failures различаются в UI и API.
- Есть integration-like tests хотя бы на локально эмулируемом уровне.

### Файлы-ориентиры

- `src/pulsar_ai/compute/ssh.py`
- `src/pulsar_ai/compute/remote_runner.py`
- `src/pulsar_ai/ui/routes/compute.py`
- `tests/test_compute.py`

## Фаза 6. Frontend decomposition, UX и tests

### Цель

Сделать UI более поддерживаемым и менее тяжелым.

### Что сделать

- Разбить большие страницы на feature slices и smaller components.
- Добавить lazy loading для тяжелых экранов.
- Убрать silent `.catch(() => {})`, где они прячут проблемы.
- Ввести Vitest и React Testing Library.
- Добавить хотя бы smoke-проверки для ключевых сценариев.
- Снизить размер основного bundle.

### Критерии готовности

- Ключевые страницы не состоят из одного большого файла.
- Есть frontend unit/integration tests.
- Сборка не ругается на чрезмерно тяжелый основной bundle или это предупреждение заметно снижено.

### Файлы-ориентиры

- `ui/src/pages/Experiments.tsx`
- `ui/src/pages/PromptLab.tsx`
- `ui/src/hooks/useWorkflow.ts`
- `ui/src/App.tsx`
- `ui/package.json`

## Фаза 7. Protocols и assistant: из demo-mode в product-mode

### Цель

Убрать витринность там, где система уже претендует на продуктовый сценарий.

### Что сделать

- Перевести protocols config/state в durable и управляемый lifecycle.
- Добавить health/readiness semantics.
- Убрать хардкод продуктовых фактов из site chat, где это возможно.
- Свести assistant behavior к более явным policy/config/data sources.

### Критерии готовности

- Protocol servers имеют понятный lifecycle и состояние после рестарта.
- Assistant/site chat меньше зависят от хардкода и легче обновляются.
- Demo content отделен от реального operational behavior.

### Файлы-ориентиры

- `src/pulsar_ai/ui/routes/protocols.py`
- `src/pulsar_ai/ui/assistant.py`
- `src/pulsar_ai/ui/routes/site_chat.py`
- `tests/test_protocols.py`
- `tests/test_site_chat.py`

## Фаза 8. Test harness и CI stabilization

### Цель

Сделать проверки воспроизводимыми и надежными на целевых окружениях, включая Windows.

### Что сделать

- Стабилизировать работу временных директорий и cache-путей для `pytest`.
- Явно настроить test temp roots для Windows.
- Разделить backend/frontend проверки в CI.
- Добавить coverage artifacts и более понятную диагностику падений.

### Критерии готовности

- Локальный `pytest` не сыпется инфраструктурными `PermissionError` на temp-пути.
- CI дает воспроизводимый сигнал о качестве.
- Backend и frontend проверяются отдельно и прозрачно.

### Файлы-ориентиры

- `pyproject.toml`
- `tests/`
- `.github/` или другой CI-конфиг, если появится

## Быстрые win-задачи до больших фаз

Это можно делать параллельно, если не мешает основным фазам:

- перестать логировать plaintext default API key;
- убрать `api_key` bootstrap из URL/query string;
- добавить ручной `reconcile stale runs` action в UI или CLI;
- явно помечать зависшие runs и показывать причину в интерфейсе;
- заменить silent `.catch(() => {})` в UI на контролируемую обработку ошибок;
- первым делом разрезать `ui/src/pages/Experiments.tsx` на более мелкие части.

## Порядок выполнения для Claude Code

Рекомендуемая последовательность:

1. Фаза 1.
2. Фаза 2.
3. Фаза 3.
4. Фаза 4.
5. Фаза 5.
6. Фаза 6.
7. Фаза 7.
8. Фаза 8.

Если ресурсов мало, нельзя прыгать сразу к frontend polishing и игнорировать persistence/security.

## Первый рекомендуемый старт

Начать с Фазы 1 и сделать минимальный, но законченный вертикальный срез:

1. Ввести SQLite schema и bootstrap.
2. Добавить migration path из JSON.
3. Перевести `ExperimentStore` и `PromptStore` на новый persistence layer.
4. Оставить UI API максимально совместимым.
5. Добавить тесты на persistence, migration и concurrent update scenarios.

Именно это даст самый полезный фундамент для всех следующих этапов.
