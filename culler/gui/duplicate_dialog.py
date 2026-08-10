from typing import Callable, Optional, Dict, Any
import customtkinter as ctk

from ..detectors.config_loader import get_duplicate_methods_config

DUP_METHODS_DATA: Dict[str, Dict[str, Any]] = get_duplicate_methods_config()


class DuplicateScanDialog(ctk.CTkToplevel):
    """
    2-Column Sidebar Modal Dialog for selecting duplicate image detection algorithms.
    Lists methods on the left sidebar with a dynamic details panel on the right.
    """

    def __init__(
        self,
        master,
        on_run: Callable[[float, str, str, Optional[str], Optional[int], str, str, Optional[str], Optional[int], str], None],
        initial_threshold: float = 6.0,
        initial_method: str = "dhash",
        initial_flag_action: str = "Reject",
        initial_tag_action: str = "Duplicate",
        initial_rating_action: str = "None",
        initial_file_type: str = "ARW"
    ):
        super().__init__(master)
        self.on_run = on_run
        self.selected_method = initial_method if initial_method in DUP_METHODS_DATA else "dhash"
        self.selected_file_type = initial_file_type
        self.initial_flag_action = initial_flag_action
        self.initial_tag_action = initial_tag_action
        self.initial_rating_action = initial_rating_action

        self.title("👯 Scan for Duplicates Options")
        self.geometry("880x620")
        self.resizable(False, False)

        # Make modal dialog window
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self.destroy())

        self._btn_map: Dict[str, ctk.CTkButton] = {}

        self._build_widgets(initial_threshold)
        self.after(10, self._center_window)

    def _center_window(self):
        try:
            if not self.winfo_exists():
                return
            self.update_idletasks()
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

    def _build_widgets(self, initial_threshold: float):
        lbl_title = ctk.CTkLabel(
            self,
            text="👯 Configure Duplicate Image Detection Algorithm",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_title.pack(side="top", pady=(12, 6))

        # Main 2-Column Split Container
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(side="top", fill="both", expand=True, padx=15, pady=5)

        # ----------------------------------------------------
        # LEFT SIDEBAR COLUMN: Method List
        # ----------------------------------------------------
        sidebar = ctk.CTkFrame(main_box, width=310, corner_radius=6, fg_color="#1e1e1e")
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        lbl_side = ctk.CTkLabel(
            sidebar,
            text="Select Algorithm:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_side.pack(anchor="w", padx=10, pady=(10, 6))

        for idx, (key, info) in enumerate(DUP_METHODS_DATA.items()):
            display_title = f"{idx + 1}. {info['title']}"
            btn = ctk.CTkButton(
                sidebar,
                text=display_title,
                anchor="w",
                height=38,
                fg_color="#1f538d" if key == self.selected_method else "transparent",
                hover_color="#333333",
                font=ctk.CTkFont(size=11, weight="bold" if key == self.selected_method else "normal"),
                command=lambda k=key: self._select_method(k)
            )
            btn.pack(fill="x", padx=4, pady=2)
            self._btn_map[key] = btn

        # ----------------------------------------------------
        # RIGHT MAIN COLUMN: Method Info Card & Threshold & Actions
        # ----------------------------------------------------
        right_panel = ctk.CTkFrame(main_box, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True)

        # Scrollable Method Details Card Box
        self.card_info = ctk.CTkScrollableFrame(right_panel, corner_radius=6, fg_color="#222222", border_width=1, border_color="#383838", height=220)
        self.card_info.pack(fill="both", expand=True, pady=(0, 6))

        self.lbl_card_title = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color="#ffffff", anchor="w")
        self.lbl_card_title.pack(anchor="w", padx=12, pady=(10, 2))

        self.lbl_card_speed = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color="#3a86ff", anchor="w")
        self.lbl_card_speed.pack(anchor="w", padx=12, pady=2)

        self.lbl_card_how = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#48cae4", justify="left", anchor="w", wraplength=510)
        self.lbl_card_how.pack(anchor="w", padx=12, pady=2)

        self.lbl_card_detects = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#dddddd", justify="left", anchor="w", wraplength=510)
        self.lbl_card_detects.pack(anchor="w", padx=12, pady=2)

        self.lbl_card_pros = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#2b9348", justify="left", anchor="w", wraplength=510)
        self.lbl_card_pros.pack(anchor="w", padx=12, pady=2)

        self.lbl_card_cons = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#d90429", justify="left", anchor="w", wraplength=510)
        self.lbl_card_cons.pack(anchor="w", padx=12, pady=2)

        self.lbl_card_guide = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#a855f7", justify="left", anchor="w", wraplength=510)
        self.lbl_card_guide.pack(anchor="w", padx=12, pady=2)

        self.lbl_card_best = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#ffb703", justify="left", anchor="w", wraplength=510)
        self.lbl_card_best.pack(anchor="w", padx=12, pady=(2, 10))

        # Threshold Section
        self.lbl_thresh_title = ctk.CTkLabel(
            right_panel,
            text="Similarity Threshold:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_thresh_title.pack(anchor="w", pady=(3, 2))

        self.f_thresh = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.f_thresh.pack(fill="x", pady=1)

        self.lbl_thresh_val = ctk.CTkLabel(self.f_thresh, text="6 bits", width=55, font=ctk.CTkFont(weight="bold"))
        self.lbl_thresh_val.pack(side="right")

        self.slider_thresh = ctk.CTkSlider(
            self.f_thresh,
            from_=1,
            to=12,
            number_of_steps=11,
            command=self._on_slider_change
        )
        self.slider_thresh.set(initial_threshold)
        self.slider_thresh.pack(side="left", fill="x", expand=True)

        # Configurable Actions for Keeper (Sharpest Photo in Each Group)
        f_keeper = ctk.CTkFrame(right_panel, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#2b9348")
        f_keeper.pack(fill="x", pady=(6, 2))

        lbl_keeper_head = ctk.CTkLabel(
            f_keeper,
            text="🏆 Keeper Actions (sharpest photo in each group):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2b9348"
        )
        lbl_keeper_head.pack(anchor="w", padx=10, pady=(6, 4))

        # Keeper Selection Method
        f_keeper_method = ctk.CTkFrame(f_keeper, fg_color="transparent")
        f_keeper_method.pack(fill="x", padx=10, pady=(0, 4))

        lbl_kmethod = ctk.CTkLabel(f_keeper_method, text="Select Best By:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_kmethod.pack(side="left", padx=(0, 4))

        self.combo_keeper_method = ctk.CTkOptionMenu(
            f_keeper_method,
            values=["Sharpest (Default)", "AI Eye Focus (Bird/Wildlife)", "Largest File", "Newest", "Oldest"],
            width=220,
            height=26,
            dynamic_resizing=False
        )
        self.combo_keeper_method.set("Sharpest (Default)")
        self.combo_keeper_method.pack(side="left")

        f_keeper_row = ctk.CTkFrame(f_keeper, fg_color="transparent")
        f_keeper_row.pack(fill="x", padx=10, pady=(0, 6))

        # Keeper Flag Dropdown
        lbl_kflag = ctk.CTkLabel(f_keeper_row, text="Flag:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_kflag.pack(side="left", padx=(0, 4))

        self.combo_keeper_flag = ctk.CTkOptionMenu(
            f_keeper_row,
            values=["Pick", "Unflagged", "None"],
            width=95,
            height=26,
            dynamic_resizing=False
        )
        self.combo_keeper_flag.set("Pick")
        self.combo_keeper_flag.pack(side="left", padx=(0, 14))

        # Keeper Tag Checkbox
        self.chk_keeper_tag_var = ctk.StringVar(value="Duplicate")
        self.chk_keeper_tag = ctk.CTkCheckBox(
            f_keeper_row,
            text="Tag: 'Duplicate'",
            variable=self.chk_keeper_tag_var,
            onvalue="Duplicate",
            offvalue="",
            font=ctk.CTkFont(size=11, weight="bold"),
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_keeper_tag.pack(side="left", padx=(0, 14))

        # Keeper Star Rating Dropdown
        lbl_kstar = ctk.CTkLabel(f_keeper_row, text="Star:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_kstar.pack(side="left", padx=(0, 4))

        self.combo_keeper_star = ctk.CTkOptionMenu(
            f_keeper_row,
            values=["None", "0 Stars", "1 Star", "2 Stars", "3 Stars", "4 Stars", "5 Stars"],
            width=105,
            height=26,
            dynamic_resizing=False
        )
        self.combo_keeper_star.set("None")
        self.combo_keeper_star.pack(side="left")

        # Configurable Actions for Detected Duplicate Items
        f_actions = ctk.CTkFrame(right_panel, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#333333")
        f_actions.pack(fill="x", pady=(4, 2))

        lbl_act_head = ctk.CTkLabel(
            f_actions,
            text="🗑️ Duplicate Actions (lower quality copies):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#d90429"
        )
        lbl_act_head.pack(anchor="w", padx=10, pady=(6, 4))

        f_act_row = ctk.CTkFrame(f_actions, fg_color="transparent")
        f_act_row.pack(fill="x", padx=10, pady=(0, 6))

        # Flag Dropdown
        lbl_flag = ctk.CTkLabel(f_act_row, text="Flag:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_flag.pack(side="left", padx=(0, 4))

        self.combo_flag = ctk.CTkOptionMenu(
            f_act_row,
            values=["Reject", "Pick", "Unflagged", "None"],
            width=95,
            height=26,
            dynamic_resizing=False
        )
        self.combo_flag.set(self.initial_flag_action)
        self.combo_flag.pack(side="left", padx=(0, 14))

        # Tag Checkbox
        self.chk_tag_var = ctk.StringVar(value="Duplicate" if self.initial_tag_action else "")
        self.chk_tag = ctk.CTkCheckBox(
            f_act_row,
            text="Tag: 'Duplicate'",
            variable=self.chk_tag_var,
            onvalue="Duplicate",
            offvalue="",
            font=ctk.CTkFont(size=11, weight="bold"),
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_tag.pack(side="left", padx=(0, 14))

        # Star Rating Dropdown
        lbl_star = ctk.CTkLabel(f_act_row, text="Star:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_star.pack(side="left", padx=(0, 4))

        self.combo_star = ctk.CTkOptionMenu(
            f_act_row,
            values=["None", "0 Stars", "1 Star", "2 Stars", "3 Stars", "4 Stars", "5 Stars"],
            width=105,
            height=26,
            dynamic_resizing=False
        )
        self.combo_star.set(self.initial_rating_action)
        self.combo_star.pack(side="left")

        # File Type Filter
        f_filetype = ctk.CTkFrame(right_panel, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#333333")
        f_filetype.pack(fill="x", pady=(6, 2))

        lbl_filetype = ctk.CTkLabel(f_filetype, text="Scan File Type:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ffb703")
        lbl_filetype.pack(anchor="w", padx=10, pady=(6, 4))

        f_filetype_row = ctk.CTkFrame(f_filetype, fg_color="transparent")
        f_filetype_row.pack(fill="x", padx=10, pady=(0, 6))

        self.combo_filetype = ctk.CTkOptionMenu(
            f_filetype_row,
            values=["All", "ARW", "JPG"],
            width=120,
            height=26,
            dynamic_resizing=False
        )
        self.combo_filetype.set(self.selected_file_type)
        self.combo_filetype.pack(side="left")

        # Bottom Button Bar
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(side="bottom", fill="x", padx=20, pady=12)

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancel",
            width=90,
            fg_color="#4a4e69",
            hover_color="#22223b",
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=4)

        btn_run = ctk.CTkButton(
            btn_bar,
            text="👯 Run Duplicate Scan",
            width=160,
            fg_color="#d97706",
            hover_color="#b45309",
            font=ctk.CTkFont(weight="bold"),
            command=self._handle_run
        )
        btn_run.pack(side="right", padx=4)

        # Initial details card & threshold populate
        self._update_card_info(self.selected_method)

    def _select_method(self, method_key: str):
        self.selected_method = method_key
        for key, btn in self._btn_map.items():
            if key == method_key:
                btn.configure(fg_color="#1f538d", font=ctk.CTkFont(size=11, weight="bold"))
            else:
                btn.configure(fg_color="transparent", font=ctk.CTkFont(size=11, weight="normal"))

        self._update_card_info(method_key)

    def _update_card_info(self, method_key: str):
        info = DUP_METHODS_DATA.get(method_key, {})
        keys = list(DUP_METHODS_DATA.keys())
        idx = keys.index(method_key) + 1 if method_key in keys else 1
        display_title = f"{idx}. {info.get('title', '')}"

        self.lbl_card_title.configure(text=display_title)
        self.lbl_card_speed.configure(text=info.get("speed", ""))
        self.lbl_card_how.configure(text=info.get("how_it_works", ""))
        self.lbl_card_detects.configure(text=info.get("detects", ""))
        self.lbl_card_pros.configure(text=info.get("pros", ""))
        self.lbl_card_cons.configure(text=info.get("cons", ""))
        self.lbl_card_guide.configure(text=info.get("thresh_guide", ""))
        self.lbl_card_best.configure(text=info.get("best_for", ""))

        if info.get("has_threshold"):
            self.lbl_thresh_title.configure(text=info["thresh_label"])
            min_v = info["min_val"]
            max_v = info["max_val"]
            def_v = info["default_val"]
            unit = info["val_unit"]

            self.slider_thresh.configure(from_=min_v, to=max_v, number_of_steps=int(max_v - min_v))
            self.slider_thresh.set(def_v)
            self.lbl_thresh_val.configure(text=f"{def_v:.1f}{unit}" if isinstance(def_v, float) else f"{int(def_v)}{unit}")
            self.f_thresh.pack(fill="x", pady=2)
        else:
            self.lbl_thresh_title.configure(text="Threshold: Exact 100% byte match (No slider needed)")
            self.f_thresh.pack_forget()

    def _on_slider_change(self, val: float):
        info = DUP_METHODS_DATA.get(self.selected_method, {})
        unit = info.get("val_unit", "")
        if unit == "s":
            self.lbl_thresh_val.configure(text=f"{val:.1f}s")
        else:
            self.lbl_thresh_val.configure(text=f"{int(val)} bits")

    def _handle_run(self):
        thresh = float(self.slider_thresh.get())
        flag_act = self.combo_flag.get()
        tag_act = self.chk_tag_var.get() if self.chk_tag_var.get() else None
        file_type = self.combo_filetype.get()
        
        star_str = self.combo_star.get()
        rating_act: Optional[int] = None
        if star_str != "None":
            try:
                rating_act = int(star_str.split()[0])
            except Exception:
                rating_act = None

        keeper_flag = self.combo_keeper_flag.get()
        keeper_tag = self.chk_keeper_tag_var.get() if self.chk_keeper_tag_var.get() else None

        keeper_star_str = self.combo_keeper_star.get()
        keeper_rating: Optional[int] = None
        if keeper_star_str != "None":
            try:
                keeper_rating = int(keeper_star_str.split()[0])
            except Exception:
                keeper_rating = None

        # Map keeper method display to key
        method_display = self.combo_keeper_method.get()
        keeper_method_map = {
            "Sharpest (Default)": "sharpest",
            "AI Eye Focus (Bird/Wildlife)": "ai_eye_focus",
            "Largest File": "largest",
            "Newest": "newest",
            "Oldest": "oldest",
        }
        keeper_method = keeper_method_map.get(method_display, "sharpest")

        try:
            self.grab_release()
        except Exception:
            pass

        try:
            self.withdraw()
        except Exception:
            pass

        if self.on_run:
            self.on_run(thresh, self.selected_method, flag_act, tag_act, rating_act, keeper_flag, keeper_tag, keeper_rating, keeper_method, file_type)

        try:
            if self.master:
                self.master.after(50, self._safe_destroy)
            else:
                self.after(50, self._safe_destroy)
        except Exception:
            pass

    def _safe_destroy(self):
        try:
            self.destroy()
        except Exception:
            pass
