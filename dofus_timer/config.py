from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .capture import Rect


@dataclass
class Calibration:
    anchor: Rect  # élément fixe du popup, sert à le détecter
    duration: Rect  # zone où s'affiche la durée du combat
    anchor_image: np.ndarray  # image de l'ancre en niveaux de gris


def config_dir() -> Path:
    appdata = os.environ.get("APPDATA") if sys.platform == "win32" else None
    return (Path(appdata) if appdata else Path.home() / ".config") / "DofusTimer"


def _write_png(path: Path, image: np.ndarray) -> None:
    # imencode plutôt qu'imwrite : imwrite échoue sur les chemins avec accents (ex. C:\Users\Léo)
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise OSError("Encodage PNG impossible")
    path.write_bytes(buf.tobytes())


def save(cal: Calibration) -> None:
    folder = config_dir()
    folder.mkdir(parents=True, exist_ok=True)
    _write_png(folder / "anchor.png", cal.anchor_image)
    data = {"version": 1, "anchor": list(cal.anchor), "duration": list(cal.duration)}
    (folder / "config.json").write_text(json.dumps(data), encoding="utf-8")


def load() -> Calibration | None:
    folder = config_dir()
    try:
        data = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        raw = np.frombuffer((folder / "anchor.png").read_bytes(), dtype=np.uint8)
        image = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
        anchor = tuple(int(v) for v in data["anchor"])
        duration = tuple(int(v) for v in data["duration"])
        if image is None or len(anchor) != 4 or len(duration) != 4:
            return None
        return Calibration(anchor, duration, image)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_debug_image(image: np.ndarray) -> None:
    """Garde la dernière zone illisible pour diagnostiquer l'OCR."""
    try:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        _write_png(folder / "last_failed.png", image)
    except OSError:
        pass
