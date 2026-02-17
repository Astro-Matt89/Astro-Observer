"""
solar_bodies_renderer.py
========================
Renders Sun and Moon as physical disks onto the allsky raw photon buffer.

CALIBRATION TARGETS (post tone-map):
  Sun disk:         saturates to pure white (>800 ph/px pre-tone)
  Sun inner corona: bright halo 5-10° from disk
  Horizon glow:     amber at dawn/dusk, 20-40% full brightness
  Moon full:        bright disk ~180/255
  Moon crescent 6%: faint but visible disk ~60/255

All intensities are in raw photon units.  The _allsky_to_surface pipeline
applies asinh tone-mapping afterwards.
"""
from __future__ import annotations
import math
import numpy as np
from typing import Optional, Tuple


def _altaz_to_xy(alt_deg, az_deg, cx, cy, radius):
    if alt_deg < -0.5:
        return None
    r_px = (90.0 - alt_deg) / 90.0 * radius
    az_r  = math.radians(az_deg)
    return cx + r_px * math.sin(az_r), cy - r_px * math.cos(az_r)


def _paint_disk(field, px, py, radius_px, colour, intensity):
    """Limb-darkened circular disk."""
    H, W = field.shape[:2]
    R   = max(radius_px, 0.6)
    pad = int(math.ceil(R)) + 2
    x0=max(0,int(px)-pad); x1=min(W,int(px)+pad+1)
    y0=max(0,int(py)-pad); y1=min(H,int(py)+pad+1)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dr = np.sqrt((xx-px)**2 + (yy-py)**2)
    limb = np.sqrt(np.clip(1.0 - (dr/R)**2, 0.0, 1.0))
    for c, col in enumerate(colour):
        field[y0:y1, x0:x1, c] += limb * intensity * col


def _paint_glow(field, px, py, sigma, colour, intensity):
    """Gaussian glow/halo."""
    H, W = field.shape[:2]
    pad = int(math.ceil(sigma * 4))
    x0=max(0,int(px)-pad); x1=min(W,int(px)+pad+1)
    y0=max(0,int(py)-pad); y1=min(H,int(py)+pad+1)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    gauss = np.exp(-((xx-px)**2+(yy-py)**2) / (2.0*sigma**2))
    for c, col in enumerate(colour):
        field[y0:y1, x0:x1, c] += gauss * intensity * col


# ── Sun ───────────────────────────────────────────────────────────────────────

SUN_ANGULAR_DIAM_DEG = 0.533

SUN_DISK_COL   = (1.00, 0.95, 0.78)   # 5778K warm white
SUN_CORONA_COL = (1.00, 0.85, 0.50)   # inner corona / bloom
SUN_GLOW_COL   = (1.00, 0.60, 0.20)   # horizon glow (amber/orange)


def render_sun(field, sun_alt_deg, sun_az_deg, cx, cy, radius, exposure_s=1.0):
    """
    Render the Sun.

    Three components:
      1. Disk:          visible when alt > 0, saturates tone-map to white
      2. Inner corona:  gaussian bloom around disk (lens optics)
      3. Horizon glow:  amber scatter near solar direction
                        → present at twilight AND daytime
                        → scales with sky_bg (not overwhelming at night)

    Glow intensity is calibrated relative to a reference sky level so it
    naturally dominates at dawn/dusk but is invisible deep at night.
    """
    disk_r_px = (SUN_ANGULAR_DIAM_DEG / 2.0) / 90.0 * radius

    # ── 1. Solar disk (above horizon only) ───────────────────────────
    if sun_alt_deg > 0.0:
        pos = _altaz_to_xy(sun_alt_deg, sun_az_deg, cx, cy, radius)
        if pos is not None:
            px, py = pos
            airmass = 1.0 / max(math.sin(math.radians(sun_alt_deg)), 0.05)
            atm_ext = 0.20 * airmass
            # 800× exposure → well above white point → saturates to white
            sun_flux = 800.0 * exposure_s * 10**(-0.4 * atm_ext)
            _paint_disk(field, px, py, disk_r_px, SUN_DISK_COL, sun_flux)
            # Inner corona: sigma = 2.5× disk radius
            _paint_glow(field, px, py, disk_r_px * 2.5, SUN_CORONA_COL,
                        sun_flux * 0.06)
            # Flare streak toward image centre
            _paint_lens_flare(field, px, py, cx, cy, sun_flux * 0.015, SUN_GLOW_COL)

    # ── 2. Horizon glow (twilight -18°→0° and low sun 0°→20°) ────────
    glow_alt = max(sun_alt_deg, -18.0)
    if glow_alt > -18.0:
        # Anchor at horizon edge in solar azimuth
        az_r  = math.radians(sun_az_deg)
        r_hor = radius * 0.97
        gx = cx + r_hor * math.sin(az_r)
        gy = cy - r_hor * math.cos(az_r)

        # Strength: peaks at horizon crossing, fades both below and above
        if sun_alt_deg <= 0.0:
            # Twilight: linear ramp from -18° to 0°
            twi = ((glow_alt + 18.0) / 18.0) ** 2.0
        else:
            # After sunrise: fades as sun rises
            twi = max(0.0, 1.0 - sun_alt_deg / 20.0) ** 1.5

        # Reference sky level at night (bg_B * exp * sky_scale_night ≈ 5 ph/px)
        # Glow target: 2.5× that at peak → glow = 12.5 ph/px
        # This ensures glow is visible but not overwhelming
        sky_night_ref = 5.0 * exposure_s
        glow_peak = sky_night_ref * 2.5 * twi

        # Wide diffuse glow (sigma = 28% of radius → ~56° spread)
        _paint_glow(field, gx, gy, radius * 0.28, SUN_GLOW_COL,  glow_peak)
        # Narrow bright core (sigma = 10% → ~20° spread)
        _paint_glow(field, gx, gy, radius * 0.10, SUN_CORONA_COL, glow_peak * 0.5)


