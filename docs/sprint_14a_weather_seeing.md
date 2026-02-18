# Sprint 14a — WeatherSystem + Smooth Seeing + Transparency

**Goal:** Replace the discrete 5-minute seeing jumps with a smooth continuous
model, add a `WeatherSystem` that drives sky transparency and seeing over the
course of a night, and wire both into the existing rendering pipeline with
minimal changes to working code.

**Files created:**
- `atmosphere/weather.py` (NEW)

**Files modified:**
- `atmosphere/atmospheric_model.py`
- `atmosphere/day_phase.py` (no change expected)
- `atmosphere/__init__.py`
- `game/state_manager.py`
- `ui_new/screen_observatory.py`

**Files NOT modified (protected):**
- `ui_new/screen_imaging.py` — contains manual _expose() bugfix
- `imaging/allsky_renderer.py` — only add optional `transparency` param
- `universe/orbital_body.py`, `universe/planet_physics.py`, `universe/minor_bodies.py`

---

## Architecture overview

```
WeatherSystem  (atmosphere/weather.py)
    │  generates per-night conditions: NightWeather
    │  NightWeather has: condition, seeing curve, transparency curve
    │
    ▼
AtmosphericModel.compute()  (atmospheric_model.py)
    │  reads WeatherSystem.current_seeing(jd)
    │  reads WeatherSystem.current_transparency(jd)
    │
    ▼
AtmosphericState
    │  new fields: transparency (0.0–1.0), weather_condition str
    │
    ▼
AllSkyRenderer.render()  (allsky_renderer.py)
    │  multiplies star flux by transparency
    │  multiplies sky_bg by transparency (partial clouds dim sky)
    │
    ▼
screen_observatory.py
    │  draws weather widget: condition icon + seeing gauge + transparency bar
    ▼
screen_imaging.py  HUD (NO CHANGE — reads atm_state.seeing_fwhm_arcsec as before)
```

---

## Task 1 — Create `atmosphere/weather.py`

This is the only new file in 14a. It must be fully self-contained (no imports
from ui or game modules).

### WeatherCondition enum

```python
from enum import Enum

class WeatherCondition(Enum):
    CLEAR         = "clear"          # transparency 0.90–1.00, seeing 1.0–2.5"
    MOSTLY_CLEAR  = "mostly_clear"   # transparency 0.70–0.90, seeing 1.5–3.5"
    PARTLY_CLOUDY = "partly_cloudy"  # transparency 0.40–0.70, seeing 2.0–4.5"
    CLOUDY        = "cloudy"         # transparency 0.10–0.40, seeing 3.0–6.0"
    OVERCAST      = "overcast"       # transparency 0.00–0.10, imaging impossible
```

### NightWeather dataclass

```python
@dataclass
class NightWeather:
    """
    Pre-generated weather profile for a single astronomical night.
    
    All curves are sampled at SAMPLE_INTERVAL_MIN intervals starting from
    local midnight (JD floor + 0.5). Values are interpolated between samples.
    """
    condition:     WeatherCondition
    jd_midnight:   float          # JD of local midnight for this night
    
    # Sampled curves — list of (transparency, seeing_arcsec) tuples
    # One sample every SAMPLE_INTERVAL_MIN minutes, covering 24 hours
    samples:       list           # list of (transp: float, seeing: float)
    
    SAMPLE_INTERVAL_MIN: ClassVar[int] = 10   # sample every 10 minutes
    N_SAMPLES:           ClassVar[int] = 144  # 24h / 10min
```

### WeatherSystem class

