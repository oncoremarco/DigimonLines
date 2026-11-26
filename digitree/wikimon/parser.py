"""Turn a Wikimon page's wikitext into structured Digimon data.

Wikimon's markup has changed over the years and differs a little between
pages, so this parser is deliberately forgiving:

* The infobox is found by scoring every top-level template on the page by how
  many Digimon-ish parameters it has (level, attribute, type, field...), rather
  than by a hard-coded template name. Numbered parameters such as ``level1``,
  ``level2`` are all collected.
* Sections are found by heading text ("Attack Techniques", "Evolves From",
  "Evolves To", "Description"...), at any heading depth.
* Attacks are read from a wikitable, from one-template-per-attack markup, or
  from a bullet list, whichever the section uses.

Everything here is pure text processing (no network, no Qt), which makes it
easy to test and to re-run over pages already stored in the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

import mwparserfromhell
from mwparserfromhell.nodes import Template, Wikilink

# Infobox parameter names (lower-cased, trailing digits removed) -> our trait.
PARAM_ALIASES: dict[str, str] = {
    "level": "level", "lvl": "level", "stage": "level",
    "attribute": "attribute", "attr": "attribute",
    "type": "type", "class": "type", "species": "type",
    "field": "field", "fields": "field", "family": "field", "fam": "field",
}
NAME_JP_PARAMS = ("jname", "japanese", "kana", "katakana", "jpname", "name_jp")
DUB_NAME_PARAMS = ("dubname", "dub", "ename", "englishname", "name_en", "dname")

KNOWN_ATTRIBUTES = {"vaccine", "data", "virus", "free", "variable", "unknown", "no data"}

# Headings we look for (compared lower-case, punctuation stripped).
ATTACK_HEADINGS = ("attack techniques", "attacks", "techniques", "special moves")
EVO_FROM_HEADINGS = ("evolves from", "digivolves from", "evolves from (jogress)", "evolution from")
EVO_TO_HEADINGS = ("evolves to", "digivolves to", "evolution to")
PROFILE_HEADINGS = ("description", "profile", "digimon reference book", "reference book")

_REF_RE = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_HEADING_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.M)
_WS_RE = re.compile(r"[ \t]+")


@dataclass
class Attack:
    name_en: str
    name_jp: str = ""
    name_jp_romaji: str = ""
    description_en: str = ""


@dataclass
class ParsedDigimon:
    key: str                         # Wikimon page title, e.g. "Volcamon"
    name: str                        # Display name
    name_jp: str = ""
    dub_name: str = ""
    levels: list[str] = dc_field(default_factory=list)
    types: list[str] = dc_field(default_factory=list)
    attributes: list[str] = dc_field(default_factory=list)
    fields: list[str] = dc_field(default_factory=list)
    profile_en: str = ""
    attacks: list[Attack] = dc_field(default_factory=list)
    evolves_from: list[tuple[str, str]] = dc_field(default_factory=list)  # (key, note)
    evolves_to: list[tuple[str, str]] = dc_field(default_factory=list)
    infobox_template: str = ""

    @property
    def looks_like_digimon(self) -> bool:
        """True if we found at least a Level or an Attribute."""
        return bool(self.levels or self.attributes)

    def traits(self) -> dict[str, list[str]]:
        return {"level": self.levels, "type": self.types,
                "attribute": self.attributes, "field": self.fields}


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """MediaWiki title normalisation: underscores -> spaces, first letter upper,
    drop any #section part."""
    title = title.split("#", 1)[0].replace("_", " ").strip()
    title = _WS_RE.sub(" ", title)
    return title[:1].upper() + title[1:] if title else title


def clean_text(wikitext: str) -> str:
    """Strip refs, comments, HTML tags and wiki markup, leaving readable text."""
    text = _COMMENT_RE.sub("", str(wikitext))
    text = _REF_RE.sub("", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    code = mwparserfromhell.parse(text)
    # Keep the visible text of simple inline templates like {{w|Foo}} or
    # {{Lang|Foo}} instead of dropping them entirely.
    for tpl in code.filter_templates(recursive=False):
        if len(tpl.params) == 1 and not tpl.params[0].showkey:
            try:
                code.replace(tpl, str(tpl.params[0].value))
            except ValueError:
                pass
    text = code.strip_code(normalize=True, collapse=True)
    text = _TAG_RE.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def _split_values(raw: str) -> list[str]:
    """'Data / Virus', 'Data, Virus', 'Data<br>Virus' -> ['Data', 'Virus']."""
    text = clean_text(raw)
    parts = re.split(r"\s*(?:\n|,|/|;|\band\b)\s*", text)
    out = []
    for p in parts:
        p = re.sub(r"\[\d+\]", "", p).strip(" .*")
        if p and p not in out and len(p) < 60:
            out.append(p)
    return out


def _norm_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9() ]+", "", clean_text(text).lower()).strip()


