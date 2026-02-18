# Sprint 14b — Cloud Layer Procedurale

**Prerequisito:** Sprint 14a completato.
`AtmosphericState.transparency` e `WeatherSystem` devono essere già operativi.

**Goal:** Rendere le nuvole visibili nell'allsky come overlay procedurale
che si muove e varia nel tempo, occulta stelle e pianeti, e si correla con
`transparency` del WeatherSystem.

**Files created:**
- `atmosphere/cloud_layer.py` (NEW)

**Files modified:**
- `imaging/allsky_renderer.py` — draw cloud overlay after stars
- `atmosphere/__init__.py`

**Files NOT modified (protected):**
- `ui_new/screen_imaging.py`
- `universe/orbital_body.py`, `universe/planet_physics.py`, `universe/minor_bodies.py`
- `atmosphere/atmospheric_model.py` — solo lettura di transparency già presente

---

## Architecture

```
WeatherSystem.transparency(jd)
    │  drives cloud coverage fraction
    ▼
CloudLayer  (atmosphere/cloud_layer.py)
    │  generates a (S, S) float32 mask: 0=clear, 1=opaque cloud
    │  mask is computed from layered noise + time offset (clouds move)
    │  mask is cached and recomputed every CLOUD_UPDATE_INTERVAL seconds
    ▼
AllSkyRenderer.render()
    │  receives cloud_mask from CloudLayer
    │  composites cloud overlay on top of rendered field
    │  stars already rendered: cloud mask attenuates them retroactively
    ▼
AllSkyScreen (screen_imaging.py, allsky live view)
    │  NO CHANGE to screen code
    │  cloud_layer instance lives in AllSkyRenderer or in screen_imaging._cloud_layer
```

---

## Task 1 — Create `atmosphere/cloud_layer.py`

Pure numpy/math module. No pygame, no game imports.