```python
class WeatherSystem:
    """
    Generates and caches nightly weather profiles.
    
    Usage pattern (same as AtmosphericModel):
        ws = WeatherSystem(base_seeing=2.5, seed=42)
        # Every frame:
        transp = ws.transparency(jd)    # 0.0–1.0
        seeing = ws.seeing(jd)          # arcsec FWHM, smooth
        cond   = ws.condition(jd)       # WeatherCondition
    """
    
    # Markov transition matrix: probability of moving to next condition
    # Rows = current, Cols = next: [CLEAR, MOSTLY_CLEAR, PARTLY_CLOUDY, CLOUDY, OVERCAST]
    # North Italy summer-ish probabilities per night
    _TRANSITION = [
        [0.70, 0.20, 0.07, 0.02, 0.01],  # from CLEAR
        [0.20, 0.50, 0.22, 0.06, 0.02],  # from MOSTLY_CLEAR
        [0.10, 0.25, 0.40, 0.20, 0.05],  # from PARTLY_CLOUDY
        [0.05, 0.10, 0.25, 0.45, 0.15],  # from CLOUDY
        [0.02, 0.05, 0.15, 0.30, 0.48],  # from OVERCAST
    ]
    
    def __init__(self, base_seeing: float = 2.5, seed: int = 42):
        self.base_seeing = base_seeing
        self.seed        = seed
        self._cache: dict[int, NightWeather] = {}   # jd_night_int → NightWeather
    
    def _night_key(self, jd: float) -> int:
        """Integer key for the astronomical night containing JD."""
        # Astronomical night: JD.5 to JD+1.5 → key = floor(jd - 0.5)
        return int(jd - 0.5)
    
    def _get_or_generate(self, jd: float) -> NightWeather:
        """Return cached NightWeather or generate a new one."""
        key = self._night_key(jd)
        if key not in self._cache:
            self._cache[key] = self._generate_night(key)
            # Evict old nights (keep only last 3) to avoid memory growth
            if len(self._cache) > 3:
                oldest = min(self._cache.keys())
                del self._cache[oldest]
        return self._cache[key]
    
    def _generate_night(self, night_key: int) -> NightWeather:
        """
        Generate a full NightWeather for night_key.
        
        Algorithm:
        1. Use Markov chain seeded by (self.seed + night_key) to pick condition
           for this night (condition persists for the whole night but varies
           within it via the seeing/transparency curves).
        2. Generate N_SAMPLES points using Perlin-like noise:
           - Low-frequency component (period ~2h): overall night trend
           - High-frequency component (period ~20min): Kolmogorov turbulence
        3. Map noise to (transparency, seeing) ranges for the condition.
        """
        import random
        import math
        
        rng = random.Random(self.seed + night_key * 1000)
        
        # Pick condition via Markov (previous night's condition → this night)
        prev_key = night_key - 1
        if prev_key in self._cache:
            prev_cond_idx = list(WeatherCondition).index(
                self._cache[prev_key].condition)
        else:
            # Cold start: seed-based initial condition
            prev_cond_idx = rng.choices(range(5), weights=[35,30,20,10,5])[0]
        
        weights = WeatherSystem._TRANSITION[prev_cond_idx]
        cond_idx = rng.choices(range(5), weights=weights)[0]
        condition = list(WeatherCondition)[cond_idx]
        
        # Transparency and seeing ranges per condition
        RANGES = {
            WeatherCondition.CLEAR:         (0.88, 1.00, 1.0, 2.5),
            WeatherCondition.MOSTLY_CLEAR:  (0.68, 0.90, 1.5, 3.5),
            WeatherCondition.PARTLY_CLOUDY: (0.38, 0.70, 2.0, 4.5),
            WeatherCondition.CLOUDY:        (0.08, 0.40, 3.0, 6.0),
            WeatherCondition.OVERCAST:      (0.00, 0.12, 4.0, 8.0),
        }
        t_min, t_max, s_min, s_max = RANGES[condition]
        
        N = NightWeather.N_SAMPLES
        samples = []
        
        # Generate two noise layers for transparency
        # Low freq: sin/cos with random phase, period ~12 samples (2h)
        lf_amp   = (t_max - t_min) * 0.35
        lf_phase = rng.uniform(0, 2 * math.pi)
        lf_freq  = rng.uniform(0.04, 0.08)   # cycles per sample
        
        # High freq: faster variation, period ~2–3 samples
        hf_amp   = (t_max - t_min) * 0.12
        hf_phases = [rng.uniform(0, 2 * math.pi) for _ in range(N)]
        
        # Base level within the range
        base_t = rng.uniform(t_min + lf_amp, t_max - lf_amp)
        base_s = rng.uniform(s_min, (s_min + s_max) / 2)
        
        for i in range(N):
            # Transparency
            lf = lf_amp * math.sin(lf_freq * i * 2 * math.pi + lf_phase)
            hf = hf_amp * math.sin(hf_phases[i % len(hf_phases)])
            t  = max(t_min, min(t_max, base_t + lf + hf))
            
            # Seeing: inversely correlated with transparency (clouds = worse seeing)
            # + independent Kolmogorov variation
            seeing_base = s_min + (1.0 - (t - t_min) / max(t_max - t_min, 0.01)) * (s_max - s_min)
            kolm = rng.lognormvariate(0, 0.18)  # lognormal ~±20%
            s = max(s_min * 0.8, min(s_max * 1.2, seeing_base * kolm))
            
            samples.append((float(t), float(s)))
        
        return NightWeather(
            condition    = condition,
            jd_midnight  = night_key + 0.5,
            samples      = samples,
        )
    
    def _interpolate(self, jd: float) -> tuple[float, float]:
        """
        Interpolate (transparency, seeing) for exact JD.
        Returns (transparency: float, seeing_arcsec: float).
        """
        night = self._get_or_generate(jd)
        
        # Offset from midnight in minutes
        minutes = (jd - night.jd_midnight) * 24.0 * 60.0
        minutes = minutes % (24.0 * 60.0)  # wrap to 0–1440
        
        N    = NightWeather.N_SAMPLES
        step = NightWeather.SAMPLE_INTERVAL_MIN
        
        # Linear interpolation between surrounding samples
        i0   = int(minutes / step) % N
        i1   = (i0 + 1) % N
        frac = (minutes % step) / step
        
        t  = night.samples[i0][0] * (1 - frac) + night.samples[i1][0] * frac
        s  = night.samples[i0][1] * (1 - frac) + night.samples[i1][1] * frac
        return float(t), float(s)
    
    def transparency(self, jd: float) -> float:
        """Sky transparency 0.0 (opaque) → 1.0 (perfect). Thread-safe read."""
        return self._interpolate(jd)[0]
    
    def seeing(self, jd: float) -> float:
        """Instantaneous seeing FWHM in arcseconds. Smooth, no 5-min jumps."""
        return self._interpolate(jd)[1]
    
    def condition(self, jd: float) -> WeatherCondition:
        """Overall weather condition for the night containing JD."""
        return self._get_or_generate(jd).condition
    
    def night_summary(self, jd: float) -> dict:
        """
        Return a summary dict for UI display.
        Keys: condition (str), avg_transparency (float), avg_seeing (float),
              min_transparency (float), max_seeing (float)
        """
        night = self._get_or_generate(jd)
        transp_vals = [s[0] for s in night.samples]
        seeing_vals = [s[1] for s in night.samples]
        return {
            "condition":        night.condition.value,
            "avg_transparency": sum(transp_vals) / len(transp_vals),
            "avg_seeing":       sum(seeing_vals) / len(seeing_vals),
            "min_transparency": min(transp_vals),
            "max_seeing":       max(seeing_vals),
        }
```

