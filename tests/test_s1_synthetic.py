"""S1: the synthetic generator is deterministic and data/synthetic holds every demo event."""

import importlib.util
import itertools
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import imagehash
import numpy as np
import pytest
import yaml
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from radar.core.settings import ROOT
from radar.ingest import load_replay

SYNTHETIC = ROOT / "data" / "synthetic"
DEMO_KEYS = {"dtp_entry", "flood_old_photo", "plant_rumor", "mall_fire", "snowfall", "water_outage"}
START = datetime.fromisoformat("2026-10-27T00:00:00+03:00")
END = datetime.fromisoformat("2026-10-28T23:59:59+03:00")
# Lower-case stems of the demo places and objects; noise must not mention them.
DEMO_STEMS = ("северн", "въезд", "речн", "промзон", "завод", "центр", "галере", "лесн", "южн")
DEMO_STEMS += ("ключев",)
# Posts outside events that mention a demo place on purpose. Empty: no such posts.
NOISE_EXCEPTIONS: dict[str, str] = {}
IMAGE_SUFFIXES = {".png", ".jpg"}
# Same settings as V1 (provenance) and V4 (official link), D-03.
LINK_THRESHOLD = 0.12
RUMOR_WINDOW = (
    datetime.fromisoformat("2026-10-27T09:30:00+03:00"),
    datetime.fromisoformat("2026-10-28T11:30:00+03:00"),
)
# pHash as in V2: 144 bits over a grid of crops.
HASH_SIZE = 12
CROP_SCALES = (0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)
CROP_OFFSETS = (0.0, 0.25, 0.5, 0.75, 1.0)


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_synthetic", ROOT / "scripts/gen_synthetic.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up while building classes
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("synthetic") / "data"
    load_generator().generate(out)
    return out


@pytest.fixture(scope="module")
def truth() -> dict[str, dict]:
    data = yaml.safe_load((SYNTHETIC / "truth.yaml").read_text(encoding="utf-8"))
    return {item["key"]: item for item in data["events"]}


@pytest.fixture(scope="module")
def replay():
    return load_replay(SYNTHETIC)


def files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def similarity(texts: list[str]) -> np.ndarray:
    vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(texts)
    return cosine_similarity(vectors)


def crop_hashes(path: Path) -> list[imagehash.ImageHash]:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    hashes = []
    for scale in CROP_SCALES:
        w, h = round(width * scale), round(height * scale)
        for fx, fy in itertools.product(CROP_OFFSETS, CROP_OFFSETS):
            x, y = round((width - w) * fx), round((height - h) * fy)
            hashes.append(imagehash.phash(image.crop((x, y, x + w, y + h)), hash_size=HASH_SIZE))
    return hashes


def archive_distance(photo: str, archive_id: str) -> int:
    index = json.loads((SYNTHETIC / "archive" / "index.json").read_text(encoding="utf-8"))
    path = next(SYNTHETIC / "archive" / e["path"] for e in index if e["id"] == archive_id)
    photo_hash = imagehash.phash(Image.open(SYNTHETIC / "media" / photo).convert("RGB"), HASH_SIZE)
    return min(int(photo_hash - h) for h in crop_hashes(path))


def archive_ids() -> list[str]:
    index = json.loads((SYNTHETIC / "archive" / "index.json").read_text(encoding="utf-8"))
    return [entry["id"] for entry in index]


def test_two_runs_are_byte_identical(generated: Path, tmp_path: Path) -> None:
    load_generator().generate(tmp_path / "again")
    first, second = files(generated), files(tmp_path / "again")
    assert list(first) == list(second)
    for name, path in first.items():
        assert path.read_bytes() == second[name].read_bytes(), name


def test_committed_data_matches_generator(generated: Path) -> None:
    """Text files byte for byte; images by pixels, since Pillow is not pinned."""
    committed, fresh = files(SYNTHETIC), files(generated)
    assert list(committed) == list(fresh)
    for name, path in fresh.items():
        if path.suffix in IMAGE_SUFFIXES:
            a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
            b = np.asarray(Image.open(committed[name]).convert("RGB"), dtype=np.int16)
            assert a.shape == b.shape, name
            assert np.abs(a - b).mean() <= 2, name
        else:
            assert path.read_bytes() == committed[name].read_bytes(), name


def test_replay_size_and_span(replay) -> None:
    channels, posts = replay
    assert 35 <= len(channels) <= 45
    assert 400 <= len(posts) <= 600
    assert all("(синтетика)" in c.title and c.region == "demo-city" for c in channels)
    assert {c.kind for c in channels} == {"public", "official", "reader_bot", "outlet"}
    assert all(START <= p.ts <= END and p.ts.utcoffset() == timedelta(hours=3) for p in posts)
    assert max(p.ts for p in posts) - min(p.ts for p in posts) > timedelta(hours=40)
    assert [p.id for p in posts] == [f"p_{n:04d}" for n in range(1, len(posts) + 1)]
    assert all(
        p.url == f"https://example.invalid/{p.channel_id}/{p.url.rsplit('/', 1)[1]}" for p in posts
    )


