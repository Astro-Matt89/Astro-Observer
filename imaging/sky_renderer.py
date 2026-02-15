"""
Photorealistic Sky Renderer for Astronomical Imaging

Renders realistic telescope images using:
- Real star catalog (Yale BSC + Hipparcos + Gaia = 389k stars)
- Real DSO catalog (Messier + NGC)
- Physical PSF (Point Spread Function) based on telescope optics
- Atmospheric seeing simulation
- Correct star colors from B-V index
- DSO morphology (galaxies, nebulae, clusters)

The output is a photon flux map (photons/pixel) that is then
fed into the Camera simulation for realistic noise.
"""

from __future__ import annotations
import math
import numpy as np
from typing import Optional, Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:
    from universe.space_object import SpaceObject


# ─────────────────────────────────────────────────────────────────────────────
# Physical constants
# ─────────────────────────────────────────────────────────────────────────────

# Calibrated photon count for a mag=0 star on a 102mm aperture, 1s, broadband (~V)
# Real value: ~3.6e6 ph/s/m2, normalized so that on 102mm/30s mag6 star = ~500 photons
# We use a relative scale tuned to fill the camera's dynamic range comfortably.
# mag=0  → ~280,000 photons/s on 102mm (calibrated empirically)
# mag=6  → ~280,000 / 250 ≈ 1,100 ph/s → ×30s = 33,000 ph → near but below full well
# mag=12 → ~280,000 / 63,000 ≈ 4 ph/s → ×30s = 130 ph → above sky background

# ── Physical photon calibration ──────────────────────────────────────────────
#
# V-band (550nm) photon flux for a mag=0 star above atmosphere:
#   F0 ≈ 3.63×10^6 photons/s/m²  (Bessell 2005)
#
# For telescope imaging we want photons at the sensor.
# mag_to_flux computes:  F0 × 10^(-0.4×mag) × area_m² × exposure_s
# This gives total photons caught by the aperture for a POINT SOURCE.
# The PSF then distributes them across pixels.
#
# Sky background uses the same formula but multiplied by pixel_scale²
# because sky brightness is in mag/arcsec², so we integrate over pixel area.
#
# Reference checks (102mm, 30s, QE=0.8, gain=0.5e/ADU, FW=63000e):
#   mag 3  → 63,000 ph → 50,400e → 100,800 ADU → ~80% FW  ✓
#   mag 6  → 3,977 ph  → 3,182e  →  6,364 ADU  →  5% FW   ✓
#   mag 10 → 100 ph    → 80e     →  160 ADU              ✓
#   sky 20.5 mag/arcsec² × 28 arcsec²/px × 30s → ~220 ph/px → 354 ADU ✓

# ── Photon calibration ───────────────────────────────────────────────────────
#
# V-band flux for mag=0 star: ~1000 ph/s/cm² (standard simplified calibration).
# This gives a physically reasonable dynamic range:
#   mag 4  → 78% full-well on ZWO ASI294MC in 30s on 102mm   (bright, OK)
#   mag 6  → 12% FW                                           (well exposed)
#   mag 10 → 0.3% FW  (faint but detectable above sky noise)
#   mag 0-3 → saturate (bloom expected — physically correct)
#
# Sky background is boosted by SKY_DISPLAY_BOOST so the pedestal is visible
# at the large pixel scales used by the render buffer.  This does not affect
# star photometry — only the extended background brightness.

VEGA_FLUX_V       = 1_000.0   # ph/s/cm² for V=0 star (broadband V-filter)
SKY_DISPLAY_BOOST =    60.0   # visual boost for sky pedestal at large pixel scales


def mag_to_flux(mag: float, aperture_cm: float, exposure_s: float,
                bandwidth_ang: float = 500.0) -> float:
    """Total photons from a point source collected by the aperture."""
    area_cm2 = math.pi * (aperture_cm / 2.0) ** 2
    return max(0.0, VEGA_FLUX_V * (10.0 ** (-0.4 * mag)) * area_cm2 * exposure_s)


