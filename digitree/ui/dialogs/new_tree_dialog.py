from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QCheckBox,
    QDialogButtonBox, QFrame,
)
from PySide6.QtCore import Qt

from digitree.models.tree import Tree, make_digimon_defaults


class NewTreeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Tree")
        self.setMinimumWidth(440)
        self._tree: Tree | None = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Digital Monster X Ver.XA")
        form.addRow("Name *", self._name_edit)

        self._device_edit = QLineEdit()
        self._device_edit.setPlaceholderText("e.g. dmx_xa  (optional)")
        form.addRow("Device ID", self._device_edit)

        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.setPlaceholderText("Optional description / notes")
        form.addRow("Notes", self._notes_edit)

        layout.addLayout(form)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._defaults_check = QCheckBox(
            "Start from Digimon defaults\n"
            "(stages I–VI, Vaccine / Data / Virus / Free types, standard requirement types)"
        )
        self._defaults_check.setChecked(True)
        layout.addWidget(self._defaults_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            self._name_edit.setFocus()
            self._name_edit.setStyleSheet("border: 1px solid red;")
            return
        self._name_edit.setStyleSheet("")

        self._tree = Tree(
            name=name,
            device=self._device_edit.text().strip(),
            notes=self._notes_edit.toPlainText().strip(),
        )

        if self._defaults_check.isChecked():
            stages, type_tags, req_types = make_digimon_defaults()
            self._tree.stages = stages
            self._tree.type_tags = type_tags
            self._tree.requirement_types = req_types

        self.accept()

    def get_tree(self) -> Tree | None:
        return self._tree
