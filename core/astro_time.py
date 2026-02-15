
from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timezone

# Lightweight time utilities (no external deps).
# We use UTC internally; caller can feed local time and tz if needed.

def datetime_to_julian_date(dt: datetime) -> float:
    """Convert a datetime (timezone-aware recommended) to Julian Date."""
    if dt.tzinfo is None:
        # assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)

    year = dt.year
    month = dt.month
    day = dt.day + (dt.hour + (dt.minute + dt.second/60.0)/60.0)/24.0

    if month <= 2:
        year -= 1
        month += 12

    A = year // 100
    B = 2 - A + (A // 4)

    jd = int(365.25*(year + 4716)) + int(30.6001*(month + 1)) + day + B - 1524.5
    return float(jd)

def gmst_deg(jd: float) -> float:
    """
    Greenwich Mean Sidereal Time in degrees.
    Approximation good to < 0.1s for typical game horizons.
    """
    T = (jd - 2451545.0) / 36525.0
    gmst = 280.46061837 + 360.98564736629*(jd - 2451545.0) + 0.000387933*T*T - (T*T*T)/38710000.0
    return gmst % 360.0

def lst_deg(jd: float, lon_deg: float) -> float:
    return (gmst_deg(jd) + lon_deg) % 360.0
