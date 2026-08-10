import sys
import unittest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import customtkinter as ctk
from PIL import Image

from culler.gui.thumbnail_list import ThumbnailList
from culler.culler_engine import ImageItem, FlagState
from culler.image_loader import ImageLoader


class TestThumbnailList(unittest.TestCase):
    """
    Automated Unit Test Suite for ThumbnailList placeholder generation, 
    non-blocking batch loading, progress bar, and soft item refresh.
    """

    def setUp(self):
        try:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
            self.root.withdraw()
        except Exception as e:
            if "TclError" in type(e).__name__ or "tk" in str(e).lower() or "sizegrip" in str(e).lower():
                self.skipTest(f"Skipping GUI test due to Tcl/Tk environment restriction: {e}")
            else:
                raise e

        self.loader = ImageLoader()
        try:
            self.list_widget = ThumbnailList(
                self.root,
                on_select_image=MagicMock(),
                image_loader=self.loader
            )
            self.list_widget.pack(fill="both", expand=True)
            self.list_widget.update()
        except Exception as e:
            if "TclError" in type(e).__name__ or "tk" in str(e).lower() or "sizegrip" in str(e).lower():
                self.skipTest(f"Skipping GUI widget test due to Tcl/Tk environment restriction: {e}")
            else:
                raise e

    def tearDown(self):
        try:
            self.list_widget.shutdown()
        except Exception:
            pass
        try:
            self.list_widget.destroy()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _make_item(self, name="TEST.JPG", is_stacked=False, flag=FlagState.UNFLAGGED, rating=0):
        p = Path(f"D:/Photos/{name}")
        item = ImageItem(p)
        item.filename = p.name
        item.flag = flag
        item.rating = rating
        if is_stacked:
            p2 = Path(f"D:/Photos/{name.replace('.JPG', '_ARW.ARW')}")
            item.stacked_paths = [p, p2]
            item.is_stacked = True
        return item

    def test_create_placeholder_image(self):
        """
        Verify _create_placeholder_image returns a correctly sized RGB image.
        """
        img = self.list_widget._create_placeholder_image((70, 70))
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (70, 70))
        self.assertEqual(img.mode, "RGB")

    def test_update_items_empty_list(self):
        """
        Verify update_items with empty list clears widgets and shows no progress.
        """
        self.list_widget.update_items([], selected_idx=0)
        self.list_widget.update()
        self.assertEqual(len(self.list_widget._row_frame_map), 0)
        self.assertEqual(self.list_widget.progress_bar.get(), 0.0)

    def test_update_items_starts_batch_load(self):
        """
        Verify update_items with items stores pending state and starts batch processing.
        """
        items = [self._make_item(f"IMG_{i:03d}.JPG") for i in range(5)]
        self.list_widget.update_items(items, selected_idx=0)
        self.assertEqual(len(self.list_widget._pending_items), 5)
        self.assertEqual(self.list_widget._pending_selected_idx, 0)

    def test_progress_bar_initialized_on_update(self):
        """
        Verify progress bar resets to 0.0 on update_items call.
        """
        items = [self._make_item(f"IMG_{i:03d}.JPG") for i in range(3)]
        self.list_widget.update_items(items, selected_idx=0)
        self.assertEqual(self.list_widget.progress_bar.get(), 0.0)

    def test_update_btn_image_tracks_progress(self):
        """
        Verify _update_btn_image increments loaded count and updates progress UI.
        """
        self.list_widget._total_thumbs = 2
        self.list_widget._loaded_thumbs = 0

        pil_thumb = Image.new("RGB", (80, 80), color="red")
        self.list_widget._current_load_id = 1
        self.list_widget._update_btn_image("D:/Photos/TEST.JPG", pil_thumb, load_id=1)

        self.assertEqual(self.list_widget._loaded_thumbs, 1)
        self.assertEqual(self.list_widget.progress_bar.get(), 0.5)

    def test_progress_bar_hides_after_completion(self):
        """
        Verify progress bar hides after all thumbnails loaded and batch complete.
        """
        self.list_widget._total_thumbs = 1
        self.list_widget._loaded_thumbs = 1
        self.list_widget._pending_items = []
        self.list_widget._batch_index = 0

        self.list_widget._update_progress_ui()
        self.assertEqual(self.list_widget.progress_bar.get(), 1.0)
        self.assertEqual(self.list_widget.lbl_progress_text.cget("text"), "Done")

    def test_batch_cancel_on_new_update(self):
        """
        Verify that calling update_items with different paths cancels any pending batch after callbacks.
        """
        items1 = [self._make_item(f"IMG_{i:03d}.JPG") for i in range(3)]
        self.list_widget.update_items(items1, selected_idx=0)
        self.list_widget._batch_after_id = "after_id_123"
        items2 = [self._make_item(f"OTHER_{i:03d}.JPG") for i in range(3)]
        self.list_widget.update_items(items2, selected_idx=0)
        self.assertIsNone(self.list_widget._batch_after_id)

    def test_soft_update_skips_rebuild_when_paths_match(self):
        """
        Verify update_items does a soft refresh (no widget destroy/recreate) when paths match.
        """
        items = [self._make_item(f"IMG_{i:03d}.JPG") for i in range(5)]
        self.list_widget.update_items(items, selected_idx=0)
        self.assertEqual(len(self.list_widget._row_frame_map), 5)

        row_count_before = len(self.list_widget._row_frame_map)
        self.list_widget.update_items(items, selected_idx=0)
        self.assertEqual(len(self.list_widget._row_frame_map), row_count_before)

    def test_soft_update_submits_thumbnails(self):
        """
        Verify soft update submits thumbnail loads for items not yet cached.
        """
        items = [self._make_item(f"IMG_{i:03d}.JPG") for i in range(3)]
        self.list_widget.update_items(items, selected_idx=0)
        self.list_widget._total_thumbs = 0
        self.list_widget._loaded_thumbs = 0
        self.list_widget._batch_raw_requests.clear()
        self.list_widget._batch_other_requests.clear()
        self.list_widget.update_items(items, selected_idx=1)
        self.assertGreater(self.list_widget._total_thumbs, 0)

    def test_placeholder_ctk_images_created(self):
        """
        Verify placeholder CTkImages are created for all sizes.
        """
        items = [self._make_item(f"IMG_{i:03d}.JPG") for i in range(2)]
        try:
            self.list_widget.update_items(items, selected_idx=0)
            self.assertTrue(hasattr(self.list_widget, "_placeholder_ctk_70"))
            self.assertTrue(hasattr(self.list_widget, "_placeholder_ctk_80"))
            self.assertTrue(hasattr(self.list_widget, "_placeholder_ctk_90"))
        except Exception as e:
            if "TclError" in type(e).__name__ or "tk.tcl" in str(e).lower():
                self.skipTest(f"Skipping CTkImage test due to headless environment Tcl restriction: {e}")
            else:
                raise e


if __name__ == "__main__":
    unittest.main()
