from __future__ import annotations
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QFrame, QFileDialog,
)
from PySide6.QtCore import Qt, Signal


class TreeSidebar(QWidget):
    tree_open_requested = Signal(str)
    new_tree_requested  = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(280)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  My Trees")
        header.setStyleSheet(
            "background:#e0e0e0; color:#333; font-weight:bold; padding:8px 4px;"
        )
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setStyleSheet(
            "QListWidget { border:none; font-size:12px; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background:#cce4ff; color:#000; }"
        )
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list, stretch=1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(8, 8, 8, 8)
        btn_layout.setSpacing(4)

        btn_new = QPushButton("+ New Tree")
        btn_new.clicked.connect(self.new_tree_requested)
        btn_layout.addWidget(btn_new)

        btn_open = QPushButton("Open Tree…")
        btn_open.clicked.connect(self._on_open_clicked)
        btn_layout.addWidget(btn_open)

        layout.addWidget(btn_widget)

    # -- Public API ----------------------------------------------------

    def populate(self, paths: list[str]) -> None:
        self._list.clear()
        for p in paths:
            self._add_item(p)

    def _add_item(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            return
        item = QListWidgetItem()
        name = path.stem.replace("_", " ")
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            date_str = mtime.strftime("%Y-%m-%d")
        except Exception:
            date_str = ""
        item.setText(f"{name}\n{date_str}")
        item.setData(Qt.UserRole, str(path))
        item.setToolTip(str(path))
        self._list.addItem(item)

    # -- Slots ---------------------------------------------------------

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.tree_open_requested.emit(path)

    def _on_open_clicked(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Tree", "", "DigiTree Files (*.dtree.xml)"
        )
        if path_str:
            self.tree_open_requested.emit(path_str)
