from __future__ import annotations
from collections import defaultdict

from digitree.models.tree import Tree

CARD_W = 160
CARD_H = 80
H_GAP = 80
V_GAP = 40


def compute_layout(
    tree: Tree,
    version_id: str | None = None,
) -> dict[str, tuple[float, float]]:
    """Return {entry_id: (x, y)} for all entries visible under version_id.

    Entries that have been manually positioned (pos_x or pos_y non-zero) keep
    their stored position. Unpositioned entries are placed in stage columns.
    """
    if version_id:
        entries = [
            e for e in tree.entries
            if not e.version_ids or version_id in e.version_ids
        ]
    else:
        entries = list(tree.entries)

    stage_order = {s.id: s.order for s in tree.stages}

    # Compute auto-layout positions (stage columns, alphabetical within column)
    by_stage: dict[int, list] = defaultdict(list)
    for e in entries:
        order = stage_order.get(e.stage_id, 9999)
        by_stage[order].append(e)

    for order in by_stage:
        by_stage[order].sort(key=lambda e: e.name)

    auto: dict[str, tuple[float, float]] = {}
    for col_idx, order in enumerate(sorted(by_stage)):
        x = float(col_idx * (CARD_W + H_GAP))
        for row_idx, e in enumerate(by_stage[order]):
            y = float(row_idx * (CARD_H + V_GAP))
            auto[e.id] = (x, y)

    # Merge: prefer stored position when non-zero
    positions: dict[str, tuple[float, float]] = {}
    for e in entries:
        if e.pos_x != 0.0 or e.pos_y != 0.0:
            positions[e.id] = (e.pos_x, e.pos_y)
        else:
            positions[e.id] = auto.get(e.id, (0.0, 0.0))

    return positions
