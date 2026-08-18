from pathlib import Path
from typing import Callable, Dict, List, Optional
import customtkinter as ctk
from tkinter import messagebox as mb

from ..db_manager import DatabaseManager
from ..logger import log_info, log_error


class SettingsDialog(ctk.CTkToplevel):
    """
    Unified Application Settings Modal Window with Tabbed Interface.
    Tab 1 (General): Output Destination Subfolders, RAW Scale, White Balance, Tools.
    Tab 2 (Workspace): Workspace Database File, Dataset Info, Folder Metadata Explorer & Cleanup.
    Tab 3 (Tags): Manage custom image tags.
    """

    def __init__(
        self,
        master,
        db: DatabaseManager,
        initial_tab: str = "General",
        on_save: Optional[Callable[[], None]] = None,
        on_cleanup_metadata: Optional[Callable[[], None]] = None,
        on_cleanup_complete: Optional[Callable[[int, List[str]], None]] = None
    ):
        super().__init__(master)
        self.db = db
        self.initial_tab = initial_tab
        self.on_save = on_save
        self.on_cleanup_metadata = on_cleanup_metadata
        self.on_cleanup_complete = on_cleanup_complete

        self._check_vars: Dict[str, ctk.BooleanVar] = {}
        self._folder_summary: Dict[str, Dict[str, int]] = {}

        self.title("⚙️ Application Settings")
        self.geometry("660x640")
        self.minsize(580, 540)
        self.resizable(True, True)

        # Make modal dialog window
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self.destroy())

        self._build_widgets()
        self.after(10, self._center_window)

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

    def _build_widgets(self):
        # Bottom Button Bar (packed FIRST with side="bottom" so Save and Cancel buttons are always visible)
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(side="bottom", fill="x", padx=20, pady=12)

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancel",
            width=90,
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=4)

        btn_save = ctk.CTkButton(
            btn_bar,
            text="💾 Save Settings",
            width=130,
            fg_color="#2b9348",
            hover_color="#1b4332",
            font=ctk.CTkFont(weight="bold"),
            command=self._save_settings
        )
        btn_save.pack(side="right", padx=4)

        # Header Label
        lbl_title = ctk.CTkLabel(
            self,
            text="⚙️ Application Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_title.pack(side="top", pady=(15, 5))

        # Tabview
        self.tabview = ctk.CTkTabview(self, width=620)
        self.tabview.pack(side="top", fill="both", expand=True, padx=15, pady=(5, 5))

        self.tabview.add("General")
        self.tabview.add("Workspace")
        self.tabview.add("Tags")

        self._build_general_tab(self.tabview.tab("General"))
        self._build_workspace_tab(self.tabview.tab("Workspace"))
        self._build_tags_tab(self.tabview.tab("Tags"))

        if self.initial_tab in ["General", "Workspace", "Tags"]:
            self.tabview.set(self.initial_tab)

    def _build_general_tab(self, tab):
        container = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        container.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # ----------------------------------------------------
        # Section 1: Output Destination Subfolders
        # ----------------------------------------------------
        lbl_sec1 = ctk.CTkLabel(
            container,
            text="📁 Destination Folders for Batch Moves",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_sec1.pack(anchor="w", pady=(5, 4))

        # Picked subfolder
        f_picked = ctk.CTkFrame(container, fg_color="transparent")
        f_picked.pack(fill="x", pady=2)
        lbl_p = ctk.CTkLabel(f_picked, text="Picked Subfolder:", width=150, anchor="w")
        lbl_p.pack(side="left")
        self.entry_picked = ctk.CTkEntry(f_picked, placeholder_text="_SELECTED")
        self.entry_picked.pack(side="left", fill="x", expand=True)
        self.entry_picked.insert(0, self.db.get_picked_folder())

        # Rejected subfolder
        f_rejected = ctk.CTkFrame(container, fg_color="transparent")
        f_rejected.pack(fill="x", pady=2)
        lbl_r = ctk.CTkLabel(f_rejected, text="Rejected Subfolder:", width=150, anchor="w")
        lbl_r.pack(side="left")
        self.entry_rejected = ctk.CTkEntry(f_rejected, placeholder_text="_REJECTED")
        self.entry_rejected.pack(side="left", fill="x", expand=True)
        self.entry_rejected.insert(0, self.db.get_rejected_folder())

        # JPG Export Subfolder
        f_jpg = ctk.CTkFrame(container, fg_color="transparent")
        f_jpg.pack(fill="x", pady=2)
        lbl_jpg = ctk.CTkLabel(f_jpg, text="Converted JPG Subfolder:", width=150, anchor="w")
        lbl_jpg.pack(side="left")
        self.entry_jpg = ctk.CTkEntry(f_jpg, placeholder_text="<source>")
        self.entry_jpg.pack(side="left", fill="x", expand=True)
        self.entry_jpg.insert(0, self.db.get_jpg_save_folder())

        # Separator line
        sep1 = ctk.CTkFrame(container, height=1, fg_color="#333333")
        sep1.pack(fill="x", pady=10)

        # ----------------------------------------------------
        # Section 2: RAW Load Performance & White Balance
        # ----------------------------------------------------
        lbl_sec2 = ctk.CTkLabel(
            container,
            text="⚡ RAW Image Load Scale & Processing",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_sec2.pack(anchor="w", pady=(0, 4))

        # RAW Scale dropdown
        f_scale = ctk.CTkFrame(container, fg_color="transparent")
        f_scale.pack(fill="x", pady=2)
        lbl_sc = ctk.CTkLabel(f_scale, text="Default RAW Scale:", width=130, anchor="w")
        lbl_sc.pack(side="left")

        init_scale = self.db.get_raw_scale()
        scale_str_default = "25%"
        if init_scale == 0.10: scale_str_default = "10%"
        elif init_scale == 0.15: scale_str_default = "15%"
        elif init_scale == 0.20: scale_str_default = "20%"
        elif init_scale == 0.50: scale_str_default = "50%"
        elif init_scale == 1.00: scale_str_default = "100%"

        self.opt_scale = ctk.CTkOptionMenu(
            f_scale,
            values=["10%", "15%", "20%", "25%", "50%", "100%"],
            width=120
        )
        self.opt_scale.set(scale_str_default)
        self.opt_scale.pack(side="left")

        # White Balance dropdown
        f_wb = ctk.CTkFrame(container, fg_color="transparent")
        f_wb.pack(fill="x", pady=2)
        lbl_wb_title = ctk.CTkLabel(f_wb, text="White Balance:", width=150, anchor="w")
        lbl_wb_title.pack(side="left")

        init_wb = self.db.get_white_balance()
        wb_str_default = "Camera" if init_wb == "camera" else "Auto"

        self.opt_wb = ctk.CTkOptionMenu(
            f_wb,
            values=["Camera", "Auto"],
            width=120
        )
        self.opt_wb.set(wb_str_default)
        self.opt_wb.pack(side="left")

        # Eye Detection Method dropdown
        f_eye = ctk.CTkFrame(container, fg_color="transparent")
        f_eye.pack(fill="x", pady=2)
        lbl_eye = ctk.CTkLabel(f_eye, text="Eye Detection Method:", width=150, anchor="w")
        lbl_eye.pack(side="left")

        init_eye = self.db.get_eye_detection_method()
        eye_opts = [
            "YOLO AI (Pose / Keypoints)",
            "Simple Hybrid (Haar + Geometry)"
        ]
        eye_display_map = {
            "yolo": "YOLO AI (Pose / Keypoints)",
            "auto": "YOLO AI (Pose / Keypoints)",
            "simple": "Simple Hybrid (Haar + Geometry)",
            "haar": "Simple Hybrid (Haar + Geometry)",
            "mediapipe": "Simple Hybrid (Haar + Geometry)",
            "geometry": "Simple Hybrid (Haar + Geometry)"
        }

        self.opt_eye = ctk.CTkOptionMenu(
            f_eye,
            values=eye_opts,
            width=230
        )
        self.opt_eye.set(eye_display_map.get(init_eye, "YOLO AI (Pose / Keypoints)"))
        self.opt_eye.pack(side="left")

        # Separator line
        sep2 = ctk.CTkFrame(container, height=1, fg_color="#333333")
        sep2.pack(fill="x", pady=10)

        # ----------------------------------------------------
        # Section 3: RAW+JPG Stacking Option
        # ----------------------------------------------------
        self.chk_stack = ctk.CTkCheckBox(
            container,
            text="Automatically Stack Matching RAW + JPG Files",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if self.db.get_stack_raw_jpg():
            self.chk_stack.select()
        else:
            self.chk_stack.deselect()
        self.chk_stack.pack(anchor="w", pady=4)
        
        self.chk_bbox = ctk.CTkCheckBox(
            container,
            text="Show Bounding Boxes (AI & Manual)",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        if self.db.get_show_bounding_boxes():
            self.chk_bbox.select()
        else:
            self.chk_bbox.deselect()
        self.chk_bbox.pack(anchor="w", pady=4)

        # ----------------------------------------------------
        # Section 4: Tools & Maintenance Actions
        # ----------------------------------------------------
        sep3 = ctk.CTkFrame(container, height=1, fg_color="#333333")
        sep3.pack(fill="x", pady=10)

        lbl_sec4 = ctk.CTkLabel(
            container,
            text="🔧 Maintenance & Session Tools",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_sec4.pack(anchor="w", pady=(0, 4))

        f_tools = ctk.CTkFrame(container, fg_color="transparent")
        f_tools.pack(fill="x", pady=2)

        # Workspace clean button jumps directly to Workspace tab
        btn_clean = ctk.CTkButton(
            f_tools,
            text="🧹 Workspace & DB",
            width=135,
            fg_color="#3a3a3a",
            hover_color="#555555",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self.tabview.set("Workspace")
        )
        btn_clean.pack(side="left", padx=2)

    def _build_workspace_tab(self, tab):
        container = ctk.CTkFrame(tab, fg_color="transparent")
        container.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # ----------------------------------------------------
        # Workspace File Information Header
        # ----------------------------------------------------
        ws_info_frame = ctk.CTkFrame(container, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#333333")
        ws_info_frame.pack(fill="x", pady=(0, 8))

        ws_file_path = str(self.db.db_path)
        ws_file_name = self.db.db_path.name
        ds_path = str(self.db.dataset_dir)

        lbl_ws_title = ctk.CTkLabel(
            ws_info_frame,
            text=f"🗂️ Active Workspace: {ws_file_name}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#3a86ff"
        )
        lbl_ws_title.pack(anchor="w", padx=12, pady=(8, 2))

        lbl_ws_path = ctk.CTkLabel(
            ws_info_frame,
            text=f"Database Path: {ws_file_path}",
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color="#888888"
        )
        lbl_ws_path.pack(anchor="w", padx=12, pady=1)

        lbl_ds_path = ctk.CTkLabel(
            ws_info_frame,
            text=f"Dataset Directory: {ds_path}",
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color="#888888"
        )
        lbl_ds_path.pack(anchor="w", padx=12, pady=(1, 8))

        # ----------------------------------------------------
        # Stored Metadata Explorer Header & Toolbar
        # ----------------------------------------------------
        tool_box = ctk.CTkFrame(container, fg_color="transparent")
        tool_box.pack(side="top", fill="x", pady=(0, 6))

        btn_sel_all = ctk.CTkButton(
            tool_box,
            text="✓ Select All",
            width=90,
            height=26,
            fg_color="#333333",
            hover_color="#555555",
            command=self._select_all_folders
        )
        btn_sel_all.pack(side="left", padx=(0, 5))

        btn_desel_all = ctk.CTkButton(
            tool_box,
            text="✗ Deselect All",
            width=90,
            height=26,
            fg_color="#333333",
            hover_color="#555555",
            command=self._deselect_all_folders
        )
        btn_desel_all.pack(side="left", padx=5)

        self.lbl_ws_stats = ctk.CTkLabel(
            tool_box,
            text="Loading stored database records...",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_ws_stats.pack(side="right", padx=5)

        # Embedded Folder Tree Container (Scrollable)
        self.ws_tree_scroll = ctk.CTkScrollableFrame(container, label_text="")
        self.ws_tree_scroll.pack(side="top", fill="both", expand=True, pady=(0, 8))

        # Action Bar for Cleanup
        action_bar = ctk.CTkFrame(container, fg_color="transparent")
        action_bar.pack(side="bottom", fill="x")

        btn_clean_sel = ctk.CTkButton(
            action_bar,
            text="🧹 Clean Selected Folders",
            fg_color="#5c0612",
            hover_color="#d90429",
            font=ctk.CTkFont(weight="bold"),
            command=self._clean_selected_folders
        )
        btn_clean_sel.pack(side="left", padx=(0, 5))

        btn_clean_all = ctk.CTkButton(
            action_bar,
            text="🗑️ Purge Entire Database",
            fg_color="#5c0612",
            hover_color="#d90429",
            font=ctk.CTkFont(weight="bold"),
            command=self._clean_entire_workspace_db
        )
        btn_clean_all.pack(side="left", padx=5)

        self._load_workspace_tree_data()

    def _load_workspace_tree_data(self):
        for w in self.ws_tree_scroll.winfo_children():
            w.destroy()
        self._check_vars.clear()

        self._folder_summary = self.db.get_stored_folders_summary()

        if not self._folder_summary:
            lbl_empty = ctk.CTkLabel(
                self.ws_tree_scroll,
                text="📁 No metadata records stored in database.",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#888888"
            )
            lbl_empty.pack(expand=True, pady=40)
            self.lbl_ws_stats.configure(text="Database: 0 Folders, 0 Records")
            return

        total_records = sum(stats["total"] for stats in self._folder_summary.values())
        self.lbl_ws_stats.configure(
            text=f"Database: {len(self._folder_summary)} Folders, {total_records} Records"
        )

        sorted_folders = sorted(self._folder_summary.keys(), key=lambda x: x.lower())

        for folder_path in sorted_folders:
            stats = self._folder_summary[folder_path]

            row_frame = ctk.CTkFrame(self.ws_tree_scroll, fg_color="#2b2b2b", corner_radius=4)
            row_frame.pack(fill="x", padx=2, pady=3)

            var = ctk.BooleanVar(value=False)
            self._check_vars[folder_path] = var

            chk = ctk.CTkCheckBox(
                row_frame,
                text="",
                variable=var,
                width=24,
                checkbox_width=18,
                checkbox_height=18
            )
            chk.pack(side="left", padx=(8, 4), pady=6)

            folder_name = Path(folder_path).name or folder_path
            lbl_folder = ctk.CTkLabel(
                row_frame,
                text=f"📁 {folder_name}",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            lbl_folder.pack(side="left", padx=4)

            badge_text = (
                f"{stats['total']} photos  |  "
                f"Pick: {stats['pick']}, Reject: {stats['reject']}, Unflagged: {stats['unflagged']}"
            )
            lbl_badge = ctk.CTkLabel(
                row_frame,
                text=badge_text,
                font=ctk.CTkFont(size=10),
                text_color="#a0a0a0",
                anchor="e"
            )
            lbl_badge.pack(side="right", padx=10)

            lbl_path = ctk.CTkLabel(
                row_frame,
                text=folder_path,
                font=ctk.CTkFont(size=10, family="Consolas"),
                text_color="#777777",
                anchor="w"
            )
            lbl_path.pack(side="left", padx=8)

        try:
            self.ws_tree_scroll.update_idletasks()
        except Exception:
            pass

    def _select_all_folders(self):
        for var in self._check_vars.values():
            var.set(True)

    def _deselect_all_folders(self):
        for var in self._check_vars.values():
            var.set(False)

    def _clean_selected_folders(self):
        selected = [fp for fp, var in self._check_vars.items() if var.get()]
        if not selected:
            mb.showwarning("Clean Up Metadata", "No folders selected. Please check at least one folder to clean.")
            return

        total_to_delete = sum(self._folder_summary[fp]["total"] for fp in selected if fp in self._folder_summary)

        ans = mb.askyesno(
            "Confirm Metadata Cleanup",
            f"Are you sure you want to clean up stored metadata for {len(selected)} selected folder(s)?\n\n"
            f"This will delete {total_to_delete} stored culling records from workspace database."
        )
        if ans:
            deleted_count = self.db.cleanup_multiple_folders(selected)
            log_info(f"SettingsDialog: Cleaned up {deleted_count} records across {len(selected)} folders.")
            mb.showinfo("Cleanup Complete", f"Successfully cleaned up {deleted_count} database records!")
            
            if self.on_cleanup_complete:
                self.on_cleanup_complete(deleted_count, selected)

            self._load_workspace_tree_data()

    def _clean_entire_workspace_db(self):
        ans = mb.askyesno(
            "PURGE ENTIRE DATABASE",
            "WARNING: This will permanently delete ALL stored culling records, ratings, and tags from workspace database!\n\n"
            "Are you sure you want to purge the entire database?",
            icon="warning"
        )
        if ans:
            deleted_count = self.db.cleanup_entire_database()
            log_info(f"SettingsDialog: Purged entire database ({deleted_count} records deleted).")
            mb.showinfo("Database Purged", f"Successfully purged {deleted_count} total database records!")

            if self.on_cleanup_complete:
                self.on_cleanup_complete(deleted_count, list(self._folder_summary.keys()))

            self._load_workspace_tree_data()

    def _build_tags_tab(self, tab):
        container = ctk.CTkFrame(tab, fg_color="transparent")
        container.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        lbl_head = ctk.CTkLabel(
            container,
            text="🏷️ Manage Image Tags",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_head.pack(anchor="w", pady=(5, 4))

        lbl_desc = ctk.CTkLabel(
            container,
            text="Standard tags (Blur, Duplicate, Dark, Over-exposed) are built-in.\nAdd your own custom tags below.",
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa",
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(0, 8))

        # Standard tags (read-only display)
        f_std = ctk.CTkFrame(container, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#333333")
        f_std.pack(fill="x", pady=(0, 8))

        lbl_std = ctk.CTkLabel(
            f_std,
            text="Built-in Tags:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#888888"
        )
        lbl_std.pack(anchor="w", padx=10, pady=(6, 4))

        f_std_tags = ctk.CTkFrame(f_std, fg_color="transparent")
        f_std_tags.pack(fill="x", padx=10, pady=(0, 6))
        for tag in ["Blur", "Duplicate", "Dark", "Over-exposed"]:
            lbl = ctk.CTkLabel(
                f_std_tags,
                text=f"🏷️ {tag}",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#3a3a3a",
                corner_radius=4,
                width=100,
                height=24
            )
            lbl.pack(side="left", padx=2)

        # Custom tags section
        f_custom = ctk.CTkFrame(container, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#2b9348")
        f_custom.pack(fill="both", expand=True, pady=(0, 4))

        lbl_custom = ctk.CTkLabel(
            f_custom,
            text="Custom Tags:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2b9348"
        )
        lbl_custom.pack(anchor="w", padx=10, pady=(6, 4))

        # Tag list scrollable frame
        self.custom_tags_frame = ctk.CTkScrollableFrame(f_custom, fg_color="transparent", height=120)
        self.custom_tags_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        # Add tag row
        f_add = ctk.CTkFrame(f_custom, fg_color="transparent")
        f_add.pack(fill="x", padx=10, pady=(0, 8))

        self.entry_new_tag = ctk.CTkEntry(f_add, placeholder_text="Enter new tag name...")
        self.entry_new_tag.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_add = ctk.CTkButton(
            f_add,
            text="+ Add Tag",
            width=90,
            height=28,
            fg_color="#2b9348",
            hover_color="#1b4332",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._add_custom_tag
        )
        btn_add.pack(side="right")

        # Load existing custom tags
        self._custom_tags: List[str] = self.db.get_custom_tags()
        self._refresh_custom_tags_list()

    def _refresh_custom_tags_list(self):
        """Rebuild the custom tags list in the Tags tab."""
        for widget in self.custom_tags_frame.winfo_children():
            widget.destroy()

        if not self._custom_tags:
            lbl_empty = ctk.CTkLabel(
                self.custom_tags_frame,
                text="No custom tags defined yet.",
                font=ctk.CTkFont(size=11),
                text_color="#666666"
            )
            lbl_empty.pack(anchor="w", pady=4)
            return

        for tag in self._custom_tags:
            f_row = ctk.CTkFrame(self.custom_tags_frame, fg_color="transparent")
            f_row.pack(fill="x", pady=1)

            lbl = ctk.CTkLabel(
                f_row,
                text=f"🏷️ {tag}",
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w"
            )
            lbl.pack(side="left", padx=(0, 8))

            btn_del = ctk.CTkButton(
                f_row,
                text="✕",
                width=28,
                height=22,
                fg_color="#d90429",
                hover_color="#a4031f",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda t=tag: self._remove_custom_tag(t)
            )
            btn_del.pack(side="right")

    def _add_custom_tag(self):
        val = self.entry_new_tag.get().strip()
        if not val:
            return
        # Don't allow duplicates or built-in tag names
        builtin = {"blur", "duplicate", "dark", "over-exposed"}
        if val.lower() in builtin or val in self._custom_tags:
            return
        self._custom_tags.append(val)
        self.entry_new_tag.delete(0, "end")
        self._refresh_custom_tags_list()

    def _remove_custom_tag(self, tag: str):
        if tag in self._custom_tags:
            self._custom_tags.remove(tag)
            self._refresh_custom_tags_list()

    def _save_settings(self):
        # 1. Output destination subfolders
        p_val = self.entry_picked.get().strip() or "Selected"
        r_val = self.entry_rejected.get().strip() or "_Rejected"
        j_val = self.entry_jpg.get().strip() or "Converted_JPGs"
        self.db.set_picked_folder(p_val)
        self.db.set_rejected_folder(r_val)
        self.db.set_jpg_save_folder(j_val)

        # 2. RAW load scale
        sc_str = self.opt_scale.get()
        scale_val = 0.25
        if "10%" in sc_str: scale_val = 0.10
        elif "15%" in sc_str: scale_val = 0.15
        elif "20%" in sc_str: scale_val = 0.20
        elif "50%" in sc_str: scale_val = 0.50
        elif "100%" in sc_str: scale_val = 1.00
        self.db.set_raw_scale(scale_val)

        # 3. White balance
        wb_str = "auto" if "Auto" in self.opt_wb.get() else "camera"
        self.db.set_white_balance(wb_str)

        # 3b. Eye detection method
        eye_display = {
            "YOLO AI (Pose / Keypoints)": "yolo",
            "Simple Hybrid (Haar + Geometry)": "simple"
        }
        eye_val = eye_display.get(self.opt_eye.get(), "yolo")
        self.db.set_eye_detection_method(eye_val)

        # 4. Stack RAW+JPG & Show Bounding Boxes
        self.db.set_stack_raw_jpg(bool(self.chk_stack.get()))
        self.db.set_show_bounding_boxes(bool(self.chk_bbox.get()))

        # 5. Custom tags
        self.db.set_custom_tags(self._custom_tags)

        if self.on_save:
            self.on_save()

        self.destroy()
