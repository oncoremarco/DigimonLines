from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from digitree.models.tree import Tree, get_entry_display_name


class ConnectionsListPanel(QWidget):
    add_requested  = Signal()
    edit_requested = Signal(str)   # connection id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        tb = QHBoxLayout()
        btn_add = QPushButton("+ Add Connection")
        btn_add.clicked.connect(self.add_requested)
        tb.addWidget(btn_add)
        tb.addStretch()
        layout.addLayout(tb)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["From", "To", "Versions", "Requirements"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
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
        entry_map   = {e.id: get_entry_display_name(e) for e in tree.entries}
        version_map = {v.id: v.label  for v in tree.versions}

        for conn in tree.connections:
            row = self._table.rowCount()
            self._table.insertRow(row)

            from_item = QTableWidgetItem(entry_map.get(conn.from_entry_id, "—"))
            from_item.setData(Qt.UserRole, conn.id)
            self._table.setItem(row, 0, from_item)

            self._table.setItem(row, 1,
                QTableWidgetItem(entry_map.get(conn.to_entry_id, "—")))

            vers = ", ".join(version_map.get(vid, vid)
                             for vid in conn.version_ids) or "All"
            self._table.setItem(row, 2, QTableWidgetItem(vers))

            has_reqs = any(grp.conditions for grp in conn.req_groups)
            self._table.setItem(row, 3,
                QTableWidgetItem("Yes" if has_reqs else "—"))

    def _on_double_click(self, item: QTableWidgetItem):
        row = item.row()
        from_item = self._table.item(row, 0)
        if from_item:
            conn_id = from_item.data(Qt.UserRole)
            if conn_id:
                self.edit_requested.emit(conn_id)
