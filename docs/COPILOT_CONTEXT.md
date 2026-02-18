# Copilot Context — Observatory Simulation Game

Read this file before working on any feature in this codebase.

---

## Project at a Glance

Astronomical observatory simulator in Python/Pygame. Retro DOS/VGA aesthetic,
professional-grade physics (VSOP87, Meeus, IAU 2012). ~21,000 lines.

**Entry point:** `python main_app.py`
**Dependencies:** `pip install pygame numpy scipy`

---

## Module Map (what lives where)

| Module | Responsibility |
|---|---|
| `ui_new/screen_skychart.py` | Interactive sky chart (altazimuth, zoom, pan) |
| `ui_new/screen_imaging.py` | Live allsky view + capture + processing pipeline |
| `ui_new/screen_catalog.py` | Catalog browser (DSO, stars, Solar System panel) |
| `ui_new/screen_observatory.py` | Hub screen — navigation + weather widget |
| `universe/orbital_body.py` | Sun, Moon, planets — build_solar_system() |
| `universe/planet_physics.py` | IAU 2012 magnitudes, Saturn rings, diameters |
| `universe/minor_bodies.py` | Asteroids, comets — build_minor_bodies() |
| `universe/universe.py` | Universe — single source of truth for stars+DSO |
| `atmosphere/atmospheric_model.py` | Rayleigh, extinction, sky glow, AtmosphericState |
| `atmosphere/weather.py` | WeatherSystem — nightly conditions, smooth seeing (Sprint 14a) |
| `atmosphere/cloud_layer.py` | CloudLayer — procedural numpy cloud mask (Sprint 14b) |
| `imaging/allsky_renderer.py` | Allsky camera render pipeline |
| `imaging/solar_bodies_renderer.py` | Planet/Sun/Moon rendering in imaging |
| `core/celestial_math.py` | Projections, coordinate transforms |
| `core/time_controller.py` | TimeController — shared JD clock |
| `docs/api/body_classes.md` | Complete API reference for all body classes |

---

## Golden Rules

### 1. Never modify these files without explicit instruction
- `ui_new/screen_imaging.py` — contains a manual _expose() bugfix (Feb 2026)
- `universe/orbital_body.py` — complete and tested
- `universe/planet_physics.py` — complete and tested
- `universe/minor_bodies.py` — complete and tested
- `imaging/allsky_renderer.py` — modify only as described in sprint specs

### 2. Solar system pattern (reference implementation in screen_imaging.py)

```python
from universe.orbital_body import build_solar_system
from universe.minor_bodies import build_minor_bodies

bodies       = build_solar_system()
sun          = next(b for b in bodies if b.is_sun)
moon         = next(b for b in bodies if b.is_moon)
planets      = [b for b in bodies if not b.is_sun and not b.is_moon]
minor_bodies = build_minor_bodies()

# Every frame:
jd  = time_controller.jd
lat = observer.latitude_deg
lon = observer.longitude_deg
sun.update_position(jd, lat, lon)
moon.update_position(jd, lat, lon)
for p in planets:
    p.update_position(jd, lat, lon)
for b in minor_bodies:
    b.update_position(jd, lat, lon)
```

### 3. OrbitalBody API (all valid after update_position)

```python
body.ra_deg                    # float -- apparent RA degrees
body.dec_deg                   # float -- apparent Dec degrees
body.apparent_mag              # float @property -- V magnitude
body.distance_au               # float @property -- AU from Earth
body.phase_fraction            # float @property -- 0=new, 1=full
body.apparent_diameter_arcsec  # float @property -- NO parentheses (OrbitalBody only!)
body.ring_inclination_B        # float @property -- Saturn B angle degrees, 0 for others
body.has_phases                # bool @property -- True for Mercury, Venus
body.is_sun / body.is_moon     # bool
body.uid                       # str -- "MERCURY", "SATURN", "MOON", "SUN", ...
body.name                      # str
body.bv_color                  # float -- B-V colour index
```

### 4. WARNING: apparent_diameter_arcsec -- property vs method inconsistency

- `OrbitalBody`: @property  =>  body.apparent_diameter_arcsec  (NO parentheses)
- `MinorBody`:   plain method =>  body.apparent_diameter_arcsec()  (WITH parentheses)
- `CometBody`:   does not exist -- check with hasattr first

Safe generic pattern:
```python
if hasattr(body, 'apparent_diameter_arcsec'):
    diam = (body.apparent_diameter_arcsec()
            if callable(body.apparent_diameter_arcsec)
            else body.apparent_diameter_arcsec)
else:
    diam = 1.0
```

### 5. Defensive attribute access for mixed object types

