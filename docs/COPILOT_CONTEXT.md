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
| `ui_new/screen_skychart.py` | Interactive sky chart (altazimuth, zoom, pan) — 1207 lines |
| `ui_new/screen_imaging.py` | Live allsky view + capture + processing pipeline |
| `ui_new/screen_catalog.py` | Catalog browser (DSO, stars, Solar System panel) |
| `ui_new/screen_equipment.py` | Telescope / camera / mount manager |
| `ui_new/screen_career.py` | Career mode tasks and progression |
| `universe/orbital_body.py` | Sun, Moon, planets — build_solar_system() |
| `universe/planet_physics.py` | IAU 2012 magnitudes, Saturn rings, diameters |
| `universe/minor_bodies.py` | Asteroids, comets — build_minor_bodies() |
| `universe/universe.py` | Universe — single source of truth for stars+DSO |
| `imaging/allsky_renderer.py` | Allsky camera render pipeline |
| `imaging/solar_bodies_renderer.py` | Planet/Sun/Moon rendering in imaging |
| `atmosphere/atmospheric_model.py` | Rayleigh, extinction, sky glow, twilight |
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
- `imaging/allsky_renderer.py` — complete and tested

### 2. Solar system pattern (reference implementation in screen_imaging.py)

```python
from universe.orbital_body import build_solar_system
from universe.minor_bodies import build_minor_bodies

bodies       = build_solar_system()     # [Sun, Moon, Mercury, ..., Pluto]
sun          = next(b for b in bodies if b.is_sun)
moon         = next(b for b in bodies if b.is_moon)
planets      = [b for b in bodies if not b.is_sun and not b.is_moon]
minor_bodies = build_minor_bodies()     # [Ceres, Vesta, Pallas, ..., Halley, Encke]

# Every frame, before reading ra_deg/dec_deg/apparent_mag:
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
body.name                      # str -- "Mercury", "Saturn", ...
body.bv_color                  # float -- B-V colour index
```

### 4. WARNING: apparent_diameter_arcsec -- property vs method inconsistency

This is the most common source of bugs when writing generic code:
- `OrbitalBody`: @property  =>  body.apparent_diameter_arcsec  (NO parentheses)
- `MinorBody`:   plain method =>  body.apparent_diameter_arcsec()  (WITH parentheses)
- `CometBody`:   does not exist -- check with hasattr first

Safe generic pattern (already used in screen_skychart.py):

```python
if hasattr(body, 'apparent_diameter_arcsec'):
    diam = (body.apparent_diameter_arcsec()
            if callable(body.apparent_diameter_arcsec)
            else body.apparent_diameter_arcsec)
else:
    diam = 1.0  # point-like fallback for CometBody
```

### 5. Defensive attribute access for mixed object types

When iterating over mixed lists (stars, DSO, planets, asteroids, comets),
use isinstance checks or hasattr before accessing class-specific fields:

```python
from universe.orbital_body import OrbitalBody
from universe.minor_bodies import MinorBody, CometBody

if isinstance(obj, OrbitalBody):
    # has: apparent_mag, distance_au, phase_fraction, ring_inclination_B, etc.
elif isinstance(obj, (MinorBody, CometBody)):
    # has: apparent_mag, distance_au, phase_fraction
    # MinorBody: apparent_diameter_arcsec() as method
    # CometBody: tail_pa_deg, _r_sun_au
else:
    # SpaceObject (star or DSO)
    # has: mag, size_arcmin, constellation, meta dict
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

Observer is always Parma, Italy: lat=44.8°N, lon=10.3°E.

### 8. Time

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
| 13a | COMPLETE | universe/, imaging/allsky_renderer.py |
| 13b | COMPLETE | ui_new/screen_skychart.py, ui_new/screen_catalog.py |
| 14  | PLANNED  | Seeing variabile, meteo, nuvole |
| 15  | PLANNED  | VFX layer, Via Lattea, twinkling |

### Sprint 13b -- What was added
- screen_skychart.py: _draw_planets() with all solar bodies, Saturn rings,
  Moon phase shading, Sun glow, minor bodies. Toggle [P] / PLANETS button.
  Click selection + info panel for all body types (OrbitalBody, MinorBody, CometBody).
- screen_catalog.py: _draw_solar_system_panel() with live ephemeris table
  (mag, distance, phase, ring B, altitude indicator up/down).
- orbital_body.py: new ring_inclination_B @property on OrbitalBody.
- docs/api/body_classes.md: full API reference generated and verified.

### Sprint 13b -- Bugs found (for future reference)
4 AttributeError/TypeError from assuming uniform interfaces across body types.
Fix: defensive hasattr + callable checks, documented in Rules 4 and 5 above.

---

## Retro Visual Style

- Palette: dark bg (2, 4, 14), green text (0, 185, 85), yellow (255, 255, 0), panel bg (0, 16, 10).
- Font: always pygame.font.SysFont('monospace', ...) -- no custom fonts.
- No anti-aliasing on shapes (crisp pixel look).
- Panels: semi-transparent surface with pygame.SRCALPHA, 1px border.
- Stars: surface.set_at(px, color) for faint, pygame.draw.circle for bright.
- Planet colours: see _PLANET_COLORS dict in screen_skychart.py lines 90-100.

---

## Further Reading

- docs/api/body_classes.md -- complete attribute/method reference for all body classes
- docs/specs/ -- per-sprint implementation specs
- README.md -- full project overview, physics references, backlog
