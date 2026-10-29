# CallLens — сервис разбора sales-звонков

CallLens MVP — русскоязычный интерфейс и небольшой FastAPI-бэкенд без CRM-интеграций. Пользователь загружает запись звонка и чек-лист, после чего получает:

1. оценку по каждому критерию и два итоговых балла — evidence-based и strict;
2. список пунктов, которые не прозвучали или были выполнены частично;
3. профиль коммуникационного стиля клиента, доказательные цитаты, контрдоводы и playbook менеджера;
4. карту возражений по категориям и проверку обработки по LAER;
5. 1–3 coaching-приоритета на следующий сопоставимый звонок и follow-up условие проверки.

В интерфейсе используются только русские названия стилей: **Результатный стратег**, **Доказательный эксперт**, **Визионер-вдохновитель** и **Надёжный партнёр**. Англоязычные идентификаторы могут встречаться только внутри совместимости с устаревшими ответами модели и не показываются пользователю.

Текущий этап — **MVP без CRM**: нет автоматической публикации в Bitrix24/amoCRM, webhook-сценариев и командной синхронизации. Результат формируется после явного запуска анализа и доступен в текущем сеансе с экспортом в Markdown/PDF.

## Почему выбран вариант B

Бэкенд нужен, потому что браузер сам по себе не должен хранить API-ключ и не может надёжно выполнить транскрибацию больших файлов. `backend.py`:

- принимает аудио;
- если файл больше 25 МБ, режет его на чанки через `ffmpeg`;
- отправляет чанки в OpenAI Whisper API;
- передаёт транскрипт, чек-лист и системный промт в Chat Completions API;
- возвращает JSON и markdown-отчёт.

Аудио и транскрипт не отправляются на сервер разработки CallLens. Они передаются только в OpenAI API, если вы сами выбрали OpenAI и указали свой ключ. Для другого провайдера замените две функции `transcribe()` и `ask_llm()`.

## Быстрый запуск локально

Нужны Python 3.10+, `ffmpeg` и API-ключ OpenAI.

```bash
cd sales-call-quality-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="ваш_ключ"
uvicorn backend:app --reload --port 8000
```

Откройте <http://127.0.0.1:8000>.

Дашборд эффективности команды доступен на <http://127.0.0.1:8000/dashboard.html>. Он стартует с явно помеченными демо-данными и умеет импортировать массив JSON или CSV с полями `date,manager,style,evidence,strict,adaptation,next,focus,gaps`.

Можно использовать `.env` через shell или менеджер секретов. Не вставляйте ключ в `app.js`, `index.html` или GitHub. Ключ нужен только бэкенду.

Health-check доступен по `GET /api/health` и возвращает `{ "status": "ok", "service": "calllens-mvp", "crm": false }`.

Шаблон конфигурации находится в `.env.example`. Рабочий AI-режим использует `OPENAI_API_KEY`; интерфейс показывает состояние `AI готов` или `Нужен API-ключ` через health-check и не раскрывает секреты. Наличие ключа проверяется только как boolean-флаг.

Для длинных звонков backend разделяет AI-анализ на два вызова: отдельный scoring по критериям и отдельный профиль/коучинг. По умолчанию используется доступная экономичная модель `gpt-5-nano` с low reasoning; транскрибация сохраняет сегментные тайм-коды. Если кредитов провайдера недостаточно, endpoint возвращает понятную ошибку, а не повреждённый отчёт.

Для проверки полного пользовательского пути без расходования API-кредита можно временно запустить backend с `CALLLENS_DEMO_MODE=1`. Этот режим принимает файл, проходит тот же endpoint `/api/analyze` и возвращает явно помеченный fixture-отчёт; он не транскрибирует запись и не предназначен для рабочих оценок.

## Как получить ключ

1. Откройте страницу API Keys в аккаунте выбранного AI-провайдера.
2. Создайте отдельный ключ с минимально нужными правами.
3. Передайте его в `OPENAI_API_KEY`.
4. После теста отзовите ключ или замените его.

Модели можно переопределить:

```bash
export OPENAI_TRANSCRIBE_MODEL=whisper-1
export OPENAI_ANALYSIS_MODEL=gpt-4o-mini
```

## Чек-лист

Можно загрузить `.md`, `.txt` или `.csv`. Поддерживаются строки:

```text
Установил цель звонка,10
Выявил потребность,20
Отработал возражения,20
```

Также пункты можно добавить вручную. Они сохраняются в `localStorage` текущего браузера.

## Запуск без API-запроса

Для локального просмотра интерфейса можно запустить простой сервер:

```bash
python3 -m http.server 8080
```

Но анализ при этом работать не будет — endpoint `/api/analyze` предоставляет FastAPI-бэкенд.

