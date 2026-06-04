from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QSplitter,
    QStatusBar, QFileDialog, QMessageBox, QDialog,
)
from PySide6.QtCore import Qt

from digitree.app_paths import TREES_DIR
from digitree.config import Config
from digitree.db.cache import CacheDB
from digitree.models.tree import Tree
from digitree.io.tree_xml import save_tree, load_tree
from digitree.ui.panels.sidebar import TreeSidebar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config = Config()
        self._db = CacheDB()
        self._current_tree: Tree | None = None
        self._current_path: Path | None = None

        self.setWindowTitle("DigiTree")
        self.resize(1280, 800)
        self._restore_geometry()

        self._build_layout()
        self._build_menu()
        self._build_status_bar()

        self._sidebar.populate(self._config.recent_trees())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        splitter = QSplitter(Qt.Horizontal)

        self._sidebar = TreeSidebar()
        self._sidebar.new_tree_requested.connect(self._on_new_tree)
        self._sidebar.tree_open_requested.connect(self._open_tree_from_path)

        self._canvas_placeholder = QLabel(
            "Canvas goes here\n\nCreate or open a tree to get started."
        )
        self._canvas_placeholder.setAlignment(Qt.AlignCenter)
        self._canvas_placeholder.setStyleSheet(
            "background:#ffffff; color:#aaa; font-size:14px;"
        )

        self._profile_placeholder = QLabel("Profile panel")
        self._profile_placeholder.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._profile_placeholder.setMinimumWidth(240)
        self._profile_placeholder.setMaximumWidth(340)
        self._profile_placeholder.setStyleSheet(
            "background:#f8f8f8; border-left:1px solid #ccc; color:#aaa;"
        )

        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._canvas_placeholder)
        splitter.addWidget(self._profile_placeholder)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction("New Tree",   self._on_new_tree)
        file_menu.addAction("Open Tree…", self._on_open_tree)
        file_menu.addSeparator()
        file_menu.addAction("Save",       self._on_save)
        file_menu.addAction("Save As…",   self._on_save_as)
        file_menu.addSeparator()
        file_menu.addAction("Exit",       self.close)

        mb.addMenu("&View").addAction("(Coming soon)")
        mb.addMenu("&Help").addAction("About DigiTree", self._on_about)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ------------------------------------------------------------------
    # Tree operations
    # ------------------------------------------------------------------

    def _on_new_tree(self):
        from digitree.ui.dialogs.new_tree_dialog import NewTreeDialog
        dlg = NewTreeDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        tree = dlg.get_tree()
        if tree is None:
            return

        path = self._pick_save_path(tree.name)
        if not path:
            return

        save_tree(tree, path)
        self._config.add_recent_tree(str(path))
        self._config.save()
        self._set_current_tree(tree, path)
        self._sidebar.populate(self._config.recent_trees())
        self._status.showMessage(f"Created: {path.name}")

    def _on_open_tree(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Tree", str(TREES_DIR), "DigiTree Files (*.dtree.xml)"
        )
        if path_str:
            self._open_tree_from_path(path_str)

    def _open_tree_from_path(self, path_str: str):
        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self, "File not found",
                                f"Could not find:\n{path_str}")
            self._config.remove_recent_tree(path_str)
            self._config.save()
            self._sidebar.populate(self._config.recent_trees())
            return
        try:
            tree = load_tree(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error loading tree", str(exc))
            return

        self._config.add_recent_tree(str(path))
        self._config.save()
        self._set_current_tree(tree, path)
        self._sidebar.populate(self._config.recent_trees())
        self._status.showMessage(f"Opened: {path.name}")

    def _on_save(self):
        if self._current_tree is None:
            self._status.showMessage("No tree open.")
            return
        if self._current_path is None:
            self._on_save_as()
            return
        save_tree(self._current_tree, self._current_path)
        self._config.add_recent_tree(str(self._current_path))
        self._config.save()
        self._status.showMessage(f"Saved: {self._current_path.name}")

    def _on_save_as(self):
        if self._current_tree is None:
            self._status.showMessage("No tree open.")
            return
        path = self._pick_save_path(self._current_tree.name)
        if not path:
            return
        save_tree(self._current_tree, path)
        self._current_path = path
        self._config.add_recent_tree(str(path))
        self._config.save()
        self._update_title()
        self._sidebar.populate(self._config.recent_trees())
        self._status.showMessage(f"Saved: {path.name}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_current_tree(self, tree: Tree, path: Path):
        self._current_tree = tree
        self._current_path = path
        self._update_title()

    def _update_title(self):
        if self._current_tree:
            self.setWindowTitle(f"DigiTree — {self._current_tree.name}")
        else:
            self.setWindowTitle("DigiTree")

    def _pick_save_path(self, suggested_name: str) -> Path | None:
        TREES_DIR.mkdir(parents=True, exist_ok=True)
        safe = suggested_name.replace(" ", "_").replace("/", "-")
        default = str(TREES_DIR / f"{safe}.dtree.xml")
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Tree As", default, "DigiTree Files (*.dtree.xml)"
        )
        return Path(path_str) if path_str else None

    def _on_about(self):
        QMessageBox.about(
            self, "DigiTree",
            "DigiTree — Digimon growth tree builder\nPhase 1"
        )

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _restore_geometry(self):
        geo = self._config.get("window_geometry", {})
        if geo:
            self.resize(geo.get("width", 1280), geo.get("height", 800))
            self.move(geo.get("x", 100), geo.get("y", 100))

    def closeEvent(self, event):
        geo = self.geometry()
        self._config.set("window_geometry", {
            "x": geo.x(), "y": geo.y(),
            "width": geo.width(), "height": geo.height(),
        })
        self._config.save()
        if self._db:
            self._db.close()
        super().closeEvent(event)
