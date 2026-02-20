"""
CloudLayer — procedural cloud mask for allsky rendering.

Generates a 2D float32 array on the allsky disk coordinate system.
Handles dynamic render_size changes (screen_imaging.py changes it at runtime).
"""

from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


CLOUD_UPDATE_INTERVAL_S: float = 2.0
DRIFT_SPEED_PX_PER_S: float = 0.18


def _coverage_from_transparency(transparency: float) -> float:
    """Map transparency (0=cloudy, 1=clear) to cloud coverage fraction."""
    t = max(0.0, min(1.0, transparency))
    coverage = (1.0 - t) ** 1.4
    return float(coverage)


def generate_cloud_mask(size: int,
                        coverage: float,
                        time_s: float,
                        seed: int = 42) -> np.ndarray:
    """
    Generate a (size, size) float32 cloud opacity mask.
    
    mask[y, x] = 0.0 → clear sky at this pixel
    mask[y, x] = 1.0 → fully opaque cloud
    """
    if coverage < 0.02:
        return np.zeros((size, size), dtype=np.float32)
    
    H = W = size
    cx = cy = size * 0.5
    
    # Coordinate grids (normalized −1 to +1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xn = (xx - cx) / cx
    yn = (yy - cy) / cy
    
    # Inside circle mask
    r_norm = np.sqrt(xn**2 + yn**2)
    inside = (r_norm <= 1.0).astype(np.float32)
    
    # Cloud drift offset
    seed_f = float(seed)
    
    # Layer 1: large-scale cloud structures
    freq1  = 2.8
    drift1_x = DRIFT_SPEED_PX_PER_S * time_s / cx * math.cos(seed_f * 0.7)
    drift1_y = DRIFT_SPEED_PX_PER_S * time_s / cy * math.sin(seed_f * 0.7)
    n1 = (np.sin((xn + drift1_x) * freq1 + seed_f * 1.3) *
          np.cos((yn + drift1_y) * freq1 + seed_f * 0.9))
    
    # Layer 2: medium-scale structures
    freq2  = 5.5
    drift2_x = DRIFT_SPEED_PX_PER_S * 0.6 * time_s / cx * math.cos(seed_f * 1.4 + 1.2)
    drift2_y = DRIFT_SPEED_PX_PER_S * 0.6 * time_s / cy * math.sin(seed_f * 1.4 + 1.2)
    n2 = (np.sin((xn + drift2_x) * freq2 + seed_f * 2.1) *
          np.cos((yn + drift2_y) * freq2 + seed_f * 1.7)) * 0.5
    
    # Layer 3: fine texture
    freq3  = 11.0
    drift3_x = DRIFT_SPEED_PX_PER_S * 0.3 * time_s / cx * math.cos(seed_f * 2.3 + 0.8)
    n3 = np.sin((xn + drift3_x) * freq3 + seed_f * 3.7) * 0.25
    
    # Combine layers
    noise = n1 + n2 + n3
    
    # Normalize to 0..1
    noise_min = float(noise.min())
    noise_max = float(noise.max())
    noise_range = max(noise_max - noise_min, 1e-6)
    noise_norm = (noise - noise_min) / noise_range
    
    # Threshold
    threshold = 1.0 - coverage
    threshold = max(0.0, min(0.99, threshold))
    
    # Soft edge
    edge_width = 0.12
    mask = np.clip((noise_norm - threshold) / edge_width, 0.0, 1.0)
    
    # Apply inside-circle mask
    mask = mask * inside
    
    return mask.astype(np.float32)


@dataclass
class CloudLayer:
    """
    Manages the cloud mask lifecycle: generation, caching, time evolution.
    Handles dynamic render_size changes.
    
    Usage in AllSkyRenderer:
        cloud = CloudLayer(seed=42)
        
        # Every render call (render_size may change between calls):
        cloud.update(transparency=atm_state.transparency, 
                     sim_time_s=elapsed_s,
                     current_size=field.shape[0])
        mask = cloud.mask   # (current_size, current_size) float32
    """
    seed:             int   = 42
    
    # Internal state
    _mask:            Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _last_update_s:   float = field(default=-999.0, init=False)
    _last_coverage:   float = field(default=0.0,    init=False)
    _last_size:       int   = field(default=0,      init=False)
    
    def update(self, transparency: float, sim_time_s: float, current_size: int) -> None:
        """
        Recompute the cloud mask if:
        - Enough simulated time has elapsed
        - Coverage changed significantly
        - Render size changed (screen_imaging.py changes it dynamically)
        """
        coverage = _coverage_from_transparency(transparency)
        
        time_delta    = abs(sim_time_s - self._last_update_s)
        coverage_jump = abs(coverage   - self._last_coverage)
        size_changed  = (current_size != self._last_size)
        
        if (time_delta >= CLOUD_UPDATE_INTERVAL_S or
                coverage_jump > 0.05 or
                size_changed or
                self._mask is None):
            self._mask = generate_cloud_mask(
                current_size, coverage, sim_time_s, self.seed)
            self._last_update_s = sim_time_s
            self._last_coverage = coverage
            self._last_size     = current_size
    
    @property
    def mask(self) -> np.ndarray:
        """Current cloud mask. Call update() before reading."""
        if self._mask is None:
            # Fallback: return empty mask with a default size
            return np.zeros((512, 512), dtype=np.float32)
        return self._mask
    
    @property
    def coverage(self) -> float:
        """Current cloud coverage fraction 0–1."""
        return self._last_coverage