Поддерживаемые записи: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.mp4`, `.webm`, `.mpeg`, `.mpga`. Ограничение MVP — 250 МБ на файл. Проверка формата и размера выполняется и в браузере, и на backend.

## Деплой

### Render

1. Создайте новый Web Service из этой папки или репозитория.
2. Build command: `pip install -r requirements.txt`.
3. Start command: `uvicorn backend:app --host 0.0.0.0 --port $PORT`.
4. Добавьте `OPENAI_API_KEY` в Environment Variables.

### Railway / Fly.io / VPS

Используйте тот же start command и задайте `OPENAI_API_KEY` в secrets. `ffmpeg` должен быть установлен на сервере.

### GitHub Pages / Netlify

Только статическая часть (`index.html`, `app.js`, `styles.css`) будет отображаться, но для реального анализа укажите публичный URL бэкенда в `app.js`, заменив `fetch('/api/analyze'...)` на `fetch('https://ваш-api.example/api/analyze'...)`. Для production добавьте CORS только для своего домена.

## Экспорт

- **Скачать .md** — сохраняет полный markdown-отчёт, который вернул API.
- **Скачать PDF** — открывает системную печать браузера с print-стилями; выберите «Сохранить как PDF».
- **Скопировать** — копирует markdown в буфер обмена.

## Ограничения и честные предупреждения

- OpenAI Whisper не делает полноценную диаризацию сам. В этой минимальной версии транскрипт маркируется как `Speaker 1`, а роль менеджера/клиента определяется LLM с `role_warning=true`, если доказательств недостаточно.
- Для production-диаризации добавьте WhisperX + pyannote на отдельный worker или внешний diarization provider. UI уже умеет показать предупреждение.
- Если аудиозапись монофоническая или неразборчивая, менеджерские баллы могут быть provisional.
- Профиль клиента — рабочая гипотеза наблюдаемого коммуникационного паттерна, а не диагноз или неизменная характеристика человека.

## Визуальная система

Интерфейс использует атомарную структуру компонентов, 8-point spacing rhythm, высокий контраст, зелёный accent для действий и нейтральные статусы. Сравнения score оформлены как горизонтальные progress bars: они начинаются с нуля, подписаны числовыми значениями и сопровождаются таблицей, поэтому информация не зависит только от цвета.

## Файлы

- `index.html` — структура интерфейса.
- `styles.css` — дизайн-система и print-layout.
- `app.js` — загрузка, localStorage-чеклист, progress UI, рендер отчёта и экспорт.
- `dashboard.html`, `dashboard.css`, `dashboard.js` — аналитика команды: KPI, сравнение менеджеров, матрица адаптации по стилям, повторяющиеся провалы и импорт JSON/CSV.
- `backend.py` — FastAPI, chunking, Whisper и JSON-анализ.
- `prompt.md` — отдельный системный промт.
- `requirements.txt` — зависимости.

## Интегрированный coaching-слой

Для развития сервиса создан новый Manus Skill `sales-call-quality-coach` в `/home/ubuntu/skills/sales-call-quality-coach/SKILL.md`. Он объединяет текущую оценку по чек-листу с навыками `call-review-coach`, `call-insights-to-objections`, `manager-coaching-cadence`, `persona-classification`, `adaptability`, `objection-recognition`, `objection-handling` и `win-loss-reason-extraction`.

В интерфейсе добавлена новая карта результата «Возражения и следующий звонок». Она отображает категорию возражения, статус обработки, подтверждённые шаги LAER, coaching-приоритеты, фразу для тренировки, триггер и сигнал успеха. Новые поля API: `objections`, `one_call_coaching`, `follow_up`, `team_insights`.

Дополнительные GitHub-навыки для разработки установлены в `/home/ubuntu/skills/_github-addons/`: `frontend-design`, `web-artifacts-builder`, `react-best-practices`, `web-design-guidelines`, `systematic-debugging`, `test-driven-development` и `verification-before-completion`. Они используются как development guidance и не подменяют runtime-логику CallLens.


## Module 1: Auth + Tenants

В проект добавлен фундамент multi-tenant авторизации без паролей:

- magic-link login;
- HttpOnly session cookie;
- таблицы `tenants`, `users`, `magic_link_tokens`, `sessions`;
- RBAC для `owner`, `rop`, `manager`, `analyst`;
- tenant isolation через явные фильтры SQLite и PostgreSQL RLS policy;
- Alembic migration;
- dev email logging;
- `/login` и минимальный `/app`;
- `scripts/create_tenant.py`;
- auth-тесты в `tests/test_auth.py`.

Для локального SQLite запуска:

```bash
cp .env.example .env
export DATABASE_URL=sqlite+aiosqlite:///./calllens_auth.db
alembic upgrade head
python3 scripts/create_tenant.py --name "Pilot" --slug pilot --owner-email owner@example.com
uvicorn backend:app --host 0.0.0.0 --port 8000
```

Подробный отчёт находится в `module-1-auth-tenants-report.md`. Scoring, транскрибация, dashboard и существующий `/api/analyze` в Module 1 не изменялись.
