"""
Method 3: Brenner Focus Measure Algorithm.
Computes focus score using squared differences between pixels separated by 2 units horizontally.
"""

from typing import Any

try:
    import numpy as np
except ImportError:
    np = None


def compute_brenner_sharpness(gray: Any) -> float:
    """
    Brenner focus measure sharpness score.
    Fast horizontal pixel gradient squared difference.
    """
    if np is None or gray is None:
        return 0.0
    diff_x = gray[:, 2:].astype(np.float64) - gray[:, :-2].astype(np.float64)
    score = float(np.mean(diff_x**2))
    return round(score, 2)
