from typing import Callable, Optional, Dict, Any
import customtkinter as ctk

from ..detectors.config_loader import get_blur_methods_config

METHODS_DATA: Dict[str, Dict[str, Any]] = get_blur_methods_config()


class BlurScanDialog(ctk.CTkToplevel):
    """
    2-Column Sidebar Modal Dialog for selecting blur detection algorithms.
    Lists all 6 methods on the left sidebar with a dynamic details panel on the right.
    """

    def __init__(
        self,
        master,
        on_run: Callable[[float, str, str, Optional[str], Optional[int]], None],
        initial_percentile: float = 15.0,
        initial_method: str = "laplacian",
        initial_flag_action: str = "Reject",
        initial_tag_action: str = "Blur",
        initial_rating_action: str = "None"
    ):
        super().__init__(master)
        self.on_run = on_run
        self.selected_method = initial_method if initial_method in METHODS_DATA else "laplacian"
        self.initial_flag_action = initial_flag_action
        self.initial_tag_action = initial_tag_action
        self.initial_rating_action = initial_rating_action

        self.title("🔍 Scan for Blur Options")
        self.geometry("880x620")
        self.resizable(False, False)

        # Make modal dialog window
        self.transient(master)
        self.grab_set()

        self.bind("<Escape>", lambda e: self.destroy())

        self._btn_map: Dict[str, ctk.CTkButton] = {}

        self._build_widgets(initial_percentile)
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

    def _build_widgets(self, initial_percentile: float):
        lbl_title = ctk.CTkLabel(
            self,
            text="🔍 Configure Blur Detection Algorithm",
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

        for idx, (key, info) in enumerate(METHODS_DATA.items()):
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
        # RIGHT MAIN COLUMN: Method Info Card & Sensitivity & Actions
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

        self.lbl_card_best = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#ffb703", justify="left", anchor="w", wraplength=510)
        self.lbl_card_best.pack(anchor="w", padx=12, pady=(2, 10))

        # Initial details card populate
        self._update_card_info(self.selected_method)

        # Sensitivity Cutoff Section
        lbl_p = ctk.CTkLabel(
            right_panel,
            text="Reject Sensitivity Cutoff (% bottom blurry photos):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_p.pack(anchor="w", pady=(3, 2))

        f_perc = ctk.CTkFrame(right_panel, fg_color="transparent")
        f_perc.pack(fill="x", pady=1)

        self.lbl_perc_val = ctk.CTkLabel(f_perc, text=f"{int(initial_percentile)}%", width=45, font=ctk.CTkFont(weight="bold"))
        self.lbl_perc_val.pack(side="right")

        self.slider_perc = ctk.CTkSlider(
            f_perc,
            from_=1,
            to=50,
            number_of_steps=49,
            command=self._on_slider_change
        )
        self.slider_perc.set(initial_percentile)
        self.slider_perc.pack(side="left", fill="x", expand=True)

        # Configurable Actions for Detected Blurry Items
        f_actions = ctk.CTkFrame(right_panel, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#333333")
        f_actions.pack(fill="x", pady=(6, 2))

        lbl_act_head = ctk.CTkLabel(
            f_actions,
            text="⚡ Actions to Apply on Detected Items:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffb703"
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
        self.chk_tag_var = ctk.StringVar(value="Blur" if self.initial_tag_action else "")
        self.chk_tag = ctk.CTkCheckBox(
            f_act_row,
            text="Tag: 'Blur'",
            variable=self.chk_tag_var,
            onvalue="Blur",
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
            text="🔍 Run Blur Scan",
            width=140,
            fg_color="#7b2cbf",
            hover_color="#5a189a",
            font=ctk.CTkFont(weight="bold"),
            command=self._handle_run
        )
        btn_run.pack(side="right", padx=4)

    def _select_method(self, method_key: str):
        self.selected_method = method_key
        for key, btn in self._btn_map.items():
            if key == method_key:
                btn.configure(fg_color="#1f538d", font=ctk.CTkFont(size=11, weight="bold"))
            else:
                btn.configure(fg_color="transparent", font=ctk.CTkFont(size=11, weight="normal"))

        self._update_card_info(method_key)

    def _update_card_info(self, method_key: str):
        info = METHODS_DATA.get(method_key, {})
        keys = list(METHODS_DATA.keys())
        idx = keys.index(method_key) + 1 if method_key in keys else 1
        display_title = f"{idx}. {info.get('title', '')}"
        self.lbl_card_title.configure(text=display_title)
        self.lbl_card_speed.configure(text=info.get("speed", ""))
        self.lbl_card_how.configure(text=info.get("how_it_works", ""))
        self.lbl_card_detects.configure(text=info.get("detects", ""))
        self.lbl_card_pros.configure(text=info.get("pros", ""))
        self.lbl_card_cons.configure(text=info.get("cons", ""))
        self.lbl_card_best.configure(text=info.get("best_for", ""))

    def _on_slider_change(self, val: float):
        self.lbl_perc_val.configure(text=f"{int(val)}%")

    def _handle_run(self):
        perc = float(self.slider_perc.get())
        flag_act = self.combo_flag.get()
        tag_act = self.chk_tag_var.get() if self.chk_tag_var.get() else None
        
        star_str = self.combo_star.get()
        rating_act: Optional[int] = None
        if star_str != "None":
            try:
                rating_act = int(star_str.split()[0])
            except Exception:
                rating_act = None

        try:
            self.grab_release()
        except Exception:
            pass

        try:
            self.withdraw()
        except Exception:
            pass

        if self.on_run:
            self.on_run(perc, self.selected_method, flag_act, tag_act, rating_act)

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
