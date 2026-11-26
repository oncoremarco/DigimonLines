"""Tools > Import Digimon Database: runs the Wikimon importer in a
background thread with a progress bar and a Stop button."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QVBoxLayout)

from digitree.db.cache import CacheDB
from digitree.wikimon.client import WikimonClient
from digitree.wikimon.importer import Importer, ImportProgress


class ImportWorker(QThread):
    progress = Signal(object)    # ImportProgress
    failed = Signal(str)

    def __init__(self, db_path, delay: float, refresh: bool, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._delay = delay
        self._refresh = refresh
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        # SQLite connections belong to one thread, so the worker opens its own.
        db = CacheDB(self._db_path)
        try:
            client = WikimonClient(min_interval=self._delay, should_stop=lambda: self._stop)
            Importer(db, client, self.progress.emit).run(refresh=self._refresh)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            db.close()


class ImportDialog(QDialog):
    def __init__(self, db: CacheDB, delay: float = 2.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Digimon Database")
        self.resize(560, 380)
        self._db = db
        self._delay = delay
        self._worker: ImportWorker | None = None

        intro = QLabel(
            "Downloads every Digimon's text profile from Wikimon (Level, Type, "
            "Attribute, Field, attacks, Reference Book description and evolution "
            "lists) into a local database. No images are downloaded.\n\n"
            f"Requests are spaced {delay:g} s apart to be kind to Wikimon. You can "
            "stop at any time and resume later from where it left off."
        )
        intro.setWordWrap(True)

        self._status = QLabel()
        self._bar = QProgressBar()
        self._log = QPlainTextEdit(readOnly=True)
        self._log.setMaximumBlockCount(500)

        self._refresh = QCheckBox("Re-download everything (refresh)")
        self._start_btn = QPushButton("Start")
        self._stop_btn = QPushButton("Stop")
        self._close_btn = QPushButton("Close")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start)
        self._stop_btn.clicked.connect(self._request_stop)
        self._close_btn.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(self._refresh)
        buttons.addStretch()
        for b in (self._start_btn, self._stop_btn, self._close_btn):
            buttons.addWidget(b)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._status)
        layout.addWidget(self._bar)
        layout.addWidget(self._log, 1)
        layout.addLayout(buttons)
        self._show_counts()

    def _show_counts(self) -> None:
        counts = self._db.queue_counts()
        total = sum(counts.values())
        n = self._db.count_digimon()
        if total == 0:
            self._status.setText("No import yet.")
            self._start_btn.setText("Start")
        else:
            finished = counts["done"] + counts["skipped"]
            self._status.setText(
                f"{n} Digimon in the database. {finished}/{total} pages processed"
                + (f", {counts['error']} errors." if counts["error"] else ".")
            )
            self._bar.setRange(0, total)
            self._bar.setValue(finished)
            self._start_btn.setText("Resume" if counts["pending"] or counts["error"] else "Update")

    def _start(self) -> None:
        self._worker = ImportWorker(self._db.path, self._delay, self._refresh.isChecked(), self)
        self._worker.progress.connect(self._on_progress)
        self._worker.failed.connect(lambda msg: self._log.appendPlainText("Error: " + msg))
        self._worker.finished.connect(self._on_finished)
        self._start_btn.setEnabled(False)
        self._refresh.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._worker.start()

    def _request_stop(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._stop_btn.setEnabled(False)
            self._log.appendPlainText("Stopping…")

    def _on_progress(self, p: ImportProgress) -> None:
        if p.total:
            self._bar.setRange(0, p.total)
            self._bar.setValue(p.done)
        elif p.stage in ("enumerate", "links"):
            self._bar.setRange(0, 0)  # busy indicator
        if p.message:
            self._status.setText(p.message)
            if p.stage != "download" or p.message.endswith("complete"):
                self._log.appendPlainText(p.message)

    def _on_finished(self) -> None:
        self._worker = None
        self._start_btn.setEnabled(True)
        self._refresh.setEnabled(True)
        self._refresh.setChecked(False)
        self._stop_btn.setEnabled(False)
        self._bar.setRange(0, 1)
        self._show_counts()
        for err in self._db.queue_errors()[:20]:
            self._log.appendPlainText(f"  {err['title']}: {err['error']}")

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(5000)
        super().closeEvent(event)
