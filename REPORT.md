# CallLens — аналитический отчёт (аудит + план усиления)

> Дата: 2026-11-19. Ревизия: `9af78c9` (main), ветка работы: `feat/psychotype-and-integrations`.
> Отчёт подготовлен AI-агентом в среде Qoder с полным доступом к ФС: этапы клонирования, анализа,
> портирования навыков и правок выполнены напрямую в репозитории.
> Все ссылки вида `файл:строки` даны на состояние main до правок, если не указано иное.

---

## 1. Краткое резюме (executive summary)

1. **CallLens** — русскоязычный MVP для evidence-based разбора sales-звонков: аудио → Whisper-транскрипт с тайм-кодами → два LLM-вызова (scoring по чек-листу + профиль/коучинг) → JSON и Markdown-отчёт (`backend.py:70–92`).
2. Сильная сторона — **принцип доказательности**: каждый балл, стиль клиента и шаг LAER требует точной цитаты с тайм-кодом; промпт запрещает клинические выводы и выдуманные цитаты (`prompt.md`, правила 2, 13).
3. Уже реализованы: два скоринга (evidence-based/strict), 4 коммуникационных стиля (русский маппинг DISC, `backend.py:18–27`), карта возражений + LAER, coaching-приоритеты, follow-up, markdown/PDF-экспорт, командный dashboard, multi-tenant auth c magic-link, RBAC и RLS (`auth_routes.py`, `auth_db.py:25–29`).
4. Главные ограничения: **vendor lock-in на OpenAI** (`backend.py:29–32`), отсутствие диаризации (все реплики — `Speaker 1`, `backend.py:56`), результаты анализа не хранятся на сервере (только в сеансе браузера), чек-листы — в `localStorage` (`app.js:65`), CRM-интеграций нет (осознанное решение MVP, `README.md:18`).
5. В рамках этой сессии добавлено обратно совместимое поле API **`personality_profile`** (DISC 0–100 + Big Five OCEAN + evidence-цитаты), обновлён системный промпт (`prompt.md`, правило 6a), добавлен опциональный чек-лист-блок «Психотип клиента», написаны тесты (7 новых, все зелёные) и обновлён README.
6. Для Qoder портированы: `AGENTS.md`, 4 модульных правила `.qoder/rules/`, 3 skill'а `.qoder/skills/` (DISC, Big Five, LAER) и под-агент `.qoder/agents/psychotype-auditor.md` — всё на открытых методологиях, без копирования проприетарных текстов.
7. Потенциал: при добавлении серверного хранилища отчётов, диаризации (WhisperX/pyannote) и CRM-публикации сервис переходит из MVP в полноценную speech-analytics платформу для РОП.

---

## 2. Что представляет собой сервис

### 2.1 Назначение и аудитория

Сервис превращает запись sales-звонка в доказательный отчёт для руководителя отдела продаж (РОП) и менеджера (`calllens-project-handoff.md:40–58`, 1213 строк — подробный handoff). Целевая аудитория: B2B-отделы продаж, РОПы, sales-коучи; язык интерфейса и отчётов — русский.

### 2.2 Архитектура и поток данных

```
Браузер (index.html/app.js)
  │  POST /api/analyze (multipart: audio + checklist JSON + meta)
  ▼
FastAPI backend.py
  ├─ валидация формата (8 расширений, backend.py:16) и размера ≤250 МБ (backend.py:215)
  ├─ чанкование ffmpeg >25 МБ → сегменты по 900 c (backend.py:40–44)
  ├─ OpenAI Whisper API, verbose_json + segment timestamps → "[MM:SS–MM:SS] Speaker 1: …" (backend.py:46–58)
  ├─ LLM-вызов 1: scoring по чек-листу (gpt-5-nano, temperature=0, json_object, backend.py:60–74)
  ├─ LLM-вызов 2: профиль/возражения/коучинг (backend.py:78–80)
  ├─ normalize(): дефолты, русский маппинг стилей, LAER, markdown (backend.py:94–154)
  ▼
JSON-отчёт + markdown → рендер в UI (app.js:94–115), экспорт .md/PDF/clipboard (app.js:116–118)
```

