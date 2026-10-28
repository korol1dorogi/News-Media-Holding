"""AI2: claims of a draft are checked against the event's posts."""

from datetime import datetime

import pytest
import yaml

from radar.cluster import build_events
from radar.core.models import Draft, Post
from radar.core.settings import ROOT
from radar.draft import check_claims, generate
from radar.draft.claims import OFFICIAL_WARNING, extract
from radar.ingest import load_replay
from radar.llm import MockProvider
from radar.normalize import enrich

SYNTHETIC = ROOT / "data" / "synthetic"
TRUTH = SYNTHETIC / "truth.yaml"
TS = datetime.fromisoformat("2026-10-27T08:12:00+03:00")


def post(post_id: str, text: str) -> Post:
    return Post(
        id=post_id,
        channel_id="ch",
        ts=TS,
        text=text,
        url="https://example.invalid/1",
        media=[],
        forward_from=None,
    )


def draft(text: str) -> Draft:
    return Draft(event_id="ev", outlet="mash", text=text, claims=[], warnings=[])


@pytest.fixture(scope="module")
def checked() -> dict[str, list[Draft]]:
    """truth key -> checked drafts for mash, life and super."""
    _, posts = load_replay(SYNTHETIC)
    posts = [enrich(p) for p in posts]
    by_id = {p.id: p for p in posts}
    events = build_events(posts)
    truth = yaml.safe_load(TRUTH.read_text(encoding="utf-8"))["events"]
    llm = MockProvider(truth_path=TRUTH)
    result = {}
    for item in truth:
        event = max(events, key=lambda e: len(set(e.post_ids) & set(item["post_ids"])))
        own = [by_id[i] for i in event.post_ids]
        result[item["key"]] = [
            check_claims(generate(event, own, outlet, llm), own)
            for outlet in ("mash", "life", "super")
        ]
    return result


def test_inject_error_event_has_exactly_one_unsupported_claim(checked) -> None:
    for d in checked["water_outage"]:
        unsupported = [c for c in d.claims if not c.supported]
        assert len(unsupported) == 1, d.outlet
        assert unsupported[0].kind == "number"
        assert unsupported[0].source_post_ids == []
        assert any(unsupported[0].text in w for w in d.warnings)


def test_other_demo_events_have_no_false_alarms(checked) -> None:
    for key, drafts in checked.items():
        if key == "water_outage":
            continue
        for d in drafts:
            assert all(c.supported for c in d.claims), (key, d.outlet)
            assert d.warnings == [], (key, d.outlet)


def test_supported_claims_link_to_posts(checked) -> None:
    for drafts in checked.values():
        for d in drafts:
            for c in d.claims:
                assert c.supported == bool(c.source_post_ids)


def test_number_words_match_digits() -> None:
    result = check_claims(draft("Пострадали три человека."), [post("p1", "трое пострадавших")])
    assert [(c.kind, c.supported) for c in result.claims] == [("number", True)]
    result = check_claims(draft("Пострадали 3 человека."), [post("p1", "троих увезли")])
    assert result.claims[0].supported


def test_wrong_number_is_flagged() -> None:
    result = check_claims(draft("Пострадали 5 человек."), [post("p1", "трое пострадавших")])
    assert not result.claims[0].supported
    assert result.claims[0].text == "5 человек"
    assert result.warnings == ["Не подтверждено источниками: «5 человек»."]


def test_times_and_dates_hide_their_digits() -> None:
    found = extract("27 октября с 9:00 до 18:00, отчёт 28.10")
    assert [(f.kind, f.key) for f in found] == [
        ("date", (27, 10)),
        ("time", (9, 0)),
        ("time", (18, 0)),
        ("date", (28, 10)),
    ]


def test_time_and_date_are_checked() -> None:
    source = post("p1", "Воды не будет 27 октября с 09:00 до 18:00.")
    ok = check_claims(draft("27 октября воду отключат с 9:00 до 18:00."), [source])
    assert all(c.supported for c in ok.claims)
    bad = check_claims(draft("Воду отключат 29 октября до 20:00."), [source])
    assert [c.supported for c in bad.claims] == [False, False]


def test_date_of_the_post_supports_the_draft() -> None:
    result = check_claims(draft("Авария произошла 27.10."), [post("p1", "Авария на въезде")])
    assert result.claims[0].supported


def test_places_by_city_dictionary() -> None:
    sources = [post("p1", "Пробка на северном въезде")]
    ok = check_claims(draft("Авария на Северном въезде."), sources)
    assert [(c.kind, c.supported) for c in ok.claims] == [("place", True)]
    bad = check_claims(draft("Авария на Садовой улице."), sources)
    assert [(c.kind, c.supported) for c in bad.claims] == [("place", False)]


def test_quoted_names_and_acronyms() -> None:
    sources = [post("p1", "Горит ТЦ «Галерея», работает МЧС.")]
    result = check_claims(draft("Пожар в «Галерее», на месте МЧС и ГИБДД."), sources)
    assert [(c.text, c.supported) for c in result.claims] == [
        ("«Галерее»", True),
        ("МЧС", True),
        ("ГИБДД", False),
    ]


def test_official_claim_without_official_source_is_warned() -> None:
    sources = [post("p1", "Говорят, завод закрывают.")]
    result = check_claims(draft("Закрытие завода официально подтверждено."), sources)
    assert OFFICIAL_WARNING in result.warnings
    confirmed = [post("p2", "В администрации подтвердили закрытие завода.")]
    assert (
        OFFICIAL_WARNING not in check_claims(draft("Официально подтверждено."), confirmed).warnings
    )


def test_existing_warnings_are_kept() -> None:
    source = [post("p1", "Текст без чисел")]
    result = check_claims(
        Draft("ev", "life", "Пять машин.", claims=[], warnings=["из AI1"]), source
    )
    assert result.warnings[0] == "из AI1"
    assert len(result.warnings) == 2
