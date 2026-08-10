from typing import Optional, Tuple
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk


class ImageCanvasViewer(ctk.CTkFrame):
    """
    Center viewport wrapping a Tkinter Canvas with interactive zoom (mouse wheel), pan (drag),
    and a prominent centered progress bar overlay for directory scanning.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=5, **kwargs)

        self.zoom_level: float = 1.0
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        self.drag_start_x: float = 0.0
        self.drag_start_y: float = 0.0

        self.current_pil_img: Optional[Image.Image] = None
        self.current_tk_img: Optional[ImageTk.PhotoImage] = None
        self.canvas_img_id: Optional[int] = None
        self._last_rendered_state: Optional[Tuple[float, float, float]] = None
        self._zoom_timer: Optional[str] = None

        # Crop Mode Variables
        self.is_cropping: bool = False
        self.crop_start_x: float = 0.0
        self.crop_start_y: float = 0.0
        self.crop_box: Optional[Tuple[float, float, float, float]] = None
        self.crop_rect_id: Optional[int] = None
        self.on_confirm_crop_cb = None

        # Subject Detection Box
        self._detection_box: Optional[Tuple[float, float, float, float]] = None
        self._detection_rect_id: Optional[int] = None

        self.canvas = tk.Canvas(self, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_release)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw(force_resize=True))

        # Centered Progress Overlay
        self.overlay_frame: Optional[ctk.CTkFrame] = None
        self._create_loading_overlay()

        # Top Crop Toolbar Overlay
        self.crop_toolbar: Optional[ctk.CTkFrame] = None
        self._create_crop_toolbar()

    def _create_loading_overlay(self):
        self.overlay_frame = ctk.CTkFrame(
            self,
            fg_color="#1e1e24",
            corner_radius=12,
            border_width=2,
            border_color="#1f538d"
        )

        self.lbl_loading_title = ctk.CTkLabel(
            self.overlay_frame,
            text="📂 Loading Directory & EXIF Metadata...",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=32
        )
        self.lbl_loading_title.pack(padx=30, pady=(20, 8))

        self.loading_progress = ctk.CTkProgressBar(
            self.overlay_frame,
            width=440,
            height=20,
            progress_color="#1f538d"
        )
        self.loading_progress.pack(padx=30, pady=10)
        self.loading_progress.set(0)

        self.lbl_loading_status = ctk.CTkLabel(
            self.overlay_frame,
            text="Initializing scan...",
            font=ctk.CTkFont(size=13),
            text_color="#a0a0a0",
            height=35
        )
        self.lbl_loading_status.pack(padx=30, pady=(5, 20))

        # Initially hidden until loading starts
        self.overlay_frame.place_forget()

    def show_loading(self, title: str = "📂 Loading Directory & EXIF Metadata..."):
        self.lbl_loading_title.configure(text=title)
        self.loading_progress.set(0.0)
        self.lbl_loading_status.configure(text="Reading files...")
        self.overlay_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.overlay_frame.lift()

    def update_loading_progress(self, current: int, total: int, fraction: float):
        self.loading_progress.set(fraction)
        pct = int(fraction * 100)
        self.lbl_loading_status.configure(text=f"Reading EXIF metadata: {current} / {total} ({pct}%)")

    def hide_loading(self):
        self.overlay_frame.place_forget()

    def set_image(self, pil_img: Optional[Image.Image], preserve_zoom: bool = True):
        self.hide_loading()
        self.current_pil_img = pil_img
        if not preserve_zoom:
            self.zoom_level = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0
        self.clear_detection_box()
        self.redraw(force_resize=True)

    def clear(self):
        """Clear canvas viewer image (e.g. when 0 items match filter)."""
        self.set_image(None, preserve_zoom=False)

    def set_detection_box(self, box: Optional[Tuple[float, float, float, float]]):
        self._detection_box = box
        self._draw_detection_rect()

    def clear_detection_box(self):
        self._detection_box = None
        if self._detection_rect_id is not None:
            self.canvas.delete(self._detection_rect_id)
            self._detection_rect_id = None

    def _draw_detection_rect(self):
        if self._detection_rect_id is not None:
            self.canvas.delete(self._detection_rect_id)
            self._detection_rect_id = None

        if not self._detection_box or self.current_pil_img is None:
            return

        nx1, ny1, nx2, ny2 = self._detection_box
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 10 or canvas_h <= 10:
            return

        img_w, img_h = self.current_pil_img.size
        ratio = min(canvas_w / img_w, canvas_h / img_h) * self.zoom_level
        new_w = max(10, int(img_w * ratio))
        new_h = max(10, int(img_h * ratio))
        center_x = (canvas_w / 2) + self.pan_x
        center_y = (canvas_h / 2) + self.pan_y

        x1 = nx1 * img_w
        y1 = ny1 * img_h
        x2 = nx2 * img_w
        y2 = ny2 * img_h

        cx1 = center_x - (new_w / 2) + (x1 * ratio)
        cy1 = center_y - (new_h / 2) + (y1 * ratio)
        cx2 = center_x - (new_w / 2) + (x2 * ratio)
        cy2 = center_y - (new_h / 2) + (y2 * ratio)

        self._detection_rect_id = self.canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline="#00ff00", width=3
        )

    def redraw(self, force_resize: bool = False, fast_mode: bool = False):
        if self.current_pil_img is None:
            self.canvas.delete("all")
            self.canvas_img_id = None
            self._last_rendered_state = None
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w <= 10 or canvas_h <= 10:
            return

        img_w, img_h = self.current_pil_img.size
        ratio = min(canvas_w / img_w, canvas_h / img_h) * self.zoom_level

        new_w = max(10, int(img_w * ratio))
        new_h = max(10, int(img_h * ratio))

        center_x = (canvas_w / 2) + self.pan_x
        center_y = (canvas_h / 2) + self.pan_y

        state_key = (round(self.zoom_level, 3), new_w, new_h)

        # FAST PATH: If image size hasn't changed (e.g. simple mouse drag panning),
        # update canvas item coordinates directly with hardware compositor (0ms CPU cost!)
        if not force_resize and self._last_rendered_state == state_key and self.canvas_img_id is not None:
            self.canvas.coords(self.canvas_img_id, center_x, center_y)
            self._draw_detection_rect()
            return

        # Standard full-image resize with fast BILINEAR / NEAREST resampling
        # Cap max render dimensions to 3500px so PIL resize is sub-millisecond
        max_dim = 3500
        if new_w > max_dim or new_h > max_dim:
            scale_down = min(max_dim / new_w, max_dim / new_h)
            new_w = int(new_w * scale_down)
            new_h = int(new_h * scale_down)

        resample = Image.Resampling.NEAREST if fast_mode else Image.Resampling.BILINEAR
        resized = self.current_pil_img.resize((new_w, new_h), resample)
        self.current_tk_img = ImageTk.PhotoImage(resized)
        self._last_rendered_state = state_key

        if self.canvas_img_id is not None and self.canvas.type(self.canvas_img_id):
            self.canvas.itemconfig(self.canvas_img_id, image=self.current_tk_img)
            self.canvas.coords(self.canvas_img_id, center_x, center_y)
        else:
            self.canvas.delete("all")
            self.canvas_img_id = self.canvas.create_image(center_x, center_y, anchor="center", image=self.current_tk_img)

        self._draw_detection_rect()

    def _on_drag_start(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def _on_drag_motion(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.pan_x += dx
        self.pan_y += dy
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        # Hardware Coords Movement - 60+ FPS Silky Smooth Dragging
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        center_x = (canvas_w / 2) + self.pan_x
        center_y = (canvas_h / 2) + self.pan_y
        if self.canvas_img_id is not None:
            self.canvas.coords(self.canvas_img_id, center_x, center_y)
        else:
            self.redraw(force_resize=False)

    def _create_crop_toolbar(self):
        self.crop_toolbar = ctk.CTkFrame(
            self,
            fg_color="#1a1a24",
            corner_radius=8,
            border_width=2,
            border_color="#ffb703",
            height=44
        )
        self.crop_toolbar.pack_propagate(False)

        lbl_title = ctk.CTkLabel(
            self.crop_toolbar,
            text="✂️ MANUAL CROP MODE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffb703"
        )
        lbl_title.pack(side="left", padx=(12, 10))

        lbl_aspect = ctk.CTkLabel(
            self.crop_toolbar,
            text="Aspect Ratio:",
            font=ctk.CTkFont(size=11)
        )
        lbl_aspect.pack(side="left", padx=(5, 2))

        self.opt_aspect = ctk.CTkOptionMenu(
            self.crop_toolbar,
            values=["Free", "1:1 Square", "16:9 Widescreen", "4:3 Standard", "3:2 DSLR", "9:16 Story/Reel", "4:5 Portrait"],
            width=130,
            command=self._on_aspect_changed
        )
        self.opt_aspect.pack(side="left", padx=5)

        self.btn_confirm_crop = ctk.CTkButton(
            self.crop_toolbar,
            text="✔️ Save Crop (Enter / Ctrl+S)",
            fg_color="#2b9348",
            hover_color="#1b4332",
            width=180,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_confirm_crop
        )
        self.btn_confirm_crop.pack(side="left", padx=5)

        self.btn_cancel_crop = ctk.CTkButton(
            self.crop_toolbar,
            text="❌ Cancel (Esc)",
            fg_color="#d90429",
            hover_color="#8d99ae",
            width=100,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.exit_crop_mode
        )
        self.btn_cancel_crop.pack(side="left", padx=5)

        self.crop_toolbar.place_forget()

    def enter_crop_mode(self, on_confirm_callback=None):
        if self.current_pil_img is None:
            return

        self.is_cropping = True
        self.on_confirm_crop_cb = on_confirm_callback
        self.crop_toolbar.place(relx=0.5, rely=0.05, anchor="n")
        self.crop_toolbar.lift()

        # Default crop box to 80% center
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        margin_x = canvas_w * 0.15
        margin_y = canvas_h * 0.15
        self.crop_box = (margin_x, margin_y, canvas_w - margin_x, canvas_h - margin_y)
        self._update_crop_rect_draw()

    def exit_crop_mode(self):
        self.is_cropping = False
        self.crop_toolbar.place_forget()
        if self.crop_rect_id is not None:
            self.canvas.delete(self.crop_rect_id)
            self.crop_rect_id = None
        self.crop_box = None

    def _on_aspect_changed(self, choice: str):
        if self.crop_box:
            x1, y1, x2, y2 = self.crop_box
            w = abs(x2 - x1)
            new_h = self._calc_aspect_height(w, choice)
            if new_h:
                cy = (y1 + y2) / 2.0
                self.crop_box = (x1, cy - (new_h / 2.0), x2, cy + (new_h / 2.0))
                self._update_crop_rect_draw()

    def _calc_aspect_height(self, width: float, choice: str) -> Optional[float]:
        ratios = {
            "1:1 Square": 1.0,
            "16:9 Widescreen": 16.0 / 9.0,
            "4:3 Standard": 4.0 / 3.0,
            "3:2 DSLR": 3.0 / 2.0,
            "9:16 Story/Reel": 9.0 / 16.0,
            "4:5 Portrait": 4.0 / 5.0,
        }
        if choice in ratios:
            return width / ratios[choice]
        return None

    def _update_crop_rect_draw(self):
        if not self.crop_box:
            return
        x1, y1, x2, y2 = self.crop_box
        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)

        if self.crop_rect_id is not None:
            self.canvas.coords(self.crop_rect_id, left, top, right, bottom)
        else:
            self.crop_rect_id = self.canvas.create_rectangle(
                left, top, right, bottom,
                outline="#ffb703", width=3, dash=(6, 4)
            )

    def _on_drag_start(self, event):
        if self.is_cropping:
            self.crop_start_x = event.x
            self.crop_start_y = event.y
            self.crop_box = (event.x, event.y, event.x, event.y)
            self._update_crop_rect_draw()
        else:
            self.drag_start_x = event.x
            self.drag_start_y = event.y

    def _on_drag_motion(self, event):
        if self.is_cropping:
            x1 = self.crop_start_x
            y1 = self.crop_start_y
            x2 = event.x
            y2 = event.y

            w = abs(x2 - x1)
            is_shift_held = bool(event.state & 0x0001) or bool(event.state & 0x0004)

            if is_shift_held:
                target_h = w
            else:
                aspect_choice = self.opt_aspect.get()
                target_h = self._calc_aspect_height(w, aspect_choice)

            if target_h:
                y2 = y1 + target_h if y2 >= y1 else y1 - target_h

            self.crop_box = (x1, y1, x2, y2)
            self._update_crop_rect_draw()
        else:
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            self.pan_x += dx
            self.pan_y += dy
            self.drag_start_x = event.x
            self.drag_start_y = event.y

            # Hardware Coords Movement - 60+ FPS Silky Smooth Dragging
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            center_x = (canvas_w / 2) + self.pan_x
            center_y = (canvas_h / 2) + self.pan_y
            if self.canvas_img_id is not None:
                self.canvas.coords(self.canvas_img_id, center_x, center_y)
            else:
                self.redraw(force_resize=False)

    def _on_drag_release(self, event):
        if self.is_cropping and self.crop_box:
            x1, y1, x2, y2 = self.crop_box
            if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
                # If tiny click, restore 80% default box
                canvas_w = self.canvas.winfo_width()
                canvas_h = self.canvas.winfo_height()
                mx = canvas_w * 0.15
                my = canvas_h * 0.15
                self.crop_box = (mx, my, canvas_w - mx, canvas_h - my)
                self._update_crop_rect_draw()

    def _on_confirm_crop(self):
        if not self.crop_box or self.current_pil_img is None:
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        img_w, img_h = self.current_pil_img.size
        ratio = min(canvas_w / img_w, canvas_h / img_h) * self.zoom_level

        new_w = max(10, int(img_w * ratio))
        new_h = max(10, int(img_h * ratio))

        # Max dimension scaling check
        max_dim = 3500
        if new_w > max_dim or new_h > max_dim:
            scale_down = min(max_dim / new_w, max_dim / new_h)
            new_w = int(new_w * scale_down)
            new_h = int(new_h * scale_down)

        center_x = (canvas_w / 2) + self.pan_x
        center_y = (canvas_h / 2) + self.pan_y
        img_left = center_x - (new_w / 2.0)
        img_top = center_y - (new_h / 2.0)

        cx1, cy1, cx2, cy2 = self.crop_box
        left_box = min(cx1, cx2)
        right_box = max(cx1, cx2)
        top_box = min(cy1, cy2)
        bottom_box = max(cy1, cy2)

        # Calculate percentage crop box relative to full source image
        pct_x1 = max(0.0, min(1.0, (left_box - img_left) / float(new_w)))
        pct_y1 = max(0.0, min(1.0, (top_box - img_top) / float(new_h)))
        pct_x2 = max(0.0, min(1.0, (right_box - img_left) / float(new_w)))
        pct_y2 = max(0.0, min(1.0, (bottom_box - img_top) / float(new_h)))

        cb = self.on_confirm_crop_cb
        self.exit_crop_mode()

        if cb:
            cb(pct_x1, pct_y1, pct_x2, pct_y2)

    def get_crop_box_percentages(self) -> Optional[Tuple[float, float, float, float]]:
        """
        If currently in crop mode with a valid crop box, return (pct_x1, pct_y1, pct_x2, pct_y2)
        relative to the full source image. Returns None if not cropping or box invalid.
        """
        if not self.is_cropping or self.crop_box is None or self.current_pil_img is None:
            return None

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 10 or canvas_h <= 10:
            return None

        img_w, img_h = self.current_pil_img.size
        ratio = min(canvas_w / img_w, canvas_h / img_h) * self.zoom_level

        new_w = max(10, int(img_w * ratio))
        new_h = max(10, int(img_h * ratio))

        max_dim = 3500
        if new_w > max_dim or new_h > max_dim:
            scale_down = min(max_dim / new_w, max_dim / new_h)
            new_w = int(new_w * scale_down)
            new_h = int(new_h * scale_down)

        center_x = (canvas_w / 2) + self.pan_x
        center_y = (canvas_h / 2) + self.pan_y
        img_left = center_x - (new_w / 2.0)
        img_top = center_y - (new_h / 2.0)

        cx1, cy1, cx2, cy2 = self.crop_box
        left_box = min(cx1, cx2)
        right_box = max(cx1, cx2)
        top_box = min(cy1, cy2)
        bottom_box = max(cy1, cy2)

        pct_x1 = max(0.0, min(1.0, (left_box - img_left) / float(new_w)))
        pct_y1 = max(0.0, min(1.0, (top_box - img_top) / float(new_h)))
        pct_x2 = max(0.0, min(1.0, (right_box - img_left) / float(new_w)))
        pct_y2 = max(0.0, min(1.0, (bottom_box - img_top) / float(new_h)))

        if pct_x2 <= pct_x1 or pct_y2 <= pct_y1:
            return None

        return (pct_x1, pct_y1, pct_x2, pct_y2)

    def _cancel_zoom_timer(self):
        if self._zoom_timer is not None:
            try:
                self.after_cancel(self._zoom_timer)
            except Exception:
                pass
            self._zoom_timer = None

    def _on_zoom(self, event):
        if event.delta > 0:
            self.zoom_level *= 1.15
        else:
            self.zoom_level /= 1.15
        self.zoom_level = max(0.2, min(5.0, self.zoom_level))

        # Render instant crop preview while scrolling
        self.redraw(force_resize=True, fast_mode=True)

        # Debounce crisp render 100ms after mouse wheel stops
        self._cancel_zoom_timer()
        self._zoom_timer = self.after(100, lambda: self.redraw(force_resize=True, fast_mode=False))

    def _on_double_click(self, event):
        if self.current_pil_img is None:
            return

        if self.zoom_level <= 1.05:
            # Zoom in to 2.5x centered at click position
            self.zoom_level = 2.5
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()

            click_offset_x = event.x - (canvas_w / 2)
            click_offset_y = event.y - (canvas_h / 2)
            self.pan_x = -click_offset_x * 1.5
            self.pan_y = -click_offset_y * 1.5
        else:
            # Reset back to fit-to-screen
            self.zoom_level = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0

        self.redraw(force_resize=True)