Слои авторизации (Module 1): magic-link без пароля, HttpOnly-cookie, таблицы `tenants/users/magic_link_tokens/sessions` (`auth_models.py`), RBAC `owner/rop/manager/analyst` (`auth_routes.py:25`), tenant isolation через явные фильтры (SQLite) и PostgreSQL RLS (`auth_db.py:25–29`), Alembic-миграции (`alembic/`), rate limit 5 запросов/мин на request-link (`auth_routes.py:77–83`).

### 2.3 Ключевые эндпоинты

| Эндпоинт | Назначение | Код |
|---|---|---|
| `GET /api/health` | статус, режим demo/ai, `ai_configured` (boolean, без раскрытия ключа) | `backend.py:191–196` |
| `POST /api/analyze` | аудио + чек-лист → полный JSON-отчёт | `backend.py:202–218` |
| `POST /api/auth/request-link`, `GET /api/auth/verify`, `POST /api/auth/logout`, `GET /api/auth/me` | magic-link-авторизация | `auth_routes.py:120–175` |
| `POST /api/tenants/{id}/invite`, `GET /api/users`, `PATCH /api/users/{id}` | управление пользователями (RBAC) | `auth_routes.py:178–229` |
| `GET /`, `GET /{asset}` | статика (index/app/dashboard/login) | `backend.py:189–200` |

### 2.4 Схема данных отчёта (контракт `prompt.md:29–63`)

`score` (criteria + earned/max/observable_max + `evidence_percent`/`strict_percent`), `omissions` (not_observed/partial), `client_communication_profile` (4 стиля + confidence + evidence/counter_evidence + manager_playbook + manager_adaptation), `objections[]` (категория, severity, статус, LAER-флаги), `one_call_coaching[]` (≤3), `follow_up`, `team_insights`, `role_warning`, `markdown`. **Новое (эта ветка):** `personality_profile` — см. раздел 7.

### 2.5 Как реализованы ключевые механизмы

- **Транскрибация**: Whisper API с сегментными тайм-кодами; чанки по 15 мин; диаризации нет — один `Speaker 1`, роли определяет LLM с `role_warning=true` при недостатке доказательств (`backend.py:46–58`, `README.md:136–138`).
- **Скоринг**: два знаменателя — evidence-based (исключает «не наблюдалось») и strict (все критерии), формулы в `prompt.md:9` и `backend.py:83–90`; жёсткая сверка числа критериев с чек-листом, иначе 502 (`backend.py:75–77`).
- **Доказательства**: каждый критерий требует `quote`+`timestamp`+`reason`; промпт запрещает выдумывать цитаты (`prompt.md:8`).
- **Профиль клиента**: 4 русскоязычных стиля = практический маппинг DISC (`prompt.md:11–15`, `backend.py:18–27`), смешанный профиль, ≥3 цитаты, контрдоводы, confidence<0.55 ⇒ гипотеза.
- **LAER**: 7 категорий возражений, 5 шагов (listen/acknowledge/explore/respond/confirm), общий питч не засчитывается как ответ (`prompt.md:19–20`, нормализация `backend.py:110–119`).
- **Coaching**: ≤3 приоритета с replacement_phrase/cue/success_signal + follow-up (`prompt.md:21`).
- **Экспорт**: markdown из API, PDF через print-стили браузера (`app.js:116–118`).
- **Dashboard**: статическая страница с демо-данными и импортом JSON/CSV (`dashboard.js`), KPI/матрица адаптации по стилям/повторяющиеся провалы.

### 2.6 Секреты и данные

Секреты — только env (`.env.example`); наличие ключа наружу — boolean `ai_configured` (`backend.py:196`). Аудио/транскрипт уходят только в выбранный OpenAI API, на серверах CallLens не хранятся (`README.md:44`). Чек-листы — `localStorage` браузера (`app.js:65`). Результаты анализа — только в текущем сеансе, серверной персистентности нет. `CALLLENS_DEMO_MODE=1` — детерминированный fixture без API-вызовов (`backend.py:156–187`).

---

