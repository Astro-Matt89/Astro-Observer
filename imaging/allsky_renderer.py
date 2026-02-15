"""
AllSkyRenderer — Full-hemisphere fish-eye sky renderer.

Equidistant azimuthal projection:
    r = (90° - alt) / 90°  →  0 at zenith, 1 at horizon
Output: square (render_size × render_size) float32 RGB photon array.

Design philosophy for HD2D-realistic look:
  - Faint stars (mag > 3):  single pixel, no PSF spreading
  - Medium stars (mag 1–3): 3×3 gaussian core
  - Bright stars (mag < 1): 5×5 core + diffraction spike hints
  - Background: dark indigo with subtle spatial noise (not flat)
  - SKY_SCALE: reduces atmospheric bg relative to telescope cameras
"""

from __future__ import annotations
import math
import numpy as np
from typing import Optional, Tuple

from imaging.sky_renderer import mag_to_flux, bv_to_rgb
from universe.orbital_body import equatorial_to_altaz


# ── PSF factory ───────────────────────────────────────────────────────────────

def _make_psf(sigma: float, size: int) -> np.ndarray:
    """Normalised 2-D Gaussian (peak=1, sum normalised)."""
    k = np.arange(size) - size // 2
    g = np.exp(-0.5 * (k / sigma) ** 2)
    psf = np.outer(g, g)
    return (psf / psf.sum()).astype(np.float32)


# ── Projection ────────────────────────────────────────────────────────────────

def _radec_to_xy(ra_deg: float, dec_deg: float,
                 jd: float, lat: float, lon: float,
                 cx: float, cy: float, radius: float
                 ) -> Optional[Tuple[float, float, float]]:
    """RA/Dec → (px, py, alt).  Returns None if below horizon."""
    alt, az = equatorial_to_altaz(ra_deg, dec_deg, lat, lon, jd)
    if alt < 0.5:          # clip a bit above horizon (refraction, trees)
        return None
    r_px = (90.0 - alt) / 90.0 * radius
    az_r  = math.radians(az)
    return cx + r_px * math.sin(az_r), cy - r_px * math.cos(az_r), alt


# ── Background ────────────────────────────────────────────────────────────────

