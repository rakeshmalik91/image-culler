import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import customtkinter as ctk
from culler.db_manager import DatabaseManager
from culler.gui.settings_dialog import SettingsDialog


class TestSettingsDialog(unittest.TestCase):
    """
    Automated Unit Test Suite for SettingsDialog layout & configuration persistence.
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = DatabaseManager(db_path=self.temp_db_path)
        try:
            self.root = ctk.CTk()
            self.root.withdraw()
            self.gui_available = True
        except Exception:
            self.gui_available = False

    def tearDown(self):
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
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

    def test_settings_dialog_initialization(self):
        """Verify that SettingsDialog initializes widgets without error."""
        if not self.gui_available:
            self.skipTest("GUI environment not available")

        saved = False

        def on_save():
            nonlocal saved
            saved = True

        dialog = SettingsDialog(master=self.root, db=self.db, on_save=on_save)
        self.assertEqual(dialog.title(), "⚙️ Application Settings")
        self.assertTrue(dialog.resizable()[0])
        self.assertTrue(dialog.resizable()[1])
        self.assertIsNotNone(dialog.tabview)

        # Trigger save settings logic directly
        dialog._save_settings()
        self.assertTrue(saved)


if __name__ == "__main__":
    unittest.main()