def _param_base(name: str) -> str:
    return re.sub(r"\d+$", "", name.strip().lower().replace(" ", "").replace("_", ""))


def _is_mostly_ascii(text: str) -> bool:
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text) > 0.9


# ----------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------

def split_sections(wikitext: str) -> list[tuple[str, int, str]]:
    """Return [(normalized_heading, depth, body)] for every heading.

    The body of a heading runs until the next heading of the same or higher
    level, so it includes its own sub-sections.
    """
    matches = list(_HEADING_RE.finditer(wikitext))
    out = []
    for i, m in enumerate(matches):
        depth = len(m.group(1))
        end = len(wikitext)
        for m2 in matches[i + 1:]:
            if len(m2.group(1)) <= depth:
                end = m2.start()
                break
        out.append((_norm_heading(m.group(2)), depth, wikitext[m.end():end]))
    return out


def find_section(sections, names: tuple[str, ...]) -> str | None:
    for wanted in names:
        for heading, _depth, body in sections:
            if heading == wanted:
                return body
    for wanted in names:
        for heading, _depth, body in sections:
            if heading.startswith(wanted):
                return body
    return None


# ----------------------------------------------------------------------
# Infobox
# ----------------------------------------------------------------------

def _score_template(tpl: Template) -> int:
    bases = {_param_base(str(p.name)) for p in tpl.params}
    return sum(1 for b in bases if b in PARAM_ALIASES and b not in ("class", "species", "stage"))


def find_infobox(code) -> Template | None:
    best, best_score = None, 0
    for tpl in code.filter_templates(recursive=True):
        score = _score_template(tpl)
        if score > best_score:
            best, best_score = tpl, score
    return best if best_score >= 2 else None


def _read_infobox(tpl: Template, result: ParsedDigimon) -> None:
    result.infobox_template = normalize_title(str(tpl.name).strip())
    buckets = {"level": result.levels, "type": result.types,
               "attribute": result.attributes, "field": result.fields}
    # Sort numbered params so level1 comes before level2.
    def sort_key(p):
        name = str(p.name).strip().lower()
        m = re.search(r"(\d+)$", name)
        return (int(m.group(1)) if m else 0)
    for p in sorted(tpl.params, key=sort_key):
        pname = str(p.name).strip().lower()
        if any(s in pname for s in ("ref", "cite", "source", "note")):
            continue
        base = _param_base(pname)
        value = str(p.value)
        if base in PARAM_ALIASES:
            for v in _split_values(value):
                bucket = buckets[PARAM_ALIASES[base]]
                if v not in bucket:
                    bucket.append(v)
        elif base in NAME_JP_PARAMS and not result.name_jp:
            result.name_jp = clean_text(value)
        elif base in DUB_NAME_PARAMS and not result.dub_name:
            result.dub_name = clean_text(value)
        elif base in ("name", "title") and clean_text(value):
            result.name = clean_text(value)
    # "Type" on some templates holds the attribute; move obvious ones over.
    for t in list(result.types):
        if t.lower() in KNOWN_ATTRIBUTES and not result.attributes:
            result.types.remove(t)
            result.attributes.append(t)


def _read_infobox_rows(wikitext: str, result: ParsedDigimon) -> None:
    """Fallback for pages whose infobox is a plain wikitable:
    ``! Level || [[Perfect]]`` or ``| Level || Perfect``."""
    buckets = {"level": result.levels, "type": result.types,
               "attribute": result.attributes, "field": result.fields}
    for line in wikitext.splitlines():
        m = re.match(r"^\s*[!|]\s*([A-Za-z ]+?)\s*(?:\|\||!!|\n\|)\s*(.+)$", line)
        if not m:
            continue
        base = _param_base(m.group(1))
        if base in PARAM_ALIASES and base not in ("class", "species", "stage"):
            value = m.group(2).split("||")[0]
            for v in _split_values(value):
                bucket = buckets[PARAM_ALIASES[base]]
                if v not in bucket:
                    bucket.append(v)


# ----------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------

