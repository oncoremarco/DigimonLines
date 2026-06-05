from __future__ import annotations
import uuid
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QFormLayout, QDialogButtonBox, QComboBox,
)
from PySide6.QtCore import Qt

from digitree.models.tree import RequirementType

_VALUE_TYPES = ["range", "threshold", "min_count", "boolean"]


class ReqTypesEditor(QDialog):
    def __init__(self, req_types: list[RequirementType], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Requirement Types")
        self.setMinimumSize(560, 380)
        self._items = [copy.copy(r) for r in req_types]
        self._updating = False
        self._build()
        self._populate()

    def _build(self):
        root = QVBoxLayout(self)
        body = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Requirement Types:"))
        self._list = QListWidget()
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

        self._vtype_combo = QComboBox()
        self._vtype_combo.addItems(_VALUE_TYPES)
        self._vtype_combo.currentIndexChanged.connect(self._on_vtype_changed)

        self._symbol_edit = QLineEdit()
        self._symbol_edit.setMaxLength(4)
        self._symbol_edit.setFixedWidth(60)
        self._symbol_edit.textChanged.connect(self._on_symbol_changed)

        form.addRow("Label:", self._label_edit)
        form.addRow("Value type:", self._vtype_combo)
        form.addRow("Symbol:", self._symbol_edit)
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
        for r in self._items:
            self._list.addItem(self._make_item(r))
        if self._list.count():
            self._list.setCurrentRow(0)

    def _make_item(self, r: RequirementType) -> QListWidgetItem:
        item = QListWidgetItem(f"{r.label}  [{r.value_type}]")
        item.setData(Qt.UserRole, r.id)
        return item

    def _current(self) -> RequirementType | None:
        row = self._list.currentRow()
        if row < 0:
            return None
        rid = self._list.item(row).data(Qt.UserRole)
        return next((r for r in self._items if r.id == rid), None)

    def _on_select(self, _row: int):
        r = self._current()
        if r is None:
            return
        self._updating = True
        self._label_edit.setText(r.label)
        idx = _VALUE_TYPES.index(r.value_type) if r.value_type in _VALUE_TYPES else 0
        self._vtype_combo.setCurrentIndex(idx)
        self._symbol_edit.setText(r.symbol)
        self._updating = False

    def _refresh_item(self):
        row = self._list.currentRow()
        r = self._current()
        if row >= 0 and r:
            self._list.item(row).setText(f"{r.label}  [{r.value_type}]")

    def _on_label_changed(self, text: str):
        if self._updating:
            return
        r = self._current()
        if r:
            r.label = text
            self._refresh_item()

    def _on_vtype_changed(self, _idx: int):
        if self._updating:
            return
        r = self._current()
        if r:
            r.value_type = self._vtype_combo.currentText()
            self._refresh_item()

    def _on_symbol_changed(self, text: str):
        if self._updating:
            return
        r = self._current()
        if r:
            r.symbol = text

    def _on_add(self):
        r = RequirementType(str(uuid.uuid4())[:8], "New Requirement", "range", "?")
        self._items.append(r)
        self._list.addItem(self._make_item(r))
        self._list.setCurrentRow(self._list.count() - 1)
        self._label_edit.selectAll()
        self._label_edit.setFocus()

    def _on_delete(self):
        row = self._list.currentRow()
        if row < 0:
            return
        rid = self._list.item(row).data(Qt.UserRole)
        self._items = [r for r in self._items if r.id != rid]
        self._list.takeItem(row)

    def get_req_types(self) -> list[RequirementType]:
        return self._items
