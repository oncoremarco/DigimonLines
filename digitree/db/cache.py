import sqlite3
from pathlib import Path
from typing import Optional

from digitree.app_paths import WIKIMON_DB_PATH, ensure_data_dirs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS digimon (
    wikimon_key     TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    name_jp         TEXT,
    level           TEXT,
    attribute       TEXT,
    type            TEXT,
    elemental_attr  TEXT,
    fields          TEXT,
    profile_en      TEXT,
    profile_jp      TEXT,
    artwork_url     TEXT,
    artwork_local   TEXT,
    sprite_url      TEXT,
    sprite_local    TEXT,
    wikimon_url     TEXT,
    fetched_at      TEXT,
    fetch_status    TEXT
);

CREATE TABLE IF NOT EXISTS digimon_attacks (
    id              TEXT PRIMARY KEY,
    wikimon_key     TEXT NOT NULL REFERENCES digimon(wikimon_key),
    attack_type     TEXT,
    name_jp         TEXT,
    name_jp_romaji  TEXT,
    name_en         TEXT,
    description_en  TEXT,
    description_jp  TEXT,
    sort_order      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS digimon_images (
    id              TEXT PRIMARY KEY,
    wikimon_key     TEXT NOT NULL REFERENCES digimon(wikimon_key),
    image_type      TEXT,
    url             TEXT,
    local_path      TEXT,
    caption         TEXT
);
"""


class CacheDB:
    def __init__(self, path: Path = WIKIMON_DB_PATH):
        ensure_data_dirs()
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- Digimon -------------------------------------------------------

    def upsert_digimon(self, data: dict) -> None:
        cols = list(data.keys())
        placeholders = ", ".join("?" for _ in cols)
        update_set = ", ".join(
            f"{c}=excluded.{c}" for c in cols if c != "wikimon_key"
        )
        sql = (
            f"INSERT INTO digimon ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(wikimon_key) DO UPDATE SET {update_set}"
        )
        self._conn.execute(sql, list(data.values()))
        self._conn.commit()

    def get_digimon(self, wikimon_key: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM digimon WHERE wikimon_key = ?", (wikimon_key,)
        ).fetchone()
        return dict(row) if row else None

    # -- Attacks -------------------------------------------------------

    def upsert_attacks(self, wikimon_key: str, attacks: list[dict]) -> None:
        self._conn.execute(
            "DELETE FROM digimon_attacks WHERE wikimon_key = ?", (wikimon_key,)
        )
        for atk in attacks:
            cols = list(atk.keys())
            placeholders = ", ".join("?" for _ in cols)
            self._conn.execute(
                f"INSERT OR REPLACE INTO digimon_attacks "
                f"({', '.join(cols)}) VALUES ({placeholders})",
                list(atk.values()),
            )
        self._conn.commit()

    def get_attacks(self, wikimon_key: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM digimon_attacks WHERE wikimon_key = ? ORDER BY sort_order",
            (wikimon_key,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Images --------------------------------------------------------

    def upsert_image(self, data: dict) -> None:
        cols = list(data.keys())
        placeholders = ", ".join("?" for _ in cols)
        self._conn.execute(
            f"INSERT OR REPLACE INTO digimon_images "
            f"({', '.join(cols)}) VALUES ({placeholders})",
            list(data.values()),
        )
        self._conn.commit()

    def get_images(self, wikimon_key: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM digimon_images WHERE wikimon_key = ?", (wikimon_key,)
        ).fetchall()
        return [dict(r) for r in rows]
