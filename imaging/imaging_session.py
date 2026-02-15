"""
Imaging System Module
Estratto e refactorizzato da astro2.py per integrazione nel gioco principale
"""

from __future__ import annotations
import numpy as np
import math
from dataclasses import dataclass
from typing import Optional, Callable

# RNG deterministico (compatibile con catalogs/procedural.py)
def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF

def hash_u64(*vals: int) -> int:
    x = 0xA5A5A5A5A5A5A5A5
    for v in vals:
        x ^= (v & 0xFFFFFFFFFFFFFFFF)
        x = splitmix64(x)
    return x

def rng_from_seed(seed_u64: int) -> np.random.Generator:
    return np.random.default_rng(np.uint64(seed_u64))

# Tag per tipi di frame
TAG_DARK = 0xD042
TAG_FLAT = 0xF1A7
TAG_LIGHT = 0x11A7

@dataclass
class ImagingTarget:
    """Target per imaging"""
    obj_id: int
    ra_deg: float
    dec_deg: float
    name: str
    mag: float
    
    # Per variabili
    is_variable: bool = False
    period_h: float = 0.0
    amp_mag: float = 0.0

@dataclass
class CameraSettings:
    """Impostazioni camera CCD/CMOS"""
    width: int = 1280
    height: int = 960
    pixel_size_um: float = 3.75
    read_noise_e: float = 3.0
    dark_current_e_s: float = 0.05
    quantum_efficiency: float = 0.75
    gain: float = 1.0
    full_well_e: int = 25000

@dataclass
class TelescopeSettings:
    """Impostazioni telescopio"""
    aperture_mm: float = 150.0
    focal_length_mm: float = 750.0
    obstruction_pct: float = 0.0
    
    def f_ratio(self) -> float:
        return self.focal_length_mm / self.aperture_mm
    
    def plate_scale_arcsec_px(self, pixel_size_um: float) -> float:
        """Plate scale in arcsec/pixel"""
        return 206.265 * pixel_size_um / self.focal_length_mm
    
    def fwhm_arcsec(self, seeing_arcsec: float = 2.5) -> float:
        """FWHM teorico limitato da seeing"""
        # Diffraction limit
        fwhm_diff = 2.44 * 0.00055 * 206265 / self.aperture_mm  # lambda=550nm
        # Combinazione seeing + diffraction
        return math.sqrt(seeing_arcsec**2 + fwhm_diff**2)

class ImagingSession:
    """Sessione di imaging completa"""
    
    def __init__(self, 
                 target: ImagingTarget,
                 camera: CameraSettings,
                 telescope: TelescopeSettings,
                 global_seed: int):
        self.target = target
        self.camera = camera
        self.telescope = telescope
        self.global_seed = global_seed
        
        # Star field "truth" (posizioni stelle)
        self.truth = None
        
        # Frames
        self.light_frames: list[np.ndarray] = []
        self.dark_frames: list[np.ndarray] = []
        self.flat_frames: list[np.ndarray] = []
        self.bias_frames: list[np.ndarray] = []
        
        # Master calibrations
        self.master_dark: Optional[np.ndarray] = None
        self.master_flat: Optional[np.ndarray] = None
        self.master_bias: Optional[np.ndarray] = None
        
        # Calibrated & stacked
        self.calibrated_frames: list[np.ndarray] = []
        self.stacked_image: Optional[np.ndarray] = None
        
        # Logging
        self.log: list[str] = []
    
    def generate_star_field(self, n_stars: int = 200) -> dict:
        """Genera campo stellare deterministico"""
        seed = hash_u64(self.global_seed, self.target.obj_id, 0x57A9)  # STAR-like value
        rng = rng_from_seed(seed)
        
        w, h = self.camera.width, self.camera.height
        
        # Posizioni
        xs = rng.uniform(0, w, size=n_stars)
        ys = rng.uniform(0, h, size=n_stars)
        
        # Flussi (distribuzione power-law per magnitudini realistiche)
        flux = (rng.pareto(a=2.2, size=n_stars) + 1.0)
        flux = flux / np.max(flux)
        flux = 0.2 + 2.8 * (flux ** 2.5)
        
        # Temperature colore
        temp = rng.uniform(3000, 9000, size=n_stars)
        
        self.truth = {"xs": xs, "ys": ys, "flux": flux, "temp": temp}
        self.log.append(f"Generated star field: {n_stars} stars")
        
        return self.truth
    
    def render_truth_image(self, fwhm_px: float = 2.5) -> np.ndarray:
        """Renderizza truth image (ideale, no noise)"""
        if self.truth is None:
            raise RuntimeError("No truth data, call generate_star_field() first")
        
        w, h = self.camera.width, self.camera.height
        img = np.zeros((h, w), dtype=np.float32)
        
        sigma = max(0.6, fwhm_px / 2.355)
        r = int(max(2, math.ceil(4.0 * sigma)))
        
        # Gaussian kernel
        y_idx = np.arange(-r, r + 1, dtype=np.float32)
        x_idx = np.arange(-r, r + 1, dtype=np.float32)
        X, Y = np.meshgrid(x_idx, y_idx)
        G = np.exp(-(X * X + Y * Y) / (2.0 * sigma * sigma)).astype(np.float32)
        G /= (G.sum() + 1e-12)
        
        # Stamp stelle
        xs = self.truth["xs"]
        ys = self.truth["ys"]
        flux = self.truth["flux"]
        
        for x, y, f in zip(xs, ys, flux):
            ix, iy = int(x), int(y)
            x0, y0 = ix - r, iy - r
            x1, y1 = ix + r + 1, iy + r + 1
            
            sx0, sy0 = 0, 0
            sx1, sy1 = G.shape[1], G.shape[0]
            
            if x0 < 0:
                sx0 = -x0
                x0 = 0
            if y0 < 0:
                sy0 = -y0
                y0 = 0
            if x1 > w:
                sx1 -= (x1 - w)
                x1 = w
            if y1 > h:
                sy1 -= (y1 - h)
                y1 = h
            
            if x0 >= x1 or y0 >= y1:
                continue
            
            img[y0:y1, x0:x1] += (f * G[sy0:sy1, sx0:sx1])
        
        return img
    
    def make_flat_field(self) -> np.ndarray:
        """Crea flat field con vignetting e dust spots"""
        seed = hash_u64(self.global_seed, TAG_FLAT, self.target.obj_id)
        rng = rng_from_seed(seed)
        
        w, h = self.camera.width, self.camera.height
        yy, xx = np.mgrid[0:h, 0:w]
        
        cx, cy = w * 0.5, h * 0.5
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2) / (0.5 * min(w, h))
        
        # Vignetting
        vignette = 1.0 - 0.35 * (r ** 2.2)
        vignette = np.clip(vignette, 0.5, 1.1)
        
        flat = vignette.astype(np.float32)
        
        # Dust motes
        n_motes = 8
        for _ in range(n_motes):
            mx = rng.uniform(0, w)
            my = rng.uniform(0, h)
            mr = rng.uniform(8, 22)
            strength = rng.uniform(0.03, 0.10)
            d = ((xx - mx)**2 + (yy - my)**2) / (2.0 * (mr**2))
            flat *= (1.0 - strength * np.exp(-d)).astype(np.float32)
        
        flat /= (flat.mean() + 1e-12)
        return flat.astype(np.float32)
    
    def make_dark_frame(self, exposure_s: float = 60.0) -> np.ndarray:
        """Crea dark frame con thermal noise e hot pixels"""
        seed = hash_u64(self.global_seed, TAG_DARK, int(exposure_s * 1000))
        rng = rng_from_seed(seed)
        
        w, h = self.camera.width, self.camera.height
        
        # Dark current
        dark_level = self.camera.dark_current_e_s * exposure_s / self.camera.gain
        dark = rng.normal(loc=dark_level, scale=dark_level * 0.5, size=(h, w)).astype(np.float32)
        
        # Hot pixels
        n_hot = int(0.0008 * w * h)
        ys = rng.integers(0, h, size=n_hot)
        xs = rng.integers(0, w, size=n_hot)
        dark[ys, xs] += rng.uniform(0.10, 0.35, size=n_hot).astype(np.float32)
        
        return np.clip(dark, 0.0, None)
    
    def make_light_frame(self, 
                        truth_img: np.ndarray,
                        flat: np.ndarray,
                        dark: np.ndarray,
                        exposure_s: float = 60.0,
                        sky_bg: float = 0.03,
                        jitter_px: float = 0.6) -> np.ndarray:
        """Crea light frame con tutti i noise sources"""
        seed = hash_u64(self.global_seed, TAG_LIGHT, len(self.light_frames))
        rng = rng_from_seed(seed)
        
        h, w = truth_img.shape
        
        # Jitter (guiding imperfetto)
        dx = int(np.round(rng.normal(0.0, jitter_px)))
        dy = int(np.round(rng.normal(0.0, jitter_px)))
        shifted = np.roll(np.roll(truth_img, dy, axis=0), dx, axis=1)
        
        # Signal con flat
        signal = shifted * flat
        
        # Sky background
        img = signal + sky_bg
        
        # Dark current
        img = img + dark
        
        # Shot noise (Poisson)
        shot_sigma = np.sqrt(np.clip(img, 0.0, None)) * 0.05
        img = img + rng.normal(0.0, shot_sigma).astype(np.float32)
        
        # Read noise
        read_sigma = self.camera.read_noise_e / self.camera.gain
        img = img + rng.normal(0.0, read_sigma, size=(h, w)).astype(np.float32)
        
        return np.clip(img, 0.0, None).astype(np.float32)
    
    def acquire_dataset(self, 
                       n_lights: int = 10,
                       n_darks: int = 10,
                       n_flats: int = 10,
                       exposure_s: float = 60.0):
        """Acquisisce un dataset completo"""
        self.log.append(f"Starting acquisition: {n_lights}L + {n_darks}D + {n_flats}F")
        
        # Generate truth
        if self.truth is None:
            self.generate_star_field()
        
        truth_img = self.render_truth_image()
        
        # Seeing conditions
        seeing_arcsec = 2.5
        plate_scale = self.telescope.plate_scale_arcsec_px(self.camera.pixel_size_um)
        fwhm_arcsec = self.telescope.fwhm_arcsec(seeing_arcsec)
        fwhm_px = fwhm_arcsec / plate_scale
        
        # Master calibrations
        flat = self.make_flat_field()
        
        # Acquire lights
        for i in range(n_lights):
            dark = self.make_dark_frame(exposure_s)
            light = self.make_light_frame(truth_img, flat, dark, exposure_s)
            self.light_frames.append(light)
        
        # Acquire darks
        for i in range(n_darks):
            dark = self.make_dark_frame(exposure_s)
            self.dark_frames.append(dark)
        
        # Acquire flats
        for i in range(n_flats):
            self.flat_frames.append(flat + np.random.normal(0, 0.01, flat.shape).astype(np.float32))
        
        self.log.append(f"Acquisition complete: {len(self.light_frames)} lights acquired")
    
    def create_masters(self):
        """Crea master dark/flat/bias"""
        if len(self.dark_frames) > 0:
            self.master_dark = np.mean(np.stack(self.dark_frames), axis=0).astype(np.float32)
            self.log.append(f"Master dark: median of {len(self.dark_frames)} frames")
        
        if len(self.flat_frames) > 0:
            self.master_flat = np.median(np.stack(self.flat_frames), axis=0).astype(np.float32)
            self.log.append(f"Master flat: median of {len(self.flat_frames)} frames")
    
    def calibrate_frames(self):
        """Calibra i light frames"""
        if self.master_dark is None or self.master_flat is None:
            self.create_masters()
        
        self.calibrated_frames = []
        
        for light in self.light_frames:
            cal = (light - self.master_dark) / (self.master_flat + 1e-6)
            cal = np.clip(cal, 0.0, None).astype(np.float32)
            self.calibrated_frames.append(cal)
        
        self.log.append(f"Calibrated {len(self.calibrated_frames)} light frames")
    
    def stack_frames(self, method: str = "mean"):
        """Stacka i frame calibrati"""
        if len(self.calibrated_frames) == 0:
            self.calibrate_frames()
        
        stack = np.stack(self.calibrated_frames, axis=0)
        
        if method == "mean":
            self.stacked_image = np.mean(stack, axis=0).astype(np.float32)
        elif method == "median":
            self.stacked_image = np.median(stack, axis=0).astype(np.float32)
        elif method == "sigma_clip":
            # Sigma clipping (rimuove outlier)
            mean = np.mean(stack, axis=0)
            std = np.std(stack, axis=0)
            
            mask = np.abs(stack - mean) < 3 * std
            masked = np.where(mask, stack, np.nan)
            
            self.stacked_image = np.nanmean(masked, axis=0).astype(np.float32)
        
        self.log.append(f"Stacked {len(self.calibrated_frames)} frames using {method}")
    
    def get_current_image(self, mode: str = "STACK", frame_idx: int = 0) -> Optional[np.ndarray]:
        """Recupera l'immagine corrente da visualizzare"""
        if mode == "RAW":
            if frame_idx < len(self.light_frames):
                return self.light_frames[frame_idx]
        elif mode == "CAL":
            if frame_idx < len(self.calibrated_frames):
                return self.calibrated_frames[frame_idx]
        elif mode == "STACK":
            return self.stacked_image
        
        return None

# Utility per conversione immagini
def stretch_to_u8(img: np.ndarray, 
                  black: float = 0.0,
                  white: float = 1.0,
                  gamma: float = 2.2) -> np.ndarray:
    """Stretch istogramma e converti a uint8"""
    if img is None:
        return None
    
    stretched = (img - black) / (white - black + 1e-9)
    stretched = np.clip(stretched, 0.0, 1.0)
    stretched = stretched ** (1.0 / gamma)
    
    return (stretched * 255).astype(np.uint8)

def histogram_counts(img: np.ndarray, bins: int = 64) -> tuple[np.ndarray, float, float]:
    """Calcola istogramma robusto"""
    if img is None:
        return np.zeros(bins), 0.0, 1.0
    
    # Usa percentili per range robusto
    lo = np.percentile(img, 1)
    hi = np.percentile(img, 99)
    
    counts, edges = np.histogram(img.flatten(), bins=bins, range=(lo, hi))
    
    return counts, lo, hi
