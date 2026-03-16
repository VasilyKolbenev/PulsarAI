# Task Packets

## Назначение

Этот файл содержит готовые task packets для совместной работы Claude Code и Codex. Его задача убрать лишнюю ручную постановку и дать короткие, исполнимые единицы работы, которые можно запускать по одной.

Использовать вместе с файлами:

- `AGENTS.md`
- `docs/CLAUDE_CODE_ROADMAP.md`
- `docs/CLAUDE_CODE_EXECUTION_PROMPT.md`
- `docs/MULTI_AGENT_OPERATING_MODEL.md`

## Как использовать

1. Выбери один packet.
2. Отдай его целиком Claude Code или Codex.
3. Не запускай одновременно два packet, которые меняют одни и те же файлы.
4. После завершения зафиксируй результат и переходи к следующему packet.

## Packet 01. SQLite Foundation

### Owner

Claude Code

### Goal

Ввести минимальный, но рабочий SQLite persistence layer для критичного состояния проекта.

### Scope

- создать базовый storage module;
- добавить schema bootstrap;
- подготовить migration scaffold из JSON.

### Files to inspect first

- `src/pulsar_ai/ui/experiment_store.py`
- `src/pulsar_ai/prompts/store.py`
- `src/pulsar_ai/tracking.py`
- `pyproject.toml`
- связанные tests для store и tracking.

### Work

1. Спроектировать минимальный SQLite backend.
2. Добавить инициализацию схемы.
3. Добавить простой migration/bootstrap path.
4. Не переводить сразу все stores, если это раздувает diff.

### Verification

- unit tests для storage bootstrap;
- smoke test на создание базы и чтение схемы.

### Done When

- есть отдельный persistence слой;
- база создается автоматически;
- есть понятная точка для миграции JSON в SQLite.

### Start Prompt

```md
Read `AGENTS.md`, `docs/CLAUDE_CODE_ROADMAP.md`, `docs/CLAUDE_CODE_EXECUTION_PROMPT.md`, and `docs/MULTI_AGENT_OPERATING_MODEL.md`.

Implement Packet 01 from `docs/TASK_PACKETS.md`: create a minimal SQLite persistence foundation with schema bootstrap and a migration scaffold from JSON. Keep the scope tight and leave the repository in a verifiable state.
```

## Packet 02. ExperimentStore Migration

### Owner

Claude Code

### Goal

Перевести `ExperimentStore` на новый persistence layer без ломки текущего UI/API поведения.

### Files to inspect first

- `src/pulsar_ai/ui/experiment_store.py`
- `src/pulsar_ai/ui/routes/experiments.py`
- связанные tests.

### Work

1. Подключить новый persistence слой.
2. Перенести create/read/update paths.
3. Сохранить максимально совместимые возвращаемые структуры.
4. Добавить migration path из текущего JSON store.

### Verification

- tests для CRUD;
- smoke path для списка экспериментов и обновления статуса.

### Done When

- `ExperimentStore` больше не зависит от `load -> mutate -> save` в runtime-критичном path;
- тесты на основные сценарии проходят.

### Start Prompt

```md
Read the repository instructions and implement Packet 02 from `docs/TASK_PACKETS.md`. Migrate `ExperimentStore` to the new persistence layer while keeping the API behavior stable. Update tests and run the relevant checks.
```

## Packet 03. PromptStore Migration

### Owner

Claude Code

### Goal

Перевести `PromptStore` на новый persistence layer и выровнять его с новой storage моделью.

### Files to inspect first

- `src/pulsar_ai/prompts/store.py`
- `src/pulsar_ai/ui/routes/prompts.py`
- связанные tests.

### Work

1. Перевести хранение prompts на новый backend.
2. Добавить миграцию старых данных.
3. Проверить совместимость API и UI.

### Verification

- tests на создание, редактирование, удаление prompts;
- smoke path для prompt listing.

### Done When

- prompts читаются и пишутся через единый persistence layer;
- migration из старого формата работает.

### Start Prompt

```md
Read the repository instructions and implement Packet 03 from `docs/TASK_PACKETS.md`. Migrate `PromptStore` to the new persistence backend, preserve compatibility, and update the tests.
```

## Packet 04. Persistence Concurrency Tests

### Owner

Codex

### Goal

Поймать race conditions и регрессии в новом persistence layer.

### Files to inspect first

- новый storage module;
- tests вокруг stores;
- `src/pulsar_ai/ui/experiment_store.py`
- `src/pulsar_ai/prompts/store.py`.

### Work