## 3. Преимущества

| Преимущество | Детали | Почему это ценно |
|---|---|---|
| Evidence-based скоринг | Каждый балл = цитата + тайм-код + reason; два балла (evidence/strict) с честным знаменателем (`prompt.md:8–9`, `backend.py:83–90`) | Снимает споры «оценка несправедлива»; РОП видит факты, а не впечатление |
| Жёсткий JSON-контракт + нормализация | `normalize()` проставляет дефолты на любое неполное поведение LLM (`backend.py:94–126`); сверка числа критериев → 502 вместо битого отчёта (`backend.py:75–77`) | UI никогда не падает на частичном ответе провайдера |
| Честность ограничений | `role_warning`, provisional-баллы, дисклеймер «профиль — гипотеза, не диагноз» (`README.md:134–139`, `prompt.md:13`) | Юридически и этически безопасная подача психотипирования |
| Приватность по дизайну | Аудио не задерживается на сервере (tempdir, `backend.py:212`), ключ только в env, health-check не раскрывает секреты | Соответствует ожиданиям B2B-клиентов о данных звонков |
| Multi-tenant фундамент | Magic-link, HttpOnly-cookie, RBAC 4 ролей, RLS для PostgreSQL, Alembic, тесты изоляции тенантов (`auth_routes.py`, `tests/test_auth.py:139–147`) | Готовый каркас для SaaS-монетизации |
| Практичный coaching-слой | LAER по шагам, replacement-фразы, триггеры и сигналы успеха, follow-up на следующий звонок (`prompt.md:19–22`) | Меняет поведение менеджера, а не только ставит оценку |
| Демо-режим и smoke-сценарии | `CALLLENS_DEMO_MODE=1` (`backend.py:209–211`), Playwright-скрипты (`smoke_test.py`, `mvp_flow_smoke.py`) | Можно проверять весь UI-путь без API-кредитов |
| Отличная документация | `calllens-project-handoff.md` (1213 строк), stage-отчёты, README с честными предупреждениями | Низкий порог входа для новых разработчиков/агентов |

## 4. Минусы и риски

| Минус | Детали | Риск/последствие |
|---|---|---|
| Vendor lock-in на OpenAI | `client()` хардкодит `OpenAI` (`backend.py:29–32`); README советует «замените две функции» (`README.md:44`) | Смена провайдера = правка кода; нет fallback при outage/лимитах |
| Нет диаризации | Все реплики — `Speaker 1` (`backend.py:56`); роли угадывает LLM | Систематический риск misattribution: баллы менеджера могут считаться по репликам клиента |
| Результаты не персистируются | Отчёт живёт только в сеансе браузера; dashboard заполняется ручным импортом JSON/CSV (`dashboard.js`, `README.md:61`) | Нет истории звонков, `team_insights` с sample_size>1 недостижимы без ручного труда |
| Чек-листы в localStorage | `app.js:65,119` | Нет командного шаринга и версионирования; потеря при очистке браузера |
| Синхронный долгий запрос | `/api/analyze` держит HTTP-соединение на всё время Whisper+2×LLM (минуты для 50-мин звонка) | Таймауты прокси/браузера, нет ретраев, нет прогресса |
| Rate limit только в памяти процесса | `RATE_BUCKETS` — dict в памяти (`auth_routes.py:24`), и только для request-link | В многопроцессном деплое лимит не работает; `/api/analyze` вообще без лимита — риск расхода кредитов |
| Плотный стиль backend.py | Однострочники, несколько ответственностей в одном файле (218 строк до правок) | Риск регрессий при росте; сложно ревьюить |
| Корневой `pytest` падает на smoke-скриптах | `smoke_test.py` собирается pytest, требует playwright+chromium (`smoke_test.py:2`), которого нет в requirements.txt | CI-ловушка: «pytest» без аргументов ≠ зелёный; нужен `pytest tests/` |
| Пустой `.github/` | Только `.keep` — нет CI | Регрессии могут уезжать в main |
| Моно-транскрипт без уверенности ASR | Нет confidence от Whisper, нет обработки неразборчивых мест, кроме role_warning | Тихие ошибки транскриптации попадают в «доказательства» |
| `gpt-5-nano` по умолчанию для анализа | `backend.py:61` | Качество DISC/LAER-выводов ограничено моделью; для продакшена нужен апгрейд по умолчанию |

