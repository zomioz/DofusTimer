from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter
from typing import Iterator, Protocol

import cv2
import numpy as np


class OcrUnavailable(RuntimeError):
    pass


class Ocr(Protocol):
    def read(self, gray: np.ndarray) -> str: ...


class WindowsOcr:
    """OCR intégré à Windows 10/11 (Windows.Media.Ocr), sans rien à installer."""

    def __init__(self) -> None:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        engine = OcrEngine.try_create_from_user_profile_languages()
        for tag in ("fr-FR", "en-US"):
            if engine is not None:
                break
            engine = OcrEngine.try_create_from_language(Language(tag))
        if engine is None:
            raise OcrUnavailable(
                "Aucune langue OCR Windows installée "
                "(Paramètres > Heure et langue > Langue et région)."
            )
        self._engine = engine

    def read(self, gray: np.ndarray) -> str:
        return asyncio.run(self._recognize(gray))

    async def _recognize(self, gray: np.ndarray) -> str:
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.storage.streams import DataWriter

        bgra = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGRA)
        writer = DataWriter()
        writer.write_bytes(bgra.tobytes())
        bitmap = SoftwareBitmap.create_copy_from_buffer(
            writer.detach_buffer(), BitmapPixelFormat.BGRA8, bgra.shape[1], bgra.shape[0]
        )
        result = await self._engine.recognize_async(bitmap)
        return result.text


def create_ocr() -> Ocr:
    if sys.platform != "win32":
        raise OcrUnavailable("L'OCR Windows n'est disponible que sous Windows.")
    return WindowsOcr()


_CLOCK_CHARS = "0-9OoQqDIl|!SBZ"
_CLOCK_SEPARATOR = r"(?:\s*[:：﹕.,;]\s*|\s+|)"
# Un troisième groupe (HH:MM:SS) n'est pas un format valide : on le rejette plutôt que de lire un faux MM:SS.
_CLOCK_MS = re.compile(
    rf"(?<![{_CLOCK_CHARS}])([{_CLOCK_CHARS}]{{2}})"
    rf"{_CLOCK_SEPARATOR}([{_CLOCK_CHARS}]{{2}})"
    rf"(?![{_CLOCK_CHARS}])(?!\s*[:：﹕.,;]\s*[{_CLOCK_CHARS}])"
)
_CLOCK_HMS = re.compile(rf"[{_CLOCK_CHARS}]{{2}}\s*[:：﹕]\s*[{_CLOCK_CHARS}]{{2}}\s*[:：﹕]\s*[{_CLOCK_CHARS}]{{2}}")
_OCR_DIGITS = str.maketrans({"O": "0", "o": "0", "Q": "0", "q": "0", "D": "0",
                             "I": "1", "l": "1", "|": "1", "!": "1",
                             "S": "5", "B": "8", "Z": "2"})
MAX_SECONDS = 59 * 60 + 59


def parse_duration(text: str) -> int | None:
    """Convertit MM:SS, avec variantes OCR (O→0, l→1...), en secondes."""
    if _CLOCK_HMS.search(text):
        return None
    for match in _CLOCK_MS.finditer(text):
        try:
            minutes, seconds = (int(part.translate(_OCR_DIGITS)) for part in match.groups())
        except ValueError:
            continue
        total = minutes * 60 + seconds
        if seconds <= 59 and 0 < total <= MAX_SECONDS:
            return total
    return None


def _variants(gray: np.ndarray) -> Iterator[np.ndarray]:
    big = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    big = cv2.copyMakeBorder(big, 20, 20, 20, 20, cv2.BORDER_REPLICATE)
    yield big
    yield 255 - big  # texte clair sur fond sombre ou l'inverse
    _, binary = cv2.threshold(cv2.GaussianBlur(big, (3, 3), 0), 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield binary
    yield 255 - binary


def read_duration(ocr: Ocr, gray: np.ndarray) -> tuple[int | None, str]:
    """Retourne (secondes ou None, texte brut lu) par vote entre plusieurs prétraitements."""
    if gray.size == 0:
        return None, ""
    votes: Counter[int] = Counter()
    texts: dict[int, str] = {}
    last = ""
    for image in _variants(gray):
        last = ocr.read(image).strip()
        seconds = parse_duration(last)
        if seconds is None:
            continue
        votes[seconds] += 1
        texts.setdefault(seconds, last)
        ranked = votes.most_common(2)
        if ranked[0][1] >= 2 and (len(ranked) == 1 or ranked[0][1] > ranked[1][1] + 1):
            break  # deux lectures concordantes et aucune concurrente proche
    if not votes:
        return None, last
    ranked = votes.most_common(2)
    if len(ranked) == 2 and ranked[0][1] == ranked[1][1]:
        return None, f"{texts[ranked[0][0]]} / {texts[ranked[1][0]]}"  # lectures contradictoires
    winner = ranked[0][0]
    return winner, texts[winner]
