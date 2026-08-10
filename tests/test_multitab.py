import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler.culler_engine import CullingSession, ImageItem, FlagState
from culler.db_manager import DatabaseManager


class TestDbManagerTabs(unittest.TestCase):
    """
    Unit tests for DatabaseManager open_tabs persistence methods.
    """

    def setUp(self):
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

    def test_get_open_tabs_default_empty(self):
        result = self.db.get_open_tabs()
        self.assertEqual(result, {"tabs": [], "active_index": 0})

    def test_save_and_get_open_tabs(self):
        tabs_data = [
            {"directory": "D:/Photos/2024", "tab_label": "2024", "filter_values": {"flag": "Pick"}},
            {"directory": "D:/Photos/2023", "tab_label": "2023", "filter_values": {"flag": "All"}},
        ]
        self.db.save_open_tabs(tabs_data, active_index=1)

        result = self.db.get_open_tabs()
        self.assertEqual(result["tabs"], tabs_data)
        self.assertEqual(result["active_index"], 1)

    def test_get_active_tab_index_default(self):
        self.assertEqual(self.db.get_active_tab_index(), 0)

    def test_get_active_tab_index_stored(self):
        self.db.save_open_tabs([{"directory": "D:/Photos"}], active_index=2)
        self.assertEqual(self.db.get_active_tab_index(), 2)


