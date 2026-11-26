import sqlite3

from digitree.db.cache import SCHEMA_VERSION, CacheDB
from digitree.wikimon.importer import store_parsed
from digitree.wikimon.parser import ParsedDigimon


def make(key, level, attr, typ, fields, frm=(), to=()):
    return ParsedDigimon(key=key, name=key, levels=[level], attributes=[attr], types=[typ],
                         fields=list(fields), evolves_from=[(k, "") for k in frm],
                         evolves_to=[(k, "") for k in to])


def test_search_and_evolutions(tmp_path):
    db = CacheDB(tmp_path / "t.db")
    store_parsed(db, make("Volcamon", "Perfect", "Data", "Cyborg", ["Metal Empire"],
                          frm=["Tankmon"], to=["Metal Greymon"]), 1)
    store_parsed(db, make("Tankmon", "Adult", "Data", "Machine", ["Metal Empire"]), 2)
    store_parsed(db, make("MetalGreymon", "Perfect", "Vaccine", "Cyborg",
                          ["Nature Spirits", "Metal Empire"], frm=["Greymon"]), 3)
    db.add_redirects({"Metal Greymon": "MetalGreymon"})
    db.commit()

    assert [d["wikimon_key"] for d in db.search(level="perfect")] == ["MetalGreymon", "Volcamon"]
    assert [d["wikimon_key"] for d in db.search(level="Perfect", attribute="Data")] == ["Volcamon"]
    assert [d["wikimon_key"] for d in db.search(field="Metal Empire", type="Cyborg")] == ["MetalGreymon", "Volcamon"]
    assert [d["wikimon_key"] for d in db.search("volc")] == ["Volcamon"]

    # Volcamon's page lists Tankmon, so Tankmon "evolves to" Volcamon even
    # though Tankmon's own page doesn't say so.
    assert [e["key"] for e in db.get_evolves_to("Tankmon")] == ["Volcamon"]
    # Redirect "Metal Greymon" resolves to MetalGreymon.
    assert [e["key"] for e in db.get_evolves_to("Volcamon")] == ["MetalGreymon"]
    assert [e["key"] for e in db.get_evolves_from("MetalGreymon")] == ["Greymon", "Volcamon"]
    assert [d["wikimon_key"] for d in db.search(evolves_from="Tankmon")] == ["Volcamon"]
    assert db.get_digimon("Metal Greymon")["wikimon_key"] == "MetalGreymon"

    assert db.distinct_values("field") == ["Metal Empire", "Nature Spirits"]
    assert db.get_traits("MetalGreymon")["field"] == ["Nature Spirits", "Metal Empire"]


def test_reimport_replaces_rows(tmp_path):
    db = CacheDB(tmp_path / "t.db")
    store_parsed(db, make("A", "Child", "Data", "X", ["F1"], to=["B", "C"]), 1)
    store_parsed(db, make("A", "Child", "Virus", "X", ["F2"], to=["B"]), 2)
    db.commit()
    assert db.get_traits("A")["attribute"] == ["Virus"]
    assert [e["key"] for e in db.get_evolves_to("A")] == ["B"]


def test_migrates_old_database(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE digimon (wikimon_key TEXT PRIMARY KEY, display_name TEXT NOT NULL)")
    conn.execute("INSERT INTO digimon VALUES ('Agumon', 'Agumon')")
    conn.commit()
    conn.close()
    db = CacheDB(path)
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.get_digimon("Agumon")["rev_id"] is None
    assert db.queue_counts()["pending"] == 0
