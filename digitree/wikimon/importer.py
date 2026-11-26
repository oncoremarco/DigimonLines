"""Build the local Digimon database from Wikimon.

The import runs in three resumable stages:

1. **Find pages**: list every Digimon page on Wikimon. By default we look at
   a couple of well-known pages (Agumon, Volcamon), work out which infobox
   template Digimon pages use, then ask the API for every page using that
   template. A category can be given instead.
2. **Download + parse**: fetch page text 50 pages per request, store the raw
   text, and parse it into the digimon / traits / attacks / evolutions
   tables. Each page is marked done in ``import_queue`` as soon as it's
   saved, so stopping and restarting picks up where it left off.
3. **Resolve links**: evolution lists sometimes link to a redirect name
   (e.g. "Metal Greymon"); we look those up so they point at the real page.

Run from the command line with ``python -m digitree.wikimon.importer``, or
from the app via Tools > Import Digimon Database.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from digitree.db.cache import CacheDB
from digitree.wikimon.client import BATCH_SIZE, StopRequested, WikimonClient
from digitree.wikimon.parser import (ParsedDigimon, find_infobox, normalize_title,
                                     parse_digimon_page)

import mwparserfromhell

SEED_PAGES = ("Agumon", "Volcamon", "Gabumon")
FALLBACK_CATEGORIES = ("Category:Digimon",)


@dataclass
class ImportProgress:
    stage: str          # 'enumerate' | 'download' | 'links' | 'done' | 'stopped' | 'error'
    done: int = 0
    total: int = 0
    message: str = ""


ProgressFn = Callable[[ImportProgress], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def store_parsed(db: CacheDB, parsed: ParsedDigimon, rev_id: int | None) -> None:
    """Write one parsed Digimon to every table (single transaction)."""
    key = parsed.key
    db.upsert_digimon({
        "wikimon_key": key,
        "display_name": parsed.name,
        "name_jp": parsed.name_jp or None,
        "dub_name": parsed.dub_name or None,
        "level": ", ".join(parsed.levels) or None,
        "attribute": ", ".join(parsed.attributes) or None,
        "type": ", ".join(parsed.types) or None,
        "fields": ", ".join(parsed.fields) or None,
        "profile_en": parsed.profile_en or None,
        "wikimon_url": "https://wikimon.net/" + key.replace(" ", "_"),
        "rev_id": rev_id,
        "fetched_at": _now(),
        "fetch_status": "ok",
    }, commit=False)
    db.set_traits(key, parsed.traits(), commit=False)
    db.upsert_attacks(key, [
        {
            "id": f"{key}#{i}",
            "wikimon_key": key,
            "name_en": a.name_en,
            "name_jp": a.name_jp or None,
            "name_jp_romaji": a.name_jp_romaji or None,
            "description_en": a.description_en or None,
            "sort_order": i,
        }
        for i, a in enumerate(parsed.attacks)
    ], commit=False)
    db.set_evolutions(key, parsed.evolves_from, parsed.evolves_to, commit=False)


class Importer:
    def __init__(self, db: CacheDB, client: WikimonClient,
                 progress: ProgressFn | None = None,
                 category: str | None = None):
        self.db = db
        self.client = client
        self.progress = progress or (lambda p: None)
        self.category = category

    # -- stage 1 -------------------------------------------------------

    def discover_infobox_template(self) -> str | None:
        pages, _ = self.client.fetch_wikitext(list(SEED_PAGES))
        names: dict[str, int] = {}
        for page in pages.values():
            if page.get("missing"):
                continue
            tpl = find_infobox(mwparserfromhell.parse(page["wikitext"]))
            if tpl is not None:
                name = normalize_title(str(tpl.name).strip())
                names[name] = names.get(name, 0) + 1
        return max(names, key=names.get) if names else None

    def enumerate_pages(self) -> int:
        self.progress(ImportProgress("enumerate", message="Finding Digimon pages on Wikimon…"))
        titles: list[str] = []
        source = ""
        if self.category:
            titles = self.client.category_members(self.category)
            source = self.category
        else:
            template = self.discover_infobox_template()
            if template:
                titles = self.client.pages_using_template(template)
                source = f"Template:{template}"
            if len(titles) < 50:
                for cat in FALLBACK_CATEGORIES:
                    titles += self.client.category_members(cat)
                    source = (source + " + " if source else "") + cat
        if not titles:
            raise RuntimeError("Couldn't find any Digimon pages on Wikimon. "
                               "Try passing a category with --category.")
        added = self.db.queue_add(sorted(set(titles)))
        self.db.set_meta("enumerated_at", _now())
        self.db.set_meta("enumerated_from", source)
        self.progress(ImportProgress("enumerate", message=f"Found {len(set(titles))} pages via {source}"))
        return added

    # -- stage 2 -------------------------------------------------------

    def download(self) -> None:
        counts = self.db.queue_counts()
        total = sum(counts.values())
        done = counts["done"] + counts["skipped"]
        while True:
            batch = self.db.queue_pending(BATCH_SIZE)
            if not batch:
                break
            self.progress(ImportProgress("download", done, total,
                                         f"Downloading {batch[0]} … ({done}/{total})"))
            try:
                pages, redirects = self.client.fetch_wikitext(batch)
            except StopRequested:
                raise
            except Exception as exc:  # whole batch failed: count an attempt each
                for t in batch:
                    self.db.queue_mark(t, "error", str(exc), commit=False)
                self.db.commit()
                continue
            if redirects:
                self.db.add_redirects({normalize_title(a): normalize_title(t)
                                       for a, t in redirects.items()}, commit=False)
            for title in batch:
                resolved = redirects.get(title, title)
                page = pages.get(resolved) or pages.get(title)
                if page is None or page.get("missing"):
                    self.db.queue_mark(title, "skipped", "missing page", commit=False)
                    done += 1
                    continue
                try:
                    self.db.save_page(page["title"], page["rev_id"], page["wikitext"], _now(), commit=False)
                    parsed = parse_digimon_page(page["title"], page["wikitext"])
                    if parsed.looks_like_digimon:
                        store_parsed(self.db, parsed, page["rev_id"])
                        self.db.queue_mark(title, "done", commit=False)
                    else:
                        self.db.queue_mark(title, "skipped", "no Digimon infobox", commit=False)
                except Exception as exc:
                    self.db.queue_mark(title, "error", f"{type(exc).__name__}: {exc}", commit=False)
                done += 1
            self.db.commit()  # one commit per batch: a stop loses at most one batch
        self.progress(ImportProgress("download", done, total, "Download complete"))

    # -- stage 3 -------------------------------------------------------

    def resolve_links(self) -> None:
        unresolved = self.db.unresolved_evolution_keys()
        if not unresolved:
            return
        self.progress(ImportProgress("links", 0, len(unresolved),
                                     f"Checking {len(unresolved)} evolution links for redirects…"))
        mapping = self.client.resolve_redirects(unresolved)
        self.db.add_redirects({normalize_title(a): normalize_title(t) for a, t in mapping.items()})

    # -- all -----------------------------------------------------------

    def run(self, refresh: bool = False) -> dict[str, int]:
        try:
            if refresh:
                self.db.queue_reset()
            if sum(self.db.queue_counts().values()) == 0 or refresh:
                self.enumerate_pages()
            self.download()
            self.resolve_links()
            self.db.set_meta("imported_at", _now())
        except StopRequested:
            self.db.commit()
            self.progress(ImportProgress("stopped", message="Stopped. Run the import again to resume."))
            return self.db.queue_counts()
        counts = self.db.queue_counts()
        self.progress(ImportProgress(
            "done", counts["done"], sum(counts.values()),
            f"Imported {self.db.count_digimon()} Digimon "
            f"({counts['skipped']} non-Digimon pages skipped, {counts['error']} errors)."))
        return counts


def reparse_all(db: CacheDB, progress: ProgressFn | None = None) -> int:
    """Re-run the parser over every stored page. No network needed, so this
    is how parser fixes get applied to an existing database."""
    progress = progress or (lambda p: None)
    pages = list(db.iter_pages())
    count = 0
    for i, page in enumerate(pages):
        parsed = parse_digimon_page(page["title"], page["wikitext"] or "")
        if parsed.looks_like_digimon:
            store_parsed(db, parsed, page["rev_id"])
            db.conn.execute("UPDATE import_queue SET status='done', error=NULL WHERE title=?",
                            (page["title"],))
            count += 1
        if i % 100 == 0:
            db.commit()
            progress(ImportProgress("download", i, len(pages), f"Re-parsing {page['title']}…"))
    db.commit()
    return count


def describe(db: CacheDB, key: str) -> dict:
    """Everything stored about one Digimon, as plain data (for --show)."""
    d = db.get_digimon(key)
    if not d:
        return {}
    return {
        "key": d["wikimon_key"],
        "name": d["display_name"],
        "name_jp": d["name_jp"],
        "traits": db.get_traits(key),
        "profile": d["profile_en"],
        "attacks": [{k: a[k] for k in ("name_en", "name_jp", "name_jp_romaji", "description_en")}
                    for a in db.get_attacks(key)],
        "evolves_from": db.get_evolves_from(key),
        "evolves_to": db.get_evolves_to(key),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import Digimon data from Wikimon into DigiTree's local database.")
    ap.add_argument("--db", type=Path, help="Database file (default: DigiTree's app data folder)")
    ap.add_argument("--category", help="Wikimon category listing Digimon pages (default: auto-detect)")
    ap.add_argument("--delay", type=float, default=None, help="Seconds between requests (default from config, 2.0)")
    ap.add_argument("--refresh", action="store_true", help="Re-download every page")
    ap.add_argument("--reparse", action="store_true", help="Re-parse stored pages without downloading")
    ap.add_argument("--status", action="store_true", help="Show import progress and exit")
    ap.add_argument("--show", metavar="NAME", help="Print what's stored for one Digimon")
    ap.add_argument("--debug-page", metavar="NAME",
                    help="Download one page and print the parser's result (doesn't touch the database)")
    args = ap.parse_args(argv)

    if args.delay is None:
        try:
            from digitree.config import Config
            args.delay = float(Config().get("wikimon_rate_limit", 2.0))
        except Exception:
            args.delay = 2.0

    if args.debug_page:
        client = WikimonClient(min_interval=args.delay)
        pages, redirects = client.fetch_wikitext([args.debug_page])
        title = redirects.get(args.debug_page, args.debug_page)
        page = pages.get(title) or next(iter(pages.values()))
        if page.get("missing"):
            print("Page not found.")
            return 1
        parsed = parse_digimon_page(page["title"], page["wikitext"])
        out = dict(parsed.__dict__)
        out["attacks"] = [a.__dict__ for a in parsed.attacks]
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    db = CacheDB(args.db) if args.db else CacheDB()
    try:
        if args.status:
            print(json.dumps({"queue": db.queue_counts(), "digimon": db.count_digimon(),
                              "enumerated_from": db.get_meta("enumerated_from"),
                              "imported_at": db.get_meta("imported_at")}, indent=2))
            return 0
        if args.show:
            print(json.dumps(describe(db, normalize_title(args.show)), indent=2, ensure_ascii=False))
            return 0
        if args.reparse:
            n = reparse_all(db, lambda p: print(p.message, end="\r"))
            print(f"\nRe-parsed {n} Digimon.")
            return 0

        def show(p: ImportProgress) -> None:
            print(f"[{p.stage}] {p.message}", flush=True)

        client = WikimonClient(min_interval=args.delay)
        counts = Importer(db, client, show, args.category).run(refresh=args.refresh)
        for err in db.queue_errors()[:20]:
            print(f"  error: {err['title']}: {err['error']}")
        return 0 if counts["error"] == 0 else 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
