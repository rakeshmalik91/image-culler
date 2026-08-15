import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from culler import (
    CullingSession,
    ImageItem,
    FlagState,
    resolve_input_path,
    find_item_index_by_path,
)
from culler.db_manager import DatabaseManager
import importlib.util

culler_py_path = Path(__file__).resolve().parent.parent / "culler.py"
spec = importlib.util.spec_from_file_location("culler_cli", culler_py_path)
culler_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(culler_cli)

build_parser = culler_cli.build_parser
cmd_scan = culler_cli.cmd_scan
cmd_cull = culler_cli.cmd_cull


class TestResolveInputPath(unittest.TestCase):
    """
    Tests for resolve_input_path.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.img_file = self.dir_path / "DSC01234.JPG"
        self.img_file.write_bytes(b"dummy image bytes")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_directory_path(self):
        folder, target = resolve_input_path(self.dir_path)
        self.assertEqual(folder, self.dir_path.resolve())
        self.assertIsNone(target)

    def test_resolve_directory_str(self):
        folder, target = resolve_input_path(str(self.dir_path))
        self.assertEqual(folder, self.dir_path.resolve())
        self.assertIsNone(target)

    def test_resolve_image_file_path(self):
        folder, target = resolve_input_path(self.img_file)
        self.assertEqual(folder, self.dir_path.resolve())
        self.assertEqual(target, self.img_file.resolve())

    def test_resolve_image_file_str(self):
        folder, target = resolve_input_path(str(self.img_file))
        self.assertEqual(folder, self.dir_path.resolve())
        self.assertEqual(target, self.img_file.resolve())

    def test_resolve_nonexistent_path_raises(self):
        nonexistent = self.dir_path / "nonexistent.jpg"
        with self.assertRaises(FileNotFoundError):
            resolve_input_path(nonexistent)


class TestFindItemIndexByPath(unittest.TestCase):
    """
    Tests for find_item_index_by_path and CullingSession.find_item.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        
        self.f1 = self.dir_path / "IMG_001.JPG"
        self.f2_raw = self.dir_path / "DSC0002.ARW"
        self.f2_jpg = self.dir_path / "DSC0002.JPG"
        self.f3 = self.dir_path / "PHOTO_003.PNG"

        for f in [self.f1, self.f2_raw, self.f2_jpg, self.f3]:
            f.write_bytes(b"data")

        self.item1 = ImageItem(self.f1)
        
        self.item2 = ImageItem(self.f2_raw)
        self.item2.is_stacked = True
        self.item2.stacked_paths = [self.f2_raw, self.f2_jpg]

        self.item3 = ImageItem(self.f3)

        self.items = [self.item1, self.item2, self.item3]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_find_exact_primary_path(self):
        idx, matched = find_item_index_by_path(self.items, self.f1)
        self.assertEqual(idx, 0)
        self.assertEqual(matched, self.f1)

    def test_find_stacked_secondary_variant(self):
        # Searching for DSC0002.JPG should find item index 1 and matched path DSC0002.JPG
        idx, matched = find_item_index_by_path(self.items, self.f2_jpg)
        self.assertEqual(idx, 1)
        self.assertEqual(matched, self.f2_jpg)

    def test_find_stacked_primary_raw(self):
        idx, matched = find_item_index_by_path(self.items, self.f2_raw)
        self.assertEqual(idx, 1)
        self.assertEqual(matched, self.f2_raw)

    def test_find_case_insensitive_path(self):
        idx, matched = find_item_index_by_path(self.items, str(self.f3).lower())
        self.assertEqual(idx, 2)

    def test_find_non_matching_returns_negative_one(self):
        missing = self.dir_path / "MISSING.JPG"
        missing.write_bytes(b"data")
        idx, matched = find_item_index_by_path(self.items, missing)
        self.assertEqual(idx, -1)
        self.assertIsNone(matched)

    def test_find_empty_items_or_none(self):
        self.assertEqual(find_item_index_by_path([], self.f1), (-1, None))
        self.assertEqual(find_item_index_by_path(self.items, None), (-1, None))

    def test_session_find_item_method(self):
        session = CullingSession()
        session.items = list(self.items)
        idx, matched = session.find_item(self.f2_jpg)
        self.assertEqual(idx, 1)
        self.assertEqual(matched, self.f2_jpg)


