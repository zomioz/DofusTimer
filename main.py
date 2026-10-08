from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def _enable_dpi_awareness() -> None:
    # Sans cela, les coordonnées d'écran dérivent avec une mise à l'échelle Windows de 125 % ou plus.
    if sys.platform == "win32":
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def selftest() -> int:
    """Vérifie que l'OCR est bien embarqué (utilisé par la CI sur l'exécutable construit)."""
    import cv2
    import numpy as np

    from dofus_timer import ocr

    code, message = 0, ""
    try:
        engine = ocr.create_ocr()
        image = np.full((60, 320), 255, np.uint8)
        cv2.putText(image, "12 min 30 s", (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 2)
        message = f"ok : {ocr.read_duration(engine, image)}"
    except ocr.OcrUnavailable as exc:
        message = f"moteur OCR indisponible (non bloquant) : {exc}"
    except Exception as exc:
        code, message = 1, f"échec : {type(exc).__name__}: {exc}"
    (Path(tempfile.gettempdir()) / "dofus_timer_selftest.log").write_text(message, encoding="utf-8")
    return code


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    _enable_dpi_awareness()
    import tkinter as tk

    from dofus_timer.ui import App

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
