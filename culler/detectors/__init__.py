"""
Detectors package containing modular blur/sharpness detection and duplicate/burst-shot detection algorithms.
"""

from .blur import calculate_sharpness
from .duplicate import find_duplicates

__all__ = ["calculate_sharpness", "find_duplicates"]
