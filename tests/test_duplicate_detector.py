import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.culler_engine import ImageItem
from culler.detectors.duplicate import (
    compute_dhash,
    hamming_distance,
    find_dhash_duplicates,
    find_md5_duplicates,
    find_burst_time_duplicates,
    find_duplicates
)


class TestDuplicateDetector(unittest.TestCase):
    """
    Automated Unit Test Suite for culler.detectors.duplicate_detector module.
    """

    def test_dhash_computation_and_hamming_distance(self):
        """
        Verify dHash computation and Hamming distance calculation.
        """
        img1 = Image.new("RGB", (100, 100), color="red")
        img2 = Image.new("RGB", (100, 100), color="red")
        img3 = Image.new("RGB", (100, 100), color="blue")

        hash1 = compute_dhash(img1)
        hash2 = compute_dhash(img2)
        hash3 = compute_dhash(img3)

        # Identical images must produce 0 Hamming distance
        self.assertEqual(hamming_distance(hash1, hash2), 0)

    def test_find_dhash_duplicates(self):
        """
        Verify find_dhash_duplicates groups identical thumbnails cleanly.
        """
        items = [
            ImageItem(Path("D:/Photos/IMG_1.JPG")),
            ImageItem(Path("D:/Photos/IMG_2.JPG")),
            ImageItem(Path("D:/Photos/IMG_3.JPG")),
        ]

        mock_loader = MagicMock()
        img = Image.new("RGB", (100, 100), color="white")
        mock_loader.get_thumbnail.return_value = img

        groups = find_dhash_duplicates(items, image_loader=mock_loader, max_dist=6)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_find_burst_time_duplicates(self):
        """
        Verify find_burst_time_duplicates groups photos taken within threshold seconds.
        """
        item1 = ImageItem(Path("D:/Photos/BURST_1.JPG"))
        item1.metadata = {"date_taken": "2026:08:08 12:00:00"}

        item2 = ImageItem(Path("D:/Photos/BURST_2.JPG"))
        item2.metadata = {"date_taken": "2026:08:08 12:00:01"}

        item3 = ImageItem(Path("D:/Photos/OTHER_1.JPG"))
        item3.metadata = {"date_taken": "2026:08:08 12:05:00"}

        groups = find_burst_time_duplicates([item1, item2, item3], threshold_seconds=2.0)
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]), {item1, item2})

    def test_unified_find_duplicates_routing(self):
        """
        Verify unified find_duplicates routes cleanly to 'dhash', 'md5', and 'burst_time'.
        """
        item1 = ImageItem(Path("D:/Photos/BURST_1.JPG"))
        item1.metadata = {"date_taken": "2026:08:08 12:00:00"}
        item2 = ImageItem(Path("D:/Photos/BURST_2.JPG"))
        item2.metadata = {"date_taken": "2026:08:08 12:00:01"}

        groups = find_duplicates([item1, item2], method="burst_time", threshold=2.0)
        self.assertEqual(len(groups), 1)


if __name__ == "__main__":
    unittest.main()