---

## Task 2 — Add `WeatherSystem` to `AtmosphericModel`

**File:** `atmosphere/atmospheric_model.py`

### 2a — Add `transparency` and `weather_condition` to `AtmosphericState`

Add two fields to the `AtmosphericState` dataclass after `extinction_zenith_v`:

```python
# NEW fields in AtmosphericState (after extinction_zenith_v):
transparency:        float = 1.0   # 0.0 = fully clouded, 1.0 = perfect
weather_condition:   str   = "clear"  # WeatherCondition.value string
```

### 2b — Add `WeatherSystem` to `AtmosphericModel.__init__`

```python
# In AtmosphericModel.__init__, after self._seeing_seed = 42:
from atmosphere.weather import WeatherSystem
self._weather = WeatherSystem(
    base_seeing = self.observer.base_seeing_arcsec,
    seed        = 42,
)
```

### 2c — Replace `seeing_fwhm_arcsec()` call in `AtmosphericModel.compute()`

Replace the current seeing calculation block:
```python
# REMOVE this block:
elapsed_s = (dt - datetime(2000,1,1,tzinfo=timezone.utc)).total_seconds()
fwhm = seeing_fwhm_arcsec(
    self.observer.base_seeing_arcsec,
    time_s = elapsed_s,
    seed   = self._seeing_seed,
)

# REPLACE WITH:
fwhm         = self._weather.seeing(jd)
transparency = self._weather.transparency(jd)
weather_cond = self._weather.condition(jd).value
```

### 2d — Add new fields to the returned `AtmosphericState`

```python
# In the AtmosphericState(...) constructor call at the end of compute(),
# add the two new fields:
return AtmosphericState(
    ...  # all existing fields unchanged
    extinction_zenith_v  = ext_z,
    transparency         = transparency,   # NEW
    weather_condition    = weather_cond,   # NEW
)
```

---

## Task 3 — Wire transparency into `AllSkyRenderer`

**File:** `imaging/allsky_renderer.py`

This is the most important rendering change. Transparency multiplies star flux
and dims the sky background (partial cloud coverage).

### 3a — In `_render_stars`, multiply photon count by transparency

```python
# In _render_stars(), AFTER computing photons, BEFORE the < 0.3 check:
transparency = getattr(atm_state, 'transparency', 1.0)  # safe default
photons *= transparency

if photons < 0.3:
    continue
```

