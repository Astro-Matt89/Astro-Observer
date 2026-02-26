"""
astro_engine.coordinates — Coordinate transformation utilities.

All angles are in degrees unless stated otherwise.
Julian Dates follow the standard astronomical convention (JD 2451545.0 = J2000.0).

Functions
---------
altaz_to_equatorial
    (alt, az) → (ra, dec) given observer position and time.
equatorial_to_altaz
    (ra, dec) → (alt, az) — thin wrapper around the existing implementation.
equatorial_to_galactic
    (ra, dec) → galactic (l, b).
galactic_to_equatorial
    (l, b) → (ra, dec).
compute_gmst
    GMST in degrees for a Julian Date.
compute_lst
    LST in degrees for a Julian Date and observer longitude.
airmass
    Airmass factor as a function of altitude (Rozenberg formula).
angular_separation
    Great-circle angular distance between two (alt, az) positions.
solar_position
    Apparent solar (alt, az) for a given Julian Date and observer location.
"""

from __future__ import annotations

import math
from typing import Tuple

from universe.orbital_body import equatorial_to_altaz as _equatorial_to_altaz  # re-export


# ---------------------------------------------------------------------------
# Galactic pole / reference direction (IAU 1958, J2000 precessed)
# ---------------------------------------------------------------------------

# Galactic North Pole in equatorial J2000 coordinates
_GNP_RA_DEG: float = 192.859_508
_GNP_DEC_DEG: float = 27.128_336

# Galactic Centre direction in equatorial J2000 coordinates
_GC_RA_DEG: float = 266.405_100
_GC_DEC_DEG: float = -28.936_175

# GMST coefficients (IAU 1982)
_GMST_OFFSET_DEG: float = 280.460_618_37
_GMST_RATE_DEG_PER_DAY: float = 360.985_647_366_29
_GMST_T2_COEF: float = 0.000_387_933
_GMST_T3_DENOM: float = 38_710_000.0


# ---------------------------------------------------------------------------
# GMST / LST
# ---------------------------------------------------------------------------

def compute_gmst(jd: float) -> float:
    """
    Greenwich Mean Sidereal Time in degrees [0, 360).

    Uses the IAU 1982 formula accurate to ~0.1 arcsec over ±50 years of J2000.

    Parameters
    ----------
    jd : float
        Julian Date (TT ≈ UTC for our purposes).

    Returns
    -------
    float
        GMST in degrees, range [0, 360).
    """
    T = (jd - 2451545.0) / 36525.0
    gmst = (_GMST_OFFSET_DEG
            + _GMST_RATE_DEG_PER_DAY * (jd - 2451545.0)
            + _GMST_T2_COEF * T * T
            - T * T * T / _GMST_T3_DENOM)
    return gmst % 360.0


def compute_lst(jd: float, lon_deg: float) -> float:
    """
    Local Sidereal Time in degrees [0, 360).

    Parameters
    ----------
    jd : float
        Julian Date.
    lon_deg : float
        Observer geographic longitude in degrees (east positive).

    Returns
    -------
    float
        LST in degrees, range [0, 360).
    """
    return (compute_gmst(jd) + lon_deg) % 360.0


# ---------------------------------------------------------------------------
# Alt/Az ↔ Equatorial
# ---------------------------------------------------------------------------

def equatorial_to_altaz(
    ra_deg: float,
    dec_deg: float,
    lat_deg: float,
    lon_deg: float,
    jd: float,
) -> Tuple[float, float]:
    """
    Convert equatorial J2000 (RA, Dec) to horizontal (alt, az).

    Delegates to the authoritative implementation in
    :func:`universe.orbital_body.equatorial_to_altaz`.

    Parameters
    ----------
    ra_deg : float
        Right ascension in degrees.
    dec_deg : float
        Declination in degrees.
    lat_deg : float
        Observer latitude in degrees (north positive).
    lon_deg : float
        Observer longitude in degrees (east positive).
    jd : float
        Julian Date.

    Returns
    -------
    tuple[float, float]
        ``(altitude_deg, azimuth_deg)`` where azimuth is measured north-through-east.
    """
    return _equatorial_to_altaz(ra_deg, dec_deg, lat_deg, lon_deg, jd)


