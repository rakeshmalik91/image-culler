import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.dataset_exporter import (
    create_dataset_structure,
    get_annotations_file,
    load_manual_annotations,
    get_manual_annotation,
    save_manual_annotation,
    delete_manual_annotation,
    normalize_box,
    save_annotation
)


class TestDatasetExporter(unittest.TestCase):
    """
    Automated Unit Test Suite for dataset_exporter and structured text annotations under _DATASET/.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_dataset_")
        self.dataset_dir = Path(self.temp_dir) / "_DATASET"

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_dataset_structure(self):
        """
        Verify that images/train, labels/train, and dataset.yaml are created.
        """
        img_dir, lbl_dir = create_dataset_structure(str(self.dataset_dir))
        self.assertTrue(img_dir.exists())
        self.assertTrue(lbl_dir.exists())
        yaml_file = self.dataset_dir / "dataset.yaml"
        self.assertTrue(yaml_file.exists())
        content = yaml_file.read_text(encoding="utf-8")
        self.assertIn("0: subject", content)
        self.assertIn("1: eye", content)

    def test_normalize_box(self):
        """
        Verify pixel bounding box conversion to normalized YOLO box format.
        """
        # (x1, y1, x2, y2) on 1000x500 image
        box = (100, 50, 300, 250)
        norm_str = normalize_box(box, img_w=1000, img_h=500)
        parts = [float(p) for p in norm_str.split()]
        self.assertEqual(len(parts), 4)
        cx, cy, bw, bh = parts
        self.assertAlmostEqual(cx, 0.2)
        self.assertAlmostEqual(cy, 0.3)
        self.assertAlmostEqual(bw, 0.2)
        self.assertAlmostEqual(bh, 0.4)

    def test_save_and_load_manual_annotation(self):
        """
        Verify saving structured manual bounding boxes to annotations.json and loading them.
        """
        img_path = str(Path(self.temp_dir) / "photos" / "DSC_001.JPG")
        subj_box = (0.1, 0.2, 0.5, 0.6)
        eye_box = (0.2, 0.25, 0.3, 0.35)

        saved = save_manual_annotation(
            image_path=img_path,
            manual_detection_box=subj_box,
            manual_eye_box=eye_box,
            dataset_dir=str(self.dataset_dir)
        )
        self.assertTrue(saved)

        # Verify json file exists on disk under dataset_dir
        json_file = get_annotations_file(str(self.dataset_dir))
        self.assertTrue(json_file.exists())

        # Load all
        all_annos = load_manual_annotations(str(self.dataset_dir))
        resolved_key = str(Path(img_path).resolve())
        self.assertIn(resolved_key, all_annos)
        rec = all_annos[resolved_key]
        self.assertEqual(rec["manual_detection_box"], subj_box)
        self.assertEqual(rec["manual_eye_box"], eye_box)
        self.assertEqual(rec["filename"], "DSC_001.JPG")

        # Get specific
        single = get_manual_annotation(img_path, dataset_dir=str(self.dataset_dir))
        self.assertIsNotNone(single)
        self.assertEqual(single["manual_detection_box"], subj_box)

    def test_delete_manual_annotation(self):
        """
        Verify removing an annotation entry from annotations.json.
        """
        img_path1 = str(Path(self.temp_dir) / "DSC_001.JPG")
        img_path2 = str(Path(self.temp_dir) / "DSC_002.JPG")

        save_manual_annotation(img_path1, (0.1, 0.1, 0.4, 0.4), None, dataset_dir=str(self.dataset_dir))
        save_manual_annotation(img_path2, None, (0.2, 0.2, 0.3, 0.3), dataset_dir=str(self.dataset_dir))

        all_annos = load_manual_annotations(str(self.dataset_dir))
        self.assertEqual(len(all_annos), 2)

        deleted = delete_manual_annotation(img_path1, dataset_dir=str(self.dataset_dir))
        self.assertTrue(deleted)

        all_annos = load_manual_annotations(str(self.dataset_dir))
        self.assertEqual(len(all_annos), 1)
        self.assertNotIn(str(Path(img_path1).resolve()), all_annos)
        self.assertIn(str(Path(img_path2).resolve()), all_annos)

    def test_save_annotation_creates_yolo_and_structured_json(self):
        """
        Verify save_annotation produces YOLO images/labels AND updates annotations.json.
        """
        # Create a dummy image
        img_file = Path(self.temp_dir) / "sample.jpg"
        img = Image.new("RGB", (640, 480), color="blue")
        img.save(img_file)

        success = save_annotation(
            image_path=str(img_file),
            img_w=640,
            img_h=480,
            subject_box=(64, 48, 320, 240),
            eye_box=(128, 96, 160, 120),
            dataset_dir=str(self.dataset_dir),
            pil_image=img
        )
        self.assertTrue(success)

        # Check YOLO label file created
        labels_dir = self.dataset_dir / "labels" / "train"
        label_files = list(labels_dir.glob("*.txt"))
        self.assertEqual(len(label_files), 1)
        lbl_content = label_files[0].read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lbl_content), 2)
        self.assertTrue(lbl_content[0].startswith("0 "))  # Subject
        self.assertTrue(lbl_content[1].startswith("1 "))  # Eye

        # Check structured JSON
        anno = get_manual_annotation(str(img_file), dataset_dir=str(self.dataset_dir))
        self.assertIsNotNone(anno)
        self.assertAlmostEqual(anno["manual_detection_box"][0], 0.1)
        self.assertAlmostEqual(anno["manual_detection_box"][2], 0.5)


if __name__ == "__main__":
    unittest.main()
