from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QLabel, QSplitter,
    QStatusBar, QMenuBar, QMenu,
)
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DigiTree")
        self.resize(1280, 800)
        self._build_menu()
        self._build_layout()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        splitter = QSplitter(Qt.Horizontal)

        self._sidebar = QLabel("Sidebar")
        self._sidebar.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._sidebar.setMinimumWidth(200)
        self._sidebar.setMaximumWidth(280)
        self._sidebar.setStyleSheet("background:#f0f0f0; border-right:1px solid #ccc;")

        self._canvas_placeholder = QLabel("Canvas goes here")
        self._canvas_placeholder.setAlignment(Qt.AlignCenter)
        self._canvas_placeholder.setStyleSheet("background:#ffffff;")

        self._profile_placeholder = QLabel("Profile panel")
        self._profile_placeholder.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._profile_placeholder.setMinimumWidth(240)
        self._profile_placeholder.setMaximumWidth(340)
        self._profile_placeholder.setStyleSheet("background:#f8f8f8; border-left:1px solid #ccc;")

        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._canvas_placeholder)
        splitter.addWidget(self._profile_placeholder)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction("New Tree", self._on_new_tree)
        file_menu.addAction("Open Tree…", self._on_open_tree)
        file_menu.addSeparator()
        file_menu.addAction("Save", self._on_save)
        file_menu.addAction("Save As…", self._on_save_as)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        view_menu = menubar.addMenu("&View")
        view_menu.addAction("(Coming soon)")

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("About DigiTree", self._on_about)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ------------------------------------------------------------------
    # Stubs — wired up in later steps
    # ------------------------------------------------------------------

    def _on_new_tree(self):
        self._status.showMessage("New Tree — coming in Step 7")

    def _on_open_tree(self):
        self._status.showMessage("Open Tree — coming in Step 8")

    def _on_save(self):
        self._status.showMessage("Save — coming in Step 4")

    def _on_save_as(self):
        self._status.showMessage("Save As — coming in Step 4")

    def _on_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "DigiTree", "DigiTree — Digimon growth tree builder\nPhase 1 skeleton")
