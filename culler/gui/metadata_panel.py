from pathlib import Path
from typing import List, Optional, Callable
import customtkinter as ctk
from ..culler_engine import ImageItem, FlagState
from .tooltip import ToolTip


class MetadataPanel(ctk.CTkFrame):
    """
    Right sidebar containing Pick/Reject action buttons, Move Picked / Move Rejected actions with custom output folders,
    Unflag All, Tagging controls (Blur, Duplicate, Dark, Over-exposed, Custom), star rating controls, and EXIF card.
    """

    def __init__(
        self,
        master,
        on_set_flag: Callable[[FlagState], None],
        on_set_rating: Callable[[int], None],
        on_toggle_tag: Optional[Callable[[str], None]] = None,
        on_unflag_all: Optional[Callable[[], None]] = None,
        on_untag_all: Optional[Callable[[], None]] = None,
        on_unrate_all: Optional[Callable[[], None]] = None,
        on_clear_all: Optional[Callable[[], None]] = None,
        on_crop: Optional[Callable[[], None]] = None,
        on_convert_jpg: Optional[Callable[[], None]] = None,
        on_move_picked: Optional[Callable[[], None]] = None,
        on_move_rejected: Optional[Callable[[], None]] = None,
        on_config_output_folders: Optional[Callable[[], None]] = None,
        initial_picked_folder: str = "_SELECTED",
        initial_rejected_folder: str = "_REJECTED",
        **kwargs
    ):
        super().__init__(master, width=290, corner_radius=5, **kwargs)
        self.pack_propagate(False)

        self.on_set_flag = on_set_flag
        self.on_set_rating = on_set_rating
        self.on_toggle_tag = on_toggle_tag
        self.on_unflag_all = on_unflag_all
        self.on_untag_all = on_untag_all
        self.on_unrate_all = on_unrate_all
        self.on_clear_all = on_clear_all
        self.on_crop = on_crop
        self.on_convert_jpg = on_convert_jpg
        self.on_move_picked = on_move_picked
        self.on_move_rejected = on_move_rejected
        self.on_config_output_folders = on_config_output_folders

        self.picked_folder = initial_picked_folder
        self.rejected_folder = initial_rejected_folder

        self.current_item: Optional[ImageItem] = None
        self._tag_buttons: dict = {}

        self._build_widgets()

    def _build_widgets(self):
        # Action Buttons Box
        self.action_box = ctk.CTkFrame(self, fg_color="transparent")
        self.action_box.pack(side="top", fill="x", padx=10, pady=6)

        self.lbl_action = ctk.CTkLabel(
            self.action_box, text="CULLING ACTIONS", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_action.pack(anchor="w", pady=(0, 4))

        self.btn_pick = ctk.CTkButton(
            self.action_box,
            text="[P] PICK",
            fg_color="#2b9348",
            hover_color="#1b4332",
            font=ctk.CTkFont(weight="bold", size=14),
            command=lambda: self.on_set_flag(FlagState.PICK)
        )
        self.btn_pick.pack(fill="x", pady=2)
        ToolTip(self.btn_pick, "Shortcut: P (Flag photo as PICK)")

        self.btn_reject = ctk.CTkButton(
            self.action_box,
            text="[X] REJECT",
            fg_color="#d90429",
            hover_color="#8d99ae",
            font=ctk.CTkFont(weight="bold", size=14),
            command=lambda: self.on_set_flag(FlagState.REJECT)
        )
        self.btn_reject.pack(fill="x", pady=2)
        ToolTip(self.btn_reject, "Shortcut: X (Flag photo as REJECT)")

        self.btn_unflag = ctk.CTkButton(
            self.action_box,
            text="[U] UNFLAG",
            fg_color="#4a4e69",
            hover_color="#22223b",
            command=lambda: self.on_set_flag(FlagState.UNFLAGGED)
        )
        self.btn_unflag.pack(fill="x", pady=2)
        ToolTip(self.btn_unflag, "Shortcut: U (Unflag active photo)")

        # Clear / Reset Metadata Row (Flags, Tags, Ratings, All side by side)
        self.reset_box = ctk.CTkFrame(self, fg_color="transparent")
        self.reset_box.pack(side="top", fill="x", padx=10, pady=4)

        self.lbl_reset = ctk.CTkLabel(
            self.reset_box, text="CLEAR METADATA", font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_reset.pack(anchor="w", pady=(0, 3))

        self.reset_btn_row = ctk.CTkFrame(self.reset_box, fg_color="transparent")
        self.reset_btn_row.pack(fill="x")

        if self.on_unflag_all:
            self.btn_unflag_all = ctk.CTkButton(
                self.reset_btn_row,
                text="🚩 Flags",
                width=62,
                height=26,
                fg_color="#333333",
                hover_color="#555555",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=self.on_unflag_all
            )
            self.btn_unflag_all.pack(side="left", padx=1)
            ToolTip(self.btn_unflag_all, "Clear flags across all photos")

        if self.on_untag_all:
            self.btn_untag_all = ctk.CTkButton(
                self.reset_btn_row,
                text="🏷️ Tags",
                width=62,
                height=26,
                fg_color="#333333",
                hover_color="#555555",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=self.on_untag_all
            )
            self.btn_untag_all.pack(side="left", padx=1)
            ToolTip(self.btn_untag_all, "Remove all tags from all photos")

        if self.on_unrate_all:
            self.btn_unrate_all = ctk.CTkButton(
                self.reset_btn_row,
                text="⭐ Stars",
                width=62,
                height=26,
                fg_color="#333333",
                hover_color="#555555",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=self.on_unrate_all
            )
            self.btn_unrate_all.pack(side="left", padx=1)
            ToolTip(self.btn_unrate_all, "Reset star ratings to 0")

        if self.on_clear_all:
            self.btn_clear_all = ctk.CTkButton(
                self.reset_btn_row,
                text="💥 All",
                width=62,
                height=26,
                fg_color="#5c0612",
                hover_color="#d90429",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=self.on_clear_all
            )
            self.btn_clear_all.pack(side="left", padx=1)
            ToolTip(self.btn_clear_all, "Clear Flags, Tags, AND Ratings across all photos")

        # Move & Export Operations Box
        self.move_box = ctk.CTkFrame(self, fg_color="transparent")
        self.move_box.pack(side="top", fill="x", padx=10, pady=4)

        self.lbl_move = ctk.CTkLabel(
            self.move_box, text="MOVE & EXPORT", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_move.pack(anchor="w", pady=(0, 4))

        p_name = Path(self.picked_folder).name or self.picked_folder
        r_name = Path(self.rejected_folder).name or self.rejected_folder

        self.btn_move_picked = ctk.CTkButton(
            self.move_box,
            text=f"📁 Move Picked -> [{p_name}]",
            fg_color="#1b4332",
            hover_color="#2b9348",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._handle_move_picked
        )
        self.btn_move_picked.pack(fill="x", pady=2)

        self.btn_move_rejected = ctk.CTkButton(
            self.move_box,
            text=f"📁 Move Rejected -> [{r_name}]",
            fg_color="#5c0612",
            hover_color="#d90429",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._handle_move_rejected
        )
        self.btn_move_rejected.pack(fill="x", pady=2)

        if self.on_crop:
            self.btn_crop = ctk.CTkButton(
                self.move_box,
                text="✂️ Crop Active Image [C]",
                fg_color="#ffb703",
                hover_color="#fb8500",
                text_color="#000000",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self.on_crop
            )
            self.btn_crop.pack(fill="x", pady=2)
            ToolTip(self.btn_crop, "Shortcut: C (Crop - Hold Shift for 1:1 Square)")

        if self.on_convert_jpg:
            self.btn_convert_jpg = ctk.CTkButton(
                self.move_box,
                text="🖼️ Convert Selected to JPG",
                fg_color="#fb5607",
                hover_color="#ff006e",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self.on_convert_jpg
            )
            self.btn_convert_jpg.pack(fill="x", pady=2)
            ToolTip(self.btn_convert_jpg, "Convert selected photo(s) to JPG (Shortcut: Ctrl+S)")

        # Tags Box (Blur, Duplicate, Dark, Over-exposed + Custom from Settings)
        self.tags_box = ctk.CTkFrame(self, fg_color="transparent")
        self.tags_box.pack(side="top", fill="x", padx=10, pady=4)

        self.lbl_tags = ctk.CTkLabel(
            self.tags_box, text="IMAGE TAGS", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_tags.pack(anchor="w", pady=(0, 4))

        self._tags_container = ctk.CTkFrame(self.tags_box, fg_color="transparent")
        self._tags_container.pack(fill="x")

        self._build_tag_buttons([])

        # Rating Stars Box
        self.rating_box = ctk.CTkFrame(self, fg_color="transparent")
        self.rating_box.pack(side="top", fill="x", padx=10, pady=4)

        self.lbl_stars = ctk.CTkLabel(
            self.rating_box, text="STAR RATING", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_stars.pack(anchor="w", pady=(0, 4))

        self.star_btn_frame = ctk.CTkFrame(self.rating_box, fg_color="transparent")
        self.star_btn_frame.pack(fill="x")

        self.star_buttons = []
        for star in range(1, 6):
            btn = ctk.CTkButton(
                self.star_btn_frame,
                text=f"★{star}",
                width=46,
                fg_color="#3a86ff",
                hover_color="#0077b6",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda s=star: self._handle_set_rating(s)
            )
            btn.pack(side="left", padx=2)
            ToolTip(btn, f"Shortcut: {star} (Set rating to {star} Star{'s' if star > 1 else ''})")
            self.star_buttons.append(btn)

        # Metadata Card Box
        self.meta_card = ctk.CTkFrame(self, corner_radius=6, fg_color="#242424")
        self.meta_card.pack(side="top", fill="both", expand=True, padx=10, pady=6)

        self.lbl_meta_title = ctk.CTkLabel(
            self.meta_card, text="EXIF METADATA", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_meta_title.pack(anchor="w", padx=10, pady=(6, 2))

        self.lbl_meta_details = ctk.CTkLabel(
            self.meta_card,
            text="No image selected.",
            justify="left",
            anchor="nw",
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.lbl_meta_details.pack(fill="both", expand=True, padx=10, pady=4)

    def update_output_folders(self, picked_folder: str, rejected_folder: str):
        self.picked_folder = picked_folder
        self.rejected_folder = rejected_folder
        p_name = Path(picked_folder).name or picked_folder
        r_name = Path(rejected_folder).name or rejected_folder
        self.btn_move_picked.configure(text=f"📁 Move Picked -> [{p_name}]")
        self.btn_move_rejected.configure(text=f"📁 Move Rejected -> [{r_name}]")

    def _handle_set_rating(self, star: int):
        if self.on_set_rating:
            current_r = self.current_item.rating if self.current_item else 0
            new_r = 0 if current_r == star else star
            self.on_set_rating(new_r)

    def _handle_move_picked(self):
        if self.on_move_picked:
            self.on_move_picked()

    def _handle_move_rejected(self):
        if self.on_move_rejected:
            self.on_move_rejected()

    def _handle_config_folders(self):
        if self.on_config_output_folders:
            self.on_config_output_folders()

    def _toggle_tag(self, tag_name: str):
        if self.on_toggle_tag:
            self.on_toggle_tag(tag_name)

    def _build_tag_buttons(self, custom_tags: List[str]):
        """Build tag toggle buttons for standard + custom tags."""
        for widget in self._tags_container.winfo_children():
            widget.destroy()
        self._tag_buttons.clear()

        all_tags = ["Blur", "Duplicate", "Dark", "Over-exposed"] + list(custom_tags)

        # Layout in rows of 2
        row_frame = None
        for idx, tag in enumerate(all_tags):
            if idx % 2 == 0:
                row_frame = ctk.CTkFrame(self._tags_container, fg_color="transparent")
                row_frame.pack(fill="x", pady=1)
            btn = ctk.CTkButton(
                row_frame,
                text=f"🏷️ {tag}",
                width=125,
                height=26,
                fg_color="#3a3a3a",
                hover_color="#555555",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda t=tag: self._toggle_tag(t)
            )
            btn.pack(side="left", padx=2, pady=1)
            self._tag_buttons[tag] = btn

        # Re-highlight if there's a current item
        if self.current_item:
            for tag, btn in self._tag_buttons.items():
                if self.current_item.has_tag(tag):
                    btn.configure(fg_color="#7b2cbf")
                else:
                    btn.configure(fg_color="#3a3a3a")

    def refresh_tag_buttons(self, custom_tags: List[str]):
        """Refresh tag buttons with updated custom tags from settings."""
        self._build_tag_buttons(custom_tags)

    def update_item_metadata(self, item: Optional[ImageItem]):
        self.current_item = item
        if item is None:
            self.lbl_meta_details.configure(text="No image selected.")
            for btn in self.star_buttons:
                btn.configure(fg_color="#3a86ff", text_color="#ffffff")
            return

        m = item.metadata
        flag_str = item.flag.value
        stars_str = "★" * item.rating if item.rating > 0 else "None"
        stacked_str = f"\nStacked: {len(item.stacked_paths)} files" if item.is_stacked else ""
        tags_display = item.tags_str if item.tags_str else "None"

        # Update star button colors (highlight active rating in gold #ffb703)
        cur_rating = item.rating if item else 0
        for star_num, btn in enumerate(self.star_buttons, start=1):
            if star_num == cur_rating:
                btn.configure(fg_color="#ffb703", text_color="#000000")
            else:
                btn.configure(fg_color="#3a86ff", text_color="#ffffff")

        # Update tag button colors (highlight active tags in purple #7b2cbf)
        for tag, btn in self._tag_buttons.items():
            if item.has_tag(tag):
                btn.configure(fg_color="#7b2cbf")
            else:
                btn.configure(fg_color="#3a3a3a")

        txt = (
            f"File: {item.filename}\n"
            f"Format: {item.format_name}{stacked_str}\n"
            f"Size: {item.formatted_size}\n"
            f"Status: {flag_str}\n"
            f"Rating: {stars_str}\n"
            f"Sharpness: {item.sharpness_score}\n"
            f"Tags: {tags_display}\n"
            "------------------------\n"
            f"Camera: {m.get('model', 'N/A')}\n"
            f"Lens: {m.get('lens', 'N/A')}\n"
            f"ISO: {m.get('iso', 'N/A')}\n"
            f"Shutter: {m.get('shutter_speed', 'N/A')}\n"
            f"Aperture: {m.get('aperture', 'N/A')}\n"
            f"Focal Length: {m.get('focal_length', 'N/A')}\n"
            f"Date Taken: {m.get('date_taken', 'N/A')}\n"
        )
        self.lbl_meta_details.configure(text=txt)

    def update_metadata(self, item: Optional[ImageItem]):
        self.update_item_metadata(item)

    def clear(self):
        """Clear metadata panel details display when no image is selected."""
        self.update_item_metadata(None)
