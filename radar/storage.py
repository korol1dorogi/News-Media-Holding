"""SQLite storage for pipeline results (task L3). Each row keeps a model as a JSON column."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from radar.core.models import Channel, Dossier, Event, Post, from_dict, to_dict

TABLES = ("channels", "posts", "events", "dossiers")
COLUMNS = "(id TEXT PRIMARY KEY, pos INTEGER NOT NULL, data TEXT NOT NULL)"


class Storage:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def replace_all(
        self,
        channels: list[Channel],
        posts: list[Post],
        events: list[Event],
        dossiers: list[Dossier],
    ) -> None:
        """Replace everything in one transaction."""
        rows: dict[str, list[tuple[str, Any]]] = {
            "channels": [(c.id, c) for c in channels],
            "posts": [(p.id, p) for p in posts],
            "events": [(e.id, e) for e in events],
            "dossiers": [(d.event_id, d) for d in dossiers],
        }
        with closing(self._connect()) as conn, conn:
            for table, items in rows.items():
                conn.execute(f"DELETE FROM {table}")
                conn.executemany(
                    f"INSERT INTO {table} (id, pos, data) VALUES (?, ?, ?)",
                    [
                        (key, pos, json.dumps(to_dict(obj), ensure_ascii=False))
                        for pos, (key, obj) in enumerate(items)
                    ],
                )

    def has_events(self) -> bool:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT 1 FROM events LIMIT 1").fetchone() is not None

    def channels(self) -> list[Channel]:
        return [from_dict(Channel, row) for row in self._rows("channels")]

    def posts(self, ids: list[str] | None = None) -> list[Post]:
        return [from_dict(Post, row) for row in self._rows("posts", ids)]

    def events(self) -> list[Event]:
        return [from_dict(Event, row) for row in self._rows("events")]

    def event(self, event_id: str) -> Event | None:
        rows = self._rows("events", [event_id])
        return from_dict(Event, rows[0]) if rows else None

    def dossier(self, event_id: str) -> Dossier | None:
        rows = self._rows("dossiers", [event_id])
        return from_dict(Dossier, rows[0]) if rows else None

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        for table in TABLES:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} {COLUMNS}")
        return conn

    def _rows(self, table: str, ids: list[str] | None = None) -> list[dict[str, Any]]:
        query = f"SELECT data FROM {table}"
        params: list[str] = []
        if ids is not None:
            marks = ",".join("?" * len(ids))
            query += f" WHERE id IN ({marks})"
            params = list(ids)
        with closing(self._connect()) as conn:
            cursor = conn.execute(query + " ORDER BY pos", params)
            return [json.loads(row[0]) for row in cursor]
