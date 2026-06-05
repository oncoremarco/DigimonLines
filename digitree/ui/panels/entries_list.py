from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from digitree.models.tree import Tree, Entry, get_stage_label, get_entry_display_name


class EntriesListPanel(QWidget):
    add_requested  = Signal()
    edit_requested = Signal(str)   # entry id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        tb = QHBoxLayout()
        btn_add = QPushButton("+ Add Entry")
        btn_add.clicked.connect(self.add_requested)
        tb.addWidget(btn_add)
        tb.addStretch()
        layout.addLayout(tb)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Name", "Stage", "Type Tags", "Wikimon"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

    def refresh(self, tree: Tree):
        self._table.setRowCount(0)
        stage_map = {s.id: s for s in tree.stages}
        tag_map   = {t.id: t.label for t in tree.type_tags}

        for entry in tree.entries:
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = QTableWidgetItem(get_entry_display_name(entry))
            name_item.setData(Qt.UserRole, entry.id)
            self._table.setItem(row, 0, name_item)

            stage = stage_map.get(entry.stage_id)
            stage_label = get_stage_label(stage, tree.stage_display_index) if stage else "—"
            self._table.setItem(row, 1, QTableWidgetItem(stage_label))

            tags = ", ".join(tag_map.get(tid, tid) for tid in entry.type_tag_ids)
            self._table.setItem(row, 2, QTableWidgetItem(tags or "—"))

            wiki = "✓" if entry.wikimon_key else "—"
            self._table.setItem(row, 3, QTableWidgetItem(wiki))

        self._table.sortItems(0)

    def _on_double_click(self, item: QTableWidgetItem):
        row = item.row()
        name_item = self._table.item(row, 0)
        if name_item:
            entry_id = name_item.data(Qt.UserRole)
            if entry_id:
                self.edit_requested.emit(entry_id)
