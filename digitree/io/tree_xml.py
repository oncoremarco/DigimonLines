from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from lxml import etree

from digitree.models.tree import (
    Tree, Stage, TypeTag, RequirementType, Version,
    Entry, Connection, RequirementGroup, RequirementCondition,
)

_SCHEMA_VERSION = "1.0"


# -- Save --------------------------------------------------------------

def save_tree(tree: Tree, path: Path | str) -> None:
    path = Path(path)
    now = datetime.now(timezone.utc).isoformat()
    tree.modified = now
    if not tree.created:
        tree.created = now

    root = etree.Element("tree",
                          id=tree.id,
                          name=tree.name,
                          device=tree.device,
                          version=_SCHEMA_VERSION)

    meta = etree.SubElement(root, "meta")
    _sub(meta, "created",  tree.created)
    _sub(meta, "modified", tree.modified)
    _sub(meta, "notes",    tree.notes)

    versions_el = etree.SubElement(root, "versions")
    for v in tree.versions:
        etree.SubElement(versions_el, "version",
                         id=v.id, label=v.label, color=v.color)

    stages_el = etree.SubElement(root, "stages")
    for s in tree.stages:
        etree.SubElement(stages_el, "stage",
                         id=s.id, label=s.label,
                         order=str(s.order), color=s.color)

    tags_el = etree.SubElement(root, "type_tags")
    for t in tree.type_tags:
        etree.SubElement(tags_el, "tag",
                         id=t.id, label=t.label,
                         color=t.color, symbol=t.symbol)

    reqs_el = etree.SubElement(root, "requirement_types")
    for r in tree.requirement_types:
        etree.SubElement(reqs_el, "req_type",
                         id=r.id, label=r.label,
                         value_type=r.value_type, symbol=r.symbol)

    entries_el = etree.SubElement(root, "entries")
    for e in tree.entries:
        entry_el = etree.SubElement(entries_el, "entry",
                                    id=e.id, name=e.name, stage=e.stage_id)
        if e.wikimon_key:
            entry_el.set("wikimon_key", e.wikimon_key)

        tt_el = etree.SubElement(entry_el, "type_tags")
        for tid in e.type_tag_ids:
            etree.SubElement(tt_el, "type_tag", ref=tid)

        ver_el = etree.SubElement(entry_el, "versions")
        for vid in e.version_ids:
            etree.SubElement(ver_el, "v", ref=vid)

        if e.image_local or e.image_source_url:
            etree.SubElement(entry_el, "image",
                             local=e.image_local or "",
                             source_url=e.image_source_url or "")
        if e.sprite_local or e.sprite_source_url:
            etree.SubElement(entry_el, "sprite",
                             local=e.sprite_local or "",
                             source_url=e.sprite_source_url or "")

        _sub(entry_el, "library_number",
             str(e.library_number) if e.library_number is not None else "")
        _sub(entry_el, "power",
             str(e.power) if e.power is not None else "")
        _sub(entry_el, "hp",
             str(e.hp) if e.hp is not None else "")
        _sub(entry_el, "sleep_time", e.sleep_time or "")
        _sub(entry_el, "notes", e.notes)
        etree.SubElement(entry_el, "pos", x=str(e.pos_x), y=str(e.pos_y))

    conns_el = etree.SubElement(root, "connections")
    for c in tree.connections:
        conn_el = etree.SubElement(conns_el, "connection",
                                   id=c.id, style=c.style)
        conn_el.set("from", c.from_entry_id)
        conn_el.set("to",   c.to_entry_id)

        ver_el = etree.SubElement(conn_el, "versions")
        for vid in c.version_ids:
            etree.SubElement(ver_el, "v", ref=vid)

        for grp in c.req_groups:
            grp_el = etree.SubElement(conn_el, "req_group")
            for cond in grp.conditions:
                attrs: dict[str, str] = {"type": cond.req_type_id}
                if cond.min is not None:
                    attrs["min"] = str(cond.min)
                if cond.max is not None:
                    attrs["max"] = str(cond.max)
                if cond.threshold is not None:
                    attrs["threshold"] = str(cond.threshold)
                if cond.count is not None:
                    attrs["count"] = str(cond.count)
                etree.SubElement(grp_el, "req", **attrs)

    doc = etree.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.write(str(path), pretty_print=True,
              xml_declaration=True, encoding="UTF-8")