```python
"""
CloudLayer — procedural cloud mask for allsky rendering.

Generates a 2D float32 array on the allsky disk coordinate system
(same as AllSkyRenderer: (S, S) image, zenithal equidistant projection).

The mask values range from 0.0 (clear sky) to 1.0 (opaque cloud).
It is driven by:
  - coverage: fraction of sky covered (0.0–1.0), derived from transparency
  - time_s: elapsed real/simulated seconds (drives cloud motion)

Algorithm:
  Two layers of 2D sine noise (different spatial frequencies and drift speeds)
  are combined and thresholded at a coverage-dependent value.
  No scipy/scikit required — pure numpy sin/cos operations.
"""

from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# How often to recompute the cloud mask (simulated seconds)
# Lower = smoother motion but more CPU. 2s matches the allsky render interval.
CLOUD_UPDATE_INTERVAL_S: float = 2.0

# Cloud drift speed (pixels per simulated second at 512px render size)
# At time_factor=1 (real time), clouds cross the allsky in ~8 minutes
DRIFT_SPEED_PX_PER_S: float = 0.18


def _coverage_from_transparency(transparency: float) -> float:
    """
    Map transparency (0=cloudy, 1=clear) to cloud coverage fraction.
    
    Non-linear: transparency > 0.85 → coverage < 0.05 (almost no clouds)
                transparency < 0.15 → coverage > 0.90 (nearly overcast)
    """
    # Inverted and curved
    t = max(0.0, min(1.0, transparency))
    coverage = (1.0 - t) ** 1.4   # power curve: slow start, fast at low transparency
    return float(coverage)


def generate_cloud_mask(size: int,
                        coverage: float,
                        time_s: float,
                        seed: int = 42) -> np.ndarray:
    """
    Generate a (size, size) float32 cloud opacity mask.
    
    mask[y, x] = 0.0 → clear sky at this pixel
    mask[y, x] = 1.0 → fully opaque cloud
    
    The mask is non-zero only inside the allsky circle (radius = size/2).
    
    Args:
        size:     image size in pixels (same as render_size)
        coverage: fraction of sky covered 0.0–1.0
        time_s:   elapsed time in seconds (drives drift)
        seed:     noise seed (consistent per WeatherSystem seed)
    
    Returns:
        (size, size) float32 array
    """
    if coverage < 0.02:
        return np.zeros((size, size), dtype=np.float32)
    
    H = W = size
    cx = cy = size * 0.5
    
    # Coordinate grids (normalized −1 to +1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xn = (xx - cx) / cx   # −1..+1
    yn = (yy - cy) / cy
    
    # Inside circle mask
    r_norm = np.sqrt(xn**2 + yn**2)
    inside = (r_norm <= 1.0).astype(np.float32)
    
    # Cloud drift offset (two layers drift at different speeds and directions)
    seed_f = float(seed)
    
    # Layer 1: large-scale cloud structures (low frequency)
    freq1  = 2.8
    drift1_x = DRIFT_SPEED_PX_PER_S * time_s / cx * math.cos(seed_f * 0.7)
    drift1_y = DRIFT_SPEED_PX_PER_S * time_s / cy * math.sin(seed_f * 0.7)
    n1 = (np.sin((xn + drift1_x) * freq1 + seed_f * 1.3) *
          np.cos((yn + drift1_y) * freq1 + seed_f * 0.9))
    
    # Layer 2: medium-scale structures (higher frequency, orthogonal drift)
    freq2  = 5.5
    drift2_x = DRIFT_SPEED_PX_PER_S * 0.6 * time_s / cx * math.cos(seed_f * 1.4 + 1.2)
    drift2_y = DRIFT_SPEED_PX_PER_S * 0.6 * time_s / cy * math.sin(seed_f * 1.4 + 1.2)
    n2 = (np.sin((xn + drift2_x) * freq2 + seed_f * 2.1) *
          np.cos((yn + drift2_y) * freq2 + seed_f * 1.7)) * 0.5
    
    # Layer 3: fine texture
    freq3  = 11.0
    drift3_x = DRIFT_SPEED_PX_PER_S * 0.3 * time_s / cx * math.cos(seed_f * 2.3 + 0.8)
    n3 = np.sin((xn + drift3_x) * freq3 + seed_f * 3.7) * 0.25
    
    # Combine layers → noise field in range roughly −1.75..+1.75
    noise = n1 + n2 + n3
    
    # Normalize to 0..1
    noise_min = float(noise.min())
    noise_max = float(noise.max())
    noise_range = max(noise_max - noise_min, 1e-6)
    noise_norm = (noise - noise_min) / noise_range
    
    # Threshold: coverage=0.5 means ~50% of sky covered
    # threshold such that fraction above it = coverage
    threshold = 1.0 - coverage
    threshold = max(0.0, min(0.99, threshold))
    
    # Soft edge: ramp instead of hard step (clouds have fuzzy edges)
    edge_width = 0.12   # fraction of noise range for soft transition
    mask = np.clip((noise_norm - threshold) / edge_width, 0.0, 1.0)
    
    # Apply inside-circle mask
    mask = mask * inside
    
    return mask.astype(np.float32)


@dataclass
class CloudLayer:
    """
    Manages the cloud mask lifecycle: generation, caching, time evolution.
    
    Usage in AllSkyRenderer:
        cloud = CloudLayer(seed=42)
        
        # Every render call:
        cloud.update(transparency=atm_state.transparency, sim_time_s=elapsed_s)
        mask = cloud.mask   # (S, S) float32, ready to composite
    """
    seed:             int   = 42
    render_size:      int   = 512
    
    # Internal state
    _mask:            Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _last_update_s:   float = field(default=-999.0, init=False)
    _last_coverage:   float = field(default=0.0,    init=False)
    
    def update(self, transparency: float, sim_time_s: float) -> None:
        """
        Recompute the cloud mask if enough simulated time has elapsed
        or if coverage changed significantly.
        """
        coverage = _coverage_from_transparency(transparency)
        
        time_delta    = abs(sim_time_s - self._last_update_s)
        coverage_jump = abs(coverage   - self._last_coverage)
        
        if (time_delta >= CLOUD_UPDATE_INTERVAL_S or
                coverage_jump > 0.05 or
                self._mask is None):
            self._mask = generate_cloud_mask(
                self.render_size, coverage, sim_time_s, self.seed)
            self._last_update_s = sim_time_s
            self._last_coverage = coverage
    
    @property
    def mask(self) -> np.ndarray:
        """Current cloud mask. Call update() before reading."""
        if self._mask is None:
            return np.zeros((self.render_size, self.render_size), dtype=np.float32)
        return self._mask
    
    @property
    def coverage(self) -> float:
        """Current cloud coverage fraction 0–1."""
        return self._last_coverage
```

