from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import cv2
import numpy as np

from . import config
from . import ocr as ocr_mod
from .calibration import CalibrationOverlay
from .capture import Grabber
from .monitor import Event, Monitor

NEEDS_CALIBRATION = ("Calibration requise : termine un combat, laisse le popup de fin affiché, "
                     "puis clique sur Calibrer.")


def format_hms(seconds: int) -> str:
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cal = config.load()
        self.ocr: ocr_mod.Ocr | None = None
        self.ocr_error = ""
        try:
            self.ocr = ocr_mod.create_ocr()
        except (ocr_mod.OcrUnavailable, ImportError) as exc:
            self.ocr_error = str(exc)
        self.events: queue.Queue = queue.Queue()
        self.monitor: Monitor | None = None
        self.total = 0
        self.count = 0

        root.title("Dofus Timer")
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=14)
        frame.grid()
        ttk.Label(frame, text="Temps de combat total").grid(row=0, column=0, columnspan=3)
        self.total_var = tk.StringVar(value=format_hms(0))
        ttk.Label(frame, textvariable=self.total_var,
                  font=tkfont.Font(size=28, weight="bold")).grid(row=1, column=0, columnspan=3)
        self.count_var = tk.StringVar(value="Combats : 0")
        ttk.Label(frame, textvariable=self.count_var).grid(row=2, column=0, columnspan=3, pady=(0, 10))
        self.start_btn = ttk.Button(frame, text="Départ", command=self.start)
        self.stop_btn = ttk.Button(frame, text="Stop", command=self.stop)
        self.cal_btn = ttk.Button(frame, text="Calibrer", command=self.calibrate)
        self.start_btn.grid(row=3, column=0, padx=3)
        self.stop_btn.grid(row=3, column=1, padx=3)
        self.cal_btn.grid(row=3, column=2, padx=3)
        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, wraplength=300,
                  justify="center").grid(row=4, column=0, columnspan=3, pady=(10, 0))
        ttk.Label(frame, text="by zephryane").grid(row=5, column=2, sticky="e", pady=(8, 0))

        self._set_idle_status()
        self._refresh_buttons()
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(200, self._poll)

    @property
    def running(self) -> bool:
        return self.monitor is not None

    def _set_idle_status(self) -> None:
        if self.ocr is None:
            self.status_var.set(f"OCR indisponible : {self.ocr_error}")
        elif self.cal is None:
            self.status_var.set(NEEDS_CALIBRATION)
        else:
            self.status_var.set("Prêt")

    def _refresh_buttons(self) -> None:
        ready = self.cal is not None and self.ocr is not None
        self.start_btn.state(["!disabled"] if ready and not self.running else ["disabled"])
        self.stop_btn.state(["!disabled"] if self.running else ["disabled"])
        self.cal_btn.state(["disabled"] if self.running else ["!disabled"])

    def _show_totals(self) -> None:
        self.total_var.set(format_hms(self.total))
        self.count_var.set(f"Combats : {self.count}")

    def start(self) -> None:
        self.total = self.count = 0
        self._show_totals()
        self.events = queue.Queue()
        self.monitor = Monitor(self.cal, self.ocr, self.events)
        self.monitor.start()
        self.status_var.set("Surveillance active : en attente du popup de fin de combat")
        self._refresh_buttons()

    def stop(self, status: str = "Arrêté") -> None:
        if self.monitor is not None:
            self.monitor.stop()
            self.monitor = None
        self._drain()
        self.status_var.set(status)
        self._refresh_buttons()

    def _drain(self) -> None:
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass

    def _handle(self, event: Event) -> None:
        if event.kind == "result":
            self.total += event.seconds
            self.count += 1
            self._show_totals()
            self.status_var.set(f"Combat détecté : {format_hms(event.seconds)}")
        elif event.kind == "error":
            self.status_var.set(f"Lecture impossible (lu : « {event.text} »), combat non compté.")
        elif event.kind == "fatal" and self.monitor is not None:
            self.monitor = None
            self.status_var.set(f"Erreur : {event.text}")
            self._refresh_buttons()

    def _poll(self) -> None:
        self._drain()
        self.root.after(200, self._poll)

    def calibrate(self) -> None:
        self.root.iconify()
        self.root.after(600, self._open_overlay)  # laisse la fenêtre se minimiser avant la capture

    def _open_overlay(self) -> None:
        grabber = Grabber()
        try:
            origin = grabber.bounds[:2]
            shot = grabber.grab(grabber.bounds)
        finally:
            grabber.close()
        if float(shot.mean()) < 3:
            self.root.deiconify()
            messagebox.showwarning(
                "Capture noire",
                "L'écran capturé est noir : Dofus est probablement en plein écran exclusif.\n"
                "Passe Dofus en mode fenêtré ou plein écran sans bordure, puis recalibre.")
            return
        CalibrationOverlay(self.root, shot, origin,
                           lambda cal: self._on_calibrated(cal, shot, origin))

    def _on_calibrated(self, cal: config.Calibration | None, shot: np.ndarray,
                       origin: tuple[int, int]) -> None:
        self.root.deiconify()
        if cal is None:
            return
        config.save(cal)
        self.cal = cal
        self._set_idle_status()
        self._refresh_buttons()
        messagebox.showinfo("Calibration enregistrée", self._test_reading(cal, shot, origin))

    def _test_reading(self, cal: config.Calibration, shot: np.ndarray, origin: tuple[int, int]) -> str:
        if self.ocr is None:
            return "Calibration enregistrée."
        x, y, w, h = cal.duration
        gray = cv2.cvtColor(shot, cv2.COLOR_BGR2GRAY)[y - origin[1]:y - origin[1] + h,
                                                      x - origin[0]:x - origin[0] + w]
        seconds, text = ocr_mod.read_duration(self.ocr, gray)
        if seconds is None:
            return (f"Calibration enregistrée, mais la durée n'a pas pu être lue (lu : « {text} »).\n"
                    "Recalibre en entourant plus précisément le texte de la durée.")
        return f"Durée lue : « {text} » = {format_hms(seconds)}.\nSi c'est correct, tu peux cliquer sur Départ."

    def _close(self) -> None:
        if self.monitor is not None:
            self.monitor.stop()
        self.root.destroy()