---

## 5. Чем дополнить и улучшить

### Quick Wins (1–2 недели)

| # | Что сделать | Зачем | Сложность | Файлы |
|---|---|---|---|---|
| Q1 | ✅ **Выполнено в этой ветке**: поле `personality_profile` (DISC+Big Five+evidence) | Углубляет психотипирование, сохраняет обратную совместимость | M | `backend.py`, `prompt.md`, `app.js`, `tests/` |
| Q2 | ✅ **Выполнено**: чек-лист-блок «Психотип клиента» | РОП может оценивать, работает ли менеджер с психотипом | S | `index.html`, `app.js` |
| Q3 | Серверное хранение чек-листов с версионированием (таблица `checklists` + CRUD под RBAC) | Шаринг внутри команды, аудит изменений | M | `auth_models.py`, `auth_routes.py`, `alembic/`, `app.js` |
| Q4 | Webhook-уведомление о завершении анализа (`CALLLENS_WEBHOOK_URL`, httpx POST, retries, секрет в env) | Интеграция с Telegram/Slack без CRM | S | `backend.py`, `.env.example` |
| Q5 | CI в GitHub Actions: `pytest tests/` + линтер | Защита от регрессий | S | `.github/workflows/` |
| Q6 | `testpaths = tests` в `pytest.ini` (или guard в smoke-скриптах) | Корневой `pytest` становится зелёным без playwright | S | `pytest.ini` |
| Q7 | Rate limit на `/api/analyze` (тот же bucket-подход) | Защита кредитов OpenAI от abuse | S | `backend.py`, `auth_routes.py` |
| Q8 | Возвращать `duration`/`model`/версию промпта в `meta` отчёта | Воспроизводимость и отладка результатов | S | `backend.py` |

### Среднесрочные (1–2 месяца)

| # | Что сделать | Зачем | Сложность | Файлы |
|---|---|---|---|---|
| M1 | Абстракция LLM/ASR-провайдера (интерфейс `transcribe()`/`ask_llm()`; env-выбор OpenAI/Anthropic/local faster-whisper) | Снять vendor lock-in, снизить стоимость | M | `backend.py` → пакет `providers/` |
| M2 | Диаризация: WhisperX + pyannote на отдельном worker | Убрать главный источник ошибок (роли) | L | новый worker, `backend.py:46–58` |
| M3 | Асинхронные job'ы: POST → task_id, GET /api/tasks/{id}, хранение отчётов в БД | Убрать таймауты, дать историю звонков | L | `backend.py`, `auth_models.py`, `alembic/`, `app.js` |
| M4 | Dashboard на реальных данных из БД вместо ручного импорта | Автоматические командные тренды, team_insights sample_size>1 | M | `dashboard.js`, новые эндпоинты |
| M5 | CRM-публикация (Bitrix24/amoCRM REST) как явное действие пользователя | Закрытие возражения «ручной перенос» | L | новый модуль `crm_*.py` |
| M6 | Observability: structlog, метрики длительности этапов, Sentry | Эксплуатация в production | M | все модули |

### Долгосрочные (квартал+)

| # | Что сделать | Зачем | Сложность |
|---|---|---|---|
| L1 | Лонгитюдные профили: динамика менеджера и клиента по серии звонков (психотип клиента как устойчивая гипотеза с пересчетом confidence по N звонкам) | Превращает разовый отчёт в систему развития | L |
| L2 | Акустический слой: темп речи, перебивания, тон, паузы (не только текст) | Маркеры DISC/E сильно акустические; повысит точность психотипа | L |
| L3 | Self-hosted ASR (faster-whisper + GPU) | Стоимость, приватность, независимость | L |
| L4 | Мультиязычность транскриптов и отчётов | Выход за RU-рынок | M |
| L5 | A/B-валидация психотипических выводов: сравнение с разметкой экспертов, калибровка confidence | Доказательная база самого продукта | L |

