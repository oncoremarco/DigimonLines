from __future__ import annotations
import math

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsPathItem,
    QStyle, QStyleOptionGraphicsItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPixmap,
)

from digitree.models.tree import Tree, get_entry_display_name
from digitree.widgets.graph_canvas import GraphCanvas

CARD_W: float = 160.0
CARD_H: float = 80.0
HEADER_H: float = 18.0
BADGE_R: float = 9.0      # badge radius
ARROW_LEN: float = 10.0
ARROW_HALF: float = 5.0


# ---------------------------------------------------------------------------
# Entry card item
# ---------------------------------------------------------------------------

class _EntryCardItem(QGraphicsObject):
    double_clicked = Signal(str)
    position_changed = Signal(str, float, float)

    def __init__(
        self,
        entry_id: str,
        name: str,
        stage_color: str,
        type_symbols: list[tuple[str, str]],
        has_wikimon: bool,
        pixmap: QPixmap | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._entry_id = entry_id
        self._name = name
        self._stage_color = QColor(stage_color or "#888888")
        self._type_symbols = type_symbols  # [(symbol, color), ...]
        self._has_wikimon = has_wikimon
        self._pixmap = pixmap
        self._hovered = False

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

    # -- QGraphicsItem interface -------------------------------------------

    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, CARD_W + 4, CARD_H + 4)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ):
        selected = bool(option.state & QStyle.State_Selected)

        # Drop shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 25)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(3, 3, CARD_W, CARD_H, 6, 6)

        # Card background
        painter.setBrush(QBrush(QColor("#ffffff")))
        border = QColor("#4a90d9") if selected else (
            QColor("#aaaaaa") if self._hovered else QColor("#cccccc")
        )
        painter.setPen(QPen(border, 2.0 if (selected or self._hovered) else 1.0))
        painter.drawRoundedRect(0, 0, CARD_W, CARD_H, 6, 6)

        # Stage color header strip
        painter.setBrush(QBrush(self._stage_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, CARD_W, HEADER_H + 6, 6, 6)
        painter.drawRect(0, int(HEADER_H / 2), int(CARD_W), int(HEADER_H / 2) + 3)

        # Sprite/image thumbnail
        img_w = 0.0
        if self._pixmap and not self._pixmap.isNull():
            ih = CARD_H - HEADER_H - 8
            iw = ih
            px = self._pixmap.scaled(
                int(iw), int(ih), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            painter.drawPixmap(6, int(HEADER_H) + 4, px)
            img_w = iw + 6

        # Name text
        text_x = 8.0 + img_w
        text_rect = QRectF(
            text_x, HEADER_H + 2, CARD_W - text_x - 6, CARD_H - HEADER_H - 4
        )
        f = QFont("Arial", 9)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor("#222222"))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self._name)

        # Type symbol badges (bottom-right)
        if self._type_symbols:
            bx = CARD_W - 4
            by = CARD_H - 4
            f2 = QFont("Arial", 7)
            f2.setBold(True)
            painter.setFont(f2)
            for sym, color in reversed(self._type_symbols):
                bx -= BADGE_R * 2 + 2
                br = QRectF(bx, by - BADGE_R * 2, BADGE_R * 2, BADGE_R * 2)
                painter.setBrush(QBrush(QColor(color or "#888888")))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(br)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(br, Qt.AlignCenter, sym[:2] if sym else "?")

        # Wikimon badge (top-right of header)
        if self._has_wikimon:
            wr = QRectF(CARD_W - 17, 2, 15, 14)
            painter.setBrush(QBrush(QColor("#1a6bb5")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(wr, 2, 2)
            f3 = QFont("Arial", 7)
            f3.setBold(True)
            painter.setFont(f3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(wr, Qt.AlignCenter, "W")

    # -- signals / events --------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.position_changed.emit(self._entry_id, float(value.x()), float(value.y()))
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self._entry_id)
        super().mouseDoubleClickEvent(event)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    # -- connection attachment points -------------------------------------

    def right_pt(self) -> QPointF:
        return self.scenePos() + QPointF(CARD_W, CARD_H / 2)

    def left_pt(self) -> QPointF:
        return self.scenePos() + QPointF(0.0, CARD_H / 2)

    def bottom_pt(self) -> QPointF:
        return self.scenePos() + QPointF(CARD_W / 2, CARD_H)

    def top_pt(self) -> QPointF:
        return self.scenePos() + QPointF(CARD_W / 2, 0.0)


# ---------------------------------------------------------------------------
# Arrow item
# ---------------------------------------------------------------------------

class _ArrowItem(QGraphicsPathItem):
    def __init__(
        self,
        from_card: _EntryCardItem,
        to_card: _EntryCardItem,
        style: str = "normal",
        parent=None,
    ):
        super().__init__(parent)
        self._from_card = from_card
        self._to_card = to_card
        self._style = style
        self.setZValue(0)
        self.setBrush(Qt.NoBrush)
        self.refresh()

    def refresh(self):
        fp = self._from_card.pos()
        tp = self._to_card.pos()

        fx = fp.x() + CARD_W
        fy = fp.y() + CARD_H / 2
        tx = tp.x()
        ty = tp.y() + CARD_H / 2

        going_right = fx < tx - 10

        if going_right:
            p1 = QPointF(fx, fy)
            p2 = QPointF(tx, ty)
            cx = (fx + tx) / 2
            c1 = QPointF(cx, fy)
            c2 = QPointF(cx, ty)
            # tangent at end: 3*(p2 - c2) direction
            tdx = p2.x() - c2.x()
            tdy = p2.y() - c2.y()
        else:
            # Route below both cards
            offset = max(50.0, abs(fy - ty) * 0.25 + 30)
            p1 = QPointF(fp.x() + CARD_W / 2, fp.y() + CARD_H)
            p2 = QPointF(tp.x() + CARD_W / 2, tp.y() + CARD_H)
            c1 = QPointF(p1.x(), p1.y() + offset)
            c2 = QPointF(p2.x(), p2.y() + offset)
            tdx = p2.x() - c2.x()
            tdy = p2.y() - c2.y()

        path = QPainterPath()
        path.moveTo(p1)
        path.cubicTo(c1, c2, p2)

        # Arrowhead
        tlen = math.hypot(tdx, tdy)
        if tlen > 0.5:
            ux, uy = tdx / tlen, tdy / tlen
        else:
            ux, uy = (1.0, 0.0) if going_right else (0.0, -1.0)

        al = ARROW_LEN
        ah = ARROW_HALF
        left_pt = QPointF(p2.x() - al * ux + ah * uy, p2.y() - al * uy - ah * ux)
        right_pt = QPointF(p2.x() - al * ux - ah * uy, p2.y() - al * uy + ah * ux)
        path.moveTo(p2)
        path.lineTo(left_pt)
        path.moveTo(p2)
        path.lineTo(right_pt)

        self.prepareGeometryChange()
        self.setPath(path)

        pen = QPen(QColor("#555555"), 1.5)
        if self._style == "dashed_failure":
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([5, 3])
        self.setPen(pen)


# ---------------------------------------------------------------------------
# Growth tree canvas
# ---------------------------------------------------------------------------

class GrowthTreeCanvas(GraphCanvas):
    entry_double_clicked = Signal(str)
    entry_moved = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tree: Tree | None = None
        self._version_filter: str | None = None
        self._cards: dict[str, _EntryCardItem] = {}
        self._arrows: list[_ArrowItem] = []
        self._scene.setBackgroundBrush(QBrush(QColor("#ebebeb")))

    # -- public API --------------------------------------------------------

    def set_tree(self, tree: Tree):
        self._tree = tree
        self.refresh()

    def set_version_filter(self, version_id: str | None):
        self._version_filter = version_id
        self.refresh()

    def refresh(self):
        self._scene.clear()
        self._cards.clear()
        self._arrows.clear()

        if not self._tree:
            return

        from digitree.layout.tree_layout import compute_layout
        positions = compute_layout(self._tree, self._version_filter)

        stage_map = {s.id: s for s in self._tree.stages}
        tag_map = {t.id: t for t in self._tree.type_tags}

        if self._version_filter:
            visible = [
                e for e in self._tree.entries
                if not e.version_ids or self._version_filter in e.version_ids
            ]
        else:
            visible = list(self._tree.entries)

        visible_ids = {e.id for e in visible}

        # Create entry cards
        for entry in visible:
            pos = positions.get(entry.id, (0.0, 0.0))

            stage = stage_map.get(entry.stage_id)
            stage_color = stage.color if stage else "#888888"

            type_symbols = []
            for tid in entry.type_tag_ids:
                tag = tag_map.get(tid)
                if tag:
                    type_symbols.append((tag.symbol or tag.label[:2], tag.color or "#888888"))

            pixmap: QPixmap | None = None
            if entry.image_local:
                px = QPixmap(entry.image_local)
                if not px.isNull():
                    pixmap = px

            card = _EntryCardItem(
                entry_id=entry.id,
                name=get_entry_display_name(entry),
                stage_color=stage_color,
                type_symbols=type_symbols,
                has_wikimon=bool(entry.wikimon_key),
                pixmap=pixmap,
            )
            card.setPos(pos[0], pos[1])
            card.double_clicked.connect(self.entry_double_clicked)
            card.position_changed.connect(self._on_card_moved)
            self._scene.addItem(card)
            self._cards[entry.id] = card

        # Create arrows
        for conn in self._tree.connections:
            if conn.from_entry_id not in visible_ids or conn.to_entry_id not in visible_ids:
                continue
            if self._version_filter and conn.version_ids:
                if self._version_filter not in conn.version_ids:
                    continue
            from_card = self._cards.get(conn.from_entry_id)
            to_card = self._cards.get(conn.to_entry_id)
            if from_card and to_card:
                arrow = _ArrowItem(from_card, to_card, conn.style)
                self._scene.addItem(arrow)
                self._arrows.append(arrow)

    # -- private slots -----------------------------------------------------

    def _on_card_moved(self, entry_id: str, x: float, y: float):
        if self._tree:
            for e in self._tree.entries:
                if e.id == entry_id:
                    e.pos_x = x
                    e.pos_y = y
                    break
        card = self._cards.get(entry_id)
        if card:
            for arrow in self._arrows:
                if arrow._from_card is card or arrow._to_card is card:
                    arrow.refresh()
        self.entry_moved.emit(entry_id, x, y)
