from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import customtkinter as ctk
from tkinter import messagebox as mb

from ..db_manager import DatabaseManager
from ..logger import log_info, log_error


class MetadataCleanupDialog(ctk.CTkToplevel):
    """
    Embedded hierarchical file explorer modal for inspecting and selectively
    cleaning up saved SQLite metadata records across folders and subdirectories.
    """

    def __init__(
        self,
        master,
        db_manager: DatabaseManager,
        on_cleanup_complete: Optional[Callable[[int, List[str]], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.db = db_manager
        self.on_cleanup_complete = on_cleanup_complete

        self.title("🧹 Database Metadata Explorer & Cleanup")
        self.geometry("720x560")
        self.minsize(640, 480)

        # Make modal dialog window
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self.destroy())

        self._check_vars: Dict[str, ctk.BooleanVar] = {}
        self._folder_summary: Dict[str, Dict[str, int]] = {}

        self._build_widgets()
        self._load_tree_data()

    def _build_widgets(self):
        # Header Box
        header_box = ctk.CTkFrame(self, corner_radius=0, fg_color="#1f538d")
        header_box.pack(side="top", fill="x", padx=0, pady=0)

        lbl_title = ctk.CTkLabel(
            header_box,
            text="🧹 Stored Database Metadata Explorer",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 2))

        lbl_sub = ctk.CTkLabel(
            header_box,
            text="Hierarchical view of all folder trees with saved flags, ratings, & tags in workspace database",
            font=ctk.CTkFont(size=11),
            text_color="#d0d0d0"
        )
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 10))

        # Toolbar Box (Select All, Deselect All, Stats)
        tool_box = ctk.CTkFrame(self, fg_color="transparent")
        tool_box.pack(side="top", fill="x", padx=15, pady=8)

        btn_sel_all = ctk.CTkButton(
            tool_box,
            text="✓ Select All",
            width=90,
            height=26,
            fg_color="#333333",
            hover_color="#555555",
            command=self._select_all
        )
        btn_sel_all.pack(side="left", padx=(0, 5))

        btn_desel_all = ctk.CTkButton(
            tool_box,
            text="✗ Deselect All",
            width=90,
            height=26,
            fg_color="#333333",
            hover_color="#555555",
            command=self._deselect_all
        )
        btn_desel_all.pack(side="left", padx=5)

        self.lbl_stats = ctk.CTkLabel(
            tool_box,
            text="Loading stored database records...",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_stats.pack(side="right", padx=5)

        # Embedded Folder Tree Container (Scrollable)
        self.tree_scroll = ctk.CTkScrollableFrame(self, label_text="")
        self.tree_scroll.pack(side="top", fill="both", expand=True, padx=15, pady=5)

        # Bottom Action Bar
        action_bar = ctk.CTkFrame(self, height=50, corner_radius=0)
        action_bar.pack(side="bottom", fill="x")

        btn_clean_sel = ctk.CTkButton(
            action_bar,
            text="🧹 Clean Selected Folders",
            fg_color="#5c0612",
            hover_color="#d90429",
            font=ctk.CTkFont(weight="bold"),
            command=self._clean_selected
        )
        btn_clean_sel.pack(side="left", padx=15, pady=10)

        btn_clean_all = ctk.CTkButton(
            action_bar,
            text="🗑️ Purge Entire Database",
            fg_color="#5c0612",
            hover_color="#d90429",
            font=ctk.CTkFont(weight="bold"),
            command=self._clean_entire_db
        )
        btn_clean_all.pack(side="left", padx=5, pady=10)

        btn_close = ctk.CTkButton(
            action_bar,
            text="Close",
            width=80,
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.destroy
        )
        btn_close.pack(side="right", padx=15, pady=10)

    def _load_tree_data(self):
        for w in self.tree_scroll.winfo_children():
            w.destroy()
        self._check_vars.clear()

        self._folder_summary = self.db.get_stored_folders_summary()

        if not self._folder_summary:
            lbl_empty = ctk.CTkLabel(
                self.tree_scroll,
                text="📁 No metadata records stored in database.",
                font=ctk.CTkFont(size=13, weight="bold")
            )
            lbl_empty.pack(expand=True, pady=40)
            self.lbl_stats.configure(text="Database: 0 Folders, 0 Records")
            return

        total_records = sum(stats["total"] for stats in self._folder_summary.values())
        self.lbl_stats.configure(
            text=f"Database: {len(self._folder_summary)} Folders, {total_records} Image Records"
        )

        sorted_folders = sorted(self._folder_summary.keys(), key=lambda x: x.lower())

        for folder_path in sorted_folders:
            stats = self._folder_summary[folder_path]

            row_frame = ctk.CTkFrame(self.tree_scroll, fg_color="#2b2b2b", corner_radius=4)
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
            self.tree_scroll.update_idletasks()
        except Exception:
            pass

    def _select_all(self):
        for var in self._check_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self._check_vars.values():
            var.set(False)

    def _clean_selected(self):
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
            log_info(f"MetadataCleanupDialog: Cleaned up {deleted_count} records across {len(selected)} folders.")
            mb.showinfo("Cleanup Complete", f"Successfully cleaned up {deleted_count} database records!")
            
            if self.on_cleanup_complete:
                self.on_cleanup_complete(deleted_count, selected)

            self._load_tree_data()

    def _clean_entire_db(self):
        ans = mb.askyesno(
            "PURGE ENTIRE DATABASE",
            "WARNING: This will permanently delete ALL stored culling records, ratings, and tags from workspace database!\n\n"
            "Are you sure you want to purge the entire database?",
            icon="warning"
        )
        if ans:
            deleted_count = self.db.cleanup_entire_database()
            log_info(f"MetadataCleanupDialog: Purged entire database ({deleted_count} records deleted).")
            mb.showinfo("Database Purged", f"Successfully purged {deleted_count} total database records!")

            if self.on_cleanup_complete:
                self.on_cleanup_complete(deleted_count, list(self._folder_summary.keys()))

            self._load_tree_data()
