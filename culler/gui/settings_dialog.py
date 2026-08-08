from typing import Callable, List, Optional
import customtkinter as ctk

from ..db_manager import DatabaseManager


class SettingsDialog(ctk.CTkToplevel):
    """
    Unified Application Settings Modal Window with Tabbed Interface.
    Tab 1 (General): Output Folder Settings, RAW Load Scale, White Balance, Stacking, Tools.
    Tab 2 (Tags): Manage custom image tags.
    """

    def __init__(
        self,
        master,
        db: DatabaseManager,
        on_save: Optional[Callable[[], None]] = None,
        on_cleanup_metadata: Optional[Callable[[], None]] = None,
        on_export_manifest: Optional[Callable[[], None]] = None,
        on_sync_exif: Optional[Callable[[], None]] = None
    ):
        super().__init__(master)
        self.db = db
        self.on_save = on_save
        self.on_cleanup_metadata = on_cleanup_metadata
        self.on_export_manifest = on_export_manifest
        self.on_sync_exif = on_sync_exif

        self.title("⚙️ Application Settings")
        self.geometry("520x560")
        self.resizable(False, False)

        # Make modal dialog window
        self.transient(master)
        self.grab_set()

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
        # Header Label
        lbl_title = ctk.CTkLabel(
            self,
            text="⚙️ Global Application Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_title.pack(side="top", pady=(15, 5))

        # Tabview
        self.tabview = ctk.CTkTabview(self, width=480, height=410)
        self.tabview.pack(side="top", fill="both", expand=True, padx=15, pady=5)

        self.tabview.add("General")
        self.tabview.add("Tags")

        self._build_general_tab(self.tabview.tab("General"))
        self._build_tags_tab(self.tabview.tab("Tags"))

        # Bottom Button Bar
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(side="bottom", fill="x", padx=20, pady=15)

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancel",
            width=90,
            fg_color="#4a4e69",
            hover_color="#22223b",
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=4)

        btn_save = ctk.CTkButton(
            btn_bar,
            text="💾 Save Settings",
            width=120,
            fg_color="#2b9348",
            hover_color="#1b4332",
            font=ctk.CTkFont(weight="bold"),
            command=self._save_settings
        )
        btn_save.pack(side="right", padx=4)

    def _build_general_tab(self, tab):
        container = ctk.CTkFrame(tab, fg_color="transparent")
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

        if self.on_cleanup_metadata:
            btn_clean = ctk.CTkButton(
                f_tools,
                text="🧹 Clean Database",
                width=125,
                fg_color="#3a3a3a",
                hover_color="#555555",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self.on_cleanup_metadata
            )
            btn_clean.pack(side="left", padx=2)

        if self.on_export_manifest:
            btn_manifest = ctk.CTkButton(
                f_tools,
                text="📄 Export JSON",
                width=120,
                fg_color="#3a3a3a",
                hover_color="#555555",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self.on_export_manifest
            )
            btn_manifest.pack(side="left", padx=2)

        if self.on_sync_exif:
            btn_sync = ctk.CTkButton(
                f_tools,
                text="🔄 Sync EXIF",
                width=120,
                fg_color="#3a3a3a",
                hover_color="#555555",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self.on_sync_exif
            )
            btn_sync.pack(side="left", padx=2)

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

        # 4. Stack RAW+JPG
        self.db.set_stack_raw_jpg(bool(self.chk_stack.get()))

        # 5. Custom tags
        self.db.set_custom_tags(self._custom_tags)

        if self.on_save:
            self.on_save()

        self.destroy()