def build_allsky_background(size: int,
                             atm_state,
                             exposure_s: float = 1.0) -> np.ndarray:
    """
    Build (size, size, 3) float32 background.

    Features:
    - Deep indigo at night, desaturated blue toward horizon
    - Subtle Perlin-like spatial noise so sky is NOT flat
    - Solar horizon glow during twilight
    - Airglow band at ~10° altitude (dark nights)
    """
    H = W = size
    cx = cy = size * 0.5
    radius = size * 0.5 - 1.5

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx;  dy = yy - cy
    r_px   = np.sqrt(dx*dx + dy*dy)
    r_norm = np.clip(r_px / radius, 0.0, 1.0)
    inside = (r_px <= radius).astype(np.float32)

    # Sky background scale: allsky lens is much smaller than a telescope.
    # Scale down atmospheric bg so stars dominate over sky noise.
    _SKY_SCALE = 0.07

    if atm_state is not None:
        bg_r = atm_state.sky_bg_r * exposure_s * _SKY_SCALE
        bg_g = atm_state.sky_bg_g * exposure_s * _SKY_SCALE
        bg_b = atm_state.sky_bg_b * exposure_s * _SKY_SCALE
        solar_alt  = atm_state.solar_alt_deg
        solar_az_r = math.radians(getattr(atm_state, 'solar_az_deg', 180.0))
    else:
        bg_r = 0.10 * exposure_s
        bg_g = 0.20 * exposure_s
        bg_b = 0.60 * exposure_s
        solar_alt  = -30.0
        solar_az_r = math.pi

    # ── Altitude gradient (airmass) ───────────────────────────────────
    horizon_boost = 1.20 if solar_alt < -12.0 else (1.5 if solar_alt < -6.0 else 2.0)
    alt_gradient  = 1.0 + r_norm * (horizon_boost - 1.0)

    # ── Spatial noise — large-scale transparency variation ────────────
    # 3 octaves of sine waves → organic blotches (10-100px scale)
    # This mimics real sky: patches of slightly different brightness
    # Scale relative to blue channel so night noise is subtle
    noise_scale = 0.025 * bg_b   # 2.5% of blue channel
    nx  = np.sin(xx * 0.012 + 1.3) * np.cos(yy * 0.015 + 0.7)
    nx += 0.4 * np.sin(xx * 0.031 - 2.1) * np.cos(yy * 0.027 + 1.8)
    nx += 0.2 * np.sin(xx * 0.058 + 0.4) * np.cos(yy * 0.063 - 1.2)
    nx  = nx / (nx.std() + 1e-9) * 0.5
    sky_noise = nx * noise_scale

    # ── Solar horizon glow (twilight) ─────────────────────────────────
    az_map      = np.arctan2(dx, -dy)
    angle_sun   = (az_map - solar_az_r + math.pi) % (2*math.pi) - math.pi
    if solar_alt > -18.0:
        glow_str    = max(0.0, (solar_alt + 18.0) / 18.0) ** 1.5
        sun_glow    = np.exp(-angle_sun**2 / 0.5) * np.clip((r_norm-0.4)/0.6, 0, 1)**1.2 * glow_str
    else:
        sun_glow    = np.zeros((H, W), np.float32)

    # ── Airglow ring at ~10° altitude (dark nights only) ──────────────
    if solar_alt < -18.0:
        airglow = np.exp(-((r_norm - 0.89) / 0.06) ** 2) * 0.4
    else:
        airglow = np.zeros((H, W), np.float32)

    # ── Compose ───────────────────────────────────────────────────────
    # Night sky colour: blue dominates but with grey-blue cast.
    # Real allsky cameras (monochrome + rgb) show blue-grey, not pure navy.
    # Boosting R and G slightly toward blue gives the correct tone.
    R = (bg_r * alt_gradient + bg_r * sun_glow * 0.8 + sky_noise * 0.4) * inside
    G = (bg_g * alt_gradient + bg_g * sun_glow * 0.3 + sky_noise * 0.6
         + airglow * bg_g * 0.3) * inside
    B = (bg_b * alt_gradient + sun_glow * bg_b * 0.05 + sky_noise
         + airglow * bg_b * 0.15) * inside

    return np.stack([np.clip(R,0,None), np.clip(G,0,None), np.clip(B,0,None)],
                    axis=-1).astype(np.float32)


# ── Main renderer ─────────────────────────────────────────────────────────────