1. Добавить tests на concurrent updates.
2. Добавить tests на recovery после restart-like сценария.
3. Проверить, нет ли потерянных обновлений.

### Verification

- прогон новых тестов;
- при возможности прогон смежных store tests.

### Done When

- есть тесты, которые ловят гонки и regressions в persistence.

### Start Prompt

```md
Read `AGENTS.md` and `docs/MULTI_AGENT_OPERATING_MODEL.md`.

Implement Packet 04 from `docs/TASK_PACKETS.md`. Focus only on tests and narrow fixes needed to validate the new persistence layer under concurrent update and restart-like scenarios.
```

## Packet 05. Durable Jobs And Sessions

### Owner

Claude Code

### Goal

Сделать jobs, sessions и run state переживающими рестарт процесса.

### Files to inspect first

- `src/pulsar_ai/ui/jobs.py`
- `src/pulsar_ai/ui/assistant.py`
- `src/pulsar_ai/ui/routes/site_chat.py`
- `src/pulsar_ai/ui/routes/pipeline_run.py`
- `src/pulsar_ai/tracking.py`.

### Work

1. Вынести job/session state в durable store.
2. Добавить reconciliation logic для stale runs.
3. Ввести cleanup policy для старых сессий.

### Verification

- tests на restart-safe behavior;
- smoke check на восстановление или перевод в terminal state.

### Done When

- состояние не теряется просто из-за рестарта процесса;
- stale runs можно reconcile-ить предсказуемо.

### Start Prompt

```md
Read the repository instructions and implement Packet 05 from `docs/TASK_PACKETS.md`. Make jobs, sessions, and run state durable and restart-safe, with reconciliation for stale state.
```

## Packet 06. Secret Handling Hardening

### Owner

Claude Code

### Goal

Убрать самые опасные демо-упрощения вокруг ключей и auth flow.

### Files to inspect first

- `src/pulsar_ai/ui/app.py`
- `src/pulsar_ai/ui/auth.py`
- `ui/src/api/client.ts`
- `tests/test_auth.py`
- `tests/test_security.py`.

### Work

1. Удалить key bootstrap через query string.
2. Убрать plaintext secrets из логов.
3. При необходимости скорректировать client/server auth bootstrap.
4. Обновить security tests.

### Verification

- auth/security tests;
- narrow smoke test для key flow.

### Done When

- ключи не светятся в URL и логах;
- security behavior явно проверен тестами.

### Start Prompt

```md
Read the repository instructions and implement Packet 06 from `docs/TASK_PACKETS.md`. Remove query-string key bootstrap, stop logging plaintext secrets, and update security tests.
```

## Packet 07. Security Regression Sweep

### Owner

Codex

### Goal

Проверить, не осталось ли в проекте похожих утечек или слабых мест после hardening.

### Files to inspect first

- auth-related backend files;
- `ui/src/api/`;
- security tests;
- logs/bootstrap code paths.

### Work

1. Найти похожие key/token handling patterns.
2. Проверить localStorage, URL params, debug logs, exception paths.
3. Либо внести узкие fixes, либо дать review summary с приоритетами.

### Verification

- targeted grep/search;
- relevant tests if code changes are made.

### Done When

- найденные security хвосты либо закрыты, либо документированы с приоритетом.

### Start Prompt

```md
Read `AGENTS.md`, `docs/CLAUDE_CODE_ROADMAP.md`, and `docs/MULTI_AGENT_OPERATING_MODEL.md`.

Execute Packet 07 from `docs/TASK_PACKETS.md`. Perform a focused security regression sweep and either fix narrow issues or produce a concise prioritized review.
```

## Packet 08. Unified Pipeline Execution

### Owner

Claude Code

### Goal

Свести sync и websocket pipeline execution к одному движку.

### Files to inspect first

- `src/pulsar_ai/pipeline/executor.py`
- `src/pulsar_ai/ui/routes/pipeline_run.py`
- `tests/test_pipeline_executor.py`.

### Work

1. Вынести общую execution logic в единый path.
2. Перевести websocket route на тот же engine.
3. Унифицировать статусы и ошибки.

### Verification

- tests around executor;
- smoke path для sync и websocket behavior.

### Done When

- нет дублирующей step-loop логики в route handler;
- оба режима дают одинаковые terminal states.

### Start Prompt

```md
Read the repository instructions and implement Packet 08 from `docs/TASK_PACKETS.md`. Unify sync and websocket pipeline execution behind one engine path and update the relevant tests.
```

## Packet 09. Remote Compute Hardening

### Owner

Claude Code

