import queue
import threading
import time

import numpy as np
import pytest

from dofus_timer import monitor
from dofus_timer.capture import clamp
from dofus_timer.config import Calibration

W, H = 400, 300
ANCHOR = (100, 100, 60, 30)
DURATION = (110, 150, 80, 20)


class FakeGrabber:
    screen = np.zeros((H, W, 3), np.uint8)
    bounds = (0, 0, W, H)
    first_grab = None

    def clamp(self, rect):
        return clamp(rect, self.bounds)

    def grab(self, rect):
        x, y, w, h = rect
        image = FakeGrabber.screen[y:y + h, x:x + w].copy()
        if FakeGrabber.first_grab is not None:
            FakeGrabber.first_grab.set()
        return image

    def close(self):
        pass


class FakeOcr:
    def read(self, gray):
        return "00:02:15"


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(monitor, "INTERVAL", 0.02)
    monkeypatch.setattr(monitor, "READ_DELAY", 0.02)
    rng = np.random.default_rng(1)
    pattern = rng.integers(0, 255, (ANCHOR[3], ANCHOR[2]), dtype=np.uint8)
    FakeGrabber.screen = np.zeros((H, W, 3), np.uint8)
    FakeGrabber.first_grab = threading.Event()
    cal = Calibration(ANCHOR, DURATION, pattern)

    def show(visible, dx=0):
        FakeGrabber.screen.fill(0)
        x, y, w, h = ANCHOR
        if visible:
            FakeGrabber.screen[y:y + h, x + dx:x + dx + w] = pattern[:, :, None]

    events = queue.Queue()
    mon = monitor.Monitor(cal, FakeOcr(), events, FakeGrabber)
    mon.start()
    assert FakeGrabber.first_grab.wait(timeout=1)
    yield show, events
    mon.stop()


def test_counts_each_popup_once(setup):
    show, events = setup
    show(True, dx=80)
    assert events.get(timeout=3).seconds == 135
    with pytest.raises(queue.Empty):
        events.get(timeout=0.5)  # le popup reste affiché : pas de doublon
    show(False)
    time.sleep(0.3)  # laisse le moniteur voir la fermeture
    show(True)
    assert events.get(timeout=3).seconds == 135


def test_popup_already_visible_at_start_is_ignored(monkeypatch):
    monkeypatch.setattr(monitor, "INTERVAL", 0.02)
    rng = np.random.default_rng(1)
    pattern = rng.integers(0, 255, (ANCHOR[3], ANCHOR[2]), dtype=np.uint8)
    FakeGrabber.screen = np.zeros((H, W, 3), np.uint8)
    FakeGrabber.screen[100:130, 100:160] = pattern[:, :, None]
    events = queue.Queue()
    mon = monitor.Monitor(Calibration(ANCHOR, DURATION, pattern), FakeOcr(), events, FakeGrabber)
    mon.start()
    with pytest.raises(queue.Empty):
        events.get(timeout=0.5)
    mon.stop()


def test_popup_is_read_from_detection_frame_if_closed_immediately(monkeypatch):
    monkeypatch.setattr(monitor, "READ_DELAY", 0.5)
    rng = np.random.default_rng(1)
    pattern = rng.integers(0, 255, (ANCHOR[3], ANCHOR[2]), dtype=np.uint8)
    FakeGrabber.screen = np.zeros((H, W, 3), np.uint8)
    FakeGrabber.screen[100:130, 100:160] = pattern[:, :, None]
    events = queue.Queue()
    mon = monitor.Monitor(Calibration(ANCHOR, DURATION, pattern), FakeOcr(), events, FakeGrabber)
    mon._region = FakeGrabber.bounds
    grabber = FakeGrabber()
    initial = mon._popup(grabber)
    FakeGrabber.screen.fill(0)

    mon._read_popup(grabber, initial)

    assert events.get_nowait().seconds == 135