def sky_photons_per_pixel(sky_mag_arcsec2: float, aperture_cm: float,
                           pixel_scale_arcsec: float, exposure_s: float) -> float:
    """
    Photons per render-pixel from sky background.
    Includes SKY_DISPLAY_BOOST to compensate for large pixel scales.
    """
    area_cm2  = math.pi * (aperture_cm / 2.0) ** 2
    px_area   = pixel_scale_arcsec ** 2
    phys = VEGA_FLUX_V * (10.0 ** (-0.4 * sky_mag_arcsec2)) * area_cm2 * px_area * exposure_s
    return max(0.0, phys * SKY_DISPLAY_BOOST)


def bv_to_rgb(bv: float, desaturate: float = 0.55) -> Tuple[float, float, float]:
    """
    Convert B-V color index to (R, G, B) multipliers.

    desaturate: blend toward white (1.0) by this fraction.
    Photographic allsky images show subtle, muted star colours —
    not saturated LEDs. desaturate=0.55 gives realistic tones:
    O/B stars: pale ice-blue, G stars: warm cream, M stars: brick-red.

    B-V < 0.0  → ice-blue (O/B)
    B-V = 0.0  → pure white (A stars, Vega)
    B-V = 0.6  → warm white/cream (G, Sun)
    B-V = 1.5  → dusty orange (K/M)
    """
    bv = max(-0.4, min(2.0, bv))

    if bv < 0.0:       # O/B: blue-white
        t = (bv + 0.4) / 0.4
        r = 0.6 + 0.2 * t
        g = 0.7 + 0.3 * t
        b = 1.0
    elif bv < 0.3:     # A/F: white
        t = bv / 0.3
        r = 0.8 + 0.2 * t
        g = 0.9 + 0.1 * t
        b = 1.0 - 0.2 * t
    elif bv < 0.7:     # G: warm white
        t = (bv - 0.3) / 0.4
        r = 1.0
        g = 0.9
        b = 0.8 - 0.4 * t
    elif bv < 1.2:     # K: pale orange
        t = (bv - 0.7) / 0.5
        r = 1.0
        g = 0.9 - 0.4 * t
        b = 0.4 - 0.3 * t
    else:              # M: dusty red
        t = min(1.0, (bv - 1.2) / 0.8)
        r = 1.0
        g = 0.5 - 0.3 * t
        b = 0.1

    # Desaturate toward white — photographic stars are never saturated LEDs
    r = r + (1.0 - r) * desaturate
    g = g + (1.0 - g) * desaturate
    b = b + (1.0 - b) * desaturate

    return (r, g, b)


# ─────────────────────────────────────────────────────────────────────────────
# PSF (Point Spread Function)
# ─────────────────────────────────────────────────────────────────────────────

def gaussian_psf(size: int, sigma: float) -> np.ndarray:
    """
    Gaussian PSF kernel for star rendering.
    
    Args:
        size: Half-size of kernel (full size = 2*size+1)
        sigma: PSF sigma in pixels
    
    Returns:
        Normalized 2D gaussian array
    """
    y, x = np.ogrid[-size:size+1, -size:size+1]
    g = np.exp(-(x*x + y*y) / (2.0 * sigma * sigma))
    return (g / g.sum()).astype(np.float32)


def airy_psf(size: int, lambda_um: float, aperture_mm: float,
             focal_length_mm: float, pixel_um: float) -> np.ndarray:
    """
    Airy disk PSF for diffraction-limited telescopes.
    More realistic than pure gaussian for larger apertures.
    
    Args:
        size: Half-size of kernel
        lambda_um: Wavelength in microns (0.55 for V-band)
        aperture_mm: Telescope aperture in mm
        focal_length_mm: Focal length in mm
        pixel_um: Pixel size in microns
    
    Returns:
        Normalized 2D Airy pattern
    """
    from scipy.special import j1
    
    # Airy radius in pixels = 1.22 * lambda * f/D / pixel_size
    f_ratio = focal_length_mm / aperture_mm
    airy_radius_um = 1.22 * lambda_um * f_ratio
    airy_radius_px = airy_radius_um / pixel_um
    
    y, x = np.ogrid[-size:size+1, -size:size+1]
    r = np.sqrt(x*x + y*y)
    
    # Avoid division by zero at center
    with np.errstate(divide='ignore', invalid='ignore'):
        u = np.pi * r / airy_radius_px
        pattern = np.where(r == 0, 1.0, (2 * j1(u) / u) ** 2)
    
    return (pattern / pattern.sum()).astype(np.float32)


