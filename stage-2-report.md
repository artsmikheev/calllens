# CallLens MVP — отчёт этапа 2

**Статус:** завершён

## Что изменено

- MVP явно обозначен как версия без CRM-интеграции.
- Добавлена поддержка записей `.mp4` и `.webm` в интерфейсе.
- Добавлена клиентская проверка формата и ограничения 250 МБ.
- Добавлена серверная проверка расширения файла.
- Ошибки формы выводятся inline через `aria-live`, без обязательного использования `alert`.
- Добавлен health endpoint `GET /api/health`.
- README обновлён под фактический MVP-контур.
- Smoke-тест расширен проверкой отклонения PDF и принятия MP4.

## Проверки

- `python3 -m py_compile backend.py` — PASS.
- `node --check app.js` — PASS.
- Browser smoke-тест формы — PASS.
- Проверка невалидного PDF — PASS: отображается сообщение «Формат не поддерживается».
- Проверка MP4 — PASS: файл принимается интерфейсом.
- `GET /api/health` — PASS: `{"status":"ok","service":"calllens-mvp","crm":false}`.

## Ограничение этапа

Фактическая транскрибация и анализ требуют `OPENAI_API_KEY` и запуска FastAPI backend. CRM, webhook и автоматическая публикация в эту версию не входят.

## Артефакты

- `index.html`
- `app.js`
- `backend.py`
- `README.md`
- `smoke_test.py`
- `calllens-mvp-stage2-smoke.png`
