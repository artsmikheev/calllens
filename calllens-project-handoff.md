# CallLens — полный handoff проекта для другого ИИ-агента

> Этот документ предназначен для передачи проекта другому ИИ-агенту, нейросети, техническому консультанту или разработчику. Он описывает продукт, текущую реализацию, историю разработки, API, формат данных, ограничения, тесты, известные проблемы и безопасный порядок внесения изменений.
>
> Документ отражает состояние проекта после этапа 5 MVP. Перед любыми изменениями необходимо сверять этот текст с фактическими файлами проекта: исходники имеют приоритет над описанием.

---

## 1. Краткое резюме

**CallLens** — русскоязычный MVP-сервис для анализа sales-звонков отдела продаж.

Пользователь загружает аудио- или видеозапись звонка и чек-лист менеджера. Сервис должен:

1. принять и проверить запись;
2. транскрибировать её с сегментными тайм-кодами;
3. по возможности разделить реплики между говорящими;
4. оценить звонок строго по переданному чек-листу;
5. рассчитать два итоговых результата — evidence-based и strict;
6. показать доказательства в виде цитат с тайм-кодами;
7. выделить пропущенные или частично выполненные этапы;
8. распознать наблюдаемый коммуникационный стиль клиента;
9. сформировать карту возражений и проверку обработки по LAER;
10. сформировать 1–3 coaching-приоритета для следующего звонка;
11. дать follow-up-условие для последующей проверки менеджера;
12. экспортировать результат в Markdown или PDF через печать браузера.

На текущем этапе CRM-интеграции **нет**. Bitrix24 и amoCRM исследовались архитектурно, но в runtime CallLens они не подключены.

---

## 2. Цель проекта

Основная бизнес-цель — превратить запись sales-звонка в доказательный отчёт для руководителя отдела продаж и менеджера.

Сервис должен отвечать на вопросы:

- Что реально сказал менеджер и клиент?
- Какие обязательные этапы разговора выполнены?
- Какие этапы не наблюдались или выполнены частично?
- Какие фразы подтверждают оценку?
- Какие возражения возникли?
- Как менеджер обработал каждое возражение?
- Что менеджеру нужно потренировать на следующем сопоставимом звонке?
- Можно ли агрегировать повторяющиеся провалы и возражения на уровне команды?

Главный принцип проекта: **не выдавать красивую, но недоказательную оценку**. Любой балл, вывод или coaching должен опираться на наблюдаемую реплику, тайм-код или явно обозначенное ограничение качества записи.

---

## 3. Принципы качества и безопасности

### 3.1. Разделение факта, интерпретации и рекомендации

Каждый вывод должен быть отделён от:

- `observed_fact` — что фактически прозвучало;
- `interpretation` — осторожная интерпретация поведения;
- `recommendation` — что менеджеру делать дальше.

Нельзя представлять гипотезу о коммуникационном стиле как диагноз личности, неизменную характеристику или кадровое решение.

### 3.2. Доказательность

Для каждого критерия чек-листа желательно хранить:

- точное название критерия;
- максимальный балл;
- статус;
- заработанные баллы;
- короткую точную цитату;
- тайм-код;
- основание оценки;
- confidence, если используется расширенный контракт.

Запрещено создавать цитаты, которых нет в транскрипте.

### 3.3. Осторожная атрибуция ролей

Если запись монофоническая и полноценная диаризация недоступна, нельзя уверенно выдавать `MANAGER` и `CLIENT` только по тону, полу, длительности речи или интуиции модели.

В этом случае следует использовать:

- `Speaker 1` / `Speaker 2`;
- `unknown_speaker`;
- `role_warning=true`;
- provisional-статус для оценок, зависящих от правильной атрибуции.

### 3.4. Конфиденциальность

Аудиозаписи, имена, телефоны, email, результаты оценки, профили клиентов и coaching-отчёты являются чувствительными данными.

Нельзя:

- публиковать записи в открытом доступе;
- отправлять оценки в CRM, HR-систему или третью систему без явного согласия;
- коммитить API-ключи;
- помещать секреты в `index.html`, `app.js` или frontend-конфигурацию.

---

## 4. Текущее состояние MVP

### Реализовано

