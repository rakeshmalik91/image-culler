import tkinter as tk
from typing import Optional


class ToolTip:
    """
    Sleek dark-mode hover tooltip for CustomTkinter & Tkinter widgets.
    Displays shortcut hints and helpful descriptions on mouse hover.
    """

    def __init__(self, widget, text: str, delay_ms: int = 350):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tooltip_window: Optional[tk.Toplevel] = None
        self._timer_id: Optional[str] = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._schedule()

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _schedule(self):
        self._cancel()
        if hasattr(self.widget, "after"):
            self._timer_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._timer_id:
            try:
                self.widget.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def _show(self):
        if self.tooltip_window or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 30
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

            tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)

            label = tk.Label(
                tw,
                text=self.text,
                justify="center",
                background="#1e1e24",
                foreground="#ffd166",
                relief="solid",
                border=1,
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=4
            )
            label.pack()
            self.tooltip_window = tw
        except Exception:
            self.tooltip_window = None

    def _hide(self):
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None