def _extract_profile(section: str) -> str:
    code = mwparserfromhell.parse(section)
    candidates: list[tuple[int, str]] = []  # (priority, text)
    for tpl in code.filter_templates(recursive=True):
        tname = str(tpl.name).strip().lower()
        for p in tpl.params:
            pname = str(p.name).strip().lower()
            text = clean_text(str(p.value))
            if len(text) < 40 or not _is_mostly_ascii(text):
                continue
            prio = 1
            if "reference" in tname or "drb" in tname or "reference" in str(p.value).lower():
                prio = 3
            if pname in ("e", "en", "eng", "english", "1", "text", "description", "desc"):
                prio += 1
            candidates.append((prio, text))
    if not candidates:
        # Plain paragraphs. Prefer the one following a "Reference Book" mention.
        plain = re.split(r"\n\s*\n", section)
        after_drb = False
        for chunk in plain:
            text = clean_text(chunk)
            if "reference book" in chunk.lower():
                after_drb = True
            if len(text) >= 40 and _is_mostly_ascii(text):
                candidates.append((2 if after_drb else 1, text))
    if not candidates:
        return ""
    best_prio = max(p for p, _ in candidates)
    for prio, text in candidates:  # first one with the best priority
        if prio == best_prio:
            return text
    return ""


# ----------------------------------------------------------------------
# Attacks
# ----------------------------------------------------------------------

def _looks_like_header(cell: str) -> bool:
    return cell.strip().lower() in ("name", "attack", "technique", "kanji", "romaji",
                                    "dub", "dub name", "description", "japanese",
                                    "english", "translation", "")


def _attacks_from_table(section: str) -> list[Attack]:
    attacks = []
    for table in re.findall(r"\{\|.*?\n\|\}", section, re.S):
        header: list[str] = []
        for row in re.split(r"\n\|-[^\n]*", table)[1:]:
            cells = []
            for line in row.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("|}"):
                    continue
                if line[0] in "!|":
                    is_header = line[0] == "!"
                    parts = re.split(r"\|\||!!", line[1:])
                    for part in parts:
                        # Drop cell attributes like 'style="..." | value'
                        if "|" in part and "[[" not in part.split("|", 1)[0] and "=" in part.split("|", 1)[0]:
                            part = part.split("|", 1)[1]
                        cells.append(("h" if is_header else "d", part))
                elif cells:
                    kind, prev = cells[-1]
                    cells[-1] = (kind, prev + "\n" + line)
            if not cells:
                continue
            if all(kind == "h" for kind, _ in cells):
                header = [clean_text(c).lower() for _, c in cells]
                continue
            texts = [clean_text(c) for _, c in cells]
            if not texts or all(_looks_like_header(t) for t in texts):
                continue
            atk = Attack(name_en="")
            if header and len(header) == len(texts):
                for h, t in zip(header, texts):
                    if "kanji" in h or "japanese" in h:
                        atk.name_jp = t
                    elif "romaji" in h:
                        atk.name_jp_romaji = t
                    elif "desc" in h:
                        atk.description_en = t
                    elif "dub" in h or "english" in h or "name" in h or "translation" in h:
                        if not atk.name_en:
                            atk.name_en = t
                if not atk.name_en:
                    atk.name_en = atk.name_jp_romaji or texts[0]
            else:
                atk = _attack_from_cells(texts)
            if atk.name_en:
                attacks.append(atk)
    return attacks


def _attack_from_cells(texts: list[str]) -> Attack:
    """Heuristic for header-less rows: the longest ASCII cell is the
    description, the first ASCII cell is the name, any Japanese cell is jp."""
    ascii_cells = [t for t in texts if t and _is_mostly_ascii(t)]
    jp_cells = [t for t in texts if t and not _is_mostly_ascii(t)]
    desc = max(ascii_cells, key=len) if ascii_cells else ""
    names = [t for t in ascii_cells if t != desc or len(ascii_cells) == 1]
    name = names[-1] if names else desc
    if len(desc) < 25:
        desc = ""
    atk = Attack(name_en=name, description_en=desc)
    if jp_cells:
        atk.name_jp = jp_cells[0]
    if len(names) >= 2:
        atk.name_jp_romaji = names[0]
    return atk


def _attacks_from_templates(section: str) -> list[Attack]:
    attacks = []
    code = mwparserfromhell.parse(section)
    for tpl in code.filter_templates(recursive=False):
        named = {_param_base(str(p.name)): clean_text(str(p.value)) for p in tpl.params if p.showkey}
        positional = [clean_text(str(p.value)) for p in tpl.params if not p.showkey]
        if named:
            name = (named.get("dub") or named.get("name") or named.get("ename")
                    or named.get("english") or named.get("translation") or named.get("romaji") or "")
            atk = Attack(
                name_en=name,
                name_jp=named.get("kanji") or named.get("jname") or named.get("japanese") or "",
                name_jp_romaji=named.get("romaji") or "",
                description_en=named.get("description") or named.get("desc") or named.get("text") or "",
            )
        elif positional:
            atk = _attack_from_cells(positional)
        else:
            continue
        if atk.name_en and len(atk.name_en) < 120:
            attacks.append(atk)
    return attacks


