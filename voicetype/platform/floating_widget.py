#!/usr/bin/env python3
# Copyright (C) 2026 VoiceType Contributors
# Licensed under AGPL-3.0

"""
Desktop floating waveform widget for VoiceType.
An always-on-top audio waveform bar that visualizes recording state.
Cross-platform: Windows, macOS, Linux (uses tkinter, built-in with Python).

States:
  - standby:   teal bars on dark bg, gentle idle sway
  - recording: bright red/orange bars on dark-red bg, energetic chaotic wave
  - loading:   electric blue bars on dark-blue bg, smooth sine ripple
"""

import logging
import math
import random
import sys
import tkinter as tk
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# --- Layout ---
BAR_COUNT = 9
BAR_WIDTH = 4
BAR_GAP = 3
BAR_MAX_H = 32
BAR_MIN_H = 4
PADDING_X = 14
PADDING_Y = 8
CORNER_RADIUS = 12

WIDGET_W = PADDING_X * 2 + BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_GAP
WIDGET_H = PADDING_Y * 2 + BAR_MAX_H

ANIM_INTERVAL_MS = 50

# --- Color Schemes (more vivid & distinct) ---
COLORS = {
    "standby": {
        "bars": ["#36cfc9", "#5cdbd3", "#87e8de", "#b5f5ec", "#87e8de",
                 "#b5f5ec", "#87e8de", "#5cdbd3", "#36cfc9"],
        "bg": "#112121",
    },
    "recording": {
        "bars": ["#ff4d4f", "#ff7a45", "#ffa940", "#ffc53d", "#ffa940",
                 "#ffc53d", "#ffa940", "#ff7a45", "#ff4d4f"],
        "bg": "#2a1215",
    },
    "loading": {
        "bars": ["#1890ff", "#40a9ff", "#69c0ff", "#91d5ff", "#69c0ff",
                 "#91d5ff", "#69c0ff", "#40a9ff", "#1890ff"],
        "bg": "#111d2c",
    },
}

_TRANSPARENT_KEY = "#010101"


