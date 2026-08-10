import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Callable, Optional, Dict, Tuple, Set
import customtkinter as ctk
from PIL import Image, ImageDraw

from ..culler_engine import ImageItem, FlagState
from ..image_loader import ImageLoader
from ..logger import log_debug, log_error


class ThumbnailList(ctk.CTkFrame):
    """
    Left sidebar displaying image thumbnails.
    Supports big 70x70 thumbnails for stacked photo variants with horizontal scrolling and zero scrollbar clipping.
    Supports multi-select checkboxes, Select All / Select None, and Ctrl/Shift mouse selection.
    """

    def __init__(
        self,
        master,
        on_select_image: Callable[..., None],
        on_select_all: Optional[Callable[[], None]] = None,
        on_select_none: Optional[Callable[[], None]] = None,
        image_loader: Optional[ImageLoader] = None,
        **kwargs
    ):
        super().__init__(master, width=340, corner_radius=5, **kwargs)
        self.pack_propagate(False)

        self.on_select_image = on_select_image
        self.on_select_all = on_select_all
        self.on_select_none = on_select_none
        self.image_loader = image_loader
        self._executor = ThreadPoolExecutor(max_workers=4)

        self._btn_map: Dict[str, ctk.CTkButton] = {}
        self._row_frame_map: Dict[int, ctk.CTkFrame] = {}
        self._indicator_map: Dict[int, ctk.CTkFrame] = {}
        self._label_map: Dict[int, Union[ctk.CTkLabel, ctk.CTkButton]] = {}
        self._checkbox_map: Dict[int, ctk.CTkCheckBox] = {}
        self._ctk_img_cache: Dict[str, ctk.CTkImage] = {}

        # Top Header Box
        self.hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.hdr_frame.pack(side="top", fill="x", padx=4, pady=(4, 2))

        self.lbl_title = ctk.CTkLabel(
            self.hdr_frame, text="Images (0)", font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        self.lbl_title.pack(side="left", padx=2)

        # Multi-select Action Buttons
        self.btn_select_none = ctk.CTkButton(
            self.hdr_frame,
            text="None",
            width=45,
            height=22,
            fg_color="#333333",
            hover_color="#555555",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._handle_select_none
        )
        self.btn_select_none.pack(side="right", padx=2)

        self.btn_select_all = ctk.CTkButton(
            self.hdr_frame,
            text="Select All",
            width=65,
            height=22,
            fg_color="#1f538d",
            hover_color="#14375e",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._handle_select_all
        )
        self.btn_select_all.pack(side="right", padx=2)

        self.lbl_selection_count = ctk.CTkLabel(
            self.hdr_frame,
            text="(1 Selected)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffb703"
        )
        self.lbl_selection_count.pack(side="right", padx=4)

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=2, pady=2)

    def _handle_select_all(self):
        if self.on_select_all:
            self.on_select_all()

    def _handle_select_none(self):
        if self.on_select_none:
            self.on_select_none()

    def _handle_chk_toggled(self, idx: int):
        self._on_btn_clicked(idx, None)

    def _on_btn_clicked(self, idx: int, path: Optional[Path], event=None):
        is_ctrl = False
        is_shift = False

        try:
            import ctypes
            VK_SHIFT = 0x10
            VK_CONTROL = 0x11
            is_shift = bool(ctypes.windll.user32.GetKeyState(VK_SHIFT) & 0x8000)
            is_ctrl = bool(ctypes.windll.user32.GetKeyState(VK_CONTROL) & 0x8000)
        except Exception:
            pass

        if event is not None:
            state = getattr(event, "state", 0)
            if not is_shift:
                is_shift = bool(state & 0x0001)
            if not is_ctrl:
                is_ctrl = bool(state & 0x0004 or state & 0x20000)

        self.on_select_image(idx, path, is_continuous=False, is_ctrl=is_ctrl, is_shift=is_shift, from_click=True)

    def set_image_loader(self, image_loader: ImageLoader):
        self.image_loader = image_loader

    def shutdown(self):
        """
        Cleanly shutdown background thread pool executor on window exit.
        """
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def set_selected_indices(self, selected_indices: Set[int], active_idx: int, active_path: Optional[Path] = None, auto_scroll: bool = True):
        total_items = len(self._row_frame_map)
        sel_count = len(selected_indices)
        self.lbl_selection_count.configure(text=f"({sel_count} Selected)")

        active_path_str = str(active_path) if active_path else None
        prev_sel = getattr(self, "_prev_selected_indices", set())
        prev_act = getattr(self, "_prev_active_idx", -1)
        prev_path = getattr(self, "_prev_active_path_str", None)

        # Compute exact set of row indices that changed state
        changed_indices = (selected_indices ^ prev_sel) | {active_idx, prev_act}

        for idx in changed_indices:
            if idx not in self._row_frame_map:
                continue
            frame = self._row_frame_map[idx]
            is_active = (idx == active_idx)
            is_selected = (idx in selected_indices)

            if is_active:
                frame.configure(border_color="#1f538d", border_width=2)
            elif is_selected:
                frame.configure(border_color="#ffb703", border_width=2)
            else:
                frame.configure(border_color="#3a3a3a", border_width=1)

            if idx in self._checkbox_map:
                chk = self._checkbox_map[idx]
                if is_selected:
                    chk.select()
                else:
                    chk.deselect()

        # Update button highlights only if active sub-path changed
        if active_path_str != prev_path:
            if prev_path and prev_path in self._btn_map:
                self._btn_map[prev_path].configure(fg_color="transparent")
            if active_path_str and active_path_str in self._btn_map:
                self._btn_map[active_path_str].configure(fg_color="#1f538d")

        self._prev_selected_indices = set(selected_indices)
        self._prev_active_idx = active_idx
        self._prev_active_path_str = active_path_str

        # Auto-scroll thumbnail list so active row is always visible and centered (ONLY during keyboard operations)
        if auto_scroll:
            try:
                if total_items > 1:
                    target_frac = (active_idx - 2) / float(max(1, total_items - 1))
                    target_frac = max(0.0, min(1.0, target_frac))
                    if hasattr(self.scroll_frame, "_parent_canvas"):
                        self.scroll_frame._parent_canvas.yview_moveto(target_frac)
            except Exception:
                pass

    def set_selected_index(self, selected_idx: int, active_path: Optional[Path] = None):
        self.set_selected_indices({selected_idx}, selected_idx, active_path)

    def update_single_item_status(self, idx: int, item: ImageItem):
        """
        Updates ONLY the flag indicator bar and star rating text for a single row
        without destroying or re-creating widgets (0ms, zero flickering!).
        """
        flag_color = "#2b9348" if item.flag == FlagState.PICK else (
            "#d90429" if item.flag == FlagState.REJECT else "#4a4e69"
        )
        if idx in self._indicator_map:
            self._indicator_map[idx].configure(fg_color=flag_color)

        stars = "★" * item.rating if item.rating > 0 else ""

        if idx in self._label_map:
            widget = self._label_map[idx]
            if isinstance(widget, ctk.CTkLabel):
                from ..culler_engine import CullingSession
                primary_p = item.stacked_paths[0]
                base_stem = CullingSession.extract_base_stem(primary_p.stem)
                widget.configure(text=f"{base_stem.upper()} [Stacked {len(item.stacked_paths)} files] {stars}")
            elif isinstance(widget, ctk.CTkButton):
                fmt_short = item.format_name.split()[0]
                widget.configure(text=f"{item.filename}\n{fmt_short} {stars}")

    def _create_placeholder_image(self, size=(70, 70)) -> Image.Image:
        img = Image.new("RGB", size, color="#222222")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, size[0]-1, size[1]-1], outline="#383838")
        return img

    def update_items(self, items: List[ImageItem], selected_idx: int = 0, white_balance: str = "camera"):
        log_debug(f"ThumbnailList.update_items: updating {len(items)} items, selected_idx={selected_idx}")
        self.lbl_title.configure(text=f"Images ({len(items)})")
        self._btn_map.clear()
        self._row_frame_map.clear()
        self._indicator_map.clear()
        self._label_map.clear()
        self._checkbox_map.clear()
        self._prev_selected_indices = set()
        self._prev_active_idx = -1
        self._prev_active_path_str = None

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        placeholder_pil_70 = self._create_placeholder_image((70, 70))
        placeholder_ctk_70 = ctk.CTkImage(light_image=placeholder_pil_70, dark_image=placeholder_pil_70, size=(70, 70))

        placeholder_pil_80 = self._create_placeholder_image((80, 80))
        placeholder_ctk_80 = ctk.CTkImage(light_image=placeholder_pil_80, dark_image=placeholder_pil_80, size=(80, 80))

        placeholder_pil_90 = self._create_placeholder_image((90, 90))
        placeholder_ctk_90 = ctk.CTkImage(light_image=placeholder_pil_90, dark_image=placeholder_pil_90, size=(90, 90))

        raw_thumb_requests: List[Tuple[Path, Tuple[int, int], str]] = []
        other_thumb_requests: List[Tuple[Path, Tuple[int, int], str]] = []

        for idx, item in enumerate(items):
            is_selected = (idx == selected_idx)

            # Container row frame (160px height for stacked rows to fit square thumbnails comfortably)
            row_frame = ctk.CTkFrame(
                self.scroll_frame,
                height=160 if (item.is_stacked and len(item.stacked_paths) >= 2) else 96,
                corner_radius=6,
                border_width=2 if is_selected else 1,
                border_color="#1f538d" if is_selected else "#3a3a3a"
            )
            row_frame.pack(fill="x", padx=1, pady=2)
            row_frame.pack_propagate(False)
            self._row_frame_map[idx] = row_frame

            # Flag status color bar indicator on the left edge
            flag_color = "#2b9348" if item.flag == FlagState.PICK else (
                "#d90429" if item.flag == FlagState.REJECT else "#4a4e69"
            )
            indicator = ctk.CTkFrame(row_frame, width=5, fg_color=flag_color)
            indicator.pack(side="left", fill="y")
            self._indicator_map[idx] = indicator

            # Multi-select Checkbox
            chk = ctk.CTkCheckBox(
                row_frame,
                text="",
                width=18,
                height=18,
                checkbox_width=18,
                checkbox_height=18,
                fg_color="#ffb703",
                hover_color="#fb8500",
                command=lambda i=idx: self._handle_chk_toggled(i)
            )
            chk.pack(side="left", padx=(4, 2))
            if is_selected:
                chk.select()
            else:
                chk.deselect()
            self._checkbox_map[idx] = chk

            stars = "★" * item.rating if item.rating > 0 else ""

            if item.is_stacked and len(item.stacked_paths) >= 2:
                # MULTI-FILE STACKED ROW: Big 70x70 thumbnails with horizontal scrolling
                info_box = ctk.CTkFrame(row_frame, fg_color="transparent")
                info_box.pack(side="top", fill="x", padx=4, pady=(2, 1))

                import re
                from ..culler_engine import CullingSession

                primary_p = item.stacked_paths[0]
                base_stem = CullingSession.extract_base_stem(primary_p.stem)

                lbl_name = ctk.CTkLabel(
                    info_box,
                    text=f"{base_stem.upper()} [Stacked {len(item.stacked_paths)} files] {stars}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    anchor="w"
                )
                lbl_name.pack(side="left")
                self._label_map[idx] = lbl_name

                thumb_scroll = ctk.CTkScrollableFrame(
                    row_frame,
                    orientation="horizontal",
                    height=130,
                    fg_color="transparent"
                )
                thumb_scroll.pack(side="top", fill="both", expand=True, padx=2, pady=1)

                for sub_p in item.stacked_paths:
                    ext = sub_p.suffix.lower()
                    diff = re.sub(re.escape(base_stem), "", sub_p.stem, flags=re.IGNORECASE).strip(" _-")

                    if ext == ".arw":
                        badge_label = f"RAW {diff}" if diff else "RAW"
                    elif sub_p.stem.lower() == base_stem.lower():
                        badge_label = "JPG"
                    else:
                        badge_label = diff if diff else "JPG"

                    btn_sub = ctk.CTkButton(
                        thumb_scroll,
                        text=badge_label,
                        image=self._ctk_img_cache.get(str(sub_p), placeholder_ctk_90),
                        compound="top",
                        font=ctk.CTkFont(size=10, weight="bold"),
                        width=95,
                        height=95,
                        fg_color="transparent",
                        hover_color="#333333",
                        command=lambda i=idx, p=sub_p: self._on_btn_clicked(i, p)
                    )
                    btn_sub.pack(side="left", padx=3)
                    self._btn_map[str(sub_p)] = btn_sub

                    if self.image_loader and str(sub_p) not in self._ctk_img_cache:
                        req = (sub_p, (90, 90), white_balance)
                        if ext == ".arw":
                            raw_thumb_requests.append(req)
                        else:
                            other_thumb_requests.append(req)

                raw_n = sum(1 for p in item.stacked_paths if p.suffix.lower() == ".arw")
                jpg_n = sum(1 for p in item.stacked_paths if p.suffix.lower() in (".jpg", ".jpeg"))
                parts = []
                if raw_n:
                    parts.append(f"{raw_n} RAW")
                if jpg_n:
                    parts.append(f"{jpg_n} JPG")
                comp = ", ".join(parts) if parts else f"{len(item.stacked_paths)} files"
                lbl_name.configure(text=f"{base_stem.upper()} [Stacked: {comp}] {stars}")
            else:
                # SINGLE ITEM ROW (80x80)
                ext = item.path.suffix.lower()
                if ext == ".arw":
                    fmt_badge = "RAW"
                elif ext in (".jpg", ".jpeg"):
                    fmt_badge = "JPG"
                else:
                    fmt_badge = item.format_name.split()[0]

                txt = f"{fmt_badge} {item.filename} {stars}"

                btn = ctk.CTkButton(
                    row_frame,
                    text=txt,
                    image=self._ctk_img_cache.get(str(item.path), placeholder_ctk_80),
                    compound="left",
                    anchor="w",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    height=88,
                    fg_color="transparent",
                    hover_color="#333333",
                    command=lambda i=idx, p=item.path: self._on_btn_clicked(i, p)
                )
                btn.pack(side="left", fill="both", expand=True, padx=2, pady=1)
                self._btn_map[str(item.path)] = btn
                self._label_map[idx] = btn

                if self.image_loader and str(item.path) not in self._ctk_img_cache:
                    req = (item.path, (80, 80), white_balance)
                    if ext == ".arw":
                        raw_thumb_requests.append(req)
                    else:
                        other_thumb_requests.append(req)

        if self.image_loader:
            for path, size, wb in raw_thumb_requests:
                self._load_single_thumb_async(path, size, wb)
            for path, size, wb in other_thumb_requests:
                self._load_single_thumb_async(path, size, wb)

    def _load_single_thumb_async(self, file_path: Path, max_size: Tuple[int, int], white_balance: str):
        path_str = str(file_path)

        def worker():
            try:
                pil_thumb = self.image_loader.get_thumbnail(
                    file_path,
                    max_size=max_size,
                    raw_scale=0.10,
                    white_balance=white_balance
                )
                if pil_thumb:
                    self.after(0, lambda: self._update_btn_image(path_str, pil_thumb))
            except Exception as e:
                log_error(f"Error generating thumbnail for {file_path.name}", exc_info=True)

        self._executor.submit(worker)

    def _update_btn_image(self, path_str: str, pil_thumb: Image.Image):
        if path_str in self._btn_map:
            btn = self._btn_map[path_str]
            w, h = pil_thumb.size
            ctk_img = ctk.CTkImage(light_image=pil_thumb, dark_image=pil_thumb, size=(w, h))
            self._ctk_img_cache[path_str] = ctk_img
            btn.configure(image=ctk_img)
