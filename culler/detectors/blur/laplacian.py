"""
Method 1 (Default): Variance of Laplacian Edge Detection Algorithm.
Calculates global sharpness by computing the variance of the 2D Laplacian operator across grayscale pixels.
"""

from typing import Any

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


def compute_laplacian_sharpness(gray: Any) -> float:
    """
    Variance of Laplacian sharpness score.
    Higher values indicate sharper edges; low values indicate motion or defocus blur.
    """
    if cv2 is None or np is None or gray is None:
        return 0.0
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return round(float(variance), 2)
