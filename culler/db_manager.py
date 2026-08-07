import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


class DatabaseManager:
    """
    SQLite Database Manager for persisting application settings,
    window geometry (size & position), image culling history/ratings, and image tags.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path).resolve()
        else:
            base_dir = Path(__file__).resolve().parent.parent
            self.db_path = base_dir / "culler.db"

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """
        Initialize SQLite database tables if they do not exist.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Key-value app settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Image culling history table (persist ratings, flags, sharpness, & tags)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS image_records (
                    file_path TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    flag TEXT NOT NULL,
                    rating INTEGER NOT NULL DEFAULT 0,
                    sharpness REAL DEFAULT 0.0,
                    tags TEXT DEFAULT '',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migration check: Ensure tags column exists
            try:
                cursor.execute("ALTER TABLE image_records ADD COLUMN tags TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass

            conn.commit()

    # --- App Settings & Window State API ---

    def set_setting(self, key: str, value: Any):
        str_val = json.dumps(value) if not isinstance(value, str) else value
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (key, str_val, str_val)
            )
            conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            if row:
                val = row["value"]
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return val
            return default

    def get_window_geometry(self) -> Tuple[int, int, Optional[int], Optional[int], bool]:
        width = self.get_setting("window_width", default=1280)
        height = self.get_setting("window_height", default=800)
        pos_x = self.get_setting("window_x", default=None)
        pos_y = self.get_setting("window_y", default=None)
        is_max = self.get_setting("window_maximized", default=False)
        return int(width), int(height), pos_x, pos_y, bool(is_max)

    def save_window_geometry(self, width: int, height: int, x: Optional[int] = None, y: Optional[int] = None, is_maximized: bool = False):
        self.set_setting("window_width", width)
        self.set_setting("window_height", height)
        if x is not None:
            self.set_setting("window_x", x)
        if y is not None:
            self.set_setting("window_y", y)
        self.set_setting("window_maximized", is_maximized)

    def get_raw_scale(self) -> float:
        val = self.get_setting("raw_scale", default=0.25)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.25

    def set_raw_scale(self, scale: float):
        self.set_setting("raw_scale", float(scale))

    def get_white_balance(self) -> str:
        return self.get_setting("white_balance", default="camera")

    def set_white_balance(self, wb: str):
        self.set_setting("white_balance", wb)

    def get_jpg_save_folder(self) -> str:
        val = self.get_setting("jpg_save_folder", default="<source>")
        if val in ("source", "<source>", ""):
            return "<source>"
        return val

    def set_jpg_save_folder(self, folder_path: str):
        val = (folder_path or "").strip()
        if val.lower() in ("source", "<source>", ""):
            val = "<source>"
        self.set_setting("jpg_save_folder", val)

    def get_stack_raw_jpg(self) -> bool:
        return self.get_setting("stack_raw_jpg", default=True)

    def set_stack_raw_jpg(self, enabled: bool):
        self.set_setting("stack_raw_jpg", enabled)

    def get_picked_folder(self) -> str:
        return self.get_setting("picked_folder", default="_SELECTED")

    def set_picked_folder(self, folder_name: str):
        self.set_setting("picked_folder", folder_name)

    def get_rejected_folder(self) -> str:
        return self.get_setting("rejected_folder", default="_REJECTED")

    def set_rejected_folder(self, folder_name: str):
        self.set_setting("rejected_folder", folder_name)

    def get_blur_method(self) -> str:
        return self.get_setting("blur_method", default="laplacian")

    def set_blur_method(self, method: str):
        self.set_setting("blur_method", method)

    def get_blur_percentile(self) -> float:
        try:
            return float(self.get_setting("blur_percentile", default=15.0))
        except Exception:
            return 15.0

    def set_blur_percentile(self, percentile: float):
        self.set_setting("blur_percentile", percentile)

    def get_duplicate_method(self) -> str:
        return self.get_setting("duplicate_method", default="dhash")

    def set_duplicate_method(self, method: str):
        self.set_setting("duplicate_method", method)

    def get_duplicate_threshold(self) -> float:
        try:
            return float(self.get_setting("duplicate_threshold", default=6.0))
        except Exception:
            return 6.0

    def set_duplicate_threshold(self, threshold: float):
        self.set_setting("duplicate_threshold", threshold)

    # Blur Action Preferences
    def get_blur_flag_action(self) -> str:
        return self.get_setting("blur_flag_action", default="Reject")

    def set_blur_flag_action(self, action: str):
        self.set_setting("blur_flag_action", action)

    def get_blur_tag_action(self) -> str:
        return self.get_setting("blur_tag_action", default="Blur")

    def set_blur_tag_action(self, tag: str):
        self.set_setting("blur_tag_action", tag)

    def get_blur_rating_action(self) -> str:
        return self.get_setting("blur_rating_action", default="None")

    def set_blur_rating_action(self, rating_str: str):
        self.set_setting("blur_rating_action", rating_str)

    # Duplicate Action Preferences
    def get_duplicate_flag_action(self) -> str:
        return self.get_setting("duplicate_flag_action", default="Reject")

    def set_duplicate_flag_action(self, action: str):
        self.set_setting("duplicate_flag_action", action)

    def get_duplicate_tag_action(self) -> str:
        return self.get_setting("duplicate_tag_action", default="Duplicate")

    def set_duplicate_tag_action(self, tag: str):
        self.set_setting("duplicate_tag_action", tag)

    def get_duplicate_rating_action(self) -> str:
        return self.get_setting("duplicate_rating_action", default="None")

    def set_duplicate_rating_action(self, rating_str: str):
        self.set_setting("duplicate_rating_action", rating_str)

    # --- Image Record Persistence & Cleanup API ---

    def save_image_record(self, file_path: str, filename: str, flag: str, rating: int = 0, sharpness: float = 0.0, tags: str = ""):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO image_records (file_path, filename, flag, rating, sharpness, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    flag = excluded.flag,
                    rating = excluded.rating,
                    sharpness = excluded.sharpness,
                    tags = excluded.tags,
                    last_updated = CURRENT_TIMESTAMP
            """, (file_path, filename, flag, rating, sharpness, tags))
            conn.commit()

    def get_all_records_for_dir(self, dir_path: str) -> Dict[str, Dict[str, Any]]:
        clean_dir = str(Path(dir_path).resolve())
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM image_records WHERE file_path LIKE ?", (clean_dir + "%",)).fetchall()
            records = {}
            for r in rows:
                norm_key = str(Path(r["file_path"]).resolve())
                records[norm_key] = {
                    "filename": r["filename"],
                    "flag": r["flag"],
                    "rating": r["rating"],
                    "sharpness": r["sharpness"],
                    "tags": r["tags"] if "tags" in r.keys() else "",
                }
            return records

    def cleanup_folder_metadata(self, folder_path: str) -> int:
        """
        Delete SQLite metadata records for a folder hierarchy and all its subfolders.
        """
        clean_prefix = str(Path(folder_path).resolve())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM image_records WHERE file_path LIKE ?", (clean_prefix + "%",))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def get_stored_folders_summary(self) -> Dict[str, Dict[str, int]]:
        """
        Return a hierarchical summary of all folders and their record counts stored in SQLite database.
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT file_path, flag FROM image_records").fetchall()
            summary: Dict[str, Dict[str, int]] = {}

            for r in rows:
                p = Path(r["file_path"])
                folder_str = str(p.parent)

                if folder_str not in summary:
                    summary[folder_str] = {"total": 0, "pick": 0, "reject": 0, "unflagged": 0}

                summary[folder_str]["total"] += 1
                flag_val = r["flag"].upper()
                if flag_val == "PICK":
                    summary[folder_str]["pick"] += 1
                elif flag_val == "REJECT":
                    summary[folder_str]["reject"] += 1
                else:
                    summary[folder_str]["unflagged"] += 1

            return summary

    def cleanup_multiple_folders(self, folder_paths: List[str]) -> int:
        """
        Delete SQLite metadata records for a list of specified folder paths.
        """
        if not folder_paths:
            return 0

        total_deleted = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for fp in folder_paths:
                clean_prefix = str(Path(fp).resolve())
                cursor.execute("DELETE FROM image_records WHERE file_path LIKE ?", (clean_prefix + "%",))
                total_deleted += cursor.rowcount
            conn.commit()

        return total_deleted

    def cleanup_entire_database(self) -> int:
        """
        Delete ALL stored metadata records in image_records.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM image_records")
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def cleanup_missing_files_metadata(self) -> int:
        """
        Clean up metadata records for files that no longer exist on disk.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT file_path FROM image_records").fetchall()
            missing = [r["file_path"] for r in rows if not Path(r["file_path"]).exists()]
            for p in missing:
                cursor.execute("DELETE FROM image_records WHERE file_path = ?", (p,))
            conn.commit()
            return len(missing)
