# Замеры «Сигнала»

Данные: `data/synthetic_hard` (синтетика). Отчёт генерирует `make eval`, руками не править.

## Сводка

| Метрика | Значение |
|---|---|
| Постов в потоке | 1522 |
| Событий в ленте | 27 |
| Демо-событий найдено | 10 из 10 |
| Постов на событие (дубли схлопнуты) | 4.15 |
| Постов отсеяно как шум | 1410 |
| Полнота кластеров, среднее | 0.933 |
| Чистота кластеров, среднее | 0.95 |
| Минут до сигнала, медиана | 7.0 |
| Минут до сигнала, максимум | 17.0 |
| Точность уровня досье | 0.7 |
| Нужная проверка дала fail | 0.8 |
| Первоисточник найден верно | 0.9 |
| Число независимых источников верно | 0.8 |
| Вызовов LLM на 100 постов ленты | 0.0 |
| Вызовов LLM на один черновик | 1.0 |
| Сверка: ошибка поймана | 3/3 |
| Сверка: ложных тревог | 0 |

## Демо-события

| Событие | Уровень | Ожидали | Верно | Мин. до сигнала | Полнота | Чистота | Первоисточник | Источников |
|---|---|---|---|---|---|---|---|---|
| dtp_entry | green | green | да | 3.0 | 1.0 | 1.0 | да | 6 (да) |
| flood_old_photo | red | red | да | 4.0 | 1.0 | 1.0 | да | 1 (да) |
| plant_rumor | yellow | yellow | да | 17.0 | 1.0 | 1.0 | да | 1 (да) |
| mall_fire | red | red | да | 8.0 | 1.0 | 1.0 | да | 4 (да) |
| snowfall | green | red | НЕТ | 12.0 | 1.0 | 1.0 | да | 2 (да) |
| water_outage | green | green | да | 12.0 | 1.0 | 1.0 | да | 3 (да) |
| hard_copy_numbers | green | yellow | НЕТ | 6.0 | 1.0 | 0.75 | да | 3 (НЕТ) |
| hard_mirrored_photo | red | red | да | 5.0 | 0.667 | 1.0 | да | 1 (да) |
| hard_late_denial | red | red | да | 12.0 | 0.667 | 1.0 | да | 2 (да) |
| hard_official_other_event | green | yellow | НЕТ | 0.0 | 1.0 | 0.75 | НЕТ | 2 (НЕТ) |

## Сверка утверждений черновиков

Черновиков: 30, утверждений: 88. Событие с внедрённой ошибкой поймано в 3 из 3 черновиков, ложных тревог: 0.

| Событие | Издание | Утверждений | Не подтверждено |
|---|---|---|---|
| dtp_entry | mash | 3 | — |
| dtp_entry | life | 4 | — |
| dtp_entry | super | 3 | — |
| flood_old_photo | mash | 1 | — |
| flood_old_photo | life | 1 | — |
| flood_old_photo | super | 1 | — |
| plant_rumor | mash | 2 | — |
| plant_rumor | life | 2 | — |
| plant_rumor | super | 2 | — |
| mall_fire | mash | 3 | — |
| mall_fire | life | 5 | — |
| mall_fire | super | 3 | — |
| snowfall | mash | 2 | — |
| snowfall | life | 2 | — |
| snowfall | super | 2 | — |
| water_outage | mash | 10 | «15 домах» |
| water_outage | life | 11 | «15 домах» |
| water_outage | super | 10 | «15 домах» |
| hard_copy_numbers | mash | 3 | — |
| hard_copy_numbers | life | 3 | — |
| hard_copy_numbers | super | 3 | — |
| hard_mirrored_photo | mash | 1 | — |
| hard_mirrored_photo | life | 1 | — |
| hard_mirrored_photo | super | 1 | — |
| hard_late_denial | mash | 1 | — |
| hard_late_denial | life | 1 | — |
| hard_late_denial | super | 1 | — |
| hard_official_other_event | mash | 2 | — |
| hard_official_other_event | life | 2 | — |
| hard_official_other_event | super | 2 | — |

## Абляции: что перестаём ловить без проверки

| Без проверки | Точность уровня | Фейки, ставшие зелёными | Изменился уровень |
|---|---|---|---|
| первоисточник и независимые источники (V1) | 0.6 | plant_rumor, snowfall, hard_copy_numbers, hard_official_other_event | plant_rumor: yellow → green, snowfall: red → green, hard_copy_numbers: yellow → green, hard_official_other_event: yellow → green |
| фото по архиву (V2) | 0.5 | snowfall, hard_copy_numbers, hard_official_other_event | flood_old_photo: red → yellow, snowfall: red → green, hard_copy_numbers: yellow → green, hard_mirrored_photo: red → yellow, hard_official_other_event: yellow → green |
| погода на фото (V3) | 0.7 | snowfall, hard_copy_numbers, hard_official_other_event | snowfall: red → green, hard_copy_numbers: yellow → green, hard_official_other_event: yellow → green |
| официальные каналы (V4) | 0.5 | mall_fire, snowfall, hard_copy_numbers, hard_late_denial, hard_official_other_event | mall_fire: red → green, snowfall: red → green, hard_copy_numbers: yellow → green, hard_late_denial: red → green, hard_official_other_event: yellow → green |

## Скоринг: ручные веса и обученная модель (C4)

ROC AUC на отложенных 30% синтетических меток «опубликовано / нет» (`data/labels`). Ручные веса остаются по умолчанию.

| Издание | Ручные веса | Логистическая регрессия | Выученные веса |
|---|---|---|---|
| mash | 0.914 | 0.922 | topic 2.75, geo 0.4, reach 0.51, speed 3.2, media 3.28 |
| life | 0.917 | 0.907 | topic 3.13, geo 2.23, reach 3.84, speed 0.96, media 0.23 |
| super | 0.876 | 0.901 | topic 4.01, geo 2.23, reach 1.01, speed 0.34, media 1.86 |
