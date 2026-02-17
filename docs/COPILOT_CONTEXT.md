# Copilot Context — Observatory Simulation Game

Read this file before working on any feature in this codebase.

---

## Project at a Glance

Astronomical observatory simulator in Python/Pygame. Retro DOS/VGA aesthetic,
professional-grade physics (VSOP87, Meeus, IAU 2012). ~20,000 lines.

**Entry point:** `python main_app.py`  
**Dependencies:** `pip install pygame numpy scipy`

---

## Module Map (what lives where)

| Module | Responsibility |
|---|---|
| `ui_new/screen_skychart.py` | Interactive sky chart (altazimuth, zoom, pan) |
| `ui_new/screen_imaging.py` | Live allsky view + capture + processing pipeline |
| `ui_new/screen_catalog.py` | Catalog browser (DSO, stars, filter/search) |
| `ui_new/screen_equipment.py` | Telescope / camera / mount manager |
| `ui_new/screen_career.py` | Career mode tasks and progression |
| `universe/orbital_body.py` | Sun, Moon, planets — `build_solar_system()` |
| `universe/planet_physics.py` | IAU 2012 magnitudes, Saturn rings, diameters |
| `universe/minor_bodies.py` | Asteroids, comets — `MinorBodyCatalog` |
| `universe/universe.py` | `Universe` — single source of truth for stars+DSO |
| `imaging/allsky_renderer.py` | Allsky camera render pipeline |
| `imaging/solar_bodies_renderer.py` | Planet/Sun/Moon rendering in imaging |
| `atmosphere/atmospheric_model.py` | Rayleigh, extinction, sky glow, twilight |
| `core/celestial_math.py` | Projections, coordinate transforms |
| `core/time_controller.py` | `TimeController` — shared JD clock |

---

## Golden Rules

### 1. Never modify these files without explicit instruction
- `ui_new/screen_imaging.py` — contains a manual `_expose()` bugfix (Feb 2026)
- `universe/orbital_body.py` — complete and tested
- `universe/planet_physics.py` — complete and tested
- `universe/minor_bodies.py` — complete and tested
- `imaging/allsky_renderer.py` — complete and tested

### 2. Solar system pattern (used in screen_imaging.py, copy faithfully)
```python
from universe.orbital_body import build_solar_system
bodies = build_solar_system()          # [Sun, Moon, Mercury, …, Pluto]
sun    = next(b for b in bodies if b.is_sun)
moon   = next(b for b in bodies if b.is_moon)
planets = [b for b in bodies if not b.is_sun and not b.is_moon]

# Every frame, before reading ra_deg/dec_deg/apparent_mag:
sun.update_position(jd, lat_deg, lon_deg)
moon.update_position(jd, lat_deg, lon_deg)
for p in planets:
    p.update_position(jd, lat_deg, lon_deg)
```

### 3. OrbitalBody API (all valid after update_position)
```python
body.ra_deg                    # float — apparent RA degrees
body.dec_deg                   # float — apparent Dec degrees
body.apparent_mag              # float property — V magnitude
body.distance_au               # float property — AU from Earth
body.phase_fraction            # float property — 0=new, 1=full
body.apparent_diameter_arcsec()  # float METHOD (call with ())
body.has_phases                # bool — True for Mercury, Venus
body.is_sun / body.is_moon     # bool
body.uid                       # str — "MERCURY", "SATURN", "MOON", "SUN", …
body.name                      # str — "Mercury", "Saturn", …
body.bv_color                  # float — B-V colour index
```

### 4. Tone mapping — never touch per-channel
The allsky renderer uses luma-chroma preserving tone mapping.
**Never apply log/gamma stretch per channel** — it desaturates colours.
Always stretch the LUMA, then scale R/G/B by the same factor.

### 5. Coordinate transforms
```python
from core.celestial_math import radec_to_altaz, altaz_to_radec, PARMA_OBSERVER
alt, az = radec_to_altaz(ra_deg, dec_deg, lst_deg, lat_deg)
```
Observer is always Parma, Italy: lat=44.8°N, lon=10.3°E.

### 6. Time
```python
from core.time_controller import TimeController
tc = TimeController()   # or reuse the existing one from state_manager
jd = tc.jd              # Julian Date (float)
tc.step(dt)             # advance by dt real seconds
```

---

## Sprint Status

| Sprint | Status | Key files |
|---|---|---|
| 13a | ✅ Complete | `universe/`, `imaging/allsky_renderer.py` |
| 13b | 🔧 In progress | `ui_new/screen_skychart.py`, `ui_new/screen_catalog.py` |
| 14 | 📋 Planned | Seeing, meteo, nuvole |
| 15 | 📋 Planned | VFX layer, Via Lattea, twinkling |

---

## Retro Visual Style

- Palette: dark background `(2, 4, 14)`, green text `(0, 185, 85)`, 
  yellow highlights `(255, 255, 0)`, panel bg `(0, 16, 10)`.
- Font: always `pygame.font.SysFont('monospace', ...)` — no custom fonts.
- No anti-aliasing on shapes (crisp pixel look).
- Panels: semi-transparent surface with `pygame.SRCALPHA`, 1px border.
- Stars: `surface.set_at(px, color)` for faint, `pygame.draw.circle` for bright.
