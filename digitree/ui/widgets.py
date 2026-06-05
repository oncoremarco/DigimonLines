from PySide6.QtWidgets import QPushButton, QColorDialog
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal


class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color: str = "#888888", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(40, 24)
        self._refresh()
        self.clicked.connect(self._pick)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self._refresh()
            self.color_changed.emit(self._color)

    def _refresh(self):
        self.setStyleSheet(
            f"QPushButton {{ background: {self._color}; border: 1px solid #999; }}"
        )

    @property
    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self._refresh()