### 3b — In `build_allsky_background`, scale background by transparency

```python
# In build_allsky_background(), AFTER computing bg_r, bg_g, bg_b
# from atm_state (around line 82-90), add:
transparency = getattr(atm_state, 'transparency', 1.0) if atm_state else 1.0

# Apply to background — clouds also dim the sky glow
# (but not completely: cloud self-emission adds a faint glow at night)
cloud_floor = max(0.0, 1.0 - transparency) * 0.15   # faint cloud glow
bg_r = bg_r * transparency + cloud_floor * bg_r * 0.3
bg_g = bg_g * transparency + cloud_floor * bg_g * 0.3
bg_b = bg_b * transparency + cloud_floor * bg_b * 0.5
```

### 3c — Sun and Moon: also scale by transparency

```python
# In AllSkyRenderer.render(), before draw_sun() and draw_moon() calls,
# pass transparency to the draw functions as a multiplier.
# These functions accept an optional brightness_mult parameter —
# if they don't, wrap with a local scale on the field after drawing.
# Simplest approach: after draw_sun/draw_moon, scale their contribution
# is handled already via the sky background; sun disk remains visible
# (it shines through clouds differently — skip for now, safe to defer to 14b).
```

Note: Sun/Moon through clouds is complex (aureole effect). For 14a, only
scale stars and background. Sun/Moon attenuation through clouds is a 14b task.

---

## Task 4 — Update `atmosphere/__init__.py`

```python
# ADD to imports from atmospheric_model:
# (AtmosphericState now has transparency and weather_condition — no new import needed)

# ADD new export for WeatherSystem:
from .weather import WeatherSystem, WeatherCondition, NightWeather

# ADD to __all__:
"WeatherSystem",
"WeatherCondition",
"NightWeather",
```

---

## Task 5 — Weather widget in `screen_observatory.py`

Add a weather status panel to the Observatory hub screen. This is the primary
player-facing window into weather conditions.

### 5a — Init WeatherSystem in ObservatoryScreen

```python
# In ObservatoryScreen.__init__, after self.current_filter = ...:
from universe.orbital_body import datetime_to_jd
from atmosphere.weather import WeatherSystem, WeatherCondition
from core.time_controller import TimeController

self._tc      = TimeController()
self._weather = WeatherSystem(base_seeing=2.5, seed=42)
```

### 5b — Update every frame

```python
# In ObservatoryScreen.update(dt):
self._tc.step(dt)
self.current_time = self._tc.utc
```

### 5c — Draw weather panel

Add a `_draw_weather_panel(surface, x, y, W_panel)` method:

