import csv
import json
import os
import shutil
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Callable, Union, Tuple
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

from .exif_wrapper import ExifToolWrapper
from .image_loader import ImageLoader
from .db_manager import DatabaseManager

Union_Path_Str = Union[Path, str]


class FlagState(Enum):
    UNFLAGGED = "UNFLAGGED"
    PICK = "PICK"
    REJECT = "REJECT"

    def __str__(self):
        return self.value


class ImageItem:
    """
    Represents a single image item in a culling session.
    Supports RAW+JPG pair stacking and customizable tagging (Blur, Duplicate, Dark, Over-exposed, Custom).
    """

    def __init__(self, file_path: Union_Path_Str):
        self.path = Path(file_path).resolve()
        self.filename = self.path.name
        self.extension = self.path.suffix.lower()
        self.format_name = ImageLoader.get_format_type(self.path)
        self.size_bytes = self.path.stat().st_size if self.path.exists() else 0

        self.stacked_paths: List[Path] = [self.path]
        self.is_stacked: bool = False

        self.flag: FlagState = FlagState.UNFLAGGED
        self.rating: int = 0  # 0 to 5
        self.sharpness_score: float = 0.0
        self.tags: Set[str] = set()
        self.dhash: Optional[int] = None
        self.metadata: Dict[str, Any] = {}

    @property
    def tags_str(self) -> str:
        return ", ".join(sorted(self.tags))

    def add_tag(self, tag: str):
        t = tag.strip().title()
        if t:
            self.tags.add(t)

    def remove_tag(self, tag: str):
        t = tag.strip().title()
        if t in self.tags:
            self.tags.remove(t)

    def has_tag(self, tag: str) -> bool:
        return tag.strip().title() in self.tags

    @property
    def formatted_size(self) -> str:
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "path": str(self.path),
            "stacked_paths": [str(p) for p in self.stacked_paths],
            "is_stacked": self.is_stacked,
            "format": self.format_name,
            "size": self.formatted_size,
            "flag": self.flag.value,
            "rating": self.rating,
            "sharpness": self.sharpness_score,
            "tags": self.tags_str,
            "camera": self.metadata.get("model", "N/A"),
            "lens": self.metadata.get("lens", "N/A"),
            "iso": self.metadata.get("iso", "N/A"),
            "shutter": self.metadata.get("shutter_speed", "N/A"),
            "aperture": self.metadata.get("aperture", "N/A"),
            "focal_length": self.metadata.get("focal_length", "N/A"),
            "date_taken": self.metadata.get("date_taken", "N/A"),
        }


