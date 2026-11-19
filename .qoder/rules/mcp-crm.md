---
name: mcp-crm
description: Как подключать MCP-серверы (CRM: Bitrix24, amoCRM; filesystem/git) к CallLens в Qoder. Использовать перед добавлением интеграций.
---

# MCP-серверы для CallLens

Текущий runtime CallLens НЕ зависит от MCP: анализ идёт через OpenAI API в
`backend.py`. MCP используется только на стороне агента разработки (Qoder).

## Подключение в Qoder

- Глобально: `~/.qoder.json`, секция `{"mcpServers": {...}}`;
- Локально для репозитория: `<root>/.mcp.json` того же формата;
- CLI: `qoder mcp add <name> <command>`, `qoder mcp list`, `qoder mcp remove`.

## Проверенные кандидаты для будущих CRM-интеграций

| Сервер | Назначение | Источник | Статус |
|---|---|---|---|
| Bitrix24 MCP (официальная REST-документация) | справка по REST API Bitrix24 при разработке интеграции | github.com/bitrix24/b24restdocs (ai-tools/mcp.md) | рекомендуется для этапа разработки |
| gunnit/bitrix24-mcp-server | операции с CRM Bitrix24 (сделки, контакты) | mcpservers.org/servers/gunnit/bitrix24-mcp-server | требует токен Bitrix24 через env |
| AmoCRM MCP (community) | leads/contacts/pipelines amoCRM, 21 tool | github.com/topics/amocrm | требует API-ключ amoCRM через env |
| filesystem, git | базовые операции агента | официальные MCP reference-серверы | подключать при необходимости |

## Правила

1. Секреты MCP (токены CRM) — только env-переменные, никогда не коммитить
   `.mcp.json` с ключами.
2. Перед подключением community-сервера проверить его лицензию и код.
3. CRM-публикация результатов анализа — только с явного действия пользователя
   (см. ограничение «MVP без CRM» в README.md); не отправлять транскрипты в
   CRM автоматически.
