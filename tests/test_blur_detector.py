import sys
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.detectors.blur import (
    calculate_sharpness,
    compute_laplacian_sharpness,
    compute_fft_sharpness,
    compute_bird_subject_sharpness
)


class TestBlurDetector(unittest.TestCase):
    """
    Automated Unit Test Suite for culler.detectors.blur_detector module.
    """

    def setUp(self):
        # Create synthetic test images (sharp checkboard & blurry solid)
        self.sharp_img = Image.new("RGB", (200, 200), color="white")
        # Draw high-contrast stripes on sharp image
        for x in range(0, 200, 10):
            for y in range(0, 200, 10):
                if (x + y) % 20 == 0:
                    for px in range(10):
                        for py in range(10):
                            if x + px < 200 and y + py < 200:
                                self.sharp_img.putpixel((x + px, y + py), (0, 0, 0))

        self.blurry_img = Image.new("RGB", (200, 200), color="gray")

    def test_sharpness_algorithms_return_higher_for_sharp_image(self):
        """
        Verify that all blur algorithms assign significantly higher scores to high-contrast sharp images than blurry ones.
        """
        methods = ["laplacian", "ai_subject", "fft"]

        for method in methods:
            sharp_score = calculate_sharpness(self.sharp_img, method=method)
            blurry_score = calculate_sharpness(self.blurry_img, method=method)

            self.assertGreater(sharp_score, blurry_score, f"Algorithm '{method}' failed to rank sharp image higher!")

    def test_backward_compat_aliases(self):
        """
        Verify that old method names still work via backward-compat aliases.
        """
        old_methods = ["tenengrad", "brenner", "local_var", "bird_subject", "yolo_subject"]
        for method in old_methods:
            score = calculate_sharpness(self.sharp_img, method=method)
            self.assertGreater(score, 0.0, f"Backward-compat alias '{method}' returned 0!")

    def test_invalid_or_none_image_handling(self):
        """
        Verify that passing None or invalid images safely returns 0.0 without throwing exceptions.
        """
        self.assertEqual(calculate_sharpness(None), 0.0)


if __name__ == "__main__":
    unittest.main()