- русскоязычный web-интерфейс;
- drag-and-drop и выбор записи через браузер;
- поддержка MP3, WAV, M4A, OGG, MP4, WEBM, MPEG, MPGA;
- клиентская и серверная проверка расширения;
- ограничение MVP — 250 МБ на файл;
- загрузка чек-листа из Markdown, TXT или CSV;
- добавление критериев вручную;
- сохранение ручного чек-листа в `localStorage` браузера;
- FastAPI backend;
- разрезание больших файлов через `ffmpeg` на 15-минутные MP3-чанки;
- транскрибация через OpenAI-compatible Audio Transcriptions API;
- сегментные тайм-коды;
- scoring по каждому критерию;
- evidence-based и strict проценты;
- карта пропусков;
- профиль коммуникационного стиля клиента;
- карта возражений;
- LAER-поля;
- one-call coaching;
- follow-up;
- экспорт Markdown;
- печать в PDF через браузер;
- dashboard команды на демо-данных;
- JSON/CSV-импорт данных менеджеров в dashboard;
- demo-режим без внешнего AI-вызова;
- health endpoint;
- smoke-тесты frontend и backend-контракта.

### Не реализовано

- полноценная акустическая диаризация в runtime;
- надёжное автоматическое сопоставление говорящих с MANAGER и CLIENT;
- импорт формул и весов Excel-чек-листа без потери семантики;
- авторизация пользователей;
- хранение истории звонков в базе данных;
- командная многопользовательская работа;
- CRM-интеграция;
- webhook-сценарии;
- автоматическая синхронизация с Bitrix24 или amoCRM;
- production-мониторинг и трассировка;
- фоновые job-и для очень длинных записей;
- политика хранения и удаления исходных аудиофайлов на production;
- полноценный worker для WhisperX/pyannote.

---

## 5. Архитектура проекта

```text
Пользователь в браузере
        |
        v
index.html + styles.css + app.js
        |
        | POST /api/analyze
        v
FastAPI backend.py
        |
        +-- проверка расширения и размера
        +-- временное сохранение файла
        +-- ffprobe: длительность
        +-- ffmpeg: разбиение больших файлов
        +-- OpenAI-compatible transcription API
        +-- scoring AI-вызов
        +-- profile/coaching AI-вызов
        +-- нормализация JSON
        +-- сборка Markdown
        v
JSON result + markdown
        |
        +-- рендер карточек результата
        +-- отображение транскрипта
        +-- экспорт .md
        +-- печать в PDF
```

### Важная текущая особенность

Backend разделяет анализ на два AI-вызова:

1. **Scoring-вызов** — оценивает все критерии чек-листа.
2. **Insights-вызов** — формирует профиль клиента, возражения, LAER, coaching и follow-up.

Такой подход появился после того, как единый длинный запрос к reasoning-модели мог израсходовать весь budget на рассуждение и вернуть пустой JSON или placeholder.

---

## 6. Структура исходников

Корневая папка web-приложения:

```text
/home/ubuntu/sales-call-quality-app/
```

### Основные файлы

| Файл | Назначение |
|---|---|
| `index.html` | Основная страница загрузки и отчёта |
| `styles.css` | Дизайн-система, responsive layout и print styles |
| `app.js` | Frontend state, загрузка, прогресс, API-вызов, render и экспорт |
| `backend.py` | FastAPI, upload, ffmpeg, транскрибация, AI-анализ, нормализация |
| `prompt.md` | Legacy/общий системный prompt и JSON-контракт |
| `requirements.txt` | Python-зависимости |
| `.env.example` | Шаблон переменных окружения |
| `dashboard.html` | Dashboard эффективности команды |
| `dashboard.css` | Стили dashboard |
| `dashboard.js` | KPI, фильтры, сравнения менеджеров, JSON/CSV-import |
| `smoke_test.py` | Smoke-тест основной страницы |
| `dashboard_smoke.py` | Smoke-тест dashboard |
| `mvp_flow_smoke.py` | Smoke-тест upload → demo result |
| `stage-2-report.md` | Отчёт этапа 2 |
| `stage-3-report.md` | Отчёт этапа 3 |
| `stage-4-report.md` | Отчёт этапа 4 |
| `calllens-*.png` | Скриншоты проверок и превью |
| `calllens-motion-graphics.mp4` | Motion-graphics демонстрация сервиса |

### Manus Skills

```text
/home/ubuntu/skills/sales-call-quality-analyst/SKILL.md
/home/ubuntu/skills/sales-call-quality-coach/SKILL.md
/home/ubuntu/skills/call-analysis-pipeline/SKILL.md
```

Главные Skills:

- `sales-call-quality-analyst` — end-to-end анализ записи, транскрипция, осторожная диаризация, scoring и профиль клиента;
- `sales-call-quality-coach` — scoring, возражения, LAER, адаптация менеджера, one-call coaching и follow-up;
- `call-analysis-pipeline` — подготовка аудио и базовый pipeline анализа.

---

## 7. Backend: фактическая реализация

### 7.1. FastAPI-приложение

Файл: `backend.py`.

Приложение создаётся так:

```python
app = FastAPI(title='CallLens API')
```

