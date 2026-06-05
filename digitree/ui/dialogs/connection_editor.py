from __future__ import annotations
import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QScrollArea, QFrame, QWidget,
    QGroupBox, QDoubleSpinBox, QSpinBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from digitree.models.tree import (
    Tree, Connection, RequirementGroup, RequirementCondition,
)

_STYLES = ["normal", "dashed_failure"]
_STYLE_LABELS = {"normal": "Normal", "dashed_failure": "Dashed (failure)"}


class ConnectionEditor(QDialog):
    def __init__(self, tree: Tree, connection: Connection | None = None, parent=None):
        super().__init__(parent)
        self._tree = tree
        self._conn = copy.deepcopy(connection) if connection else Connection()
        self._is_new = connection is None
        self._delete_requested = False
        self._group_widgets: list[_GroupWidget] = []

        self.setWindowTitle("Edit Connection" if not self._is_new else "Add Connection")
        self.setMinimumSize(560, 540)
        self._build()
        self._populate()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setSpacing(8)
        scroll.setWidget(inner)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # From / To
        self._from_combo = QComboBox()
        self._to_combo = QComboBox()
        entries_sorted = sorted(self._tree.entries, key=lambda e: e.name)
        for e in entries_sorted:
            self._from_combo.addItem(e.name, e.id)
            self._to_combo.addItem(e.name, e.id)
        form.addRow("From:", self._from_combo)
        form.addRow("To:",   self._to_combo)

        # Style
        self._style_combo = QComboBox()
        for s in _STYLES:
            self._style_combo.addItem(_STYLE_LABELS[s], s)
        form.addRow("Style:", self._style_combo)
        self._inner_layout.addLayout(form)

        # Versions
        if self._tree.versions:
            self._inner_layout.addWidget(self._section_label("Versions:"))
            self._ver_checks: dict[str, QCheckBox] = {}
            ver_row = QHBoxLayout()
            for v in self._tree.versions:
                cb = QCheckBox(v.label)
                self._ver_checks[v.id] = cb
                ver_row.addWidget(cb)
            ver_row.addStretch()
            self._inner_layout.addLayout(ver_row)

        self._inner_layout.addWidget(self._section_sep())

        # Requirement groups header
        hdr = QHBoxLayout()
        hdr.addWidget(self._section_label("Requirement Groups  (OR between groups):"))
        hdr.addStretch()
        self._inner_layout.addLayout(hdr)

        # Groups container
        self._groups_container = QVBoxLayout()
        self._groups_container.setSpacing(8)
        self._inner_layout.addLayout(self._groups_container)

        # Add group button
        btn_add_grp = QPushButton("+ Add Group")
        btn_add_grp.setFixedWidth(120)
        btn_add_grp.clicked.connect(self._add_group)
        self._inner_layout.addWidget(btn_add_grp)
        self._inner_layout.addStretch()

        root.addWidget(scroll)

        # Bottom buttons
        btn_row = QHBoxLayout()
        if not self._is_new:
            btn_del = QPushButton("Delete Connection")
            btn_del.setStyleSheet("color:red;")
            btn_del.clicked.connect(self._on_delete)
            btn_row.addWidget(btn_del)
        btn_row.addStretch()
        std = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        std.accepted.connect(self._on_save)
        std.rejected.connect(self.reject)
        btn_row.addWidget(std)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Populate
    # ------------------------------------------------------------------

    def _populate(self):
        c = self._conn

        for i in range(self._from_combo.count()):
            if self._from_combo.itemData(i) == c.from_entry_id:
                self._from_combo.setCurrentIndex(i)
                break
        for i in range(self._to_combo.count()):
            if self._to_combo.itemData(i) == c.to_entry_id:
                self._to_combo.setCurrentIndex(i)
                break

        for i, s in enumerate(_STYLES):
            if s == c.style:
                self._style_combo.setCurrentIndex(i)
                break

        for vid, cb in getattr(self, "_ver_checks", {}).items():
            cb.setChecked(vid in c.version_ids)

        for grp in c.req_groups:
            self._add_group(grp)

    # ------------------------------------------------------------------
    # Group management
    # ------------------------------------------------------------------

    def _add_group(self, grp: RequirementGroup | None = None):
        if grp is None:
            grp = RequirementGroup()
        w = _GroupWidget(self._tree.requirement_types, grp, self)
        w.remove_requested.connect(self._remove_group)
        self._group_widgets.append(w)
        # insert before the stretch at the end of _groups_container
        self._groups_container.addWidget(w)

    def _remove_group(self, w: "_GroupWidget"):
        self._groups_container.removeWidget(w)
        w.deleteLater()
        if w in self._group_widgets:
            self._group_widgets.remove(w)

    # ------------------------------------------------------------------
    # Save / Delete
    # ------------------------------------------------------------------

    def _on_save(self):
        c = self._conn
        c.from_entry_id = self._from_combo.currentData() or ""
        c.to_entry_id   = self._to_combo.currentData() or ""
        c.style         = self._style_combo.currentData() or "normal"
        c.version_ids   = [vid for vid, cb in
                           getattr(self, "_ver_checks", {}).items() if cb.isChecked()]
        c.req_groups    = [w.get_group() for w in self._group_widgets]
        self.accept()

    def _on_delete(self):
        self._delete_requested = True
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_connection(self) -> Connection:
        return self._conn

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


# ----------------------------------------------------------------------
# Group widget
# ----------------------------------------------------------------------

from PySide6.QtCore import Signal  # noqa: E402


