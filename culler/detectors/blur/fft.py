"""
Method 4: 2D Fast Fourier Transform (FFT) High Frequency Analysis Algorithm.
Measures focus by analyzing the ratio of high-frequency spatial components in frequency domain.
"""

from typing import Any

try:
    import numpy as np
except ImportError:
    np = None


def compute_fft_sharpness(gray: Any) -> float:
    """
    FFT high-frequency analysis sharpness score.
    Zeroes out central low frequencies and computes mean high frequency magnitude.
    """
    if np is None or gray is None:
        return 0.0
    h, w = gray.shape
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)
    cy, cx = h // 2, w // 2
    r = min(h, w) // 8
    magnitude[cy-r:cy+r, cx-r:cx+r] = 0
    score = float(np.mean(magnitude))
    return round(score, 2)
