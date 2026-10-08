from __future__ import annotations

import base64
import tkinter as tk
from typing import Callable

import cv2
import numpy as np

from .config import Calibration

STEPS = (
    "Étape 1/2 : entoure un élément FIXE du popup (titre, logo), sans texte variable",
    "Étape 2/2 : entoure uniquement la durée du combat",
)
CANCEL_HINT = "   (Échap ou clic droit : annuler)"
MIN_SIZE = 8
MIN_CONTRAST = 8  # écart-type minimal de l'ancre, sinon la détection est peu fiable


class CalibrationOverlay(tk.Toplevel):
    """Plein écran figé sur une capture : l'utilisateur dessine deux rectangles à la souris."""

    def __init__(self, master: tk.Misc, shot: np.ndarray, origin: tuple[int, int],
                 on_done: Callable[[Calibration | None], None]) -> None:
        super().__init__(master)
        self._shot = shot
        self._gray = cv2.cvtColor(shot, cv2.COLOR_BGR2GRAY)
        self._origin = origin
        self._on_done = on_done
        self._step = 0
        self._anchor: tuple[int, int, int, int] | None = None
        self._start = (0, 0)
        self._rubber = 0
        self._notice = ""

        h, w = shot.shape[:2]
        self.overrideredirect(True)
        self.geometry(f"{w}x{h}+{origin[0]}+{origin[1]}")
        self.attributes("-topmost", True)
        self._canvas = tk.Canvas(self, width=w, height=h, highlightthickness=0, cursor="crosshair")
        self._canvas.pack()
        _, png = cv2.imencode(".png", shot)
        self._photo = tk.PhotoImage(data=base64.b64encode(png.tobytes()))
        self._canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self._banner_bg = self._canvas.create_rectangle(0, 0, 0, 0, fill="#202020", outline="")
        self._banner = self._canvas.create_text(0, 0, anchor="nw", fill="white",
                                                font=("Segoe UI", 12, "bold"))
        self._move_banner(w // 2, h // 2)

        for widget in (self, self._canvas):
            widget.bind("<Escape>", lambda _e: self._finish(None))
        self._canvas.bind("<Button-3>", lambda _e: self._finish(None))
        self._canvas.bind("<Motion>", lambda e: self._move_banner(e.x, e.y))
        self._canvas.bind("<ButtonPress-1>", self._press)
        self._canvas.bind("<B1-Motion>", self._drag)
        self._canvas.bind("<ButtonRelease-1>", self._release)
        self.focus_force()
        self._canvas.focus_set()

    def _move_banner(self, x: int, y: int) -> None:
        text = (self._notice + "\n" if self._notice else "") + STEPS[self._step] + CANCEL_HINT
        self._canvas.itemconfigure(self._banner, text=text)
        self._canvas.coords(self._banner, x + 24, y + 24)
        x0, y0, x1, y1 = self._canvas.bbox(self._banner)
        self._canvas.coords(self._banner_bg, x0 - 8, y0 - 6, x1 + 8, y1 + 6)
        self._canvas.tag_raise(self._banner_bg)
        self._canvas.tag_raise(self._banner)

    def _press(self, e: tk.Event) -> None:
        self._start = (e.x, e.y)
        self._rubber = self._canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="#ff3030", width=2)

    def _drag(self, e: tk.Event) -> None:
        self._canvas.coords(self._rubber, *self._start, e.x, e.y)
        self._move_banner(e.x, e.y)

    def _release(self, e: tk.Event) -> None:
        h, w = self._gray.shape
        x0, x1 = sorted((max(0, min(w, self._start[0])), max(0, min(w, e.x))))
        y0, y1 = sorted((max(0, min(h, self._start[1])), max(0, min(h, e.y))))
        rect = (x0, y0, x1 - x0, y1 - y0)
        self._canvas.delete(self._rubber)
        if rect[2] < MIN_SIZE or rect[3] < MIN_SIZE:
            self._notice = "Sélection trop petite, recommence."
        elif self._step == 0 and float(np.std(self._gray[y0:y1, x0:x1])) < MIN_CONTRAST:
            self._notice = "Zone trop uniforme : choisis un élément avec du contraste."
        elif self._step == 0:
            self._anchor = rect
            self._step, self._notice = 1, ""
            self._canvas.create_rectangle(x0, y0, x1, y1, outline="#30ff30", width=2)
        else:
            self._finish(self._build(rect))
            return
        self._move_banner(e.x, e.y)

    def _build(self, duration: tuple[int, int, int, int]) -> Calibration:
        ox, oy = self._origin
        ax, ay, aw, ah = self._anchor
        image = self._gray[ay:ay + ah, ax:ax + aw].copy()
        return Calibration((ox + ax, oy + ay, aw, ah),
                           (ox + duration[0], oy + duration[1], duration[2], duration[3]), image)

    def _finish(self, result: Calibration | None) -> None:
        self.destroy()
        self._on_done(result)
