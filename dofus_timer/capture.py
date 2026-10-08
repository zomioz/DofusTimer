from __future__ import annotations

import mss
import numpy as np

Rect = tuple[int, int, int, int]  # x, y, largeur, hauteur (coordonnées de l'écran virtuel)


def union(a: Rect, b: Rect) -> Rect:
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def grow(r: Rect, margin: int) -> Rect:
    return (r[0] - margin, r[1] - margin, r[2] + 2 * margin, r[3] + 2 * margin)


def clamp(r: Rect, bounds: Rect) -> Rect:
    x0, y0 = max(r[0], bounds[0]), max(r[1], bounds[1])
    x1 = min(r[0] + r[2], bounds[0] + bounds[2])
    y1 = min(r[1] + r[3], bounds[1] + bounds[3])
    if x1 <= x0 or y1 <= y0:
        raise ValueError("La zone calibrée est hors de l'écran : recalibre.")
    return (x0, y0, x1 - x0, y1 - y0)


class Grabber:
    """Capture passive de l'écran (lecture seule). À créer dans le thread qui l'utilise."""

    def __init__(self) -> None:
        self._sct = mss.mss()
        m = self._sct.monitors[0]  # tous les écrans réunis
        self.bounds: Rect = (m["left"], m["top"], m["width"], m["height"])

    def clamp(self, r: Rect) -> Rect:
        return clamp(r, self.bounds)

    def grab(self, rect: Rect) -> np.ndarray:
        x, y, w, h = rect
        shot = self._sct.grab({"left": x, "top": y, "width": w, "height": h})
        return np.ascontiguousarray(np.array(shot)[:, :, :3])  # BGR

    def close(self) -> None:
        self._sct.close()
