"""
Backward-compatibility alias module for duplicate detection.
"""

from .duplicate import (
    find_duplicates,
    compute_dhash,
    hamming_distance,
    find_dhash_duplicates,
    find_md5_duplicates,
    find_burst_time_duplicates,
)

__all__ = [
    "find_duplicates",
    "compute_dhash",
    "hamming_distance",
    "find_dhash_duplicates",
    "find_md5_duplicates",
    "find_burst_time_duplicates",
]