```python
def _draw_weather_panel(self, surface: pygame.Surface,
                        x: int, y: int, W_panel: int = 300):
    """
    Draw a compact weather status widget showing:
    - Current condition name + icon
    - Sky transparency bar (0–100%)
    - Seeing gauge (arcsec, colour-coded)
    - Short text forecast hint
    """
    import pygame
    from atmosphere.weather import WeatherCondition

    jd   = self._tc.jd
    cond = self._weather.condition(jd)
    transp = self._weather.transparency(jd)
    seeing = self._weather.seeing(jd)
    summary = self._weather.night_summary(jd)

    H_panel = 130
    bg = pygame.Surface((W_panel, H_panel), pygame.SRCALPHA)
    bg.fill((0, 18, 10, 210))
    pygame.draw.rect(bg, (0, 100, 50), (0, 0, W_panel, H_panel), 1)
    surface.blit(bg, (x, y))

    fn = pygame.font.SysFont('monospace', 12, bold=True)
    fs = pygame.font.SysFont('monospace', 11)

    # Condition icon + name
    ICONS = {
        "clear":         "★",
        "mostly_clear":  "◑",
        "partly_cloudy": "◒",
        "cloudy":        "●",
        "overcast":      "■",
    }
    COND_COLORS = {
        "clear":         (0, 220, 100),
        "mostly_clear":  (160, 220, 80),
        "partly_cloudy": (220, 200, 60),
        "cloudy":        (200, 140, 60),
        "overcast":      (180, 80, 60),
    }
    icon  = ICONS.get(cond.value, "?")
    color = COND_COLORS.get(cond.value, (180, 180, 180))
    label = cond.value.replace("_", " ").upper()

    surface.blit(fn.render(f"WEATHER  {icon} {label}", True, color), (x + 8, y + 8))

    # Transparency bar
    bar_y = y + 30
    bar_w = W_panel - 20
    bar_h = 12
    pygame.draw.rect(surface, (0, 50, 25), (x + 10, bar_y, bar_w, bar_h))
    fill_w = int(bar_w * transp)
    bar_col = (0, 200, 80) if transp > 0.7 else (200, 180, 60) if transp > 0.4 else (200, 80, 60)
    pygame.draw.rect(surface, bar_col, (x + 10, bar_y, fill_w, bar_h))
    pygame.draw.rect(surface, (0, 80, 40), (x + 10, bar_y, bar_w, bar_h), 1)
    surface.blit(fs.render(f"Transparency  {transp*100:.0f}%", True, (160, 210, 160)),
                 (x + 10, bar_y + 14))

    # Seeing gauge
    see_y = bar_y + 32
    see_col = (0, 220, 100) if seeing < 2.0 else (200, 200, 60) if seeing < 3.5 else (200, 80, 60)
    see_rating = "Excellent" if seeing < 1.5 else "Good" if seeing < 2.5 else "Fair" if seeing < 4.0 else "Poor"
    surface.blit(fs.render(f"Seeing        {seeing:.1f}\"  ({see_rating})", True, see_col),
                 (x + 10, see_y))

    # Avg night forecast hint
    avg_t = summary["avg_transparency"]
    avg_s = summary["avg_seeing"]
    hint_col = (120, 160, 120)
    surface.blit(fs.render(f"Night avg:  transp {avg_t*100:.0f}%  see {avg_s:.1f}\"",
                           True, hint_col), (x + 10, see_y + 18))

    # Imaging suitability indicator
    if transp < 0.15:
        suit_text = "● IMAGING IMPOSSIBLE"
        suit_col  = (200, 60, 60)
    elif transp < 0.45:
        suit_text = "◑ POOR CONDITIONS"
        suit_col  = (200, 150, 60)
    elif transp < 0.75:
        suit_text = "◕ ACCEPTABLE"
        suit_col  = (180, 200, 80)
    else:
        suit_text = "★ GOOD NIGHT"
        suit_col  = (0, 220, 100)
    surface.blit(fs.render(suit_text, True, suit_col), (x + 10, see_y + 36))
```

### 5d — Call from `render()`

```python
# In ObservatoryScreen.render(), before drawing the footer:
self._draw_weather_panel(surface, x=W - 320, y=110, W_panel=310)
```

---

## Task 6 — Update HUD in `screen_imaging.py`

**File:** `ui_new/screen_imaging.py`  
⚠️ This file has a manual _expose() bugfix. Only touch the HUD line, nothing else.

Find the line (approximately line 822):
```python
f"ATM: {ph}  Sol {a.solar_alt_deg:+.0f}°  See {a.seeing_fwhm_arcsec:.1f}\"  "
f"Bg {a.sky_bg_g:.0f}ph"
```

Replace with:
```python
transp = getattr(a, 'transparency', 1.0)
wc     = getattr(a, 'weather_condition', 'clear')
f"ATM: {ph}  Sol {a.solar_alt_deg:+.0f}°  See {a.seeing_fwhm_arcsec:.1f}\"  "
f"Transp {transp*100:.0f}%  {wc}  Bg {a.sky_bg_g:.0f}ph"
```

⚠️ Use `getattr` with defaults — never assume the fields exist (backward compat).

---

## Acceptance Criteria

1. Seeing in allsky HUD changes smoothly across frames (no 5-min jumps).
2. On a "clear" night, `transparency ≈ 0.90–1.00` and stars are bright.
3. On an "overcast" night, `transparency < 0.15` and most stars invisible.
4. Observatory screen shows weather panel with condition, bar, seeing.
5. No crash if `atm_state` lacks `transparency` (getattr default everywhere).
6. `WeatherSystem` generates consistent results for same JD + seed (deterministic).
7. `WeatherSystem._cache` never grows beyond 3 entries (memory safe).

---

## Implementation Notes

- **Do not import `pygame` in `atmosphere/weather.py`** — it's a pure data module.
- **Do not import from `ui_new/` or `game/`** in `atmosphere/weather.py`.
- `NightWeather.SAMPLE_INTERVAL_MIN = 10` means seeing updates every 10 simulated
  minutes, but `_interpolate()` gives a smooth value between samples at any JD.
- The `cloud_floor` in Task 3b models the fact that clouds at night emit a faint
  upward glow (scattered city light) — keeps the sky from going pure black.
- Keep `seeing_fwhm_arcsec()` function in `atmospheric_model.py` — do not delete it.
  It may be used in tests or career mode. Just stop calling it from `AtmosphericModel.compute()`.
