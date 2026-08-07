"""
Configuration Loader module for Blur & Duplicate detection algorithm metadata.
Reads titles, ordering, descriptions, speed, pros, cons, and thresholds from detector_algorithms.json.
"""

import json
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).resolve().parent / "detector_algorithms.json"


def load_detector_config() -> Dict[str, Any]:
    """
    Load detector configuration JSON from detector_algorithms.json file.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_blur_methods_config() -> Dict[str, Dict[str, Any]]:
    """
    Get blur algorithms metadata dictionary.
    """
    cfg = load_detector_config()
    return cfg.get("blur_methods", {})


def get_duplicate_methods_config() -> Dict[str, Dict[str, Any]]:
    """
    Get duplicate algorithms metadata dictionary.
    """
    cfg = load_detector_config()
    return cfg.get("duplicate_methods", {})
