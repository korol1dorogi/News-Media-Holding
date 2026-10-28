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
- Сразу, без ожидания других, можно брать: AI1, UX1, S2, L4 (лид), S3 (генератор, без отчёта).

## Кодовые задачи

| ID | Файлы задачи (писать можно только сюда + tests/test_{id}_*.py) | Зависит | Готово, когда | Статус |
|---|---|---|---|---|
| L1 | каркас | — | make check зелёный | готово (#11) |
| L2 | radar/core/*, radar/api/*, frontend/src/types.ts, frontend/src/api.ts, frontend/src/mock/* | L1 | API отдаёт ту же форму, что mock-JSON | готово (в L1) |
| L3 | radar/pipeline.py, radar/storage.py | все Must-модули | make run поднимает всё, /api/replay/reset пересобирает базу | готово (в main) |
| S1 | scripts/gen_synthetic.py, data/synthetic/* | контракт | генератор детерминирован, все события демо-сценария в truth.yaml | готово (#6) |
| S2 | scripts/eval.py, reports/* (кроме reports/hard/ и reports/redteam.md) | S1, L3 | make eval пишет reports/metrics.json и metrics.md; максимум — в карточке | готово (в main) |
| S3 | scripts/gen_synthetic_hard.py, data/synthetic_hard/*, reports/hard/* | S1, S2 | хитрые фейки во втором городе, свой truth.yaml, отчёт S2 по ним в reports/hard/ | готово (в main): 6 из 10 уровней, провалы в reports/hard/findings.md |
| C1 | radar/normalize/* | контракт | geo и topic совпадают с ожиданием на 20 постах | готово (#7) |
| C2 | radar/cluster/* | C1 | каждое событие truth.yaml собрано в один кластер | готово (#8) |
| C3 | radar/score/*, data/profiles/* | C2 | шум ниже событий, порядок для mash и life различается | готово (#9) |
| C4 | radar/score/learn.py, data/labels/* | C3, S2 | логрегрессия на метках «опубликовано / нет» обучается детерминированно, S2 сравнивает её с ручными весами | готово (в main) |
| AI1 | radar/draft/generate.py, radar/llm/* (кроме `__init__.py`) | контракт | разные черновики для mash и life без сети и ключа; максимум — в карточке | готово (в main) |
| AI2 | radar/draft/claims.py | AI1 | на событии с inject_error ровно одно supported=false, на остальных ноль; максимум — в карточке | готово (в main) |
| AI3 | tests/redteam/*.yaml, reports/redteam.md | AI2 | 20+ сценариев red team зелёные в make check, сводка в reports/redteam.md | готово (в main) |
| V1 | radar/verify/provenance.py | контракт | independent и first_source совпадают с truth.yaml | готово (#1) |
| V2 | radar/verify/media.py | контракт | «наводнение» fail, пережатая и обрезанная копия находится | готово (#4) |
| V3 | radar/verify/weather.py | контракт | «снегопад» fail с понятным summary | готово (#5) |
| V4 | radar/verify/official.py, radar/verify/dossier.py | V1 | уровни досье совпадают с truth.yaml | готово (#2) |
| V5 | radar/verify/watchdog.py | V4, L4 | событие, опровергнутое после публикации, видно в /api/alerts (реэкспорт в `verify/__init__.py` добавит лид) | готово (в main) |
| L4 | radar/api/*, radar/core/*, frontend/src/types.ts, frontend/src/api.ts, frontend/src/mock/* | L3 | /api/events/{id}/publish, /api/alerts, /api/replay/stream отдают фикстуры, тест на форму | готово (в main) |
| UX1 | frontend/src/App.tsx, frontend/src/components/*, frontend/src/pages/* (кроме Live.tsx и Quality.tsx) | mock-JSON | демо-сценарий проходится кликами; максимум — в карточке | готово (в main) |
| UX2 | frontend/src/components/RepostGraph.tsx | UX1, V1 | у «слуха» видно один первоисточник | готово (в main) |
| UX3 | frontend/src/pages/Live.tsx | UX1, L4 | на видео видно, через сколько минут ДТП поднялось в ленте и как «наводнение» краснеет | готово (в main) |
| UX4 | frontend/src/pages/Quality.tsx | UX1, S2 | страница показывает метрики из /api/metrics после make eval | готово (в main) |

UX1 не трогает `frontend/src/components/RepostGraph.tsx` — это файл UX2.

## Некодовые задачи (ведутся в Google Doc)

| ID | Задача | Зависит |
|---|---|---|
| REL1 | Деплой на VPS за Caddy, сброс демо, /api/ready | L3 |
| REL2 | Релизные проверки: make check, make eval, чистый клон, протокол, тег на проверенном коммите | всё в main |
| P1 | Видео на 2–3 минуты по демо-сценарию | UX1, AI2 |
| P2 | Слайды (около 12) со скриншотами и замерами | UX1, S2 |
| P3 | Внешняя проверка: человек, не писавший код, поднимает проект по README | DOC2 |
| DOC1 | Текст заявки по 5 пунктам задания | S2 |
| DOC2 | README для жюри и docs/assumptions.md — готово (в main), ждёт P3 и скриншотов | UX1, S2 |

Подробные карточки и «максимум» каждой задачи — в Google Doc, раздел «Расширения задач».
Порядок: сначала база всех Must (AI1, AI2, UX1, S2, DOC1, DOC2, P1, P2, REL2), потом расширения.

Что режем, если не успеваем (по порядку): C4, UX4, S3, AI3, связка L4 + V5 + UX3,
«максимум» в AI1, AI2, UX1, S2, P3, UX2, REL1.

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
POST /api/events/{id}/publish  body {"outlet", "at"?} -> Publication            (L4)
GET  /api/alerts               -> [Alert] сторожа опровержений                  (V5)
GET  /api/replay/stream?until=ISO&outlet= -> {"start","end","until","events":[{"event","level","score","rose_at","minutes_to_signal"}]}
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
