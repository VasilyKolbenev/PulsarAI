# План на 14 марта 2026 — Pulsar AI: День 1 реализации

## Приоритет дня: Chunk 1 (Brand) — полный ребрендинг

### Сессия 1: env.py + rename пакета (~1.5 часа)

**Task 1: env.py helper** (15 мин)
- [ ] Написать тест `tests/test_env.py` (5 тестов включая reset _warned)
- [ ] Реализовать `src/pulsar_ai/env.py` (get_env с PULSAR_ fallback)
- [ ] Прогнать тесты, коммит

**Task 2: Rename Python package** (45 мин)
- [ ] `git mv src/pulsar_ai src/pulsar_ai`
- [ ] Bulk rename imports в ~111 .py файлах (`from pulsar_ai` → `from pulsar_ai`)
- [ ] Обновить `pyproject.toml` (name, packages, entry points, license)
- [ ] Обновить `storage/database.py` — DEFAULT_DB_PATH → `pulsar.db`
- [ ] Обновить `storage/schema.py` — project DEFAULT → `pulsar-ai`
- [ ] Обновить `ui/auth.py` — key prefix `forge_` → `pulsar_`
- [ ] `pip install -e ".[dev]"` + проверка импортов
- [ ] Прогнать тесты, коммит

### Сессия 2: Frontend + Docker/Docs rename (~1 час)

**Task 3: Rename frontend** (20 мин)
- [ ] `ui/package.json` — name → `pulsar-ai-ui`
- [ ] `ui/src/api/client.ts` — удалить `bootstrapApiKeyFromUrl()`, rename localStorage keys
- [ ] `ui/vite.config.ts` — outDir → `src/pulsar_ai/ui/static`
- [ ] `npm run build`, коммит

**Task 4: Rename Docker/scripts/docs/configs** (30 мин)
- [ ] `Dockerfile` — paths, labels, env vars, CMD
- [ ] `docker-compose.yml` — service name, volumes, env vars
- [ ] Все `.env*` файлы — PULSAR_* → PULSAR_*
- [ ] `scripts/*.py`, `scripts/*.ps1` — env vars + imports
- [ ] `docs/*.md` (~47 файлов) — все упоминания forge/pulsar-ai
- [ ] `configs/*.yaml` — все ссылки
- [ ] `site_chat.py` — system prompt ("Pulsar AI" → "Pulsar AI", "MIT" → "Apache 2.0")
- [ ] Создать Apache 2.0 LICENSE файл
- [ ] AGENTS.md, PRESENTATION.md, README.md — все ссылки
- [ ] Коммит

### Сессия 3: Landing page + README (~1.5 часа)

**Task 5: Landing page** (60 мин)
- [ ] Создать `ui/src/pages/Landing.tsx` с 6 секциями из спеки
- [ ] Обновить `App.tsx` — Landing на `/`, Dashboard на `/dashboard`, lazy loading
- [ ] Обновить Sidebar — Dashboard link → `/dashboard`
- [ ] `npm run build`, коммит

**Task 6: README** (30 мин)
- [ ] Полный rewrite README.md — Pulsar AI branding, badges, quick start, comparison table
- [ ] Коммит

### Если останется время: начать Chunk 2 (Core)

**Task 7: New SQLite tables** (30 мин)
- [ ] Написать тест `tests/test_schema_new_tables.py`
- [ ] Добавить 5 таблиц в BOOTSTRAP_SQL (api_keys, compute_targets, jobs, assistant_sessions, api_key_events)
- [ ] Bump SCHEMA_VERSION = 2
- [ ] Коммит

---

## Полный оставшийся бэклог (26 задач)

### Chunk 1: Brand (Tasks 1-6) — День 1
- [x] Task 1: env.py helper
- [x] Task 2: Rename Python package
- [x] Task 3: Rename frontend
- [x] Task 4: Rename Docker/docs/scripts
- [x] Task 5: Landing page
- [x] Task 6: README rewrite

### Chunk 2: Core (Tasks 7-13d) — Дни 2-4
- [ ] Task 7: New SQLite tables (schema.py)
- [ ] Task 8: WorkflowStore → SQLite
- [ ] Task 9: PromptStore → SQLite
- [ ] Task 10: ApiKeyStore → SQLite + migration
- [ ] Task 11: ComputeManager → SQLite + migration
- [ ] Task 12: JobRegistry (durable jobs)
- [ ] Task 13: Pipeline callback (unified execution)
- [ ] Task 13b: Session persistence (assistant + site_chat)
- [ ] Task 13c: Security hardening (audit trail, demo mode)
- [ ] Task 13d: Remote compute hardening (shlex, retry)

### Chunk 3: UI (Tasks 14-16d) — Дни 3-5
- [x] Task 14: Toast notification system
- [x] Task 15: Empty states
- [x] Task 16: Dashboard upgrade (metrics, activity feed)
- [x] Task 16b: Design system components (Card, Badge, MetricCard, StatusDot)
- [x] Task 16c: Page decomposition (Experiments, PromptLab)
- [x] Task 16d: UX improvements (Breadcrumbs, Skeletons)

### Chunk 4: Quality (Tasks 17-20) — Дни 5-6
- [x] Task 17: Test infrastructure (conftest.py, pytest config)
- [x] Task 18: Docker verification
- [x] Task 19: GitHub Actions CI (lint + test + build + docker)
- [x] Task 20: DX files (Makefile, .env.example, CONTRIBUTING.md)

---

## Ключевые файлы для rename (справочник)

| Категория | Кол-во файлов | Что менять |
|-----------|--------------|------------|
| Python imports | ~111 | `from pulsar_ai` → `from pulsar_ai` |
| TypeScript | ~11 | localStorage keys, UI text |
| Markdown docs | ~47 | forge/pulsar-ai/Pulsar AI → pulsar/pulsar-ai/Pulsar AI |
| Scripts | 5+ | env vars + imports |
| Configs (YAML) | 10+ | ссылки на pulsar-ai |
| Docker | 2 | paths, labels, env vars, CMD |
| Env files | 4 | PULSAR_* → PULSAR_* |
| vite.config.ts | 1 | outDir path |
| pyproject.toml | 1 | name, packages, entry points, deps, license |

## Риски и митигация

- **Сломанные импорты после rename**: сразу прогнать `python -m pytest tests/ -x --timeout=30`
- **Frontend build fails**: сразу проверить `npm run build` после каждого изменения
- **Пропущенные hardcoded strings**: использовать `grep -r "forge" --include="*.py"` после rename
