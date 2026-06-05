from __future__ import annotations
import uuid
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QFormLayout, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from digitree.models.tree import Version
from digitree.ui.widgets import ColorButton


class VersionsEditor(QDialog):
    def __init__(self, versions: list[Version], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Versions")
        self.setMinimumSize(480, 340)
        self._items = [copy.copy(v) for v in versions]
        self._updating = False
        self._build()
        self._populate()

    def _build(self):
        root = QVBoxLayout(self)
        body = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Versions:"))
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
        self._color_btn = ColorButton()
        self._color_btn.color_changed.connect(self._on_color_changed)
        form.addRow("Label:", self._label_edit)
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
        for v in self._items:
            self._list.addItem(self._make_item(v))
        if self._list.count():
            self._list.setCurrentRow(0)

    def _make_item(self, v: Version) -> QListWidgetItem:
        item = QListWidgetItem(v.label)
        item.setData(Qt.UserRole, v.id)
        return item

    def _current(self) -> Version | None:
        row = self._list.currentRow()
        if row < 0:
            return None
        vid = self._list.item(row).data(Qt.UserRole)
        return next((v for v in self._items if v.id == vid), None)

    def _on_select(self, _row: int):
        v = self._current()
        if v is None:
            return
        self._updating = True
        self._label_edit.setText(v.label)
        self._color_btn.set_color(v.color)
        self._updating = False

    def _on_label_changed(self, text: str):
        if self._updating:
            return
        v = self._current()
        if v:
            v.label = text
            row = self._list.currentRow()
            if row >= 0:
                self._list.item(row).setText(text)

    def _on_color_changed(self, color: str):
        v = self._current()
        if v:
            v.color = color

    def _on_add(self):
        v = Version(str(uuid.uuid4())[:8], "New Version", "#888888")
        self._items.append(v)
        self._list.addItem(self._make_item(v))
        self._list.setCurrentRow(self._list.count() - 1)
        self._label_edit.selectAll()
        self._label_edit.setFocus()

    def _on_delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        vid = self._list.item(row).data(Qt.UserRole)
        self._items = [v for v in self._items if v.id != vid]
        self._list.takeItem(row)

    def get_versions(self) -> list[Version]:
        return self._items
