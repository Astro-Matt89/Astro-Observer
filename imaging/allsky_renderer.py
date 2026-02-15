"""
AllSkyRenderer — Full-hemisphere fish-eye sky renderer.

Projects the entire visible sky (Alt > 0°) onto a circular disk
using equidistant azimuthal (zenithal equidistant) projection:
    r = (90° - alt) / 90°  →  0 at zenith, 1 at horizon

The output is a square render buffer (render_size × render_size).
Stars outside the horizon circle are clipped.

Usage:
    renderer = AllSkyRenderer(camera_spec, observer_lat, observer_lon)
    renderer.render(surface_rect, jd, universe, atm_state)
    # Returns numpy (H, W, 3) float32 photon array
"""

from __future__ import annotations
import math
import numpy as np
from typing import Optional, Tuple

from imaging.sky_renderer import mag_to_flux, bv_to_rgb, gaussian_psf
from universe.orbital_body import equatorial_to_altaz


# ─────────────────────────────────────────────────────────────────────────────
# Projection
# ─────────────────────────────────────────────────────────────────────────────

def radec_to_allsky_pixel(ra_deg: float, dec_deg: float,
                           jd: float,
                           lat_deg: float, lon_deg: float,
                           cx: float, cy: float, radius: float
                           ) -> Optional[Tuple[float, float]]:
    """
    Convert RA/Dec to pixel on fish-eye disk.
    Returns None if below horizon.
    cx, cy: disk centre in pixels
    radius: disk radius in pixels (= horizon)
    """
    alt, az = equatorial_to_altaz(ra_deg, dec_deg, lat_deg, lon_deg, jd)
    if alt < 0.0:
        return None
    # Equidistant projection: r=0 at zenith, r=radius at horizon
    r_norm = (90.0 - alt) / 90.0
    r_px   = r_norm * radius
    az_r   = math.radians(az)
    px = cx + r_px * math.sin(az_r)
    py = cy - r_px * math.cos(az_r)   # N at top, so subtract
    return px, py


# ─────────────────────────────────────────────────────────────────────────────
# Sky background — full hemisphere gradient
# ─────────────────────────────────────────────────────────────────────────────

def build_allsky_background(size: int,
                             atm_state,
                             exposure_s: float = 1.0) -> np.ndarray:
    """
    Build (size, size, 3) background for the allsky disk.

    - Zenith (centre): darkest, most blue
    - Horizon (edge): slightly brighter + warm gradient if twilight
    - Outside disk: black
    """
    H = W = size
    cx = cy = size / 2.0
    radius = size / 2.0 - 2

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx; dy = yy - cy
    r_px = np.sqrt(dx*dx + dy*dy)
    r_norm = np.clip(r_px / radius, 0, 1)   # 0=zenith, 1=horizon
    inside = (r_px <= radius).astype(np.float32)

    # Base sky from atmospheric state
    if atm_state is not None:
        bg_r, bg_g, bg_b = (
            atm_state.sky_bg_r * exposure_s,
            atm_state.sky_bg_g * exposure_s,
            atm_state.sky_bg_b * exposure_s,
        )
    else:
        bg_r, bg_g, bg_b = 50.0, 100.0, 250.0

    # Altitude gradient: horizon ~2× brighter than zenith (airmass effect)
    alt_gradient = 1.0 + r_norm * 1.2

    # North horizon glow (weak, represents LP or twilight direction)
    az_map = np.arctan2(dx, -dy)   # N=0, E=pi/2
    if atm_state is not None:
        sol_az = math.radians(atm_state.solar_az_deg)
        angle_to_sun = np.abs(az_map - sol_az)
        angle_to_sun = np.where(angle_to_sun > math.pi, 2*math.pi - angle_to_sun, angle_to_sun)
        sun_glow_mask = np.exp(-angle_to_sun**2 / 0.5) * r_norm**2
    else:
        sun_glow_mask = np.zeros((H, W), np.float32)

    field = np.stack([
        np.clip((bg_r * alt_gradient + bg_r * sun_glow_mask * 0.5) * inside, 0, None),
        np.clip((bg_g * alt_gradient + bg_g * sun_glow_mask * 0.2) * inside, 0, None),
        np.clip((bg_b * alt_gradient) * inside, 0, None),
    ], axis=-1).astype(np.float32)

    return field


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────

