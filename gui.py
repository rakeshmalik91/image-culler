import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog as fd, messagebox as mb, simpledialog
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field

import customtkinter as ctk
from PIL import Image

from culler.culler_engine import CullingSession, ImageItem, FlagState
from culler.db_manager import DatabaseManager
from culler.gui import HeaderToolbar, ThumbnailList, ImageCanvasViewer, MetadataPanel, MetadataCleanupDialog, SettingsDialog, BlurScanDialog, DuplicateScanDialog, ProgressDialog, TabBar
from culler.logger import log_info, log_debug, log_error

# Set modern dark UI theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ImageCullerApp(ctk.CTk):
    """
    Main Application Window for Fast Photo Culler.
    Features: Multi-tab folder management, Fast ARW/RAW+JPG culling, 0ms RAM pre-fetch buffer navigation,
    Scan for Blur, Scan for Duplicates, Tagging (Blur, Duplicate, Dark, Over-exposed, Custom),
    and SQLite metadata folder hierarchy cleanup.
    """

    def __init__(self):
        super().__init__()

        self.title("Fast Photo Culler - Professional RAW+JPG Photo Selection")
        
        self.db = DatabaseManager()

        self.tabs: List[Dict[str, Any]] = []
        self.active_tab_index: int = -1

        # Restore window geometry (size & position) from DB
        w, h, x, y, is_max = self.db.get_window_geometry()
        if x is not None and y is not None:
            self.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.geometry(f"{w}x{h}")

        if is_max:
            self.after(10, lambda: self.state("zoomed"))

        self._load_request_id: int = 0

        self.current_items: List[ImageItem] = []
        self.current_index: int = -1
        self.selected_indices: Set[int] = set()
        self.selection_anchor_idx: int = 0

        self._create_components()
        self._bind_events()

        # Restore open tabs from DB (lazy loads all except active)
        self._restore_tabs_state()

        # Force a full render pass so the active tab color is painted
        # before mainloop() starts. Without this, CustomTkinter may show
        # unrendered grey boxes until the first after() callback fires.
        self.update_idletasks()
        try:
            self.update()
        except Exception:
            pass

    def _get_active_tab(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.active_tab_index < len(self.tabs):
            return self.tabs[self.active_tab_index]
        return None

    def _get_active_session(self) -> Optional[CullingSession]:
        tab = self._get_active_tab()
        return tab["session"] if tab else None

    def _save_active_tab_state(self):
        tab = self._get_active_tab()
        if not tab:
            return
        tab["filter_values"] = self.toolbar.get_filter_values()
        tab["selected_indices"] = set(self.selected_indices)
        tab["selection_anchor_idx"] = self.selection_anchor_idx
        tab["current_items"] = list(self.current_items)
        tab["current_index"] = self.current_index

    def _create_tab_info(self, directory: str) -> Dict[str, Any]:
        folder_name = os.path.basename(directory) or directory
        return {
            "directory": str(Path(directory).resolve()),
            "tab_label": folder_name,
            "session": CullingSession(db_manager=self.db),
            "filter_values": {
                "flag": "All",
                "rating": [],
                "format": "All Formats",
                "tag": []
            },
            "current_items": [],
            "current_index": -1,
            "selected_indices": set(),
            "selection_anchor_idx": 0,
            "is_loaded": False,
            "loading": False,
            "load_total": 0,
            "load_current": 0,
        }

    def _restore_tabs_state(self):
        saved = self.db.get_open_tabs()
        if not saved or not isinstance(saved, dict):
            saved = {"tabs": [], "active_index": 0}

        tabs_data = saved.get("tabs", [])
        active_idx = saved.get("active_index", 0)

        if not tabs_data:
            return

        restored_tabs = []
        for t in tabs_data:
            if not isinstance(t, dict):
                continue
            directory = t.get("directory", "")
            if not directory or not os.path.exists(directory):
                continue
            tab_info = self._create_tab_info(directory)
            tab_info["tab_label"] = t.get("tab_label", tab_info["tab_label"]).replace(" ⟳", "")
            tab_info["filter_values"] = t.get("filter_values", tab_info["filter_values"])
            tab_info["is_loaded"] = False
            restored_tabs.append(tab_info)

        if not restored_tabs:
            return

        self.tabs = restored_tabs
        active_idx = min(active_idx, len(self.tabs) - 1)
        self.active_tab_index = active_idx

        for i, t in enumerate(self.tabs):
            self.tab_bar.add_tab(t["tab_label"])

        self.tab_bar.set_active(active_idx)
        self.tab_bar.update_idletasks()
        try:
            self.tab_bar.update()
        except Exception:
            pass

        # Lazy load: only load active tab on startup, others load on demand
        tab = self.tabs[active_idx]
        self._load_tab_directory(tab, show_progress=True)

        # Re-assert active tab color after loading indicator may have updated label
        def _restore_active_color():
            self.tab_bar.set_active(self.active_tab_index)
            self.tab_bar.update_idletasks()

        self.after(1, _restore_active_color)
        self.after(100, _restore_active_color)

    def _add_tab(self, directory: str):
        tab_info = self._create_tab_info(directory)
        self.tabs.append(tab_info)
        idx = self.tab_bar.add_tab(tab_info["tab_label"])
        self.tab_bar.set_active(len(self.tabs) - 1)
        self.active_tab_index = len(self.tabs) - 1
        self._load_tab_directory(tab_info, show_progress=True)
        self._persist_tabs_state()

    def _close_tab(self, index: int):
        if len(self.tabs) <= 1:
            return

        tab = self.tabs[index]
        session = tab["session"]

        self.tab_bar.remove_tab(index)
        self.tabs.pop(index)

        if self.active_tab_index == index:
            new_idx = min(index, len(self.tabs) - 1)
            self.active_tab_index = new_idx
            self.tab_bar.set_active(new_idx)
            target = self.tabs[new_idx]
            if not target["is_loaded"]:
                self._load_tab_directory(target, show_progress=True)
            else:
                self._apply_tab_state(target)
        elif self.active_tab_index > index:
            self.active_tab_index -= 1

        self._persist_tabs_state()

    def _switch_tab(self, index: int):
        if index == self.active_tab_index:
            return
        if not (0 <= index < len(self.tabs)):
            return

        self._save_active_tab_state()
        self.active_tab_index = index
        self.tab_bar.set_active(index)
        target = self.tabs[index]

        if not target["is_loaded"]:
            self._apply_tab_state(target)
            self._load_tab_directory(target, show_progress=True)
        else:
            self._apply_tab_state(target)

        self._sync_loading_progress()
        self._persist_tabs_state()

    def _apply_tab_state(self, tab: Dict[str, Any]):
        session = tab["session"]
        self.current_items = list(tab.get("current_items", []))
        self.current_index = tab.get("current_index", -1)
        self.selected_indices = set(tab.get("selected_indices", set()))
        self.selection_anchor_idx = tab.get("selection_anchor_idx", 0)

        self.thumb_list.set_image_loader(session.image_loader)
        self.toolbar.apply_filter_values(tab.get("filter_values", {}))
        self.meta_panel.update_output_folders(
            self.db.get_picked_folder(),
            self.db.get_rejected_folder()
        )

        white_balance = self.toolbar.get_white_balance()
        self.thumb_list.update_items(self.current_items, selected_idx=self.current_index, white_balance=white_balance)

        if self.current_items and 0 <= self.current_index < len(self.current_items):
            self._select_image(self.current_index, from_click=False)
        else:
            self.viewer.clear()
            self.meta_panel.clear()

        self._update_status(f"Tab: {tab['tab_label']} | {len(self.current_items)} photos loaded")

    def _load_tab_directory(self, tab: Dict[str, Any], show_progress: bool = True):
        directory = tab["directory"]
        if not directory or not os.path.exists(directory):
            return

        tab["loading"] = True
        tab["load_total"] = 0
        tab["load_current"] = 0
        tab["_placeholders_loaded"] = False
        self._update_tab_loading_indicator(tab)

        white_balance = self.toolbar.get_white_balance()

        def on_progress(current: int, total: int, filename: str = ""):
            tab["load_current"] = current
            tab["load_total"] = total
            if tab is self._get_active_tab():
                if current == 0 and total > 0 and not tab.get("_placeholders_loaded"):
                    tab["_placeholders_loaded"] = True
                    self.after(50, lambda: self._preload_placeholder_items(tab, white_balance))
                self.after(0, self._sync_loading_progress)

        def worker():
            try:
                tab["session"].scan_directory(
                    directory,
                    stack_raw_jpg=True,
                    progress_callback=on_progress
                )
                tab["is_loaded"] = True
                tab["loading"] = False
                self.after(0, lambda: self._on_tab_scan_complete(tab))
            except Exception as e:
                tab["loading"] = False
                self.after(0, lambda err=e: self._on_tab_scan_error(tab, err))

        threading.Thread(target=worker, daemon=True).start()

    def _preload_placeholder_items(self, tab: Dict[str, Any], white_balance: str):
        session = tab["session"]
        if not session or not session.items:
            return

        placeholder_items = []
        for item in session.items:
            pi = ImageItem(item.path)
            pi.filename = item.filename or item.path.name
            pi.flag = item.flag
            pi.rating = item.rating
            pi.is_stacked = item.is_stacked
            pi.stacked_paths = list(item.stacked_paths)
            placeholder_items.append(pi)

        self.thumb_list.set_image_loader(session.image_loader)
        self.thumb_list.update_items(placeholder_items, selected_idx=0, white_balance=white_balance)

    def _on_tab_scan_complete(self, tab: Dict[str, Any]):
        self._update_tab_loading_indicator(tab)

        session = tab["session"]
        self._apply_tab_filter_values(tab)

        if tab is not self._get_active_tab():
            return

        self.thumb_list.progress_bar.set(0.0)
        self.thumb_list.lbl_progress_text.configure(text="")

        self.thumb_list.set_image_loader(session.image_loader)
        self._on_filter_changed()
        stats = tab["session"].get_summary_stats()
        if stats['total_images'] == 0:
            folder_str = str(tab["session"].directory) if tab["session"].directory else "selected directory"
            self._update_status(f"No supported photo files found in {folder_str}.")
        else:
            self._update_status(
                f"Loaded {stats['total_images']} photos ({stats['total_size_mb']} MB) | "
                f"Picked: {stats['picked']}, Rejected: {stats['rejected']}, Unflagged: {stats['unflagged']}"
            )

    def _on_tab_scan_error(self, tab: Dict[str, Any], err: Exception):
        self._update_tab_loading_indicator(tab)
        self._update_status("Error loading directory.")

    def _sync_loading_progress(self):
        tab = self._get_active_tab()
        if not tab or not tab.get("loading"):
            return

        total = tab.get("load_total", 0)
        current = tab.get("load_current", 0)
        if total > 0:
            pct = current / total
            self.thumb_list.progress_bar.set(pct)
            self.thumb_list.lbl_progress_text.configure(text=f"Loading {current}/{total}")
        else:
            self.thumb_list.progress_bar.set(0.0)
            self.thumb_list.lbl_progress_text.configure(text="Loading...")

    def _update_tab_loading_indicator(self, tab: Dict[str, Any]):
        idx = self.tabs.index(tab) if tab in self.tabs else -1
        if idx < 0:
            return
        base_label = tab.get("tab_label", "")
        if not base_label:
            return
        if tab.get("loading") and not base_label.endswith(" ⟳"):
            tab["tab_label"] = base_label + " ⟳"
        elif not tab.get("loading") and base_label.endswith(" ⟳"):
            tab["tab_label"] = base_label[:-2]
        self.tab_bar.set_label(idx, tab["tab_label"])

    def _apply_tab_filter_values(self, tab: Dict[str, Any]):
        session = tab["session"]
        if not session or not session.items:
            tab["current_items"] = []
            tab["current_index"] = -1
            return

        filter_vals = tab.get("filter_values", {})

        rating_selected = filter_vals.get("rating", [])
        rating_filter_set = None
        if rating_selected:
            rating_filter_set = set()
            for r_str in rating_selected:
                if r_str == "Unrated":
                    rating_filter_set.add(0)
                else:
                    try:
                        rating_filter_set.add(int(r_str.replace("★", "").strip()))
                    except Exception:
                        pass

        fmt_val = filter_vals.get("format", "All Formats")
        if ".ARW" in fmt_val.upper() or "ARW" in fmt_val.upper():
            fmt_val = ".ARW"
        elif ".JPG" in fmt_val.upper() or "JPG" in fmt_val.upper():
            fmt_val = ".JPG"
        elif ".PNG" in fmt_val.upper() or "PNG" in fmt_val.upper():
            fmt_val = ".PNG"
        elif ".HEIC" in fmt_val.upper() or "HEIC" in fmt_val.upper():
            fmt_val = ".HEIC"
        else:
            fmt_val = "All"

        tag_selected = filter_vals.get("tag", [])
        tag_filter = tag_selected if tag_selected else None

        tab["current_items"] = session.get_filtered_items(
            flag_filter=filter_vals.get("flag", "All"),
            rating_filter=rating_filter_set,
            format_filter=fmt_val,
            tag_filter=tag_filter
        )
        tab["current_index"] = 0 if tab["current_items"] else -1

    def _persist_tabs_state(self):
        self._save_active_tab_state()
        payload = []
        for t in self.tabs:
            payload.append({
                "directory": t["directory"],
                "tab_label": t["tab_label"],
                "filter_values": t.get("filter_values", {}),
            })
        self.db.save_open_tabs(payload, self.active_tab_index)

    def _on_tab_selected(self, index: int):
        self._switch_tab(index)

    def _on_tab_closed(self, index: int):
        self._close_tab(index)

    def _on_tab_reordered(self, from_idx: int, to_idx: int):
        self._save_active_tab_state()
        self.tab_bar.reorder(from_idx, to_idx)
        tab = self.tabs.pop(from_idx)
        self.tabs.insert(to_idx, tab)
        if self.active_tab_index == from_idx:
            self.active_tab_index = to_idx
        elif from_idx < to_idx and self.active_tab_index > from_idx and self.active_tab_index <= to_idx:
            self.active_tab_index -= 1
        elif from_idx > to_idx and self.active_tab_index >= to_idx and self.active_tab_index < from_idx:
            self.active_tab_index += 1
        self._persist_tabs_state()

    def _on_new_tab(self):
        folder = fd.askdirectory(title="Select Photo Directory to Cull")
        if folder:
            self._add_tab(folder)

    def _create_components(self):
        init_scale = self.db.get_raw_scale()
        init_wb = self.db.get_white_balance()

        # Tab Bar
        self.tab_bar = TabBar(
            self,
            on_tab_selected=self._on_tab_selected,
            on_tab_closed=self._on_tab_closed,
            on_tab_reordered=self._on_tab_reordered,
            on_new_tab=self._on_new_tab
        )
        self.tab_bar.pack(side="top", fill="x", padx=0, pady=0)

        # Top Header Toolbar
        self.toolbar = HeaderToolbar(
            self,
            on_open_explorer=self._on_open_explorer,
            on_refresh=self._on_refresh_directory,
            on_filter_change=self._on_filter_changed,
            on_raw_settings_change=self._on_raw_settings_changed,
            on_load_100_percent=self._on_load_100_percent,
            on_scan_blur=self._on_scan_blur,
            on_scan_duplicates=self._on_scan_duplicates,
            on_open_settings=self._on_open_settings,
            initial_raw_scale=init_scale,
            initial_wb=init_wb
        )
        self.toolbar.pack(side="top", fill="x", padx=5, pady=5)

        # Main Container
        self.main_container = ctk.CTkFrame(self, corner_radius=0)
        self.main_container.pack(side="top", fill="both", expand=True, padx=5, pady=2)

        # Left Thumbnail List
        self.thumb_list = ThumbnailList(
            self.main_container,
            on_select_image=self._select_image,
            on_select_all=self._select_all,
            on_select_none=self._select_none
        )
        self.thumb_list.pack(side="left", fill="y", padx=3, pady=3)

        # Center Canvas Viewer
        self.viewer = ImageCanvasViewer(self.main_container)
        self.viewer.pack(side="left", fill="both", expand=True, padx=3, pady=3)

        # Right Metadata & Action Panel
        init_picked_folder = self.db.get_picked_folder()
        init_rejected_folder = self.db.get_rejected_folder()

        self.meta_panel = MetadataPanel(
            self.main_container,
            on_set_flag=self._set_current_flag,
            on_set_rating=self._set_current_rating,
            on_toggle_tag=self._on_toggle_tag,
            on_unflag_all=self._on_unflag_all,
            on_untag_all=self._on_untag_all,
            on_unrate_all=self._on_unrate_all,
            on_clear_all=self._on_clear_all,
            on_crop=self._on_trigger_crop,
            on_convert_jpg=self._on_convert_jpg,
            on_move_picked=self._on_move_picked,
            on_move_rejected=self._on_move_rejected,
            on_config_output_folders=self._on_config_output_folders,
            initial_picked_folder=init_picked_folder,
            initial_rejected_folder=init_rejected_folder
        )
        self.meta_panel.pack(side="right", fill="y", padx=3, pady=3)
        self.meta_panel.refresh_tag_buttons(self.db.get_custom_tags())

        # Status Bar
        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0)
        self.status_bar.pack(side="bottom", fill="x")

        self.lbl_status = ctk.CTkLabel(
            self.status_bar, text="Ready. Open a directory to begin culling.", anchor="w"
        )
        self.lbl_status.pack(side="left", padx=10, pady=4)

        # Right Side Background Prefetch Indicator Box
        self.prefetch_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        self.prefetch_frame.pack(side="right", padx=10, pady=2)

        self.lbl_prefetch = ctk.CTkLabel(
            self.prefetch_frame,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2b9348"
        )
        self.lbl_prefetch.pack(side="left", padx=(0, 6))

        self.prefetch_bar = ctk.CTkProgressBar(
            self.prefetch_frame,
            width=110,
            height=12,
            progress_color="#2b9348"
        )
        self.prefetch_bar.pack(side="left")
        self.prefetch_bar.set(1.0)

    def _bind_events(self):
        # Navigation & Multi-Selection Bindings
        # Single Step (+/- 1)
        self.bind("<Right>", lambda e: self._navigate(1, is_shift=False))
        self.bind("<Left>", lambda e: self._navigate(-1, is_shift=False))
        self.bind("<Down>", lambda e: self._navigate(1, is_shift=False))
        self.bind("<Up>", lambda e: self._navigate(-1, is_shift=False))

        # 100% Full Resolution Shortcut
        self.bind("a", lambda e: self._on_load_100_percent())
        self.bind("A", lambda e: self._on_load_100_percent())

        # Shift + Navigation (Multi-select range +/- 1)
        self.bind("<Shift-Right>", lambda e: self._navigate(1, is_shift=True))
        self.bind("<Shift-Left>", lambda e: self._navigate(-1, is_shift=True))
        self.bind("<Shift-Down>", lambda e: self._navigate(1, is_shift=True))
        self.bind("<Shift-Up>", lambda e: self._navigate(-1, is_shift=True))

        # Ctrl + Navigation (+/- 10 photos)
        self.bind("<Control-Right>", lambda e: self._navigate(10, is_shift=False))
        self.bind("<Control-Left>", lambda e: self._navigate(-10, is_shift=False))
        self.bind("<Control-Down>", lambda e: self._navigate(10, is_shift=False))
        self.bind("<Control-Up>", lambda e: self._navigate(-10, is_shift=False))
        self.bind("<Prior>", lambda e: self._navigate(-10, is_shift=False))
        self.bind("<Next>", lambda e: self._navigate(10, is_shift=False))

        # Shift + Ctrl + Navigation (Multi-select range +/- 10 photos)
        self.bind("<Shift-Control-Right>", lambda e: self._navigate(10, is_shift=True))
        self.bind("<Shift-Control-Left>", lambda e: self._navigate(-10, is_shift=True))
        self.bind("<Shift-Control-Down>", lambda e: self._navigate(10, is_shift=True))
        self.bind("<Shift-Control-Up>", lambda e: self._navigate(-10, is_shift=True))

        # Home & End Jump
        self.bind("<Home>", lambda e: self._navigate_first(is_shift=False))
        self.bind("<End>", lambda e: self._navigate_last(is_shift=False))
        self.bind("<Shift-Home>", lambda e: self._navigate_first(is_shift=True))
        self.bind("<Shift-End>", lambda e: self._navigate_last(is_shift=True))

        # Trash / Delete Shortcuts
        self.bind("<Delete>", lambda e: self._on_delete_selected_to_trash())
        self.bind("d", lambda e: self._on_d_key_pressed())
        self.bind("D", lambda e: self._on_d_key_pressed())

        # Culling Flags & Ratings
        self.bind("p", lambda e: self._set_current_flag(FlagState.PICK))
        self.bind("P", lambda e: self._set_current_flag(FlagState.PICK))
        self.bind("x", lambda e: self._set_current_flag(FlagState.REJECT))
        self.bind("X", lambda e: self._set_current_flag(FlagState.REJECT))
        self.bind("u", lambda e: self._set_current_flag(FlagState.UNFLAGGED))
        self.bind("U", lambda e: self._set_current_flag(FlagState.UNFLAGGED))

        self.bind("c", lambda e: self._on_trigger_crop())
        self.bind("C", lambda e: self._on_trigger_crop())
        self.bind("<Control-c>", lambda e: self._on_copy_image_to_clipboard())
        self.bind("<Control-C>", lambda e: self._on_copy_image_to_clipboard())
        self.bind("<Control-s>", lambda e: self._on_save_as())
        self.bind("<Control-S>", lambda e: self._on_save_as())
        self.bind("<Return>", lambda e: self._on_return_pressed())
        self.bind("<KP_Enter>", lambda e: self._on_return_pressed())
        self.bind("<Escape>", lambda e: self._on_escape_pressed())

        for star in range(6):
            self.bind(str(star), lambda e, s=star: self._set_current_rating(s))

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        try:
            is_max = (self.state() == "zoomed")
            w = self.winfo_width()
            h = self.winfo_height()
            x = self.winfo_x()
            y = self.winfo_y()
            self.db.save_window_geometry(w, h, x, y, is_max)
        except Exception:
            pass

        try:
            if hasattr(self, "thumb_list"):
                self.thumb_list.shutdown()
        except Exception:
            pass

        try:
            self._persist_tabs_state()
            for tab in self.tabs:
                tab["session"].image_loader.clear_cache()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

        os._exit(0)

    def _update_status(self, text: str):
        self.lbl_status.configure(text=text)

    def _on_refresh_directory(self):
        tab = self._get_active_tab()
        if tab and tab.get("session") and tab["session"].directory and tab["session"].directory.exists():
            self._load_directory(str(tab["session"].directory))
        else:
            mb.showinfo("Refresh Directory", "No active photo folder opened.")

    def _load_directory(self, folder_path: str):
        tab = self._get_active_tab()
        if not tab:
            mb.showinfo("No Tab", "Open a directory in a tab first.")
            return

        self.db.set_setting("last_directory", str(folder_path))
        tab["directory"] = str(Path(folder_path).resolve())
        tab["tab_label"] = os.path.basename(folder_path) or folder_path
        tab["is_loaded"] = False
        tab["current_items"] = []
        tab["current_index"] = -1
        tab["selected_indices"] = set()
        tab["filter_values"] = {
            "flag": "All",
            "rating": [],
            "format": "All Formats",
            "tag": []
        }
        tab["loading"] = True
        tab["load_total"] = 0
        tab["load_current"] = 0

        self.tab_bar.set_label(self.active_tab_index, tab["tab_label"] + " ⟳")
        self._update_status(f"Scanning directory: {folder_path}...")

        def on_progress(current: int, total: int, filename: str = ""):
            tab["load_current"] = current
            tab["load_total"] = total
            if tab is self._get_active_tab():
                self.after(0, self._sync_loading_progress)

        def worker():
            try:
                tab["session"].scan_directory(
                    folder_path,
                    stack_raw_jpg=True,
                    progress_callback=on_progress
                )
                tab["is_loaded"] = True
                tab["loading"] = False
                self.after(0, lambda: self._on_scan_complete(tab))
            except Exception as e:
                tab["loading"] = False
                self.after(0, lambda err=e: self._on_scan_error(tab, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_complete(self, tab: Dict[str, Any]):
        self._update_tab_loading_indicator(tab)

        if tab is not self._get_active_tab():
            return

        self.thumb_list.progress_bar.set(0.0)
        self.thumb_list.lbl_progress_text.configure(text="")

        self._on_filter_changed()
        stats = tab["session"].get_summary_stats()
        if stats['total_images'] == 0:
            folder_str = str(tab["session"].directory) if tab["session"].directory else "selected directory"
            mb.showwarning(
                "No Photos Found",
                f"No supported photo files (.ARW, .JPG, .PNG, .HEIC, .CR2, .NEF, etc.) were found in:\n\n{folder_str}"
            )
            self._update_status(f"No supported photo files found in {folder_str}.")
        else:
            self._update_status(
                f"Loaded {stats['total_images']} photos ({stats['total_size_mb']} MB) | "
                f"Picked: {stats['picked']}, Rejected: {stats['rejected']}, Unflagged: {stats['unflagged']}"
            )

    def _on_scan_error(self, tab: Dict[str, Any], err: Exception):
        self._update_tab_loading_indicator(tab)
        self._update_status("Error loading directory.")

    def _on_filter_changed(self, trigger_source: str = "filter"):
        tab = self._get_active_tab()
        session = self._get_active_session()
        if not tab or not session:
            return

        filter_vals = self.toolbar.get_filter_values()

        rating_selected = filter_vals["rating"]
        rating_filter_set = None
        if rating_selected:
            rating_filter_set = set()
            for r_str in rating_selected:
                if r_str == "Unrated":
                    rating_filter_set.add(0)
                else:
                    try:
                        rating_filter_set.add(int(r_str.replace("★", "").strip()))
                    except Exception:
                        pass

        fmt_val = filter_vals["format"]
        if ".ARW" in fmt_val.upper() or "ARW" in fmt_val.upper(): fmt_val = ".ARW"
        elif ".JPG" in fmt_val.upper() or "JPG" in fmt_val.upper(): fmt_val = ".JPG"
        elif ".PNG" in fmt_val.upper() or "PNG" in fmt_val.upper(): fmt_val = ".PNG"
        elif ".HEIC" in fmt_val.upper() or "HEIC" in fmt_val.upper(): fmt_val = ".HEIC"
        else: fmt_val = "All"

        tag_selected = filter_vals.get("tag", [])
        tag_filter = tag_selected if tag_selected else None

        prev_selected_path = None
        if self.current_items and 0 <= self.current_index < len(self.current_items):
            prev_selected_path = self.current_items[self.current_index].path

        self.current_items = session.get_filtered_items(
            flag_filter=filter_vals["flag"],
            rating_filter=rating_filter_set,
            format_filter=fmt_val,
            tag_filter=tag_filter
        )
        tab["current_items"] = self.current_items

        target_idx = 0
        if prev_selected_path and self.current_items:
            for idx, item in enumerate(self.current_items):
                if item.path == prev_selected_path or prev_selected_path in item.stacked_paths:
                    target_idx = idx
                    break

        log_info(f"_on_filter_changed: filter='{filter_vals['flag']}', rating={rating_filter_set}, format='{fmt_val}', tag='{tag_filter}' -> {len(self.current_items)} items matched")

        white_balance = self.toolbar.get_white_balance()

        self.thumb_list.update_items(
            self.current_items,
            selected_idx=target_idx,
            white_balance=white_balance
        )

        if self.current_items:
            self._select_image(target_idx, from_click=False)
        else:
            self.selected_indices = set()
            self.viewer.clear()
            self.meta_panel.clear()
            self._update_status("No photos match current filter criteria.")

    def _select_all(self):
        if not self.current_items:
            return
        self.selected_indices = set(range(len(self.current_items)))
        cur_idx = self.current_index if 0 <= self.current_index < len(self.current_items) else 0
        cur_item = self.current_items[cur_idx]
        self.thumb_list.set_selected_indices(self.selected_indices, cur_idx, active_path=cur_item.path)
        self._update_status(f"Selected all {len(self.current_items)} photos.")

    def _select_none(self):
        if not self.current_items:
            return
        cur_idx = self.current_index if 0 <= self.current_index < len(self.current_items) else 0
        self.selected_indices = {cur_idx}
        self.selection_anchor_idx = cur_idx
        cur_item = self.current_items[cur_idx]
        self.thumb_list.set_selected_indices(self.selected_indices, cur_idx, active_path=cur_item.path)
        self._update_status(f"Selection cleared to active photo ({cur_idx + 1}/{len(self.current_items)}).")

    def _select_image(self, index: int, target_path: Optional[Path] = None, is_continuous: bool = False, is_ctrl: bool = False, is_shift: bool = False, from_click: bool = False):
        tab = self._get_active_tab()
        session = self._get_active_session()
        if not tab or not session or not self.current_items:
            return

        if not (0 <= index < len(self.current_items)):
            return

        self.current_index = index
        tab["current_index"] = index
        item = self.current_items[index]
        load_path = target_path or item.path

        if is_ctrl:
            if index in self.selected_indices and len(self.selected_indices) > 1:
                self.selected_indices.remove(index)
            else:
                self.selected_indices.add(index)
            self.selection_anchor_idx = index
            tab["selected_indices"] = set(self.selected_indices)
        elif is_shift:
            anchor = getattr(self, "selection_anchor_idx", index)
            start_i, end_i = min(anchor, index), max(anchor, index)
            self.selected_indices = set(range(start_i, end_i + 1))
            tab["selected_indices"] = set(self.selected_indices)
        else:
            self.selected_indices = {index}
            self.selection_anchor_idx = index
            tab["selected_indices"] = {index}

        tab["selection_anchor_idx"] = self.selection_anchor_idx
        self._load_request_id += 1
        req_id = self._load_request_id

        display_name = load_path.name if load_path else item.filename
        sel_info = f" [{len(self.selected_indices)} selected]" if len(self.selected_indices) > 1 else ""
        self._update_status(f"Displaying: {display_name} ({index + 1}/{len(self.current_items)}) [{item.format_name}]{sel_info}")

        cached_thumb = session.image_loader.get_cached_thumbnail(load_path)
        if cached_thumb:
            self.viewer.set_image(cached_thumb, preserve_zoom=True)

        def do_sidebar_update():
            self._sidebar_scheduled = False
            cur_idx = self.current_index
            if 0 <= cur_idx < len(self.current_items):
                cur_item = self.current_items[cur_idx]
                self.thumb_list.set_selected_indices(
                    self.selected_indices,
                    cur_idx,
                    active_path=load_path,
                    auto_scroll=(not from_click)
                )
                self.meta_panel.update_metadata(cur_item)

        if is_continuous:
            if not getattr(self, "_sidebar_scheduled", False):
                self._sidebar_scheduled = True
                self.after(30, do_sidebar_update)
        else:
            self._sidebar_scheduled = False
            do_sidebar_update()

        raw_scale = self.toolbar.get_raw_scale()
        white_balance = self.toolbar.get_white_balance()

        cached_img = session.image_loader.get_cached_full_image(load_path, raw_scale, white_balance)
        if cached_img:
            self._on_image_loaded(item, cached_img, full_res=False, active_path=load_path, req_id=req_id)
            self._prefetch_surrounding_images(index, is_continuous=is_continuous)
            return

        def start_background_load():
            if req_id != self._load_request_id:
                return

            def load_worker():
                if req_id != self._load_request_id:
                    return

                if not cached_thumb:
                    fast_thumb = session.image_loader.get_thumbnail(
                        load_path,
                        max_size=(400, 400),
                        raw_scale=0.10,
                        white_balance=white_balance
                    )
                    if req_id != self._load_request_id:
                        return
                    if fast_thumb:
                        self.after(0, lambda: self.viewer.set_image(fast_thumb, preserve_zoom=True))

                if req_id != self._load_request_id:
                    return

                pil_img = session.image_loader.load_full_image(
                    load_path,
                    raw_scale=raw_scale,
                    white_balance=white_balance
                )
                if req_id == self._load_request_id:
                    self.after(0, lambda: self._on_image_loaded(item, pil_img, full_res=False, active_path=load_path, req_id=req_id))
                    self._prefetch_surrounding_images(index, is_continuous=is_continuous)

            threading.Thread(target=load_worker, daemon=True).start()

        if hasattr(self, "_nav_timer") and self._nav_timer is not None:
            try:
                self.after_cancel(self._nav_timer)
            except Exception:
                pass
            self._nav_timer = None

        if is_continuous:
            self._nav_timer = self.after(150, start_background_load)
        else:
            start_background_load()

    def _prefetch_surrounding_images(self, center_idx: int, is_continuous: bool = False):
        session = self._get_active_session()
        if not session or not self.current_items:
            return

        current_req = self._load_request_id
        indices_to_prefetch = [
            center_idx + 1,
            center_idx + 2,
            center_idx - 1,
        ]
        raw_scale = self.toolbar.get_raw_scale()
        white_balance = self.toolbar.get_white_balance()

        if hasattr(self, "_prefetch_timer") and self._prefetch_timer is not None:
            try:
                self.after_cancel(self._prefetch_timer)
            except Exception:
                pass
            self._prefetch_timer = None

        def start_prefetch_thread():
            if current_req != self._load_request_id:
                return

            self.after(0, lambda: self._update_prefetch_progress(0.1, is_done=False))

            def prefetch_worker():
                total = len(indices_to_prefetch)
                completed = 0

                for idx in indices_to_prefetch:
                    if current_req != self._load_request_id:
                        break
                    if 0 <= idx < len(self.current_items):
                        item = self.current_items[idx]
                        for p in item.stacked_paths:
                            if current_req != self._load_request_id:
                                break
                            try:
                                session.image_loader.load_full_image(
                                    p,
                                    raw_scale=raw_scale,
                                    white_balance=white_balance
                                )
                            except Exception:
                                pass
                    completed += 1
                    frac = completed / float(total)
                    if current_req == self._load_request_id:
                        self.after(0, lambda f=frac: self._update_prefetch_progress(f, is_done=False))

                if current_req == self._load_request_id:
                    self.after(0, lambda: self._update_prefetch_progress(1.0, is_done=True))

            threading.Thread(target=prefetch_worker, daemon=True).start()

        if is_continuous:
            self._prefetch_timer = self.after(80, start_prefetch_thread)
        else:
            start_prefetch_thread()

    def _update_prefetch_progress(self, fraction: float, is_done: bool):
        self.prefetch_bar.set(fraction)
        if is_done:
            self.prefetch_bar.configure(progress_color="#2b9348")
        else:
            self.prefetch_bar.configure(progress_color="#ffb703")

    def _on_image_loaded(self, item: ImageItem, pil_img: Optional[Image.Image], full_res: bool = False, active_path: Optional[Path] = None, req_id: Optional[int] = None):
        if req_id is not None and req_id != self._load_request_id:
            return
        self.viewer.set_image(pil_img)
        if getattr(item, 'detection_box', None):
            self.viewer.set_detection_box(item.detection_box)
        else:
            self.viewer.clear_detection_box()
        self.meta_panel.update_metadata(item)
        res_str = "100% Full Resolution" if full_res else "Preview"
        display_name = active_path.name if active_path else item.filename
        self._update_status(f"Displaying: {display_name} [{item.format_name} - {res_str}]")

    def _set_current_flag(self, flag: FlagState):
        session = self._get_active_session()
        if self.current_index < 0 or not self.current_items or not session:
            return
        target_indices = self.selected_indices if self.selected_indices else {self.current_index}
        for idx in target_indices:
            if 0 <= idx < len(self.current_items):
                item = self.current_items[idx]
                item.flag = flag
                session.save_item_record(item)
                self.thumb_list.update_single_item_status(idx, item)

        cur_item = self.current_items[self.current_index]
        self.meta_panel.update_metadata(cur_item)
        count_str = f" across {len(target_indices)} photos" if len(target_indices) > 1 else ""
        self._update_status(f"Flagged {cur_item.filename} as {flag.value}{count_str}")

    def _set_current_rating(self, rating: int):
        session = self._get_active_session()
        if self.current_index < 0 or not self.current_items or not session:
            return
        target_indices = self.selected_indices if self.selected_indices else {self.current_index}
        for idx in target_indices:
            if 0 <= idx < len(self.current_items):
                item = self.current_items[idx]
                item.rating = rating
                session.save_item_record(item)
                self.thumb_list.update_single_item_status(idx, item)

        cur_item = self.current_items[self.current_index]
        self.meta_panel.update_metadata(cur_item)
        count_str = f" across {len(target_indices)} photos" if len(target_indices) > 1 else ""
        self._update_status(f"Set rating for {cur_item.filename} to {rating} stars{count_str}")

    def _on_toggle_tag(self, tag_name: str):
        session = self._get_active_session()
        if self.current_index < 0 or not self.current_items or not session:
            return
        target_indices = self.selected_indices if self.selected_indices else {self.current_index}
        for idx in target_indices:
            if 0 <= idx < len(self.current_items):
                item = self.current_items[idx]
                if item.has_tag(tag_name):
                    item.remove_tag(tag_name)
                else:
                    item.add_tag(tag_name)
                session.save_item_record(item)

        cur_item = self.current_items[self.current_index]
        self.meta_panel.update_metadata(cur_item)
        self._update_status(f"Toggled tag '{tag_name}' for {len(target_indices)} photo(s)")

    def _navigate(self, delta: int, is_shift: bool = False):
        if not self.current_items:
            return
        is_cont = (abs(delta) == 1 and not is_shift)
        new_idx = max(0, min(len(self.current_items) - 1, self.current_index + delta))
        if 0 <= new_idx < len(self.current_items):
            self._select_image(new_idx, is_continuous=is_cont, is_shift=is_shift)

    def _navigate_first(self, is_shift: bool = False):
        if not self.current_items:
            return
        self._select_image(0, is_continuous=False, is_shift=is_shift)

    def _navigate_last(self, is_shift: bool = False):
        if not self.current_items:
            return
        self._select_image(len(self.current_items) - 1, is_continuous=False, is_shift=is_shift)

    def _on_d_key_pressed(self):
        """
        Shortcut 'd' / 'D' moves selected photos to Trash!
        """
        self._on_delete_selected_to_trash()

    def _on_delete_selected_to_trash(self):
        if not self.current_items:
            return

        target_indices = sorted(self.selected_indices) if self.selected_indices else [self.current_index]
        target_items = [self.current_items[i] for i in target_indices if 0 <= i < len(self.current_items)]

        if not target_items:
            return

        fmt_filter = self.toolbar.get_format_filter() if hasattr(self, "toolbar") else "All"
        stacked_count = sum(1 for it in target_items if it.is_stacked)

        if fmt_filter and fmt_filter.upper() == "JPG":
            paths_to_delete = []
            for item in target_items:
                for p in item.stacked_paths:
                    if p.suffix.lower() in (".jpg", ".jpeg"):
                        paths_to_delete.append(p)
            if paths_to_delete:
                self._confirm_and_delete_files(target_items, paths_to_delete)
            else:
                mb.showinfo("No JPG Files", "No JPG files found in the selected items.")
        elif fmt_filter and fmt_filter.upper() in ("RAW", "ARW"):
            paths_to_delete = []
            for item in target_items:
                for p in item.stacked_paths:
                    if p.suffix.lower() == ".arw":
                        paths_to_delete.append(p)
            if paths_to_delete:
                self._confirm_and_delete_files(target_items, paths_to_delete)
            else:
                mb.showinfo("No RAW Files", "No RAW files found in the selected items.")
        elif stacked_count > 0:
            dialog = DeleteStackedDialog(self, target_items=target_items)
            if dialog.result is None:
                return
            self._confirm_and_delete_files(target_items, dialog.result)
        else:
            self._confirm_and_delete_files(target_items, [p for item in target_items for p in item.stacked_paths])

    def _confirm_and_delete_files(self, items: List['ImageItem'], paths: List[Path]):
        session = self._get_active_session()
        if not paths or not session:
            return

        if len(paths) <= 5:
            path_list = "\n".join(f"  • {p.name}" for p in paths)
            msg = f"Move {len(paths)} file(s) to Recycle Bin / Trash?\n\n{path_list}"
        else:
            preview = "\n".join(f"  • {p.name}" for p in paths[:5])
            msg = f"Move {len(paths)} file(s) to Recycle Bin / Trash?\n\n{preview}\n  ... and {len(paths) - 5} more"

        confirm = mb.askyesno(title="Move Files to Trash", message=msg, icon="warning")
        if not confirm:
            return

        moved_count = session.move_specific_files_to_trash(items, paths)
        self._update_status(f"Moved {moved_count} file(s) to Recycle Bin / Trash.")
        self._on_filter_changed()

    def _on_raw_settings_changed(self):
        scale = self.toolbar.get_raw_scale()
        wb = self.toolbar.get_white_balance()

        self.db.set_raw_scale(scale)
        self.db.set_white_balance(wb)

        self._update_status(f"Updated RAW Settings -> Scale: {int(scale*100)}%, WB: {wb.title()}")
        if 0 <= self.current_index < len(self.current_items):
            self._select_image(self.current_index)

    def _on_load_100_percent(self):
        session = self._get_active_session()
        if self.current_index < 0 or not self.current_items or not session:
            return

        item = self.current_items[self.current_index]
        wb = self.toolbar.get_white_balance()

        self._update_status(f"Loading 100% Full Resolution for {item.filename}...")
        self.viewer.show_loading(f"🔍 Loading 100% Full Resolution: {item.filename}")

        def worker():
            pil_img = session.image_loader.load_full_image(item.path, raw_scale=1.0, white_balance=wb)
            self.after(0, lambda: self._on_100_percent_loaded(item, pil_img))

        threading.Thread(target=worker, daemon=True).start()

    def _on_100_percent_loaded(self, item: ImageItem, pil_img: Optional[Image.Image]):
        self.viewer.hide_loading()
        self._on_image_loaded(item, pil_img, full_res=True)

    def _on_scan_blur(self):
        session = self._get_active_session()
        if not session or not session.items:
            mb.showinfo("Scan for Blur", "No directory loaded to scan.")
            return

        init_method = self.db.get_blur_method()
        init_perc = self.db.get_blur_percentile()
        init_flag = self.db.get_blur_flag_action()
        init_tag = self.db.get_blur_tag_action()
        init_star = self.db.get_blur_rating_action()
        init_subject = self.db.get_blur_subject_detect()

        BlurScanDialog(
            self,
            on_run=self._run_blur_scan,
            initial_percentile=init_perc,
            initial_method=init_method,
            initial_flag_action=init_flag,
            initial_tag_action=init_tag,
            initial_rating_action=init_star,
            initial_file_type="ARW",
            initial_subject_detect=init_subject
        )

    def _run_blur_scan(
        self,
        bottom_percentile: float,
        method: str,
        flag_action: str = "Reject",
        tag_action: Optional[str] = "Blur",
        rating_action: Optional[int] = None,
        file_type_filter: str = "ARW",
        subject_detect: bool = False
    ):
        self.db.set_blur_method(method)
        self.db.set_blur_percentile(bottom_percentile)
        self.db.set_blur_flag_action(flag_action)
        self.db.set_blur_tag_action(tag_action or "")
        self.db.set_blur_rating_action(f"{rating_action} Star{'s' if rating_action and rating_action > 1 else ''}" if rating_action is not None else "None")
        self.db.set_blur_subject_detect(subject_detect)

        status_msg = f"Scanning directory for blurry photos (Method: {method}, Cutoff: {int(bottom_percentile)}%)"
        if subject_detect:
            status_msg += " + Subject Detection"
        self._update_status(status_msg)

        cancel_event = threading.Event()

        prog_dialog = ProgressDialog(
            self,
            title_text="🔍 Scan for Blur Progress",
            header_text=f"🔍 Scanning Blurry Photos ({method.upper()})...",
            on_cancel=lambda: cancel_event.set()
        )

        def progress_cb(completed: int, total: int, fn: str = ""):
            if not prog_dialog.is_cancelled:
                self.after(0, lambda c=completed, t=total, f=fn: prog_dialog.update_progress(c, t, f))

        def worker():
            session = self._get_active_session()
            if not session:
                return
            flagged = session.scan_for_blur(
                bottom_percentile=bottom_percentile,
                method=method,
                flag_action=flag_action,
                tag_action=tag_action,
                rating_action=rating_action,
                file_type_filter=file_type_filter,
                progress_callback=progress_cb,
                cancel_event=cancel_event
            )
            if not cancel_event.is_set() and subject_detect:
                prog_dialog.lbl_header.configure(text="🎯 Detecting subjects with YOLO...")
                prog_dialog.lbl_item.configure(text="Detecting subjects...")
                prog_dialog.progress_bar.set(0.0)

                def subject_progress_cb(completed: int, total: int, fn: str = ""):
                    if not prog_dialog.is_cancelled:
                        self.after(0, lambda c=completed, t=total, f=fn: prog_dialog.update_progress(c, t, f))

                session.detect_subjects(progress_callback=subject_progress_cb, cancel_event=cancel_event)

            if not cancel_event.is_set():
                self.after(0, lambda: self._on_scan_blur_complete(len(flagged), prog_dialog, subject_detect=subject_detect))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_blur_complete(self, count: int, prog_dialog: Optional[ProgressDialog] = None, subject_detect: bool = False):
        if prog_dialog and prog_dialog.winfo_exists():
            try:
                prog_dialog.destroy()
            except Exception:
                pass
        if count > 0:
            self._on_filter_changed()
            mb.showinfo("Scan for Blur Complete", f"Identified {count} blurry photos and applied configured actions.")
        else:
            self._update_status("Blur scan complete — no blurry photos found.")

        if subject_detect and self.current_items and 0 <= self.current_index < len(self.current_items):
            cur_item = self.current_items[self.current_index]
            if cur_item.detection_box:
                self.viewer.set_detection_box(cur_item.detection_box)
            else:
                self.viewer.clear_detection_box()

    def _on_scan_duplicates(self):
        session = self._get_active_session()
        if not session or not session.items:
            mb.showinfo("Scan for Duplicates", "No directory loaded to scan.")
            return

        init_method = self.db.get_duplicate_method()
        init_thresh = self.db.get_duplicate_threshold()
        init_flag = self.db.get_duplicate_flag_action()
        init_tag = self.db.get_duplicate_tag_action()
        init_star = self.db.get_duplicate_rating_action()

        DuplicateScanDialog(
            self,
            on_run=self._run_duplicate_scan,
            initial_threshold=init_thresh,
            initial_method=init_method,
            initial_flag_action=init_flag,
            initial_tag_action=init_tag,
            initial_rating_action=init_star
        )

    def _run_duplicate_scan(
        self,
        threshold: float,
        method: str,
        flag_action: str = "Reject",
        tag_action: Optional[str] = "Duplicate",
        rating_action: Optional[int] = None,
        keeper_flag: str = "Pick",
        keeper_tag: Optional[str] = None,
        keeper_rating: Optional[int] = None,
        keeper_method: str = "sharpest",
        file_type_filter: str = "ARW"
    ):
        self.db.set_duplicate_method(method)
        self.db.set_duplicate_threshold(threshold)
        self.db.set_duplicate_flag_action(flag_action)
        self.db.set_duplicate_tag_action(tag_action or "")
        self.db.set_duplicate_rating_action(f"{rating_action} Star{'s' if rating_action and rating_action > 1 else ''}" if rating_action is not None else "None")

        self._update_status(f"Scanning directory for duplicates (Method: {method}, Threshold: {threshold})...")

        cancel_event = threading.Event()

        prog_dialog = ProgressDialog(
            self,
            title_text="👯 Scan for Duplicates Progress",
            header_text=f"👯 Scanning Duplicate Photos ({method.upper()})...",
            on_cancel=lambda: cancel_event.set()
        )

        def progress_cb(completed: int, total: int, fn: str = ""):
            if not prog_dialog.is_cancelled:
                self.after(0, lambda c=completed, t=total, f=fn: prog_dialog.update_progress(c, t, f))

        def worker():
            session = self._get_active_session()
            if not session:
                return
            flagged = session.scan_for_duplicates(
                method=method,
                threshold=threshold,
                flag_action=flag_action,
                tag_action=tag_action,
                rating_action=rating_action,
                keeper_flag=keeper_flag,
                keeper_tag=keeper_tag,
                keeper_rating=keeper_rating,
                keeper_method=keeper_method,
                file_type_filter=file_type_filter,
                progress_callback=progress_cb,
                cancel_event=cancel_event
            )
            if not cancel_event.is_set():
                self.after(0, lambda: self._on_scan_dups_complete(len(flagged), prog_dialog))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_dups_complete(self, count: int, prog_dialog: Optional[ProgressDialog] = None):
        if prog_dialog and prog_dialog.winfo_exists():
            try:
                prog_dialog.destroy()
            except Exception:
                pass
        if count > 0:
            self._on_filter_changed()
            mb.showinfo("Scan for Duplicates Complete", f"Identified {count} duplicate photos and applied configured actions.")
        else:
            self._update_status("Duplicate scan complete — no duplicates found.")

    def _on_unflag_all(self):
        session = self._get_active_session()
        if not session or not session.items:
            return

        ans = mb.askyesno("Unflag All Images", "Are you sure you want to reset all flags to UNFLAGGED?")
        if ans:
            count = session.unflag_all_items()
            self._on_filter_changed()
            self._update_status(f"Unflagged {count} images across current directory.")

    def _on_untag_all(self):
        session = self._get_active_session()
        if not session or not session.items:
            return

        ans = mb.askyesno("Untag All Images", "Are you sure you want to remove all tags from all images?")
        if ans:
            count = session.untag_all_items()
            self._on_filter_changed()
            self._update_status(f"Removed all tags across {count} images.")

    def _on_unrate_all(self):
        session = self._get_active_session()
        if not session or not session.items:
            return

        ans = mb.askyesno("Remove All Ratings", "Are you sure you want to reset all star ratings to 0?")
        if ans:
            count = session.unrate_all_items()
            self._on_filter_changed()
            self._update_status(f"Reset star ratings to 0 across {count} images.")

    def _on_clear_all(self):
        session = self._get_active_session()
        if not session or not session.items:
            return

        ans = mb.askyesno("Clear All Metadata", "Are you sure you want to reset Flags, Tags, Star Ratings, AND Subject Bounding Boxes for ALL photos?")
        if ans:
            count = session.clear_all_metadata()
            self.viewer.clear_detection_box()
            self._on_filter_changed()
            self._update_status(f"Cleared flags, tags, ratings, and subject bounding boxes across {count} photos.")

    def _on_trigger_crop(self):
        if self.current_index < 0 or not self.current_items:
            return
        if self.viewer.is_cropping:
            self.viewer.exit_crop_mode()
            self._update_status("Cancelled Manual Crop Mode.")
        else:
            self.viewer.enter_crop_mode(on_confirm_callback=self._on_save_crop)
            self._update_status("Entered Manual Crop Mode (Hold Shift for 1:1 Square, Esc to Cancel).")

    def _on_escape_pressed(self):
        if hasattr(self, "viewer") and self.viewer.is_cropping:
            self.viewer.exit_crop_mode()
            self._update_status("Cancelled Manual Crop Mode.")

    def _on_return_pressed(self):
        if hasattr(self, "viewer") and self.viewer.is_cropping:
            self.viewer._on_confirm_crop()

    def _on_save_crop(self, pct_x1: float, pct_y1: float, pct_x2: float, pct_y2: float):
        session = self._get_active_session()
        if self.current_index < 0 or not self.current_items or not session:
            return

        item = self.current_items[self.current_index]
        default_name = f"{item.path.stem}_cropped.jpg"

        dest = fd.asksaveasfilename(
            title="Save Cropped Image As...",
            initialfile=default_name,
            filetypes=[
                ("JPEG Image (*.jpg;*.jpeg)", "*.jpg;*.jpeg"),
                ("PNG Image (*.png)", "*.png"),
                ("WEBP Image (*.webp)", "*.webp")
            ],
            defaultextension=".jpg"
        )
        if not dest:
            self._update_status("Crop save cancelled.")
            return

        target_path = Path(dest)
        wb = self.toolbar.get_white_balance()

        self._update_status(f"Saving cropped image to {target_path.name}...")
        self.viewer.show_loading(f"✂️ Cropping & Saving Image: {target_path.name}")

        def worker():
            session = self._get_active_session()
            if not session:
                return
            try:
                full_img = session.image_loader.load_full_image(item.path, raw_scale=1.0, white_balance=wb)
                if full_img is None:
                    self.after(0, lambda: self._on_save_error("Failed to load source image for crop."))
                    return

                iw, ih = full_img.size
                src_x1 = max(0, int(iw * pct_x1))
                src_y1 = max(0, int(ih * pct_y1))
                src_x2 = min(iw, int(iw * pct_x2))
                src_y2 = min(ih, int(ih * pct_y2))

                if src_x2 <= src_x1 or src_y2 <= src_y1:
                    src_x1, src_y1, src_x2, src_y2 = 0, 0, iw, ih

                cropped = full_img.crop((src_x1, src_y1, src_x2, src_y2))
                target_path.parent.mkdir(parents=True, exist_ok=True)

                fmt_ext = target_path.suffix.lower()
                save_fmt = "PNG" if fmt_ext == ".png" else ("WEBP" if fmt_ext == ".webp" else "JPEG")

                if save_fmt == "JPEG" and cropped.mode in ("RGBA", "P"):
                    cropped = cropped.convert("RGB")

                cropped.save(target_path, format=save_fmt, quality=95)
                self.after(0, lambda: self._on_save_success(f"Cropped image saved successfully:\n{target_path}"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_save_error(f"Error saving cropped image: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_as(self):
        if hasattr(self, "viewer") and self.viewer.is_cropping:
            self.viewer._on_confirm_crop()
            return

        if self.current_index < 0 or not self.current_items:
            mb.showinfo("Save Image As", "No image selected.")
            return

        item = self.current_items[self.current_index]
        default_name = item.path.with_suffix(".jpg").name

        dest = fd.asksaveasfilename(
            title="Save Active Image As...",
            initialfile=default_name,
            filetypes=[
                ("JPEG Image (*.jpg;*.jpeg)", "*.jpg;*.jpeg"),
                ("PNG Image (*.png)", "*.png"),
                ("WEBP Image (*.webp)", "*.webp")
            ],
            defaultextension=".jpg"
        )
        if not dest:
            self._update_status("Save As cancelled.")
            return

        target_path = Path(dest)
        wb = self.toolbar.get_white_balance()

        self._update_status(f"Saving {item.filename} as {target_path.name}...")
        self.viewer.show_loading(f"💾 Saving Image: {target_path.name}")

        def worker():
            session = self._get_active_session()
            if not session:
                return
            try:
                full_img = session.image_loader.load_full_image(item.path, raw_scale=1.0, white_balance=wb)
                if full_img is None:
                    self.after(0, lambda: self._on_save_error("Failed to load source image."))
                    return

                target_path.parent.mkdir(parents=True, exist_ok=True)
                fmt_ext = target_path.suffix.lower()
                save_fmt = "PNG" if fmt_ext == ".png" else ("WEBP" if fmt_ext == ".webp" else "JPEG")

                if save_fmt == "JPEG" and full_img.mode in ("RGBA", "P"):
                    full_img = full_img.convert("RGB")

                full_img.save(target_path, format=save_fmt, quality=95)
                self.after(0, lambda: self._on_save_success(f"Image saved successfully:\n{target_path}"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_save_error(f"Error saving image: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_success(self, msg: str):
        self.viewer.hide_loading()
        mb.showinfo("Save Image Success", msg)
        self._update_status("Saved image successfully.")

    def _on_save_error(self, err_msg: str):
        self.viewer.hide_loading()
        mb.showerror("Save Image Error", err_msg)
        self._update_status("Failed to save image.")

    def _on_convert_jpg(self):
        if not self.current_items:
            return

        target_items = [self.current_items[idx] for idx in sorted(self.selected_indices) if 0 <= idx < len(self.current_items)]
        if not target_items and 0 <= self.current_index < len(self.current_items):
            target_items = [self.current_items[self.current_index]]

        if not target_items:
            return

        save_folder = self.db.get_jpg_save_folder()

        if len(target_items) == 1:
            item = target_items[0]
            suggested_name = item.path.with_suffix(".jpg").name
            initial_dir = self.db.get_jpg_save_folder()
            if initial_dir in ("source", "<source>", "") or not initial_dir:
                initial_dir = str(item.path.parent)
            else:
                initial_dir = str(Path(initial_dir).resolve())

            res_path = fd.asksaveasfilename(
                title="Save JPG As",
                initialdir=initial_dir,
                initialfile=suggested_name,
                filetypes=[("JPEG files", "*.jpg"), ("All files", "*.*")],
                defaultextension=".jpg"
            )
            if not res_path:
                self._update_status("JPG conversion cancelled.")
                return

            out_path = Path(res_path)
            if out_path.suffix.lower() not in ('.jpg', '.jpeg'):
                out_path = out_path.with_suffix('.jpg')

            self._update_status(f"Converting {item.filename} to JPG...")
            self.viewer.show_loading(f"🖼️ Converting to JPG: {item.filename}")

            def worker():
                session = self._get_active_session()
                if not session:
                    return
                ok, reason, res_path = session.convert_item_to_jpg(item, target_path=out_path, overwrite=True)
                self.after(0, lambda: self._on_convert_complete(ok, reason, res_path))

            threading.Thread(target=worker, daemon=True).start()
        else:
            ans = mb.askyesno(
                "Convert Selected to JPG",
                f"Convert all {len(target_items)} selected photos to JPG format?"
            )
            if not ans:
                return

            self._update_status(f"Converting {len(target_items)} selected photos to JPG...")
            self.viewer.show_loading(f"🖼️ Converting {len(target_items)} selected photos to JPG...")

            def worker_batch():
                session = self._get_active_session()
                if not session:
                    return
                success_count = 0
                total = len(target_items)
                for idx, item in enumerate(target_items):
                    if save_folder in ("source", "<source>", "") or not save_folder:
                        out_dir = item.path.parent
                    else:
                        out_dir = Path(save_folder)

                    ok, _, _ = session.convert_item_to_jpg(item, output_dir=out_dir, overwrite=True)
                    if ok:
                        success_count += 1
                    frac = (idx + 1) / float(total)
                    self.after(0, lambda i=idx+1, t=total, f=frac: self.viewer.update_loading_progress(i, t, f))

                self.after(0, lambda: self._on_batch_convert_complete(success_count, total))

            threading.Thread(target=worker_batch, daemon=True).start()

    def _on_convert_complete(self, ok: bool, reason: str, res_path: Path):
        self.viewer.hide_loading()
        if ok:
            if reason == "already_jpg":
                mb.showinfo("Convert to JPG", "Selected file is already a JPG.")
            else:
                mb.showinfo("Convert to JPG Success", f"Successfully saved JPG:\n{res_path}")
                self._update_status(f"Saved JPG to {res_path.name}")
                tab = self._get_active_tab()
                if tab and tab["session"].directory:
                    self._load_directory(str(tab["session"].directory))
        else:
            mb.showerror("Convert to JPG Failed", f"Failed to convert image: {reason}")
            self._update_status("JPG conversion failed.")

    def _on_batch_convert_complete(self, success_count: int, total_count: int):
        self.viewer.hide_loading()
        mb.showinfo("Convert to JPG Complete", f"Successfully converted {success_count} of {total_count} selected photos to JPG.")
        self._update_status(f"Converted {success_count} selected photos to JPG.")
        tab = self._get_active_tab()
        if tab and tab["session"].directory:
            self._load_directory(str(tab["session"].directory))

    def _on_set_jpg_folder(self):
        current_val = self.db.get_jpg_save_folder()
        choice = simpledialog.askstring(
            "JPG Save Folder Setting",
            "Set JPG destination directory:\n• Enter '<source>' to save in same directory as RAW\n• Or enter a custom folder path:",
            initialvalue=current_val
        )
        if choice and choice.strip():
            val = choice.strip()
            if val.lower() in ("source", "<source>"):
                val = "<source>"
            self.db.set_jpg_save_folder(val)
            self._update_status(f"Updated JPG Save Folder Setting: '{val}'")
            mb.showinfo("Setting Updated", f"JPG Save Destination set to: {val}")

    def _on_cleanup_metadata(self):
        log_info("Opening MetadataCleanupDialog explorer modal")
        dialog = MetadataCleanupDialog(
            self,
            db_manager=self.db,
            on_cleanup_complete=self._on_cleanup_done
        )

    def _on_cleanup_done(self, deleted_count: int, cleaned_folders: List[str]):
        self._update_status(f"Cleaned up {deleted_count} database metadata records across {len(cleaned_folders)} folders.")
        tab = self._get_active_tab()
        if tab and tab["session"].directory:
            cur_dir_str = str(tab["session"].directory).lower()
            for cf in cleaned_folders:
                if cf.lower() in cur_dir_str or cur_dir_str in cf.lower():
                    self._load_directory(str(tab["session"].directory))
                    break

    def _on_move_picked(self):
        tab = self._get_active_tab()
        session = self._get_active_session()
        if not session or not tab or not session.directory:
            mb.showinfo("Move Picked Images", "No active directory loaded.")
            return

        folder_name = self.db.get_picked_folder()
        ans = mb.askyesno(
            "Move Picked Images",
            f"Move all images flagged as PICK into destination subfolder '{folder_name}'?"
        )
        if ans:
            try:
                moved = session.move_items_by_flag(FlagState.PICK, folder_name)
                mb.showinfo("Move Picked Complete", f"Successfully moved {len(moved)} PICK files into '{folder_name}'.")
                self._load_directory(str(session.directory))
            except Exception as e:
                mb.showerror("Move Error", f"Failed to move picked files: {e}")

    def _on_move_rejected(self):
        tab = self._get_active_tab()
        session = self._get_active_session()
        if not session or not tab or not session.directory:
            mb.showinfo("Move Rejected Images", "No active directory loaded.")
            return

        folder_name = self.db.get_rejected_folder()
        ans = mb.askyesno(
            "Move Rejected Images",
            f"Move all images flagged as REJECT into destination subfolder '{folder_name}'?"
        )
        if ans:
            try:
                moved = session.move_items_by_flag(FlagState.REJECT, folder_name)
                mb.showinfo("Move Rejected Complete", f"Successfully moved {len(moved)} REJECT files into '{folder_name}'.")
                self._load_directory(str(session.directory))
            except Exception as e:
                mb.showerror("Move Error", f"Failed to move rejected files: {e}")

    def _on_config_output_folders(self):
        self._on_open_settings()

    def _on_open_settings(self):
        SettingsDialog(
            self,
            self.db,
            on_save=self._on_settings_saved,
            on_cleanup_metadata=self._on_cleanup_metadata,
            on_export_manifest=self._export_manifest,
            on_sync_exif=self._sync_exif_ratings
        )

    def _on_settings_saved(self):
        new_p = self.db.get_picked_folder()
        new_r = self.db.get_rejected_folder()
        self.meta_panel.update_output_folders(new_p, new_r)

        scale_val = self.db.get_raw_scale()
        sc_str = "25%"
        if scale_val == 0.10: sc_str = "10%"
        elif scale_val == 0.15: sc_str = "15%"
        elif scale_val == 0.20: sc_str = "20%"
        elif scale_val == 0.50: sc_str = "50%"
        elif scale_val == 1.00: sc_str = "100%"
        self.toolbar.opt_raw_scale.set(sc_str)

        wb_val = self.db.get_white_balance()
        self.toolbar.opt_wb.set("Camera" if wb_val == "camera" else "Auto")

        self._update_status(f"Settings saved. Picked: '{new_p}', Rejected: '{new_r}', RAW Scale: {sc_str}")

        custom_tags = self.db.get_custom_tags()
        self.meta_panel.refresh_tag_buttons(custom_tags)
        self.toolbar.update_tag_options(custom_tags)

        tab = self._get_active_tab()
        if tab and tab["session"].directory:
            self._load_directory(str(tab["session"].directory))

    def _batch_move(self, flag: FlagState, folder_name: str):
        session = self._get_active_session()
        if not session or not session.directory:
            return

        ans = mb.askyesno(
            f"Move {flag.value} Images",
            f"Move all images flagged as {flag.value} into subfolder '{folder_name}'?"
        )
        if ans:
            try:
                moved = session.move_items_by_flag(flag, folder_name)
                mb.showinfo("Batch Move Complete", f"Moved {len(moved)} files into subfolder '{folder_name}'.")
                self._load_directory(str(session.directory))
            except Exception as e:
                mb.showerror("Batch Move Error", f"Failed to move files: {e}")

    def _export_manifest(self):
        tab = self._get_active_tab()
        if not tab or not tab["session"].items or not tab["session"].directory:
            return

        out_file = tab["session"].directory / "culling_manifest.json"
        try:
            res_path = tab["session"].export_manifest(out_file, format_type="json")
            mb.showinfo("Export Manifest Success", f"Culling manifest saved to:\n{res_path}")
            self._update_status("Exported manifest JSON.")
        except Exception as e:
            mb.showerror("Export Manifest Failed", f"Error exporting manifest: {e}")

    def _sync_exif_ratings(self):
        session = self._get_active_session()
        if not session or not session.items:
            return

        self._update_status("Syncing star ratings to EXIF metadata...")
        self.viewer.show_loading("Syncing Star Ratings to EXIF...")

        def worker():
            count = session.sync_exif_ratings()
            self.after(0, lambda: self._on_sync_complete(count))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sync_complete(self, count: int):
        self.viewer.hide_loading()
        mb.showinfo("Sync Complete", f"Successfully synced star ratings to EXIF metadata for {count} files.")
        self._update_status(f"Synced EXIF ratings for {count} files.")

    def _on_load_100_percent(self):
        session = self._get_active_session()
        if not self.current_items or not (0 <= self.current_index < len(self.current_items)):
            return

        cur_item = self.current_items[self.current_index]

        self._update_status(f"🔍 Loading 100% Full Resolution: {cur_item.filename}...")
        self.viewer.show_loading(f"🔍 Decoding 100% Full Resolution: {cur_item.filename}")

        def worker():
            white_balance = self.toolbar.get_white_balance() if hasattr(self, "toolbar") else "camera"
            img = session.image_loader.load_full_image(cur_item.path, raw_scale=1.00, white_balance=white_balance) if session else None
            if img:
                def update_ui():
                    self.viewer.set_image(img, preserve_zoom=False)
                    self._update_status(f"🔍 Loaded 100% Full Resolution: {cur_item.filename}")

                self.after(0, update_ui)
            else:
                self.after(0, lambda: self.viewer.hide_loading())

        threading.Thread(target=worker, daemon=True).start()

    def _on_copy_image_to_clipboard(self):
        session = self._get_active_session()
        if not session or not self.current_items or not (0 <= self.current_index < len(self.current_items)):
            return

        cur_item = self.current_items[self.current_index]
        self._update_status(f"Copying {cur_item.filename} to Clipboard...")

        def worker():
            session = self._get_active_session()
            if not session:
                return
            crop_pcts = self.viewer.get_crop_box_percentages()

            raw_scale = self.toolbar.get_raw_scale()
            white_balance = self.toolbar.get_white_balance()

            img = session.image_loader.get_cached_full_image(cur_item.path, raw_scale=raw_scale, white_balance=white_balance)
            if img is None:
                img = session.image_loader.load_full_image(cur_item.path, raw_scale=raw_scale, white_balance=white_balance)

            if img:
                if crop_pcts is not None:
                    w, h = img.size
                    px1 = max(0, min(w, int(crop_pcts[0] * w)))
                    py1 = max(0, min(h, int(crop_pcts[1] * h)))
                    px2 = max(0, min(w, int(crop_pcts[2] * w)))
                    py2 = max(0, min(h, int(crop_pcts[3] * h)))

                    if px2 > px1 and py2 > py1:
                        img = img.crop((px1, py1, px2, py2))

                    ok = copy_image_to_clipboard(img)
                    if ok:
                        self.after(0, lambda: self._update_status(f"📋 Copied Cropped Selection of '{cur_item.filename}' as JPEG to Clipboard!"))
                    else:
                        self.after(0, lambda: self._update_status("❌ Failed to copy cropped image to Clipboard."))
                else:
                    ok = copy_image_to_clipboard(img)
                    if ok:
                        self.after(0, lambda: self._update_status(f"📋 Copied '{cur_item.filename}' as JPEG to Clipboard!"))
                    else:
                        self.after(0, lambda: self._update_status("❌ Failed to copy image to Clipboard."))
            else:
                self.after(0, lambda: self._update_status("❌ Could not decode image for Clipboard."))

        threading.Thread(target=worker, daemon=True).start()

    def _on_open_explorer(self):
        tab = self._get_active_tab()
        if tab and tab.get("session") and tab["session"].directory and tab["session"].directory.exists():
            open_folder_in_explorer(tab["session"].directory)
            self._update_status(f"Opened folder in File Explorer: {tab['session'].directory.name}")
        else:
            mb.showinfo("Open Folder", "No active photo folder opened.")


def copy_image_to_clipboard(pil_img: Image.Image, temp_jpg_path: Optional[Path] = None) -> bool:
    """
    Copy a PIL Image to the Windows System Clipboard using dual payloads:
    1. CF_DIB: Bitmap pixel data (for Photoshop, Paint, GIMP, Word, PowerPoint)
    2. CF_HDROP: Temp JPEG file path payload (for Discord, Slack, WhatsApp, Telegram, Browsers, File Explorer)
    """
    if pil_img is None:
        return False

    try:
        import io
        import os
        import ctypes
        import tempfile

        rgb_img = pil_img.convert("RGB")

        # 1. Generate CF_DIB bitmap data
        output = io.BytesIO()
        rgb_img.save(output, "BMP")
        data = output.getvalue()[14:]  # Strip 14-byte BMP header
        output.close()

        # 2. Save temporary JPEG file for file-drop clipboard readers (Discord, Slack, WhatsApp)
        if temp_jpg_path is None:
            tmp_fd, tmp_file_str = tempfile.mkstemp(suffix=".jpg", prefix="culler_clip_")
            os.close(tmp_fd)
            temp_jpg_path = Path(tmp_file_str)

        rgb_img.save(str(temp_jpg_path), "JPEG", quality=95)

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Define 64-bit safe Win32 API function signatures
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = ctypes.c_bool

        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p

        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool

        CF_DIB = 8
        CF_HDROP = 15
        GMEM_MOVEABLE = 0x0002
        GMEM_ZEROINIT = 0x0040

        if not user32.OpenClipboard(None):
            log_error("[Clipboard Error] OpenClipboard failed")
            return False

        dib_ok = False
        hdrop_ok = False

        try:
            user32.EmptyClipboard()

            # A) Set CF_DIB (Bitmap pixel data)
            h_dib = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
            if h_dib:
                ptr = kernel32.GlobalLock(h_dib)
                if ptr:
                    ctypes.memmove(ptr, data, len(data))
                    kernel32.GlobalUnlock(h_dib)
                    res = user32.SetClipboardData(CF_DIB, h_dib)
                    if res:
                        dib_ok = True

            # B) Set CF_HDROP (File drop payload for Discord, Slack, WhatsApp, Telegram, Browsers, Explorer)
            abs_path_str = str(temp_jpg_path.resolve()) + "\0\0"
            path_bytes = abs_path_str.encode("utf-16le")
            header = (20).to_bytes(4, "little") + b"\x00" * 12 + (1).to_bytes(4, "little")
            drop_data = header + path_bytes

            h_hdrop = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(drop_data))
            if h_hdrop:
                ptr = kernel32.GlobalLock(h_hdrop)
                if ptr:
                    ctypes.memmove(ptr, drop_data, len(drop_data))
                    kernel32.GlobalUnlock(h_hdrop)
                    res = user32.SetClipboardData(CF_HDROP, h_hdrop)
                    if res:
                        hdrop_ok = True

            log_info(f"Copy image to clipboard success: CF_DIB={dib_ok}, CF_HDROP={hdrop_ok}")
            return dib_ok or hdrop_ok
        finally:
            user32.CloseClipboard()
    except Exception as e:
        log_error(f"Error copying image to clipboard: {e}")
        return False


class DeleteStackedDialog(ctk.CTkToplevel):
    """
    Modal dialog showing individual files with checkboxes for selective deletion.
    """

    def __init__(self, master, target_items: List['ImageItem']):
        super().__init__(master)
        self.result: Optional[List[Path]] = None
        self._check_vars: Dict[Path, ctk.BooleanVar] = {}

        self.title("🗑️ Select Files to Delete")
        self.geometry("600x480")
        self.resizable(True, True)

        self.transient(master)
        self.grab_set()

        self.bind("<Escape>", lambda e: self._on_cancel())

        all_paths: List[Path] = []
        for item in target_items:
            for p in item.stacked_paths:
                all_paths.append(p)

        lbl_title = ctk.CTkLabel(
            self,
            text=f"Select files to move to Recycle Bin / Trash ({len(all_paths)} files)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_title.pack(anchor="w", padx=15, pady=(12, 6))

        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(0, 6))

        btn_sel_all = ctk.CTkButton(
            btn_bar, text="Select All", width=90, height=26,
            fg_color="#333333", hover_color="#555555",
            font=ctk.CTkFont(size=11), command=lambda: self._set_all(True)
        )
        btn_sel_all.pack(side="left", padx=(0, 4))

        btn_desel = ctk.CTkButton(
            btn_bar, text="Deselect All", width=90, height=26,
            fg_color="#333333", hover_color="#555555",
            font=ctk.CTkFont(size=11), command=lambda: self._set_all(False)
        )
        btn_desel.pack(side="left", padx=4)

        self.lbl_count = ctk.CTkLabel(
            btn_bar, text="0 selected", font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_count.pack(side="right", padx=5)

        scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=6, fg_color="#1e1e1e", border_width=1, border_color="#383838")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=5)

        for p in all_paths:
            ext = p.suffix.lower()
            if ext == ".arw":
                badge = "RAW"
                badge_color = "#3a86ff"
            elif ext in (".jpg", ".jpeg"):
                badge = "JPG"
                badge_color = "#2b9348"
            else:
                badge = ext.upper().lstrip(".")
                badge_color = "#888888"

            row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            var = ctk.BooleanVar(value=True)
            self._check_vars[p] = var

            chk = ctk.CTkCheckBox(
                row, text="", variable=var, width=24,
                checkbox_width=18, checkbox_height=18,
                command=lambda v=var: self._update_count()
            )
            chk.pack(side="left", padx=(4, 8), pady=4)

            badge_lbl = ctk.CTkLabel(
                row, text=badge, width=40, height=22,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=badge_color, corner_radius=4,
                anchor="center"
            )
            badge_lbl.pack(side="left", padx=(0, 8))

            name_lbl = ctk.CTkLabel(
                row, text=p.name, font=ctk.CTkFont(size=11),
                anchor="w"
            )
            name_lbl.pack(side="left", fill="x", expand=True)

        self._update_count()

        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=15, pady=(8, 12))

        btn_cancel = ctk.CTkButton(
            bottom_bar, text="Cancel", width=90, height=32,
            fg_color="#4a4e69", hover_color="#22223b",
            command=self._on_cancel
        )
        btn_cancel.pack(side="right", padx=(4, 0))

        btn_delete = ctk.CTkButton(
            bottom_bar, text="🗑️ Delete Selected", width=140, height=32,
            fg_color="#d90429", hover_color="#b00020",
            font=ctk.CTkFont(weight="bold", size=12),
            command=self._on_delete
        )
        btn_delete.pack(side="right", padx=(0, 4))

        self.after(10, self._center_window)
        self.wait_window()

    def _center_window(self):
        self.update_idletasks()
        try:
            pw = self.master.winfo_width()
            ph = self.master.winfo_height()
            px = self.master.winfo_x()
            py = self.master.winfo_y()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _set_all(self, value: bool):
        for var in self._check_vars.values():
            var.set(value)
        self._update_count()

    def _update_count(self):
        count = sum(1 for var in self._check_vars.values() if var.get())
        self.lbl_count.configure(text=f"{count} selected")

    def _on_delete(self):
        selected = [p for p, var in self._check_vars.items() if var.get()]
        if not selected:
            mb.showwarning("No Files Selected", "Please select at least one file to delete.")
            return
        self.result = selected
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def open_folder_in_explorer(folder_path: Path):
    """
    Open directory in OS File Manager (Windows Explorer, macOS Finder, Linux File Manager).
    """
    p = Path(folder_path).resolve()
    if not p.exists():
        return

    if sys.platform == "win32":
        os.startfile(str(p))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


if __name__ == "__main__":
    app = ImageCullerApp()
    app.mainloop()
