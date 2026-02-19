"""
AllSkyRenderer — Full-hemisphere fish-eye sky renderer.

SKY_SCALE adattivo: notte scura (0.055) → crepuscolo (0.008) → giorno (0.001)
Stelle: singolo pixel per mag>=3, PSF 3x3 per mag<3, PSF 5x5 per mag<0
"""
from __future__ import annotations
import math
import numpy as np
from typing import Optional, Tuple

from imaging.sky_renderer import mag_to_flux, bv_to_rgb
from imaging.celestial_bodies import (draw_sun, draw_moon,
                                       draw_atmospheric_glow)
from imaging.solar_bodies_renderer import render_solar_bodies, render_planet
from universe.orbital_body import equatorial_to_altaz
from atmosphere.cloud_layer import CloudLayer

def _sky_scale(solar_alt_deg: float) -> float:
    """
    Fattore scala adattivo per sky_bg_* in base all'altitudine solare.
    Calibrato perché bg_B_post-scale sia:
      notte (<-12°):  ~5 ph/px   (deep dark)
      civil dusk (0°): ~25 ph/px (glow visibile)
      mattino (+15°): ~140 ph/px (cielo blu)
      mezzogiorno:    ~500 ph/px (pieno)
    """
    if solar_alt_deg < -12.0:
        return 0.055
    elif solar_alt_deg < 0.0:
        t = (solar_alt_deg + 12.0) / 12.0
        return 0.055 * (1 - t) + 0.008 * t
    elif solar_alt_deg < 15.0:
        t = solar_alt_deg / 15.0
        return 0.008 * (1 - t) + 0.001 * t
    else:
        return max(0.0005, 0.001 * (1.0 - (solar_alt_deg - 15.0) / 75.0))

def _make_psf(sigma: float, size: int) -> np.ndarray:
    k = np.arange(size) - size // 2
    g = np.exp(-0.5 * (k / sigma) ** 2)
    psf = np.outer(g, g)
    return (psf / psf.sum()).astype(np.float32)

def _radec_to_xy(ra_deg, dec_deg, jd, lat, lon, cx, cy, radius):
    alt, az = equatorial_to_altaz(ra_deg, dec_deg, lat, lon, jd)
    if alt < 0.5:
        return None
    r_px = (90.0 - alt) / 90.0 * radius
    az_r  = math.radians(az)
    return cx + r_px * math.sin(az_r), cy - r_px * math.cos(az_r), alt

def _gain_mult(gain_sw: int) -> float:
    """
    Multiplicatore segnale relativo a gain_sw=200 (reference).
    ADU = electrons / gain_e_per_adu
    gain_ref ≈ 0.776 e/ADU (gain=200)  →  gain=50: 0.41×  gain=400: 1.78×
    """
    g_eff = 3.6 / (1.0 + gain_sw / 55.0)
    g_ref = 3.6 / (1.0 + 200.0 / 55.0)
    return g_ref / g_eff