---

## Task 2 — Add `CloudLayer` to `AllSkyRenderer`

**File:** `imaging/allsky_renderer.py`

### 2a — Import and instantiate

```python
# ADD import at top of allsky_renderer.py:
from atmosphere.cloud_layer import CloudLayer

# ADD in AllSkyRenderer.__init__, after self._psf5 = ...:
self._cloud = CloudLayer(seed=42, render_size=render_size)
self._sim_time_s: float = 0.0   # accumulated simulated time
```

### 2b — Update cloud layer in `render()`

```python
# In AllSkyRenderer.render(), at the very beginning, BEFORE building background:

# Accumulate simulated time (exposure_s is simulated time per render call)
self._sim_time_s += exposure_s

# Update cloud mask
transparency = getattr(atm_state, 'transparency', 1.0) if atm_state else 1.0
self._cloud.update(transparency=transparency, sim_time_s=self._sim_time_s)
```

### 2c — Composite cloud overlay AFTER all stars and bodies are rendered

```python
# In AllSkyRenderer.render(), AFTER the solar_bodies rendering loop,
# BEFORE the final return:

if self._cloud.coverage > 0.01:
    _apply_cloud_overlay(field, self._cloud.mask)

return field
```

### 2d — Add `_apply_cloud_overlay` function (module-level)

```python
def _apply_cloud_overlay(field: np.ndarray, cloud_mask: np.ndarray) -> None:
    """
    Composite cloud mask onto the rendered field in-place.
    
    Cloud appearance:
    - Opaque cloud (mask=1.0): replaces field with a grey-white cloud colour
    - Thin cloud (mask=0.5):   blends 50% field + 50% cloud colour
    - Clear (mask=0.0):        field unchanged
    
    Cloud colour: faint grey, slightly warm (scattered city light).
    At night: dark grey (clouds absorb sky glow and re-emit dimly).
    During day: bright white/grey.
    
    Implementation:
        cloud_rgb is uniform grey: (cloud_r, cloud_g, cloud_b)
        field[..., c] = field[..., c] * (1 - mask) + cloud_c * mask
    
    Args:
        field:      (H, W, 3) float32 in-place
        cloud_mask: (H, W) float32, 0=clear, 1=opaque
    """
    # Cloud colour (photon units, similar to a faint background)
    # Keep it very dark at night — clouds don't glow brightly
    cloud_r = 8.0
    cloud_g = 9.0
    cloud_b = 10.0   # slightly blue-grey

    mask3 = cloud_mask[:, :, np.newaxis]   # broadcast across RGB

    field[:, :, 0] = field[:, :, 0] * (1.0 - cloud_mask) + cloud_r * cloud_mask
    field[:, :, 1] = field[:, :, 1] * (1.0 - cloud_mask) + cloud_g * cloud_mask
    field[:, :, 2] = field[:, :, 2] * (1.0 - cloud_mask) + cloud_b * cloud_mask
```

---

## Task 3 — Update `atmosphere/__init__.py`

```python
# ADD to imports:
from .cloud_layer import CloudLayer, generate_cloud_mask

# ADD to __all__:
"CloudLayer",
"generate_cloud_mask",
```

---

## Task 4 — Sky chart: cloud overlay (optional, low priority)

The sky chart (`screen_skychart.py`) renders stars with pygame, not numpy.
A proper cloud overlay here is a Sprint 15 task (VFX layer).

