from __future__ import annotations

import asyncio
import re
import sys
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


_CLOCK_CHARS = "0-9OoQqIl|"
_CLOCK_SEPARATOR = r"(?:\s*[:：﹕.,;]\s*|\s+)"
_CLOCK_HMS = re.compile(
    rf"(?<![{_CLOCK_CHARS}])([{_CLOCK_CHARS}]{{2}})"
    rf"{_CLOCK_SEPARATOR}([{_CLOCK_CHARS}]{{2}})"
    rf"{_CLOCK_SEPARATOR}([{_CLOCK_CHARS}]{{2}})(?![{_CLOCK_CHARS}])"
)
_CLOCK_MS = re.compile(
    rf"(?<![{_CLOCK_CHARS}])([{_CLOCK_CHARS}]{{2}})"
    rf"{_CLOCK_SEPARATOR}([{_CLOCK_CHARS}]{{2}})(?![{_CLOCK_CHARS}])"
)
_OCR_DIGITS = str.maketrans({"O": "0", "o": "0", "Q": "0", "q": "0",
                             "I": "1", "l": "1", "|": "1"})


def parse_duration(text: str) -> int | None:
    """Convertit MM:SS ou HH:MM:SS, avec variantes OCR, en secondes."""
    match = _CLOCK_HMS.search(text)
    if match is not None:
        hours, minutes, seconds = (int(part.translate(_OCR_DIGITS)) for part in match.groups())
        if hours > 23 or minutes > 59 or seconds > 59:
            return None
        total = hours * 3600 + minutes * 60 + seconds
    else:
        match = _CLOCK_MS.search(text)
        if match is None:
            return None
        minutes, seconds = (int(part.translate(_OCR_DIGITS)) for part in match.groups())
        if minutes > 59 or seconds > 59:
            return None
        total = minutes * 60 + seconds
    return total if 0 < total < 24 * 3600 else None


def _variants(gray: np.ndarray) -> Iterator[np.ndarray]:
    big = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    big = cv2.copyMakeBorder(big, 20, 20, 20, 20, cv2.BORDER_REPLICATE)
    yield big
    yield 255 - big  # texte clair sur fond sombre ou l'inverse


def read_duration(ocr: Ocr, gray: np.ndarray) -> tuple[int | None, str]:
    """Retourne (secondes ou None, texte brut lu)."""
    if gray.size == 0:
        return None, ""
    text = ""
    for image in _variants(gray):
        text = ocr.read(image).strip()
        seconds = parse_duration(text)
        if seconds is not None:
            return seconds, text
    return None, text
