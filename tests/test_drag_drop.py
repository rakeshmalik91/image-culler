import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gui as gui_module
from culler.image_loader import ImageLoader


class TestParseDropData(unittest.TestCase):
    """Tests for ImageCullerApp._parse_drop_data (tkdnd <<Drop>> data parsing)."""

    def _make_app(self, splitlist_return):
        app = MagicMock()
        app.tk = MagicMock()
        app.tk.splitlist = lambda data: tuple(splitlist_return)
        return app

    def test_empty_data_returns_empty(self):
        app = self._make_app([])
        self.assertEqual(gui_module.ImageCullerApp._parse_drop_data(app, ""), [])

    def test_single_existing_path(self):
        with tempfile.TemporaryDirectory() as d:
            app = self._make_app([str(d)])
            self.assertEqual(gui_module.ImageCullerApp._parse_drop_data(app, str(d)),
                             [Path(d).resolve()])

    def test_filters_nonexistent_paths(self):
        with tempfile.TemporaryDirectory() as d:
            app = self._make_app([str(d), "C:/this/does/not/exist/hopefully"])
            result = gui_module.ImageCullerApp._parse_drop_data(app, "x")
            self.assertEqual(result, [Path(d).resolve()])
            self.assertEqual(len(result), 1)

    def test_deduplicates_same_path(self):
        with tempfile.TemporaryDirectory() as d:
            sub_a = Path(d) / "a"
            sub_a.mkdir()
            app = self._make_app([str(sub_a), str(sub_a)])
            result = gui_module.ImageCullerApp._parse_drop_data(app, "x")
            self.assertEqual(result, [sub_a.resolve()])

    def test_deduplicates_resolved_same_path(self):
        with tempfile.TemporaryDirectory() as d:
            # '.' and the resolved form are the same after resolve()
            app = self._make_app([d, str(Path(d) / ".")])
            result = gui_module.ImageCullerApp._parse_drop_data(app, "x")
            self.assertEqual(len(result), 1)

    def test_multiple_unique_paths(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a"; a.mkdir()
            b = Path(d) / "b"; b.mkdir()
            app = self._make_app([str(a), str(b)])
            result = gui_module.ImageCullerApp._parse_drop_data(app, "x")
            self.assertEqual(result, [a.resolve(), b.resolve()])

    def test_path_with_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            sp = Path(d) / "my folder with spaces"
            sp.mkdir()
            app = self._make_app([str(sp)])
            result = gui_module.ImageCullerApp._parse_drop_data(app, "x")
            self.assertEqual(result, [sp.resolve()])

    def test_falls_back_when_splitlist_fails(self):
        app = MagicMock()
        app.tk = MagicMock()
        app.tk.splitlist = MagicMock(side_effect=ValueError("boom"))
        with tempfile.TemporaryDirectory() as d:
            result = gui_module.ImageCullerApp._parse_drop_data(app, str(d))
            self.assertEqual(result, [Path(d).resolve()])

    def test_empty_strings_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            app = self._make_app(["", "   ", str(d)])
            result = gui_module.ImageCullerApp._parse_drop_data(app, "x")
            self.assertEqual(result, [Path(d).resolve()])


class TestHandleDroppedPath(unittest.TestCase):
    """Tests for ImageCullerApp._handle_dropped_path (folder vs image routing)."""

    def _make_app(self):
        app = MagicMock()
        app.open_path = MagicMock()
        return app

    def test_folder_routes_to_open_path(self):
        app = self._make_app()
        with tempfile.TemporaryDirectory() as d:
            result = gui_module.ImageCullerApp._handle_dropped_path(app, Path(d))
            self.assertTrue(result)
            app.open_path.assert_called_once_with(Path(d))

    def test_supported_image_routes_to_open_path(self):
        app = self._make_app()
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "photo.jpg"
            img.write_bytes(b"")
            result = gui_module.ImageCullerApp._handle_dropped_path(app, img)
            self.assertTrue(result)
            app.open_path.assert_called_once_with(img)

    def test_unsupported_file_ignored(self):
        app = self._make_app()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "notes.zip"
            f.write_bytes(b"")
            result = gui_module.ImageCullerApp._handle_dropped_path(app, f)
            self.assertFalse(result)
            app.open_path.assert_not_called()

    def test_nonexistent_path_ignored(self):
        app = self._make_app()
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "ghost.jpg"  # does not exist
            result = gui_module.ImageCullerApp._handle_dropped_path(app, img)
            self.assertFalse(result)
            app.open_path.assert_not_called()

    def test_exception_in_open_path_is_caught(self):
        app = self._make_app()
        app.open_path.side_effect = RuntimeError("boom")
        with tempfile.TemporaryDirectory() as d:
            # Should not raise; returns False because path.exists()/is_dir() fine
            # but open_path raised, handled by try/except -> returns False
            result = gui_module.ImageCullerApp._handle_dropped_path(app, Path(d))
            self.assertFalse(result)


class TestOnDragDrop(unittest.TestCase):
    """Tests for ImageCullerApp._on_drag_drop end-to-end dispatch."""

    def _make_app(self, paths):
        app = MagicMock()
        app.tk = MagicMock()
        app.tk.splitlist = lambda data: tuple(str(p) for p in paths)
        app.open_path = MagicMock()
        # Bind the real methods so _on_drag_drop's internal calls route through
        # the actual implementation (the app itself is a mock).
        app._parse_drop_data = lambda data: gui_module.ImageCullerApp._parse_drop_data(app, data)
        app._handle_dropped_path = lambda p: gui_module.ImageCullerApp._handle_dropped_path(app, p)
        return app

    def test_dispatches_folder_and_image_ignores_unsupported(self):
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "pic.jpg"; img.write_bytes(b"")
            other = Path(d) / "data.zip"; other.write_bytes(b"")
            app = self._make_app([Path(d), img, other])
            event = MagicMock()
            event.data = "dummy"
            gui_module.ImageCullerApp._on_drag_drop(app, event)
            called = [c.args[0] for c in app.open_path.call_args_list]
            self.assertIn(Path(d), called)
            self.assertIn(img, called)
            self.assertNotIn(other, called)
            app._update_status.assert_called()

    def test_empty_data_does_nothing(self):
        app = self._make_app([])
        app.tk.splitlist = lambda data: ()
        event = MagicMock()
        event.data = ""
        gui_module.ImageCullerApp._on_drag_drop(app, event)
        app.open_path.assert_not_called()
        app._update_status.assert_not_called()  # nothing to report on empty drop


class TestSetupDragDrop(unittest.TestCase):
    """Tests for ImageCullerApp._setup_drag_drop wiring."""

    def _make_app(self):
        app = MagicMock()
        app.tab_bar = MagicMock()
        app.toolbar = MagicMock()
        app.main_container = MagicMock()
        app.status_bar = MagicMock()
        app._on_drag_drop = MagicMock()
        return app

    def test_disabled_when_no_dnd(self):
        app = self._make_app()
        with patch.object(gui_module, "_HAS_DND", False):
            gui_module.ImageCullerApp._setup_drag_drop(app)
        for target in (app.tab_bar, app.toolbar, app.main_container, app.status_bar):
            target.drop_target_register.assert_not_called()
            target.dnd_bind.assert_not_called()

    def test_require_failure_disables_dnd(self):
        app = self._make_app()
        with patch.object(gui_module, "_HAS_DND", True):
            with patch.object(gui_module, "TkinterDnD") as mock_tkdnd:
                mock_tkdnd.require.side_effect = RuntimeError("no tkdnd")
                gui_module.ImageCullerApp._setup_drag_drop(app)
        for target in (app.tab_bar, app.toolbar, app.main_container, app.status_bar):
            target.drop_target_register.assert_not_called()

    def test_registers_containers_as_drop_targets(self):
        app = self._make_app()
        with patch.object(gui_module, "_HAS_DND", True):
            with patch.object(gui_module, "TkinterDnD") as mock_tkdnd:
                gui_module.ImageCullerApp._setup_drag_drop(app)
        for target in (app.tab_bar, app.toolbar, app.main_container, app.status_bar):
            target.drop_target_register.assert_called_once_with(gui_module.DND_FILES)
            target.dnd_bind.assert_called_once_with("<<Drop>>", app._on_drag_drop)


if __name__ == "__main__":
    unittest.main()
