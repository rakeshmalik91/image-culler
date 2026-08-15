import os
import sys
import json
import io
import struct
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image


def _run_cli(cmd, **kwargs):
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


class ExifToolWrapper:
    """
    Wrapper for ExifTool binary executable.
    Provides fast batch metadata extraction, star rating updates,
    and ultra-fast embedded ARW preview extraction.
    """

    def __init__(self, exiftool_path: Optional[str] = None):
        if exiftool_path:
            self.exiftool_path = str(Path(exiftool_path).resolve())
        else:
            self.exiftool_path = self._find_default_exiftool()
        self._orientation_cache: Dict[Tuple[str, float], int] = {}

    def _find_default_exiftool(self) -> str:
        # Check PyInstaller bundle or workspace lib/exif-tools directory
        base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        bundled_exe = base_dir / "lib" / "exif-tools" / "exiftool.exe"
        if bundled_exe.exists():
            return str(bundled_exe)

        # Fallback to system exiftool
        return "exiftool"

    def is_available(self) -> bool:
        try:
            res = _run_cli([self.exiftool_path, "-ver"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _get_tiff_orientation_pure_py(file_path: str) -> Optional[int]:
        """
        Parse IFD0 Orientation tag (0x0112) from TIFF/RAW header in < 1 ms without external dependencies.
        Supports Sony ARW, DNG, NEF, CR2, CR3, TIFF formats.
        Returns int (1..8) if tag is found, or None if tag/header is absent.
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
                if len(header) < 8:
                    return None
                if header[:2] == b"II":
                    endian = "<"
                elif header[:2] == b"MM":
                    endian = ">"
                else:
                    return None
                magic = struct.unpack(endian + "H", header[2:4])[0]
                if magic not in (42, 0x4352):
                    return None
                ifd0_offset = struct.unpack(endian + "I", header[4:8])[0]
                f.seek(ifd0_offset)
                num_entries_bytes = f.read(2)
                if len(num_entries_bytes) < 2:
                    return None
                num_entries = struct.unpack(endian + "H", num_entries_bytes)[0]
                for _ in range(num_entries):
                    entry = f.read(12)
                    if len(entry) < 12:
                        break
                    tag, ftype, count = struct.unpack(endian + "HHI", entry[:8])
                    if tag == 0x0112:  # Orientation tag
                        val = struct.unpack(endian + "H", entry[8:10])[0]
                        return val if 1 <= val <= 8 else 1
        except Exception:
            pass
        return None

    def get_orientation(self, image_path: str) -> int:
        """
        Extract EXIF orientation integer (1..8) for an image file.
        Fast lookup using pure Python TIFF header parsing for RAW/TIFF files (< 0.05ms),
        PIL getexif for JPEGs/PNGs (< 0.1ms), falling back to ExifTool CLI process only if needed.
        Results are cached by (path, mtime) to avoid repeated I/O.
        """
        if not image_path or not os.path.exists(image_path):
            return 1

        cache_key = (str(Path(image_path).resolve()), os.path.getmtime(image_path))
        if cache_key in self._orientation_cache:
            return self._orientation_cache[cache_key]

        result = 1

        # 1. Fast pure Python TIFF header parser for ARW/RAW/TIFF (< 0.05ms, zero subprocesses!)
        try:
            ext = Path(image_path).suffix.lower()
            if ext in [".arw", ".tif", ".tiff", ".dng", ".nef", ".cr2", ".cr3"]:
                orient = self._get_tiff_orientation_pure_py(image_path)
                if orient is not None:
                    result = orient
                    self._orientation_cache[cache_key] = result
                    return result
        except Exception:
            pass

        # 2. Fast PIL getexif lookup for JPG/PNG/HEIC (< 0.1ms, zero subprocesses!)
        try:
            with Image.open(image_path) as img:
                exif = img.getexif()
                if exif and 0x0112 in exif:
                    val_int = int(exif[0x0112])
                    if 1 <= val_int <= 8:
                        result = val_int
                        self._orientation_cache[cache_key] = result
                        return result
        except Exception:
            pass

        # 3. ExifTool CLI fallback process (ONLY as last resort if pure Python & PIL return no data)
        if self.is_available():
            try:
                cmd = [
                    self.exiftool_path,
                    "-json",
                    "-n",
                    "-Orientation",
                    "-IFD0:Orientation",
                    "-EXIF:Orientation",
                    str(image_path)
                ]
                res = _run_cli(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0 and res.stdout:
                    raw_list = json.loads(res.stdout)
                    if raw_list:
                        item = raw_list[0]
                        val = item.get("Orientation") or item.get("IFD0:Orientation") or item.get("EXIF:Orientation")
                        if val is not None:
                            val_int = int(val)
                            if 1 <= val_int <= 8:
                                result = val_int
            except Exception:
                pass

        self._orientation_cache[cache_key] = result
        return result

    def extract_preview_bytes(self, arw_path: str, min_width: int = 1200) -> Optional[bytes]:
        """
        Extract embedded high-resolution JPEG preview from Sony ARW file.
        Uses fast pure Python binary header extraction with PIL verification,
        falling back to ExifTool process if needed.
        """
        # Strategy 1: Pure Python binary header extraction with PIL verification
        try:
            with open(arw_path, "rb") as f:
                data = f.read()
                idx = 0
                best_bytes = None
                best_w = 0
                while True:
                    soi = data.find(b"\xff\xd8\xff", idx)
                    if soi == -1:
                        break
                    eoi = data.find(b"\xff\xd9", soi + 1000)
                    if eoi != -1:
                        jpeg_bytes = data[soi : eoi + 2]
                        if len(jpeg_bytes) > 50000:
                            try:
                                im = Image.open(io.BytesIO(jpeg_bytes))
                                w, h = im.size
                                if w >= min_width:
                                    return jpeg_bytes
                                elif w > best_w:
                                    best_bytes = jpeg_bytes
                                    best_w = w
                            except Exception:
                                pass
                    idx = soi + 4

                if best_bytes and best_w >= 800:
                    return best_bytes
        except Exception:
            pass

        # Strategy 2: ExifTool binary process fallback
        if not self.is_available():
            return None

        tag_options = ["-PreviewImage", "-JpgFromRaw"]
        for tag in tag_options:
            try:
                cmd = [self.exiftool_path, "-b", tag, str(arw_path)]
                res = _run_cli(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0 and len(res.stdout) > 50000:
                    try:
                        im = Image.open(io.BytesIO(res.stdout))
                        im.verify()
                        return res.stdout
                    except Exception:
                        pass
            except Exception:
                continue
        return None

    def get_metadata(self, image_path: str) -> Dict[str, Any]:
        """
        Read detailed metadata for a single image file.
        """
        batch_res = self.get_batch_metadata([image_path])
        if batch_res:
            return batch_res[0]
        return {}

    def get_batch_metadata(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Read metadata for multiple image files in a single fast ExifTool process.
        """
        if not image_paths:
            return [{} for _ in image_paths]

        if not self.is_available():
            return [self._get_pil_fallback_metadata(p) for p in image_paths]

        try:
            cmd = [
                self.exiftool_path,
                "-json",
                "-G1",
                "-n",
                "-FileType",
                "-ImageWidth",
                "-ImageHeight",
                "-Orientation",
                "-Rating",
                "-Make",
                "-Model",
                "-LensModel",
                "-LensID",
                "-LensSpec",
                "-ISO",
                "-ExposureTime",
                "-ShutterSpeed",
                "-FNumber",
                "-Aperture",
                "-FocalLength",
                "-DateTimeOriginal",
                "-CreateDate"
            ] + [str(p) for p in image_paths]

            res = _run_cli(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0 or not res.stdout:
                return [self._get_pil_fallback_metadata(p) for p in image_paths]

            raw_list = json.loads(res.stdout)
            meta_map = {}

            def _get_tag(item_dict: dict, *keys):
                for k in keys:
                    if k in item_dict and item_dict[k] is not None and str(item_dict[k]).strip() != "":
                        return item_dict[k]
                return None

            for item in raw_list:
                raw_src = item.get("SourceFile", "")
                if not raw_src:
                    continue

                try:
                    norm_key = str(Path(raw_src).resolve()).lower()
                except Exception:
                    norm_key = raw_src.replace("/", "\\").lower()

                # Orientation
                orient_val = _get_tag(item, "IFD0:Orientation", "EXIF:Orientation", "ExifIFD:Orientation", "Composite:Orientation", "Orientation")
                try:
                    orient_num = int(orient_val) if orient_val is not None else 1
                except Exception:
                    orient_num = 1

                # Shutter Speed
                shutter = _get_tag(item, "ExifIFD:ExposureTime", "EXIF:ExposureTime", "Composite:ExposureTime", "Composite:ShutterSpeed", "ExposureTime")
                if shutter is not None:
                    try:
                        sh_val = float(shutter)
                        shutter_str = f"1/{int(round(1.0 / sh_val))}s" if sh_val < 1.0 else f"{sh_val:g}s"
                    except Exception:
                        shutter_str = str(shutter)
                else:
                    shutter_str = "N/A"

                # Aperture
                fnumber = _get_tag(item, "ExifIFD:FNumber", "EXIF:FNumber", "Composite:FNumber", "Composite:Aperture", "FNumber")
                if fnumber is not None:
                    try:
                        fnum_str = f"f/{float(fnumber):.1f}"
                    except Exception:
                        fnum_str = str(fnumber)
                else:
                    fnum_str = "N/A"

                # Camera Model
                make = _get_tag(item, "IFD0:Make", "EXIF:Make", "Make")
                model = _get_tag(item, "IFD0:Model", "ExifIFD:Model", "EXIF:Model", "Model")
                if model:
                    model_str = str(model)
                    if make and str(make) not in model_str:
                        model_str = f"{make} {model_str}"
                else:
                    model_str = "N/A"

                # Lens Model
                lens = _get_tag(item, "ExifIFD:LensModel", "Composite:LensModel", "Composite:LensID", "Composite:LensSpec", "LensModel")
                lens_str = str(lens) if lens else "N/A"

                # ISO
                iso = _get_tag(item, "ExifIFD:ISO", "EXIF:ISO", "IFD0:ISO", "MakerNotes:ISO", "ISO")
                iso_str = str(iso) if iso is not None else "N/A"

                # Focal Length
                focal = _get_tag(item, "ExifIFD:FocalLength", "EXIF:FocalLength", "Composite:FocalLength", "FocalLength")
                if focal is not None:
                    try:
                        focal_str = f"{float(focal):g}mm"
                    except Exception:
                        focal_str = f"{focal}mm"
                else:
                    focal_str = "N/A"

                # Date Taken
                date_taken = _get_tag(item, "ExifIFD:DateTimeOriginal", "EXIF:DateTimeOriginal", "IFD0:DateTimeOriginal", "ExifIFD:CreateDate", "DateTimeOriginal", "CreateDate")
                date_str = str(date_taken) if date_taken else "N/A"

                # Rating
                rating_val = _get_tag(item, "XMP:Rating", "IFD0:Rating", "ExifIFD:Rating", "Rating")
                try:
                    rating_num = int(rating_val) if rating_val is not None else 0
                except Exception:
                    rating_num = 0

                meta_map[norm_key] = {
                    "file_type": str(_get_tag(item, "File:FileType", "FileType") or "N/A"),
                    "orientation": orient_num,
                    "width": int(_get_tag(item, "File:ImageWidth", "ImageWidth") or 0),
                    "height": int(_get_tag(item, "File:ImageHeight", "ImageHeight") or 0),
                    "rating": rating_num,
                    "model": model_str,
                    "lens": lens_str,
                    "iso": iso_str,
                    "shutter_speed": shutter_str,
                    "aperture": fnum_str,
                    "focal_length": focal_str,
                    "date_taken": date_str,
                }

            result = []
            for p in image_paths:
                try:
                    lookup_key = str(Path(p).resolve()).lower()
                except Exception:
                    lookup_key = str(p).replace("/", "\\").lower()

                item_meta = meta_map.get(lookup_key)
                if not item_meta:
                    item_meta = self._get_pil_fallback_metadata(p)
                result.append(item_meta)

            return result

        except Exception as e:
            print(f"ExifTool batch metadata error: {e}")
            return [self._get_pil_fallback_metadata(p) for p in image_paths]

    def _get_pil_fallback_metadata(self, image_path: str) -> Dict[str, Any]:
        """
        Pure Python PIL fallback for extracting EXIF metadata when ExifTool is unavailable.
        """
        res = {
            "file_type": Path(image_path).suffix.upper().lstrip("."),
            "orientation": self.get_orientation(image_path),
            "width": 0,
            "height": 0,
            "rating": 0,
            "model": "N/A",
            "lens": "N/A",
            "iso": "N/A",
            "shutter_speed": "N/A",
            "aperture": "N/A",
            "focal_length": "N/A",
            "date_taken": "N/A",
        }
        try:
            with Image.open(image_path) as img:
                res["width"], res["height"] = img.size
                exif_data = img._getexif() if hasattr(img, "_getexif") else None
                if exif_data:
                    from PIL.ExifTags import TAGS
                    exif = {TAGS.get(k, k): v for k, v in exif_data.items()}

                    make = exif.get("Make", "")
                    model = exif.get("Model", "")
                    if model:
                        res["model"] = f"{make} {model}".strip() if make and make not in model else model

                    if "LensModel" in exif:
                        res["lens"] = str(exif["LensModel"])

                    if "ISOSpeedRatings" in exif:
                        res["iso"] = str(exif["ISOSpeedRatings"])

                    if "ExposureTime" in exif:
                        try:
                            exp = float(exif["ExposureTime"])
                            res["shutter_speed"] = f"1/{int(round(1.0/exp))}s" if exp < 1.0 else f"{exp:g}s"
                        except Exception:
                            res["shutter_speed"] = str(exif["ExposureTime"])

                    if "FNumber" in exif:
                        try:
                            res["aperture"] = f"f/{float(exif['FNumber']):.1f}"
                        except Exception:
                            res["aperture"] = str(exif["FNumber"])

                    if "FocalLength" in exif:
                        try:
                            res["focal_length"] = f"{float(exif['FocalLength']):g}mm"
                        except Exception:
                            res["focal_length"] = str(exif["FocalLength"])

                    if "DateTimeOriginal" in exif:
                        res["date_taken"] = str(exif["DateTimeOriginal"])
        except Exception:
            pass

        return res

    def write_rating(self, image_path: str, rating: int) -> bool:
        """
        Write star rating back into image file EXIF/XMP metadata using ExifTool.
        """
        if not self.is_available() or not (0 <= rating <= 5):
            return False

        try:
            cmd = [
                self.exiftool_path,
                "-overwrite_original",
                f"-XMP:Rating={rating}",
                f"-IFD0:Rating={rating}",
                str(image_path)
            ]
            res = _run_cli(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return res.returncode == 0
        except Exception as e:
            print(f"Error writing rating to {image_path}: {e}")
            return False

