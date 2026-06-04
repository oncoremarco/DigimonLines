import os
import sys
from pathlib import Path


def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "DigiTree"


DATA_DIR: Path = _get_data_dir()
TREES_DIR: Path = DATA_DIR / "trees"
EXPORTS_DIR: Path = DATA_DIR / "exports"
WIKIMON_IMAGES_DIR: Path = DATA_DIR / "wikimon_images"
WIKIMON_DB_PATH: Path = DATA_DIR / "wikimon_cache.db"
CONFIG_PATH: Path = DATA_DIR / "config.json"

# Bundled presets live next to the package source, not in APPDATA
BUNDLED_PRESETS_DIR: Path = Path(__file__).parent / "presets"


def ensure_data_dirs() -> None:
    for d in (DATA_DIR, TREES_DIR, EXPORTS_DIR, WIKIMON_IMAGES_DIR):
        d.mkdir(parents=True, exist_ok=True)
    BUNDLED_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
