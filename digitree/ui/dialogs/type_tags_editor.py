from __future__ import annotations
import uuid
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QFormLayout, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from digitree.models.tree import TypeTag
from digitree.ui.widgets import ColorButton


class TypeTagsEditor(QDialog):
    def __init__(self, tags: list[TypeTag], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Type Tags")
        self.setMinimumSize(520, 360)
        self._items = [copy.copy(t) for t in tags]
        self._updating = False
        self._build()
        self._populate()

    def _build(self):
        root = QVBoxLayout(self)
        body = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Type Tags:"))
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list)

        btns = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._on_add)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._on_delete)
        btns.addWidget(btn_add)
        btns.addWidget(btn_del)
        left.addLayout(btns)

        right = QVBoxLayout()
        right.addWidget(QLabel("Edit selected:"))
        form = QFormLayout()
        self._label_edit = QLineEdit()
        self._label_edit.textChanged.connect(self._on_label_changed)
        self._symbol_edit = QLineEdit()
        self._symbol_edit.setMaxLength(4)
        self._symbol_edit.setFixedWidth(60)
        self._symbol_edit.textChanged.connect(self._on_symbol_changed)
        self._color_btn = ColorButton()
        self._color_btn.color_changed.connect(self._on_color_changed)
        form.addRow("Label:", self._label_edit)
        form.addRow("Symbol:", self._symbol_edit)
        form.addRow("Color:", self._color_btn)
        right.addLayout(form)
        right.addStretch()

        body.addLayout(left, 2)
        body.addLayout(right, 1)
        root.addLayout(body)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _populate(self):
        self._list.clear()
        for t in self._items:
            self._list.addItem(self._make_item(t))
        if self._list.count():
            self._list.setCurrentRow(0)

    def _make_item(self, t: TypeTag) -> QListWidgetItem:
        item = QListWidgetItem(f"{t.label}  [{t.symbol}]")
        item.setData(Qt.UserRole, t.id)
        return item

    def _current(self) -> TypeTag | None:
        row = self._list.currentRow()
        if row < 0:
            return None
        tid = self._list.item(row).data(Qt.UserRole)
        return next((t for t in self._items if t.id == tid), None)

    def _on_select(self, _row: int):
        t = self._current()
        if t is None:
            return
        self._updating = True
        self._label_edit.setText(t.label)
        self._symbol_edit.setText(t.symbol)
        self._color_btn.set_color(t.color)
        self._updating = False

    def _refresh_item(self):
        row = self._list.currentRow()
        t = self._current()
        if row >= 0 and t:
            self._list.item(row).setText(f"{t.label}  [{t.symbol}]")

    def _on_label_changed(self, text: str):
        if self._updating:
            return
        t = self._current()
        if t:
            t.label = text
            self._refresh_item()

    def _on_symbol_changed(self, text: str):
        if self._updating:
            return
        t = self._current()
        if t:
            t.symbol = text
            self._refresh_item()

    def _on_color_changed(self, color: str):
        t = self._current()
        if t:
            t.color = color

    def _on_add(self):
        t = TypeTag(str(uuid.uuid4())[:8], "New Tag", "#888888", "?")
        self._items.append(t)
        self._list.addItem(self._make_item(t))
        self._list.setCurrentRow(self._list.count() - 1)
        self._label_edit.selectAll()
        self._label_edit.setFocus()

    def _on_delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        tid = self._list.item(row).data(Qt.UserRole)
        self._items = [t for t in self._items if t.id != tid]
        self._list.takeItem(row)

    def get_tags(self) -> list[TypeTag]:
        return self._items
