import json
from pathlib import Path
from typing import Any

from digitree.app_paths import CONFIG_PATH, ensure_data_dirs

_DEFAULTS: dict[str, Any] = {
    "recent_trees": [],
    "last_open_path": "",
    "window_geometry": {},
    "theme": "light",
    "card_size": "medium",
    "wikimon_rate_limit": 2.0,
    "wikimon_image_dir": "",
}


class Config:
    def __init__(self):
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self.load()

    def load(self) -> None:
        ensure_data_dirs()
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception:
                pass  # corrupt config — start fresh

    def save(self) -> None:
        ensure_data_dirs()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    # -- Recent trees --------------------------------------------------

    def add_recent_tree(self, path: str) -> None:
        recent: list[str] = self._data.get("recent_trees", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._data["recent_trees"] = recent[:20]

    def remove_recent_tree(self, path: str) -> None:
        recent: list[str] = self._data.get("recent_trees", [])
        if path in recent:
            recent.remove(path)
        self._data["recent_trees"] = recent

    def recent_trees(self) -> list[str]:
        return list(self._data.get("recent_trees", []))