def altaz_to_equatorial(
    alt_deg: float,
    az_deg: float,
    lat_deg: float,
    lon_deg: float,
    jd: float,
) -> Tuple[float, float]:
    """
    Convert horizontal (alt, az) to equatorial J2000 (RA, Dec).

    Parameters
    ----------
    alt_deg : float
        Altitude in degrees above the horizon.
    az_deg : float
        Azimuth in degrees, measured north-through-east.
    lat_deg : float
        Observer latitude in degrees.
    lon_deg : float
        Observer longitude in degrees (east positive).
    jd : float
        Julian Date.

    Returns
    -------
    tuple[float, float]
        ``(ra_deg, dec_deg)`` in the J2000 frame.
    """
    lst = compute_lst(jd, lon_deg)

    alt_r = math.radians(alt_deg)
    az_r = math.radians(az_deg)
    lat_r = math.radians(lat_deg)

    sin_dec = (math.sin(alt_r) * math.sin(lat_r)
               + math.cos(alt_r) * math.cos(lat_r) * math.cos(az_r))
    sin_dec = max(-1.0, min(1.0, sin_dec))
    dec_r = math.asin(sin_dec)

    cos_ha_num = math.sin(alt_r) - math.sin(dec_r) * math.sin(lat_r)
    cos_ha_den = math.cos(dec_r) * math.cos(lat_r)
    cos_ha = max(-1.0, min(1.0, cos_ha_num / (cos_ha_den + 1e-12)))
    ha_r = math.acos(cos_ha)
    if math.sin(az_r) > 0:
        ha_r = 2 * math.pi - ha_r

    ha_deg = math.degrees(ha_r)
    ra_deg = (lst - ha_deg) % 360.0
    dec_deg = math.degrees(dec_r)
    return ra_deg, dec_deg


# ---------------------------------------------------------------------------
# Galactic ↔ Equatorial
# ---------------------------------------------------------------------------

def _unit_vector(dec_deg: float, ra_deg: float) -> Tuple[float, float, float]:
    """Return unit Cartesian vector for equatorial (ra, dec) in degrees."""
    dec_r = math.radians(dec_deg)
    ra_r = math.radians(ra_deg)
    return (
        math.cos(dec_r) * math.cos(ra_r),
        math.cos(dec_r) * math.sin(ra_r),
        math.sin(dec_r),
    )


def equatorial_to_galactic(ra_deg: float, dec_deg: float) -> Tuple[float, float]:
    """
    Convert equatorial J2000 (RA, Dec) to galactic coordinates (l, b).

    Parameters
    ----------
    ra_deg : float
        Right ascension in degrees.
    dec_deg : float
        Declination in degrees.

    Returns
    -------
    tuple[float, float]
        ``(l_deg, b_deg)`` — galactic longitude [0, 360) and latitude [-90, 90].
    """
    # Unit vector of the target point
    vx, vy, vz = _unit_vector(dec_deg, ra_deg)

    # Galactic North Pole unit vector
    gx, gy, gz = _unit_vector(_GNP_DEC_DEG, _GNP_RA_DEG)

    # Galactic Centre unit vector
    cx_gc, cy_gc, cz_gc = _unit_vector(_GC_DEC_DEG, _GC_RA_DEG)

    # Galactic latitude: sin(b) = v · gnp
    sin_b = vx * gx + vy * gy + vz * gz
    sin_b = max(-1.0, min(1.0, sin_b))
    b_deg = math.degrees(math.asin(sin_b))

    # Galactic longitude: project v onto galactic plane and measure from GC
    # Build gc_plane (GC direction projected onto galactic plane, normalised)
    dot_gc_gnp = cx_gc * gx + cy_gc * gy + cz_gc * gz
    p_x = cx_gc - dot_gc_gnp * gx
    p_y = cy_gc - dot_gc_gnp * gy
    p_z = cz_gc - dot_gc_gnp * gz
    p_norm = math.sqrt(p_x * p_x + p_y * p_y + p_z * p_z) + 1e-15
    p_x /= p_norm
    p_y /= p_norm
    p_z /= p_norm

    # East galactic direction = gnp × gc_plane
    e_x = gy * p_z - gz * p_y
    e_y = gz * p_x - gx * p_z
    e_z = gx * p_y - gy * p_x

    dot_p = vx * p_x + vy * p_y + vz * p_z
    dot_e = vx * e_x + vy * e_y + vz * e_z
    l_deg = math.degrees(math.atan2(dot_e, dot_p)) % 360.0

    return l_deg, b_deg


