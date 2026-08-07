"""
Duplicate & Burst Shot Detection Package.
Exposes all 3 duplicate algorithms and the router function.
"""

from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...culler_engine import ImageItem

from .dhash import compute_dhash, hamming_distance, find_dhash_duplicates
from .md5_hash import find_md5_duplicates
from .burst_time import find_burst_time_duplicates


def find_duplicates(
    items: List['ImageItem'],
    image_loader=None,
    method: str = "dhash",
    threshold: float = 6.0,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[List['ImageItem']]:
    """
    Unified entry point for scanning duplicates across 'dhash', 'md5', and 'burst_time' methods.
    """
    if not items:
        return []

    m = (method or "dhash").lower()
    if m == "md5":
        return find_md5_duplicates(items, progress_callback=progress_callback)
    elif m == "burst_time":
        return find_burst_time_duplicates(items, threshold_seconds=threshold, progress_callback=progress_callback)
    else:
        max_dist = int(threshold)
        return find_dhash_duplicates(items, image_loader=image_loader, max_dist=max_dist, progress_callback=progress_callback)


__all__ = [
    "find_duplicates",
    "compute_dhash",
    "hamming_distance",
    "find_dhash_duplicates",
    "find_md5_duplicates",
    "find_burst_time_duplicates",
]