def _attacks_from_list(section: str) -> list[Attack]:
    attacks = []
    for line in section.splitlines():
        if not line.lstrip().startswith(("*", "#")):
            continue
        body = line.lstrip("*# ").strip()
        m = re.match(r"^'''(.+?)'''\s*(?:\((.*?)\))?\s*[:\-–—]?\s*(.*)$", body)
        if m:
            atk = Attack(name_en=clean_text(m.group(1)),
                         name_jp_romaji=clean_text(m.group(2) or ""),
                         description_en=clean_text(m.group(3)))
        else:
            name, _, desc = clean_text(body).partition(":")
            atk = Attack(name_en=name.strip(), description_en=desc.strip())
        if atk.name_en:
            attacks.append(atk)
    return attacks


def extract_attacks(section: str) -> list[Attack]:
    for fn in (_attacks_from_table, _attacks_from_templates, _attacks_from_list):
        found = fn(section)
        if found:
            # De-duplicate by name, keep order.
            seen, out = set(), []
            for a in found:
                if a.name_en.lower() not in seen:
                    seen.add(a.name_en.lower())
                    out.append(a)
            return out
    return []


# ----------------------------------------------------------------------
# Evolution lists
# ----------------------------------------------------------------------

_SKIP_LINK_PREFIXES = ("file:", "image:", "category:", "media:", "w:", "wikipedia:",
                       "template:", "special:", "user:", "help:")


def _first_digimon_link(code) -> str | None:
    for node in code.filter(recursive=True, forcetype=(Wikilink, Template)):
        if isinstance(node, Wikilink):
            target = str(node.title).strip()
            if not target or target.lower().startswith(_SKIP_LINK_PREFIXES) or target.startswith("#"):
                continue
            return normalize_title(target)
        if isinstance(node, Template):
            tname = str(node.name).strip().lower()
            if tname in ("ref", "cite", "note", "efn") or tname.startswith("cite"):
                continue
            pos = [p for p in node.params if not p.showkey]
            if pos and ("evo" in tname or "link" in tname or tname in ("d", "digimon", "dl")):
                return normalize_title(clean_text(str(pos[0].value)))
    return None


def extract_evolutions(section: str) -> list[tuple[str, str]]:
    """Each list item becomes (linked Digimon key, readable note)."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    section = _COMMENT_RE.sub("", section)
    section = _REF_RE.sub("", section)
    for line in section.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith(("*", "#")):
            continue
        body = stripped.lstrip("*#: ").strip()
        code = mwparserfromhell.parse(body)
        key = _first_digimon_link(code)
        if not key or key in seen:
            continue
        seen.add(key)
        note = clean_text(body)
        out.append((key, note))
    return out


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def _unwrap_tabbers(wikitext: str) -> str:
    """<tabber> blocks hold several versions of a section ("Anime|-|Manga").
    Remove the tab separators so their contents are parsed as one section."""
    text = re.sub(r"</?tabber>", "\n", wikitext, flags=re.I)
    text = re.sub(r"^\|-\|\s*", "", text, flags=re.M)
    return text


def parse_digimon_page(title: str, wikitext: str) -> ParsedDigimon:
    key = normalize_title(title)
    result = ParsedDigimon(key=key, name=key)
    text = _unwrap_tabbers(_COMMENT_RE.sub("", wikitext))
    code = mwparserfromhell.parse(text)

    infobox = find_infobox(code)
    if infobox is not None:
        _read_infobox(infobox, result)
    if not result.looks_like_digimon:
        _read_infobox_rows(text, result)
    # Keep the page title as the key; only use the infobox "name" if it's
    # a plain variant of the title (avoids picking up image captions).
    if not result.name or len(result.name) > 80:
        result.name = key

    sections = split_sections(text)

    profile = find_section(sections, PROFILE_HEADINGS)
    if profile:
        result.profile_en = _extract_profile(profile)

    attacks = find_section(sections, ATTACK_HEADINGS)
    if attacks:
        result.attacks = extract_attacks(attacks)

    evo_from = find_section(sections, EVO_FROM_HEADINGS)
    if evo_from:
        result.evolves_from = [(k, n) for k, n in extract_evolutions(evo_from) if k != key]
    evo_to = find_section(sections, EVO_TO_HEADINGS)
    if evo_to:
        result.evolves_to = [(k, n) for k, n in extract_evolutions(evo_to) if k != key]

    return result
