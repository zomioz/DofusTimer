import pytest

from dofus_timer.ocr import parse_duration


@pytest.mark.parametrize("text, expected", [
    ("00:01:41", 101),
    ("00.01.41", 101),
    ("00：01﹕41", 101),
    ("OO:Ol:4l", 101),
    ("00 01 41", 101),
    ("00,01;41", 101),
    ("00:04", 4),
    ("59:59", 3599),
    ("01.41", 101),
    ("O1:4l", 101),
    ("Durée : 00:01:41", 101),
    ("01 : 02 : 03", 3723),
    ("01:00:00", 3600),
    ("23:59:59", 86399),
    ("00:61:00", None),
    ("00:00:73", None),
    ("24:00:00", None),
    ("000141", None),
    ("60:00", None),
    ("2 min 15 s", None),
    ("1 h 5 min", None),
    ("45 s", None),
    ("", None),
    ("combat terminé", None),
    ("00:00:00", None),
])
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected
