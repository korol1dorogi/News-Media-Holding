# Задачи

Зеркало доски из «Плана победы». Источник правды по статусам — Google Doc.
Таблицу меняет только лид.

## Правила бронирования

- Берёшь одну свободную задачу, у которой готовы зависимости.
- Пишешь «беру {ID}» в чат, ставишь в доске «в работе (ник)».
- Статусы: «не начато», «в работе (ник)», «на ревью (#PR)», «готово (#PR)»,
  «перенесено → ID», «отменено: причина».
- «Готово» — только по смерженному PR.
- Ветка = ID задачи. Тесты — `tests/test_{id}_*.py`, id в нижнем регистре.
- Сразу, без ожидания других, можно брать: S1, C1, V1, V2, V3, AI1, UX1 (работают от контракта).

## Кодовые задачи

| ID | Файлы задачи (писать можно только сюда + tests/test_{id}_*.py) | Зависит | Готово, когда | Статус |
|---|---|---|---|---|
| L1 | каркас | — | make check зелёный | на ревью |
| L2 | radar/core/*, radar/api/*, frontend/src/types.ts, frontend/src/api.ts, frontend/src/mock/* | L1 | API отдаёт ту же форму, что mock-JSON | не начато |
| L3 | radar/pipeline.py, radar/storage.py | все Must-модули | make run поднимает всё, /api/replay/reset пересобирает базу | не начато |
| S1 | scripts/gen_synthetic.py, data/synthetic/* | контракт | генератор детерминирован, все события демо-сценария в truth.yaml | не начато |
| S2 | scripts/eval.py, reports/* | S1, L3 | make eval пишет reports/metrics.json и metrics.md | не начато |
| C1 | radar/normalize/* | контракт | geo и topic совпадают с ожиданием на 20 постах | не начато |
| C2 | radar/cluster/* | C1 | каждое событие truth.yaml собрано в один кластер | не начато |
| C3 | radar/score/*, data/profiles/* | C2 | шум ниже событий, порядок для mash и life различается | не начато |
| AI1 | radar/draft/generate.py, radar/llm/* (кроме `__init__.py`) | контракт | разные черновики для mash и life без сети и ключа | не начато |
| AI2 | radar/draft/claims.py | AI1 | на событии с inject_error ровно одно supported=false, на остальных ноль | не начато |
| V1 | radar/verify/provenance.py | контракт | independent и first_source совпадают с truth.yaml | не начато |
| V2 | radar/verify/media.py | контракт | «наводнение» fail, пережатая и обрезанная копия находится | не начато |
| V3 | radar/verify/weather.py | контракт | «снегопад» fail с понятным summary | не начато |
| V4 | radar/verify/official.py, radar/verify/dossier.py | V1 | уровни досье совпадают с truth.yaml | не начато |
| UX1 | frontend/src/App.tsx, frontend/src/components/*, frontend/src/pages/* | mock-JSON | демо-сценарий проходится кликами | не начато |
| UX2 | frontend/src/components/RepostGraph.tsx | UX1, V1 | у «слуха» видно один первоисточник | не начато |

UX1 не трогает `frontend/src/components/RepostGraph.tsx` — это файл UX2.

## Некодовые задачи (ведутся в Google Doc)

| ID | Задача | Зависит |
|---|---|---|
| REL1 | Деплой на VPS за Caddy, сброс демо | L3 |
| P1 | Видео на 2 минуты по демо-сценарию | L3, UX1 |
| P2 | Слайды (около 10) со скриншотами | UX1 |
| DOC1 | Текст заявки, README | S2 |

Что режем, если не успеваем (по порядку): V3, UX2, REL1, профиль Super.

## Контракт

Модели — `radar/core/models.py`, их зеркало — `frontend/src/types.ts`.

### Сигнатуры модулей

```
radar.ingest.load_replay(dir: Path) -> tuple[list[Channel], list[Post]]
radar.normalize.enrich(post: Post) -> Post
radar.cluster.build_events(posts: list[Post]) -> list[Event]
radar.score.score(event, posts, profile: dict) -> float
radar.verify.provenance(event, posts, channels) -> tuple[Check, str, int]
radar.verify.repost_graph(event, posts) -> dict  # {"nodes":[{id,channel_id,ts}], "edges":[{from,to,kind}]}
radar.verify.media_archive(event, posts, archive_dir: Path) -> Check
radar.verify.weather(event, posts, weather: dict, media_meta: dict) -> Check
radar.verify.official(event, posts, channels) -> Check
radar.verify.build_dossier(event, checks, first_id, independent) -> Dossier
radar.draft.generate(event, posts, outlet, llm) -> Draft
radar.draft.check_claims(draft, posts) -> Draft
radar.llm.Provider.complete(system: str, user: str) -> str
```

`edges[].kind` — `"forward"` или `"copy"`. В `verify.*` и `score` передаются все посты replay,
в `draft.*` — только посты события (D-09).

### API

```
GET  /api/events?outlet=mash   -> [{"event", "level", "score"}], по убыванию score
GET  /api/events/{id}          -> {"event", "dossier", "posts", "graph"}
POST /api/events/{id}/draft    body {"outlet"} -> Draft
POST /api/replay/reset         -> {"events": n}
GET  /api/metrics              -> содержимое reports/metrics.json или {}
GET  /api/ready                -> {"ok": true}
```

Пока в базе нет событий, API отдаёт фикстуры из `frontend/src/mock` с заголовком
`X-Radar-Source: fixtures` (D-08).

### Данные

```
data/synthetic/channels.json     list[Channel]
data/synthetic/posts.jsonl       Post на строку, ts в ISO 8601
data/synthetic/media/            картинки + meta.json {file: {"scene": "snow"|"rain"|"clear", "daylight": bool}}
data/synthetic/archive/          старые медиа + index.json [{"id","path","published_at","source"}]
data/synthetic/weather.json      {geo: {"YYYY-MM-DD": {"t_min","t_max","precip": "snow"|"rain"|"none"}}}
data/synthetic/truth.yaml        events: [{key, post_ids, first_source?, independent_sources?,
                                  expected_level?, expected_fail?, inject_error?}]
data/profiles/{mash,life,super}.yaml
```
