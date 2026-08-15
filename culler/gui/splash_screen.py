import os
import sys
import tkinter as tk
from typing import Optional
import customtkinter as ctk


class SplashScreen(ctk.CTkToplevel):
    """
    Lightweight, fast-launching dark mode splash screen for Fast Photo Culler.
    Appears immediately on startup with progress animation while components initialize.
    """

    def __init__(self, master=None, width: int = 460, height: int = 240, **kwargs):
        super().__init__(master, **kwargs)

        self.title("Fast Photo Culler")
        self.overrideredirect(True)
        self.configure(fg_color="#121212")

        # Center on screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)

        # Outer card frame with subtle border
        self.card = ctk.CTkFrame(
            self,
            corner_radius=10,
            border_width=2,
            border_color="#1f538d",
            fg_color="#1a1a1a"
        )
        self.card.pack(fill="both", expand=True, padx=2, pady=2)

        # App Title & Icon badge
        self.title_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.title_frame.pack(side="top", fill="x", padx=20, pady=(28, 6))

        self.lbl_title = ctk.CTkLabel(
            self.title_frame,
            text="FAST PHOTO CULLER",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#ffffff"
        )
        self.lbl_title.pack(anchor="center")

        self.lbl_subtitle = ctk.CTkLabel(
            self.card,
            text="Professional RAW+JPG Selection & Culling Engine",
            font=ctk.CTkFont(size=11),
            text_color="#8d99ae"
        )
        self.lbl_subtitle.pack(anchor="center", padx=20, pady=(0, 20))

        # Animated progress bar
        self.progress = ctk.CTkProgressBar(
            self.card,
            width=360,
            height=6,
            progress_color="#1f538d",
            mode="indeterminate"
        )
        self.progress.pack(anchor="center", padx=30, pady=(10, 8))
        self.progress.start()

        # Dynamic Status label
        self.lbl_status = ctk.CTkLabel(
            self.card,
            text="Initializing workspace...",
            font=ctk.CTkFont(size=11),
            text_color="#adb5bd"
        )
        self.lbl_status.pack(anchor="center", pady=(2, 8))

        # Version tag
        self.lbl_ver = ctk.CTkLabel(
            self.card,
            text="v1.0.0",
            font=ctk.CTkFont(size=9),
            text_color="#495057"
        )
        self.lbl_ver.pack(side="bottom", anchor="e", padx=14, pady=6)

        self.update_idletasks()
        try:
            self.update()
        except Exception:
            pass

    def set_status(self, message: str):
        """Update splash status text in real time."""
        try:
            self.lbl_status.configure(text=message)
            self.update_idletasks()
            self.update()
        except Exception:
            pass

    def close(self):
        """Cleanly stop animations and destroy the splash window."""
        try:
            self.progress.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