def seeing_psf(base_sigma: float, seeing_arcsec: float,
               pixel_scale_arcsec: float) -> float:
    """
    Compute effective PSF sigma including atmospheric seeing.
    
    Args:
        base_sigma: Diffraction-limited sigma in pixels
        seeing_arcsec: Atmospheric seeing FWHM in arcseconds
        pixel_scale_arcsec: Arcseconds per pixel
    
    Returns:
        Effective sigma in pixels
    """
    seeing_fwhm_px = seeing_arcsec / pixel_scale_arcsec
    seeing_sigma_px = seeing_fwhm_px / 2.355  # FWHM to sigma
    
    # Quadrature sum (both are gaussian approximations)
    effective_sigma = math.sqrt(base_sigma**2 + seeing_sigma_px**2)
    return effective_sigma


# ─────────────────────────────────────────────────────────────────────────────
# DSO Renderers
# ─────────────────────────────────────────────────────────────────────────────

def render_galaxy(field: np.ndarray, cx: float, cy: float,
                  total_photons: float, size_px: float,
                  bv: float = 0.8) -> None:
    """
    Render a galaxy as a Sérsic profile (n=4 for ellipticals, n=1 for spirals).
    
    Args:
        field: Output array (H, W)
        cx, cy: Center in pixels
        total_photons: Total photon flux
        size_px: Effective radius in pixels
        bv: B-V color (affects profile slightly)
    """
    H, W = field.shape
    r_e = max(2.0, size_px * 0.5)   # Effective radius
    
    # Sérsic index: 4 for elliptical, 1 for spiral
    n = 4.0 if bv > 0.7 else 1.0
    b_n = 1.9992 * n - 0.3271       # Approximation for b_n
    
    # Bounding box
    extent = int(min(r_e * 5, min(H, W) / 2))
    x0, x1 = max(0, int(cx) - extent), min(W, int(cx) + extent + 1)
    y0, y1 = max(0, int(cy) - extent), min(H, int(cy) + extent + 1)
    
    if x0 >= x1 or y0 >= y1:
        return
    
    yy, xx = np.ogrid[y0:y1, x0:x1]
    
    # Elliptical distance (slight elongation for realism)
    dx = (xx - cx)
    dy = (yy - cy) * 1.4  # Slight elongation
    r = np.sqrt(dx*dx + dy*dy)
    
    # Sérsic profile
    profile = np.exp(-b_n * ((r / r_e) ** (1.0 / n) - 1.0))
    profile_sum = profile.sum()
    
    if profile_sum > 0:
        field[y0:y1, x0:x1] += (profile / profile_sum * total_photons).astype(np.float32)


def render_nebula(field: np.ndarray, cx: float, cy: float,
                  total_photons: float, size_px: float,
                  nebula_type: str = "emission") -> None:
    """
    Render a nebula with appropriate morphology.
    
    Types:
        emission: HII region — irregular, bright core, filaments
        planetary: small, ring-like
        reflection: diffuse, gaussian-ish
        snr: ring/shell structure
    """
    H, W = field.shape
    extent = int(min(size_px * 2.5, min(H, W) / 2))
    x0, x1 = max(0, int(cx) - extent), min(W, int(cx) + extent + 1)
    y0, y1 = max(0, int(cy) - extent), min(H, int(cy) + extent + 1)
    
    if x0 >= x1 or y0 >= y1:
        return
    
    yy, xx = np.ogrid[y0:y1, x0:x1]
    dx = xx - cx
    dy = yy - cy
    r = np.sqrt(dx*dx + dy*dy)
    
    if nebula_type == "planetary":
        # Ring profile
        r0 = size_px * 0.6
        ring_width = max(1.0, size_px * 0.15)
        profile = np.exp(-((r - r0) / ring_width) ** 2)
        # Slight central brightening
        profile += 0.3 * np.exp(-(r / (size_px * 0.2)) ** 2)
        
    elif nebula_type == "snr":
        # Thin shell
        r0 = size_px * 0.85
        shell_width = max(0.5, size_px * 0.08)
        profile = np.exp(-((r - r0) / shell_width) ** 2)
        
    elif nebula_type == "emission":
        # Irregular with filaments — use gaussian + noise seed
        rng = np.random.default_rng(int(cx * 1000 + cy))
        profile = np.exp(-(r / size_px) ** 1.2)
        # Add turbulence
        noise = rng.standard_normal(profile.shape) * 0.3 + 1.0
        noise = np.clip(noise, 0.1, 3.0)
        profile = profile * noise
        
    else:  # reflection, generic
        profile = np.exp(-(r / (size_px * 0.8)) ** 1.8)
    
    profile_sum = profile.sum()
    if profile_sum > 0:
        field[y0:y1, x0:x1] += (profile / profile_sum * total_photons).astype(np.float32)


