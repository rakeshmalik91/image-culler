import os
import sys
from pathlib import Path

APP_NAME = "FastPhotoCuller"


def _get_app_data_dir() -> Path:
    env_override = os.environ.get("FAST_PHOTO_CULLER_DATA_DIR")
    if env_override:
        return Path(env_override).resolve()

    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", "")))
        return base / APP_NAME

    return Path(__file__).resolve().parent.parent


APP_DATA_DIR = _get_app_data_dir()
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DATA_DIR / "culler.db"
DATASET_DIR = APP_DATA_DIR / "_DATASET"
MODELS_DIR = APP_DATA_DIR / "lib" / "models"
EXIFTOOL_DIR = APP_DATA_DIR / "lib" / "exif-tools"