def test_truth_integrity(replay, truth) -> None:
    _, posts = replay
    ids = {p.id for p in posts}
    assert set(truth) == DEMO_KEYS
    for key, item in truth.items():
        assert item["post_ids"] and set(item["post_ids"]) <= ids, key
        assert item["first_source"] in item["post_ids"], key
        assert item["expected_level"] in ("green", "yellow", "red"), key
    assert [k for k, item in truth.items() if item.get("inject_error")] == ["water_outage"]
    assert truth["dtp_entry"]["independent_sources"] == 6
    assert truth["plant_rumor"]["independent_sources"] == 1
    assert len(truth["plant_rumor"]["post_ids"]) == 15


def test_forwards_point_back_and_media_has_meta(replay) -> None:
    _, posts = replay
    by_id = {p.id: p for p in posts}
    for post in posts:
        if post.forward_from is not None:
            original = by_id[post.forward_from]
            assert original.ts < post.ts and original.id < post.id, post.id
    meta = json.loads((SYNTHETIC / "media" / "meta.json").read_text(encoding="utf-8"))
    on_disk = {p.name for p in (SYNTHETIC / "media").iterdir() if p.suffix in IMAGE_SUFFIXES}
    used = {file for post in posts for file in post.media}
    assert used == on_disk == set(meta)
    for record in json.loads((SYNTHETIC / "archive" / "index.json").read_text("utf-8")):
        assert (SYNTHETIC / "archive" / record["path"]).is_file()
        assert datetime.fromisoformat(record["published_at"]).tzinfo is not None


def test_media_posts_are_in_daylight(replay) -> None:
    """meta.json says daylight for every photo, so V3 must not warn on the hour."""
    _, posts = replay
    assert all(7 <= p.ts.hour < 19 for p in posts if p.media)


def test_dtp_sources_are_distinct_retellings(replay, truth) -> None:
    _, posts = replay
    item = truth["dtp_entry"]
    roots = [p for p in posts if p.id in item["post_ids"] and p.forward_from is None]
    assert len(roots) == 6
    assert len({p.channel_id for p in roots}) == 6
    sim = similarity([p.text for p in roots])
    for i, j in itertools.combinations(range(len(roots)), 2):
        assert sim[i, j] < 0.6, (roots[i].id, roots[j].id, sim[i, j])


def test_rumor_copies_are_near_identical(replay, truth) -> None:
    _, posts = replay
    item = truth["plant_rumor"]
    event = [p for p in posts if p.id in item["post_ids"]]
    first = item["first_source"]
    copies = [p for p in event if p.forward_from is None and p.id != first]
    assert copies and all(p.forward_from == first for p in event if p.forward_from)
    texts = [p.text for p in event]
    sim = similarity(texts)
    origin = next(i for i, p in enumerate(event) if p.id == first)
    for i, post in enumerate(event):
        if post in copies:
            assert sim[i, origin] >= 0.85, (post.id, sim[i, origin])


def test_flood_photo_is_an_archive_crop() -> None:
    assert archive_distance("flood.jpg", "arc_flood_2024") <= 16
    for archive_id in archive_ids():
        if archive_id != "arc_flood_2024":
            assert archive_distance("flood.jpg", archive_id) >= 30, archive_id


@pytest.mark.parametrize("photo", ["snow.jpg", "dtp.jpg"])
def test_fresh_photos_are_not_in_archive(photo: str) -> None:
    for archive_id in archive_ids():
        assert archive_distance(photo, archive_id) >= 30, archive_id


def test_noise_does_not_mention_demo_places(replay, truth) -> None:
    _, posts = replay
    in_events = {pid for item in truth.values() for pid in item["post_ids"]}
    for post in posts:
        if post.id in in_events or post.id in NOISE_EXCEPTIONS:
            continue
        lowered = post.text.lower()
        assert not any(stem in lowered for stem in DEMO_STEMS), (post.id, post.text)


def test_no_official_posts_in_rumor_window(replay) -> None:
    """V4 looks for official posts 2 h before and 24 h after the rumor; there are none."""
    channels, posts = replay
    official = {c.id for c in channels if c.kind == "official"}
    start, end = RUMOR_WINDOW
    assert not [p.id for p in posts if p.channel_id in official and start <= p.ts <= end]


def test_mchs_denial_is_linked_to_the_fire(replay, truth) -> None:
    """The denial is inside the event; as a fallback it also passes V4's text threshold."""
    channels, posts = replay
    official = {c.id for c in channels if c.kind == "official"}
    event = [p for p in posts if p.id in truth["mall_fire"]["post_ids"]]
    denials = [p for p in event if p.channel_id in official]
    assert len(denials) == 1
    assert "не соответствует действительности" in denials[0].text
    publics = [p for p in event if p.channel_id not in official]
    sim = similarity([p.text for p in publics] + [denials[0].text])
    assert sim[-1, :-1].max() >= LINK_THRESHOLD
