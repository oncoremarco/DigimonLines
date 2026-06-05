from __future__ import annotations
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QCheckBox, QComboBox,
    QPushButton, QDialogButtonBox, QFrame,
    QFileDialog, QScrollArea, QWidget, QSizePolicy,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from digitree.models.tree import Tree, Entry


class EntryEditor(QDialog):
    def __init__(self, tree: Tree, entry: Entry | None = None, parent=None):
        super().__init__(parent)
        self._tree = tree
        self._entry = copy.deepcopy(entry) if entry else Entry()
        self._is_new = entry is None
        self._delete_requested = False

        self.setWindowTitle("Edit Entry" if not self._is_new else "Add Entry")
        self.setMinimumWidth(480)
        self._build()
        self._populate()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(8)
        scroll.setWidget(inner)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Agumon X")
        form.addRow("Name *:", self._name_edit)

        # Stage
        self._stage_combo = QComboBox()
        for s in sorted(self._tree.stages, key=lambda x: x.order):
            self._stage_combo.addItem(s.label, s.id)
        form.addRow("Stage:", self._stage_combo)

        inner_layout.addLayout(form)

        # Type tags
        if self._tree.type_tags:
            inner_layout.addWidget(self._section_label("Type Tags:"))
            self._tag_checks: dict[str, QCheckBox] = {}
            tags_row = QHBoxLayout()
            for t in self._tree.type_tags:
                cb = QCheckBox(t.label)
                self._tag_checks[t.id] = cb
                tags_row.addWidget(cb)
            tags_row.addStretch()
            inner_layout.addLayout(tags_row)

        # Versions
        if self._tree.versions:
            inner_layout.addWidget(self._section_label("Versions:"))
            self._ver_checks: dict[str, QCheckBox] = {}
            vers_row = QHBoxLayout()
            for v in self._tree.versions:
                cb = QCheckBox(v.label)
                self._ver_checks[v.id] = cb
                vers_row.addWidget(cb)
            vers_row.addStretch()
            inner_layout.addLayout(vers_row)

        # Images
        inner_layout.addWidget(self._section_sep())
        inner_layout.addWidget(self._section_label("Images:"))

        img_form = QFormLayout()
        img_form.setLabelAlignment(Qt.AlignRight)

        # Artwork
        self._image_preview = QLabel()
        self._image_preview.setFixedSize(64, 64)
        self._image_preview.setStyleSheet("border:1px solid #ccc; background:#f5f5f5;")
        self._image_preview.setAlignment(Qt.AlignCenter)
        self._image_preview.setText("—")

        self._image_path_label = QLabel("(none)")
        self._image_path_label.setStyleSheet("color:#888; font-size:11px;")
        img_btn_layout = QHBoxLayout()
        btn_browse_img = QPushButton("Browse…")
        btn_browse_img.clicked.connect(lambda: self._browse_image(False))
        btn_clear_img = QPushButton("Clear")
        btn_clear_img.clicked.connect(lambda: self._clear_image(False))
        img_btn_layout.addWidget(btn_browse_img)
        img_btn_layout.addWidget(btn_clear_img)
        img_btn_layout.addStretch()
        img_col = QVBoxLayout()
        img_col.addWidget(self._image_preview)
        img_col.addWidget(self._image_path_label)
        img_col.addLayout(img_btn_layout)
        img_form.addRow("Artwork:", img_col)

        # Sprite
        self._sprite_preview = QLabel()
        self._sprite_preview.setFixedSize(64, 64)
        self._sprite_preview.setStyleSheet("border:1px solid #ccc; background:#f5f5f5;")
        self._sprite_preview.setAlignment(Qt.AlignCenter)
        self._sprite_preview.setText("—")

        self._sprite_path_label = QLabel("(none)")
        self._sprite_path_label.setStyleSheet("color:#888; font-size:11px;")
        spr_btn_layout = QHBoxLayout()
        btn_browse_spr = QPushButton("Browse…")
        btn_browse_spr.clicked.connect(lambda: self._browse_image(True))
        btn_clear_spr = QPushButton("Clear")
        btn_clear_spr.clicked.connect(lambda: self._clear_image(True))
        spr_btn_layout.addWidget(btn_browse_spr)
        spr_btn_layout.addWidget(btn_clear_spr)
        spr_btn_layout.addStretch()
        spr_col = QVBoxLayout()
        spr_col.addWidget(self._sprite_preview)
        spr_col.addWidget(self._sprite_path_label)
        spr_col.addLayout(spr_btn_layout)
        img_form.addRow("Sprite:", spr_col)
        inner_layout.addLayout(img_form)

        # Device data
        inner_layout.addWidget(self._section_sep())
        inner_layout.addWidget(self._section_label("Device Data  (optional):"))

        dev_form = QFormLayout()
        dev_form.setLabelAlignment(Qt.AlignRight)
        self._lib_edit     = QLineEdit(); self._lib_edit.setFixedWidth(80)
        self._power_edit   = QLineEdit(); self._power_edit.setFixedWidth(80)
        self._hp_edit      = QLineEdit(); self._hp_edit.setFixedWidth(80)
        self._sleep_edit   = QLineEdit(); self._sleep_edit.setFixedWidth(80)
        self._sleep_edit.setPlaceholderText("21:00")
        dev_form.addRow("Library #:", self._lib_edit)
        dev_form.addRow("Power:",     self._power_edit)
        dev_form.addRow("HP:",        self._hp_edit)
        dev_form.addRow("Sleep time:", self._sleep_edit)
        inner_layout.addLayout(dev_form)

        # Wikimon
        inner_layout.addWidget(self._section_sep())
        inner_layout.addWidget(self._section_label("Wikimon:"))

        wiki_form = QFormLayout()
        wiki_form.setLabelAlignment(Qt.AlignRight)
        self._wiki_key_edit = QLineEdit()
        self._wiki_key_edit.setPlaceholderText("e.g. Agumon_X")
        wiki_row = QHBoxLayout()
        wiki_row.addWidget(self._wiki_key_edit)
        btn_test = QPushButton("Test link")
        btn_test.setToolTip("Validate key (Phase 4)")
        btn_test.setEnabled(False)
        wiki_row.addWidget(btn_test)
        wiki_form.addRow("Wikimon key:", wiki_row)
        inner_layout.addLayout(wiki_form)

        # Notes
        inner_layout.addWidget(self._section_sep())
        inner_layout.addWidget(self._section_label("Notes:"))
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        inner_layout.addWidget(self._notes_edit)

        inner_layout.addStretch()
        root.addWidget(scroll)

        # Buttons
        btn_box = QHBoxLayout()
        if not self._is_new:
            btn_delete = QPushButton("Delete Entry")
            btn_delete.setStyleSheet("color:red;")
            btn_delete.clicked.connect(self._on_delete)
            btn_box.addWidget(btn_delete)
        btn_box.addStretch()
        std_btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        std_btns.accepted.connect(self._on_save)
        std_btns.rejected.connect(self.reject)
        btn_box.addWidget(std_btns)
        root.addLayout(btn_box)

    # ------------------------------------------------------------------
    # Populate
    # ------------------------------------------------------------------

    def _populate(self):
        e = self._entry
        self._name_edit.setText(e.name)

        # stage
        for i in range(self._stage_combo.count()):
            if self._stage_combo.itemData(i) == e.stage_id:
                self._stage_combo.setCurrentIndex(i)
                break

        # type tags
        for tid, cb in getattr(self, "_tag_checks", {}).items():
            cb.setChecked(tid in e.type_tag_ids)

        # versions
        for vid, cb in getattr(self, "_ver_checks", {}).items():
            cb.setChecked(vid in e.version_ids)

        # images
        if e.image_local:
            self._load_preview(e.image_local, self._image_preview)
            self._image_path_label.setText(e.image_local)
        if e.sprite_local:
            self._load_preview(e.sprite_local, self._sprite_preview)
            self._sprite_path_label.setText(e.sprite_local)

        # device data
        if e.library_number is not None:
            self._lib_edit.setText(str(e.library_number))
        if e.power is not None:
            self._power_edit.setText(str(e.power))
        if e.hp is not None:
            self._hp_edit.setText(str(e.hp))
        if e.sleep_time:
            self._sleep_edit.setText(e.sleep_time)

        # wikimon
        if e.wikimon_key:
            self._wiki_key_edit.setText(e.wikimon_key)

        # notes
        self._notes_edit.setPlainText(e.notes)

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    def _browse_image(self, is_sprite: bool):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if not path:
            return
        if is_sprite:
            self._entry.sprite_local = path
            self._sprite_path_label.setText(path)
            self._load_preview(path, self._sprite_preview)
        else:
            self._entry.image_local = path
            self._image_path_label.setText(path)
            self._load_preview(path, self._image_preview)

    def _clear_image(self, is_sprite: bool):
        if is_sprite:
            self._entry.sprite_local = None
            self._sprite_preview.setText("—")
            self._sprite_path_label.setText("(none)")
        else:
            self._entry.image_local = None
            self._image_preview.setText("—")
            self._image_path_label.setText("(none)")

    def _load_preview(self, path: str, label: QLabel):
        pix = QPixmap(path)
        if not pix.isNull():
            label.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        else:
            label.setText("?")

    # ------------------------------------------------------------------
    # Save / Delete
    # ------------------------------------------------------------------

    def _on_save(self):
        name = self._name_edit.text().strip()
        if not name:
            self._name_edit.setFocus()
            self._name_edit.setStyleSheet("border:1px solid red;")
            return
        self._name_edit.setStyleSheet("")

        e = self._entry
        e.name     = name
        e.stage_id = self._stage_combo.currentData() or ""
        e.type_tag_ids = [tid for tid, cb in
                          getattr(self, "_tag_checks", {}).items() if cb.isChecked()]
        e.version_ids  = [vid for vid, cb in
                          getattr(self, "_ver_checks", {}).items() if cb.isChecked()]

        e.library_number = _to_int(self._lib_edit.text())
        e.power          = _to_int(self._power_edit.text())
        e.hp             = _to_int(self._hp_edit.text())
        e.sleep_time     = self._sleep_edit.text().strip() or None
        e.wikimon_key    = self._wiki_key_edit.text().strip() or None
        e.notes          = self._notes_edit.toPlainText().strip()

        self.accept()

    def _on_delete(self):
        self._delete_requested = True
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_entry(self) -> Entry:
        return self._entry

    def was_deleted(self) -> bool:
        return self._delete_requested

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight:bold; color:#555; font-size:11px;")
        return lbl

    @staticmethod
    def _section_sep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep


def _to_int(text: str) -> int | None:
    try:
        return int(text.strip()) if text.strip() else None
    except ValueError:
        return None