def _paint_lens_flare(field, px, py, cx, cy, intensity, colour):
    H, W = field.shape[:2]
    dx = cx - px; dy = cy - py
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 2: return
    dx /= dist; dy /= dist
    for frac in (0.30, 0.50, 0.70):
        fx = px + dx * dist * frac
        fy = py + dy * dist * frac
        _paint_glow(field, fx, fy, dist * 0.035, colour, intensity * 0.35)


# ── Moon ──────────────────────────────────────────────────────────────────────

MOON_ANGULAR_DIAM_DEG = 0.518
MOON_LIT_COL  = (0.95, 0.92, 0.85)   # sunlit disk — warm grey-white
MOON_GLOW_COL = (0.80, 0.85, 1.00)   # atmospheric halo — slightly blue


def render_moon(field, moon_alt_deg, moon_az_deg, phase_fraction, phase_angle_deg,
                cx, cy, radius, exposure_s=1.0):
    """
    Render the Moon with correct phase illumination.

    Phase:
      phase_fraction = (1 + cos(phase_angle)) / 2
        1.0 → full moon (brightest)
        0.5 → quarter
        0.0 → new moon (invisible)

    Flux calibration:
      Full moon, zenith, 1s: moon_flux = 40 ph/px → bright disk post-tone-map
      Crescent 6%, 21°alt, 1.5s: ~1.3 ph/px → faint but visible
    """
    if moon_alt_deg < -1.0 or phase_fraction < 0.01:
        return
    pos = _altaz_to_xy(moon_alt_deg, moon_az_deg, cx, cy, radius)
    if pos is None:
        return
    px, py = pos

    # Altitude factor (sin) — moon near horizon is dimmer through atmosphere
    alt_factor = max(0.0, math.sin(math.radians(max(0.0, moon_alt_deg))))
    rel_flux   = phase_fraction * alt_factor

    # Disk radius
    disk_r_px = (MOON_ANGULAR_DIAM_DEG / 2.0) / 90.0 * radius

    # Calibrated flux: full moon zenith 1s → 40 ph/px (post-scale, pre-tone)
    moon_flux = rel_flux * 40.0 * exposure_s

    if moon_flux < 0.1:
        return

    # Disk with phase mask
    _paint_moon_disk(field, px, py, disk_r_px, phase_angle_deg,
                     moon_flux, MOON_LIT_COL)

    # Atmospheric glow (proportional to phase)
    glow = moon_flux * phase_fraction * 0.25
    _paint_glow(field, px, py, disk_r_px * 4.0,  MOON_GLOW_COL, glow * 0.5)
    _paint_glow(field, px, py, disk_r_px * 10.0, MOON_GLOW_COL, glow * 0.12)


