from __future__ import annotations

import queue
import threading
from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np

from . import config, detector
from . import ocr as ocr_mod
from .capture import Grabber, grow, union

THRESHOLD = 0.8  # score minimal de détection du popup
INTERVAL = 0.08  # environ 12 captures/s sur la seule zone utile
MARGIN = 220  # tolérance de déplacement du popup, en pixels
READ_ATTEMPTS = 6
CONSENSUS = 2  # lectures identiques (sur des captures différentes) pour valider une durée
READ_DELAY = 0.15  # délai entre les tentatives OCR après la première lecture immédiate
ABSENT_FRAMES = 6  # captures consécutives sans popup avant de le considérer fermé


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
            popup = self._popup(grabber)
            if popup is None:
                absent += 1
                if absent >= ABSENT_FRAMES:
                    shown = False
                continue
            absent = 0
            if not shown:
                shown = True
                self._read_popup(grabber, popup)

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

    def _read_popup(self, grabber: Grabber,
                    initial: tuple[np.ndarray, tuple[int, int]]) -> None:
        crop, text = np.empty(0), ""
        gray, loc = initial
        votes: Counter[int] = Counter()
        texts: dict[int, str] = {}
        for attempt in range(READ_ATTEMPTS):
            if attempt:
                if self._halt.wait(READ_DELAY):
                    return
                gray = cv2.cvtColor(grabber.grab(self._region), cv2.COLOR_BGR2GRAY)
                score, new_loc = detector.find(gray, self.cal.anchor_image)
                if score >= THRESHOLD:
                    loc = new_loc  # le popup peut encore bouger pendant son animation
            crop = self._crop_duration(gray, loc)
            seconds, text = ocr_mod.read_duration(self.ocr, crop)
            if seconds is None:
                continue
            votes[seconds] += 1
            texts.setdefault(seconds, text)
            if votes[seconds] >= CONSENSUS:
                self.events.put(Event("result", seconds, text))
                return
        ranked = votes.most_common(2)
        if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
            self.events.put(Event("result", ranked[0][0], texts[ranked[0][0]]))
            return
        if crop.size:
            config.save_debug_image(crop)
        self.events.put(Event("error", text=text))
