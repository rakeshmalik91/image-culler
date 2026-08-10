import time
from typing import Optional, Callable
import customtkinter as ctk


class ProgressDialog(ctk.CTkToplevel):
    """
    Modal Progress Window for long-running scan operations (Blur & Duplicate scans).
    Displays progress bar, processed / total photo counts, elapsed time, and ETA remaining time.
    """

    def __init__(
        self,
        master,
        title_text: str = "Scanning Directory...",
        header_text: str = "🔍 Running Analysis Scan...",
        on_cancel: Optional[Callable[[], None]] = None
    ):
        super().__init__(master)
        self.on_cancel_callback = on_cancel
        self.is_cancelled = False
        self.start_time = time.time()

        self.title(title_text)
        self.geometry("480x230")
        self.resizable(False, False)

        # Make modal dialog window
        self.transient(master)
        self.grab_set()

        self.bind("<Escape>", lambda e: self._handle_cancel())

        self._build_widgets(header_text)
        self.after(10, self._center_window)

    def _center_window(self):
        self.update_idletasks()
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w = self.winfo_width()
            h = self.winfo_height()

            if w <= 0 or h <= 0:
                return

            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build_widgets(self, header_text: str):
        # Header Label
        self.lbl_header = ctk.CTkLabel(
            self,
            text=header_text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#3a86ff"
        )
        self.lbl_header.pack(anchor="w", padx=20, pady=(16, 6))

        # Current Item Label
        self.lbl_item = ctk.CTkLabel(
            self,
            text="Preparing scan...",
            font=ctk.CTkFont(size=11),
            text_color="#cccccc",
            anchor="w"
        )
        self.lbl_item.pack(fill="x", padx=20, pady=(0, 8))

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, height=14, corner_radius=7, fg_color="#2b2b2b", progress_color="#3a86ff")
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=20, pady=4)

        # Counts & Percentage Row
        self.lbl_counts = ctk.CTkLabel(
            self,
            text="Photos: 0 / 0 (0%)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffffff"
        )
        self.lbl_counts.pack(anchor="w", padx=20, pady=(6, 2))

        # Time Elapsed / ETA Row
        self.lbl_time = ctk.CTkLabel(
            self,
            text="⏱️ Elapsed: 00:00   |   ⌛ Remaining: --",
            font=ctk.CTkFont(size=11),
            text_color="#ffb703"
        )
        self.lbl_time.pack(anchor="w", padx=20, pady=(0, 10))

        # Bottom Cancel Button Bar
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(side="bottom", fill="x", padx=20, pady=(0, 14))

        self.btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancel Scan",
            width=100,
            height=28,
            fg_color="#4a4e69",
            hover_color="#d90429",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._handle_cancel
        )
        self.btn_cancel.pack(side="right")

    def update_progress(self, completed: int, total: int, current_filename: str = ""):
        """
        Thread-safe UI updater called periodically during background scanning.
        """
        if total <= 0:
            return

        now = time.time()
        elapsed_sec = now - self.start_time
        pct = completed / total

        # Format elapsed mm:ss
        em, es = divmod(int(elapsed_sec), 60)
        elapsed_str = f"{em:02d}:{es:02d}"

        # Estimate remaining ETA
        remaining_items = total - completed
        if completed > 0 and remaining_items > 0:
            avg_sec = elapsed_sec / completed
            eta_sec = int(remaining_items * avg_sec)
            rm, rs = divmod(eta_sec, 60)
            if rm > 0:
                eta_str = f"~{rm}m {rs:02d}s"
            else:
                eta_str = f"~{rs}s"
        else:
            eta_str = "Calculating..."

        fn_display = current_filename if len(current_filename) <= 45 else f"...{current_filename[-42:]}"

        try:
            self.progress_bar.set(pct)
            self.lbl_item.configure(text=f"Processing: {fn_display}" if fn_display else "Scanning...")
            self.lbl_counts.configure(text=f"Photos: {completed} / {total} ({int(pct * 100)}%)")
            self.lbl_time.configure(text=f"⏱️ Elapsed: {elapsed_str}   |   ⌛ Remaining: {eta_str} ({remaining_items} left)")
        except Exception:
            pass

    def _handle_cancel(self):
        self.is_cancelled = True
        if self.on_cancel_callback:
            self.on_cancel_callback()
        self.destroy()