def galactic_to_equatorial(l_deg: float, b_deg: float) -> Tuple[float, float]:
    """
    Convert galactic coordinates (l, b) to equatorial J2000 (RA, Dec).

    Parameters
    ----------
    l_deg : float
        Galactic longitude in degrees [0, 360).
    b_deg : float
        Galactic latitude in degrees [-90, 90].

    Returns
    -------
    tuple[float, float]
        ``(ra_deg, dec_deg)`` in degrees.
    """
    # Galactic frame unit vectors in equatorial coordinates
    gx, gy, gz = _unit_vector(_GNP_DEC_DEG, _GNP_RA_DEG)
    cx_gc, cy_gc, cz_gc = _unit_vector(_GC_DEC_DEG, _GC_RA_DEG)

    dot_gc_gnp = cx_gc * gx + cy_gc * gy + cz_gc * gz
    p_x = cx_gc - dot_gc_gnp * gx
    p_y = cy_gc - dot_gc_gnp * gy
    p_z = cz_gc - dot_gc_gnp * gz
    p_norm = math.sqrt(p_x * p_x + p_y * p_y + p_z * p_z) + 1e-15
    p_x /= p_norm
    p_y /= p_norm
    p_z /= p_norm

    e_x = gy * p_z - gz * p_y
    e_y = gz * p_x - gx * p_z
    e_z = gx * p_y - gy * p_x

    # Galactic (l, b) → equatorial Cartesian
    l_r = math.radians(l_deg)
    b_r = math.radians(b_deg)
    cos_b = math.cos(b_r)
    sin_b = math.sin(b_r)
    cos_l = math.cos(l_r)
    sin_l = math.sin(l_r)

    vx = cos_b * cos_l * p_x + cos_b * sin_l * e_x + sin_b * gx
    vy = cos_b * cos_l * p_y + cos_b * sin_l * e_y + sin_b * gy
    vz = cos_b * cos_l * p_z + cos_b * sin_l * e_z + sin_b * gz

    dec_deg = math.degrees(math.asin(max(-1.0, min(1.0, vz))))
    ra_deg = math.degrees(math.atan2(vy, vx)) % 360.0
    return ra_deg, dec_deg


# ---------------------------------------------------------------------------
# Airmass
# ---------------------------------------------------------------------------

def airmass(alt_deg: float) -> float:
    """
    Airmass factor as a function of altitude using the Rozenberg (1966) formula.

    The Rozenberg formula is accurate to ~0.5 % down to the horizon and avoids
    the singularity at alt = 0° that affects the simple ``1/sin(alt)`` formula.

    Parameters
    ----------
    alt_deg : float
        Altitude above horizon in degrees.  Values below −2° are clamped.

    Returns
    -------
    float
        Airmass X ≥ 1.  Returns ~38 at the horizon (alt = 0°).
    """
    alt_clamped = max(-2.0, alt_deg)
    alt_r = math.radians(alt_clamped)
    # Rozenberg 1966: X = 1 / (sin(alt) + 0.025 * exp(11.1 * sin(alt)))
    sin_alt = math.sin(alt_r)
    denom = sin_alt + 0.025 * math.exp(-11.1 * sin_alt)
    return 1.0 / max(denom, 1e-6)