---

## 6. Навыки и методологии для анализа психотипа в продажах

### 6.1 Методологии

| Методология | Источник/статус | Лицензия | Что даёт | Адаптация под Qoder/CallLens | Приоритет |
|---|---|---|---|---|---|
| **DISC** | Marston 1928; открытые описания (Wikipedia «DISC assessment») | идея — public domain; тексты Wikipedia — CC BY-SA; опросники TTI/Crystal — проприетарные | 4 наблюдаемых фактора поведения; уже частично есть в CallLens (4 стиля = D/C/I/S, `prompt.md:11–15`) | ✅ Портировано: `.qoder/rules/psychotype-disc.md` + `.qoder/skills/psychotype-disc/SKILL.md` + поле `disc_profile` в API | **Высокий — внедрено** |
| **Big Five / OCEAN** | Costa & McCrae; Wikipedia «Big Five personality traits»; IPIP-маркеры | академические описания открыты; IPIP — public domain | Научно обоснованная 5-факторная модель; речевые маркеры (лингвистические корреляты хорошо изучены) | ✅ Портировано: `.qoder/rules/psychotype-big-five.md` + skill + `big_five_scores` в API | **Высокий — внедрено** |
| **LAER** (Listen-Acknowledge-Explore-Respond) | Общедоступная sales-методология; уже используется в CallLens (`prompt.md:20`) | открытая | Оценка качества обработки возражений | ✅ Портировано как skill/rule `.qoder/rules/sales-objections-laer.md` | **Высокий — внедрено** |
| **MBTI** | Myers-Briggs Foundation | проприетарная; научная валидность критикуется | 16 типов личности | ❌ Не адаптировать в runtime: закрытая лицензия + низкая валидность; допустимо только упоминание в docs | Низкий |
| **Enneagram** | Открытые описания 9 типов, но коммерческие тесты закрыты | смешанная | Мотивационные типы | ❌ Не адаптировать: слабая эмпирика для sales-контекста | Низкий |
| **FDNA** (анализ лица) | Проприетарная | закрытая | «Психотип по фото» | ❌ Категорически не использовать: этические/юридические риски (биометрия), неприменимо к аудио | Запрещено |
| **Humantic AI** | Проприетарный SaaS buyer intelligence | закрытая | DISC/OCEAN по email/LinkedIn/звонкам | ⚠️ Только как концептуальный референс (их «buyer intelligence» = наша задача); тексты/шкалы не копировать | Контекст |
| **Crystal** | Проприетарный SaaS (DISC-профили по LinkedIn) | закрытая | DISC + коммуникативные советы | ⚠️ Референс формата «profile + do/don't советы» — уже есть в manager_playbook | Контекст |
| **Second Opinion for Sales** | Проприетарная методология/тренинг | закрытая | Sales-психотипирование в переговорах | ⚠️ Только идейный контекст | Низкий |
| **EQALL** | Проприетарная оценка EQ | закрытая | Emotional intelligence скоринг | ⚠️ Контекст; открытые аналоги — модели Mayer-Salovey-Caruso (описания) | Низкий |

### 6.2 Существующие открытые Skills-наборы

| Навык/репозиторий | Источник | Лицензия | Что даёт | Способ адаптации под Qoder | Приоритет |
|---|---|---|---|---|---|
| **louisblythe/Sales-Skills** | github.com/louisblythe/Sales-Skills — 122 B2B-sales skill'а (discovery, objection handling, negotiation), формат SKILL.md c YAML front matter (name, description) | **MIT** («Use these however you want») | Готовые структуры sales-playbook skill'ов для агентов | Использован как референс формата; содержимое переписано своими словами в `.qoder/skills/` (копирование текста не требуется лицензией MIT, но переработка безопаснее и точнее под CallLens) | Высокий (референс) |
| **alirezarezvani/claude-skills** | github.com/alirezarezvani/claude-skills — 410 skills + 824 stdlib-скрипта | проверить перед использованием | Большая библиотека паттернов SKILL.md | Точечный просмотр sales/communication-категорий | Средний |
| **agent-skills / claude-code-skills (GitHub Topics)** | github.com/topics/agent-skills; коллекции 1000+ skills | смешанные | Поиск новых sales/psychology-навыков | Мониторинг при будущих итерациях | Низкий |
| **Manus skill `sales-call-quality-coach`** | Упомянут в `README.md:157`, лежит вне репо (`/home/ubuntu/skills/...`) | недоступен | Исторический предшественник coaching-слоя | Не переносим — файл отсутствует в репозитории; его функции уже в `prompt.md` | — |