Сейчас CORS открыт широко:

```python
allow_origins=['*']
```

Для production это нужно заменить на whitelist доверенных доменов.

### 7.2. Поддерживаемые расширения

```python
SUPPORTED_AUDIO_SUFFIXES = {
    '.mp3', '.wav', '.m4a', '.ogg',
    '.mp4', '.webm', '.mpeg', '.mpga'
}
```

### 7.3. Ограничения

- frontend и backend ограничивают размер файла 250 МБ;
- если файл больше 25 МБ, backend режет его на чанки;
- chunk duration — 900 секунд;
- codec для промежуточных чанков — `libmp3lame`;
- bitrate промежуточных чанков — 96 kbps;
- временные файлы создаются через `TemporaryDirectory` и удаляются после запроса.

### 7.4. Транскрибация

Текущий путь:

```python
api.audio.transcriptions.create(
    model=os.getenv('OPENAI_TRANSCRIBE_MODEL', 'whisper-1'),
    file=f,
    response_format='verbose_json',
    timestamp_granularities=['segment']
)
```

Сегменты нормализуются в текстовый формат:

```text
[00:01–00:05] Speaker 1: текст реплики
```

Важно: текущий backend не выполняет полноценную speaker diarization. Он выдаёт `Speaker 1` для полученных сегментов, если отдельная диаризация не была добавлена.

### 7.5. Scoring-вызов

Scoring system prompt требует:

- оценить каждый критерий ровно один раз;
- использовать только реальные цитаты;
- вернуть `name`, `max_points`, `earned_points`, `verdict`, `quote`, `timestamp`, `reason`;
- использовать статусы:
  - `выполнено`;
  - `частично`;
  - `провал`;
  - `не наблюдалось`.

По умолчанию используется:

```text
OPENAI_ANALYSIS_MODEL=gpt-5-nano
reasoning_effort=low
```

### 7.6. Insights-вызов

Insights system prompt отвечает за:

- `client_communication_profile`;
- `objections`;
- LAER;
- `one_call_coaching`;
- `follow_up`;
- `team_insights`;
- `role_warning`.

Если confidence профиля ниже 0.55, нужно сообщать, что надёжный профиль не сформирован.

### 7.7. Нормализация

`normalize()`:

- всегда добавляет фактический транскрипт в результат;
- нормализует русские названия стилей;
- добавляет `verdict_key` для frontend;
- заполняет отсутствующие поля objections и LAER;
- ограничивает coaching тремя элементами;
- заменяет placeholder-markdown на локально собранный Markdown;
- приводит невалидный `role_warning` к boolean и сохраняет исходные детали в `role_warning_detail`.

---

## 8. API-контракт

### 8.1. `GET /`

Возвращает `index.html`.

### 8.2. `GET /api/health`

Пример ответа:

```json
{
  "status": "ok",
  "service": "calllens-mvp",
  "crm": false,
  "mode": "demo",
  "provider": "openai",
  "ai_configured": true
}
```

`mode`:

- `demo` — внешний AI не вызывается;
- `ai` — backend пытается выполнить реальный анализ.

### 8.3. `POST /api/analyze`

`multipart/form-data`:

| Поле | Тип | Обязательно | Описание |
|---|---|---:|---|
| `audio` | file | да | Аудио или видео |
| `checklist` | string | да | JSON-массив критериев |
| `manager_name` | string | нет | Имя менеджера |
| `client_name` | string | нет | Имя клиента |
| `call_goal` | string | нет | Цель звонка |

Пример checklist:

```json
[
  {"name":"Установил цель звонка","max_points":10},
  {"name":"Выявил потребность","max_points":20},
  {"name":"Отработал возражения","max_points":20}
]
```

### 8.4. Основной response contract

```json
{
  "role_warning": true,
  "role_warning_detail": null,
  "roles": {
    "manager": "MANAGER",
    "client": "CLIENT"
  },
  "transcript": "[00:00–00:05] Speaker 1: ...",
  "score": {
    "earned_points": 0,
    "max_points": 0,
    "observable_max_points": 0,
    "evidence_percent": 0,
    "strict_percent": 0,
    "criteria": [
      {
        "name": "",
        "max_points": 0,
        "earned_points": 0,
        "verdict": "выполнено",
        "verdict_key": "pass",
        "quote": "",
        "timestamp": "",
        "reason": ""
      }
    ]
  },
  "omissions": {
    "not_observed": [],
    "partial": []
  },
  "client_communication_profile": {
    "primary_type": "",
    "primary_type_label": "",
    "secondary_type": "",
    "secondary_type_label": "",
    "confidence": 0,
    "confidence_percent": 0,
    "confidence_label": "low",
    "evidence": [],
    "counter_evidence": [],
    "manager_playbook": {},
    "manager_adaptation": {}
  },
  "objections": [],
  "one_call_coaching": [],
  "follow_up": {},
  "team_insights": {},
  "markdown": "# Разбор sales-звонка"
}
```

