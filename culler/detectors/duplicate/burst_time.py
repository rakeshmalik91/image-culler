"""
EXIF Timestamp & Sequence Burst Time Grouping Duplicate Algorithm.
Groups photos taken within threshold seconds of each other.
"""

import datetime
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ...culler_engine import ImageItem


def find_burst_time_duplicates(
    items: List['ImageItem'],
    threshold_seconds: float = 2.0,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[List['ImageItem']]:
    """
    Group burst shot photos taken within threshold seconds using EXIF date_taken or stat mtime.
    """
    times: List[Tuple[float, 'ImageItem']] = []
    for idx, item in enumerate(items):
        t_val = 0.0
        try:
            t_val = item.path.stat().st_mtime
        except Exception:
            pass

        m = item.metadata
        if m.get("date_taken"):
            try:
                dt = datetime.datetime.strptime(str(m["date_taken"]), "%Y:%m:%d %H:%M:%S")
                t_val = dt.timestamp()
            except Exception:
                pass
        times.append((t_val, item))

    times.sort(key=lambda x: x[0])

    groups: List[List['ImageItem']] = []
    current_group: List['ImageItem'] = []
    for idx, (t, item) in enumerate(times):
        if not current_group:
            current_group.append(item)
        else:
            prev_t = times[idx - 1][0]
            if abs(t - prev_t) <= threshold_seconds:
                current_group.append(item)
            else:
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = [item]
        if progress_callback:
            progress_callback(idx + 1, len(times))

    if len(current_group) > 1:
        groups.append(current_group)

    return groups