class AllSkyRenderer:
    """
    Full visible-sky hemisphere rendered on a circular fish-eye disk.

    Star rendering strategy:
      mag < 0   : 5×5 PSF (bright star with minor halo)
      0 ≤ mag < 3 : 3×3 PSF (medium star, just a touch larger than 1px)  
      mag ≥ 3   : SINGLE PIXEL — no spreading at all

    This ensures that at render_size=512, with ~2× upscale to display,
    faint stars appear as 1-2px points instead of blobs.
    """

    FOCAL_LENGTH_MM = 3.0
    APERTURE_MM     = 25.0

    def __init__(self, camera_spec,
                 observer_lat: float = 45.0,
                 observer_lon: float = 9.0,
                 render_size:  int   = 512):
        self.spec        = camera_spec
        self.lat         = observer_lat
        self.lon         = observer_lon
        self.render_size = render_size

        # PSF for bright and medium stars only
        self._psf3 = _make_psf(0.55, 3)   # 3×3 for mag 0–3
        self._psf5 = _make_psf(0.70, 5)   # 5×5 for mag < 0

        ap_cm          = self.APERTURE_MM / 10.0
        self._area_cm2 = math.pi * (ap_cm / 2.0) ** 2
        self._qe       = camera_spec.quantum_efficiency

    def render(self, jd: float, universe,
               exposure_s: float = 1.0,
               mag_limit:  float = 5.0,
               atm_state         = None) -> np.ndarray:
        S  = self.render_size
        cx = cy = S / 2.0
        radius  = S / 2.0 - 1.5

        field = build_allsky_background(S, atm_state, exposure_s)
        self._render_stars(field, jd, universe, mag_limit,
                           cx, cy, radius, exposure_s, atm_state)
        return field

    def _render_stars(self, field: np.ndarray,
                      jd: float, universe,
                      mag_limit: float,
                      cx: float, cy: float, radius: float,
                      exposure_s: float, atm_state) -> None:
        H = W = self.render_size

        for star in universe.get_stars():
            if star.mag > mag_limit:
                continue

            pos = _radec_to_xy(star.ra_deg, star.dec_deg, jd,
                               self.lat, self.lon, cx, cy, radius)
            if pos is None:
                continue

            px, py, alt = pos
            if not (0.5 <= px < W-0.5 and 0.5 <= py < H-0.5):
                continue

            # Extinction
            eff_mag = star.mag
            if atm_state is not None:
                ext = atm_state.extinction_at(max(2.0, alt),
                                               getattr(star, 'bv_color', 0.6))
                eff_mag += ext
                if eff_mag > mag_limit + 0.3:
                    continue

            # Photon flux
            photons = (mag_to_flux(eff_mag, self._area_cm2 / math.pi * 2, exposure_s)
                       * self._qe)
            if photons < 0.3:
                continue

            # Star colour (already desaturated in bv_to_rgb)
            bv  = getattr(star, 'bv_color', 0.6)
            rc, gc, bc = bv_to_rgb(bv)

            ix = int(round(px)); iy = int(round(py))

            if eff_mag < 0.0:
                # Very bright: 5×5 PSF
                psf  = self._psf5; half = 2
                y0 = max(0,iy-half); y1 = min(H,iy+half+1)
                x0 = max(0,ix-half); x1 = min(W,ix+half+1)
                ky0 = half-(iy-y0); ky1 = ky0+(y1-y0)
                kx0 = half-(ix-x0); kx1 = kx0+(x1-x0)
                if y0<y1 and x0<x1 and ky0<ky1 and kx0<kx1:
                    patch = psf[ky0:ky1, kx0:kx1] * photons
                    field[y0:y1,x0:x1,0] += patch * rc
                    field[y0:y1,x0:x1,1] += patch * gc
                    field[y0:y1,x0:x1,2] += patch * bc

            elif eff_mag < 3.0:
                # Medium bright: 3×3 PSF
                psf  = self._psf3; half = 1
                y0 = max(0,iy-1); y1 = min(H,iy+2)
                x0 = max(0,ix-1); x1 = min(W,ix+2)
                ky0 = 1-(iy-y0); ky1 = ky0+(y1-y0)
                kx0 = 1-(ix-x0); kx1 = kx0+(x1-x0)
                if y0<y1 and x0<x1 and ky0<ky1 and kx0<kx1:
                    patch = psf[ky0:ky1, kx0:kx1] * photons
                    field[y0:y1,x0:x1,0] += patch * rc
                    field[y0:y1,x0:x1,1] += patch * gc
                    field[y0:y1,x0:x1,2] += patch * bc

            else:
                # Faint star: SINGLE PIXEL — no spreading whatsoever
                if 0 <= iy < H and 0 <= ix < W:
                    field[iy, ix, 0] += photons * rc
                    field[iy, ix, 1] += photons * gc
                    field[iy, ix, 2] += photons * bc

    def get_info(self) -> dict:
        return {
            "camera":       self.spec.name,
            "fov_deg":      (180.0, 180.0),
            "projection":   "equidistant_azimuthal",
            "render_size":  self.render_size,
            "aperture_mm":  self.APERTURE_MM,
            "focal_length": self.FOCAL_LENGTH_MM,
            "mag_limit":    5.0,
        }
