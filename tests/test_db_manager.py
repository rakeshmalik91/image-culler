import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.db_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """
    Automated Unit Test Suite for DatabaseManager (SQLite persistence & preferences).
    """

    def setUp(self):
        # Create a temporary SQLite database file for testing
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = DatabaseManager(db_path=self.temp_db_path)

    def tearDown(self):
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_settings_kv_store(self):
        """
        Verify setting/getting string, integer, float, and boolean configuration values.
        """
        self.db.set_setting("test_key", "hello_world")
        self.assertEqual(self.db.get_setting("test_key"), "hello_world")

        self.db.set_raw_scale(0.5)
        self.assertEqual(self.db.get_raw_scale(), 0.5)

        self.db.set_white_balance("daylight")
        self.assertEqual(self.db.get_white_balance(), "daylight")

        self.db.set_picked_folder("_APPROVED")
        self.assertEqual(self.db.get_picked_folder(), "_APPROVED")

        self.db.set_rejected_folder("_DISCARDED")
        self.assertEqual(self.db.get_rejected_folder(), "_DISCARDED")

        # Blur Scan config persistence
        self.db.set_blur_method("yolo_subject")
        self.assertEqual(self.db.get_blur_method(), "yolo_subject")
        self.db.set_blur_percentile(5.0)
        self.assertEqual(self.db.get_blur_percentile(), 5.0)
        self.db.set_blur_flag_action("Reject")
        self.assertEqual(self.db.get_blur_flag_action(), "Reject")
        self.db.set_blur_tag_action("Blur")
        self.assertEqual(self.db.get_blur_tag_action(), "Blur")
        self.db.set_blur_rating_action("1 Star")
        self.assertEqual(self.db.get_blur_rating_action(), "1 Star")

        # Duplicate Scan config persistence
        self.db.set_duplicate_method("phash")
        self.assertEqual(self.db.get_duplicate_method(), "phash")
        self.db.set_duplicate_threshold(4.0)
        self.assertEqual(self.db.get_duplicate_threshold(), 4.0)
        self.db.set_duplicate_flag_action("Pick")
        self.assertEqual(self.db.get_duplicate_flag_action(), "Pick")
        self.db.set_duplicate_tag_action("Duplicate")
        self.assertEqual(self.db.get_duplicate_tag_action(), "Duplicate")
        self.db.set_duplicate_rating_action("None")
        self.assertEqual(self.db.get_duplicate_rating_action(), "None")

    def test_window_geometry_persistence(self):
        """
        Verify window dimensions, position, and maximized state persistence.
        """
        self.db.save_window_geometry(width=1600, height=900, x=100, y=50, is_maximized=True)
        w, h, x, y, is_max = self.db.get_window_geometry()

        self.assertEqual(w, 1600)
        self.assertEqual(h, 900)
        self.assertEqual(x, 100)
        self.assertEqual(y, 50)
        self.assertTrue(is_max)

    def test_image_record_persistence_and_query(self):
        """
        Verify saving image records (flag, rating, sharpness, tags) and querying by directory.
        """
        dir_path = Path("D:/Photos/Shoot1").resolve()
        file1 = str(dir_path / "DSC0001.ARW")
        file2 = str(dir_path / "DSC0002.JPG")

        self.db.save_image_record(
            file_path=file1,
            filename="DSC0001.ARW",
            flag="PICK",
            rating=5,
            sharpness=120.5,
            tags="portrait, favorite"
        )

        self.db.save_image_record(
            file_path=file2,
            filename="DSC0002.JPG",
            flag="REJECT",
            rating=0,
            sharpness=45.0,
            tags="blurry"
        )

        records = self.db.get_all_records_for_dir(str(dir_path))
        self.assertIn(file1, records)
        self.assertIn(file2, records)

        rec1 = records[file1]
        self.assertEqual(rec1["flag"], "PICK")
        self.assertEqual(rec1["rating"], 5)
        self.assertEqual(rec1["sharpness"], 120.5)
        self.assertEqual(rec1["tags"], "portrait, favorite")

        rec2 = records[file2]
        self.assertEqual(rec2["flag"], "REJECT")
        self.assertEqual(rec2["rating"], 0)

    def test_image_record_update_upsert(self):
        """
        Verify that ON CONFLICT DO UPDATE correctly updates existing records in SQLite.
        """
        dir_path = Path("D:/Photos/Shoot1").resolve()
        file1 = str(dir_path / "DSC0001.ARW")

        # Initial save
        self.db.save_image_record(file_path=file1, filename="DSC0001.ARW", flag="PICK", rating=5)

        # Update rating to 0 (unrate)
        self.db.save_image_record(file_path=file1, filename="DSC0001.ARW", flag="UNFLAGGED", rating=0)

        records = self.db.get_all_records_for_dir(str(dir_path))
        rec = records[file1]
        self.assertEqual(rec["flag"], "UNFLAGGED")
        self.assertEqual(rec["rating"], 0)

    def test_cleanup_folder_metadata(self):
        """
        Verify deleting SQLite metadata for a folder hierarchy.
        """
        dir_path = Path("D:/Photos/Shoot1").resolve()
        file1 = str(dir_path / "DSC0001.ARW")
        file2 = str(dir_path / "DSC0002.JPG")

        self.db.save_image_record(file_path=file1, filename="DSC0001.ARW", flag="PICK", rating=3)
        self.db.save_image_record(file_path=file2, filename="DSC0002.JPG", flag="REJECT", rating=1)

        deleted = self.db.cleanup_folder_metadata(str(dir_path))
        self.assertEqual(deleted, 2)

        records = self.db.get_all_records_for_dir(str(dir_path))
        self.assertEqual(len(records), 0)


if __name__ == "__main__":
    unittest.main()
