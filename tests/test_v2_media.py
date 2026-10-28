"""V2: event media against the archive by pHash."""

import io
import json
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import imagehash
import pytest
from PIL import Image, ImageDraw

from radar.core.models import Event, Post
from radar.core.settings import ROOT
from radar.ingest import load_replay
from radar.verify import media_archive
from radar.verify.media import _ARCHIVE_CACHE, HASH_SIZE, MAX_DISTANCE, _crop_hashes

TS = datetime.fromisoformat("2026-10-27T10:00:00+03:00")
SYNTHETIC = ROOT / "data" / "synthetic"


def archive_frame() -> Image.Image:
    """Street-like frame: sky gradient, houses, a road and a lamp post."""
    img = Image.new("RGB", (320, 240))
    draw = ImageDraw.Draw(img)
    for y in range(240):
        draw.line([(0, y), (319, y)], fill=(40 + y // 3, 90 + y // 4, 200 - y // 2))
    draw.rectangle([20, 70, 110, 200], fill=(150, 70, 50))
    draw.rectangle([130, 40, 200, 200], fill=(210, 200, 170))
    draw.polygon([(215, 200), (265, 90), (315, 200)], fill=(60, 120, 60))
    draw.rectangle([0, 200, 319, 239], fill=(70, 70, 80))
    for x in (40, 75, 150, 175):
        draw.rectangle([x, 100, x + 15, 120], fill=(250, 230, 120))
    draw.line([(118, 60), (118, 210)], fill=(20, 20, 20), width=4)
    draw.ellipse([250, 20, 290, 60], fill=(250, 250, 220))
    return img


def other_circles() -> Image.Image:
    img = Image.new("RGB", (320, 240), (240, 240, 235))
    draw = ImageDraw.Draw(img)
    for i, color in enumerate([(200, 30, 30), (30, 160, 60), (40, 60, 200), (220, 180, 20)]):
        draw.ellipse([20 + i * 70, 40 + (i % 2) * 90, 90 + i * 70, 110 + (i % 2) * 90], fill=color)
    return img


def other_stripes() -> Image.Image:
    img = Image.new("RGB", (320, 240))
    draw = ImageDraw.Draw(img)
    for i in range(8):
        shade = (i * 30, 255 - i * 30, 128)
        draw.polygon(
            [(i * 40, 0), (i * 40 + 40, 0), (i * 40 - 60, 240), (i * 40 - 100, 240)], shade
        )
    return img


def other_noise() -> Image.Image:
    """Dark night scene: a big bright window block on the left and random dots."""
    rng = random.Random(7)
    img = Image.new("RGB", (320, 240), (15, 15, 35))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 30, 140, 230], fill=(230, 220, 160))
    for _ in range(300):
        x, y = rng.randrange(150, 320), rng.randrange(0, 240)
        draw.point((x, y), fill=(255, 255, 255))
    return img


def jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return Image.open(io.BytesIO(buf.getvalue()))


def crop80(img: Image.Image) -> Image.Image:
    w, h = img.size
    return img.crop((round(w * 0.2), round(h * 0.05), w, round(h * 0.85)))


