from __future__ import annotations

import cv2
import numpy as np


def find(gray: np.ndarray, template: np.ndarray) -> tuple[float, tuple[int, int]]:
    """Retourne (score 0..1, position x/y du meilleur match) de `template` dans `gray`."""
    if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
        return 0.0, (0, 0)
    result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(np.nan_to_num(result))
    return float(score), loc
