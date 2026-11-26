"""Local SQLite database of Digimon imported from Wikimon.

This module is pure Python (no Qt) so it can be used from the importer's
background thread, the command line, and tests.

Schema versions are tracked with ``PRAGMA user_version`` so that databases
created by older builds are upgraded in place.
"""

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from digitree.app_paths import WIKIMON_DB_PATH, ensure_data_dirs

SCHEMA_VERSION = 2

# Version 1: the original tables from Phase 1 of the old plan.
_SCHEMA_V1 = """
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

# Version 2: everything the Wikimon importer needs.
_SCHEMA_V2 = """
-- One row per (Digimon, trait, value). Digimon can have several Levels,
-- Types, Attributes and Fields, so this is what the search filters use.
CREATE TABLE IF NOT EXISTS digimon_traits (
    wikimon_key TEXT NOT NULL REFERENCES digimon(wikimon_key) ON DELETE CASCADE,
    trait       TEXT NOT NULL,          -- 'level' | 'type' | 'attribute' | 'field'
    value       TEXT NOT NULL,
    PRIMARY KEY (wikimon_key, trait, value)
);
CREATE INDEX IF NOT EXISTS idx_traits_lookup ON digimon_traits(trait, value);

-- Evolves From / Evolves To, stored as directed edges from -> to.
-- source_key is the page the edge was read from, so re-importing a page
-- replaces only the edges that page contributed.
CREATE TABLE IF NOT EXISTS digimon_evolutions (
    source_key  TEXT NOT NULL,
    from_key    TEXT NOT NULL,
    to_key      TEXT NOT NULL,
    listed_as   TEXT NOT NULL,          -- 'from' or 'to' (which list it came from)
    note        TEXT,
    sort_order  INTEGER DEFAULT 0,
    PRIMARY KEY (source_key, from_key, to_key)
);
CREATE INDEX IF NOT EXISTS idx_evo_from ON digimon_evolutions(from_key);
CREATE INDEX IF NOT EXISTS idx_evo_to   ON digimon_evolutions(to_key);

-- Wikimon redirects (e.g. "Metal Greymon" -> "MetalGreymon") so evolution
-- links written with an alternate name still resolve.
CREATE TABLE IF NOT EXISTS digimon_redirects (
    alias       TEXT PRIMARY KEY,
    target      TEXT NOT NULL
);

-- Raw page text, kept so the parser can be improved and re-run offline
-- without downloading anything again.
CREATE TABLE IF NOT EXISTS wikimon_pages (
    title       TEXT PRIMARY KEY,
    rev_id      INTEGER,
    wikitext    TEXT,
    fetched_at  TEXT
);