def render_cluster(field: np.ndarray, cx: float, cy: float,
                   total_photons: float, size_px: float,
                   is_globular: bool = False) -> None:
    """Render a star cluster."""
    H, W = field.shape
    rng = np.random.default_rng(int(cx * 1000 + cy))
    
    if is_globular:
        # Globular: concentrated King profile
        n_stars = 300
        sigma = size_px * 0.3
        radii = rng.exponential(sigma, n_stars)
        angles = rng.uniform(0, 2*math.pi, n_stars)
        # Core concentration
        radii = radii * (1 - 0.7 * np.exp(-radii / (size_px * 0.1)))
    else:
        # Open: sparse, irregular
        n_stars = 80
        sigma = size_px * 0.5
        radii = np.abs(rng.normal(0, sigma, n_stars))
        angles = rng.uniform(0, 2*math.pi, n_stars)
    
    xs = cx + radii * np.cos(angles)
    ys = cy + radii * np.sin(angles)
    brightnesses = rng.pareto(2.0, n_stars) + 1.0
    brightnesses = (brightnesses / brightnesses.sum()) * total_photons
    
    sigma_psf = 1.2
    size_k = 4
    kernel = gaussian_psf(size_k, sigma_psf)
    
    for x, y, b in zip(xs, ys, brightnesses):
        ix, iy = int(round(x)), int(round(y))
        y0 = max(0, iy - size_k)
        y1 = min(H, iy + size_k + 1)
        x0 = max(0, ix - size_k)
        x1 = min(W, ix + size_k + 1)
        ky0 = size_k - (iy - y0)
        ky1 = ky0 + (y1 - y0)
        kx0 = size_k - (ix - x0)
        kx1 = kx0 + (x1 - x0)
        if y0 < y1 and x0 < x1:
            field[y0:y1, x0:x1] += (kernel[ky0:ky1, kx0:kx1] * b).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Main Renderer
# ─────────────────────────────────────────────────────────────────────────────