# ---------------------------------------------------------------------------
# Angular separation
# ---------------------------------------------------------------------------

def angular_separation(
    alt1_deg: float,
    az1_deg: float,
    alt2_deg: float,
    az2_deg: float,
) -> float:
    """
    Great-circle angular distance between two points in horizontal coordinates.

    Uses the haversine formula for numerical stability at small separations.

    Parameters
    ----------
    alt1_deg, az1_deg : float
        Altitude and azimuth of the first point in degrees.
    alt2_deg, az2_deg : float
        Altitude and azimuth of the second point in degrees.

    Returns
    -------
    float
        Angular separation in degrees, in [0, 180].
    """
    alt1_r = math.radians(alt1_deg)
    alt2_r = math.radians(alt2_deg)
    daz_r = math.radians(az2_deg - az1_deg)
    dalt_r = math.radians(alt2_deg - alt1_deg)

    a = (math.sin(dalt_r / 2.0) ** 2
         + math.cos(alt1_r) * math.cos(alt2_r) * math.sin(daz_r / 2.0) ** 2)
    a = max(0.0, min(1.0, a))
    return math.degrees(2.0 * math.asin(math.sqrt(a)))


# ---------------------------------------------------------------------------
# Solar position
# ---------------------------------------------------------------------------

# Obliquity of the ecliptic at J2000.0 (degrees)
_OBLIQUITY_J2000: float = 23.43928


def solar_position(jd: float, lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    """
    Apparent solar altitude and azimuth for a given time and observer location.

    Uses the VSOP87 low-precision algorithm (accuracy ~0.01°) extracted from
    :meth:`~universe.orbital_body.OrbitalBody._compute_sun_position`.

    Parameters
    ----------
    jd : float
        Julian Date (TT ≈ UTC for visual purposes).
    lat_deg : float
        Observer geographic latitude in degrees (north positive).
    lon_deg : float
        Observer geographic longitude in degrees (east positive).

    Returns
    -------
    tuple[float, float]
        ``(solar_alt_deg, solar_az_deg)`` — apparent solar altitude and
        azimuth in degrees.  Altitude is negative when the Sun is below
        the horizon.
    """
    T = (jd - 2451545.0) / 36525.0

    # Geometric mean longitude of the Sun (degrees)
    L0 = (280.46646 + 36000.76983 * T) % 360.0
    # Mean anomaly
    M = (357.52911 + 35999.05029 * T - 0.0001537 * T * T) % 360.0
    M_r = math.radians(M)
    # Equation of center
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_r)
         + (0.019993 - 0.000101 * T) * math.sin(2.0 * M_r)
         + 0.000289 * math.sin(3.0 * M_r))
    # Sun's true longitude
    sun_lon = L0 + C
    # Apparent longitude (aberration + nutation correction)
    omega = (125.04 - 1934.136 * T) % 360.0
    lam = sun_lon - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    # Obliquity with nutation correction
    eps = _OBLIQUITY_J2000 - 0.013004 * T + 0.00000164 * T * T
    eps_r = math.radians(eps + 0.00256 * math.cos(math.radians(omega)))
    lam_r = math.radians(lam)

    # Geocentric equatorial coordinates
    ra_r = math.atan2(math.cos(eps_r) * math.sin(lam_r), math.cos(lam_r))
    dec_r = math.asin(math.sin(eps_r) * math.sin(lam_r))
    ra_deg = math.degrees(ra_r) % 360.0
    dec_deg = math.degrees(dec_r)

    return equatorial_to_altaz(ra_deg, dec_deg, lat_deg, lon_deg, jd)