For 14b, add only a simple visual hint: if `transparency < 0.4`, draw
a semi-transparent grey rect over the sky chart surface.

```python
# In SkychartScreen.render(), AFTER _draw_planets, BEFORE Earth horizon:
if hasattr(self, '_weather'):
    transp = self._weather.transparency(self._tc.jd)
    if transp < 0.85:
        cloud_alpha = int((1.0 - transp) * 120)   # max alpha=120 (not fully opaque)
        cloud_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        cloud_surf.fill((40, 40, 50, cloud_alpha))
        surface.blit(cloud_surf, (0, 0))
```

For this to work, `SkychartScreen` needs a `WeatherSystem` instance.
Add it in `__init__`:

```python
# In SkychartScreen.__init__, after self._earth = EarthRenderer():
from atmosphere.weather import WeatherSystem
self._weather = WeatherSystem(base_seeing=2.5, seed=42)
```

⚠️ The seed must match the one in `AtmosphericModel` and `ObservatoryScreen`
so all screens see the same weather. Hardcode seed=42 everywhere for now;
Sprint 17 (Career Mode) will centralise it in `GameState`.

---

## Task 5 — Visual tuning guide

After implementation, the cloud appearance needs tuning. Key parameters:

| Parameter | Location | Effect |
|---|---|---|
| `cloud_r/g/b` in `_apply_cloud_overlay` | `allsky_renderer.py` | Cloud brightness — raise if too dark |
| `edge_width = 0.12` | `cloud_layer.py` | Cloud edge softness — raise for wispier clouds |
| `freq1 = 2.8` | `cloud_layer.py` | Large cloud scale — lower for bigger patches |
| `freq2 = 5.5` | `cloud_layer.py` | Medium cloud scale |
| `DRIFT_SPEED_PX_PER_S = 0.18` | `cloud_layer.py` | Cloud motion speed |
| `cloud_alpha = int((1-t)*120)` | `screen_skychart.py` | Sky chart dimming intensity |

**Target appearance at `transparency=0.50`:**
- ~30–40% of allsky disk covered by irregular grey patches
- Stars behind clouds invisible, stars in gaps bright
- Cloud edges soft (no hard geometry)
- Clouds visibly move between allsky renders (2s interval)

---

## Acceptance Criteria

1. With `transparency=1.0`: cloud mask is all zeros, allsky unchanged.
2. With `transparency=0.05`: most of allsky is grey, few stars visible.
3. With `transparency=0.50`: ~35–45% cloud coverage, irregular patterns.
4. Cloud patches move between frames (position changes with `sim_time_s`).
5. Sky chart shows dimming overlay when `transparency < 0.85`.
6. No performance regression: `generate_cloud_mask(512, ...)` < 5ms.
7. Deterministic: same `transparency`, `time_s`, `seed` → same mask.

---

## Performance Note

`generate_cloud_mask(512, ...)` runs in ~1–3ms on modern CPUs (pure numpy).
It is recomputed only every `CLOUD_UPDATE_INTERVAL_S = 2.0` simulated seconds,
so at normal game speed (real-time) it triggers at most once every 2 real seconds.
At time acceleration (×3600 = 1 hour/second), it triggers every frame but the
clouds will visibly streak across the sky — which is the correct physical behavior.

If performance is an issue at high time acceleration, add:
```python
# In CloudLayer.update():
if time_factor > 100:
    self._sim_time_s += time_delta * 0.01  # slow down cloud motion at high accel
```

---

## Files Modified Summary

| File | Change |
|---|---|
| `atmosphere/cloud_layer.py` | NEW — CloudLayer + generate_cloud_mask |
| `imaging/allsky_renderer.py` | Add CloudLayer, _apply_cloud_overlay, wire in render() |
| `atmosphere/__init__.py` | Export CloudLayer, generate_cloud_mask |
| `ui_new/screen_skychart.py` | Add WeatherSystem, semi-transparent cloud overlay |