def build_allsky_background(size: int, atm_state, exposure_s: float = 1.0,
                             gain_sw: int = 200) -> np.ndarray:
    H = W = size
    cx = cy = size * 0.5
    radius = size * 0.5 - 1.5
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx;  dy = yy - cy
    r_px   = np.sqrt(dx * dx + dy * dy)
    r_norm = np.clip(r_px / radius, 0.0, 1.0)
    inside = (r_px <= radius).astype(np.float32)

    # Get transparency from atmospheric state
    transparency = getattr(atm_state, 'transparency', 1.0)

    if atm_state is not None:
        solar_alt  = atm_state.solar_alt_deg
        solar_az_r = math.radians(float(getattr(atm_state, 'solar_az_deg', 180.0)))
        scale = _sky_scale(solar_alt)
        gm = _gain_mult(gain_sw)
        bg_r = atm_state.sky_bg_r * exposure_s * scale * gm * transparency
        bg_g = atm_state.sky_bg_g * exposure_s * scale * gm * transparency
        bg_b = atm_state.sky_bg_b * exposure_s * scale * gm * transparency
    else:
        solar_alt  = -30.0
        solar_az_r = math.pi
        gm = _gain_mult(gain_sw)
        bg_r = 0.10 * exposure_s * gm * transparency
        bg_g = 0.20 * exposure_s * gm * transparency
        bg_b = 0.60 * exposure_s * gm * transparency

    # Airmass gradient
    horizon_boost = 1.20 if solar_alt < -12.0 else (1.45 if solar_alt < 0.0 else 1.8)
    alt_gradient  = 1.0 + r_norm * (horizon_boost - 1.0)

    # Spatial noise
    noise_scale = 0.025 * max(bg_b, 0.1)
    nx  = np.sin(xx * 0.012 + 1.3) * np.cos(yy * 0.015 + 0.7)
    nx += 0.4 * np.sin(xx * 0.031 - 2.1) * np.cos(yy * 0.027 + 1.8)
    nx += 0.2 * np.sin(xx * 0.058 + 0.4) * np.cos(yy * 0.063 - 1.2)
    nx  = nx / (nx.std() + 1e-9) * 0.5
    sky_noise = nx * noise_scale

    # Twilight glow (solo -18° < alt < 0°; il disco solare viene da solar_bodies_renderer)
    az_map    = np.arctan2(dx, -dy)
    angle_sun = (az_map - solar_az_r + math.pi) % (2 * math.pi) - math.pi
    if -18.0 < solar_alt < 0.0:
        glow_str = ((solar_alt + 18.0) / 18.0) ** 1.5
        sun_glow = (np.exp(-angle_sun ** 2 / 0.5) *
                    np.clip((r_norm - 0.4) / 0.6, 0, 1) ** 1.2 * glow_str)
    else:
        sun_glow = np.zeros((H, W), np.float32)

    # Airglow band (only at deep night)
    if solar_alt < -18.0:
        airglow = np.exp(-((r_norm - 0.89) / 0.06) ** 2) * 0.4
    else:
        airglow = np.zeros((H, W), np.float32)

    R = (bg_r * alt_gradient + bg_r * sun_glow * 0.8 + sky_noise * 0.4) * inside
    G = (bg_g * alt_gradient + bg_g * sun_glow * 0.3 + sky_noise * 0.6
         + airglow * bg_g * 0.3) * inside
    B = (bg_b * alt_gradient + sun_glow * bg_b * 0.05 + sky_noise
         + airglow * bg_b * 0.15) * inside

    return np.stack([np.clip(R, 0, None), np.clip(G, 0, None), np.clip(B, 0, None)],
                    axis=-1).astype(np.float32)

def _apply_cloud_overlay(field: np.ndarray, cloud_layer: CloudLayer, 
                         cx: float, cy: float, radius: float) -> None:
    """
    Apply procedural cloud layer overlay to rendered field (in-place).
    For each pixel in the fisheye:
      - Convert (x,y) → (az, alt)
      - Query cloud_layer.get_coverage_at(az, alt) → coverage 0..1
      - Blend: darken background + add cloud color

    Cloud color: greyish-white (200, 210, 220) RGB photons
    """
    H, W = field.shape[:2]
    for row in range(H):
        for col in range(W):
            dx = col - cx
            dy = row - cy
            r = math.sqrt(dx * dx + dy * dy)
            if r > radius:
                continue  # Outside fisheye circle
            # Convert pixel to alt/az
            r_norm = r / radius
            alt = 90.0 * (1.0 - r_norm)  # 0° at edge, 90° at zenith
            az_rad = math.atan2(dx, -dy)  # N=0°, E=90°, ...
            az = math.degrees(az_rad) % 360.0
            # Get cloud coverage at this direction
            coverage = cloud_layer.get_coverage_at(az, alt)
            if coverage > 0.01:
                # Cloud color in photon units (greyish-white)
                cloud_rgb = np.array([200.0, 210.0, 220.0], dtype=np.float32) * coverage
                # Blend: darken sky + add cloud
                # coverage = 1.0 → 90% darkening + full cloud color
                # coverage = 0.5 → 45% darkening + half cloud color
                field[row, col] = field[row, col] * (1.0 - coverage * 0.9) + cloud_rgb