### 8.5. Ошибки API

Ожидаемые статусы:

- `400` — некорректный JSON чек-листа;
- `413` — файл больше 250 МБ;
- `415` — неподдерживаемый формат;
- `500` — отсутствует `OPENAI_API_KEY`;
- `502` — внешний AI-провайдер вернул ошибку, пустой ответ или некорректный JSON.

Нельзя возвращать частично сформированный отчёт после провала AI-вызова.

---

## 9. Frontend

### 9.1. Основной state

```javascript
const state = {
  audio: null,
  checklist: [],
  result: null
};
```

### 9.2. Основной пользовательский flow

1. Пользователь выбирает файл или перетаскивает его в dropzone.
2. Frontend проверяет расширение и размер.
3. Пользователь загружает чек-лист или добавляет пункты вручную.
4. Frontend сохраняет чек-лист в `localStorage`.
5. Пользователь нажимает «Анализировать».
6. Отображается прогресс:
   - загрузка;
   - транскрибация;
   - чек-лист;
   - психотип;
   - готово.
7. Frontend отправляет multipart-запрос на `/api/analyze`.
8. Рендерятся карточки:
   - score;
   - omissions;
   - profile;
   - objections/coaching;
   - transcript.
9. Пользователь скачивает Markdown, печатает PDF или копирует отчёт.

### 9.3. Русские названия стилей

В интерфейсе должны использоваться только:

- `Результатный стратег`;
- `Доказательный эксперт`;
- `Визионер-вдохновитель`;
- `Надёжный партнёр`.

Английские ключи допускаются только в compatibility map для старых ответов модели.

### 9.4. Frontend-риски

- `app.js` рассчитан на объектную структуру ответа; если внешний AI вернёт нестандартный тип поля, нужен defensive normalization на backend;
- progress bar является UX-индикатором, а не реальным процентом завершения job;
- в текущем MVP запрос выполняется синхронно;
- при очень длинной записи браузер ждёт ответ в одном HTTP-запросе;
- для production стоит перейти на job ID + polling/WebSocket.

---

## 10. Dashboard команды

Файлы:

```text
dashboard.html
dashboard.css
dashboard.js
```

Dashboard показывает:

- количество звонков;
- средний evidence score;
- средний strict score;
- среднюю адаптацию;
- сравнение менеджеров;
- матрицу менеджер × стиль клиента;
- повторяющиеся провалы;
- фокус следующего звонка.

Поддерживаемая структура импорта:

```text
[
  {
    "date": "2026-08-01",
    "manager": "Анна",
    "style": "Доказательный эксперт",
    "evidence": 82,
    "strict": 74,
    "adaptation": 68,
    "next": "Уточнение бюджета",
    "focus": "Работа с возражением",
    "gaps": "Не зафиксирован следующий шаг"
  }
]
```

CSV должен содержать поля:

```text
date,manager,style,evidence,strict,adaptation,next,focus,gaps
```

На текущем этапе dashboard использует импортируемые данные и demo fixtures. Он не получает автоматически историю из backend и не хранит базу звонков.

---

## 11. Чек-лист и веса

В MVP frontend принимает простую структуру `name + max_points`.

Пример:

```text
Установил цель звонка,10
Выявил потребность,20
Провёл презентацию,15
Отработал возражение,20
Зафиксировал следующий шаг,15
```

Текущая проблема: сложные Excel-чек-листы с формулами, процентными весами, объединёнными ячейками и правилами частичного выполнения пока не импортируются семантически.

### Обязательная следующая доработка

Создать отдельный parser:

1. читать XLSX через `openpyxl`;
2. находить рабочий диапазон критериев;
3. извлекать точный текст критерия;
4. извлекать maximum/weight;
5. сохранять правила partial-credit;
6. сохранять признак `not_applicable`;
7. валидировать сумму весов;
8. передавать в backend уже нормализованный JSON;
9. сохранять исходный текст и формулы для аудита.

Нельзя молча заменять сложные веса равными единичными баллами в production.

---

## 12. Коммуникационные стили клиента

CallLens использует четыре практические категории, основанные прежде всего на DISC и Social Styles. Это не диагнозы.

### 12.1. Результатный стратег

Наблюдаемые сигналы:

- прямые короткие вопросы;
- сроки, деньги, результат, контроль;
- желание быстро перейти к решению;
- нетерпимость к длинному вступлению.

