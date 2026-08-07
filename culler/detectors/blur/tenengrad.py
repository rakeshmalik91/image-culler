"""
Method 2: Tenengrad Sobel Gradient Magnitude Energy Algorithm.
Measures focus sharpness using Sobel gradient filters in X and Y directions.
"""

from typing import Any

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


def compute_tenengrad_sharpness(gray: Any) -> float:
    """
    Tenengrad sharpness score.
    Computes mean Sobel gradient magnitude energy (gx^2 + gy^2).
    """
    if cv2 is None or np is None or gray is None:
        return 0.0
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    score = float(np.mean(gx**2 + gy**2) * 0.1)
    return round(score, 2)