class CullingSession:
    """
    Manages image files, metadata reading, flagging, ratings, filtering,
    tagging (Scan for Blur & Scan for Duplicate), batch operations, and reporting.
    """

    def __init__(self, exif_wrapper: Optional[ExifToolWrapper] = None, db_manager: Optional[DatabaseManager] = None):
        self.exif_wrapper = exif_wrapper or ExifToolWrapper()
        self.db = db_manager or DatabaseManager()
        self.image_loader = ImageLoader(exif_wrapper=self.exif_wrapper)
        self.items: List[ImageItem] = []
        self.directory: Optional[Path] = None

    @staticmethod
    def extract_base_stem(stem: str) -> str:
        """
        Extract primary base photo stem from filenames with generic prefixes/suffixes:
        Prefixes: "Copy of ", "Copy (1) of ", "Edited - ", "Crop of "
        Suffixes: " (1)", " (copy)", " - Copy", "_1", "_crop", "_edit", "-v2"
        """
        import re
        s = stem.strip()
        prefix_pattern = re.compile(
            r"^(?:copy\s*(?:\(\d+\))?\s*of\s*|edit(?:ed)?\s*[-_of]*\s*|crop\s*[-_of]*\s*)",
            re.IGNORECASE
        )
        suffix_pattern = re.compile(
            r"(?:[\s_-]+(?:\d+|copy|edit(?:ed)?|crop|v\d+|final|hdr|bw|export|enhanced)|\(\s*\d+\s*\)|\(\s*copy\s*\))+$",
            re.IGNORECASE
        )

        while True:
            prev = s
            s = prefix_pattern.sub("", s).strip()
            s = suffix_pattern.sub("", s).strip()
            if s == prev or not s:
                break

        return (s if s else stem.strip()).lower()

    def scan_directory(
        self,
        directory_path: Union_Path_Str,
        recursive: bool = False,
        stack_raw_jpg: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ImageItem]:
        """
        Scan a directory for supported image formats (ARW, JPG, PNG, HEIC).
        Automatically stacks matching RAW, JPG, and edited variant pairs into 1 item.
        Reads EXIF metadata in high-speed batches using ExifTool.
        Restores saved flags, ratings, & tags from local SQLite database.
        """
        dir_path = Path(directory_path).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Directory standard path does not exist: {directory_path}")

        self.directory = dir_path
        self.items.clear()
        self.image_loader.clear_cache()

        # Find all files matching supported extensions
        pattern = "**/*" if recursive else "*"
        found_paths: List[Path] = []
        for p in dir_path.glob(pattern):
            if p.is_file() and ImageLoader.is_supported(p):
                found_paths.append(p)

        if not found_paths:
            return []

        self.items = []

        if stack_raw_jpg:
            # Group found paths by parent directory and extracted base stem
            groups: Dict[Tuple[Path, str], List[Path]] = {}
            for p in found_paths:
                base_stem = self.extract_base_stem(p.stem)
                key = (p.parent, base_stem)
                if key not in groups:
                    groups[key] = []
                groups[key].append(p)

            for (parent, base_stem), group_paths in groups.items():
                if len(group_paths) > 1:
                    # Sort group: RAW (.ARW) first, then exact base stem JPG, then edits (_1, _crop)
                    def sort_key(p: Path):
                        ext = p.suffix.lower()
                        s = p.stem.lower()
                        if ext == ".arw": return (0, s)
                        if s == base_stem.lower(): return (1, s)
                        return (2, s)

                    group_paths.sort(key=sort_key)
                    primary = group_paths[0]
                    item = ImageItem(primary)
                    item.stacked_paths = group_paths
                    item.is_stacked = True
                    display_stem = self.extract_base_stem(primary.stem).upper()
                    item.filename = f"{display_stem} [Stacked {len(group_paths)} files]"
                    item.format_name = f"Stacked ({len(group_paths)} files)"
                    item.size_bytes = sum(p.stat().st_size for p in item.stacked_paths if p.exists())
                    self.items.append(item)
                else:
                    self.items.append(ImageItem(group_paths[0]))
        else:
            # Unstacked mode: Load every supported file as an independent ImageItem
            for p in found_paths:
                self.items.append(ImageItem(p))

        # Sort naturally by primary filename
        self.items.sort(key=lambda x: x.path.name.lower())

        # Fetch saved DB records for this directory
        db_records = self.db.get_all_records_for_dir(str(dir_path))

        # Batch fetch metadata via ExifTool
        str_paths = [str(item.path) for item in self.items]
        metadata_list = self.exif_wrapper.get_batch_metadata(str_paths)

        for i, item in enumerate(self.items):
            if i < len(metadata_list):
                item.metadata = metadata_list[i]
                item.rating = metadata_list[i].get("rating", 0)

            # Overlay saved SQLite DB record if available
            item_path_str = str(item.path)
            if item_path_str in db_records:
                rec = db_records[item_path_str]
                try:
                    item.flag = FlagState(rec["flag"])
                except ValueError:
                    pass
                item.rating = rec.get("rating", 0)
                if rec.get("sharpness", 0.0) > 0:
                    item.sharpness_score = rec["sharpness"]
                tags_raw = rec.get("tags", "")
                item.tags.clear()
                if tags_raw:
                    for t in tags_raw.split(","):
                        if t.strip():
                            item.add_tag(t.strip())

            if progress_callback:
                try:
                    progress_callback(i + 1, len(self.items), item.filename)
                except TypeError:
                    progress_callback(i + 1, len(self.items))

        return self.items

    def save_item_record(self, item: ImageItem):
        """
        Save/update image item record in SQLite DB (handles stacked pairs & tags).
        """
        if self.db:
            for p in item.stacked_paths:
                self.db.save_image_record(
                    file_path=str(p),
                    filename=p.name,
                    flag=item.flag.value,
                    rating=item.rating,
                    sharpness=item.sharpness_score,
                    tags=item.tags_str
                )

    def unflag_all_items(self) -> int:
        """
        Reset all item flags in session to UNFLAGGED and update DB.
        """
        count = 0
        for item in self.items:
            if item.flag != FlagState.UNFLAGGED:
                item.flag = FlagState.UNFLAGGED
                self.save_item_record(item)
                count += 1
        return count

    def untag_all_items(self) -> int:
        """
        Remove all tags from every item in session and update DB.
        """
        count = 0
        for item in self.items:
            if item.tags:
                item.tags.clear()
                self.save_item_record(item)
                count += 1
        return count

    def unrate_all_items(self) -> int:
        """
        Reset all star ratings to 0 across all items in session and update DB.
        """
        count = 0
        for item in self.items:
            item.rating = 0
            self.save_item_record(item)
            count += 1
        return count

    def clear_all_metadata(self) -> int:
        """
        Reset flags to UNFLAGGED, remove all tags, and set star ratings to 0 across all items in session.
        """
        count = 0
        for item in self.items:
            changed = False
            if item.flag != FlagState.UNFLAGGED:
                item.flag = FlagState.UNFLAGGED
                changed = True
            if item.tags:
                item.tags.clear()
                changed = True
            if item.rating != 0:
                item.rating = 0
                changed = True
            if changed:
                self.save_item_record(item)
                count += 1
        return count

    def move_items_to_trash(self, items: List[ImageItem], format_filter: Optional[str] = None) -> int:
        """
        Safely move items to the OS Recycle Bin / Trash using send2trash.
        If format_filter is specified (e.g. '.jpg' or 'JPG'), only files matching that extension
        are moved to trash, unstacking the item and preserving RAW originals.
        """
        import send2trash
        moved_count = 0
        target_ext = None
        if format_filter and "ALL" not in format_filter.upper():
            target_ext = format_filter.lower()
            if not target_ext.startswith("."):
                if target_ext == "raw":
                    target_ext = ".arw"
                else:
                    target_ext = "." + target_ext

        for item in list(items):
            if target_ext:
                paths_to_delete = [p for p in list(item.stacked_paths) if p.suffix.lower() == target_ext or (target_ext == ".arw" and ImageLoader.is_raw(p))]
                remaining_paths = [p for p in list(item.stacked_paths) if p not in paths_to_delete]

                for p in paths_to_delete:
                    if p.exists():
                        try:
                            send2trash.send2trash(str(p))
                            moved_count += 1
                        except Exception as e:
                            log_error(f"Error moving {p} to trash: {e}")

                if remaining_paths:
                    item.stacked_paths = remaining_paths
                    item.path = remaining_paths[0]
                    item.filename = item.path.name
                    item.extension = item.path.suffix.lower()
                    item.is_stacked = len(remaining_paths) > 1
                    if not item.is_stacked:
                        item.format_name = ImageLoader.get_format_type(item.path)
                    if self.db:
                        self.save_item_record(item)
                else:
                    if self.db:
                        self.db.cleanup_folder_metadata(str(item.path))
                    if item in self.items:
                        self.items.remove(item)
            else:
                for p in list(item.stacked_paths):
                    if p.exists():
                        try:
                            send2trash.send2trash(str(p))
                            moved_count += 1
                        except Exception as e:
                            log_error(f"Error moving {p} to trash: {e}")
                if self.db:
                    self.db.cleanup_folder_metadata(str(item.path))
                if item in self.items:
                    self.items.remove(item)

        return moved_count

    def compute_sharpness_scores(
        self,
        method: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """
        Calculate sharpness score for all loaded items using multi-threading.
        Supports algorithms: 'laplacian', 'tenengrad', 'bird_subject'.
        """
        blur_method = method or (self.db.get_blur_method() if self.db else "laplacian")

        def calc_item(index_and_item):
            idx, item = index_and_item
            item.sharpness_score = self.image_loader.calculate_sharpness(item.path, method=blur_method)
            self.save_item_record(item)
            return item

        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
            completed = 0
            for item in executor.map(calc_item, enumerate(self.items)):
                completed += 1
                if progress_callback:
                    try:
                        progress_callback(completed, len(self.items), item.filename)
                    except TypeError:
                        progress_callback(completed, len(self.items))

    def scan_for_blur(
        self,
        bottom_percentile: float = 15.0,
        method: Optional[str] = None,
        flag_action: str = "Reject",
        tag_action: Optional[str] = "Blur",
        rating_action: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ImageItem]:
        """
        Scan for Blur: Analyzes sharpness scores across all photos using selected method.
        Applies configurable flag, tag, and rating actions to detected blurry photos.
        """
        if not self.items:
            return []

        # Force re-computation if method is explicitly requested or missing scores
        blur_method = method or (self.db.get_blur_method() if self.db else "laplacian")
        self.compute_sharpness_scores(method=blur_method, progress_callback=progress_callback)

        # Sort items by sharpness score
        sorted_items = sorted(self.items, key=lambda x: x.sharpness_score)
        cutoff_index = int(len(sorted_items) * (bottom_percentile / 100.0))
        cutoff_index = max(1, min(cutoff_index, len(sorted_items)))

        flag_map = {
            "Reject": FlagState.REJECT,
            "Pick": FlagState.PICK,
            "Unflagged": FlagState.UNFLAGGED,
        }

        flagged_blurry = []
        for i in range(cutoff_index):
            item = sorted_items[i]
            
            # Tag action
            if tag_action:
                item.add_tag(tag_action)
            
            # Flag action
            if flag_action in flag_map:
                item.flag = flag_map[flag_action]
            
            # Rating action
            if rating_action is not None:
                item.rating = max(0, min(5, rating_action))

            self.save_item_record(item)
            flagged_blurry.append(item)

        return flagged_blurry

    def scan_for_duplicates(
        self,
        method: str = "dhash",
        threshold: float = 6.0,
        flag_action: str = "Reject",
        tag_action: Optional[str] = "Duplicate",
        rating_action: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ImageItem]:
        """
        Scan for Duplicates: Detects duplicate, near-identical, or burst-shot photos.
        Delegates detection to culler.detectors.duplicate_detector module.
        Keeps the sharpest photo in each group, and applies configurable flag, tag, and rating actions to duplicates.
        """
        if not self.items:
            return []

        from .detectors.duplicate_detector import find_duplicates
        groups = find_duplicates(
            self.items,
            image_loader=self.image_loader,
            method=method,
            threshold=threshold,
            progress_callback=progress_callback
        )

        # Ensure sharpness scores are computed to pick the keeper
        uncomputed = [item for item in self.items if item.sharpness_score == 0.0]
        if uncomputed:
            self.compute_sharpness_scores()

        flag_map = {
            "Reject": FlagState.REJECT,
            "Pick": FlagState.PICK,
            "Unflagged": FlagState.UNFLAGGED,
        }

        flagged_duplicates = []
        for group in groups:
            # Sort group by sharpness score descending (best photo first)
            group.sort(key=lambda x: x.sharpness_score, reverse=True)

            # Keep the sharpest shot as keeper
            keeper = group[0]
            if keeper.flag == FlagState.UNFLAGGED and flag_action == "Reject":
                keeper.flag = FlagState.PICK
                self.save_item_record(keeper)

            # Apply actions to all other duplicates in group
            for dup in group[1:]:
                if tag_action:
                    dup.add_tag(tag_action)
                
                if flag_action in flag_map:
                    dup.flag = flag_map[flag_action]

                if rating_action is not None:
                    dup.rating = max(0, min(5, rating_action))

                self.save_item_record(dup)
                flagged_duplicates.append(dup)

        return flagged_duplicates

    def _compute_dhash(self, img: Image.Image) -> int:
        """
        Compute 64-bit difference hash (dHash) for fast perceptual image similarity comparison.
        """
        small = img.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
        pixels = list(small.getdata())
        diff = []
        for row in range(8):
            for col in range(8):
                diff.append(pixels[row * 9 + col] > pixels[row * 9 + col + 1])
        val = 0
        for b in diff:
            val = (val << 1) | b
        return val

    def convert_item_to_jpg(
        self,
        item: ImageItem,
        output_dir: Optional[Union_Path_Str] = None,
        overwrite: bool = False
    ) -> Tuple[bool, str, Path]:
        source_path = item.path

        if output_dir and str(output_dir).lower() != "source":
            target_dir = Path(output_dir).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / source_path.with_suffix(".jpg").name
        else:
            target_path = source_path.with_suffix(".jpg")

        if source_path == target_path:
            return True, "already_jpg", source_path

        if target_path.exists() and not overwrite:
            return False, "exists", target_path

        try:
            pil_img = self.image_loader.load_full_image(source_path, raw_scale=1.0, white_balance="camera")
            if pil_img is None:
                return False, "failed_load", target_path

            pil_img.save(target_path, "JPEG", quality=95, optimize=True)
            return True, "success", target_path
        except Exception as e:
            print(f"Error converting {source_path} to JPG: {e}")
            return False, f"error: {e}", target_path

    def get_filtered_items(
        self,
        flag_filter: Optional[str] = None,
        rating_filter: Optional[int] = None,
        format_filter: Optional[str] = None,
        tag_filter: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[ImageItem]:
        filtered = self.items

        if flag_filter and flag_filter.upper() != "ALL":
            target_flag = flag_filter.upper()
            filtered = [item for item in filtered if item.flag.value == target_flag]

        if rating_filter is not None and rating_filter > 0:
            filtered = [item for item in filtered if item.rating >= rating_filter]

        if format_filter and "ALL" not in format_filter.upper():
            target_ext = format_filter.lower()
            if not target_ext.startswith("."):
                target_ext = "." + target_ext
            filtered = [item for item in filtered if item.extension == target_ext or (item.is_stacked and target_ext == ".arw")]

        if tag_filter and "ALL" not in tag_filter.upper():
            target_tag = tag_filter.strip().lower()
            filtered = [item for item in filtered if any(t.lower() == target_tag for t in item.tags)]

        if search_query:
            query = search_query.lower()
            filtered = [
                item for item in filtered
                if query in item.filename.lower() or query in item.tags_str.lower()
            ]

        return filtered

    def move_items_by_flag(self, flag: FlagState, subfolder_name: str) -> List[Path]:
        if not self.directory:
            raise ValueError("No directory active in culling session")

        target_dir = self.directory / subfolder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        moved_paths: List[Path] = []
        items_to_move = [item for item in self.items if item.flag == flag]

        for item in items_to_move:
            for p in item.stacked_paths:
                dest_path = target_dir / p.name
                if p.exists():
                    shutil.move(str(p), str(dest_path))
                    moved_paths.append(dest_path)
            item.path = target_dir / item.stacked_paths[0].name

        return moved_paths

    def delete_rejected_items(self, trash_dir_name: str = "_Trash") -> List[Path]:
        return self.move_items_by_flag(FlagState.REJECT, trash_dir_name)

    def sync_exif_ratings(self) -> int:
        success_count = 0
        for item in self.items:
            if item.rating > 0:
                for p in item.stacked_paths:
                    if self.exif_wrapper.write_rating(str(p), item.rating):
                        success_count += 1
        return success_count

    def export_manifest(self, output_path: Union_Path_Str, format_type: str = "json") -> str:
        out_path = Path(output_path)
        data = [item.to_dict() for item in self.items]

        if format_type.lower() == "csv":
            if not out_path.name.endswith(".csv"):
                out_path = out_path.with_suffix(".csv")
            if data:
                fieldnames = list(data[0].keys())
                with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
        else:
            if not out_path.name.endswith(".json"):
                out_path = out_path.with_suffix(".json")
            with open(out_path, mode="w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        return str(out_path)

    def get_summary_stats(self) -> Dict[str, Any]:
        total = len(self.items)
        picked = sum(1 for i in self.items if i.flag == FlagState.PICK)
        rejected = sum(1 for i in self.items if i.flag == FlagState.REJECT)
        unflagged = sum(1 for i in self.items if i.flag == FlagState.UNFLAGGED)

        by_format = {}
        for item in self.items:
            fmt = item.format_name
            by_format[fmt] = by_format.get(fmt, 0) + 1

        total_bytes = sum(i.size_bytes for i in self.items)
        size_mb = round(total_bytes / (1024 * 1024), 2)

        return {
            "total_images": total,
            "picked": picked,
            "rejected": rejected,
            "unflagged": unflagged,
            "total_size_mb": size_mb,
            "by_format": by_format,
        }
