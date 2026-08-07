"""
Method 5: Local Patch Texture Variance Algorithm.
Divides image into grid patches and calculates 90th percentile texture variance.
"""

from typing import Any

try:
    import numpy as np
except ImportError:
    np = None


def compute_local_var_sharpness(gray: Any) -> float:
    """
    Local patch variance sharpness score.
    Useful for detecting isolated in-focus subjects against blurred backgrounds.
    """
    if np is None or gray is None:
        return 0.0
    h, w = gray.shape
    pw, ph = max(10, w // 10), max(10, h // 10)
    patches = [gray[y:y+ph, x:x+pw] for y in range(0, h-ph, ph) for x in range(0, w-pw, pw)]
    vars_list = [float(p.var()) for p in patches if p.size > 0]
    score = float(np.percentile(vars_list, 90)) if vars_list else 0.0
    return round(score, 2)
