
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class SkyObject:
    ra_deg: float
    dec_deg: float
    mag: float
    name: str = ""
    catalog: str = ""
    id: int = 0

@dataclass(slots=True)
class Observer:
    lat_deg: float
    lon_deg: float
    elevation_m: float = 0.0

@dataclass(slots=True)
class ViewState:
    # chart center in equatorial J2000-ish (we ignore precession for now; good enough for gameplay)
    center_ra_deg: float = 0.0
    center_dec_deg: float = 0.0
    # field of view across the screen, degrees
    fov_deg: float = 120.0
