# Sprint 14b — Cloud Layer Procedurale (REVISED)

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
- `ui_new/screen_skychart.py` — NO cloud overlay (it's a pointing tool, not a realistic view)
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
    │  mask is computed from layered sin/cos noise + time offset (clouds move)
    │  mask is cached and recomputed every CLOUD_UPDATE_INTERVAL seconds
    │  adapts dynamically to render_size changes (screen_imaging changes it at runtime)
    ▼
AllSkyRenderer.render()
    │  receives cloud_mask from CloudLayer
    │  composites cloud overlay on top of rendered field
    │  stars already rendered: cloud mask attenuates them retroactively
    ▼
AllSkyScreen (screen_imaging.py, allsky live view)
    │  NO CHANGE to screen code
    │  cloud_layer instance lives in AllSkyRenderer
```

**IMPORTANT:** Cloud overlay is ONLY in allsky live view. Sky chart remains a clean
pointing tool with NO cloud overlay — it's an atlas/planetarium, not a camera view.

---

## Task 1 — Create `atmosphere/cloud_layer.py`

Pure numpy/math module. No pygame, no game imports.

### Key implementation details

**Dynamic size handling:**
`screen_imaging.py` changes `AllSkyRenderer.render_size` dynamically at runtime
(from 512 to 560+ depending on window size). CloudLayer must regenerate mask
when size changes.

```python
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
    
    Args:
        size:     image size in pixels (can change between calls)
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
    xn = (xx - cx) / cx
    yn = (yy - cy) / cy
    
    # Inside circle mask
    r_norm = np.sqrt(xn**2 + yn**2)
    inside = (r_norm <= 1.0).astype(np.float32)
    
    # Cloud drift offset
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
```

---

## Task 2 — Add `CloudLayer` to `AllSkyRenderer`

**File:** `imaging/allsky_renderer.py`

### 2a — Import and instantiate

```python
# ADD import at top of allsky_renderer.py:
from atmosphere.cloud_layer import CloudLayer

# ADD in AllSkyRenderer.__init__, after existing initialization:
self._cloud = CloudLayer(seed=42)
self._sim_time_s = 0.0
```

**CRITICAL:** Do NOT pass `render_size` to CloudLayer — it adapts dynamically.

### 2b — Update cloud layer in `render()`

```python
# In AllSkyRenderer.render(), AFTER field = build_allsky_background(...):

# Update cloud mask (AFTER field exists so we can use field.shape[0])
self._sim_time_s += exposure_s
transparency = getattr(atm_state, 'transparency', 1.0) if atm_state else 1.0
current_size = field.shape[0]  # Get actual render size from field
self._cloud.update(transparency=transparency, 
                   sim_time_s=self._sim_time_s,
                   current_size=current_size)
```

**CRITICAL PLACEMENT:** This MUST be AFTER `field = build_allsky_background(...)`.
If you call it before field exists, you'll get "cannot access local variable 'field'".

### 2c — Composite cloud overlay AFTER all stars and bodies are rendered

```python
# In AllSkyRenderer.render(), AFTER the solar_bodies rendering loop,
# BEFORE the final return:

if self._cloud.coverage > 0.01:
    _apply_cloud_overlay(field, self._cloud.mask)

return field
```

### 2d — Add `_apply_cloud_overlay` function (module-level, top of file)

```python
def _apply_cloud_overlay(field: np.ndarray, cloud_mask: np.ndarray) -> None:
    """
    Composite cloud mask onto the rendered field in-place.
    
    Cloud appearance:
    - Opaque cloud (mask=1.0): replaces field with a grey-white cloud colour
    - Thin cloud (mask=0.5):   blends 50% field + 50% cloud colour
    - Clear (mask=0.0):        field unchanged
    
    Args:
        field:      (H, W, 3) float32 in-place
        cloud_mask: (H, W) float32, 0=clear, 1=opaque
    """
    # Cloud colour (photon units, similar to a faint background)
    # Keep it very dark at night — clouds don't glow brightly
    cloud_r = 8.0
    cloud_g = 9.0
    cloud_b = 10.0   # slightly blue-grey

    # Vectorized operation (NO LOOPS)
    mask_inv = 1.0 - cloud_mask
    field[:, :, 0] = field[:, :, 0] * mask_inv + cloud_r * cloud_mask
    field[:, :, 1] = field[:, :, 1] * mask_inv + cloud_g * cloud_mask
    field[:, :, 2] = field[:, :, 2] * mask_inv + cloud_b * cloud_mask
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

## Task 4 — Visual tuning guide (REVISED)

After implementation, the cloud appearance needs tuning. Key parameters:

| Parameter | Location | Effect | Suggested values |
|---|---|---|---|
| `cloud_r/g/b` in `_apply_cloud_overlay` | `allsky_renderer.py` | Cloud brightness | Try 40/45/50 (day), 15/18/20 (night) |
| `edge_width = 0.12` | `cloud_layer.py` | Cloud edge softness | Try 0.25–0.35 for softer clouds |
| `freq1 = 2.8` | `cloud_layer.py` | Large cloud scale | Try 2.0–2.2 for bigger patches |
| `freq2 = 5.5` | `cloud_layer.py` | Medium cloud scale | Try 4.0–4.5 |
| `DRIFT_SPEED_PX_PER_S = 0.18` | `cloud_layer.py` | Cloud motion speed | Try 0.5 for faster visible motion |

**Target appearance at `transparency=0.50`:**
- ~30–40% of allsky disk covered by irregular grey patches
- Stars behind clouds invisible, stars in gaps bright
- Cloud edges soft (no hard geometry)
- Clouds visibly move between allsky renders (at ×60 acceleration)

**Breaking pattern repetition:**
If clouds look too geometric/"appiccicate", add a 4th noise layer:

```python
# In generate_cloud_mask(), after n3:
freq4 = 18.0
n4 = np.sin(xn * freq4 + seed_f * 4.9) * np.cos(yn * freq4 + seed_f * 3.2) * 0.15
noise = n1 + n2 + n3 + n4  # ← add n4
```

---

## Task 5 — Sky Chart: NO CLOUD OVERLAY

**IMPORTANT:** Do NOT add cloud overlay to `screen_skychart.py`.

The sky chart is a pointing/navigation tool (like Cartes du Ciel, SkySafari, or
Dwarf Lab atlas). It must remain clean and usable as a mount goto reference.

Clouds are only rendered in the allsky live camera view (`screen_imaging.py`),
which shows the physical sky as the camera sees it.

If you want weather indication in the sky chart, add a small widget in the corner
(like `screen_observatory.py` weather panel) that shows:
- Condition icon (★ clear, ◒ cloudy)
- Transparency %
- Seeing "

But NO dimming overlay on the stars — that would make the tool unusable.

---

## Acceptance Criteria

1. With `transparency=1.0`: cloud mask is all zeros, allsky unchanged.
2. With `transparency=0.05`: most of allsky is grey, few stars visible.
3. With `transparency=0.50`: ~35–45% cloud coverage, irregular patterns.
4. Cloud patches move between frames (position changes with `sim_time_s`).
5. **Sky chart has NO cloud overlay** — remains a clean pointing tool.
6. No performance regression: `generate_cloud_mask(560, ...)` < 5ms.
7. Deterministic: same `transparency`, `time_s`, `seed` → same mask.
8. Dynamic size: render_size changes from 512 to 560+ → no crashes.

---

## Performance Note

`generate_cloud_mask(560, ...)` runs in ~1–4ms on modern CPUs (pure numpy).
It is recomputed only when:
- `CLOUD_UPDATE_INTERVAL_S = 2.0` simulated seconds have passed
- Coverage changes by >5%
- Render size changes

At normal game speed (real-time) it triggers at most once every 2 real seconds.
At time acceleration (×3600 = 1 hour/second), it triggers every frame but the
clouds will visibly streak across the sky — which is correct physical behavior.

---

## Common Pitfalls (from implementation experience)

### 1. Calling cloud.update() before field exists
**Error:** `cannot access local variable 'field'`
**Fix:** Move `cloud.update()` AFTER `field = build_allsky_background(...)`

### 2. Passing render_size to CloudLayer.__init__
**Error:** `CloudLayer.__init__() got an unexpected keyword argument 'render_size'`
**Fix:** `CloudLayer(seed=42)` with NO other parameters. Size is passed in update().

### 3. Missing current_size parameter
**Error:** `CloudLayer.update() missing 1 required positional argument: 'current_size'`
**Fix:** Always call with 3 parameters:
```python
cloud.update(transparency=..., sim_time_s=..., current_size=field.shape[0])
```

### 4. Broadcast shape mismatch
**Error:** `operands could not be broadcast together with shapes (560,560) (512,512)`
**Fix:** Make sure CloudLayer regenerates mask when size changes — it should check
`current_size != self._last_size` in update().

### 5. Using pixel-by-pixel loop in _apply_cloud_overlay
**Symptom:** Freeze at time acceleration ×10 or higher
**Fix:** Use vectorized numpy operations (see Task 2d). NO for loops.

---

## Files Modified Summary

| File | Change |
|---|---|
| `atmosphere/cloud_layer.py` | NEW — CloudLayer + generate_cloud_mask with dynamic size |
| `imaging/allsky_renderer.py` | Add CloudLayer, _apply_cloud_overlay, wire in render() |
| `atmosphere/__init__.py` | Export CloudLayer, generate_cloud_mask |
| `ui_new/screen_skychart.py` | NO CHANGES — remains a clean pointing tool |