### 6.3 MCP-серверы для продаж/CRM

| Сервер | Источник | Что даёт | Статус в CallLens |
|---|---|---|---|
| Bitrix24 MCP (официальный, REST-доки) | github.com/bitrix24/b24restdocs (ai-tools/mcp.md) | Актуальная документация Bitrix24 REST для агента-разработчика | Описан в `.qoder/rules/mcp-crm.md`; подключается вручную при старте CRM-интеграции |
| gunnit/bitrix24-mcp-server | mcpservers.org/servers/gunnit/bitrix24-mcp-server | Операции с CRM Bitrix24 (сделки/контакты) | Кандидат для этапа M5; токен только через env |
| AmoCRM MCP (community) | github.com/topics/amocrm; mcpmarket.com/server/amocrm | 21 tool: leads/contacts/pipelines | Кандидат для этапа M5 |
| Aiyo28/yzel | github.com/Aiyo28/yzel | Мост к 1С/Bitrix24/AmoCRM/Telegram | Альтернатива для RU-стека |
| filesystem / git (reference servers) | официальные MCP | Базовые операции агента | Подключаются в Qoder при необходимости |

> Реальные подключения MCP не выполнялись: runtime CallLens от MCP не зависит, а CRM-токены не предоставлены (см. раздел «Следующие шаги»).

### 6.4 Что установлено/создано в этой сессии (артефакты Qoder)

| Артефакт | Путь | Источник/лицензия |
|---|---|---|
| Инструкции проекта для агентов | `AGENTS.md` | собственный текст; вкл. блок правил психотипирования |
| Правило DISC | `.qoder/rules/psychotype-disc.md` | адаптация открытых описаний DISC (Wikipedia CC BY-SA, Marston PD) |
| Правило Big Five | `.qoder/rules/psychotype-big-five.md` | адаптация открытых описаний Big Five / IPIP (PD) |
| Правило LAER | `.qoder/rules/sales-objections-laer.md` | открытая методология; референс louisblythe/Sales-Skills (MIT) |
| Правило MCP | `.qoder/rules/mcp-crm.md` | собственные заметки + публичные источники MCP-серверов |
| Skill DISC | `.qoder/skills/psychotype-disc/SKILL.md` | CC-BY-SA-4.0 (адаптация), собственный текст |
| Skill Big Five | `.qoder/skills/psychotype-big-five/SKILL.md` | CC-BY-SA-4.0 (адаптация), собственный текст |
| Skill LAER | `.qoder/skills/sales-objections-laer/SKILL.md` | MIT, собственный текст |
| Под-агент аудитор | `.qoder/agents/psychotype-auditor.md` | собственный; tools: Read, Grep, Glob, Bash; model: inherit |

---

## 7. Рекомендуемые правки в CallLens

### 7.1 Выполнено в ветке `feat/psychotype-and-integrations`

1. **API**: новое поле `personality_profile` в ответе `/api/analyze` (`backend.py`, `normalize_personality_profile()`):
   - `communication_style` — дубль текущих 4 стилей (primary/secondary/confidence) для удобства потребителей;
   - `disc_profile` — `d/i/s/c` (0–100), `primary` (D/I/S/C/none, выводится из стиля при отсутствии), `confidence` (0–1);
   - `big_five_scores` — `openness/conscientiousness/extraversion/agreeableness/neuroticism` (0–100), `low_evidence` если сигнал не наблюдался (дефолт 50 — не выдумываем);
   - `evidence.disc[]` и `evidence.big_five[]` — цитаты с тайм-кодами;
   - `provisional` — привязка к `role_warning`.
   Обратная совместимость: старые поля не тронуты; при отсутствии `personality_profile` в ответе LLM normalize() достраивает дефолты.
