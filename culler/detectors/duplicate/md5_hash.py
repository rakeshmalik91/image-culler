"""
Exact MD5 Byte Hash Duplicate Detection Algorithm.
Detects identical files using fast 2MB byte hash + file size lookup.
"""

import hashlib
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...culler_engine import ImageItem


def find_md5_duplicates(
    items: List['ImageItem'],
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event=None
) -> List[List['ImageItem']]:
    """
    Find duplicate photos using fast MD5 byte hashing (first 2MB + file size).
    """
    hashes: Dict[str, List['ImageItem']] = {}
    for idx, item in enumerate(items):
        if cancel_event and cancel_event.is_set():
            return []
        try:
            with open(item.path, "rb") as f:
                data = f.read(2 * 1024 * 1024)
                h_val = hashlib.md5(data + str(item.path.stat().st_size).encode()).hexdigest()
                hashes.setdefault(h_val, []).append(item)
        except Exception:
            pass
        if progress_callback:
            progress_callback(idx + 1, len(items))

    return [grp for grp in hashes.values() if len(grp) > 1]