Рекомендации менеджеру:

- начинать с цели и результата;
- показывать ROI, сроки и варианты;
- отвечать прямо;
- не перегружать контекстом.

### 12.2. Доказательный эксперт

Наблюдаемые сигналы:

- вопросы «как посчитано?»;
- запросы доказательств, методики и ограничений;
- сравнение вариантов по критериям;
- внимание к рискам и реализации.

Рекомендации:

- показывать предпосылки и доказательства;
- разделять факты и оценки;
- объяснять риски;
- не использовать неподтверждённые обещания.

### 12.3. Визионер-вдохновитель

Наблюдаемые сигналы:

- язык возможностей и будущего;
- истории и идеи;
- фразы «а можно ещё?»;
- эмоциональная реакция на демонстрации.

Рекомендации:

- показать образ будущего;
- использовать короткий пример или историю;
- быстро перевести интерес в пилот, владельца и дату;
- не оставлять идеи без следующего шага.

### 12.4. Надёжный партнёр

Наблюдаемые сигналы:

- вопросы о команде и поддержке;
- осторожность в изменениях;
- ссылки на коллег и согласование;
- вежливое согласие без явного commitment.

Рекомендации:

- создать доверие;
- выяснить скрытые риски;
- показать поддержку и план внедрения;
- не путать вежливое согласие с решением.

При confidence ниже 0.55 нужно писать, что надёжный профиль не сформирован.

---

## 13. Возражения и LAER

Поддерживаемые категории возражений:

- цена;
- сроки;
- потребность / соответствие;
- доверие / риск;
- полномочия / процесс;
- конкурент;
- реализация.

LAER:

1. **Listen** — менеджер выслушал без перебивания;
2. **Acknowledge** — признал concern клиента;
3. **Explore** — исследовал причину;
4. **Respond** — дал релевантный ответ, доказательство или вариант;
5. **Confirm** — проверил, снят ли вопрос.

Общий product pitch нельзя засчитывать как ответ на конкретное возражение.

---

## 14. История разработки

### Этап 1 — baseline

- создана папка `callLens/CallLens MVP` на Google Drive;
- сохранён baseline проекта;
- зафиксирована архитектура MVP без CRM.

### Этап 2 — upload MVP

- добавлена поддержка MP4 и WEBM;
- добавлена проверка формата на frontend и backend;
- добавлен health endpoint;
- добавлены inline-сообщения ошибок;
- создан smoke-тест загрузки.

### Этап 3 — demo flow

- добавлен demo-режим без API-ключа;
- проверен полный путь upload → progress → result;
- добавлен fixture-результат с отчётом.

### Этап 4 — AI configuration

- добавлен AI/demo status в верхнюю панель;
- добавлен `.env.example`;
- health endpoint показывает режим;
- проверены сценарии отсутствующего ключа и demo-режима.

### Этап 5 — первый реальный анализ

- выполнена транскрибация длинной записи;
- первоначальный единый AI-вызов столкнулся с недостатком кредитов и пустым reasoning-ответом;
- backend переведён на `gpt-5-nano` с `reasoning_effort=low`;
- анализ разделён на scoring и insights;
- реальный отчёт собран по 27 критериям;
- результаты сохранены локально и на Google Drive.

Итог тестового реального анализа:

- длительность: 51:36.8;
- 943 транскрибированные строки;
- 27 критериев;
- evidence-based: 95.8%;
- strict: 85.2%;
- 3 objections;
- 3 coaching priorities;
- полноценная роль MANAGER/CLIENT не подтверждена из-за моно-записи.

---

## 15. Артефакты реального анализа

Локально:

```text
/home/ubuntu/calllens-stage5-result/stage-5-real-analysis-report.md
/home/ubuntu/calllens-stage5-result/transcript.txt
/home/ubuntu/calllens-stage5-result/result.json
/home/ubuntu/calllens-stage5-result/result-summary.json
/home/ubuntu/calllens-stage5-result.zip
```

Google Drive, папка `callLens/CallLens MVP`:

- `Stage 5 real analysis report.md`;
- `Stage 5 full transcript.txt`;
- `CallLens stage 5 real analysis result.zip`;
- `CallLens MVP stage 5 project.zip`.

Не включать API-ключи в архивы и handoff-документы.

---

## 16. Запуск проекта

### 16.1. Установка

```bash
cd /home/ubuntu/sales-call-quality-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Нужен установленный `ffmpeg`.

### 16.2. Demo-режим

Используется для тестирования интерфейса без внешнего AI-вызова:

```bash
cd /home/ubuntu/sales-call-quality-app
CALLLENS_DEMO_MODE=1 python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000
```

### 16.3. AI-режим

```bash
export OPENAI_API_KEY="ваш_ключ"
export OPENAI_TRANSCRIBE_MODEL="whisper-1"
export OPENAI_ANALYSIS_MODEL="gpt-5-nano"
export CALLLENS_DEMO_MODE=0

