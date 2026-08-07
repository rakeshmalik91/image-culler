"""
Blur & Sharpness Detection Algorithms Package.
Exposes all 7 focus algorithms and the router function.
"""

from typing import Any, Optional
from PIL import Image

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from .laplacian import compute_laplacian_sharpness
from .tenengrad import compute_tenengrad_sharpness
from .brenner import compute_brenner_sharpness
from .fft import compute_fft_sharpness
from .local_var import compute_local_var_sharpness
from .bird_subject import compute_bird_subject_sharpness
from .yolo_subject import compute_yolo_subject_sharpness


def calculate_sharpness(pil_img: Image.Image, method: str = "laplacian", yolo_model: Optional[Any] = None) -> float:
    """
    Unified router delegating to individual blur detection modules.
    """
    if cv2 is None or np is None or pil_img is None:
        return 0.0

    gray = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    m = (method or "laplacian").lower()

    if m == "tenengrad":
        return compute_tenengrad_sharpness(gray)
    elif m == "brenner":
        return compute_brenner_sharpness(gray)
    elif m == "fft":
        return compute_fft_sharpness(gray)
    elif m == "local_var":
        return compute_local_var_sharpness(gray)
    elif m == "bird_subject":
        return compute_bird_subject_sharpness(gray)
    elif m in ("yolo_subject", "yolo", "yolo_bird_eye", "bird_eye_yolo", "yolo_eye"):
        return compute_yolo_subject_sharpness(gray, pil_img, yolo_model=yolo_model)
    else:
        return compute_laplacian_sharpness(gray)


__all__ = [
    "calculate_sharpness",
    "compute_laplacian_sharpness",
    "compute_tenengrad_sharpness",
    "compute_brenner_sharpness",
    "compute_fft_sharpness",
    "compute_local_var_sharpness",
    "compute_bird_subject_sharpness",
    "compute_yolo_subject_sharpness",
]