class _GroupWidget(QGroupBox):
    remove_requested = Signal(object)

    def __init__(self, req_types, grp: RequirementGroup, parent=None):
        super().__init__(parent)
        self._req_types = req_types
        self._condition_widgets: list[_ConditionRow] = []
        self._build()
        for cond in grp.conditions:
            self._add_condition(cond)

    def _build(self):
        self.setTitle("Requirement Group  (AND)")

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self._conditions_layout = QVBoxLayout()
        self._conditions_layout.setSpacing(4)
        layout.addLayout(self._conditions_layout)

        btns = QHBoxLayout()
        btn_add = QPushButton("+ Add condition")
        btn_add.setFixedWidth(130)
        btn_add.clicked.connect(lambda: self._add_condition(None))
        btns.addWidget(btn_add)
        btns.addStretch()
        btn_remove = QPushButton("Remove group")
        btn_remove.setStyleSheet("color:red; font-size:11px;")
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        btns.addWidget(btn_remove)
        layout.addLayout(btns)

    def _add_condition(self, cond: RequirementCondition | None):
        row = _ConditionRow(self._req_types, cond, self)
        row.remove_requested.connect(self._remove_condition)
        self._condition_widgets.append(row)
        self._conditions_layout.addWidget(row)

    def _remove_condition(self, row: "_ConditionRow"):
        self._conditions_layout.removeWidget(row)
        row.deleteLater()
        if row in self._condition_widgets:
            self._condition_widgets.remove(row)

    def get_group(self) -> RequirementGroup:
        grp = RequirementGroup()
        grp.conditions = [w.get_condition() for w in self._condition_widgets]
        return grp


# ----------------------------------------------------------------------
# Condition row widget
# ----------------------------------------------------------------------

class _ConditionRow(QWidget):
    remove_requested = Signal(object)

    def __init__(self, req_types, cond: RequirementCondition | None, parent=None):
        super().__init__(parent)
        self._req_types = req_types
        self._build()
        if cond:
            self._populate(cond)

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._type_combo = QComboBox()
        self._type_combo.setMinimumWidth(160)
        for rt in self._req_types:
            self._type_combo.addItem(rt.label, rt.id)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self._type_combo)

        # Range fields
        self._range_widget = QWidget()
        rl = QHBoxLayout(self._range_widget)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("min:"))
        self._range_min = QDoubleSpinBox()
        self._range_min.setRange(-9999, 9999)
        self._range_min.setDecimals(0)
        self._range_min.setFixedWidth(70)
        rl.addWidget(self._range_min)
        rl.addWidget(QLabel("max:"))
        self._range_max = QDoubleSpinBox()
        self._range_max.setRange(-9999, 9999)
        self._range_max.setDecimals(0)
        self._range_max.setFixedWidth(70)
        rl.addWidget(self._range_max)

        # Threshold field
        self._thresh_widget = QWidget()
        tl = QHBoxLayout(self._thresh_widget)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(QLabel("threshold:"))
        self._thresh_spin = QDoubleSpinBox()
        self._thresh_spin.setRange(0, 9999)
        self._thresh_spin.setDecimals(0)
        self._thresh_spin.setFixedWidth(80)
        tl.addWidget(self._thresh_spin)

        # Count field
        self._count_widget = QWidget()
        cl = QHBoxLayout(self._count_widget)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(QLabel("count:"))
        self._count_spin = QSpinBox()
        self._count_spin.setRange(0, 9999)
        self._count_spin.setFixedWidth(80)
        cl.addWidget(self._count_spin)

        # Boolean: no extra fields
        self._bool_widget = QLabel("(boolean — no value needed)")
        self._bool_widget.setStyleSheet("color:#888; font-size:11px;")

        layout.addWidget(self._range_widget)
        layout.addWidget(self._thresh_widget)
        layout.addWidget(self._count_widget)
        layout.addWidget(self._bool_widget)

        layout.addStretch()

        btn_remove = QPushButton("✕")
        btn_remove.setFixedSize(24, 24)
        btn_remove.setStyleSheet("color:red; font-weight:bold;")
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(btn_remove)

        self._on_type_changed(0)

    def _populate(self, cond: RequirementCondition):
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) == cond.req_type_id:
                self._type_combo.setCurrentIndex(i)
                break
        if cond.min is not None:
            self._range_min.setValue(cond.min)
        if cond.max is not None:
            self._range_max.setValue(cond.max)
        if cond.threshold is not None:
            self._thresh_spin.setValue(cond.threshold)
        if cond.count is not None:
            self._count_spin.setValue(cond.count)

    def _on_type_changed(self, _idx: int):
        rid = self._type_combo.currentData()
        rt = next((r for r in self._req_types if r.id == rid), None)
        vtype = rt.value_type if rt else "range"

        self._range_widget.setVisible(vtype == "range")
        self._thresh_widget.setVisible(vtype == "threshold")
        self._count_widget.setVisible(vtype == "min_count")
        self._bool_widget.setVisible(vtype == "boolean")

    def get_condition(self) -> RequirementCondition:
        rid = self._type_combo.currentData() or ""
        rt = next((r for r in self._req_types if r.id == rid), None)
        vtype = rt.value_type if rt else "range"

        cond = RequirementCondition(req_type_id=rid)
        if vtype == "range":
            cond.min = self._range_min.value()
            cond.max = self._range_max.value()
        elif vtype == "threshold":
            cond.threshold = self._thresh_spin.value()
        elif vtype == "min_count":
            cond.count = self._count_spin.value()
        return cond