### Goal

Усилить надежность и наблюдаемость remote compute.

### Files to inspect first

- `src/pulsar_ai/compute/ssh.py`
- `src/pulsar_ai/compute/remote_runner.py`
- `src/pulsar_ai/ui/routes/compute.py`
- `tests/test_compute.py`.

### Work

1. Улучшить command building и shell safety.
2. Нормализовать exit-code capture, stderr и timeout reason.
3. Добавить heartbeat или аналогичную наблюдаемость.
4. Обновить tests.

### Verification

- compute tests;
- narrow smoke scenarios for failure handling.

### Done When

- remote failures диагностируются явно;
- terminal state у remote runs предсказуем.

### Start Prompt

```md
Read the repository instructions and implement Packet 09 from `docs/TASK_PACKETS.md`. Harden remote compute around command safety, lifecycle handling, exit-state capture, and observability.
```

## Packet 10. Experiments Page Decomposition

### Owner

Claude Code

### Goal

Разрезать `Experiments.tsx` на более поддерживаемые части без изменения пользовательского поведения.

### Files to inspect first

- `ui/src/pages/Experiments.tsx`
- смежные hooks/components;
- `ui/src/App.tsx`.

### Work

1. Выделить крупные UI blocks в отдельные components.
2. Упростить container/page logic.
3. Не делать большой redesign.
4. Сохранить совместимость поведения.

### Verification

- frontend build;
- smoke test ключевых экранов.

### Done When

- основной файл страницы заметно меньше и понятнее;
- сборка проходит.

### Start Prompt

```md
Read the repository instructions and implement Packet 10 from `docs/TASK_PACKETS.md`. Decompose `ui/src/pages/Experiments.tsx` into smaller maintainable pieces without changing user-visible behavior.
```

## Packet 11. Frontend Test Harness

### Owner

Codex

### Goal

Добавить минимальный frontend test stack для ключевых сценариев.

### Files to inspect first

- `ui/package.json`
- `ui/src/`
- существующие frontend scripts.

### Work

1. Добавить Vitest и React Testing Library или совместимый stack.
2. Настроить базовый test command.
3. Добавить 2-3 smoke tests на ключевые UI flows.

### Verification

- frontend test run;
- frontend build.

### Done When

- в UI есть работающий test command;
- есть хотя бы минимальное покрытие ключевых сценариев.

### Start Prompt

```md
Read `AGENTS.md` and `docs/MULTI_AGENT_OPERATING_MODEL.md`.

Implement Packet 11 from `docs/TASK_PACKETS.md`. Add a minimal frontend test harness and a few high-signal smoke tests without expanding scope into unrelated UI refactors.
```

## Packet 12. Release Readiness Audit

### Owner

Codex

### Goal

Периодически проверять проект на блокеры выхода на рынок и расхождения с roadmap.

### Files to inspect first

- `AGENTS.md`
- `docs/CLAUDE_CODE_ROADMAP.md`
- `docs/MULTI_AGENT_OPERATING_MODEL.md`
- актуальные changed files.

### Work

1. Сопоставить текущее состояние репозитория с roadmap.
2. Найти blockers в reliability, security, test signal, remote compute и UX maintainability.
3. Выдать короткий prioritized report.
4. При наличии очевидного узкого fix можно сделать его в отдельной ветке.

### Verification

- repository scan;
- targeted tests only if code changes are made.

### Done When

- есть краткий, приоритизированный список market-readiness blockers и один следующий лучший шаг.

### Start Prompt

```md
Read `AGENTS.md`, `docs/CLAUDE_CODE_ROADMAP.md`, `docs/CLAUDE_CODE_EXECUTION_PROMPT.md`, and `docs/MULTI_AGENT_OPERATING_MODEL.md`.

Execute Packet 12 from `docs/TASK_PACKETS.md`. Audit the repository for market-readiness blockers, roadmap drift, missing tests, reliability gaps, and security risks. Produce a concise prioritized report and recommend the next best task.
```

## Рекомендуемая последовательность запуска

1. Packet 01
2. Packet 02
3. Packet 03
4. Packet 04
5. Packet 05
6. Packet 06
7. Packet 07
8. Packet 08
9. Packet 09
10. Packet 10
11. Packet 11
12. Packet 12

## Минимальная ежедневная схема

Утром:

- запускай Claude Code на следующий packet разработки;
- запускай Codex на review или audit packet.

Вечером:

- фиксируй, какой packet завершен;
- обновляй roadmap только по реальным новым фактам;
- ставь следующий packet в очередь.