2. **Системный промпт**: правило 6a в `prompt.md` + расширение insight-промпта в `backend.py` (маркеры DISC и Big Five по речевым паттернам: темп, лексика — цифры/эмоции/статус/гарантии, структура аргументации, реакция на риски). Синхронизировано с `.qoder/rules/psychotype-disc.md` и `psychotype-big-five.md`. Evidence-принцип сохранён: «без цитаты — нет вывода».
3. **UI**: блок «Психотип: DISC и Big Five» в карточке профиля (`app.js:psychotypeBlock()`), кнопка «+ Психотип клиента» в чек-листе (`index.html`, `app.js:PSYCHOTYPE_BLOCK`) — 3 опциональных критерия с дедупликацией.
4. **Markdown-отчёт**: новая секция «Психотип: DISC и Big Five» с шкалами и доказательствами (`backend.py:make_markdown()`).
5. **Тесты**: `tests/test_personality_profile.py` — 7 тестов (дефолты, клампинг, вывод primary из стиля, provisional, markdown, demo-endpoint, demo_result).
6. **Docs**: README — описание поля, чек-лист-блока, раздела «Тесты».

### 7.2 Рекомендовано следующими PR (из раздела 5)

- Q3: серверные чек-листы (модель `Checklist` c `tenant_id`, `version`, CRUD под RBAC) — убирает localStorage-ограничение.
- Q4: webhook `CALLLENS_WEBHOOK_URL` (httpx уже в requirements) — уведомление о завершении анализа.
- Q6: `testpaths = tests` в `pytest.ini` — чинит корневой pytest.
- M1: интерфейс провайдеров вместо хардкода OpenAI в `backend.py:29–32`.
- Дальнейшие поля API: `personality_profile.cross_call_confidence` (после M3 — история звонков), `acoustic_features` (после L2).

---

## 8. Итоговая оценка сервиса

**Сильные стороны**: зрелый для MVP принцип доказательности; продуманная нормализация LLM-ответов; честная документация ограничений; готовый multi-tenant/auth-фундамент с RLS и тестами; практичный coaching-слой (LAER, replacement-фразы, follow-up); приватность данных по дизайну.

**Ограничения**: OpenAI-only; отсутствие диаризации — главный источник ошибок атрибуции; синхронный долгий запрос без job-очереди; отсутствие серверной персистентности отчётов и чек-листов; нет CI; in-memory rate limit; dashboard на ручном импорте.

**Потенциал**: высокий. Каркас (тенанты, RBAC, evidence-based ядро) позволяет за 1–2 квартала превратить MVP в production speech-analytics платформу: jobs+БД (M3) → dashboard на реальных данных (M4) → диаризация (M2) → CRM (M5). Добавленный в этой ветке `personality_profile` (DISC+Big Five с evidence) выводит психотипирование на уровень, сопоставимый с Humantic AI/Crystal по формату вывода, но с открытой проверяемой методологией и цитатами-доказательствами — это дифференциатор против «чёрных ящиков» коммерческих скорингов.

**Оценка: 7.5/10 как MVP** (продуктовая логика и документация — 9, инженерная инфраструктура — 6, готовность к production — 5).

---

### Приложения

- Артефакты Qoder: `AGENTS.md`, `.qoder/rules/*.md` (4), `.qoder/skills/*/SKILL.md` (3), `.qoder/agents/psychotype-auditor.md`.
- Тесты: `.venv/Scripts/python -m pytest tests/ -q` → **17 passed, 1 skipped** (10 auth + 7 personality_profile; skip — PostgreSQL RLS-проверка без `DATABASE_URL_RLS`).
- Источники web-поиска: louisblythe/Sales-Skills (MIT), alirezarezvani/claude-skills, GitHub Topics «agent-skills», bitrix24/b24restdocs MCP, gunnit/bitrix24-mcp-server, AmoCRM MCP (mcpmarket), Aiyo28/yzel.
