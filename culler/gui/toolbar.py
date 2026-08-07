from typing import Callable, Dict, Any, Optional
import customtkinter as ctk
from .tooltip import ToolTip


class HeaderToolbar(ctk.CTkFrame):
    """
    Top Navigation and Action Toolbar containing:
    - Open Directory button
    - Filter controls (Segmented flag filter, rating filter, format filter)
    - RAW scale preview selector (10%, 15%, 20%, 25%, 50%, 100%)
    - White balance mode selector (Camera vs Auto)
    - 100% full-resolution preview button
    - Automated Scan for Blur and Scan for Duplicates actions
    - Application preferences settings button
    """

    def __init__(
        self,
        master,
        on_open_dir: Callable[[], None],
        on_open_explorer: Optional[Callable[[], None]] = None,
        on_filter_change: Callable[[str], None] = None,
        on_raw_settings_change: Callable[[], None] = None,
        on_load_100_percent: Callable[[], None] = None,
        on_scan_blur: Callable[[], None] = None,
        on_scan_duplicates: Callable[[], None] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        initial_raw_scale: float = 0.25,
        initial_wb: str = "camera",
        **kwargs
    ):
        super().__init__(master, height=50, corner_radius=0, **kwargs)

        self.on_open_dir = on_open_dir
        self.on_open_explorer = on_open_explorer
        self.on_filter_change = on_filter_change
        self.on_raw_settings_change = on_raw_settings_change
        self.on_load_100_percent = on_load_100_percent
        self.on_scan_blur = on_scan_blur
        self.on_scan_duplicates = on_scan_duplicates
        self.on_open_settings = on_open_settings

        self.initial_raw_scale = initial_raw_scale
        self.initial_wb = initial_wb

        self._build_widgets()

    def _build_widgets(self):
        # Open Directory button
        self.btn_open = ctk.CTkButton(
            self,
            text="📁 Open Directory",
            width=120,
            command=self.on_open_dir,
            fg_color="#1f538d",
            hover_color="#14375e"
        )
        self.btn_open.pack(side="left", padx=4, pady=5)
        ToolTip(self.btn_open, "Select photo folder to cull")

        # Open Folder in Explorer button
        if self.on_open_explorer:
            self.btn_explorer = ctk.CTkButton(
                self,
                text="📂 Open in Explorer",
                width=125,
                command=self.on_open_explorer,
                fg_color="#4a4e69",
                hover_color="#22223b"
            )
            self.btn_explorer.pack(side="left", padx=4, pady=5)
            ToolTip(self.btn_explorer, "Open current photo folder in OS File Explorer / Finder")

        # Filter Segmented Control
        self.lbl_filter = ctk.CTkLabel(self, text="Filter:", font=ctk.CTkFont(weight="bold"))
        self.lbl_filter.pack(side="left", padx=(6, 2))

        self.seg_filter = ctk.CTkSegmentedButton(
            self,
            values=["All", "Pick", "Reject", "Unflagged"],
            command=lambda v: self.on_filter_change("filter")
        )
        self.seg_filter.set("All")
        self.seg_filter.pack(side="left", padx=3)

        # Rating Filter
        self.opt_rating = ctk.CTkOptionMenu(
            self,
            values=["All Stars", "★ 1+", "★ 2+", "★ 3+", "★ 4+", "★ 5"],
            command=lambda v: self.on_filter_change("filter"),
            width=90
        )
        self.opt_rating.set("All Stars")
        self.opt_rating.pack(side="left", padx=3)

        # Format Filter
        self.opt_format = ctk.CTkOptionMenu(
            self,
            values=["All Formats", ".ARW", ".JPG", ".PNG", ".HEIC"],
            command=lambda v: self.on_filter_change("filter"),
            width=95
        )
        self.opt_format.set("All Formats")
        self.opt_format.pack(side="left", padx=3)

        # Tag Filter
        self.opt_tag = ctk.CTkOptionMenu(
            self,
            values=["All Tags", "Blur", "Duplicate", "Dark", "Over-exposed"],
            command=lambda v: self.on_filter_change("filter"),
            width=95
        )
        self.opt_tag.set("All Tags")
        self.opt_tag.pack(side="left", padx=3)
        ToolTip(self.opt_tag, "Filter by Tag (Blur, Duplicate, Dark, Over-exposed, or custom tags)")

        # 100% Full Resolution Button
        self.btn_100 = ctk.CTkButton(
            self,
            text="🔍 Load 100%",
            width=95,
            fg_color="#e63946",
            hover_color="#d62828",
            font=ctk.CTkFont(weight="bold"),
            command=self.on_load_100_percent
        )
        self.btn_100.pack(side="left", padx=(8, 3))
        ToolTip(self.btn_100, "Load 100% Full Resolution for active photo")

        # RAW Load Scale Dropdown (Options: 10%, 15%, 20%, 25%, 50%, 100%)
        self.lbl_raw = ctk.CTkLabel(self, text="RAW:", font=ctk.CTkFont(weight="bold"))
        self.lbl_raw.pack(side="left", padx=(6, 2))

        scale_default_str = "25%"
        if self.initial_raw_scale == 0.10: scale_default_str = "10%"
        elif self.initial_raw_scale == 0.15: scale_default_str = "15%"
        elif self.initial_raw_scale == 0.20: scale_default_str = "20%"
        elif self.initial_raw_scale == 0.50: scale_default_str = "50%"
        elif self.initial_raw_scale == 1.00: scale_default_str = "100%"

        self.opt_raw_scale = ctk.CTkOptionMenu(
            self,
            values=["10%", "15%", "20%", "25%", "50%", "100%"],
            command=lambda v: self.on_raw_settings_change(),
            width=80,
            fg_color="#2b9348",
            button_color="#1b4332",
            button_hover_color="#081c15"
        )
        self.opt_raw_scale.set(scale_default_str)
        self.opt_raw_scale.pack(side="left", padx=3)

        # White Balance Dropdown
        self.lbl_wb = ctk.CTkLabel(self, text="WB:", font=ctk.CTkFont(weight="bold"))
        self.lbl_wb.pack(side="left", padx=(4, 2))

        wb_default_str = "Camera" if self.initial_wb == "camera" else "Auto"
        self.opt_wb = ctk.CTkOptionMenu(
            self,
            values=["Camera", "Auto"],
            command=lambda v: self.on_raw_settings_change(),
            width=85,
            fg_color="#3a86ff",
            button_color="#0077b6",
            button_hover_color="#03045e"
        )
        self.opt_wb.set(wb_default_str)
        self.opt_wb.pack(side="left", padx=3)

        # Scan for Blur Button
        self.btn_scan_blur = ctk.CTkButton(
            self,
            text="🔍 Scan for Blur",
            width=110,
            fg_color="#7b2cbf",
            hover_color="#5a189a",
            font=ctk.CTkFont(weight="bold"),
            command=self.on_scan_blur
        )
        self.btn_scan_blur.pack(side="left", padx=3)
        ToolTip(self.btn_scan_blur, "Scan photoshoot for blurry photos")

        # Scan for Duplicates Button
        self.btn_scan_dups = ctk.CTkButton(
            self,
            text="👯 Scan for Duplicates",
            width=135,
            fg_color="#d97706",
            hover_color="#b45309",
            font=ctk.CTkFont(weight="bold"),
            command=self.on_scan_duplicates
        )
        self.btn_scan_dups.pack(side="left", padx=3)
        ToolTip(self.btn_scan_dups, "Detect duplicate burst shots & keep sharpest")

        # Settings Button
        if self.on_open_settings:
            self.btn_settings = ctk.CTkButton(
                self,
                text="⚙️ Settings",
                width=95,
                fg_color="#1f538d",
                hover_color="#14375e",
                font=ctk.CTkFont(weight="bold"),
                command=self.on_open_settings
            )
            self.btn_settings.pack(side="right", padx=4)
            ToolTip(self.btn_settings, "Open preferences & global settings")

    def get_filter_values(self) -> Dict[str, Any]:
        return {
            "flag": self.seg_filter.get(),
            "rating": self.opt_rating.get(),
            "format": self.opt_format.get(),
            "tag": self.opt_tag.get()
        }

    def update_tag_options(self, available_tags: list):
        """Dynamically update the Tag Filter dropdown choices based on tags present in session."""
        base_tags = ["All Tags", "Blur", "Duplicate", "Dark", "Over-exposed"]
        for t in available_tags:
            if t and t not in base_tags:
                base_tags.append(t)
        cur = self.opt_tag.get()
        self.opt_tag.configure(values=base_tags)
        if cur in base_tags:
            self.opt_tag.set(cur)
        else:
            self.opt_tag.set("All Tags")

    def get_format_filter(self) -> str:
        return self.opt_format.get()

    def get_raw_scale(self) -> float:
        val_str = self.opt_raw_scale.get()
        if "10%" in val_str: return 0.10
        if "15%" in val_str: return 0.15
        if "20%" in val_str: return 0.20
        if "50%" in val_str: return 0.50
        if "100%" in val_str: return 1.00
        return 0.25

    def get_white_balance(self) -> str:
        val_str = self.opt_wb.get()
        if "Auto" in val_str: return "auto"
        return "camera"
