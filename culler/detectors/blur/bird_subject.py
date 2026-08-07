"""
Method 6: Bird & Wildlife Subject ROI Crop Algorithm.
Crops central 60% box and calculates weighted Laplacian + Tenengrad focus energy.
"""

from typing import Any

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


def compute_bird_subject_sharpness(gray: Any) -> float:
    """
    Bird & Wildlife Subject ROI sharpness score.
    Focuses evaluation on central 60% subject box.
    Uses 85th percentile feature energy for immunity to smooth background bokeh.
    """
    if cv2 is None or np is None or gray is None:
        return 0.0
    h, w = gray.shape
    y1, y2 = int(h * 0.20), int(h * 0.80)
    x1, x2 = int(w * 0.20), int(w * 0.80)
    roi = gray[y1:y2, x1:x2]

    if roi.size == 0:
        return 0.0

    lap_mag = np.abs(cv2.Laplacian(roi, cv2.CV_64F))
    gx = cv2.Sobel(roi, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(roi, cv2.CV_64F, 0, 1, ksize=3)
    sob_mag = np.sqrt(gx**2 + gy**2)

    p85_lap = float(np.percentile(lap_mag, 85))
    p85_sob = float(np.percentile(sob_mag, 85))
    score = (p85_lap * 4.0) + (p85_sob * 0.5)
    return round(score, 2)