-- Work queue that makes the import resumable.
CREATE TABLE IF NOT EXISTS import_queue (
    title       TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | done | skipped | error
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_queue_status ON import_queue(status);

CREATE TABLE IF NOT EXISTS import_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT
);
"""

TRAITS = ("level", "type", "attribute", "field")


class CacheDB:
    def __init__(self, path: Path = WIKIMON_DB_PATH):
        if path == WIKIMON_DB_PATH:
            ensure_data_dirs()
        self.path = Path(path)
        # Short-lived worker threads open their own CacheDB, so the default
        # same-thread check is fine and catches accidental sharing.
        self._conn = sqlite3.connect(str(path), timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self._conn.executescript(_SCHEMA_V1)
        if version < 2:
            self._conn.executescript(_SCHEMA_V2)
            existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(digimon)")}
            for col, decl in (("rev_id", "INTEGER"), ("dub_name", "TEXT")):
                if col not in existing:
                    self._conn.execute(f"ALTER TABLE digimon ADD COLUMN {col} {decl}")
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    # -- Digimon -------------------------------------------------------

    def upsert_digimon(self, data: dict, commit: bool = True) -> None:
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
        if commit:
            self._conn.commit()

    def get_digimon(self, wikimon_key: str) -> Optional[dict]:
        key = self.resolve_key(wikimon_key)
        row = self._conn.execute(
            "SELECT * FROM digimon WHERE wikimon_key = ?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def count_digimon(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM digimon").fetchone()[0]

    # -- Traits (Level / Type / Attribute / Field) ---------------------

    def set_traits(self, wikimon_key: str, traits: dict[str, Iterable[str]],
                   commit: bool = True) -> None:
        self._conn.execute("DELETE FROM digimon_traits WHERE wikimon_key = ?", (wikimon_key,))
        for trait, values in traits.items():
            for v in values:
                self._conn.execute(
                    "INSERT OR IGNORE INTO digimon_traits VALUES (?, ?, ?)",
                    (wikimon_key, trait, v),
                )
        if commit:
            self._conn.commit()

    def get_traits(self, wikimon_key: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {t: [] for t in TRAITS}
        for r in self._conn.execute(
            "SELECT trait, value FROM digimon_traits WHERE wikimon_key = ? ORDER BY rowid",
            (self.resolve_key(wikimon_key),),
        ):
            out.setdefault(r["trait"], []).append(r["value"])
        return out

    def distinct_values(self, trait: str) -> list[str]:
        """All known values of a trait, e.g. every Field, for filter dropdowns."""
        rows = self._conn.execute(
            "SELECT value, COUNT(*) AS n FROM digimon_traits WHERE trait = ? "
            "GROUP BY value ORDER BY value COLLATE NOCASE",
            (trait,),
        ).fetchall()
        return [r["value"] for r in rows]

    # -- Attacks -------------------------------------------------------

    def upsert_attacks(self, wikimon_key: str, attacks: list[dict],
                       commit: bool = True) -> None:
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
        if commit:
            self._conn.commit()

    def get_attacks(self, wikimon_key: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM digimon_attacks WHERE wikimon_key = ? ORDER BY sort_order",
            (self.resolve_key(wikimon_key),),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Evolutions ----------------------------------------------------

    def set_evolutions(self, source_key: str, evolves_from: list[tuple[str, str]],
                       evolves_to: list[tuple[str, str]], commit: bool = True) -> None:
        """Replace the edges contributed by one page.

        ``evolves_from`` / ``evolves_to`` are lists of (other_key, note).
        """
        self._conn.execute("DELETE FROM digimon_evolutions WHERE source_key = ?", (source_key,))
        rows = []
        for i, (other, note) in enumerate(evolves_from):
            rows.append((source_key, other, source_key, "from", note, i))
        for i, (other, note) in enumerate(evolves_to):
            rows.append((source_key, source_key, other, "to", note, i))
        self._conn.executemany(
            "INSERT OR IGNORE INTO digimon_evolutions VALUES (?, ?, ?, ?, ?, ?)", rows
        )
        if commit:
            self._conn.commit()

    def _evo_query(self, key: str, direction: str) -> list[dict]:
        # Wikimon lists are authoritative per page: "Evolves From" on X's page
        # says who X comes from. We also use the reverse lists of other pages
        # so a link mentioned only on one side still shows up.
        key = self.resolve_key(key)
        if direction == "from":
            sql = """
                SELECT COALESCE(r.target, e.from_key) AS key, e.note, e.listed_as, e.source_key, e.sort_order
                FROM digimon_evolutions e
                LEFT JOIN digimon_redirects r ON r.alias = e.from_key
                LEFT JOIN digimon_redirects r2 ON r2.alias = e.to_key
                WHERE COALESCE(r2.target, e.to_key) = ?
            """
        else:
            sql = """
                SELECT COALESCE(r.target, e.to_key) AS key, e.note, e.listed_as, e.source_key, e.sort_order
                FROM digimon_evolutions e
                LEFT JOIN digimon_redirects r ON r.alias = e.to_key
                LEFT JOIN digimon_redirects r2 ON r2.alias = e.from_key
                WHERE COALESCE(r2.target, e.from_key) = ?
            """
        seen: dict[str, dict] = {}
        rows = self._conn.execute(sql, (key,)).fetchall()
        # Prefer the entry from this Digimon's own page (keeps its order/notes).
        rows = sorted(rows, key=lambda r: (r["source_key"] != key, r["sort_order"]))
        for r in rows:
            if r["key"] not in seen:
                seen[r["key"]] = {"key": r["key"], "note": r["note"]}
        return list(seen.values())

    def get_evolves_from(self, wikimon_key: str) -> list[dict]:
        return self._evo_query(wikimon_key, "from")

    def get_evolves_to(self, wikimon_key: str) -> list[dict]:
        return self._evo_query(wikimon_key, "to")

    # -- Redirects -----------------------------------------------------

    def add_redirects(self, mapping: dict[str, str], commit: bool = True) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO digimon_redirects VALUES (?, ?)",
            [(a, t) for a, t in mapping.items() if a != t],
        )
        if commit:
            self._conn.commit()

    def resolve_key(self, key: str) -> str:
        row = self._conn.execute(
            "SELECT target FROM digimon_redirects WHERE alias = ?", (key,)
        ).fetchone()
        return row["target"] if row else key

    def unresolved_evolution_keys(self) -> list[str]:
        """Evolution targets that aren't an imported Digimon or a known redirect."""
        rows = self._conn.execute("""
            SELECT DISTINCT k FROM (
                SELECT from_key AS k FROM digimon_evolutions
                UNION SELECT to_key FROM digimon_evolutions
            )
            WHERE k NOT IN (SELECT wikimon_key FROM digimon)
              AND k NOT IN (SELECT alias FROM digimon_redirects)
        """).fetchall()
        return [r["k"] for r in rows]

    # -- Search --------------------------------------------------------

    def search(self, name: str = "", *, level: str | None = None,
               attribute: str | None = None, type: str | None = None,
               field: str | None = None, evolves_from: str | None = None,
               limit: int = 500) -> list[dict]:
        """Find Digimon by name and/or trait filters.

        Each filter is an exact (case-insensitive) match against any of the
        Digimon's values for that trait, so a Digimon with Fields
        "Metal Empire" and "Dark Area" matches either one.
        ``evolves_from`` keeps only Digimon that canonically evolve from it.
        """
        where = []
        params: list = []
        if name:
            where.append("(d.display_name LIKE ? OR d.wikimon_key LIKE ? OR d.dub_name LIKE ?)")
            like = f"%{name}%"
            params += [like, like, like]
        for trait, value in (("level", level), ("attribute", attribute),
                             ("type", type), ("field", field)):
            if value:
                where.append(
                    "EXISTS (SELECT 1 FROM digimon_traits t WHERE t.wikimon_key = d.wikimon_key "
                    "AND t.trait = ? AND t.value = ? COLLATE NOCASE)"
                )
                params += [trait, value]
        sql = "SELECT d.* FROM digimon d"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY d.display_name COLLATE NOCASE LIMIT ?"
        params.append(limit)
        rows = [dict(r) for r in self._conn.execute(sql, params)]
        if evolves_from:
            allowed = {e["key"] for e in self.get_evolves_to(evolves_from)}
            rows = [r for r in rows if r["wikimon_key"] in allowed]
        return rows

    # -- Raw pages -----------------------------------------------------

    def save_page(self, title: str, rev_id: int | None, wikitext: str,
                  fetched_at: str, commit: bool = True) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO wikimon_pages VALUES (?, ?, ?, ?)",
            (title, rev_id, wikitext, fetched_at),
        )
        if commit:
            self._conn.commit()

    def iter_pages(self):
        for r in self._conn.execute("SELECT * FROM wikimon_pages ORDER BY title"):
            yield dict(r)

    def get_page(self, title: str) -> Optional[dict]:
        r = self._conn.execute("SELECT * FROM wikimon_pages WHERE title = ?", (title,)).fetchone()
        return dict(r) if r else None

    # -- Import queue --------------------------------------------------

    def queue_add(self, titles: Iterable[str]) -> int:
        cur = self._conn.executemany(
            "INSERT OR IGNORE INTO import_queue (title) VALUES (?)",
            [(t,) for t in titles],
        )
        self._conn.commit()
        return cur.rowcount

    def queue_pending(self, limit: int, max_attempts: int = 3) -> list[str]:
        rows = self._conn.execute(
            "SELECT title FROM import_queue WHERE status = 'pending' "
            "OR (status = 'error' AND attempts < ?) ORDER BY title LIMIT ?",
            (max_attempts, limit),
        ).fetchall()
        return [r["title"] for r in rows]

    def queue_mark(self, title: str, status: str, error: str | None = None,
                   commit: bool = True) -> None:
        self._conn.execute(
            "UPDATE import_queue SET status = ?, error = ?, attempts = attempts + 1 "
            "WHERE title = ?",
            (status, error, title),
        )
        if commit:
            self._conn.commit()

    def queue_counts(self) -> dict[str, int]:
        counts = {"pending": 0, "done": 0, "skipped": 0, "error": 0}
        for r in self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM import_queue GROUP BY status"
        ):
            counts[r["status"]] = r["n"]
        return counts

    def queue_reset(self) -> None:
        """Mark every page as pending again (for a full refresh)."""
        self._conn.execute("UPDATE import_queue SET status = 'pending', attempts = 0, error = NULL")
        self._conn.commit()

    def queue_errors(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM import_queue WHERE status = 'error' ORDER BY title")]

    # -- Meta ----------------------------------------------------------

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        r = self._conn.execute("SELECT value FROM import_meta WHERE key = ?", (key,)).fetchone()
        return r["value"] if r else default

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute("INSERT OR REPLACE INTO import_meta VALUES (?, ?)", (key, value))
        self._conn.commit()

    def commit(self) -> None:
        self._conn.commit()

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