python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000
```

### 16.4. Проверка

```bash
curl http://127.0.0.1:8000/api/health
curl -I http://127.0.0.1:8000/
```

### 16.5. Доступ в текущем Manus sandbox

Эфемерная ссылка строится по шаблону:

```text
https://8000-iehriisix4wcstw7ao95i-7d08188f.us5.manus.computer/
```

Она относится к текущей sandbox-сессии и не является production-доменом.

---

## 17. Тестирование

### Синтаксические проверки

```bash
python3 -m py_compile backend.py
node --check app.js
```

### Основной smoke-тест

```bash
python3 /home/ubuntu/skills/webapp-testing/scripts/with_server.py \
  --server "python3 -m http.server 8101" \
  --port 8101 \
  -- env TEST_PORT=8101 python3 smoke_test.py
```

### Demo flow

```bash
python3 /home/ubuntu/skills/webapp-testing/scripts/with_server.py \
  --server "CALLLENS_DEMO_MODE=1 python3 -m uvicorn backend:app --host 127.0.0.1 --port 8133" \
  --port 8133 \
  -- env TEST_PORT=8133 python3 mvp_flow_smoke.py
```

### Dashboard

```bash
python3 /home/ubuntu/skills/webapp-testing/scripts/with_server.py \
  --server "python3 -m http.server 8117 --bind 127.0.0.1" \
  --port 8117 \
  -- env TEST_PORT=8117 python3 dashboard_smoke.py
```

### Что уже проверено

- backend syntax — passed;
- frontend syntax — passed;
- health endpoint — passed;
- demo upload flow — passed;
- dashboard smoke — passed;
- полный реальный scoring по 27 критериям — passed;
- проверка отсутствия placeholder-цитат — passed;
- сохранение отчёта и транскрипта на Google Drive — passed.

---

## 18. Известные проблемы и технический долг

### P0 — нельзя использовать для production scoring без исправления

1. **Нет полноценной диаризации.** Моно-записи могут смешивать роли.
2. **Excel-веса не импортируются полностью.** Возможна потеря весов и правил частичного балла.
3. **Синхронный длинный HTTP-запрос.** Большие записи могут привести к timeout.
4. **CORS `*`.** Для production нужен whitelist.
5. **Нет авторизации и изоляции данных.** Любой production deployment должен получить auth и tenant boundaries.

### P1 — важные улучшения

1. Добавить WhisperX/pyannote worker.
2. Перевести анализ на job queue: `POST /api/jobs` → `GET /api/jobs/{id}`.
3. Хранить normalized transcript отдельно от report JSON.
4. Добавить UUID звонка и audit log.
5. Добавить retry с лимитом для временных ошибок AI provider.
6. Добавить модель провайдера через adapter interface.
7. Добавить structured output schema с JSON Schema.
8. Добавить реальную проверку суммы весов чек-листа.
9. Добавить regression fixtures с эталонными ответами.
10. Ограничить prompt injection из пользовательского транскрипта.

### P2 — качество продукта

1. Показать в UI качество записи и confidence диаризации.
2. Добавить отдельный блок «что нельзя оценить из этой записи».
3. Добавить сравнение нескольких звонков одного менеджера.
4. Подключить team insights к настоящему хранилищу.
5. Добавить экспорт JSON, CSV и PDF-файла на backend.
6. Добавить удаление записи после обработки.
7. Добавить локализацию и настройку формата тайм-кодов.

### Небольшие проблемы текущего кода

- В `backend.py` присутствует недостижимая повторная строка `return normalize(...)` после уже выполненного return; её можно удалить как cleanup.
- В старом `prompt.md` остаётся общий JSON-контракт с placeholder-примером; production path сейчас использует inline prompts в `backend.py`, поэтому нужно либо синхронизировать файлы, либо явно разделить legacy prompt и runtime prompts.
- `health()` сейчас возвращает `provider: openai` даже если в будущем будет подключён другой adapter; это поле следует сделать динамическим.
- Некоторые ответы внешней модели могут возвращать объектные поля в нестандартном виде; нормализация уже частично защищает от этого, но нужен строгий schema validator.

---

## 19. Рекомендуемая архитектура следующей версии

```text
Frontend
  |
  +-- POST /api/jobs
  |       |
  |       +-- job_id
  |