def _paint_moon_disk(field, px, py, radius_px, phase_angle_deg, intensity, colour):
    """
    Paint Moon disk with correct phase illumination.

    The terminator divides the disk into lit and dark halves.
    phase_angle=0°  → full (all lit)
    phase_angle=90° → quarter (right half lit, waxing)
    phase_angle=180°→ new (all dark)
    """
    H, W = field.shape[:2]
    R   = max(radius_px, 0.6)
    pad = int(math.ceil(R)) + 2
    x0=max(0,int(px)-pad); x1=min(W,int(px)+pad+1)
    y0=max(0,int(py)-pad); y1=min(H,int(py)+pad+1)

    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    nx = (xx - px) / R
    ny = (yy - py) / R
    dr2 = nx**2 + ny**2

    inside = dr2 <= 1.0
    limb   = np.sqrt(np.clip(1.0 - dr2, 0.0, 1.0))   # limb darkening

    # Terminator: lit side determined by phase_angle
    # cos(0°)=+1 → full lit; cos(90°)=0 → half; cos(180°)=-1 → new
    cos_pa = math.cos(math.radians(phase_angle_deg))
    ny_safe = np.sqrt(np.clip(1.0 - ny**2, 0.0, 1.0))
    x_term  = -cos_pa * ny_safe   # terminator x-position at height ny

    if phase_angle_deg <= 180.0:
        lit = nx >= x_term    # waxing: right (east) side lit
    else:
        cos_pa2 = math.cos(math.radians(360.0 - phase_angle_deg))
        x_term2 = -cos_pa2 * ny_safe
        lit = nx <= x_term2   # waning: left (west) side lit

    # Subtle mare texture on lit face
    mare = 0.88 + 0.12 * np.sin(nx * 6.2 + 1.1) * np.cos(ny * 7.8 - 0.4)

    mask = inside.astype(np.float32) * lit.astype(np.float32) * limb * mare
    for c, col in enumerate(colour):
        field[y0:y1, x0:x1, c] += mask * intensity * col


# ── Planets & Minor Bodies ────────────────────────────────────────────────────

def render_planet(field, body, cx, cy, radius, exposure_s=1.0):
    """
    Render a planet or minor body onto the allsky photon field.

    Usa le magnitudini fisiche accurate da planet_physics.
    Per pianeti con diametro apparente > 1px disegna un disco.
    Per Saturno aggiunge un'ellisse per gli anelli.
    Per Mercurio/Venere applica la maschera di fase.
    """
    alt = body.altitude_deg
    az  = body.azimuth_deg
    mag = body.apparent_mag

    if alt < 0.5:
        return
    pos = _altaz_to_xy(alt, az, cx, cy, radius)
    if pos is None:
        return
    px, py = pos

    # Colore B-V → RGB
    from imaging.sky_renderer import bv_to_rgb, mag_to_flux
    bv = getattr(body, 'bv_base', None) or getattr(body, 'bv_color', 0.6)
    # Correzione colore per fase (Venere, Marte)
    from universe.planet_physics import phase_bv_correction
    phase_deg = getattr(body, '_phase_angle', 0.0)
    bv = phase_bv_correction(bv, phase_deg, body.uid)
    rc, gc, bc = bv_to_rgb(bv)

    # Flusso fisico in fotoni (stessa pipeline delle stelle)
    airmass = 1.0 / max(math.sin(math.radians(alt)), 0.05)
    ext_mag = 0.20 * airmass   # estinzione atmosferica standard
    eff_mag = mag + ext_mag

    # Area apertura allsky (cm²) — dal renderer
    area_cm2 = math.pi * 1.25**2   # 25mm apertura, come allsky
    photons = mag_to_flux(eff_mag, area_cm2, exposure_s) * 0.78   # QE

    if photons < 0.01:
        return

    # Diametro apparente in pixel
    diam_arcsec = getattr(body, 'apparent_diameter_arcsec',
                           lambda: 0.0)() if callable(
                           getattr(body, 'apparent_diameter_arcsec', None)
                           ) else getattr(body, 'apparent_diameter_arcsec', 0.0)
    arcsec_per_px = (180.0 * 3600.0) / (2.0 * radius)
    diam_px = diam_arcsec / arcsec_per_px if arcsec_per_px > 0 else 0.0
    disk_r  = max(diam_px / 2.0, 0.5)

    uid = getattr(body, 'uid', '').upper()

    # ── Saturno: ellisse anelli ───────────────────────────────────────────
    if uid == "SATURN":
        B_deg = getattr(body, 'ring_inclination_B', 0.0)
        _paint_saturn_rings(field, px, py, disk_r, B_deg,
                            body._distance_au, radius, photons * 0.7,
                            (rc, gc, bc))

    # ── Disco pianeta ─────────────────────────────────────────────────────
    if uid in ("MERCURY", "VENUS") and phase_deg > 5.0:
        # Fase visibile: usa maschera di fase
        _paint_moon_disk(field, px, py, disk_r, phase_deg, photons, (rc, gc, bc))
    elif disk_r >= 0.8:
        # Disco risolvibile (Giove, Saturno, Marte vicino)
        colour = (rc, gc, bc)
        _paint_disk(field, px, py, disk_r, colour, photons)
    else:
        # Punto stellare (stelle deboli, oggetti minori, pianeti lontani)
        H, W = field.shape[:2]
        ix = int(round(px)); iy = int(round(py))
        if 0 <= iy < H and 0 <= ix < W:
            field[iy, ix, 0] += photons * rc
            field[iy, ix, 1] += photons * gc
            field[iy, ix, 2] += photons * bc
        # Alone per pianeti brillanti (mag < 2)
        if mag < 2.0:
            glow_s = max(0.8, (2.0 - mag) * 0.6)
            _paint_glow(field, px, py, glow_s, (rc, gc, bc), photons * 0.15)


