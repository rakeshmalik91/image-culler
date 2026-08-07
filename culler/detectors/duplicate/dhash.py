"""
Perceptual 64-bit dHash & Hamming Distance Duplicate Detection Algorithm.
Calculates difference hash (dHash) for fast image similarity comparison.
"""

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING
from PIL import Image

if TYPE_CHECKING:
    from ...culler_engine import ImageItem


def compute_dhash(img: Image.Image, hash_size: int = 8) -> int:
    """
    Calculate 64-bit difference hash (dHash) for perceptual similarity comparison.
    """
    resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    pixels = list(resized.getdata())

    diff_bits = 0
    bit_index = 0
    for row in range(hash_size):
        row_start = row * (hash_size + 1)
        for col in range(hash_size):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            if left > right:
                diff_bits |= (1 << bit_index)
            bit_index += 1

    return diff_bits


def hamming_distance(hash1: int, hash2: int) -> int:
    """
    Calculate Hamming distance (number of differing bits) between two 64-bit hashes.
    """
    return bin(hash1 ^ hash2).count('1')


def find_dhash_duplicates(
    items: List['ImageItem'],
    image_loader,
    max_dist: int = 6,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[List['ImageItem']]:
    """
    Find duplicate or near-identical photos using perceptual dHash Hamming distance <= max_dist.
    """
    hashes: List[Tuple[int, 'ImageItem']] = []
    for idx, item in enumerate(items):
        try:
            img = image_loader.get_thumbnail(item.path, max_size=(160, 160))
            if img:
                h = compute_dhash(img)
                hashes.append((h, item))
        except Exception:
            pass
        if progress_callback:
            progress_callback(idx + 1, len(items))

    visited = set()
    groups: List[List['ImageItem']] = []
    for i in range(len(hashes)):
        if i in visited:
            continue
        h1, item1 = hashes[i]
        grp = [item1]
        for j in range(i + 1, len(hashes)):
            if j in visited:
                continue
            h2, item2 = hashes[j]
            if hamming_distance(h1, h2) <= max_dist:
                grp.append(item2)
                visited.add(j)
        if len(grp) > 1:
            visited.add(i)
            groups.append(grp)

    return groups
