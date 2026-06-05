from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QWheelEvent


class GraphCanvas(QGraphicsView):
    """Base zoomable/pannable QGraphicsView."""

    MIN_ZOOM = 0.08
    MAX_ZOOM = 5.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._zoom: float = 1.0

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1.0 / 1.15
            new_zoom = self._zoom * factor
            if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
                self._zoom = new_zoom
                self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def fit_view(self):
        rect = self._scene.itemsBoundingRect()
        if not rect.isEmpty():
            self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.KeepAspectRatio)
            self._zoom = self.transform().m11()