def _paint_saturn_rings(field, px, py, disk_r_px, B_deg,
                         distance_au, render_radius, intensity, colour):
    """
    Disegna gli anelli di Saturno come ellisse.
    B_deg: inclinazione (0=taglio, 26.7=massima apertura).
    """
    from universe.planet_physics import (SATURN_RING_OUTER_KM,
                                          _KM_PER_AU, _ARCSEC_PER_RAD)
    ring_au   = SATURN_RING_OUTER_KM / _KM_PER_AU
    ring_arcsec = (ring_au / max(distance_au, 0.1)) * _ARCSEC_PER_RAD
    arcsec_per_px = (180.0 * 3600.0) / (2.0 * render_radius)
    ring_a = ring_arcsec / arcsec_per_px       # semiasse maggiore (px)
    ring_b = ring_a * abs(math.sin(math.radians(B_deg)))  # semiasse minore

    if ring_a < 0.5:
        return

    H, W = field.shape[:2]
    pad = int(math.ceil(ring_a)) + 2
    x0 = max(0, int(px)-pad); x1 = min(W, int(px)+pad+1)
    y0 = max(0, int(py)-pad); y1 = min(H, int(py)+pad+1)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)

    dx_ = (xx - px) / max(ring_a, 0.1)
    dy_ = (yy - py) / max(ring_b, 0.1) if ring_b > 0.1 else np.zeros_like(dx_)
    ell  = dx_**2 + dy_**2

    # Anello: corona tra raggio interno (0.6×) e esterno (1.0×)
    ring_mask = ((ell >= 0.35) & (ell <= 1.0)).astype(np.float32)
    # Sfuma i bordi
    ring_mask *= np.clip(1.0 - (ell - 0.35) / 0.05, 0, 1) + np.clip(1.0 - (1.0 - ell) / 0.05, 0, 1)
    ring_mask = np.clip(ring_mask, 0, 1)

    for c, col in enumerate(colour):
        field[y0:y1, x0:x1, c] += ring_mask * intensity * 0.6 * col


# ── Dispatcher aggiornato ─────────────────────────────────────────────────────

def render_solar_bodies(field, solar_bodies, cx, cy, radius, exposure_s=1.0):
    """
    Render all Solar System bodies: Sun, Moon, planets, minor bodies.
    solar_bodies: lista di OrbitalBody e/o MinorBody/CometBody.
    """
    for body in solar_bodies:
        if body.is_sun:
            render_sun(field, body.altitude_deg, body.azimuth_deg,
                       cx, cy, radius, exposure_s)
        elif body.is_moon:
            render_moon(field, body.altitude_deg, body.azimuth_deg,
                        body.phase_fraction, body._phase_angle,
                        cx, cy, radius, exposure_s)
        else:
            # Pianeti e oggetti minori
            try:
                render_planet(field, body, cx, cy, radius, exposure_s)
            except Exception:
                pass   # Non bloccare il render per un singolo corpo
