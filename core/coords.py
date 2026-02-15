
from __future__ import annotations
import math
from dataclasses import dataclass

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def wrap_deg(x: float) -> float:
    x = x % 360.0
    return x if x >= 0 else x + 360.0

def ang_diff_deg(a: float, b: float) -> float:
    """Smallest signed difference a-b in degrees in [-180,180)."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return d

def sph_to_cart(ra_deg: float, dec_deg: float) -> tuple[float,float,float]:
    ra = math.radians(ra_deg)
    dec = math.radians(dec_deg)
    c = math.cos(dec)
    return (c*math.cos(ra), c*math.sin(ra), math.sin(dec))

def cart_to_sph(x: float, y: float, z: float) -> tuple[float,float]:
    h = math.hypot(x, y)
    ra = math.degrees(math.atan2(y, x)) % 360.0
    dec = math.degrees(math.atan2(z, h))
    return ra, dec

def equatorial_to_horizontal(ra_deg: float, dec_deg: float, lat_deg: float, lst_deg: float) -> tuple[float,float]:
    """
    Return (az_deg, alt_deg). Az measured from North towards East (0..360).
    """
    ha = math.radians((lst_deg - ra_deg) % 360.0)
    dec = math.radians(dec_deg)
    lat = math.radians(lat_deg)

    sin_alt = math.sin(dec)*math.sin(lat) + math.cos(dec)*math.cos(lat)*math.cos(ha)
    alt = math.asin(max(-1.0, min(1.0, sin_alt)))

    # Azimuth
    cos_az = (math.sin(dec) - math.sin(alt)*math.sin(lat)) / (math.cos(alt)*math.cos(lat) + 1e-12)
    cos_az = max(-1.0, min(1.0, cos_az))
    az = math.acos(cos_az)
    if math.sin(ha) > 0:
        az = 2*math.pi - az
    az_deg = (math.degrees(az) + 360.0) % 360.0
    alt_deg = math.degrees(alt)
    return az_deg, alt_deg

def az_alt_to_screen(
    az_deg: float,
    alt_deg: float,
    w: int,
    h: int,
    fov_deg: float,
    *,
    cx: float | None = None,
    cy: float | None = None,
    R: float | None = None
) -> tuple[float,float,bool]:
    """
    Project horizontal coords to screen using azimuthal equidistant projection.
    Optional cx,cy,R let the caller place the sky disk inside a UI-safe viewport.
    - Center is zenith (alt=90).
    - Horizon (alt=0) maps to radius ~R at fov=180.
    Returns (x,y,inside).
    """
    fov = max(10.0, min(180.0, float(fov_deg)))

    # In azimuthal equidistant: r ∝ (90 - alt)
    max_r_deg = fov / 2.0
    r_deg = (90.0 - alt_deg)
    if r_deg < 0:
        r_deg = 0.0

    if cx is None:
        cx = w / 2.0
    if cy is None:
        cy = h / 2.0
    if R is None:
        R = 0.48 * min(w, h)

    r = (r_deg / max_r_deg) * R
    ang = math.radians(az_deg)

    x = cx + r * math.sin(ang)   # az=0 north
    y = cy - r * math.cos(ang)
    inside = (r_deg <= max_r_deg + 1e-6)
    return x, y, inside
