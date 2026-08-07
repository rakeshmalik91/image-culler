from typing import Callable, Optional
import customtkinter as ctk

from ..db_manager import DatabaseManager


class SettingsDialog(ctk.CTkToplevel):
    """
    Unified Application Settings Modal Window.
    Consolidates Output Folder Settings (Picked/Rejected), RAW Load Scale,
    White Balance Mode, and RAW+JPG Stacking into a single clean modal interface.
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
        self.geometry("470x520")
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
        lbl_title.pack(side="top", pady=(15, 10))

        # Main scrollable container
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(side="top", fill="both", expand=True, padx=20, pady=5)

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

        if self.on_save:
            self.on_save()

        self.destroy()
