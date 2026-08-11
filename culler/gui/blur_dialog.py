from typing import Callable, Optional, Dict, Any
import customtkinter as ctk

from ..detectors.config_loader import get_blur_methods_config
from .tooltip import ToolTip

METHODS_DATA: Dict[str, Dict[str, Any]] = get_blur_methods_config()


class BlurScanDialog(ctk.CTkToplevel):
    """
    2-Column Sidebar Modal Dialog for selecting blur detection algorithms.
    Lists all 6 methods on the left sidebar with a dynamic details panel on the right.
    """

    def __init__(
        self,
        master,
        on_run: Callable[[float, str, str, Optional[str], Optional[int], str, bool, bool, bool, str], None],
        initial_percentile: float = 15.0,
        initial_method: str = "laplacian",
        initial_flag_action: str = "Reject",
        initial_tag_action: str = "Blur",
        initial_rating_action: str = "None",
        initial_file_type: str = "ARW",
        initial_subject_detect: bool = False,
        initial_safe_blur: bool = True,
        initial_clear_before_scan: bool = True,
        initial_eye_detection_method: str = "auto"
    ):
        super().__init__(master)
        self.on_run = on_run
        self.selected_method = initial_method if initial_method in METHODS_DATA else "laplacian"
        self.selected_file_type = initial_file_type
        self.selected_subject_detect = initial_subject_detect
        self.selected_safe_blur = initial_safe_blur
        self.selected_clear_before_scan = initial_clear_before_scan
        self.selected_eye_detection_method = initial_eye_detection_method
        self.initial_flag_action = initial_flag_action
        self.initial_tag_action = initial_tag_action
        self.initial_rating_action = initial_rating_action

        self.title("🔍 Scan for Blur Options")
        self.geometry("960x680")
        self.resizable(False, False)

        # Make modal dialog window
        self.transient(master)
        try:
            self.grab_set()
        except Exception:
            pass

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

        # Scrollable Method Details Card Box (Height: 215)
        self.card_info = ctk.CTkScrollableFrame(right_panel, corner_radius=6, fg_color="#222222", border_width=1, border_color="#383838", height=215)
        self.card_info.pack(fill="x", pady=(0, 2))

        self.lbl_card_title = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", anchor="w")
        self.lbl_card_title.pack(anchor="w", padx=10, pady=(6, 1))

        self.lbl_card_speed = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color="#3a86ff", anchor="w")
        self.lbl_card_speed.pack(anchor="w", padx=10, pady=1)

        self.lbl_card_how = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#48cae4", justify="left", anchor="w", wraplength=600)
        self.lbl_card_how.pack(anchor="w", padx=10, pady=1)

        self.lbl_card_detects = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#dddddd", justify="left", anchor="w", wraplength=600)
        self.lbl_card_detects.pack(anchor="w", padx=10, pady=1)

        self.lbl_card_pros = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#2b9348", justify="left", anchor="w", wraplength=600)
        self.lbl_card_pros.pack(anchor="w", padx=10, pady=1)

        self.lbl_card_cons = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#d90429", justify="left", anchor="w", wraplength=600)
        self.lbl_card_cons.pack(anchor="w", padx=10, pady=1)

        self.lbl_card_best = ctk.CTkLabel(self.card_info, text="", font=ctk.CTkFont(size=11), text_color="#ffb703", justify="left", anchor="w", wraplength=600)
        self.lbl_card_best.pack(anchor="w", padx=10, pady=(1, 6))

        # Initial details card populate
        self._update_card_info(self.selected_method)

        # Sensitivity Cutoff Section
        lbl_p = ctk.CTkLabel(
            right_panel,
            text="Reject Sensitivity Cutoff (% bottom blurry photos):",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_p.pack(anchor="w", pady=(2, 2))

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
        f_actions.pack(fill="x", pady=(2, 2))

        lbl_act_head = ctk.CTkLabel(
            f_actions,
            text="⚡ Actions to Apply on Detected Items:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffb703"
        )
        lbl_act_head.pack(anchor="w", padx=10, pady=(4, 2))

        f_act_row = ctk.CTkFrame(f_actions, fg_color="transparent")
        f_act_row.pack(fill="x", padx=10, pady=(0, 4))

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

        # File Type & Options Box
        f_options = ctk.CTkFrame(right_panel, corner_radius=6, fg_color="#1a1a1a", border_width=1, border_color="#333333")
        f_options.pack(fill="x", pady=(2, 2))

        f_filetype_row = ctk.CTkFrame(f_options, fg_color="transparent")
        f_filetype_row.pack(fill="x", padx=10, pady=(6, 2))

        lbl_filetype = ctk.CTkLabel(f_filetype_row, text="Scan File Type:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ffb703")
        lbl_filetype.pack(side="left")

        self.combo_filetype = ctk.CTkOptionMenu(
            f_filetype_row,
            values=["All", "ARW", "JPG"],
            width=100,
            height=26,
            dynamic_resizing=False
        )
        self.combo_filetype.set(self.selected_file_type)
        self.combo_filetype.pack(side="left", padx=(8, 0))

        self.chk_subject_var = ctk.BooleanVar(value=self.selected_subject_detect)
        self.chk_subject = ctk.CTkCheckBox(
            f_options,
            text="Highlight Subject Detection (YOLO)",
            variable=self.chk_subject_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_subject.pack(anchor="w", padx=10, pady=(4, 2))

        self.f_eye = ctk.CTkFrame(f_options, fg_color="transparent")
        self.f_eye.pack(fill="x", padx=10, pady=(0, 4))

        lbl_eye = ctk.CTkLabel(self.f_eye, text="Eye Detection Method:", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_eye.pack(side="left", padx=(0, 4))

        self.combo_eye = ctk.CTkOptionMenu(
            self.f_eye,
            values=["YOLO AI (Pose + BBox + Eye ROI)"],
            width=245,
            height=26,
            dynamic_resizing=False
        )
        self.combo_eye.set("YOLO AI (Pose + BBox + Eye ROI)")
        self.combo_eye.pack(side="left")

        self.chk_safe_blur_var = ctk.BooleanVar(value=self.selected_safe_blur)
        self.chk_safe_blur = ctk.CTkCheckBox(
            f_options,
            text="🛡️ Safe Blur Scan (Only reject if a sharper duplicate exists)",
            variable=self.chk_safe_blur_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_safe_blur.pack(anchor="w", padx=10, pady=(0, 2))
        ToolTip(self.chk_safe_blur, "Prevents rejecting unique photos. A blurry photo is only marked for reject if a sharper or non-blurry duplicate exists.")

        self.chk_clear_var = ctk.BooleanVar(value=self.selected_clear_before_scan)
        self.chk_clear = ctk.CTkCheckBox(
            f_options,
            text="Clear flags, tags & bounding boxes before scan",
            variable=self.chk_clear_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            checkbox_width=18,
            checkbox_height=18
        )
        self.chk_clear.pack(anchor="w", padx=10, pady=(0, 6))

        self._update_subject_visibility(self.selected_method)

        # Bottom Button Bar
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

        btn_run = ctk.CTkButton(
            btn_bar,
            text="🔍 Run Blur Scan",
            width=140,
            fg_color="#1f538d",
            hover_color="#14375e",
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
        self._update_subject_visibility(method_key)

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

    @staticmethod
    def _is_yolo_method(method_key: str) -> bool:
        return method_key.lower() in (
            "ai_subject", "yolo_subject", "yolo", "yolo_bird_eye",
            "bird_eye_yolo", "yolo_eye", "bird_subject", "local_var"
        )

    def _update_subject_visibility(self, method_key: str):
        show = self._is_yolo_method(method_key)
        if show:
            if not self.chk_subject.winfo_ismapped():
                self.chk_subject.pack(anchor="w", padx=10, pady=(4, 2))
            if not self.f_eye.winfo_ismapped():
                self.f_eye.pack(fill="x", padx=10, pady=(0, 4))
        else:
            if self.chk_subject.winfo_ismapped():
                self.chk_subject.pack_forget()
                self.chk_subject_var.set(False)
            if self.f_eye.winfo_ismapped():
                self.f_eye.pack_forget()

    def _on_slider_change(self, val: float):
        self.lbl_perc_val.configure(text=f"{int(val)}%")

    def _handle_run(self):
        perc = float(self.slider_perc.get())
        flag_act = self.combo_flag.get()
        tag_act = self.chk_tag_var.get() if self.chk_tag_var.get() else None
        file_type = self.combo_filetype.get()
        subject_detect = self.chk_subject_var.get()
        safe_blur = self.chk_safe_blur_var.get()
        
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
            eye_method = "auto"
            self.on_run(perc, self.selected_method, flag_act, tag_act, rating_act, file_type, subject_detect, safe_blur, self.chk_clear_var.get(), eye_method)

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
