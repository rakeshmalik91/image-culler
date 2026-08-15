import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.gui.splash_screen import SplashScreen
from culler.db_manager import DatabaseManager


class TestSplashScreen(unittest.TestCase):
    """
    Unit tests for SplashScreen component.
    """

    def test_splash_screen_initialization_and_status(self):
        with patch("customtkinter.CTkToplevel.__init__", return_value=None), \
             patch.object(SplashScreen, "overrideredirect"), \
             patch.object(SplashScreen, "configure"), \
             patch.object(SplashScreen, "geometry"), \
             patch.object(SplashScreen, "attributes"), \
             patch.object(SplashScreen, "winfo_screenwidth", return_value=1920), \
             patch.object(SplashScreen, "winfo_screenheight", return_value=1080), \
             patch.object(SplashScreen, "update_idletasks"), \
             patch.object(SplashScreen, "update"):

            splash = SplashScreen.__new__(SplashScreen)
            splash.lbl_status = MagicMock()
            splash.progress = MagicMock()

            # Test set_status
            SplashScreen.set_status(splash, "Loading test folder...")
            splash.lbl_status.configure.assert_called_with(text="Loading test folder...")

            # Test close
            SplashScreen.close(splash)
            splash.progress.stop.assert_called_once()

    def test_image_culler_app_splash_screen_lifecycle(self):
        from gui import ImageCullerApp

        temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_db_fd)
        db = DatabaseManager(db_path=temp_db_path)

        with patch("customtkinter.CTk.__init__", return_value=None):
            app = ImageCullerApp.__new__(ImageCullerApp)
            app.db = db
            app.tabs = []
            app.active_tab_index = -1
            app.current_items = []
            app.current_index = -1
            app.selected_indices = set()
            app.selection_anchor_idx = 0
            app._create_components = MagicMock()
            app._bind_events = MagicMock()
            app._restore_tabs_state = MagicMock()
            app.deiconify = MagicMock()
            app.withdraw = MagicMock()
            app.lift = MagicMock()
            app.focus_force = MagicMock()
            app.update_idletasks = MagicMock()
            app.update = MagicMock()
            app.title = MagicMock()
            app.geometry = MagicMock()
            app.after = MagicMock()

            splash = MagicMock()
            ImageCullerApp.__init__(app, initial_path=None, show_splash=False, splash_screen=splash)

        app.withdraw.assert_called_once()
        self.assertTrue(splash.set_status.called)
        app.deiconify.assert_called_once()
        splash.close.assert_called_once()

        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

    def test_image_culler_app_creates_splash_when_enabled(self):
        from gui import ImageCullerApp

        temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_db_fd)
        db = DatabaseManager(db_path=temp_db_path)

        with patch("customtkinter.CTk.__init__", return_value=None), \
             patch("gui.SplashScreen") as mock_splash_cls:
            mock_splash_inst = MagicMock()
            mock_splash_cls.return_value = mock_splash_inst

            app = ImageCullerApp.__new__(ImageCullerApp)
            app.db = db
            app.tabs = []
            app.active_tab_index = -1
            app.current_items = []
            app.current_index = -1
            app.selected_indices = set()
            app.selection_anchor_idx = 0
            app._create_components = MagicMock()
            app._bind_events = MagicMock()
            app._restore_tabs_state = MagicMock()
            app.deiconify = MagicMock()
            app.withdraw = MagicMock()
            app.lift = MagicMock()
            app.focus_force = MagicMock()
            app.update_idletasks = MagicMock()
            app.update = MagicMock()
            app.title = MagicMock()
            app.geometry = MagicMock()
            app.after = MagicMock()

            ImageCullerApp.__init__(app, initial_path="D:/Photos/Trip", show_splash=True)

            mock_splash_cls.assert_called_once_with(master=app)
            self.assertTrue(mock_splash_inst.set_status.called)
            mock_splash_inst.close.assert_called_once()

        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