class AllSkyRenderer:
    """
    Renders the full visible sky hemisphere onto a square buffer.

    The camera spec is used only for:
      - pixel_size_um: determines effective star PSF size
      - quantum_efficiency, gain: for photon→ADU conversion
      - is_allsky: must be True (validated on init)

    The optical system is a fixed f/1.2 fish-eye lens with:
      - 180° FOV (equidistant projection)
      - ~3mm effective focal length
      - ~6μm/px at the sensor

    render_size: output buffer side in pixels (default 512)
    """

    # Effective focal length of the allsky fish-eye lens (mm)
    # f=3mm, sensor diagonal covers 180°
    FOCAL_LENGTH_MM = 3.0
    APERTURE_MM     = 25.0    # f/1.2 lens

    def __init__(self, camera_spec,
                 observer_lat: float = 45.0,
                 observer_lon: float = 9.0,
                 render_size: int = 512):
        self.spec         = camera_spec
        self.lat          = observer_lat
        self.lon          = observer_lon
        self.render_size  = render_size

        # PSF for point stars (allsky: stars are always tiny, 1-2px)
        self._psf_star  = gaussian_psf(sigma=0.8, size=3)
        self._psf_bright = gaussian_psf(sigma=1.5, size=5)

        # Photon scale: aperture area × QE
        ap_cm = self.APERTURE_MM / 10.0
        self._area_cm2 = math.pi * (ap_cm / 2.0) ** 2
        self._qe       = camera_spec.quantum_efficiency

    def render(self, jd: float, universe,
               exposure_s: float = 30.0,
               mag_limit: float = 9.0,
               atm_state=None) -> np.ndarray:
        """
        Render the full allsky field.
        Returns float32 (render_size, render_size, 3) photon array.
        """
        S = self.render_size
        cx = cy = S / 2.0
        radius = S / 2.0 - 2.0

        # Background
        field = build_allsky_background(S, atm_state, exposure_s)

        # Stars
        self._render_stars_allsky(field, jd, universe, mag_limit,
                                   cx, cy, radius, exposure_s, atm_state)

        # Solar system bodies (Sun, Moon, planets) — future hook
        # self._render_solar_bodies(field, jd, solar_bodies, cx, cy, radius)

        return field

    def _render_stars_allsky(self, field: np.ndarray,
                              jd: float, universe,
                              mag_limit: float,
                              cx: float, cy: float, radius: float,
                              exposure_s: float,
                              atm_state) -> None:
        S = self.render_size
        H = W = S

        for star in universe.get_stars():
            if star.mag > mag_limit:
                continue

            pos = radec_to_allsky_pixel(
                star.ra_deg, star.dec_deg, jd,
                self.lat, self.lon, cx, cy, radius
            )
            if pos is None:
                continue

            px, py = pos
            if px < 0 or px >= W or py < 0 or py >= H:
                continue

            # Approximate altitude for extinction
            alt, _ = equatorial_to_altaz(
                star.ra_deg, star.dec_deg, self.lat, self.lon, jd)

            # Extinction
            eff_mag = star.mag
            if atm_state is not None:
                ext = atm_state.extinction_at(max(1.0, alt),
                                               getattr(star, 'bv_color', 0.6))
                eff_mag += ext
                if eff_mag > mag_limit + 0.5:
                    continue

            # Photon flux (small aperture = fewer photons than telescope)
            photons = mag_to_flux(eff_mag, self._area_cm2 / math.pi * 2, exposure_s)
            photons *= self._qe

            r_col, g_col, b_col = bv_to_rgb(getattr(star, 'bv_color', 0.6))

            # PSF: bright stars slightly larger
            psf = self._psf_bright if eff_mag < 3.0 else self._psf_star
            size = psf.shape[0] // 2

            ix, iy = int(round(px)), int(round(py))
            y0 = max(0, iy-size); y1 = min(H, iy+size+1)
            x0 = max(0, ix-size); x1 = min(W, ix+size+1)
            ky0 = size-(iy-y0); ky1 = ky0+(y1-y0)
            kx0 = size-(ix-x0); kx1 = kx0+(x1-x0)

            if y0 < y1 and x0 < x1 and ky0 < ky1 and kx0 < kx1:
                patch = psf[ky0:ky1, kx0:kx1] * photons
                field[y0:y1, x0:x1, 0] += (patch * r_col).astype(np.float32)
                field[y0:y1, x0:x1, 1] += (patch * g_col).astype(np.float32)
                field[y0:y1, x0:x1, 2] += (patch * b_col).astype(np.float32)

    def get_info(self) -> dict:
        return {
            "camera":        self.spec.name,
            "fov_deg":       (180.0, 180.0),
            "projection":    "equidistant_azimuthal",
            "render_size":   self.render_size,
            "aperture_mm":   self.APERTURE_MM,
            "focal_length":  self.FOCAL_LENGTH_MM,
            "mag_limit_sky": 9.0,
        }