class AllSkyRenderer:
    FOCAL_LENGTH_MM = 3.0
    APERTURE_MM     = 25.0

    def __init__(self, camera_spec, observer_lat=45.0, observer_lon=9.0, render_size=512):
        self.spec        = camera_spec
        self.lat         = observer_lat
        self.lon         = observer_lon
        self.render_size = render_size
        self._psf3 = _make_psf(0.55, 3)
        self._psf5 = _make_psf(0.70, 5)
        ap_cm          = self.APERTURE_MM / 10.0
        self._area_cm2 = math.pi * (ap_cm / 2.0) ** 2
        self._qe       = camera_spec.quantum_efficiency
        
        # Cloud layer for procedural clouds (Sprint 14b)
        self.cloud_layer = CloudLayer(
            seed=42,
            wind_speed_deg_per_s=5.0,
            wind_direction_deg=270.0,  # West wind
            base_coverage=0.3
        )

    def render(self, jd: float, universe,
               exposure_s: float = 1.0,
               mag_limit:  float = 5.0,
               atm_state         = None,
               sun_body          = None,
               moon_body         = None,
               solar_bodies      = None,
               gain_sw:    int   = 200) -> np.ndarray:
        """
        Render the full allsky hemisphere.

        Parameters:
          sun_body     : OrbitalBody with is_sun=True  (already update_position called)
          moon_body    : OrbitalBody with is_moon=True (already update_position called)
          solar_bodies : lista completa (Sole+Luna+pianeti+minori), usata per
                         render_planet su tutti i corpi non-Sole non-Luna
        """
        S      = self.render_size
        cx = cy = S / 2.0
        radius  = S / 2.0 - 1.5
        
        # Update cloud layer with current time (Sprint 14b)
        self.cloud_layer.update(jd)

        # ── Background (sky colour + spatial noise + airglow) ──────────
        field = build_allsky_background(S, atm_state, exposure_s, gain_sw=gain_sw)

        # ── Atmospheric twilight glow (direzionale, prima delle stelle) ─
        solar_alt = atm_state.solar_alt_deg if atm_state else -90.0
        solar_az  = atm_state.solar_az_deg  if atm_state else 180.0
        if sun_body is not None:
            solar_alt = sun_body._alt_deg
            solar_az  = sun_body._az_deg
        draw_atmospheric_glow(field, solar_alt, solar_az, cx, cy, radius)

        # ── Stars (only if not full daylight) ───────────────────────────
        if solar_alt < 5.0:
            self._render_stars(field, jd, universe, mag_limit,
                               cx, cy, radius, exposure_s, atm_state,
                               gain_sw=gain_sw)

        # ── Solar disk ──────────────────────────────────────────────────
        transparency = getattr(atm_state, 'transparency', 1.0)
        if sun_body is not None:
            draw_sun(field, sun_body._alt_deg, sun_body._az_deg,
                     cx, cy, radius, S, gain_sw=gain_sw, exposure_s=exposure_s,
                     transparency=transparency)
        elif solar_alt > -2.0:
            draw_sun(field, solar_alt, solar_az, cx, cy, radius, S,
                     gain_sw=gain_sw, exposure_s=exposure_s,
                     transparency=transparency)

        # ── Lunar disk ──────────────────────────────────────────────────
        if moon_body is not None and moon_body._alt_deg > 0.5:
            draw_moon(field,
                      moon_body._alt_deg, moon_body._az_deg,
                      moon_body._phase_angle,
                      cx, cy, radius, S, gain_sw=gain_sw, exposure_s=exposure_s,
                      transparency=transparency)

        # ── Planets & minor bodies ───────────────────────────────────────
        if solar_bodies is not None:
            gm = _gain_mult(gain_sw)
            for body in solar_bodies:
                if body.is_sun or body.is_moon:
                    continue
                try:
                    render_planet(field, body, cx, cy, radius,
                                  exposure_s * gm)
                except Exception:
                    pass

        # ── Cloud overlay (Sprint 14b) ────────────────────────────────────
        _apply_cloud_overlay(field, self.cloud_layer, cx, cy, radius)

        return field

    def _render_stars(self, field, jd, universe, mag_limit,
                      cx, cy, radius, exposure_s, atm_state, gain_sw=200):
        H = W = self.render_size
        gm = _gain_mult(gain_sw)
        
        # Get transparency from atmospheric state
        transparency = getattr(atm_state, 'transparency', 1.0)
        
        for star in universe.get_stars():
            if star.mag > mag_limit:
                continue
            pos = _radec_to_xy(star.ra_deg, star.dec_deg, jd,
                               self.lat, self.lon, cx, cy, radius)
            if pos is None:
                continue
            px, py, alt = pos
            if not (0.5 <= px < W - 0.5 and 0.5 <= py < H - 0.5):
                continue
            eff_mag = star.mag
            if atm_state is not None:
                ext = atm_state.extinction_at(max(2.0, alt),
                                               getattr(star, 'bv_color', 0.6))
                eff_mag += ext
                if eff_mag > mag_limit + 0.3:
                    continue
            photons = (mag_to_flux(eff_mag, self._area_cm2 / math.pi * 2, exposure_s)
                       * self._qe * gm)
            photons *= transparency  # Scale by atmospheric transparency
            if photons < 0.3:
                continue
            bv = getattr(star, 'bv_color', 0.6)
            rc, gc, bc = bv_to_rgb(bv)
            ix = int(round(px)); iy = int(round(py))
            if eff_mag < 0.0:
                psf = self._psf5; half = 2
                y0=max(0,iy-half); y1=min(H,iy+half+1)
                x0=max(0,ix-half); x1=min(W,ix+half+1)
                ky0=half-(iy-y0); ky1=ky0+(y1-y0)
                kx0=half-(ix-x0); kx1=kx0+(x1-x0)
                if y0<y1 and x0<x1 and ky0<ky1 and kx0<kx1:
                    patch=psf[ky0:ky1,kx0:kx1]*photons
                    field[y0:y1,x0:x1,0]+=patch*rc
                    field[y0:y1,x0:x1,1]+=patch*gc
                    field[y0:y1,x0:x1,2]+=patch*bc
            elif eff_mag < 3.0:
                psf = self._psf3
                y0=max(0,iy-1); y1=min(H,iy+2)
                x0=max(0,ix-1); x1=min(W,ix+2)
                ky0=1-(iy-y0); ky1=ky0+(y1-y0)
                kx0=1-(ix-x0); kx1=kx0+(x1-x0)
                if y0<y1 and x0<x1 and ky0<ky1 and kx0<kx1:
                    patch=psf[ky0:ky1,kx0:kx1]*photons
                    field[y0:y1,x0:x1,0]+=patch*rc
                    field[y0:y1,x0:x1,1]+=patch*gc
                    field[y0:y1,x0:x1,2]+=patch*bc
            else:
                if 0<=iy<H and 0<=ix<W:
                    field[iy,ix,0]+=photons*rc
                    field[iy,ix,1]+=photons*gc
                    field[iy,ix,2]+=photons*bc

    def get_info(self):
        return {"camera": self.spec.name, "fov_deg": (180.0,180.0),
                "projection": "equidistant_azimuthal", "render_size": self.render_size}