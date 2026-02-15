"""
TimeController — Gestione tempo simulato condivisa.

Usato da SkychartScreen e ImagingScreen per avanzamento fluido del tempo.
Il JD viene aggiornato ad ogni frame con precisione floating-point — nessun
accumulo a soglia, nessun salto a intervalli interi di secondi.

Velocità disponibili:
    SPEEDS = [0, 1, 10, 60, 300, 3600, 86400, 7*86400]
    (pausa, tempo reale, 10×, 1min/s, 5min/s, 1h/s, 1d/s, 1settimana/s)

Controllo:
    tc.speed_up()    — prossimo step di velocità avanti
    tc.speed_down()  — step indietro (0 = pausa)
    tc.reverse()     — inverte direzione
    tc.realtime()    — torna a tempo reale, sincronizza con clock di sistema
    tc.toggle_pause()
    tc.step(dt_wall_seconds)  — chiamato ogni frame, ritorna JD aggiornato
"""

from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import Optional


# Passi di velocità in secondi simulati per secondo reale
SPEEDS = [0, 1, 10, 60, 300, 3600, 86400, 7 * 86400]
SPEED_LABELS = ["PAUSED", "1×", "10×", "1min/s", "5min/s",
                "1h/s", "1d/s", "1wk/s"]

# Secondi in un giorno siderale (IAU)
SIDEREAL_DAY_S = 86164.0905

# Coefficiente GMST (gradi per giorno solare)
GMST_RATE_DEG_PER_DAY = 360.98564736629


def _gmst_deg(jd: float) -> float:
    """GMST in gradi [0,360) — IAU 1982."""
    T = (jd - 2451545.0) / 36525.0
    g = (280.46061837
         + GMST_RATE_DEG_PER_DAY * (jd - 2451545.0)
         + 0.000387933 * T * T
         - T * T * T / 38710000.0)
    return g % 360.0


def _lst_deg(jd: float, lon_deg: float) -> float:
    return (_gmst_deg(jd) + lon_deg) % 360.0


class TimeController:
    """
    Gestione tempo simulato con avanzamento fluido per frame.

    Parametri
    ----------
    start_utc : datetime UTC da cui partire (default: adesso)
    speed_idx : indice in SPEEDS (default: 1 = tempo reale)
    """

    def __init__(self,
                 start_utc: Optional[datetime] = None,
                 speed_idx: int = 1):
        if start_utc is None:
            start_utc = datetime.now(timezone.utc)
        self._jd        = _dt_to_jd(start_utc)
        self._speed_idx = max(0, min(speed_idx, len(SPEEDS) - 1))
        self._direction = +1    # +1 avanti, -1 indietro
        self._paused    = (self._speed_idx == 0)

    # ── Proprietà ────────────────────────────────────────────────────────────

    @property
    def jd(self) -> float:
        return self._jd

    @property
    def utc(self) -> datetime:
        return _jd_to_dt(self._jd)

    @property
    def speed(self) -> float:
        return SPEEDS[self._speed_idx] * self._direction

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def speed_label(self) -> str:
        if self._paused:
            return "PAUSED"
        lbl = SPEED_LABELS[self._speed_idx]
        return ("◀◀ " if self._direction < 0 else "") + lbl

    @property
    def speed_idx(self) -> int:
        return self._speed_idx

    # ── Controlli ────────────────────────────────────────────────────────────

    def speed_up(self):
        """Aumenta velocità (o riprende se in pausa)."""
        if self._paused:
            self._paused = False
        elif self._speed_idx < len(SPEEDS) - 1:
            self._speed_idx += 1

    def speed_down(self):
        """Diminuisce velocità (pausa a 0)."""
        if self._speed_idx > 0:
            self._speed_idx -= 1
        if self._speed_idx == 0:
            self._paused = True

    def toggle_pause(self):
        self._paused = not self._paused

    def reverse(self):
        """Inverte la direzione del tempo."""
        self._direction *= -1

    def realtime(self):
        """Torna a tempo reale e sincronizza con l'orologio di sistema."""
        now = datetime.now(timezone.utc)
        self._jd        = _dt_to_jd(now)
        self._speed_idx = 1
        self._direction = +1
        self._paused    = False

    def set_speed_idx(self, idx: int):
        self._speed_idx = max(0, min(idx, len(SPEEDS) - 1))
        self._paused    = (self._speed_idx == 0)

    def jump(self, delta_seconds: float):
        """Salta di delta_seconds (può essere negativo)."""
        self._jd += delta_seconds / 86400.0

    # ── Aggiornamento frame ───────────────────────────────────────────────────

    def step(self, dt_wall: float) -> float:
        """
        Avanza il tempo di dt_wall secondi reali.
        Ritorna il JD aggiornato.
        dt_wall: secondi reali dall'ultimo frame (tipicamente 1/60).
        """
        if not self._paused:
            sim_secs = dt_wall * SPEEDS[self._speed_idx] * self._direction
            self._jd += sim_secs / 86400.0
        return self._jd

    # ── Astronomia ───────────────────────────────────────────────────────────

    def lst(self, lon_deg: float) -> float:
        """Local Sidereal Time in gradi [0, 360)."""
        return _lst_deg(self._jd, lon_deg)

    def gmst(self) -> float:
        """GMST in gradi [0, 360)."""
        return _gmst_deg(self._jd)


# ── Conversioni JD ↔ datetime ─────────────────────────────────────────────

def _dt_to_jd(dt: datetime) -> float:
    """datetime UTC → JD (identico a orbital_body.datetime_to_jd)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return 2451545.0 + (dt - j2000).total_seconds() / 86400.0


def _jd_to_dt(jd: float) -> datetime:
    """JD → datetime UTC."""
    delta_s = (jd - 2451545.0) * 86400.0
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return j2000 + timedelta(seconds=delta_s)