class FloatingWidget:
    """
    Floating audio waveform indicator.
    Must be started via run() in a dedicated thread (blocks on tkinter mainloop).
    """

    def __init__(
        self,
        on_toggle: Optional[Callable] = None,
        on_open_settings: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
    ):
        self._on_toggle = on_toggle
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit

        self._state = "loading"
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._bar_ids: list[int] = []
        self._bg_rect_id = None
        self._tooltip_win: Optional[tk.Toplevel] = None

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._dragging = False

        self._bar_heights = [BAR_MIN_H] * BAR_COUNT
        self._bar_targets = [BAR_MIN_H] * BAR_COUNT
        # Each bar has independent phase/speed for organic movement
        self._bar_phases = [random.uniform(0, math.tau) for _ in range(BAR_COUNT)]
        self._bar_speeds = [random.uniform(0.08, 0.18) for _ in range(BAR_COUNT)]

        self._anim_tick = 0
        self._running = False

    def run(self):
        self._running = True
        try:
            self._root = tk.Tk()
        except tk.TclError as e:
            logger.warning("Cannot create tkinter window: %s", e)
            return

        self._root.title("VoiceType")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)

        if sys.platform == "win32":
            self._root.attributes("-transparentcolor", _TRANSPARENT_KEY)
            self._root.config(bg=_TRANSPARENT_KEY)
            canvas_bg = _TRANSPARENT_KEY
        else:
            canvas_bg = COLORS["loading"]["bg"]
            self._root.config(bg=canvas_bg)
            try:
                self._root.attributes("-transparent", True)
                self._root.config(bg="systemTransparent")
                canvas_bg = "systemTransparent"
            except tk.TclError:
                pass

        self._canvas = tk.Canvas(
            self._root,
            width=WIDGET_W,
            height=WIDGET_H,
            bg=canvas_bg,
            highlightthickness=0,
            cursor="hand2",
        )
        self._canvas.pack()

        self._draw_bg(COLORS["loading"]["bg"])

        for i in range(BAR_COUNT):
            x = PADDING_X + i * (BAR_WIDTH + BAR_GAP)
            h = BAR_MIN_H
            y_top = PADDING_Y + (BAR_MAX_H - h)
            y_bot = PADDING_Y + BAR_MAX_H
            bar_id = self._canvas.create_rectangle(
                x, y_top, x + BAR_WIDTH, y_bot,
                fill=COLORS["loading"]["bars"][i % len(COLORS["loading"]["bars"])],
                outline="",
            )
            self._bar_ids.append(bar_id)

        # Position: bottom-center of screen
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = (screen_w - WIDGET_W) // 2
        y = screen_h - WIDGET_H - 100
        self._root.geometry(f"{WIDGET_W}x{WIDGET_H}+{x}+{y}")

        self._canvas.bind("<Button-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Button-3>", self._on_right_click)
        self._canvas.bind("<Enter>", self._on_enter)
        self._canvas.bind("<Leave>", self._on_leave)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._animate()

        logger.info("Floating widget started")
        self._root.mainloop()

    def stop(self):
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def set_state(self, state: str):
        if state not in COLORS:
            return
        self._state = state
        if self._root and self._running:
            try:
                self._root.after(0, self._apply_colors)
            except Exception:
                pass

    def _draw_bg(self, color: str):
        if self._bg_rect_id:
            self._canvas.delete(self._bg_rect_id)

        r = CORNER_RADIUS
        w, h = WIDGET_W, WIDGET_H
        points = [
            r, 0, w - r, 0, w, 0, w, r,
            w, h - r, w, h, w - r, h,
            r, h, 0, h, 0, h - r,
            0, r, 0, 0, r, 0,
        ]
        self._bg_rect_id = self._canvas.create_polygon(
            points, fill=color, outline="", smooth=True,
        )
        self._canvas.tag_lower(self._bg_rect_id)

    def _apply_colors(self):
        if not self._canvas:
            return
        scheme = COLORS[self._state]
        self._draw_bg(scheme["bg"])
        for i, bar_id in enumerate(self._bar_ids):
            self._canvas.itemconfig(bar_id, fill=scheme["bars"][i % len(scheme["bars"])])

    def _animate(self):
        if not self._running or not self._root:
            return

        self._anim_tick += 1
        t = self._anim_tick

        if self._state == "recording":
            for i in range(BAR_COUNT):
                self._bar_phases[i] += self._bar_speeds[i]
                # Layered noise: slow sine + fast jitter
                base = 0.5 + 0.35 * math.sin(self._bar_phases[i])
                jitter = random.uniform(-0.15, 0.15)
                # Occasional spike for energy feel
                spike = 0.2 if random.random() < 0.08 else 0
                ratio = max(0.1, min(1.0, base + jitter + spike))
                self._bar_targets[i] = int(BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * ratio)

        elif self._state == "loading":
            for i in range(BAR_COUNT):
                phase = t * 0.1 + i * 0.9
                ratio = 0.25 + 0.3 * math.sin(phase)
                self._bar_targets[i] = int(BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * ratio)

        else:  # standby
            for i in range(BAR_COUNT):
                phase = t * 0.04 + i * 0.7
                ratio = 0.12 + 0.08 * math.sin(phase)
                self._bar_targets[i] = int(BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * ratio)

        # Smooth interpolation with different speeds per state
        lerp = 0.45 if self._state == "recording" else 0.25
        for i in range(BAR_COUNT):
            diff = self._bar_targets[i] - self._bar_heights[i]
            self._bar_heights[i] += diff * lerp

            h = max(BAR_MIN_H, int(self._bar_heights[i]))
            x = PADDING_X + i * (BAR_WIDTH + BAR_GAP)
            y_top = PADDING_Y + (BAR_MAX_H - h)
            y_bot = PADDING_Y + BAR_MAX_H
            self._canvas.coords(self._bar_ids[i], x, y_top, x + BAR_WIDTH, y_bot)

        self._root.after(ANIM_INTERVAL_MS, self._animate)

    # --- Mouse events ---

    def _on_press(self, event):
        self._drag_start_x = event.x_root - self._root.winfo_x()
        self._drag_start_y = event.y_root - self._root.winfo_y()
        self._dragging = False

    def _on_drag(self, event):
        self._dragging = True
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self._root.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._dragging and self._on_toggle:
            # Visual feedback: brief color flash
            if self._canvas:
                original_cursor = self._canvas.cget("cursor")
                self._canvas.config(cursor="wait")
                self._root.after(100, lambda: self._canvas.config(cursor=original_cursor) if self._canvas else None)
            
            self._on_toggle()
        self._dragging = False

    def _on_right_click(self, event):
        menu = tk.Menu(self._root, tearoff=0)
        labels = {
            "standby": "Standby",
            "recording": "Recording...",
            "loading": "Loading...",
        }
        menu.add_command(label=labels.get(self._state, ""), state="disabled")
        menu.add_separator()
        menu.add_command(label="Settings", command=self._open_settings)
        menu.add_command(label="Quit", command=self._quit)
        menu.tk_popup(event.x_root, event.y_root)

    def _on_enter(self, event):
        self._show_tooltip()

    def _on_leave(self, event):
        self._hide_tooltip()

    def _show_tooltip(self):
        if self._tooltip_win:
            return
        texts = {
            "standby": "VoiceType - Click to record",
            "recording": "Recording - Click to stop",
            "loading": "VoiceType - Starting...",
        }
        text = texts.get(self._state, "VoiceType")

        self._tooltip_win = tw = tk.Toplevel(self._root)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        label = tk.Label(
            tw, text=text,
            bg="#262626", fg="white",
            font=("Segoe UI", 9) if sys.platform == "win32" else ("Arial", 11),
            padx=8, pady=4,
        )
        label.pack()

        wx = self._root.winfo_x()
        wy = self._root.winfo_y() - 30
        tw.geometry(f"+{wx}+{wy}")

    def _hide_tooltip(self):
        if self._tooltip_win:
            self._tooltip_win.destroy()
            self._tooltip_win = None

    def _open_settings(self):
        if self._on_open_settings:
            self._on_open_settings()

    def _quit(self):
        if self._on_quit:
            self._on_quit()

    def _on_close(self):
        self.stop()
