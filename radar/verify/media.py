"""Media match against the archive by pHash (task V2)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import imagehash
from PIL import Image, ImageOps

from radar.core.models import Check, Event, Post

# Archive frames are hashed over a grid of crops: a cropped and resized copy is close
# to one of them even when the whole-frame hashes differ a lot. The mirrored frame is hashed
# too: flipping an old photo is a common way to fool a plain pHash (found in S3).
CROP_SCALES = (0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)
CROP_OFFSETS = (0.0, 0.25, 0.5, 0.75, 1.0)
# 144-bit pHash: at 64 bits a real copy scores 6 and an unrelated frame 10, no threshold fits.
HASH_SIZE = 12
# Max Hamming distance between a post photo and the best archive crop.
MAX_DISTANCE = 22

NAME = "media_archive"


@dataclass(frozen=True)
class _Record:
    id: str
    published_at: datetime
    source: str
    hashes: tuple[imagehash.ImageHash, ...]


# (resolved archive_dir, index.json mtime_ns) -> records sorted by id.
_ARCHIVE_CACHE: dict[tuple[Path, int], list[_Record]] = {}


def media_archive(event: Event, posts: list[Post], archive_dir: Path) -> Check:
    """fail with a link to the archive record if the event's media appeared earlier."""
    wanted = set(event.post_ids)
    event_posts = sorted((p for p in posts if p.id in wanted), key=lambda p: (p.ts, p.id))
    first_post: dict[str, Post] = {}
    for post in event_posts:
        for file in post.media:
            first_post.setdefault(file, post)
    if not first_post:
        return _check("n/a", "В событии нет фото, сверять нечего.", [])

    records = _load_archive(Path(archive_dir))
    if isinstance(records, str):
        return _check("n/a", records, [])

    media_dir = Path(archive_dir).parent / "media"
    checked: list[str] = []
    matches: list[tuple[str, _Record, int]] = []
    for file in sorted(first_post):
        photo_hash = _phash(media_dir / file)
        if photo_hash is None:
            continue
        checked.append(file)
        earlier = [r for r in records if _before(r.published_at, first_post[file].ts)]
        found = _nearest(photo_hash, earlier)
        if found is not None and found[1] <= MAX_DISTANCE:
            matches.append((file, *found))

    if not checked:
        return _check("n/a", "Ни одно фото события не удалось открыть, сверка невозможна.", [])

    if matches:
        file, record, _ = matches[0]
        summary = (
            f"Фото уже публиковалось {record.published_at:%d.%m.%Y} "
            f"({record.source}) — это старый кадр."
        )
        evidence: list[dict] = []
        for file, record, distance in matches:
            evidence.append(
                {"archive_id": record.id, "note": f"совпадение pHash, расстояние {distance}"}
            )
            evidence.append({"post_id": first_post[file].id, "note": f"фото {file}"})
        return _check("fail", summary, evidence)

    first_with_photo = min((first_post[f] for f in checked), key=lambda p: (p.ts, p.id))
    return _check(
        "ok",
        "Фото не найдено в архиве, похоже на новое.",
        [{"post_id": first_with_photo.id, "note": f"{len(checked)} фото проверено"}],
    )


def _before(a: datetime, b: datetime) -> bool:
    # Naive and aware datetimes can't be compared; take the naive one in the other's zone.
    if a.tzinfo is None and b.tzinfo is not None:
        a = a.replace(tzinfo=b.tzinfo)
    elif b.tzinfo is None and a.tzinfo is not None:
        b = b.replace(tzinfo=a.tzinfo)
    return a < b


def _check(status: str, summary: str, evidence: list[dict]) -> Check:
    return Check(name=NAME, status=status, summary=summary, evidence=evidence)


def _load_archive(archive_dir: Path) -> list[_Record] | str:
    """Archive records with crop hashes, or a reason why the archive is unavailable."""
    index = archive_dir / "index.json"
    if not index.is_file():
        return "Архив медиа не найден, сверить фото не с чем."
    key = (archive_dir.resolve(), index.stat().st_mtime_ns)
    if key in _ARCHIVE_CACHE:
        return _ARCHIVE_CACHE[key]
    try:
        entries = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Индекс архива медиа не читается, сверка невозможна."
    if not isinstance(entries, list):
        return "Индекс архива медиа не читается, сверка невозможна."

    records = []
    for entry in entries:
        try:
            published_at = datetime.fromisoformat(entry["published_at"])
            image = _open(archive_dir / entry["path"])
            record_id, source = str(entry["id"]), str(entry["source"])
        except (KeyError, TypeError, ValueError):
            continue
        if image is None:
            continue
        records.append(_Record(record_id, published_at, source, _crop_hashes(image)))
    records.sort(key=lambda r: r.id)
    if not records:
        return "В архиве медиа нет ни одной читаемой записи, сверка невозможна."
    _ARCHIVE_CACHE[key] = records
    return records


def _crop_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    boxes = set()
    for scale in CROP_SCALES:
        w, h = round(width * scale), round(height * scale)
        for fx in CROP_OFFSETS:
            for fy in CROP_OFFSETS:
                x, y = round((width - w) * fx), round((height - h) * fy)
                boxes.add((x, y, x + w, y + h))
    return sorted(boxes)


def _crop_hashes(image: Image.Image) -> tuple[imagehash.ImageHash, ...]:
    boxes = _crop_boxes(*image.size)
    return tuple(
        imagehash.phash(frame.crop(box), hash_size=HASH_SIZE)
        for frame in (image, ImageOps.mirror(image))
        for box in boxes
    )


def _open(path: Path) -> Image.Image | None:
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def _phash(path: Path) -> imagehash.ImageHash | None:
    image = _open(path)
    return None if image is None else imagehash.phash(image, hash_size=HASH_SIZE)


def _nearest(photo_hash: imagehash.ImageHash, records: list[_Record]) -> tuple[_Record, int] | None:
    """Closest record by the best crop; ties go to the smaller id (records are sorted)."""
    best: tuple[_Record, int] | None = None
    for record in records:
        distance = min(int(photo_hash - h) for h in record.hashes)
        if best is None or distance < best[1]:
            best = (record, distance)
    return best
