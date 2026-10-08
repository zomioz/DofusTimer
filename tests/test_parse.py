import pytest

from dofus_timer.ocr import parse_duration


@pytest.mark.parametrize("text, expected", [
    ("2 min 15 s", 135),
    ("2min15s", 135),
    ("1 h 5 min", 3900),
    ("1 heure 5 minutes 3 secondes", 3903),
    ("Durée : 12:30", 750),
    ("1:02:03", 3723),
    ("45 s", 45),
    ("", None),
    ("combat terminé", None),
    ("0 s", None),
])
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected
