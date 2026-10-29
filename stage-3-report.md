# CallLens MVP — отчёт этапа 3

**Статус:** завершён

## Что добавлено

В backend добавлен безопасный `CALLLENS_DEMO_MODE=1`. В этом режиме endpoint `/api/analyze` принимает загруженный файл, использует тот же контракт формы и возвращает детерминированный fixture-отчёт без обращения к OpenAI и без транскрибации. Production-режим не изменён и продолжает требовать `OPENAI_API_KEY`.

Demo-результат содержит транскрипт-заглушку, баллы по текущему чек-листу, evidence-based и strict итоги, русский профиль коммуникации, карту возражений, coaching-приоритет, follow-up и Markdown-отчёт. В каждом месте явно указано, что это локальный demo-режим, а не анализ реального звонка.

## Проверки

- `python3 -m py_compile backend.py` — PASS.
- `node --check app.js` — PASS.
- Browser smoke полного пути — PASS.
- Сценарий: загрузка MP4 → запуск анализа → progress state → отображение результата — PASS.
- Demo endpoint не требует `OPENAI_API_KEY` — PASS.
- Скриншот полного demo-потока сохранён как `calllens-mvp-stage3-flow.png`.

## Как запустить

```bash
cd sales-call-quality-app
CALLLENS_DEMO_MODE=1 uvicorn backend:app --reload --port 8000
```

После проверки demo-режима переменную `CALLLENS_DEMO_MODE` нужно убрать или установить в `0`, чтобы включить рабочий AI-анализ с `OPENAI_API_KEY`.

## Ограничение этапа

Demo-режим предназначен только для проверки интерфейса и связности MVP. Он не оценивает качество менеджера и не должен использоваться для принятия рабочих решений.