API Gateway / Auth
  |
  +-- Upload storage with TTL
  |
  +-- Queue: transcription job
  |       |
  |       +-- Media preparation
  |       +-- Channel split / diarization
  |       +-- STT
  |
  +-- Queue: analysis job
  |       |
  |       +-- checklist scoring
  |       +-- objection extraction
  |       +-- profile hypothesis
  |       +-- coaching
  |
  +-- Report store
  |       |
  |       +-- transcript.json
  |       +-- report.json
  |       +-- report.md
  |
  +-- Dashboard aggregation
  |
  +-- Optional CRM adapters
          |
          +-- Bitrix24
          +-- amoCRM
```

### Adapter interface для AI-провайдера

Рекомендуемый интерфейс:

```python
class TranscriptionProvider:
    def transcribe(self, media_path: str) -> TranscriptResult: ...

class AnalysisProvider:
    def score_checklist(self, transcript, checklist, meta) -> ScoreResult: ...
    def extract_insights(self, transcript, meta) -> InsightsResult: ...
```

Это позволит заменить OpenAI-compatible provider на Gemini, локальную модель, Azure OpenAI или другой сервис без переписывания FastAPI endpoint.

---

## 20. Предлагаемый порядок доработки

### Шаг 1 — корректность данных

- реализовать XLSX parser;
- добавить JSON Schema для report;
- зафиксировать точный contract;
- написать fixtures для 5 типовых звонков.

### Шаг 2 — диаризация

- проверить stereo/dual-channel;
- добавить WhisperX/pyannote worker;
- сохранять `source_channel`, `speaker`, `confidence`;
- добавить ручное подтверждение mapping MANAGER/CLIENT.

### Шаг 3 — надёжность исполнения

- job queue;
- progress persistence;
- retry/backoff;
- timeouts;
- ограничение concurrency;
- structured logs.

### Шаг 4 — безопасность

- auth;
- tenant isolation;
- signed upload URLs;
- TTL storage;
- deletion policy;
- redaction;
- CORS whitelist;
- rate limits.

### Шаг 5 — team analytics

- database for calls/reports;
- repeated objections aggregation;
- manager trend lines;
- confidence-aware dashboard;
- comparison by call type.

### Шаг 6 — CRM adapters

Только после стабилизации report contract:

- Bitrix24 adapter;
- amoCRM adapter;
- explicit user confirmation before publishing report;
- idempotency keys;
- timeline comment / note mapping;
- error queue and retry.

---

## 21. Инструкция другому ИИ-агенту перед началом работы

Перед изменениями агент должен:

1. Прочитать этот файл.
2. Прочитать `README.md`.
3. Прочитать `backend.py`, `app.js`, `prompt.md`.
4. Проверить актуальную структуру файлов командой `find`.
5. Не считать README единственным источником истины — сверить фактический код.
6. Не менять scoring contract без описания migration impact.
7. Не включать CRM без отдельного запроса и подтверждения.
8. Не включать production AI-вызовы в smoke-тест без явного указания.
9. Не использовать реальные API-ключи в коде или коммитах.
10. После каждого значимого изменения выполнить syntax checks и соответствующий smoke-тест.
11. Для изменения frontend проверить desktop, narrow viewport, keyboard focus и print layout.
12. Для изменения scoring проверить минимум один fixture с известными баллами.
13. Для изменения транскрибации проверить timestamps, chunk boundaries и error handling.
14. В отчёте указать, какие файлы изменены, какие тесты пройдены и какие ограничения остались.

---

## 22. Формат обратной связи от другого агента

Другой ИИ должен возвращать рекомендации в следующей структуре:

```markdown
# Code / Architecture Review: CallLens

## Executive summary

Кратко: что хорошо, какие 3 главные проблемы, что делать первым.

## Findings

### [P0/P1/P2] Название проблемы

- File:
- Lines:
- Evidence:
- Risk:
- Suggested fix:
- Regression test:

## Product risks

- Что может привести к неправильному scoring?
- Что может навредить менеджеру или клиенту?
- Где возможна утечка данных?

## Architecture recommendations

- Что менять сейчас;
- что отложить;
- какие решения не принимать до появления дополнительных данных.

## Test plan

- Unit tests;
- API tests;
- browser tests;
- fixtures;
- load/error tests.

## Migration plan

Порядок внесения изменений без разрушения текущего MVP.
```

Агент не должен ограничиваться общими советами вроде «добавьте безопасность». Нужны конкретные файлы, функции, риски, тесты и критерии готовности.

---

## 23. Готовый prompt для передачи другому ИИ

```text
Ты — независимый технический архитектор и reviewer проекта CallLens.

Прочитай файл calllens-project-handoff.md и сверяй его с исходниками проекта.
Проект — русскоязычный MVP для загрузки аудиозаписи sales-звонка, транскрибации,
оценки по чек-листу, анализа возражений и coaching менеджера.