class TestImageCullerAppTabLogic(unittest.TestCase):
    """
    Unit tests for ImageCullerApp tab management logic (_create_tab_info, _get_active_tab,
    _save_active_tab_state, _switch_tab, _close_tab, _add_tab, _persist_tabs_state).
    """

    def setUp(self):
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

    def _make_app(self):
        from gui import ImageCullerApp
        app = MagicMock()
        app.db = self.db
        app.tabs = []
        app.active_tab_index = -1
        app.current_items = []
        app.current_index = -1
        app.selected_indices = set()
        app.selection_anchor_idx = 0
        app.toolbar = MagicMock()
        app.toolbar.get_filter_values.return_value = {
            "flag": "All",
            "rating": [],
            "format": "All Formats",
            "tag": []
        }
        app.thumb_list = MagicMock()
        app.viewer = MagicMock()
        app.meta_panel = MagicMock()
        app.tab_bar = MagicMock()
        app.tab_bar.add_tab = MagicMock(return_value=0)
        app._create_tab_info = lambda directory: ImageCullerApp._create_tab_info(app, directory)
        app._get_active_tab = lambda: ImageCullerApp._get_active_tab(app)
        app._get_active_session = lambda: ImageCullerApp._get_active_session(app)
        app._save_active_tab_state = lambda: ImageCullerApp._save_active_tab_state(app)
        app._switch_tab = lambda index: ImageCullerApp._switch_tab(app, index)
        app._close_tab = lambda index: ImageCullerApp._close_tab(app, index)
        app._add_tab = lambda directory: ImageCullerApp._add_tab(app, directory)
        app._persist_tabs_state = lambda: ImageCullerApp._persist_tabs_state(app)
        app._restore_tabs_state = lambda: ImageCullerApp._restore_tabs_state(app)
        app._apply_tab_state = lambda tab: ImageCullerApp._apply_tab_state(app, tab)
        app._load_tab_directory = MagicMock()
        return app

    def test_create_tab_info(self):
        from gui import ImageCullerApp

        app = self._make_app()
        tab = ImageCullerApp._create_tab_info(app, "D:/Photos/2024")

        self.assertEqual(tab["directory"], str(Path("D:/Photos/2024").resolve()))
        self.assertEqual(tab["tab_label"], "2024")
        self.assertIn("session", tab)
        self.assertIn("filter_values", tab)
        self.assertEqual(tab["filter_values"]["flag"], "All")
        self.assertEqual(tab["current_items"], [])
        self.assertEqual(tab["current_index"], -1)
        self.assertEqual(tab["selected_indices"], set())
        self.assertEqual(tab["selection_anchor_idx"], 0)
        self.assertFalse(tab["is_loaded"])

    def test_add_tab_appends_and_activates(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._load_tab_directory = MagicMock()
        app._persist_tabs_state = MagicMock()

        ImageCullerApp._add_tab(app, "D:/Photos/A")

        self.assertEqual(len(app.tabs), 1)
        self.assertEqual(app.tabs[0]["directory"], str(Path("D:/Photos/A").resolve()))
        self.assertEqual(app.active_tab_index, 0)
        app.tab_bar.add_tab.assert_called_once_with("A")
        app._load_tab_directory.assert_called_once_with(app.tabs[0], show_progress=True)
        app._persist_tabs_state.assert_called_once()

    def test_close_tab_removes_and_readjusts_active(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._persist_tabs_state = MagicMock()
        ImageCullerApp._add_tab(app, "D:/Photos/A")
        ImageCullerApp._add_tab(app, "D:/Photos/B")
        ImageCullerApp._add_tab(app, "D:/Photos/C")

        app.tab_bar.reset_mock()
        app._persist_tabs_state.reset_mock()

        ImageCullerApp._close_tab(app, 1)

        self.assertEqual(len(app.tabs), 2)
        self.assertEqual(app.tabs[0]["directory"], str(Path("D:/Photos/A").resolve()))
        self.assertEqual(app.tabs[1]["directory"], str(Path("D:/Photos/C").resolve()))
        app.tab_bar.remove_tab.assert_called_once_with(1)
        self.assertEqual(app.active_tab_index, 1)
        app._persist_tabs_state.assert_called_once()

    def test_close_active_tab_switches_to_neighbor(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._persist_tabs_state = MagicMock()
        app._load_tab_directory = MagicMock()
        app._apply_tab_state = MagicMock()
        ImageCullerApp._add_tab(app, "D:/Photos/A")
        ImageCullerApp._add_tab(app, "D:/Photos/B")

        app.tab_bar.reset_mock()
        app._persist_tabs_state.reset_mock()

        app.tabs[0]["is_loaded"] = True
        app.active_tab_index = 1
        ImageCullerApp._close_tab(app, 1)

        self.assertEqual(app.active_tab_index, 0)
        app._apply_tab_state.assert_called_once_with(app.tabs[0])

    def test_close_tab_when_only_one_does_nothing(self):
        from gui import ImageCullerApp

        app = self._make_app()
        ImageCullerApp._add_tab(app, "D:/Photos/A")

        app.tab_bar.reset_mock()
        ImageCullerApp._close_tab(app, 0)

        self.assertEqual(len(app.tabs), 1)
        app.tab_bar.remove_tab.assert_not_called()

    def test_switch_tab_saves_and_applies_state(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._persist_tabs_state = MagicMock()
        app._load_tab_directory = MagicMock()
        app._apply_tab_state = MagicMock()
        app._save_active_tab_state = MagicMock()

        ImageCullerApp._add_tab(app, "D:/Photos/A")
        ImageCullerApp._add_tab(app, "D:/Photos/B")
        app.tab_bar.reset_mock()
        app._persist_tabs_state.reset_mock()

        app.active_tab_index = 0
        tab_b = app.tabs[1]
        tab_b["is_loaded"] = True
        ImageCullerApp._switch_tab(app, 1)

        app._save_active_tab_state.assert_called_once()
        app.tab_bar.set_active.assert_called_once_with(1)
        app._apply_tab_state.assert_called_once_with(tab_b)
        app._persist_tabs_state.assert_called_once()
        self.assertEqual(app.active_tab_index, 1)

    def test_switch_tab_loads_if_not_loaded(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._persist_tabs_state = MagicMock()
        app._load_tab_directory = MagicMock()
        app._apply_tab_state = MagicMock()

        ImageCullerApp._add_tab(app, "D:/Photos/A")
        ImageCullerApp._add_tab(app, "D:/Photos/B")
        app.tab_bar.reset_mock()
        app._persist_tabs_state.reset_mock()
        app._load_tab_directory.reset_mock()

        app.active_tab_index = 0
        tab_b = app.tabs[1]
        tab_b["is_loaded"] = False
        ImageCullerApp._switch_tab(app, 1)

        app._load_tab_directory.assert_called_once_with(tab_b, show_progress=True)
        app._apply_tab_state.assert_called_once_with(tab_b)

    def test_switch_same_index_noop(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._persist_tabs_state = MagicMock()
        ImageCullerApp._add_tab(app, "D:/Photos/A")
        app._save_active_tab_state = MagicMock()

        ImageCullerApp._switch_tab(app, 0)

        app._save_active_tab_state.assert_not_called()

    def test_save_active_tab_state(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app.current_items = [MagicMock()]
        app.current_index = 0
        app.selected_indices = {0, 1}
        app.selection_anchor_idx = 1

        tab = {
            "directory": "D:/Photos",
            "tab_label": "Photos",
            "session": MagicMock(),
            "filter_values": {},
            "current_items": [],
            "current_index": -1,
            "selected_indices": set(),
            "selection_anchor_idx": 0,
            "is_loaded": False,
        }
        app.tabs = [tab]
        app.active_tab_index = 0

        ImageCullerApp._save_active_tab_state(app)

        self.assertEqual(tab["current_items"], app.current_items)
        self.assertEqual(tab["current_index"], 0)
        self.assertEqual(tab["selected_indices"], {0, 1})
        self.assertEqual(tab["selection_anchor_idx"], 1)
        self.assertEqual(tab["filter_values"]["flag"], "All")
        app.toolbar.get_filter_values.assert_called_once()

    def test_persist_tabs_state_roundtrip(self):
        from gui import ImageCullerApp

        app = self._make_app()
        ImageCullerApp._add_tab(app, "D:/Photos/A")
        ImageCullerApp._add_tab(app, "D:/Photos/B")

        app.tabs[0]["filter_values"] = {"flag": "Pick", "rating": ["5"], "format": ".JPG", "tag": ["Blur"]}
        app.tabs[1]["filter_values"] = {"flag": "All", "rating": [], "format": "All Formats", "tag": []}
        app.active_tab_index = 1

        ImageCullerApp._persist_tabs_state(app)

        loaded = self.db.get_open_tabs()
        self.assertEqual(len(loaded["tabs"]), 2)
        self.assertEqual(loaded["tabs"][0]["directory"], str(Path("D:/Photos/A").resolve()))
        self.assertEqual(loaded["tabs"][0]["filter_values"]["flag"], "Pick")
        self.assertEqual(loaded["tabs"][1]["directory"], str(Path("D:/Photos/B").resolve()))
        self.assertEqual(loaded["active_index"], 1)

    def test_restore_tabs_state(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._load_tab_directory = MagicMock()
        app._apply_tab_state = MagicMock()

        tabs_payload = [
            {"directory": "D:/Photos/A", "tab_label": "A", "filter_values": {"flag": "Pick"}},
            {"directory": "D:/Photos/B", "tab_label": "B", "filter_values": {"flag": "Reject"}},
        ]
        self.db.save_open_tabs(tabs_payload, active_index=0)

        with patch("os.path.exists", return_value=True):
            ImageCullerApp._restore_tabs_state(app)

        self.assertEqual(len(app.tabs), 2)
        self.assertEqual(app.tabs[0]["tab_label"], "A")
        self.assertEqual(app.tabs[0]["filter_values"]["flag"], "Pick")
        self.assertEqual(app.tabs[1]["tab_label"], "B")
        self.assertEqual(app.tabs[1]["filter_values"]["flag"], "Reject")
        self.assertEqual(app.active_tab_index, 0)
        self.assertFalse(app.tabs[0]["is_loaded"])
        self.assertFalse(app.tabs[1]["is_loaded"])
        app._load_tab_directory.assert_called_once_with(app.tabs[0], show_progress=True)

    def test_restore_tabs_skips_missing_directories(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app._load_tab_directory = MagicMock()

        tabs_payload = [
            {"directory": "D:/Photos/Exists", "tab_label": "Exists", "filter_values": {}},
            {"directory": "D:/Photos/Missing", "tab_label": "Missing", "filter_values": {}},
        ]
        self.db.save_open_tabs(tabs_payload, active_index=0)

        with patch("os.path.exists", side_effect=lambda p: "Exists" in p):
            ImageCullerApp._restore_tabs_state(app)

        self.assertEqual(len(app.tabs), 1)
        self.assertEqual(app.tabs[0]["tab_label"], "Exists")

    def test_get_active_tab_returns_correct_tab(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app.tabs = [{"directory": "A"}, {"directory": "B"}, {"directory": "C"}]
        app.active_tab_index = 2

        tab = ImageCullerApp._get_active_tab(app)
        self.assertEqual(tab["directory"], "C")

    def test_get_active_tab_returns_none_when_empty(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app.tabs = []
        app.active_tab_index = -1

        tab = ImageCullerApp._get_active_tab(app)
        self.assertIsNone(tab)

    def test_tab_independent_filter_values(self):
        from gui import ImageCullerApp

        app = self._make_app()
        app.toolbar.get_filter_values.return_value = {"flag": "Pick", "rating": ["5"], "format": ".ARW", "tag": ["Blur"]}

        ImageCullerApp._add_tab(app, "D:/Photos/A")
        ImageCullerApp._add_tab(app, "D:/Photos/B")

        app.toolbar.get_filter_values.return_value = {"flag": "All", "rating": [], "format": "All Formats", "tag": []}
        app.current_items = []
        app.current_index = -1
        app.selected_indices = set()
        app.selection_anchor_idx = 0
        ImageCullerApp._save_active_tab_state(app)

        app.toolbar.get_filter_values.return_value = {"flag": "Reject", "rating": ["1", "2"], "format": ".JPG", "tag": ["Dark"]}
        app.current_items = []
        app.current_index = -1
        app.selected_indices = set()
        app.selection_anchor_idx = 0
        ImageCullerApp._save_active_tab_state(app)

        self.assertEqual(app.tabs[0]["filter_values"]["flag"], "Pick")
        self.assertEqual(app.tabs[0]["filter_values"]["rating"], ["5"])
        self.assertEqual(app.tabs[1]["filter_values"]["flag"], "Reject")
        self.assertEqual(app.tabs[1]["filter_values"]["rating"], ["1", "2"])


class TestTabBarDynamicIndex(unittest.TestCase):
    """
    Unit tests for TabBar dynamic index lookups after tab removal and reordering.
    """

    def test_close_btn_click_resolves_correct_index_after_removal(self):
        from culler.gui.tab_bar import TabBar
        closed_indices = []

        bar = TabBar.__new__(TabBar)
        bar.on_tab_closed = lambda idx: closed_indices.append(idx)
        bar._tab_buttons = [MagicMock(), MagicMock(), MagicMock()]
        bar._close_buttons = [MagicMock(), MagicMock(), MagicMock()]
        bar._tab_labels = ["Tab 0", "Tab 1", "Tab 2"]
        bar._tab_count = 3
        bar._active_index = 0
        bar._update_scroll_region = MagicMock()

        btn0, btn1, btn2 = bar._close_buttons[0], bar._close_buttons[1], bar._close_buttons[2]

        # Close middle tab (index 1)
        bar._handle_close_btn_click(btn1)
        self.assertEqual(closed_indices, [1])

        # Remove tab 1
        bar.remove_tab(1)
        self.assertEqual(bar._tab_count, 2)
        self.assertEqual(bar._close_buttons, [btn0, btn2])

        # Click close on what was originally btn2 (now at list index 1)
        closed_indices.clear()
        bar._handle_close_btn_click(btn2)
        self.assertEqual(closed_indices, [1], "Clicking close on btn2 should resolve to new index 1, not old index 2")

    def test_get_index_for_widget_after_reorder(self):
        from culler.gui.tab_bar import TabBar

        bar = TabBar.__new__(TabBar)
        btnA, btnB, btnC = MagicMock(), MagicMock(), MagicMock()
        bar._tab_buttons = [btnA, btnB, btnC]
        bar._close_buttons = [MagicMock(), MagicMock(), MagicMock()]
        bar._tab_labels = ["A", "B", "C"]
        bar._tab_count = 3
        bar._active_index = 0
        bar._update_scroll_region = MagicMock()

        bar.reorder(0, 2)  # Move A to position 2: [B, C, A]
        self.assertEqual(bar._get_index_for_widget(btnA), 2)
        self.assertEqual(bar._get_index_for_widget(btnB), 0)
        self.assertEqual(bar._get_index_for_widget(btnC), 1)


if __name__ == "__main__":
    unittest.main()
