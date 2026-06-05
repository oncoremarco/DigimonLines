from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Stage:
    id: str
    label: str
    order: int
    color: str = "#FFFFFF"
    aliases: list[str] = field(default_factory=list)


@dataclass
class TypeTag:
    id: str
    label: str
    color: str = "#888888"
    symbol: str = ""


@dataclass
class RequirementType:
    id: str
    label: str
    value_type: str  # "range" | "threshold" | "min_count" | "boolean"
    symbol: str = ""


@dataclass
class Version:
    id: str
    label: str
    color: str = "#888888"


@dataclass
class RequirementCondition:
    req_type_id: str
    min: Optional[float] = None
    max: Optional[float] = None
    threshold: Optional[float] = None
    count: Optional[int] = None


@dataclass
class RequirementGroup:
    conditions: list[RequirementCondition] = field(default_factory=list)


@dataclass
class Entry:
    id: str = field(default_factory=_new_id)
    name: str = ""
    stage_id: str = ""
    type_tag_ids: list[str] = field(default_factory=list)
    version_ids: list[str] = field(default_factory=list)
    image_local: Optional[str] = None
    image_source_url: Optional[str] = None
    sprite_local: Optional[str] = None
    sprite_source_url: Optional[str] = None
    library_number: Optional[int] = None
    power: Optional[int] = None
    hp: Optional[int] = None
    sleep_time: Optional[str] = None
    wikimon_key: Optional[str] = None
    notes: str = ""
    pos_x: float = 0.0
    pos_y: float = 0.0
    aliases: list[str] = field(default_factory=list)
    display_name: str = ""


@dataclass
class Connection:
    id: str = field(default_factory=_new_id)
    from_entry_id: str = ""
    to_entry_id: str = ""
    version_ids: list[str] = field(default_factory=list)
    style: str = "normal"  # "normal" | "dashed_failure"
    req_groups: list[RequirementGroup] = field(default_factory=list)


@dataclass
class Tree:
    id: str = field(default_factory=_new_id)
    name: str = "Untitled Tree"
    device: str = ""
    notes: str = ""
    created: str = ""
    modified: str = ""
    versions: list[Version] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)
    type_tags: list[TypeTag] = field(default_factory=list)
    requirement_types: list[RequirementType] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    stage_display_index: int = 0  # 0=primary label, 1=alias[0], 2=alias[1], ...


# -- Display helpers ---------------------------------------------------

def get_stage_label(stage: Stage, display_index: int = 0) -> str:
    """Return the stage label for the given alias slot (0 = primary)."""
    if display_index <= 0 or not stage.aliases:
        return stage.label
    idx = display_index - 1
    return stage.aliases[idx] if idx < len(stage.aliases) else stage.label


def get_entry_display_name(entry: Entry) -> str:
    """Return the active display name for an entry (alias override or canonical)."""
    return entry.display_name if entry.display_name else entry.name


# -- Digimon defaults --------------------------------------------------

def make_digimon_defaults() -> tuple[list[Stage], list[TypeTag], list[RequirementType]]:
    stages = [
        Stage("s1", "Stage I",   1, "#E8D5FF", aliases=["Baby I",   "Baby"]),
        Stage("s2", "Stage II",  2, "#D5E8FF", aliases=["Baby II",  "In-Training"]),
        Stage("s3", "Stage III", 3, "#D5FFE8", aliases=["Child",    "Rookie"]),
        Stage("s4", "Stage IV",  4, "#FFFBD5", aliases=["Adult",    "Champion"]),
        Stage("s5", "Stage V",   5, "#FFE8D5", aliases=["Perfect",  "Ultimate"]),
        Stage("s6", "Stage VI",  6, "#FFD5D5", aliases=["Ultimate", "Mega"]),
    ]
    type_tags = [
        TypeTag("vaccine", "Vaccine", "#4A90D9", "V"),
        TypeTag("data",    "Data",    "#7ED321", "D"),
        TypeTag("virus",   "Virus",   "#D0021B", "Vi"),
        TypeTag("free",    "Free",    "#888888", "F"),
    ]
    requirement_types = [
        RequirementType("care_mistakes",    "Care Mistakes",             "range",     "✗"),
        RequirementType("effort",           "Effort",                    "range",     "⚡"),
        RequirementType("level",            "Level",                     "range",     "L"),
        RequirementType("area_cleared",     "Area Cleared",              "threshold", "▶"),
        RequirementType("area_not_cleared", "Area Not Cleared",          "threshold", "✕"),
        RequirementType("defeat_stage6",    "Defeat Stage VI",           "min_count", "⚔"),
        RequirementType("special_enc",      "Special Encounter Cleared", "boolean",   "★"),
        RequirementType("evo_fail",         "Evolution Failure",         "boolean",   "✘"),
    ]
    return stages, type_tags, requirement_types
