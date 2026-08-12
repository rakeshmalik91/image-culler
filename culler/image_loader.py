import io
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from PIL import Image, ImageOps

# Register pillow_heif for HEIC / HEIF support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

# Try importing rawpy for ARW fallback
try:
    import rawpy
except ImportError:
    rawpy = None

# Try importing cv2 for sharpness calculation
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from .exif_wrapper import ExifToolWrapper


class ImageLoader:
    """
    Unified image loader supporting ARW, JPG, PNG, and HEIF/HEIC.
    Uses standalone in-memory PIL loading to prevent 'Operation on closed image' errors.
    """

    SUPPORTED_EXTENSIONS = {
        ".arw": "Sony ARW RAW",
        ".jpg": "JPEG Image",
        ".jpeg": "JPEG Image",
        ".png": "PNG Image",
        ".heic": "HEIF / HEIC Image",
        ".heif": "HEIF / HEIC Image",
    }

    MAX_THUMB_CACHE = 180  # Max cached thumbnail items in RAM
    MAX_FULL_CACHE = 30    # Max full resolution preview items in RAM (Pre-fetch buffer)

    def __init__(self, exif_wrapper: Optional[ExifToolWrapper] = None):
        self.exif_wrapper = exif_wrapper or ExifToolWrapper()
        self._thumb_cache: OrderedDict[Tuple, Image.Image] = OrderedDict()
        self._thumb_cache_index: Dict[str, Tuple] = {}
        self._full_cache: OrderedDict[Tuple, Image.Image] = OrderedDict()

    @classmethod
    def is_supported(cls, file_path: Union[str, Path]) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_format_type(cls, file_path: Union[str, Path]) -> str:
        ext = Path(file_path).suffix.lower()
        return cls.SUPPORTED_EXTENSIONS.get(ext, "Unknown")

    def get_cached_full_image(
        self,
        file_path: Union[str, Path],
        raw_scale: float = 0.25,
        white_balance: str = "camera"
    ) -> Optional[Image.Image]:
        """
        Check if full image is ALREADY cached in RAM buffer and return a copy instantly (0ms delay).
        """
        cache_key = (str(file_path), raw_scale, white_balance)
        if cache_key in self._full_cache:
            self._full_cache.move_to_end(cache_key)
            return self._full_cache[cache_key].copy()
        return None

    def get_cached_thumbnail(
        self,
        file_path: Union[str, Path]
    ) -> Optional[Image.Image]:
        """
        Instantly retrieve cached thumbnail from RAM (0ms lookup, zero disk I/O).
        """
        file_path_str = str(file_path)
        cache_key = self._thumb_cache_index.get(file_path_str)
        if cache_key and cache_key in self._thumb_cache:
            self._thumb_cache.move_to_end(cache_key)
            return self._thumb_cache[cache_key].copy()
        return None

    def load_full_image(
        self,
        file_path: Union[str, Path],
        raw_scale: float = 0.25,
        white_balance: str = "camera"
    ) -> Optional[Image.Image]:
        """
        Load image as standalone PIL.Image object with LRU caching.
        """
        file_path_str = str(file_path)
        cache_key = (file_path_str, raw_scale, white_balance)

        if cache_key in self._full_cache:
            self._full_cache.move_to_end(cache_key)
            return self._full_cache[cache_key].copy()

        ext = Path(file_path_str).suffix.lower()
        img: Optional[Image.Image] = None

        if ext == ".arw":
            img = self._load_arw_image(file_path_str, raw_scale=raw_scale, white_balance=white_balance)
        else:
            try:
                with Image.open(file_path_str) as raw_img:
                    if raw_scale < 1.0:
                        raw_img.draft("RGB", (1920, 1080))
                    raw_img = ImageOps.exif_transpose(raw_img)
                    img = raw_img.convert("RGB")
                    img.load()
            except Exception as e:
                print(f"Error loading image {file_path_str}: {e}")

        if img is not None:
            # Force full pixel load into memory RAM
            try:
                img.load()
            except Exception:
                pass

            self._full_cache[cache_key] = img
            self._full_cache.move_to_end(cache_key)

            # Evict oldest item if LRU limit reached (let GC handle memory release safely)
            if len(self._full_cache) > self.MAX_FULL_CACHE:
                self._full_cache.popitem(last=False)

            return img.copy()

        return None

    @classmethod
    def apply_exif_orientation(cls, img: Image.Image, orientation: Optional[int] = None) -> Image.Image:
        """
        Apply standard PIL EXIF orientation transpose.
        If an explicit orientation integer (1..8) is passed and img lacks an EXIF tag, injects it.
        """
        if img is None:
            return img
        try:
            exif = img.getexif()
            if orientation and 1 <= orientation <= 8 and orientation != 1:
                if 0x0112 not in exif or exif[0x0112] == 1:
                    exif[0x0112] = orientation
                    try:
                        img.info['exif'] = exif.tobytes()
                    except Exception:
                        pass
            if 0x0112 in exif and exif[0x0112] != 1:
                return ImageOps.exif_transpose(img)
            return img
        except Exception:
            return img

    def _load_arw_image(
        self,
        arw_path: str,
        raw_scale: float = 0.25,
        white_balance: str = "camera"
    ) -> Optional[Image.Image]:
        """
        Load Sony ARW photo using ExifTool high-res preview or RawPy demosaicing.
        """
        img: Optional[Image.Image] = None
        orientation = self.exif_wrapper.get_orientation(arw_path) if self.exif_wrapper else 1

        # 100% Full scale request: Use RawPy for maximum demosaiced detail if available
        if raw_scale >= 1.0 and rawpy is not None:
            try:
                use_cam_wb = (white_balance.lower() == "camera")
                use_auto_wb = (white_balance.lower() == "auto")
                with rawpy.imread(arw_path) as raw:
                    rgb = raw.postprocess(
                        use_camera_wb=use_cam_wb,
                        use_auto_wb=use_auto_wb,
                        half_size=False
                    )
                    full_img = Image.fromarray(rgb)
                    full_img = self.apply_exif_orientation(full_img, orientation=orientation)
                    full_img.load()
                    return full_img
            except Exception as e:
                print(f"RawPy 100% load error for {arw_path}: {e}")

        # ExifTool binary preview strategy (fast high-res embedded preview)
        if self.exif_wrapper and self.exif_wrapper.is_available():
            preview_bytes = self.exif_wrapper.extract_preview_bytes(arw_path)
            if preview_bytes:
                try:
                    with Image.open(io.BytesIO(preview_bytes)) as p_img:
                        img = self.apply_exif_orientation(p_img, orientation=orientation)
                        img = img.convert("RGB")
                        img.load()
                except Exception as e:
                    print(f"Failed decoding ExifTool preview bytes for {arw_path}: {e}")

        # RawPy fallback strategy
        if img is None and rawpy is not None:
            try:
                use_cam_wb = (white_balance.lower() == "camera")
                use_auto_wb = (white_balance.lower() == "auto")
                half_sz = (raw_scale <= 0.5)

                with rawpy.imread(arw_path) as raw:
                    rgb = raw.postprocess(
                        use_camera_wb=use_cam_wb,
                        use_auto_wb=use_auto_wb,
                        half_size=half_sz
                    )
                    img = Image.fromarray(rgb)
                    img = self.apply_exif_orientation(img, orientation=orientation)
                    img.load()
            except Exception as e:
                print(f"RawPy error loading {arw_path}: {e}")

        # Embedded preview JPEGs (1600x1080) are already ~25% scale of full raw resolution.
        # Only downscale if explicitly requesting ultra-small scale (e.g. for thumbnails).
        if img is not None:
            if raw_scale < 0.15:
                # Downsample embedded preview for thumbnail extraction while preserving aspect ratio
                max_thumb_dim = 400
                if max(img.width, img.height) > max_thumb_dim:
                    if img.width >= img.height:
                        target_w = max_thumb_dim
                        target_h = int(round(img.height * (max_thumb_dim / float(img.width))))
                    else:
                        target_h = max_thumb_dim
                        target_w = int(round(img.width * (max_thumb_dim / float(img.height))))
                    img = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
                    img.load()
            return img

        return None

    def get_thumbnail(
        self,
        file_path: Union[str, Path],
        max_size: Tuple[int, int] = (80, 80),
        raw_scale: float = 0.10,
        white_balance: str = "camera"
    ) -> Optional[Image.Image]:
        """
        Generates thumbnail resized to fit within max_size with LRU caching.
        Thumbnails are generated at a canonical size and cached keyed by (path, scale, WB).
        The requested max_size is applied as a fast final downscale if needed.
        Returns a standalone image copy safely loaded in RAM.
        """
        file_path_str = str(file_path)
        cache_key = (file_path_str, raw_scale, white_balance)

        # O(1) index lookup first
        indexed_key = self._thumb_cache_index.get(file_path_str)
        if indexed_key and indexed_key in self._thumb_cache:
            self._thumb_cache.move_to_end(indexed_key)
            cached = self._thumb_cache[indexed_key]
            if cached.size == max_size:
                return cached.copy()
            result = cached.copy()
            result.thumbnail(max_size, Image.Resampling.BILINEAR)
            result.load()
            return result

        ext = Path(file_path_str).suffix.lower()

        # Fast direct JPG thumbnail extraction (< 5ms) without allocating full image RAM
        if ext in [".jpg", ".jpeg"]:
            try:
                with Image.open(file_path_str) as raw_img:
                    raw_img.draft("RGB", (max_size[0] * 4, max_size[1] * 4))
                    raw_img = ImageOps.exif_transpose(raw_img)
                    img = raw_img.convert("RGB")
                    img.load()
                    if max(img.width, img.height) > 400:
                        img.thumbnail((400, 400), Image.Resampling.BILINEAR)
                        img.load()
            except Exception as e:
                print(f"Error extracting fast JPG thumbnail for {file_path_str}: {e}")
                img = None
        else:
            img = self.load_full_image(file_path_str, raw_scale=raw_scale, white_balance=white_balance)

        if img is None:
            return None

        self._thumb_cache[cache_key] = img
        self._thumb_cache_index[file_path_str] = cache_key
        self._thumb_cache.move_to_end(cache_key)

        if len(self._thumb_cache) > self.MAX_THUMB_CACHE:
            oldest = next(iter(self._thumb_cache))
            self._thumb_cache.popitem(last=False)
            self._thumb_cache_index.pop(oldest[0], None)

        if img.size == max_size:
            return img.copy()

        result = img.copy()
        result.thumbnail(max_size, Image.Resampling.BILINEAR)
        result.load()
        return result

    def get_yolo_model(self) -> Optional[Any]:
        """
        Lazily loads and caches YOLO subject detection model (yolov8n.pt).
        """
        if not hasattr(self, "_yolo_model") or self._yolo_model is None:
            try:
                from ultralytics import YOLO
                root_dir = Path(__file__).resolve().parent.parent
                models_dir = root_dir / "lib" / "models"
                models_dir.mkdir(parents=True, exist_ok=True)
                model_path = models_dir / "yolov8n.pt"
                # Ultralytics will automatically download to model_path if it doesn't exist
                self._yolo_model = YOLO(str(model_path))
            except Exception as e:
                print(f"Error loading YOLO model: {e}")
                self._yolo_model = None
        return self._yolo_model

    def get_yolo_pose_model(self) -> Optional[Any]:
        """
        Lazily loads and caches YOLO pose keypoint model (yolov8n-pose.pt) for eye detection.
        """
        if not hasattr(self, "_yolo_pose_model") or self._yolo_pose_model is None:
            try:
                from ultralytics import YOLO
                root_dir = Path(__file__).resolve().parent.parent
                models_dir = root_dir / "lib" / "models"
                models_dir.mkdir(parents=True, exist_ok=True)
                pose_path = models_dir / "yolov8n-pose.pt"
                # Ultralytics will automatically download to pose_path if it doesn't exist
                self._yolo_pose_model = YOLO(str(pose_path))
            except Exception as e:
                print(f"Error loading YOLO pose model: {e}")
                self._yolo_pose_model = None
        return self._yolo_pose_model

    def calculate_sharpness(self, pil_image_or_path: Union[Image.Image, str, Path], method: str = "laplacian", eye_detection_method: str = "yolo") -> float:
        """
        Calculate sharpness score using selected algorithm via culler.detectors.blur_detector module.
        """
        from .detectors.blur_detector import calculate_sharpness as calc_blur
        try:
            if isinstance(pil_image_or_path, (str, Path)):
                img = self.get_thumbnail(str(pil_image_or_path), max_size=(400, 400))
            else:
                img = pil_image_or_path

            if img is None:
                return 0.0

            yolo_model = self.get_yolo_model()
            yolo_pose_model = self.get_yolo_pose_model() if eye_detection_method == "yolo" else None
            score = calc_blur(
                img,
                method=method,
                yolo_model=yolo_model,
                eye_detection_method=eye_detection_method,
                yolo_pose_model=yolo_pose_model
            )
            return score
        except Exception as e:
            print(f"Error computing sharpness: {e}")
            return 0.0

    def clear_cache(self):
        """
        Purge all cached PIL image references from memory.
        """
        self._thumb_cache.clear()
        self._thumb_cache_index.clear()
        self._full_cache.clear()
