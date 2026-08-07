"""
Backward-compatibility alias module for blur detection.
"""

from .blur import (
    calculate_sharpness,
    compute_laplacian_sharpness,
    compute_tenengrad_sharpness,
    compute_brenner_sharpness,
    compute_fft_sharpness,
    compute_local_var_sharpness,
    compute_bird_subject_sharpness,
    compute_yolo_subject_sharpness,
)

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
