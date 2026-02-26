"""
milky_way_texture.py — Photorealistic Milky Way texture generator.

Generates a pre-computed galactic coordinate texture (l, b → RGB) with:
  - Accurate band profile (two-component: narrow core + wide halo)
  - Longitude brightness modulation matching real surface photometry
  - Central bulge (elliptical, warm golden)
  - Named star clouds (Scutum, Sagittarius, Cygnus, Carina, Norma, etc.)
  - Complex dust lane network (Great Rift, Coalsack, Pipe, Aquila, etc.)
  - Red emission nebulae at real HII region positions
  - Multi-octave fractal noise for organic, non-repeating structure
  - Unresolved star field granularity

The texture is built once at init (~100ms) and sampled via fast bilinear
interpolation during rendering.  The 3-channel output (R, G, B) encodes
warm starlight, cool disc light, and red emission separately.

Texture resolution: 1440×720 (0.25° per pixel in l and b).
"""
from __future__ import annotations
import math
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates


# ═══════════════════════════════════════════════════════════════════════════
# Value noise (hash-based, deterministic, no external deps)
# ═══════════════════════════════════════════════════════════════════════════

def _hash2d(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
    """Fast integer hash → [0, 1) float.  Deterministic."""
    # Robert Jenkins' 32-bit hash, vectorised
    h = (ix * 374761393 + iy * 668265263 + 1013904223).astype(np.int64)
    h = ((h >> 13) ^ h) * 1274126177
    h = ((h >> 16) ^ h)
    return (h & 0x7FFFFFFF).astype(np.float32) / 0x7FFFFFFF


def _value_noise_2d(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear-interpolated 2D value noise in [-1, +1]."""
    ix = np.floor(x).astype(np.int64)
    iy = np.floor(y).astype(np.int64)
    fx = (x - ix).astype(np.float32)
    fy = (y - iy).astype(np.float32)
    # Smoothstep for less blocky interpolation
    sx = fx * fx * (3.0 - 2.0 * fx)
    sy = fy * fy * (3.0 - 2.0 * fy)

    n00 = _hash2d(ix, iy)
    n10 = _hash2d(ix + 1, iy)
    n01 = _hash2d(ix, iy + 1)
    n11 = _hash2d(ix + 1, iy + 1)

    nx0 = n00 * (1 - sx) + n10 * sx
    nx1 = n01 * (1 - sx) + n11 * sx
    return (nx0 * (1 - sy) + nx1 * sy) * 2.0 - 1.0   # remap to [-1, +1]


def _fbm(x: np.ndarray, y: np.ndarray,
         octaves: int = 6, lacunarity: float = 2.0,
         gain: float = 0.5, seed_offset: float = 0.0) -> np.ndarray:
    """Fractal Brownian Motion (multi-octave value noise)."""
    total = np.zeros_like(x, dtype=np.float32)
    amplitude = 1.0
    freq = 1.0
    max_amp = 0.0
    for _ in range(octaves):
        total += amplitude * _value_noise_2d(
            x * freq + seed_offset, y * freq + seed_offset * 0.7)
        max_amp += amplitude
        amplitude *= gain
        freq *= lacunarity
        seed_offset += 31.7  # shift each octave
    return total / max_amp   # normalised to roughly [-1, +1]


# ═══════════════════════════════════════════════════════════════════════════
# Galactic feature definitions
# ═══════════════════════════════════════════════════════════════════════════

# Star clouds: (l_centre, b_centre, sigma_l, sigma_b, peak_brightness)
_STAR_CLOUDS = [
    # Sagittarius core region
    (  0.0,  -1.0,  8.0, 3.5, 0.50),
    # Large Sagittarius Star Cloud (M24 region)
    ( 18.0,  -1.5,  5.0, 2.5, 0.35),
    # Scutum Star Cloud
    ( 28.0,  -1.0,  5.0, 2.0, 0.40),
    # Cygnus Star Cloud
    ( 80.0,   0.5,  8.0, 3.0, 0.30),
    # Perseus arm tangent
    (105.0,   0.0,  8.0, 2.5, 0.15),
    # Carina arm
    (284.0,  -1.5,  10.0, 3.0, 0.35),
    # Centaurus / Crux
    (300.0,  -0.5,  8.0, 3.0, 0.30),
    # Norma Star Cloud
    (330.0,  -1.0,  6.0, 2.5, 0.35),
    # Vela region
    (265.0,  -1.0,  6.0, 2.5, 0.18),
]

# Dust lanes: (l_centre, b_centre, sigma_l, sigma_b, absorption_depth, tilt_deg)
# tilt_deg rotates the ellipse — models the rift not being perfectly aligned
_DUST_LANES = [
    # ── Great Rift main trunk ──
    # Cygnus Rift (northern end)
    ( 78.0,   2.0,  10.0, 2.0, 0.70, 15.0),
    # Aquila Rift
    ( 55.0,   3.0,  12.0, 2.5, 0.60,  5.0),
    ( 40.0,   2.5,  10.0, 2.0, 0.65, -5.0),
    # Ophiuchus dark clouds
    ( 25.0,   4.0,   8.0, 3.0, 0.55, 10.0),
    # Sagittarius dark lane (splits the core)
    (  8.0,   1.5,  10.0, 1.5, 0.70,  0.0),
    (  0.0,   1.0,   6.0, 1.5, 0.60, -5.0),
    # ── Southern dark features ──
    # Coalsack
    (303.0,  -1.0,   4.0, 3.0, 0.80,  0.0),
    # Pipe Nebula
    (  1.0,   5.0,   4.0, 2.0, 0.50, 30.0),
    # Dark Horse (Ophiuchus)
    (  5.0,   7.0,   5.0, 4.0, 0.40, 20.0),
    # Lupus dark cloud
    (335.0,  10.0,   5.0, 4.0, 0.30,  0.0),
    # Taurus dark clouds (anti-centre)
    (175.0,  -15.0,  8.0, 5.0, 0.25,  0.0),
    # Scorpius dark lane
    (350.0,   2.0,   6.0, 1.5, 0.55,  0.0),
    # Norma gap
    (325.0,   0.0,   5.0, 1.5, 0.45,  0.0),
    # Circinus dark patch
    (310.0,  -2.0,   4.0, 2.0, 0.40,  0.0),
    # Carina dark lane
    (288.0,  -1.0,   6.0, 1.5, 0.45, -10.0),
    # Vela dark clouds
    (262.0,   0.0,   5.0, 2.0, 0.35,  0.0),
]

# Emission nebulae (HII regions): (l, b, sigma, brightness, R_boost, G_boost, B_boost)
# In broadband allsky cameras, emission nebulae are INVISIBLE as individual
# features.  They contribute only a very subtle warm colour shift within the
# MW band.  Brightness values here are ~10× lower than a narrowband renderer
# would use.  Anything off the galactic plane (like Barnard's Loop at b=-19°)
# is completely undetectable.
_EMISSION_NEBULAE = [
    # Carina Nebula complex (NGC 3372) — subtle warm tint only
    (287.5,  -0.7,  3.0, 0.035,  1.0, 0.15, 0.20),
    # Eta Carinae extended
    (287.0,  -1.5,  5.0, 0.015,  0.8, 0.10, 0.15),
    # Gum Nebula (huge, extremely faint — below detection)
    (264.0,  -4.0, 12.0, 0.005,  0.6, 0.10, 0.15),
    # Lagoon Nebula (M8) — within band, subtle
    (  6.0,  -1.3,  1.5, 0.025,  1.0, 0.15, 0.10),
    # Trifid (M20) + Omega (M17)
    ( 15.0,  -0.7,  2.0, 0.020,  0.9, 0.15, 0.10),
    # Eagle Nebula (M16)
    ( 17.0,   0.8,  1.5, 0.015,  0.8, 0.12, 0.10),
    # North America Nebula (NGC 7000) — faint in broadband
    ( 85.0,  -0.5,  2.5, 0.018,  0.9, 0.15, 0.15),
    # Cygnus Loop / Veil (SNR) — way off-plane, invisible
    ( 74.0,  -8.5,  3.0, 0.003,  0.5, 0.20, 0.30),
    # Rosette Nebula
    (206.0,  -2.0,  2.0, 0.008,  0.7, 0.10, 0.10),
    # IC 1396 (Elephant's Trunk region)
    ( 99.0,   3.7,  2.5, 0.008,  0.7, 0.10, 0.10),
    # Orion Nebula complex — far off-plane (b=-19°), completely invisible allsky
    (209.0, -19.0,  4.0, 0.002,  0.8, 0.15, 0.20),
    # Heart & Soul nebulae
    (135.0,   1.0,  3.0, 0.006,  0.6, 0.10, 0.10),
    # W51 giant HII region
    ( 49.5,  -0.4,  2.0, 0.012,  0.7, 0.10, 0.08),
    # RCW 49 (Westerlund 2)
    (284.0,  -0.3,  1.5, 0.015,  0.8, 0.10, 0.10),
    # NGC 3603
    (291.6,  -0.5,  1.0, 0.012,  0.9, 0.12, 0.10),
    # Sagittarius B2 (near GC, warm)
    (  0.7,  -0.1,  1.0, 0.010,  0.6, 0.20, 0.05),
    # Lambda Centauri (IC 2944)
    (294.0,  -1.5,  1.5, 0.008,  0.6, 0.10, 0.10),
    # Flaming Star / IC 405 region
    (173.0,  -2.0,  2.0, 0.004,  0.5, 0.10, 0.12),
]


# ═══════════════════════════════════════════════════════════════════════════
# Texture builder
# ═══════════════════════════════════════════════════════════════════════════

def build_milky_way_texture(res_l: int = 1440, res_b: int = 720,
                             seed: int = 42) -> np.ndarray:
    """
    Build a (res_b, res_l, 3) float32 texture in galactic coordinates.

    l ∈ [0, 360), b ∈ [-90, +90).
    Channel 0 = Red, 1 = Green, 2 = Blue.
    Values are in "relative brightness" units (0–~2).

    The texture is symmetric-ish but not perfectly so, thanks to fractal
    noise — matching the real MW's slightly irregular appearance.
    """
    # Coordinate grids
    l_1d = np.linspace(0.0, 360.0, res_l, endpoint=False, dtype=np.float32)
    b_1d = np.linspace(-90.0, 90.0, res_b, endpoint=False, dtype=np.float32)
    l_grid, b_grid = np.meshgrid(l_1d, b_1d)   # (res_b, res_l)
    l_c = ((l_grid + 180.0) % 360.0) - 180.0   # centred on GC

    # ── 1. Band profile ───────────────────────────────────────────────────
    # Two-component Gaussian matching real allsky photos:
    #   - Narrow core (σ=5°): the bright band where dust lanes are visible
    #   - Moderate halo (σ=18°): gradual falloff into dark sky
    # NO wide background component — away from the plane, the sky is BLACK.
    # Real allsky photos show ~10-15° visible band width with ~20° soft fade.
    sigma_core = 5.0    # narrow bright core — dust lanes live here
    sigma_halo = 18.0   # soft transition to dark sky
    band_core = np.exp(-0.5 * (b_grid / sigma_core) ** 2)
    band_halo = np.exp(-0.5 * (b_grid / sigma_halo) ** 2) * 0.20
    band = (band_core + band_halo).astype(np.float32)

    # ── 2. Longitude brightness ───────────────────────────────────────────
    l_rad = np.radians(l_grid)
    lon_base = 0.35 + 0.65 * np.cos(l_rad)   # 1.0 at GC, ~0 anti-centre
    # Smooth the base with a secondary harmonic for arm structure
    lon_base += 0.08 * np.cos(2 * l_rad + 0.3)
    lon_base += 0.05 * np.cos(3 * l_rad - 0.7)
    lon_mod = np.clip(lon_base, 0.08, 1.0).astype(np.float32)

    # ── 3. Star clouds ────────────────────────────────────────────────────
    star_cloud_layer = np.zeros_like(l_grid)
    for (cl, cb, sl, sb, pk) in _STAR_CLOUDS:
        dl = ((l_grid - cl + 180.0) % 360.0) - 180.0
        star_cloud_layer += pk * np.exp(-0.5 * ((dl / sl) ** 2 + (b_grid - cb) ** 2 / sb ** 2))

    # ── 4. Central bulge ──────────────────────────────────────────────────
    # Elliptical, slightly tilted, golden
    bulge_l = l_c
    bulge_b = b_grid + 0.5  # centre slightly below plane
    bulge = 1.00 * np.exp(-0.5 * ((bulge_l / 12.0) ** 2 + (bulge_b / 6.0) ** 2))
    # Inner bright core
    bulge += 0.80 * np.exp(-0.5 * ((bulge_l / 4.0) ** 2 + (bulge_b / 2.5) ** 2))

    # ── 5. Dust lanes (absorption) ────────────────────────────────────────
    absorption = np.ones_like(l_grid)
    for (cl, cb, sl, sb, depth, tilt) in _DUST_LANES:
        dl = ((l_grid - cl + 180.0) % 360.0) - 180.0
        db = b_grid - cb
        # Apply tilt rotation
        if abs(tilt) > 0.5:
            cos_t = math.cos(math.radians(tilt))
            sin_t = math.sin(math.radians(tilt))
            dl_r = dl * cos_t + db * sin_t
            db_r = -dl * sin_t + db * cos_t
        else:
            dl_r, db_r = dl, db
        mask = np.exp(-0.5 * ((dl_r / sl) ** 2 + (db_r / sb) ** 2))
        absorption *= (1.0 - depth * mask)

    # Add fractal noise to dust for organic edges
    rng_seed = seed + 100
    dust_noise = _fbm(l_grid * 0.08 + rng_seed, b_grid * 0.15 + rng_seed * 0.3,
                       octaves=5, lacunarity=2.1, gain=0.48)
    # Modulate absorption edges: noise makes dust clumpier and more visible
    absorption_noisy = absorption + 0.22 * dust_noise * (1.0 - absorption)
    absorption = np.clip(absorption_noisy, 0.03, 1.0).astype(np.float32)

    # ── 6. Fractal noise for star field texture ───────────────────────────
    # Large-scale arm structure
    noise_large = _fbm(l_grid * 0.03 + seed, b_grid * 0.06 + seed,
                        octaves=3, lacunarity=2.0, gain=0.5)
    # Medium-scale star cloud clumps
    noise_med = _fbm(l_grid * 0.10 + seed * 1.3, b_grid * 0.18 + seed * 1.3,
                      octaves=4, lacunarity=2.0, gain=0.50)
    # Fine-scale granularity (individual star clusters, dark globules)
    noise_fine = _fbm(l_grid * 0.35 + seed * 2.1, b_grid * 0.60 + seed * 2.1,
                       octaves=3, lacunarity=2.2, gain=0.45)
    # Very fine noise — unresolved star cluster granularity
    noise_vfine = _fbm(l_grid * 0.95 + seed * 3.3, b_grid * 1.60 + seed * 3.3,
                        octaves=3, lacunarity=2.2, gain=0.42)
    texture = (1.0
               + 0.25 * noise_large
               + 0.18 * noise_med
               + 0.15 * noise_fine
               + 0.08 * noise_vfine)
    texture = np.clip(texture, 0.45, 1.55).astype(np.float32)

    # ── 7. Combine into luminance ─────────────────────────────────────────
    luminance = (band * lon_mod + star_cloud_layer + bulge) * absorption * texture
    luminance = np.clip(luminance, 0.0, None).astype(np.float32)
    # Minimum floor: essentially zero — the MW band naturally fades to nothing
    # at high galactic latitudes.  The halo component (σ=18°) provides the
    # gradual transition.  No artificial floor needed.
    luminance = np.maximum(luminance, 0.001)

    # ── 8. Colour mapping ─────────────────────────────────────────────────
    # Base colour depends on longitude (warm core → cool disc)
    core_weight = np.exp(-0.5 * (l_c / 45.0) ** 2)  # 1 at GC, 0 far away
    # Also modulate by latitude: off-plane is cooler
    lat_cool = np.clip(np.abs(b_grid) / 15.0, 0.0, 1.0)

    # Starlight colour channels
    # Core: warm gold   (1.00, 0.85, 0.55)
    # Disc: cool silver  (0.80, 0.88, 1.00)
    w = core_weight * (1.0 - lat_cool * 0.5)  # warm weight
    c = 1.0 - w                                # cool weight

    r_base = (1.00 * w + 0.80 * c).astype(np.float32)
    g_base = (0.85 * w + 0.88 * c).astype(np.float32)
    b_base = (0.55 * w + 1.00 * c).astype(np.float32)

    # Bulge is extra warm/golden
    bulge_norm = np.clip(bulge / (bulge.max() + 1e-9), 0, 1)
    r_base += bulge_norm * 0.20
    g_base += bulge_norm * 0.05
    b_base -= bulge_norm * 0.15

    out_r = luminance * r_base
    out_g = luminance * g_base
    out_b = luminance * b_base

    # ── 9. Emission nebulae (red) ─────────────────────────────────────────
    for (cl, cb, sig, bright, er, eg, eb) in _EMISSION_NEBULAE:
        dl = ((l_grid - cl + 180.0) % 360.0) - 180.0
        db = b_grid - cb
        mask = np.exp(-0.5 * ((dl / sig) ** 2 + (db / sig) ** 2))
        # Add noise to emission for filamentary structure
        em_noise = _fbm(dl * 0.5 + cl, db * 0.8 + cb, octaves=3, gain=0.5)
        mask *= np.clip(0.6 + 0.4 * em_noise, 0.1, 1.0)
        out_r += mask * bright * er
        out_g += mask * bright * eg
        out_b += mask * bright * eb

    # ── 10. Zodiacal light + gegenschein ─────────────────────────────────
    # Ecliptic north pole in galactic coordinates: (l≈96.4°, b≈29.8°)
    _enp_l_r = math.radians(96.4)
    _enp_b_r = math.radians(29.8)
    enp_x = math.cos(_enp_b_r) * math.cos(_enp_l_r)
    enp_y = math.cos(_enp_b_r) * math.sin(_enp_l_r)
    enp_z = math.sin(_enp_b_r)

    # Galactic unit vectors for the texture grid
    b_r = np.radians(b_grid)
    l_r_zod = np.radians(l_grid)
    vx_g = np.cos(b_r) * np.cos(l_r_zod)
    vy_g = np.cos(b_r) * np.sin(l_r_zod)
    vz_g = np.sin(b_r)

    # Ecliptic latitude (sine = dot product with ecliptic pole)
    sin_elat = np.clip(vx_g * enp_x + vy_g * enp_y + vz_g * enp_z, -1.0, 1.0)
    elat_deg = np.degrees(np.arcsin(sin_elat))

    # Zodiacal band: sigma ~15° in ecliptic latitude, warm yellow-white colour
    sigma_zod = 15.0
    zod_band = np.exp(-0.5 * (elat_deg / sigma_zod) ** 2).astype(np.float32)
    # Brightness modulation: brighter near l=0 (galactic centre direction)
    zod_lon_mod = (0.55 + 0.45 * np.cos(np.radians(l_grid))).astype(np.float32)
    # Zodiacal light is barely perceptible in broadband allsky photos.
    # Only visible as a very subtle warm tint near the ecliptic plane.
    zod_brightness = 0.015
    out_r += zod_band * zod_lon_mod * zod_brightness * 1.10   # warm yellow-white
    out_g += zod_band * zod_lon_mod * zod_brightness * 1.05
    out_b += zod_band * zod_lon_mod * zod_brightness * 0.85

    # Gegenschein: broad faint spot at anti-solar proxy (l=180° ecliptic plane crossing)
    # Use a fixed representative position near ecliptic at l≈180°, b≈0°
    gsch_dl = (l_grid % 360.0) - 180.0
    gsch_db = b_grid
    gegenschein = np.exp(-0.5 * ((gsch_dl / 12.0) ** 2 + (gsch_db / 10.0) ** 2))
    gegenschein *= zod_band * 0.008   # essentially invisible in allsky
    out_r += gegenschein.astype(np.float32) * 1.10
    out_g += gegenschein.astype(np.float32) * 1.05
    out_b += gegenschein.astype(np.float32) * 0.85

    # ── 11. Finalise ──────────────────────────────────────────────────────
    tex = np.stack([out_r, out_g, out_b], axis=-1).astype(np.float32)

    # Poissonian micro-variation: faint per-pixel noise to prevent smooth look
    rng = np.random.default_rng(seed + 7)
    lum_mean = np.mean(tex, axis=-1, keepdims=True)
    poisson_noise = rng.uniform(-1.0, 1.0, tex.shape).astype(np.float32)
    tex += poisson_noise * np.clip(lum_mean * 0.015, 0.0, None)

    # Gaussian blur to smooth texture edges — larger sigma produces the
    # soft, nebulous look of real MW photographs instead of hard patches
    for ch in range(3):
        tex[:, :, ch] = gaussian_filter(tex[:, :, ch], sigma=1.5)

    return tex


# ═══════════════════════════════════════════════════════════════════════════
# MilkyWayLayer (drop-in replacement)
# ═══════════════════════════════════════════════════════════════════════════

class MilkyWayLayer:
    """
    Texture-based Milky Way renderer for the allsky camera.

    At initialisation, builds a high-detail galactic coordinate texture
    (1440×720, 0.25°/px) encoding MW structure, dust lanes, star clouds,
    and emission nebulae.  At render time, converts each fisheye pixel
    to galactic (l, b) and samples the texture via bilinear interpolation.

    The photon brightness is calibrated so the MW core adds ~30–50% above
    the dark sky pedestal (~5 ph/px), matching real allsky photos from
    Bortle 2–3 sites.

    Usage::

        mw = MilkyWayLayer()
        mw.render(field, jd, lat, lon, cx, cy, radius)
    """

    _GC_RA_DEG   = 266.405_100
    _GC_DEC_DEG  = -28.936_175
    _GNP_RA_DEG  = 192.859_508
    _GNP_DEC_DEG =  27.128_336

    def __init__(self, brightness: float = 18.0, seed: int = 44):
        """
        Parameters
        ----------
        brightness : float
            Global brightness multiplier.  Default 18.0 tuned for the narrow
            band profile — the MW core is clearly visible with dark lanes
            while the sky away from the plane stays uniformly dark.
            
            Guide:  8  = barely visible (ultra-realistic Bortle 3)
                   14  = subtle glow (realistic wide-field photo)
                   18  = clear band with dust detail (game default)
                   30+ = dramatic poster look
        seed : int
            Random seed for fractal noise (deterministic).
        """
        self.brightness = brightness

        # Pre-compute galactic reference vectors
        self._gnp = self._unit(math.radians(self._GNP_DEC_DEG),
                               math.radians(self._GNP_RA_DEG))
        self._gc  = self._unit(math.radians(self._GC_DEC_DEG),
                               math.radians(self._GC_RA_DEG))

        # Pre-compute galactic coordinate helpers
        gnp = self._gnp.astype(np.float64)
        gc  = self._gc.astype(np.float64)
        ge  = np.cross(gnp, gc)
        ge /= np.linalg.norm(ge) + 1e-15
        gc_plane = gc - np.dot(gc, gnp) * gnp
        gc_plane /= np.linalg.norm(gc_plane) + 1e-15
        self._gnp_f = gnp.astype(np.float32)
        self._ge_f  = ge.astype(np.float32)
        self._gcp_f = gc_plane.astype(np.float32)

        # Build the texture map (or load from cache)
        self._tex_res_l = 1440
        self._tex_res_b = 720
        self._texture = self._load_or_build_texture(seed)
        # Pixel scale for coordinate → texture index conversion
        self._l_scale = self._tex_res_l / 360.0   # px per degree
        self._b_scale = self._tex_res_b / 180.0   # px per degree
        self._b_offset = 90.0                       # b=-90 → row 0

    def _load_or_build_texture(self, seed: int) -> np.ndarray:
        """Load texture from disk cache, or build and save it."""
        import os, hashlib
        cache_key = f"mw_tex_{self._tex_res_l}x{self._tex_res_b}_s{seed}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()[:10]
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
        cache_path = os.path.join(cache_dir, f"milky_way_{cache_hash}.npz")

        if os.path.exists(cache_path):
            try:
                data = np.load(cache_path)
                tex = data['texture']
                if tex.shape == (self._tex_res_b, self._tex_res_l, 3):
                    return tex.astype(np.float32)
            except Exception:
                pass  # Rebuild if cache is corrupted

        tex = build_milky_way_texture(self._tex_res_l, self._tex_res_b, seed=seed)
        try:
            os.makedirs(cache_dir, exist_ok=True)
            np.savez_compressed(cache_path, texture=tex)
        except Exception:
            pass  # Not fatal if we can't cache
        return tex

    @staticmethod
    def _unit(dec_r: float, ra_r: float) -> np.ndarray:
        return np.array([
            math.cos(dec_r) * math.cos(ra_r),
            math.cos(dec_r) * math.sin(ra_r),
            math.sin(dec_r),
        ], dtype=np.float64)

    def _sample_texture(self, l_deg: np.ndarray, b_deg: np.ndarray) -> np.ndarray:
        """
        Bilinear sample from the pre-built texture.

        l_deg: (H, W) in [0, 360)
        b_deg: (H, W) in [-90, +90)
        Returns: (H, W, 3) float32
        """
        # Convert (l, b) to texture pixel coordinates
        tx = l_deg * self._l_scale                       # 0 → res_l
        ty = (b_deg + self._b_offset) * self._b_scale   # -90→0, +90→res_b

        result = np.zeros(l_deg.shape + (3,), dtype=np.float32)
        for c in range(3):
            result[:, :, c] = map_coordinates(
                self._texture[:, :, c],
                [ty, tx],
                order=1,          # bilinear
                mode='wrap',      # l wraps around 360°
                prefilter=False,
            )
        return result

    def render(self, field: np.ndarray, jd: float,
               lat: float, lon: float,
               cx: float, cy: float, radius: float,
               solar_alt_deg: float = -90.0) -> None:
        """Composite the Milky Way onto *field* in-place."""
        if solar_alt_deg > -6.0:
            return

        fade = min(1.0, (-6.0 - solar_alt_deg) / 6.0)

        H, W = field.shape[:2]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dx = xx - cx
        dy = yy - cy
        r_px = np.sqrt(dx * dx + dy * dy)
        inside = r_px <= radius

        # Alt/Az maps
        alt_map = np.where(inside,
                           90.0 * (1.0 - r_px / (radius + 1e-9)),
                           -1.0).astype(np.float64)
        az_map  = (np.degrees(np.arctan2(dx, -dy)) % 360.0).astype(np.float64)

        lat_r = math.radians(lat)
        alt_r = np.radians(alt_map)
        az_r  = np.radians(az_map)

        # Alt/Az → Equatorial
        sin_dec = (np.sin(alt_r) * math.sin(lat_r) +
                   np.cos(alt_r) * math.cos(lat_r) * np.cos(az_r))
        sin_dec = np.clip(sin_dec, -1.0, 1.0)
        dec_r_map = np.arcsin(sin_dec)
        cos_dec   = np.cos(dec_r_map)

        cos_ha = np.where(
            cos_dec > 1e-9,
            np.clip((np.sin(alt_r) - math.sin(lat_r) * sin_dec) /
                    (math.cos(lat_r) * cos_dec + 1e-15), -1.0, 1.0),
            1.0)
        ha_r = np.arccos(cos_ha)
        ha_r = np.where(np.sin(az_r) > 0, 2 * math.pi - ha_r, ha_r)

        T = (jd - 2451545.0) / 36525.0
        GMST = (280.46061837 + 360.98564736629 * (jd - 2451545.0) +
                T * T * 0.000387933) % 360.0
        lst_r = math.radians((GMST + lon) % 360.0)
        ra_r = (lst_r - ha_r) % (2 * math.pi)

        # Equatorial unit vectors
        vx = np.cos(dec_r_map) * np.cos(ra_r)
        vy = np.cos(dec_r_map) * np.sin(ra_r)
        vz = sin_dec

        # → Galactic (l, b)
        gnp = self._gnp_f
        sin_b = np.clip(vx * gnp[0] + vy * gnp[1] + vz * gnp[2], -1.0, 1.0)
        b_deg = np.degrees(np.arcsin(sin_b))

        gcp = self._gcp_f
        ge  = self._ge_f
        dot_gc = vx * gcp[0] + vy * gcp[1] + vz * gcp[2]
        dot_ge = vx * ge[0]  + vy * ge[1]  + vz * ge[2]
        l_deg  = np.degrees(np.arctan2(dot_ge, dot_gc)) % 360.0

        # Sample the pre-built texture
        mw_rgb = self._sample_texture(l_deg, b_deg)

        # Apply brightness, fade, and mask
        scale = self.brightness * fade

        # Soft horizon mask: smooth fade from 0° to 5° altitude instead of
        # hard cutoff at 0.5°.  Prevents visible "stamp edge" at horizon.
        horizon_fade = np.clip(alt_map / 5.0, 0.0, 1.0).astype(np.float32)
        mask = inside.astype(np.float32) * horizon_fade

        # Galactic latitude opacity: the MW is visible within ~30° of
        # the galactic plane, with a gentle fade into the sky background.
        abs_b = np.abs(b_deg)
        # Full brightness at |b|<10° (core with dust lanes), smooth
        # fade to zero at |b|=35°.  The warmer sky background (Bortle)
        # provides continuity so the MW doesn't look "pasted on".
        lat_opacity = np.clip(1.0 - (abs_b - 10.0) / 25.0, 0.0, 1.0).astype(np.float32)
        mask *= lat_opacity

        field[:, :, 0] += mw_rgb[:, :, 0] * scale * mask
        field[:, :, 1] += mw_rgb[:, :, 1] * scale * mask
        field[:, :, 2] += mw_rgb[:, :, 2] * scale * mask