Твоя задача:
1. Проверить соответствие документации фактическому коду.
2. Найти ошибки в scoring, транскрибации, атрибуции ролей, нормализации JSON и UI.
3. Отделить P0/P1/P2-проблемы.
4. Не предлагать CRM-интеграцию, если она не нужна для конкретного улучшения.
5. Особое внимание уделить:
   - сохранению точных весов Excel-чек-листа;
   - доказательности цитат и тайм-кодов;
   - ошибкам монофонической записи;
   - prompt injection из транскрипта;
   - долгим синхронным AI-запросам;
   - утечке аудио и персональных данных;
   - качеству fallback/error handling;
   - расхождению между prompt.md и runtime prompts в backend.py.

Не меняй файлы автоматически. Сначала подготовь review с конкретными file/line references,
риском, предлагаемым исправлением и регрессионным тестом.
```

---

## 24. Критерии готовности production-версии

CallLens можно считать готовым к ограниченному production-пилоту, когда выполнены все условия:

- [ ] есть авторизация и разделение пользователей;
- [ ] есть политика удаления аудио и транскриптов;
- [ ] есть точный импорт Excel-весов;
- [ ] есть полноценная или подтверждаемая диаризация;
- [ ] роль-зависимые баллы помечаются provisional при низкой уверенности;
- [ ] длинные звонки обрабатываются через фоновые jobs;
- [ ] report contract валидируется JSON Schema;
- [ ] AI-ошибки не приводят к частичным или выдуманным отчётам;
- [ ] есть regression fixtures;
- [ ] есть rate limit и audit log;
- [ ] CORS ограничен доверенными доменами;
- [ ] есть ручное подтверждение публикации результатов во внешние системы;
- [ ] dashboard строится на сохранённых структурированных отчётах;
- [ ] privacy review пройден;
- [ ] установлен production monitoring.

---

## 25. Итог для нового агента

CallLens уже имеет рабочий MVP-путь «загрузка записи → транскрибация/анализ → структурированный отчёт», demo-режим, dashboard и coaching-слой.

Самые важные ограничения сейчас — не визуальная часть, а надёжность данных:

1. точность speaker diarization;
2. сохранение исходных весов чек-листа;
3. устойчивость обработки длинных файлов;
4. строгая валидация AI-ответов;
5. безопасность хранения и передачи записей.

Любые следующие изменения должны сначала улучшать доказательность и надёжность отчёта, а уже потом добавлять новые визуальные или CRM-функции.


---

## 26. Module 1: Auth + Tenants — добавлено 2026-10-29

Проект получил фундамент multi-tenant авторизации без паролей. Реализованы SQLAlchemy 2 async models, Alembic migration, magic-link login, HttpOnly session cookie, RBAC, tenant-aware user access, dev email logging и SQLite fallback.

Новые runtime-файлы находятся в `sales-call-quality-app/`:

- `auth_settings.py`;
- `auth_models.py`;
- `auth_db.py`;
- `auth_mail.py`;
- `auth_routes.py`;
- `login.html`;
- `app-home.html`;
- `alembic.ini`;
- `alembic/env.py`;
- `alembic/versions/0001_auth_tenants.py`;
- `scripts/create_tenant.py`;
- `tests/test_auth.py`;
- `pytest.ini`;
- `module-1-auth-tenants-report.md`.

Добавлены endpoints:

- `POST /api/auth/request-link`;
- `GET /api/auth/verify`;
- `POST /api/auth/logout`;
- `GET /api/auth/me`;
- `POST /api/tenants/{tenant_id}/invite`;
- `GET /api/users`;
- `PATCH /api/users/{user_id}`.

PostgreSQL migration создаёт `pgcrypto`, `citext`, таблицы tenants/users/tokens/sessions и RLS policy на `users`. В таблицу sessions добавлен `tenant_id`, чтобы до чтения пользователя установить `SET LOCAL app.current_tenant` и корректно пройти RLS bootstrap.

Проверки Module 1:

- auth tests: **7 passed**;
- Alembic SQLite migration: **passed**;
- `create_tenant.py`: **passed**;
- Python compile и frontend syntax: **passed**;
- основной UI smoke: **passed**;
- dashboard smoke: **passed**;
- demo upload flow: **passed**.

Ограничения: PostgreSQL RLS пока не прогонялся на реальном PostgreSQL в текущей sandbox-среде; `/api/analyze` оставлен без auth dependency, чтобы не ломать текущий MVP-контракт. Перед сохранением звонков и отчётов в Module 2 необходимо привязать `/api/analyze` к current tenant.
