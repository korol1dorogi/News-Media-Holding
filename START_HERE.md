# START_HERE — онбординг участника

Правила для тебя и твоего агента — в [AGENTS.md](AGENTS.md). Доска задач —
[docs/tasks.md](docs/tasks.md) и [«План победы»](https://docs.google.com/document/d/1UG1O0tvd8P1grRZos_uGmGy4PIYQ2Bhj9QoK_XMZEOQ/edit?tab=t.0).

## 1. Окружение

- Python 3.12, Node из `.nvmrc` (`nvm use`).
- На Windows — WSL2, и репозиторий клонируй внутрь WSL (`~/...`, не `/mnt/c/...`).
- Первый запуск:

  ```bash
  git clone https://github.com/korol1dorogi/News-Media-Holding.git
  cd News-Media-Holding
  cp .env.example .env && make setup && make check
  ```

- `make run` — API на :8000 и интерфейс на http://localhost:5173. Ctrl+C гасит оба.
- `.env.example` работает без правок: LLM — MockProvider, сеть не нужна.
  `VITE_USE_MOCK=true` — фронт читает `frontend/src/mock`, `false` — живой API.

## 2. Как взять задачу

1. Выбери свободную задачу в `docs/tasks.md`, у которой готовы зависимости.
2. Напиши в чат команды: «беру {ID}».
3. Поставь в доске Google Doc статус «в работе (ник)».

Одна задача за раз. Статус «готово» ставится только по смерженному PR.

## 3. Промт первой сессии агента

Подставь ID из `docs/tasks.md`:

```
Ты работаешь в репозитории «Сигнал». Прочитай AGENTS.md и docs/tasks.md.
Моя задача: {ID}. Файлы задачи и критерий готовности — в её строке docs/tasks.md.
Дай план (файлы, функции, тесты, как проверим критерий) и жди моего «ок».
Потом ветка {ID}, маленькие коммиты, make check, PR по шаблону.
```

## 4. Если агент сам не читает AGENTS.md

Claude Code читает CLAUDE.md, Gemini CLI — GEMINI.md, Codex — AGENTS.md.
Grok Build и другие могут не подхватить файл: вставь AGENTS.md в первое сообщение целиком.

## 5. Защита main

Прямой пуш в `main` запрещён: только PR, мержит лид.
{TODO: лид — если тариф GitHub не даёт защиту веток в приватном репозитории, правило
держится на договорённости; оставить эту строку или убрать.}

## 6. Частые проблемы

| Симптом | Что сделать |
|---|---|
| `npm ci` или `vite` падает с ошибкой версии Node | `nvm install && nvm use` (версия из `.nvmrc`) |
| `ModuleNotFoundError: radar` или `No module named fastapi` | Запусти `make setup`; вручную — `source .venv/bin/activate` |
| Фронт показывает пусто или не те данные | Нет `.env`: `cp .env.example .env`, перезапусти `make run` |
| `address already in use` на 8000 или 5173 | Найди процесс: `lsof -i :8000` (или `:5173`), останови его |
| `make: command not found` | В WSL: `sudo apt install make` |
