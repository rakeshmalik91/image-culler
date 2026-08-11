"""
Blur & Sharpness Detection Algorithms Package.
Exposes 3 focus algorithms and the router function:
  1. Laplacian (default, ultra-fast)
  2. AI Subject Focus (YOLO + ROI + Patch Grid)
  3. FFT Frequency Analysis (motion blur)
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
from .fft import compute_fft_sharpness
from .bird_subject import compute_bird_subject_sharpness
from .yolo_subject import compute_ai_subject_sharpness, compute_yolo_subject_sharpness


def calculate_sharpness(
    pil_img: Image.Image,
    method: str = "laplacian",
    yolo_model: Optional[Any] = None,
    return_box: bool = False,
    eye_detection_method: str = "yolo",
    yolo_pose_model: Optional[Any] = None
) -> float:
    """
    Unified router delegating to individual blur detection modules.
    Supports 3 algorithms: 'laplacian', 'ai_subject', 'fft'.
    Old method names are silently redirected for backward compatibility.
    """
    if cv2 is None or np is None or pil_img is None:
        if return_box:
            return 0.0, (None, None)
        return 0.0

    gray = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    m = (method or "laplacian").lower()

    # AI Subject Focus (covers old yolo_subject, bird_subject, local_var aliases)
    if m in ("ai_subject", "yolo_subject", "yolo", "yolo_bird_eye", "bird_eye_yolo",
             "yolo_eye", "bird_subject", "local_var"):
        return compute_ai_subject_sharpness(
            gray,
            pil_img,
            yolo_model=yolo_model,
            return_box=return_box,
            eye_detection_method=eye_detection_method,
            yolo_pose_model=yolo_pose_model
        )

    # FFT Frequency Analysis
    elif m == "fft":
        if return_box:
            return compute_fft_sharpness(gray), (None, None)
        return compute_fft_sharpness(gray)

    # Laplacian (default — also catches old tenengrad/brenner aliases)
    else:
        if return_box:
            return compute_laplacian_sharpness(gray), (None, None)
        return compute_laplacian_sharpness(gray)


from .eye_detector import extract_eye_face_box, extract_eye_box_yolo_pose, detect_animal_bird_eye


__all__ = [
    "calculate_sharpness",
    "compute_laplacian_sharpness",
    "compute_fft_sharpness",
    "compute_bird_subject_sharpness",
    "compute_ai_subject_sharpness",
    "compute_yolo_subject_sharpness",
    "extract_eye_face_box",
    "extract_eye_box_yolo_pose",
    "detect_animal_bird_eye",
]