def half(img: Image.Image) -> Image.Image:
    return img.resize((img.width // 2, img.height // 2))


COPIES = {
    "jpeg_q30": lambda img: jpeg(img, 30),
    "crop80_shifted": crop80,
    "half_size": half,
    "all_together": lambda img: jpeg(half(crop80(img)), 30),
}
OTHERS = {"circles": other_circles, "stripes": other_stripes, "night": other_noise}


def make_post(post_id: str, minutes: float, media: list[str]) -> Post:
    return Post(
        id=post_id,
        channel_id="ch_public",
        ts=TS + timedelta(minutes=minutes),
        text="Наводнение на Речной улице",
        url=f"https://example.invalid/{post_id}",
        media=media,
        forward_from=None,
    )


def make_event(post_ids: list[str]) -> Event:
    return Event(
        id="e_test",
        post_ids=post_ids,
        first_ts=TS,
        title="Наводнение",
        geo=None,
        topic=None,
        scores={},
    )


def make_data(tmp_path: Path, photo: Image.Image, published_at: str = "2024-10-20T09:00:00+03:00"):
    """data_dir with one archive record (archive_frame) and one post photo; returns archive dir."""
    archive = tmp_path / "archive"
    media = tmp_path / "media"
    archive.mkdir()
    media.mkdir()
    archive_frame().save(archive / "frame.png")
    index = [{"id": "arc_1", "path": "frame.png", "published_at": published_at, "source": "Архив"}]
    (archive / "index.json").write_text(json.dumps(index), encoding="utf-8")
    photo.convert("RGB").save(media / "photo.jpg", "JPEG", quality=90)
    return archive


def ids(check, key: str) -> list[str]:
    return [item[key] for item in check.evidence if key in item]


@pytest.mark.parametrize("data_dir", [ROOT / "tests" / "fixtures" / "mini", SYNTHETIC])
def test_flood_is_old_photo(data_dir: Path):
    _, posts = load_replay(data_dir)
    check = media_archive(make_event(["m_004", "m_005", "m_006"]), posts, data_dir / "archive")
    assert check.name == "media_archive"
    assert check.status == "fail"
    assert ids(check, "archive_id") == ["arc_flood_2024"]
    assert ids(check, "post_id") == ["m_004"]
    assert "20.10.2024" in check.summary


@pytest.mark.parametrize("data_dir", [ROOT / "tests" / "fixtures" / "mini", SYNTHETIC])
def test_event_without_photos_is_na(data_dir: Path):
    _, posts = load_replay(data_dir)
    check = media_archive(make_event(["m_001", "m_002", "m_003"]), posts, data_dir / "archive")
    assert check.status == "n/a"
    assert check.summary == "В событии нет фото, сверять нечего."


@pytest.mark.parametrize("name", sorted(COPIES))
def test_modified_copy_is_found(tmp_path: Path, name: str):
    archive = make_data(tmp_path, COPIES[name](archive_frame()))
    check = media_archive(make_event(["p_1"]), [make_post("p_1", 0, ["photo.jpg"])], archive)
    assert check.status == "fail"
    assert ids(check, "archive_id") == ["arc_1"]
    assert ids(check, "post_id") == ["p_1"]


@pytest.mark.parametrize("name", sorted(OTHERS))
def test_unrelated_photo_is_ok(tmp_path: Path, name: str):
    archive = make_data(tmp_path, OTHERS[name]())
    check = media_archive(make_event(["p_1"]), [make_post("p_1", 0, ["photo.jpg"])], archive)
    assert check.status == "ok"
    assert check.evidence == [{"post_id": "p_1", "note": "1 фото проверено"}]


@pytest.mark.parametrize("name", sorted(OTHERS))
def test_unrelated_photo_keeps_margin(name: str):
    # The best crop of the archive frame must stay well away from the threshold.
    photo_hash = imagehash.phash(OTHERS[name](), hash_size=HASH_SIZE)
    flood = Image.open(SYNTHETIC / "archive" / "flood_2024.png").convert("RGB")
    for archive in (archive_frame(), flood):
        distance = min(int(photo_hash - h) for h in _crop_hashes(archive))
        assert distance >= MAX_DISTANCE + 4


def test_similar_layout_is_not_old_photo(tmp_path: Path):
    # Regression: at 64 bits this frame (sky, houses, dark band, moon) matched flood_2024.
    shutil.copytree(SYNTHETIC / "archive", tmp_path / "archive")
    (tmp_path / "media").mkdir()
    archive_frame().save(tmp_path / "media" / "street.jpg", "JPEG", quality=90)
    post = make_post("p_1", 0, ["street.jpg"])
    check = media_archive(make_event(["p_1"]), [post], tmp_path / "archive")
    assert check.status == "ok"


def test_archive_record_after_post_is_not_fail(tmp_path: Path):
    archive = make_data(
        tmp_path, jpeg(archive_frame(), 30), published_at="2026-10-28T09:00:00+03:00"
    )
    check = media_archive(make_event(["p_1"]), [make_post("p_1", 0, ["photo.jpg"])], archive)
    assert check.status == "ok"


@pytest.mark.parametrize(
    ("published_at", "status"), [("2024-10-20T09:00:00", "fail"), ("2026-10-27T10:30:00", "ok")]
)
def test_archive_date_without_timezone(tmp_path: Path, published_at: str, status: str):
    archive = make_data(tmp_path, jpeg(archive_frame(), 30), published_at=published_at)
    check = media_archive(make_event(["p_1"]), [make_post("p_1", 0, ["photo.jpg"])], archive)
    assert check.status == status


@pytest.mark.parametrize(
    ("published_at", "status"),
    [("2026-10-27T09:30:00+03:00", "fail"), ("2026-10-27T10:30:00+03:00", "ok")],
)
def test_post_date_without_timezone(tmp_path: Path, published_at: str, status: str):
    archive = make_data(tmp_path, jpeg(archive_frame(), 30), published_at=published_at)
    post = make_post("p_1", 0, ["photo.jpg"])
    post.ts = post.ts.replace(tzinfo=None)
    check = media_archive(make_event(["p_1"]), [post], archive)
    assert check.status == status


def test_missing_archive_is_na(tmp_path: Path):
    (tmp_path / "media").mkdir()
    archive_frame().save(tmp_path / "media" / "photo.jpg")
    post = make_post("p_1", 0, ["photo.jpg"])
    check = media_archive(make_event(["p_1"]), [post], tmp_path / "archive")
    assert check.status == "n/a"
    assert "Архив" in check.summary


def test_broken_or_missing_media_is_na(tmp_path: Path):
    archive = make_data(tmp_path, archive_frame())
    (tmp_path / "media" / "broken.jpg").write_bytes(b"not an image")
    posts = [make_post("p_1", 0, ["broken.jpg"]), make_post("p_2", 5, ["absent.jpg"])]
    check = media_archive(make_event(["p_1", "p_2"]), posts, archive)
    assert check.status == "n/a"
    assert "не удалось открыть" in check.summary
    assert check.evidence == []


def test_broken_file_is_skipped_when_others_are_checked(tmp_path: Path):
    archive = make_data(tmp_path, other_circles())
    (tmp_path / "media" / "broken.jpg").write_bytes(b"not an image")
    posts = [make_post("p_1", 0, ["broken.jpg", "photo.jpg"])]
    check = media_archive(make_event(["p_1"]), posts, archive)
    assert check.status == "ok"
    assert check.evidence == [{"post_id": "p_1", "note": "1 фото проверено"}]


def test_every_match_goes_to_evidence(tmp_path: Path):
    archive = make_data(tmp_path, half(archive_frame()))
    jpeg(archive_frame(), 30).save(tmp_path / "media" / "another.jpg")
    posts = [
        make_post("p_1", 0, ["photo.jpg"]),
        make_post("p_2", 3, ["photo.jpg", "another.jpg"]),
        make_post("p_3", 9, ["another.jpg"]),
    ]
    check = media_archive(make_event(["p_1", "p_2", "p_3"]), posts, archive)
    assert check.status == "fail"
    # Files go by name: another.jpg (first seen in p_2), then photo.jpg (first seen in p_1).
    assert ids(check, "archive_id") == ["arc_1", "arc_1"]
    assert ids(check, "post_id") == ["p_2", "p_1"]


def test_order_of_posts_does_not_matter():
    _, posts = load_replay(SYNTHETIC)
    post_ids = ["m_004", "m_005", "m_006"]
    expected = media_archive(make_event(post_ids), posts, SYNTHETIC / "archive")
    rng = random.Random(42)
    for _ in range(5):
        shuffled_posts, shuffled_ids = posts[:], post_ids[:]
        rng.shuffle(shuffled_posts)
        rng.shuffle(shuffled_ids)
        assert (
            media_archive(make_event(shuffled_ids), shuffled_posts, SYNTHETIC / "archive")
            == expected
        )


def test_cached_archive_gives_same_check(tmp_path: Path):
    archive = make_data(tmp_path, crop80(archive_frame()))
    event, posts = make_event(["p_1"]), [make_post("p_1", 0, ["photo.jpg"])]
    _ARCHIVE_CACHE.clear()
    first = media_archive(event, posts, archive)
    second = media_archive(event, posts, archive)
    assert first == second
    assert first.status == "fail"
