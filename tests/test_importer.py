"""Runs the importer against a fake Wikimon API (no network)."""
from pathlib import Path

import pytest

from digitree.db.cache import CacheDB
from digitree.wikimon.client import StopRequested, WikimonClient
from digitree.wikimon.importer import Importer, describe, reparse_all

FIX = Path(__file__).parent / "fixtures"

INFOBOX = "{{{{S2|level1={lvl}|attribute1={attr}|type1={typ}|family1={field}}}}}\n"
PAGES = {
    "Agumon": INFOBOX.format(lvl="Child", attr="Vaccine", typ="Reptile", field="Nature Spirits")
              + "==Evolves To==\n*[[Greymon]]\n",
    "Gabumon": INFOBOX.format(lvl="Child", attr="Data", typ="Reptile", field="Nature Spirits"),
    "Greymon": (FIX / "table_style.wiki").read_text(encoding="utf-8"),
    "Volcamon": (FIX / "volcamon.wiki").read_text(encoding="utf-8"),
    "Digimon Adventure": "An anime. Uses {{S2}} oddly.",
}
REDIRECTS = {"Metal Greymon": "MetalGreymon"}


class FakeResponse:
    status_code = 200
    headers: dict = {}

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, fail_first_content=False):
        self.headers = {}
        self.calls = []
        self.fail_first_content = fail_first_content

    def get(self, url, params, timeout):
        self.calls.append(params)
        if params.get("list") == "embeddedin":
            assert params["eititle"] == "Template:S2"
            return FakeResponse({"query": {"embeddedin": [{"title": t} for t in PAGES]}})
        if params.get("list") == "categorymembers":
            return FakeResponse({"query": {"categorymembers": []}})
        titles = params["titles"].split("|")
        redirects = [{"from": t, "to": REDIRECTS[t]} for t in titles if t in REDIRECTS]
        if params.get("prop") != "revisions":
            return FakeResponse({"query": {"redirects": redirects}})
        if self.fail_first_content:
            self.fail_first_content = False
            return FakeResponse({"error": {"code": "internal_api_error", "info": "boom"}})
        pages = []
        for t in titles:
            if t in PAGES:
                pages.append({"title": t, "revisions": [
                    {"revid": 100, "slots": {"main": {"content": PAGES[t]}}}]})
            else:
                pages.append({"title": t, "missing": True})
        return FakeResponse({"query": {"pages": pages, "redirects": redirects}})


def make_client(session, **kw):
    return WikimonClient(min_interval=0, session=session, **kw)


def test_full_import(tmp_path):
    db = CacheDB(tmp_path / "w.db")
    session = FakeSession()
    counts = Importer(db, make_client(session)).run()
    assert counts == {"pending": 0, "done": 4, "skipped": 1, "error": 0}
    assert db.count_digimon() == 4
    v = describe(db, "Volcamon")
    assert v["traits"]["level"] == ["Perfect"]
    assert v["traits"]["field"] == ["Metal Empire", "Nature Spirits"]
    assert [a["name_en"] for a in v["attacks"]] == ["Volcanic Hammer", "Battle Hawk"]
    # Redirect resolved in the links stage
    assert [e["key"] for e in v["evolves_to"]] == ["MetalGreymon", "ShineGreymon"]
    assert [e["key"] for e in db.get_evolves_from("Greymon")] == ["Agumon", "Koromon"]
    # Every request was polite
    assert all(c["maxlag"] == "5" for c in session.calls)
    # Second run has nothing to do (no new content requests)
    n = len(session.calls)
    Importer(db, make_client(session)).run()
    assert not [c for c in session.calls[n:] if c.get("prop") == "revisions"]


def test_resume_after_stop(tmp_path):
    db = CacheDB(tmp_path / "w.db")
    session = FakeSession()
    stop = {"flag": False}

    def progress(p):
        if p.stage == "enumerate" and p.message.startswith("Found"):
            stop["flag"] = True

    client = make_client(session, should_stop=lambda: stop["flag"])
    counts = Importer(db, client, progress).run()
    assert counts["pending"] == 5 and db.count_digimon() == 0

    counts = Importer(db, make_client(session)).run()
    assert counts["done"] == 4 and db.count_digimon() == 4


def test_failed_batch_is_retried(tmp_path):
    db = CacheDB(tmp_path / "w.db")
    counts = Importer(db, make_client(FakeSession(fail_first_content=False))).run()
    # Seed request is a content request; make the first *download* batch fail.
    db2 = CacheDB(tmp_path / "w2.db")
    session = FakeSession()
    imp = Importer(db2, make_client(session))
    imp.enumerate_pages()
    session.fail_first_content = True
    imp.download()
    assert db2.count_digimon() == 4  # error rows were retried in the same loop
    assert counts["done"] == 4


def test_reparse_offline(tmp_path):
    db = CacheDB(tmp_path / "w.db")
    Importer(db, make_client(FakeSession())).run()
    db.conn.execute("DELETE FROM digimon_traits")
    db.commit()
    assert reparse_all(db) == 4
    assert db.get_traits("Volcamon")["type"] == ["Cyborg"]


def test_stop_interrupts_sleep():
    client = WikimonClient(min_interval=0, session=FakeSession(), should_stop=lambda: True)
    with pytest.raises(StopRequested):
        client._sleep(10)