class TestCliPathHandling(unittest.TestCase):
    """
    Tests for CLI argument parsing and commands with folder vs image file.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.img1 = self.dir_path / "TEST_01.JPG"
        self.img2 = self.dir_path / "TEST_02.JPG"
        self.img1.write_bytes(b"jpg1")
        self.img2.write_bytes(b"jpg2")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_parser_subcommands(self):
        parser = build_parser()
        # Scan with folder
        args = parser.parse_args(["scan", str(self.dir_path)])
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.path, str(self.dir_path))

        # Scan with image file
        args_file = parser.parse_args(["scan", str(self.img1)])
        self.assertEqual(args_file.command, "scan")
        self.assertEqual(args_file.path, str(self.img1))

        # Cull with image file
        args_cull = parser.parse_args(["cull", str(self.img2)])
        self.assertEqual(args_cull.command, "cull")
        self.assertEqual(args_cull.path, str(self.img2))

        # GUI command with optional path
        args_gui = parser.parse_args(["gui", str(self.img1)])
        self.assertEqual(args_gui.command, "gui")
        self.assertEqual(args_gui.path, str(self.img1))

    def test_cmd_scan_with_image_file(self):
        session = CullingSession()
        parser = build_parser()
        args = parser.parse_args(["scan", str(self.img1)])

        with patch.object(culler_cli.console, "print") as mock_print:
            with patch.object(session, "scan_directory", return_value=[ImageItem(self.img1), ImageItem(self.img2)]):
                with patch.object(session, "get_summary_stats", return_value={
                    "total_images": 2, "total_size_mb": 1.0, "picked": 0, "rejected": 0, "unflagged": 2
                }):
                    cmd_scan(session, args)
                    self.assertTrue(mock_print.called)

    def test_cmd_cull_with_image_file_starts_at_target(self):
        session = CullingSession()
        item1 = ImageItem(self.img1)
        item2 = ImageItem(self.img2)
        session.items = [item1, item2]

        parser = build_parser()
        args = parser.parse_args(["cull", str(self.img2)])

        with patch.object(culler_cli.Prompt, "ask", return_value="q") as mock_prompt:
            with patch.object(culler_cli.console, "print"):
                with patch.object(session, "scan_directory", return_value=[item1, item2]):
                    with patch.object(session, "get_summary_stats", return_value={
                        "total_images": 2, "total_size_mb": 1.0, "picked": 0, "rejected": 0, "unflagged": 2
                    }):
                        cmd_cull(session, args)
                        self.assertTrue(mock_prompt.called)


class TestGuiOpenPathLogic(unittest.TestCase):
    """
    Tests for ImageCullerApp open_path, multi-tab integration, and target image auto-selection.
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = DatabaseManager(db_path=self.temp_db_path)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.img1 = self.dir_path / "PHOTO_A.JPG"
        self.img2 = self.dir_path / "PHOTO_B.JPG"
        self.img1.write_bytes(b"data1")
        self.img2.write_bytes(b"data2")

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
        self.temp_dir.cleanup()

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
        app.toolbar.get_white_balance.return_value = "camera"
        app.toolbar.get_raw_scale.return_value = 0.25
        app.thumb_list = MagicMock()
        app.viewer = MagicMock()
        app.meta_panel = MagicMock()
        app.tab_bar = MagicMock()
        app.tab_bar.add_tab = MagicMock(side_effect=lambda lbl: len(app.tabs) - 1)

        # Bind methods from ImageCullerApp to mocked app
        app._create_tab_info = lambda directory, target_image=None: ImageCullerApp._create_tab_info(app, directory, target_image=target_image)
        app._get_active_tab = lambda: ImageCullerApp._get_active_tab(app)
        app._get_active_session = lambda: ImageCullerApp._get_active_session(app)
        app._save_active_tab_state = lambda: ImageCullerApp._save_active_tab_state(app)
        app._switch_tab = lambda index: ImageCullerApp._switch_tab(app, index)
        app._close_tab = lambda index: ImageCullerApp._close_tab(app, index)
        app._add_tab = lambda directory, target_image=None: ImageCullerApp._add_tab(app, directory, target_image=target_image)
        app._persist_tabs_state = lambda: ImageCullerApp._persist_tabs_state(app)
        app._restore_tabs_state = lambda: ImageCullerApp._restore_tabs_state(app)
        app._apply_tab_state = lambda tab: ImageCullerApp._apply_tab_state(app, tab)
        app._apply_tab_filter_values = lambda tab: ImageCullerApp._apply_tab_filter_values(app, tab)
        app._preload_placeholder_items = lambda tab, wb: ImageCullerApp._preload_placeholder_items(app, tab, wb)
        app._on_filter_changed = lambda trigger_source="filter": ImageCullerApp._on_filter_changed(app, trigger_source=trigger_source)
        app._select_image = MagicMock()
        app._update_status = MagicMock()
        app.open_path = lambda p: ImageCullerApp.open_path(app, p)
        app._load_tab_directory = MagicMock()

        return app

    def test_open_path_directory_creates_tab(self):
        from gui import ImageCullerApp
        app = self._make_app()

        app.open_path(self.dir_path)

        self.assertEqual(len(app.tabs), 1)
        self.assertEqual(app.tabs[0]["directory"], str(self.dir_path.resolve()))
        self.assertIsNone(app.tabs[0]["pending_target_image"])
        app._load_tab_directory.assert_called_once()

    def test_open_path_image_file_creates_tab_with_pending_target(self):
        from gui import ImageCullerApp
        app = self._make_app()

        app.open_path(self.img2)

        self.assertEqual(len(app.tabs), 1)
        self.assertEqual(app.tabs[0]["directory"], str(self.dir_path.resolve()))
        self.assertEqual(app.tabs[0]["pending_target_image"], self.img2.resolve())

    def test_open_path_already_open_directory_switches_tab(self):
        from gui import ImageCullerApp
        app = self._make_app()

        # Add two tabs
        app._add_tab(str(self.dir_path))
        other_dir = tempfile.TemporaryDirectory()
        app._add_tab(other_dir.name)

        self.assertEqual(app.active_tab_index, 1)

        # Open first folder again
        app.open_path(self.dir_path)

        # Should have switched back to index 0 without creating a 3rd tab
        self.assertEqual(len(app.tabs), 2)
        self.assertEqual(app.active_tab_index, 0)
        other_dir.cleanup()

    def test_open_path_already_open_loaded_tab_selects_image(self):
        from gui import ImageCullerApp
        app = self._make_app()

        app._add_tab(str(self.dir_path))
        tab = app.tabs[0]
        tab["is_loaded"] = True
        
        item1 = ImageItem(self.img1)
        item2 = ImageItem(self.img2)
        tab["session"].items = [item1, item2]
        app.current_items = [item1, item2]

        app.open_path(self.img2)

        app._select_image.assert_called_with(1, target_path=self.img2.resolve(), from_click=False)

    def test_filter_changed_consumes_pending_target_image(self):
        from gui import ImageCullerApp
        app = self._make_app()

        app._add_tab(str(self.dir_path))
        tab = app.tabs[0]
        tab["pending_target_image"] = self.img2.resolve()

        item1 = ImageItem(self.img1)
        item2 = ImageItem(self.img2)
        tab["session"].items = [item1, item2]

        # Trigger filter changed
        app._on_filter_changed()

        # Pending target should have been consumed
        self.assertIsNone(tab["pending_target_image"])
        # Selected image should have been called on index 1
        app._select_image.assert_called_with(1, target_path=self.img2.resolve(), from_click=False)


if __name__ == "__main__":
    unittest.main()
