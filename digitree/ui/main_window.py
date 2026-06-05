from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QSplitter, QDialog,
    QStatusBar, QFileDialog, QMessageBox,
    QToolBar, QTabWidget, QWidget, QComboBox,
)
from PySide6.QtCore import Qt

from digitree.app_paths import TREES_DIR
from digitree.config import Config
from digitree.db.cache import CacheDB
from digitree.models.tree import Tree
from digitree.io.tree_xml import save_tree, load_tree
from digitree.ui.panels.sidebar import TreeSidebar
from digitree.ui.panels.entries_list import EntriesListPanel
from digitree.ui.panels.connections_list import ConnectionsListPanel
from digitree.widgets.growth_tree_canvas import GrowthTreeCanvas


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
        self._build_toolbar()
        self._build_menu()
        self._build_status_bar()

        self._sidebar.populate(self._config.recent_trees())
        self._set_tree_actions_enabled(False)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        splitter = QSplitter(Qt.Horizontal)

        # Left sidebar
        self._sidebar = TreeSidebar()
        self._sidebar.new_tree_requested.connect(self._on_new_tree)
        self._sidebar.tree_open_requested.connect(self._open_tree_from_path)

        # Center: tab widget with graph canvas + entries + connections lists
        self._center_tabs = QTabWidget()

        self._canvas = GrowthTreeCanvas()
        self._canvas.entry_double_clicked.connect(self._on_edit_entry)
        self._canvas.entry_moved.connect(self._on_entry_moved)
        self._center_tabs.addTab(self._canvas, "Graph")

        self._entries_panel = EntriesListPanel()
        self._entries_panel.add_requested.connect(self._on_add_entry)
        self._entries_panel.edit_requested.connect(self._on_edit_entry)
        self._connections_panel = ConnectionsListPanel()
        self._connections_panel.add_requested.connect(self._on_add_connection)
        self._connections_panel.edit_requested.connect(self._on_edit_connection)
        self._center_tabs.addTab(self._entries_panel, "Entries")
        self._center_tabs.addTab(self._connections_panel, "Connections")

        # Canvas placeholder (shown when no tree is open)
        self._no_tree_label = QLabel(
            "Canvas goes here\n\nCreate or open a tree to get started."
        )
        self._no_tree_label.setAlignment(Qt.AlignCenter)
        self._no_tree_label.setStyleSheet(
            "background:#ffffff; color:#aaa; font-size:14px;"
        )

        # Use a stacked-ish approach: swap between placeholder and tabs
        from PySide6.QtWidgets import QStackedWidget
        self._center_stack = QStackedWidget()
        self._center_stack.addWidget(self._no_tree_label)   # index 0
        self._center_stack.addWidget(self._center_tabs)      # index 1
        self._center_stack.setCurrentIndex(0)

        # Right profile placeholder
        self._profile_placeholder = QLabel("Profile panel")
        self._profile_placeholder.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._profile_placeholder.setMinimumWidth(240)
        self._profile_placeholder.setMaximumWidth(340)
        self._profile_placeholder.setStyleSheet(
            "background:#f8f8f8; border-left:1px solid #ccc; color:#aaa;"
        )

        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._center_stack)
        splitter.addWidget(self._profile_placeholder)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        tb = QToolBar("Tree Settings")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._action_stages   = tb.addAction("Stages",       self._on_edit_stages)
        self._action_types    = tb.addAction("Type Tags",    self._on_edit_type_tags)
        self._action_reqs     = tb.addAction("Req. Types",   self._on_edit_req_types)
        self._action_versions = tb.addAction("Versions",     self._on_edit_versions)
        tb.addSeparator()
        self._action_save     = tb.addAction("Save",         self._on_save)
        tb.addSeparator()
        self._action_fit      = tb.addAction("Fit View",     self._on_fit_view)
        tb.addSeparator()
        self._ver_filter_combo = QComboBox()
        self._ver_filter_combo.setMinimumWidth(110)
        self._ver_filter_combo.setToolTip("Filter graph by version")
        self._ver_filter_combo.currentIndexChanged.connect(self._on_version_filter_changed)
        tb.addWidget(self._ver_filter_combo)

        tb.addSeparator()
        self._stage_names_combo = QComboBox()
        self._stage_names_combo.setMinimumWidth(130)
        self._stage_names_combo.setToolTip("Stage naming convention")
        self._stage_names_combo.currentIndexChanged.connect(self._on_stage_names_changed)
        tb.addWidget(self._stage_names_combo)

    def _set_tree_actions_enabled(self, enabled: bool):
        for action in (self._action_stages, self._action_types,
                       self._action_reqs, self._action_versions,
                       self._action_save, self._action_fit):
            action.setEnabled(enabled)
        self._ver_filter_combo.setEnabled(enabled)
        self._stage_names_combo.setEnabled(enabled)

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
    # Tree settings dialogs
    # ------------------------------------------------------------------

    def _on_edit_stages(self):
        if not self._current_tree:
            return
        from digitree.ui.dialogs.stages_editor import StagesEditor
        dlg = StagesEditor(self._current_tree.stages, self)
        if dlg.exec() == QDialog.Accepted:
            self._current_tree.stages = dlg.get_stages()
            self._rebuild_stage_names_combo()
            self._refresh_panels()
            self._auto_save()

    def _on_edit_type_tags(self):
        if not self._current_tree:
            return
        from digitree.ui.dialogs.type_tags_editor import TypeTagsEditor
        dlg = TypeTagsEditor(self._current_tree.type_tags, self)
        if dlg.exec() == QDialog.Accepted:
            self._current_tree.type_tags = dlg.get_tags()
            self._refresh_panels()
            self._auto_save()

    def _on_edit_req_types(self):
        if not self._current_tree:
            return
        from digitree.ui.dialogs.req_types_editor import ReqTypesEditor
        dlg = ReqTypesEditor(self._current_tree.requirement_types, self)
        if dlg.exec() == QDialog.Accepted:
            self._current_tree.requirement_types = dlg.get_req_types()
            self._refresh_panels()
            self._auto_save()

    def _on_edit_versions(self):
        if not self._current_tree:
            return
        from digitree.ui.dialogs.versions_editor import VersionsEditor
        dlg = VersionsEditor(self._current_tree.versions, self)
        if dlg.exec() == QDialog.Accepted:
            self._current_tree.versions = dlg.get_versions()
            self._rebuild_version_filter()
            self._refresh_panels()
            self._auto_save()

    # ------------------------------------------------------------------
    # Entry operations
    # ------------------------------------------------------------------

    def _on_add_entry(self):
        if not self._current_tree:
            return
        from digitree.ui.dialogs.entry_editor import EntryEditor
        dlg = EntryEditor(self._current_tree, parent=self)
        if dlg.exec() == QDialog.Accepted and not dlg.was_deleted():
            self._current_tree.entries.append(dlg.get_entry())
            self._refresh_panels()
            self._auto_save()

    def _on_edit_entry(self, entry_id: str):
        if not self._current_tree:
            return
        entry = next((e for e in self._current_tree.entries
                      if e.id == entry_id), None)
        if entry is None:
            return
        from digitree.ui.dialogs.entry_editor import EntryEditor
        dlg = EntryEditor(self._current_tree, entry, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.was_deleted():
            self._current_tree.entries = [
                e for e in self._current_tree.entries if e.id != entry_id
            ]
            # also remove connections that reference this entry
            self._current_tree.connections = [
                c for c in self._current_tree.connections
                if c.from_entry_id != entry_id and c.to_entry_id != entry_id
            ]
        else:
            updated = dlg.get_entry()
            for i, e in enumerate(self._current_tree.entries):
                if e.id == entry_id:
                    self._current_tree.entries[i] = updated
                    break
        self._refresh_panels()
        self._auto_save()

    # ------------------------------------------------------------------
    # Connection operations
    # ------------------------------------------------------------------

    def _on_add_connection(self):
        if not self._current_tree:
            return
        if len(self._current_tree.entries) < 2:
            QMessageBox.information(self, "Not enough entries",
                                    "Add at least 2 entries before creating a connection.")
            return
        from digitree.ui.dialogs.connection_editor import ConnectionEditor
        dlg = ConnectionEditor(self._current_tree, parent=self)
        if dlg.exec() == QDialog.Accepted and not dlg.was_deleted():
            self._current_tree.connections.append(dlg.get_connection())
            self._refresh_panels()
            self._auto_save()

    def _on_edit_connection(self, conn_id: str):
        if not self._current_tree:
            return
        conn = next((c for c in self._current_tree.connections
                     if c.id == conn_id), None)
        if conn is None:
            return
        from digitree.ui.dialogs.connection_editor import ConnectionEditor
        dlg = ConnectionEditor(self._current_tree, conn, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.was_deleted():
            self._current_tree.connections = [
                c for c in self._current_tree.connections if c.id != conn_id
            ]
        else:
            updated = dlg.get_connection()
            for i, c in enumerate(self._current_tree.connections):
                if c.id == conn_id:
                    self._current_tree.connections[i] = updated
                    break
        self._refresh_panels()
        self._auto_save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_fit_view(self):
        self._canvas.fit_view()

    def _on_version_filter_changed(self, _idx: int):
        version_id = self._ver_filter_combo.currentData()
        self._canvas.set_version_filter(version_id or None)

    def _on_entry_moved(self, _entry_id: str, _x: float, _y: float):
        self._auto_save()

    def _rebuild_stage_names_combo(self):
        self._stage_names_combo.blockSignals(True)
        self._stage_names_combo.clear()
        if not self._current_tree:
            self._stage_names_combo.blockSignals(False)
            return
        self._stage_names_combo.addItem("Primary labels", 0)
        # Discover how many alias slots are populated across all stages
        max_aliases = max((len(s.aliases) for s in self._current_tree.stages), default=0)
        for slot in range(max_aliases):
            samples = [
                s.aliases[slot]
                for s in sorted(self._current_tree.stages, key=lambda x: x.order)
                if slot < len(s.aliases)
            ]
            preview = " / ".join(samples[:4])
            if len(samples) > 4:
                preview += "…"
            self._stage_names_combo.addItem(f"Alias {slot + 1}  ({preview})", slot + 1)
        # Restore saved selection
        stored = self._current_tree.stage_display_index
        for i in range(self._stage_names_combo.count()):
            if self._stage_names_combo.itemData(i) == stored:
                self._stage_names_combo.setCurrentIndex(i)
                break
        self._stage_names_combo.blockSignals(False)

    def _on_stage_names_changed(self, _idx: int):
        if not self._current_tree:
            return
        idx = self._stage_names_combo.currentData()
        if idx is None:
            return
        self._current_tree.stage_display_index = idx
        self._refresh_panels()
        self._auto_save()

    def _rebuild_version_filter(self):
        self._ver_filter_combo.blockSignals(True)
        self._ver_filter_combo.clear()
        self._ver_filter_combo.addItem("All versions", None)
        if self._current_tree:
            for v in self._current_tree.versions:
                self._ver_filter_combo.addItem(v.label, v.id)
        self._ver_filter_combo.blockSignals(False)

    def _set_current_tree(self, tree: Tree, path: Path):
        self._current_tree = tree
        self._current_path = path
        self._update_title()
        self._rebuild_version_filter()
        self._rebuild_stage_names_combo()
        self._set_tree_actions_enabled(True)
        self._center_stack.setCurrentIndex(1)
        self._refresh_panels()

    def _refresh_panels(self):
        if self._current_tree:
            self._entries_panel.refresh(self._current_tree)
            self._connections_panel.refresh(self._current_tree)
            self._canvas.set_tree(self._current_tree)

    def _auto_save(self):
        if self._current_tree and self._current_path:
            save_tree(self._current_tree, self._current_path)
            self._status.showMessage(f"Saved: {self._current_path.name}")

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
        QMessageBox.about(self, "DigiTree",
                          "DigiTree — Digimon growth tree builder\nPhase 1–2")

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
