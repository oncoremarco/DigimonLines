from pathlib import Path

from digitree.wikimon.parser import clean_text, normalize_title, parse_digimon_page

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_infobox_template_style():
    d = parse_digimon_page("Volcamon", load("volcamon.wiki"))
    assert d.name == "Volcamon"
    assert d.name_jp == "ヴォルクモン"
    assert d.levels == ["Perfect"]
    assert d.types == ["Cyborg"]
    assert d.attributes == ["Data"]
    assert d.fields == ["Metal Empire", "Nature Spirits"]
    assert d.infobox_template == "S2"


def test_profile_prefers_english():
    d = parse_digimon_page("Volcamon", load("volcamon.wiki"))
    assert d.profile_en.startswith("A Cyborg Digimon whose entire body")
    assert "ref" not in d.profile_en.lower()


def test_attacks_from_wikitable_with_header():
    d = parse_digimon_page("Volcamon", load("volcamon.wiki"))
    names = [a.name_en for a in d.attacks]
    assert names == ["Volcanic Hammer", "Battle Hawk"]
    assert d.attacks[0].name_jp == "ヴォルケーノハンマー"
    assert d.attacks[0].name_jp_romaji == "Vorukēno Hanmā"
    assert "eruption" in d.attacks[0].description_en


def test_evolution_lists():
    d = parse_digimon_page("Volcamon", load("volcamon.wiki"))
    assert [k for k, _ in d.evolves_from] == ["Tankmon", "Greymon", "Gururumon"]
    assert "Metal Empire" in d.evolves_from[1][1]          # note kept
    assert [k for k, _ in d.evolves_to] == ["Metal Greymon", "ShineGreymon"]


def test_table_style_page():
    d = parse_digimon_page("Greymon", load("table_style.wiki"))
    assert d.levels == ["Adult"]
    assert d.attributes == ["Vaccine"]
    assert d.fields == ["Nature Spirits", "Dragon's Roar"]
    assert d.profile_en.startswith("A dinosaur Digimon")
    assert [a.name_en for a in d.attacks] == ["Mega Flame", "Great Antler"]
    assert d.attacks[0].description_en == "Spits a ball of fire."
    assert [k for k, _ in d.evolves_from] == ["Agumon", "Koromon"]
    assert [k for k, _ in d.evolves_to] == ["MetalGreymon"]


def test_non_digimon_page_is_detected():
    d = parse_digimon_page("Digimon Adventure", "'''Digimon Adventure''' is an anime.\n==Plot==\nStuff.")
    assert not d.looks_like_digimon


def test_helpers():
    assert normalize_title("metal_Greymon#Anime") == "Metal Greymon"
    assert clean_text("[[Perfect|Ultimate]]<ref>x</ref> ''level''") == "Ultimate level"
