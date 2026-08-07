import sys
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.image_loader import ImageLoader


class TestImageLoader(unittest.TestCase):
    """
    Automated Unit Test Suite for ImageLoader (supported formats, thumbnail caching, and fast downscaling).
    """

    def setUp(self):
        self.loader = ImageLoader()

    def test_supported_extensions(self):
        """
        Verify supported image format detection (.ARW, .JPG, .PNG, .HEIC).
        """
        self.assertTrue(ImageLoader.is_supported(Path("sample.arw")))
        self.assertTrue(ImageLoader.is_supported(Path("sample.ARW")))
        self.assertTrue(ImageLoader.is_supported(Path("photo.jpg")))
        self.assertTrue(ImageLoader.is_supported(Path("photo.JPG")))
        self.assertTrue(ImageLoader.is_supported(Path("image.png")))
        self.assertTrue(ImageLoader.is_supported(Path("image.heic")))

        self.assertFalse(ImageLoader.is_supported(Path("document.pdf")))
        self.assertFalse(ImageLoader.is_supported(Path("script.py")))
        self.assertFalse(ImageLoader.is_supported(Path("data.txt")))

    def test_thumbnail_ram_caching(self):
        """
        Verify storing and retrieving thumbnails in RAM cache.
        """
        test_path = Path("D:/Photos/TEST_CACHE.JPG")
        dummy_img = Image.new("RGB", (100, 100), color="blue")

        # Key thumbnail into cache
        cache_key = (str(test_path), (100, 100), 0.10, "camera")
        self.loader._thumb_cache[cache_key] = dummy_img

        cached = self.loader.get_cached_thumbnail(test_path)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.size, (100, 100))

    def test_full_image_ram_caching(self):
        """
        Verify storing and retrieving full-resolution preview images in RAM cache.
        """
        test_path = Path("D:/Photos/TEST_FULL.JPG")
        dummy_img = Image.new("RGB", (1920, 1080), color="green")

        cache_key = (str(test_path), 0.25, "camera")
        self.loader._full_cache[cache_key] = dummy_img

        cached = self.loader.get_cached_full_image(test_path, raw_scale=0.25, white_balance="camera")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.size, (1920, 1080))

    def test_clear_cache(self):
        """
        Verify clear_cache empties both thumbnail and full image RAM caches.
        """
        test_path = Path("D:/Photos/TEST.JPG")
        dummy_img = Image.new("RGB", (50, 50))

        self.loader._thumb_cache[(str(test_path), (50, 50), 0.10, "camera")] = dummy_img
        self.loader._full_cache[(str(test_path), 0.25, "camera")] = dummy_img

        self.loader.clear_cache()

        self.assertEqual(len(self.loader._thumb_cache), 0)
        self.assertEqual(len(self.loader._full_cache), 0)


    def test_exif_orientation_handling(self):
        """
        Verify EXIF orientation rotation transforms via apply_exif_orientation.
        """
        img = Image.new("RGB", (300, 200), color="red")
        transposed = ImageLoader.apply_exif_orientation(img)
        self.assertIsNotNone(transposed)
        self.assertEqual(transposed.size, (300, 200))

        # Test injecting orientation 6 (Rotate 90 CW) -> 300x200 landscape becomes 200x300 portrait
        portrait_img = ImageLoader.apply_exif_orientation(img, orientation=6)
        self.assertEqual(portrait_img.size, (200, 300))

    def test_get_orientation(self):
        """
        Verify get_orientation defaults cleanly to 1 for unknown or non-existent files.
        """
        orient = self.loader.exif_wrapper.get_orientation("non_existent_file.jpg")
        self.assertEqual(orient, 1)


if __name__ == "__main__":
    unittest.main()
