import pytest

from dofus_timer.ocr import parse_duration, read_duration

import numpy as np


@pytest.mark.parametrize("text, expected", [
    ("01:41", 101),
    ("01.41", 101),
    ("01：41", 101),
    ("01﹕41", 101),
    ("O1:4l", 101),
    ("Ol:4I", 101),
    ("0l:4|", 101),
    ("01 41", 101),
    ("0141", 101),
    ("01,41", 101),
    ("01 : 41", 101),
    ("Durée : 01:41", 101),
    ("00:04", 4),
    ("59:59", 3599),
    ("02:S5", 175),
    ("00:61", None),
    ("60:00", None),
    ("00:00", None),
    ("00:01:41", None),
    ("1:41", None),
    ("2 min 15 s", None),
    ("45 s", None),
    ("", None),
    ("combat terminé", None),
])
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected


class ScriptedOcr:
    def __init__(self, *texts):
        self.texts = list(texts)

    def read(self, gray):
        return self.texts.pop(0) if self.texts else ""


IMG = np.zeros((10, 30), np.uint8)


def test_read_duration_majority_vote():
    assert read_duration(ScriptedOcr("01:41", "01:47", "01:41", "01:41"), IMG)[0] == 101


def test_read_duration_contradiction_is_rejected():
    assert read_duration(ScriptedOcr("01:41", "01:47", "", ""), IMG)[0] is None
