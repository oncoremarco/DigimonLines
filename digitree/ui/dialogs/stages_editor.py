from __future__ import annotations
import uuid
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QPlainTextEdit, QFormLayout, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from digitree.models.tree import Stage
from digitree.ui.widgets import ColorButton


class StagesEditor(QDialog):
    def __init__(self, stages: list[Stage], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Stages")
        self.setMinimumSize(520, 400)
        self._items = [copy.deepcopy(s) for s in stages]
        self._updating = False
        self._build()
        self._populate()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)

        body = QHBoxLayout()

        # --- Left: list -----------------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Stages  (drag to reorder):"))

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list)

        list_btns = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._on_add)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._on_delete)
        list_btns.addWidget(btn_add)
        list_btns.addWidget(btn_del)
        left.addLayout(list_btns)

        # --- Right: form ----------------------------------------------
        right = QVBoxLayout()
        right.addWidget(QLabel("Edit selected:"))

        form = QFormLayout()
        self._label_edit = QLineEdit()
        self._label_edit.textChanged.connect(self._on_label_changed)
        self._color_btn = ColorButton()
        self._color_btn.color_changed.connect(self._on_color_changed)
        form.addRow("Label:", self._label_edit)
        form.addRow("Color:", self._color_btn)
        right.addLayout(form)

        right.addWidget(QLabel(
            "Aliases  (one per line — slot 1 = JP name, slot 2 = EN dub name, …):"
        ))
        self._aliases_edit = QPlainTextEdit()
        self._aliases_edit.setMaximumHeight(80)
        self._aliases_edit.setPlaceholderText("e.g.\nChild\nRookie")
        self._aliases_edit.textChanged.connect(self._on_aliases_changed)
        right.addWidget(self._aliases_edit)
        right.addStretch()

        body.addLayout(left, 2)
        body.addLayout(right, 1)
        root.addLayout(body)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Populate / select
    # ------------------------------------------------------------------

    def _populate(self):
        self._list.clear()
        for s in self._items:
            self._list.addItem(self._make_item(s))
        if self._list.count():
            self._list.setCurrentRow(0)

    def _make_item(self, s: Stage) -> QListWidgetItem:
        item = QListWidgetItem(s.label)
        item.setData(Qt.UserRole, s.id)
        return item

    def _current(self) -> Stage | None:
        row = self._list.currentRow()
        if row < 0:
            return None
        sid = self._list.item(row).data(Qt.UserRole)
        return next((s for s in self._items if s.id == sid), None)

    def _on_select(self, _row: int):
        s = self._current()
        if s is None:
            return
        self._updating = True
        self._label_edit.setText(s.label)
        self._color_btn.set_color(s.color)
        self._aliases_edit.setPlainText("\n".join(s.aliases))
        self._updating = False

    # ------------------------------------------------------------------
    # Live sync
    # ------------------------------------------------------------------

    def _on_label_changed(self, text: str):
        if self._updating:
            return
        s = self._current()
        if s:
            s.label = text
            row = self._list.currentRow()
            if row >= 0:
                self._list.item(row).setText(text)

    def _on_color_changed(self, color: str):
        s = self._current()
        if s:
            s.color = color

    def _on_aliases_changed(self):
        if self._updating:
            return
        s = self._current()
        if s:
            s.aliases = [
                line.strip()
                for line in self._aliases_edit.toPlainText().splitlines()
                if line.strip()
            ]

    # ------------------------------------------------------------------
    # Add / Delete
    # ------------------------------------------------------------------

    def _on_add(self):
        s = Stage(str(uuid.uuid4())[:8], "New Stage",
                  len(self._items) + 1, "#CCCCCC")
        self._items.append(s)
        self._list.addItem(self._make_item(s))
        self._list.setCurrentRow(self._list.count() - 1)
        self._label_edit.selectAll()
        self._label_edit.setFocus()

    def _on_delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        sid = self._list.item(row).data(Qt.UserRole)
        self._items = [s for s in self._items if s.id != sid]
        self._list.takeItem(row)

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def _on_accept(self):
        result: list[Stage] = []
        for i in range(self._list.count()):
            sid = self._list.item(i).data(Qt.UserRole)
            s = next((x for x in self._items if x.id == sid), None)
            if s:
                s.order = i + 1
                result.append(s)
        self._items = result
        self.accept()

    def get_stages(self) -> list[Stage]:
        return self._items