# -- Load --------------------------------------------------------------

def load_tree(path: Path | str) -> Tree:
    path = Path(path)
    root = etree.parse(str(path)).getroot()

    tree = Tree(
        id=root.get("id", ""),
        name=root.get("name", "Untitled"),
        device=root.get("device", ""),
    )

    meta = root.find("meta")
    if meta is not None:
        tree.created  = _txt(meta, "created")
        tree.modified = _txt(meta, "modified")
        tree.notes    = _txt(meta, "notes")

    for el in root.findall("versions/version"):
        tree.versions.append(Version(
            id=el.get("id", ""),
            label=el.get("label", ""),
            color=el.get("color", "#888888"),
        ))

    for el in root.findall("stages/stage"):
        tree.stages.append(Stage(
            id=el.get("id", ""),
            label=el.get("label", ""),
            order=int(el.get("order", "0")),
            color=el.get("color", "#FFFFFF"),
        ))

    for el in root.findall("type_tags/tag"):
        tree.type_tags.append(TypeTag(
            id=el.get("id", ""),
            label=el.get("label", ""),
            color=el.get("color", "#888888"),
            symbol=el.get("symbol", ""),
        ))

    for el in root.findall("requirement_types/req_type"):
        tree.requirement_types.append(RequirementType(
            id=el.get("id", ""),
            label=el.get("label", ""),
            value_type=el.get("value_type", "range"),
            symbol=el.get("symbol", ""),
        ))

    for e_el in root.findall("entries/entry"):
        entry = Entry(
            id=e_el.get("id", ""),
            name=e_el.get("name", ""),
            stage_id=e_el.get("stage", ""),
            wikimon_key=e_el.get("wikimon_key") or None,
        )
        entry.type_tag_ids = [t.get("ref", "") for t in e_el.findall("type_tags/type_tag")]
        entry.version_ids  = [v.get("ref", "") for v in e_el.findall("versions/v")]

        img = e_el.find("image")
        if img is not None:
            entry.image_local      = img.get("local") or None
            entry.image_source_url = img.get("source_url") or None

        spr = e_el.find("sprite")
        if spr is not None:
            entry.sprite_local      = spr.get("local") or None
            entry.sprite_source_url = spr.get("source_url") or None

        entry.library_number = _int_txt(e_el, "library_number")
        entry.power          = _int_txt(e_el, "power")
        entry.hp             = _int_txt(e_el, "hp")
        entry.sleep_time     = _txt(e_el, "sleep_time") or None
        entry.notes          = _txt(e_el, "notes")

        pos = e_el.find("pos")
        if pos is not None:
            entry.pos_x = float(pos.get("x", "0"))
            entry.pos_y = float(pos.get("y", "0"))

        tree.entries.append(entry)

    for c_el in root.findall("connections/connection"):
        conn = Connection(
            id=c_el.get("id", ""),
            from_entry_id=c_el.get("from", ""),
            to_entry_id=c_el.get("to", ""),
            style=c_el.get("style", "normal"),
        )
        conn.version_ids = [v.get("ref", "") for v in c_el.findall("versions/v")]

        for grp_el in c_el.findall("req_group"):
            grp = RequirementGroup()
            for req_el in grp_el.findall("req"):
                cond = RequirementCondition(req_type_id=req_el.get("type", ""))
                if req_el.get("min") is not None:
                    cond.min = float(req_el.get("min"))
                if req_el.get("max") is not None:
                    cond.max = float(req_el.get("max"))
                if req_el.get("threshold") is not None:
                    cond.threshold = float(req_el.get("threshold"))
                if req_el.get("count") is not None:
                    cond.count = int(req_el.get("count"))
                grp.conditions.append(cond)
            conn.req_groups.append(grp)

        tree.connections.append(conn)

    return tree


# -- Helpers -----------------------------------------------------------

def _sub(parent: etree._Element, tag: str, text: str) -> etree._Element:
    el = etree.SubElement(parent, tag)
    el.text = text
    return el


def _txt(parent: etree._Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _int_txt(parent: etree._Element, tag: str) -> Optional[int]:
    val = _txt(parent, tag)
    try:
        return int(val) if val else None
    except ValueError:
        return None