class SkyRenderer:
    """
    Photorealistic sky renderer for telescope imaging.
    
    Uses real catalog data to generate scientifically accurate
    photon flux maps for the camera simulation.
    
    render_w / render_h define the internal render buffer size.
    Keep small (e.g. 480×270) for performance — the DisplayPipeline
    handles upscaling to display resolution with nearest-neighbour.
    """
    
    def __init__(self,
                 aperture_mm: float = 102.0,
                 focal_length_mm: float = 714.0,
                 pixel_size_um: float = 3.76,
                 sensor_w: int = 1920,
                 sensor_h: int = 1080,
                 render_w: int = 480,
                 render_h: int = 270,
                 seeing_arcsec: float = 2.5,
                 sky_background_mag: float = 20.0):
        """
        Args:
            aperture_mm: Telescope aperture
            focal_length_mm: Focal length
            pixel_size_um: Camera pixel size in microns
            sensor_w/h: Physical sensor dimensions (for scientific accuracy)
            render_w/h: Render buffer dimensions (smaller = faster, pixel-art look)
            seeing_arcsec: Atmospheric seeing FWHM
            sky_background_mag: Sky background magnitude/arcsec²
        """
        self.aperture_mm = aperture_mm
        self.aperture_cm = aperture_mm / 10.0
        self.focal_length_mm = focal_length_mm
        self.pixel_size_um = pixel_size_um
        self.sensor_w = sensor_w
        self.sensor_h = sensor_h
        self.render_w = render_w
        self.render_h = render_h
        self.seeing_arcsec = seeing_arcsec
        self.sky_background_mag = sky_background_mag
        
        # Effective pixel size in the render buffer
        # Each render pixel covers (sensor_w / render_w) sensor pixels
        self._bin_x = sensor_w / render_w
        self._bin_y = sensor_h / render_h
        effective_pixel_um = pixel_size_um * self._bin_x
        
        # Pixel scale of the render buffer (arcsec/pixel)
        self.pixel_scale = (effective_pixel_um / 1000.0) / focal_length_mm * 206265.0
        
        # FOV in degrees (same physical FOV regardless of render resolution)
        self.fov_w = (pixel_size_um / 1000.0) / focal_length_mm * 206265.0 * sensor_w / 3600.0
        self.fov_h = (pixel_size_um / 1000.0) / focal_length_mm * 206265.0 * sensor_h / 3600.0
        
        # Diffraction limit + seeing → effective PSF sigma in render pixels
        diff_limit_arcsec = 1.22 * 0.00055 / aperture_mm * 206265.0
        diff_limit_sigma_px = (diff_limit_arcsec / 2.355) / self.pixel_scale
        seeing_sigma_px = (seeing_arcsec / 2.355) / self.pixel_scale
        self.psf_sigma = math.sqrt(diff_limit_sigma_px**2 + seeing_sigma_px**2)
        # Enforce minimum 1.2px so stars are never 1-pixel dots.
        # At coarse render scales (4.3 arcsec/px) seeing is undersampled —
        # we boost PSF to ensure visible, round star images.
        min_sigma = max(1.2, seeing_arcsec / self.pixel_scale / 2.355)
        self.psf_sigma = max(min_sigma, self.psf_sigma)
        
        # PSF kernel cache
        self._psf_cache = {}
    
    def _get_psf(self, mag: float) -> Tuple[np.ndarray, int]:
        """
        PSF kernel for a star of given magnitude.

        Bright stars use larger sigma to simulate saturation bloom and the
        fact that their core contribution spreads beyond the Airy disk.
        This prevents single-pixel white dots for bright objects.
        """
        s = self.psf_sigma
        if   mag < 0:   sigma, size = s * 4.0, 14
        elif mag < 2:   sigma, size = s * 2.8, 10
        elif mag < 4:   sigma, size = s * 1.9,  8
        elif mag < 6:   sigma, size = s * 1.3,  6
        elif mag < 8:   sigma, size = s * 1.0,  4
        elif mag < 10:  sigma, size = s * 0.9,  3
        else:           sigma, size = s * 0.8,  2

        key = round(sigma, 2)
        if key not in self._psf_cache:
            self._psf_cache[key] = (gaussian_psf(size, sigma), size)
        return self._psf_cache[key]
    
    def render_field(self,
                     target_ra: float,
                     target_dec: float,
                     exposure_s: float,
                     universe,
                     mag_limit: float = 14.0,
                     atm_state=None) -> np.ndarray:
        """
        Render a complete telescope field of view.
        atm_state: AtmosphericState (optional) — if provided, uses physical
                   sky background and applies per-star extinction.
        Output shape is (render_h, render_w) — the small buffer.
        """
        W, H = self.render_w, self.render_h
        field = np.zeros((H, W), dtype=np.float32)

        if atm_state is not None:
            bg = atm_state.sky_background_field(H, W, exposure_s)
            # Mono: use luminance of RGB background
            field += (bg[:,:,0]*0.299 + bg[:,:,1]*0.587 + bg[:,:,2]*0.114)
        else:
            field += self._render_sky_background(W, H, exposure_s)

        self._render_dso(field, target_ra, target_dec, exposure_s, universe)
        self._render_stars(field, target_ra, target_dec, exposure_s, universe,
                           mag_limit, atm_state=atm_state)
        return field
    
    def _render_sky_background(self, W: int, H: int, exposure_s: float) -> np.ndarray:
        """
        Sky glow: uniform pedestal + Milky Way gradient + vignette.
        sky_photons_per_pixel() already includes the display boost.
        """
        sky_ph = sky_photons_per_pixel(
            self.sky_background_mag, self.aperture_cm,
            self.pixel_scale, exposure_s)

        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

        # Milky Way gradient — slow diagonal variation
        angle = 0.7
        grad = (xx * math.cos(angle) + yy * math.sin(angle)) / (W + H)
        grad = (grad - grad.min()) / (grad.max() - grad.min() + 1e-9)

        bg = (sky_ph * (1.0 + grad * 0.5)).astype(np.float32)

        # Vignette
        cx, cy = W / 2.0, H / 2.0
        r = np.sqrt(((xx - cx) / cx)**2 + ((yy - cy) / cy)**2)
        bg *= (1.0 - 0.30 * np.clip(r, 0, 1) ** 2.5)

        return bg.astype(np.float32)
    
    def _radec_to_pixel(self, ra: float, dec: float,
                         center_ra: float, center_dec: float) -> Optional[Tuple[float, float]]:
        """
        Convert RA/Dec to pixel coordinates.
        Uses gnomonic (tangent plane) projection for small FOVs.
        
        Returns:
            (px, py) or None if outside field
        """
        # Convert to radians
        ra_r = math.radians(ra)
        dec_r = math.radians(dec)
        ra0 = math.radians(center_ra)
        dec0 = math.radians(center_dec)
        
        # Gnomonic projection
        cos_c = (math.sin(dec0) * math.sin(dec_r) +
                 math.cos(dec0) * math.cos(dec_r) * math.cos(ra_r - ra0))
        
        if cos_c <= 0:
            return None  # Behind the projection plane
        
        x = (math.cos(dec_r) * math.sin(ra_r - ra0)) / cos_c
        y = ((math.cos(dec0) * math.sin(dec_r) -
              math.sin(dec0) * math.cos(dec_r) * math.cos(ra_r - ra0)) / cos_c)
        
        # Convert radians to pixels in the render buffer
        # 1 radian = 206265 arcsec, pixel_scale arcsec/render_pixel
        scale = 206265.0 / self.pixel_scale  # render_pixels per radian
        
        px = self.render_w / 2.0 - x * scale   # RA increases right→left
        py = self.render_h / 2.0 - y * scale   # Dec increases bottom→top
        
        return (px, py)
    
    def _render_stars(self, field: np.ndarray,
                       center_ra: float, center_dec: float,
                       exposure_s: float, universe,
                       mag_limit: float,
                       atm_state=None) -> int:
        """Render stars from catalog onto field, with optional atmospheric extinction."""
        H, W = field.shape

        ra_margin    = self.fov_w * 0.75
        dec_margin   = self.fov_h * 0.75
        dec_min      = center_dec - dec_margin
        dec_max      = center_dec + dec_margin
        ra_margin_adj = ra_margin / max(0.01, math.cos(math.radians(center_dec)))

        n_rendered = 0

        for star in universe.get_stars():
            if star.mag > mag_limit:
                continue
            if star.dec_deg < dec_min or star.dec_deg > dec_max:
                continue
            dra = abs(star.ra_deg - center_ra)
            if dra > 180: dra = 360 - dra
            if dra > ra_margin_adj:
                continue

            pos = self._radec_to_pixel(star.ra_deg, star.dec_deg, center_ra, center_dec)
            if pos is None:
                continue
            px, py = pos
            if px < -20 or px > W + 20 or py < -20 or py > H + 20:
                continue

            # Apparent magnitude after atmospheric extinction
            eff_mag = star.mag
            if atm_state is not None:
                # Convert pixel position to approximate altitude
                # (centre of field = target altitude; edges ±FOV/2)
                # Simple approximation: use target altitude for all stars in field
                ext = atm_state.extinction_at(
                    self._target_alt if hasattr(self, '_target_alt') else 45.0,
                    getattr(star, 'bv_color', 0.6)
                )
                eff_mag += ext
                if eff_mag > mag_limit + 1.0:
                    continue   # extincted below limit

            photons = mag_to_flux(eff_mag, self.aperture_cm, exposure_s)
            psf, size = self._get_psf(eff_mag)

            ix, iy = int(round(px)), int(round(py))
            y0 = max(0, iy - size);  y1 = min(H, iy + size + 1)
            x0 = max(0, ix - size);  x1 = min(W, ix + size + 1)
            ky0 = size - (iy - y0);  ky1 = ky0 + (y1 - y0)
            kx0 = size - (ix - x0);  kx1 = kx0 + (x1 - x0)

            if y0 < y1 and x0 < x1 and ky0 < ky1 and kx0 < kx1:
                field[y0:y1, x0:x1] += (psf[ky0:ky1, kx0:kx1] * photons).astype(np.float32)
                n_rendered += 1

        return n_rendered
    
    def _render_dso(self, field: np.ndarray,
                     center_ra: float, center_dec: float,
                     exposure_s: float, universe) -> int:
        """Render deep-sky objects."""
        H, W = field.shape
        
        ra_margin = self.fov_w * 0.75
        dec_margin = self.fov_h * 0.7
        
        n_rendered = 0
        
        for obj in universe.get_dso():
            if obj.mag > 14.0:
                continue
            
            # Bounding box
            if abs(obj.dec_deg - center_dec) > dec_margin:
                continue
            dra = abs(obj.ra_deg - center_ra)
            if dra > 180: dra = 360 - dra
            if dra > ra_margin / max(0.01, math.cos(math.radians(center_dec))):
                continue
            
            pos = self._radec_to_pixel(obj.ra_deg, obj.dec_deg, center_ra, center_dec)
            if pos is None:
                continue
            
            px, py = pos
            if px < -100 or px > W + 100 or py < -100 or py > H + 100:
                continue
            
            # Total photons
            photons = mag_to_flux(obj.mag, self.aperture_cm, exposure_s) * 0.3
            
            # Size in pixels
            size_arcsec = obj.size_arcmin * 60.0
            size_px = size_arcsec / self.pixel_scale
            size_px = max(3.0, min(size_px, min(W, H) * 0.4))
            
            # Render by type
            from universe.space_object import ObjectClass, ObjectSubtype
            
            if obj.obj_class == ObjectClass.GALAXY:
                bv = obj.meta.get("bv_color", obj.bv_color)
                render_galaxy(field, px, py, photons, size_px, bv)
                
            elif obj.obj_class == ObjectClass.NEBULA:
                subtype = getattr(obj, 'subtype', None)
                if subtype and hasattr(subtype, 'value'):
                    ntype = subtype.value
                else:
                    ntype = "emission"
                
                if "planetary" in str(ntype).lower():
                    render_nebula(field, px, py, photons, size_px, "planetary")
                elif "snr" in str(ntype).lower() or "supernova" in str(ntype).lower():
                    render_nebula(field, px, py, photons, size_px, "snr")
                else:
                    render_nebula(field, px, py, photons, size_px, "emission")
                
            elif obj.obj_class == ObjectClass.CLUSTER:
                subtype = getattr(obj, 'subtype', None)
                is_glob = subtype and "globular" in str(subtype).lower()
                render_cluster(field, px, py, photons, size_px, is_glob)
            
            n_rendered += 1
        
        return n_rendered
    
    def render_rgb(self, field_r: np.ndarray, field_g: np.ndarray,
                   field_b: np.ndarray,
                   target_ra: float, target_dec: float,
                   exposure_s: float, universe,
                   mag_limit: float = 14.0,
                   atm_state=None) -> None:
        """
        Render R/G/B channel fields (render_h × render_w each).
        atm_state: AtmosphericState — if provided, uses physical sky background
                   (Rayleigh scattering + airglow + moon glow) and per-star extinction.
        """
        W, H = self.render_w, self.render_h

        # ── Sky background ────────────────────────────────────────────────
        if atm_state is not None:
            bg = atm_state.sky_background_field(H, W, exposure_s)
            field_r += bg[:, :, 0]
            field_g += bg[:, :, 1]
            field_b += bg[:, :, 2]
        else:
            # Legacy: uniform mono background with slight blue tint
            sky_ph = sky_photons_per_pixel(
                self.sky_background_mag, self.aperture_cm, self.pixel_scale, exposure_s)
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            grad = (xx * math.cos(0.7) + yy * math.sin(0.7)) / (W + H)
            grad = (grad - grad.min()) / (grad.max() - grad.min() + 1e-9)
            sky_map = (sky_ph * (1.0 + grad * 0.4)).astype(np.float32)
            cx, cy = W/2.0, H/2.0
            r2 = np.sqrt(((xx-cx)/cx)**2 + ((yy-cy)/cy)**2)
            sky_map *= (1.0 - 0.30 * np.clip(r2, 0, 1)**2.5).astype(np.float32)
            field_r += sky_map * 0.85
            field_g += sky_map * 1.00
            field_b += sky_map * 1.10

        # ── DSOs ─────────────────────────────────────────────────────────
        dso_lum = np.zeros_like(field_g)
        self._render_dso(dso_lum, target_ra, target_dec, exposure_s, universe)
        field_r += dso_lum * 0.9
        field_g += dso_lum * 1.0
        field_b += dso_lum * 0.8

        # ── Stars ────────────────────────────────────────────────────────
        ra_margin     = self.fov_w * 0.75
        dec_margin    = self.fov_h * 0.6
        dec_min       = target_dec - dec_margin
        dec_max       = target_dec + dec_margin
        ra_margin_adj = ra_margin / max(0.01, math.cos(math.radians(target_dec)))

        # Target altitude (for extinction calculation)
        target_alt = getattr(self, '_target_alt', 45.0)

        for star in universe.get_stars():
            if star.mag > mag_limit:
                continue
            if star.dec_deg < dec_min or star.dec_deg > dec_max:
                continue
            dra = abs(star.ra_deg - target_ra)
            if dra > 180: dra = 360 - dra
            if dra > ra_margin_adj:
                continue

            pos = self._radec_to_pixel(star.ra_deg, star.dec_deg, target_ra, target_dec)
            if pos is None:
                continue
            px, py = pos
            if px < -20 or px > W + 20 or py < -20 or py > H + 20:
                continue

            # Extinction
            eff_mag = star.mag
            if atm_state is not None:
                ext = atm_state.extinction_at(target_alt,
                                               getattr(star, 'bv_color', 0.6))
                eff_mag += ext
                if eff_mag > mag_limit + 1.0:
                    continue

            total_photons = mag_to_flux(eff_mag, self.aperture_cm, exposure_s)
            r, g, b = bv_to_rgb(star.bv_color)

            psf, size = self._get_psf(eff_mag)
            ix, iy = int(round(px)), int(round(py))
            y0 = max(0, iy-size); y1 = min(H, iy+size+1)
            x0 = max(0, ix-size); x1 = min(W, ix+size+1)
            ky0 = size-(iy-y0); ky1 = ky0+(y1-y0)
            kx0 = size-(ix-x0); kx1 = kx0+(x1-x0)

            if y0 < y1 and x0 < x1 and ky0 < ky1 and kx0 < kx1:
                patch = psf[ky0:ky1, kx0:kx1] * total_photons
                field_r[y0:y1, x0:x1] += (patch * r).astype(np.float32)
                field_g[y0:y1, x0:x1] += (patch * g).astype(np.float32)
                field_b[y0:y1, x0:x1] += (patch * b).astype(np.float32)
    
    def get_info(self) -> dict:
        """Return optical parameters for display."""
        return {
            "aperture_mm": self.aperture_mm,
            "focal_length_mm": self.focal_length_mm,
            "focal_ratio": self.focal_length_mm / self.aperture_mm,
            "pixel_scale_arcsec": round(self.pixel_scale, 2),
            "fov_deg": (round(self.fov_w, 2), round(self.fov_h, 2)),
            "psf_fwhm_arcsec": round(self.psf_sigma * 2.355 * self.pixel_scale, 2),
            "seeing_arcsec": self.seeing_arcsec,
        }