```python
from universe.orbital_body import OrbitalBody
from universe.minor_bodies import MinorBody, CometBody

if isinstance(obj, OrbitalBody):
    # apparent_mag, distance_au, phase_fraction, ring_inclination_B, etc.
elif isinstance(obj, (MinorBody, CometBody)):
    # apparent_mag, distance_au, phase_fraction
    # MinorBody: apparent_diameter_arcsec() as method
    # CometBody: tail_pa_deg, _r_sun_au
else:
    # SpaceObject (star or DSO): mag, size_arcmin, constellation, meta dict
```

Attributes ABSENT on solar system bodies: obj_class, constellation, size_arcmin, meta.

### 6. Tone mapping -- never stretch per-channel

The allsky renderer uses luma-chroma preserving tone mapping.
Never apply log/gamma stretch per channel -- it desaturates colours.
Always stretch the LUMA, then scale R/G/B by the same factor.

### 7. Coordinate transforms

```python
from core.celestial_math import radec_to_altaz, altaz_to_radec, PARMA_OBSERVER
alt, az = radec_to_altaz(ra_deg, dec_deg, lst_deg, lat_deg)
```

Observer is always Parma, Italy: lat=44.8N, lon=10.3E.

### 8. Time

```python
from core.time_controller import TimeController
tc = TimeController()
jd = tc.jd              # Julian Date (float)
tc.step(dt)             # advance by dt real seconds
```

### 9. Weather/atmosphere pattern (Sprint 14+)

```python
from atmosphere.weather import WeatherSystem, WeatherCondition

ws = WeatherSystem(base_seeing=2.5, seed=42)  # seed=42 EVERYWHERE (must match)

# Every frame:
transparency = ws.transparency(jd)   # float 0.0-1.0
seeing       = ws.seeing(jd)         # float arcsec FWHM, smooth
condition    = ws.condition(jd)      # WeatherCondition enum

# AtmosphericState now has two new fields (use getattr for backward compat):
transp = getattr(atm_state, 'transparency', 1.0)
wc     = getattr(atm_state, 'weather_condition', 'clear')
```

**Seed consistency rule:** WeatherSystem seed must be 42 in ALL locations
(screen_observatory, screen_skychart, AtmosphericModel, CloudLayer).
Sprint 17 will centralise this in GameState.

### 10. Cloud layer pattern (Sprint 14b+)

```python
from atmosphere.cloud_layer import CloudLayer

cloud = CloudLayer(seed=42, render_size=512)

# Every render:
cloud.update(transparency=transp, sim_time_s=elapsed_s)
mask = cloud.mask   # (S, S) float32: 0=clear, 1=opaque
```

`generate_cloud_mask(512, ...)` runs in ~1-3ms (pure numpy, no scipy).

---

## Sprint Status

| Sprint | Status | Key files |
|---|---|---|
| 13a | COMPLETE | universe/, imaging/allsky_renderer.py |
| 13b | COMPLETE | ui_new/screen_skychart.py, ui_new/screen_catalog.py |
| 14a | IN PROGRESS | atmosphere/weather.py (NEW), atmospheric_model.py, screen_observatory.py |
| 14b | PLANNED | atmosphere/cloud_layer.py (NEW), allsky_renderer.py |
| 15  | PLANNED | VFX layer, Via Lattea, twinkling |

### Sprint 14a -- What to build
1. `atmosphere/weather.py`: WeatherSystem + WeatherCondition + NightWeather
2. Add `transparency` and `weather_condition` fields to AtmosphericState
3. Replace 5-min discrete seeing jumps with smooth WeatherSystem.seeing(jd)
4. Wire transparency into AllSkyRenderer star flux and background
5. Weather widget in screen_observatory.py
6. One-line HUD update in screen_imaging.py (getattr, safe)

### Sprint 14b -- What to build (after 14a)
1. `atmosphere/cloud_layer.py`: CloudLayer + generate_cloud_mask (numpy only)
2. Composite cloud overlay in AllSkyRenderer.render() after stars
3. Semi-transparent grey overlay in screen_skychart.py
4. Export new classes in atmosphere/__init__.py

### Sprint 13b -- Bugs found (for reference)
4 AttributeError/TypeError from assuming uniform interfaces across body types.
Fix: defensive hasattr + callable checks, documented in Rules 4 and 5 above.

---

## Retro Visual Style

- Palette: dark bg (2, 4, 14), green text (0, 185, 85), yellow (255, 255, 0), panel bg (0, 16, 10)
- Font: always pygame.font.SysFont('monospace', ...) -- no custom fonts
- No anti-aliasing on shapes (crisp pixel look)
- Panels: semi-transparent surface with pygame.SRCALPHA, 1px border
- Stars: surface.set_at(px, color) for faint, pygame.draw.circle for bright
- Planet colours: see _PLANET_COLORS dict in screen_skychart.py

---

## Further Reading

- docs/api/body_classes.md -- complete attribute/method reference for all body classes
- docs/specs/sprint_14a_weather_seeing.md -- detailed task list for 14a
- docs/specs/sprint_14b_cloud_layer.md -- detailed task list for 14b
- README.md -- full project overview, physics references, backlog
