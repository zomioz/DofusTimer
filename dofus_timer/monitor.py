from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from . import config, detector
from . import ocr as ocr_mod
from .capture import Grabber, grow, union

THRESHOLD = 0.8  # score minimal de détection du popup
INTERVAL = 0.4  # secondes entre deux captures
MARGIN = 40  # tolérance de déplacement du popup, en pixels
READ_ATTEMPTS = 4
READ_DELAY = 0.5  # laisse finir l'animation du popup avant la lecture
ABSENT_FRAMES = 3  # captures consécutives sans popup avant de le considérer fermé


@dataclass
class Event:
    kind: str  # "result" | "error" | "fatal"
    seconds: int = 0
    text: str = ""


class Monitor(threading.Thread):
    """Surveille l'écran en lecture seule et publie un Event à chaque popup de fin de combat."""

    def __init__(self, cal: config.Calibration, ocr: ocr_mod.Ocr, events: queue.Queue,
                 grabber_factory=Grabber) -> None:
        super().__init__(daemon=True)
        self.cal = cal
        self.ocr = ocr
        self.events = events
        self._factory = grabber_factory
        self._halt = threading.Event()
        self._region = (0, 0, 0, 0)

    def stop(self) -> None:
        self._halt.set()
        self.join(timeout=3)

    def run(self) -> None:
        grabber = None
        try:
            grabber = self._factory()
            self._loop(grabber)
        except Exception as exc:  # remonté à l'UI plutôt que de tuer le thread en silence
            self.events.put(Event("fatal", text=f"{type(exc).__name__}: {exc}"))
        finally:
            if grabber is not None:
                grabber.close()

    def _loop(self, grabber: Grabber) -> None:
        self._region = grabber.clamp(grow(union(self.cal.anchor, self.cal.duration), MARGIN))
        shown = self._popup(grabber) is not None  # popup déjà affiché au départ : ignoré
        absent = 0
        while not self._halt.wait(INTERVAL):
            if self._popup(grabber) is None:
                absent += 1
                if absent >= ABSENT_FRAMES:
                    shown = False
                continue
            absent = 0
            if not shown:
                shown = True
                self._read_popup(grabber)

    def _popup(self, grabber: Grabber) -> tuple[np.ndarray, tuple[int, int]] | None:
        gray = cv2.cvtColor(grabber.grab(self._region), cv2.COLOR_BGR2GRAY)
        score, loc = detector.find(gray, self.cal.anchor_image)
        return (gray, loc) if score >= THRESHOLD else None

    def _crop_duration(self, gray: np.ndarray, loc: tuple[int, int]) -> np.ndarray:
        rx, ry = self._region[:2]
        ax, ay = self.cal.anchor[:2]
        dx, dy, w, h = self.cal.duration
        # suit le popup s'il a bougé par rapport à la calibration
        x = dx - rx + (loc[0] - (ax - rx))
        y = dy - ry + (loc[1] - (ay - ry))
        return gray[max(y, 0): max(y + h, 0), max(x, 0): max(x + w, 0)]

    def _read_popup(self, grabber: Grabber) -> None:
        crop, text = np.empty(0), ""
        for _ in range(READ_ATTEMPTS):
            if self._halt.wait(READ_DELAY):
                return
            found = self._popup(grabber)
            if found is None:
                return
            crop = self._crop_duration(*found)
            seconds, text = ocr_mod.read_duration(self.ocr, crop)
            if seconds is not None:
                self.events.put(Event("result", seconds, text))
                return
        if crop.size:
            config.save_debug_image(crop)
        self.events.put(Event("error", text=text))
