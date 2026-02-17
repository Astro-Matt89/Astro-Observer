# Sprint 13b — Planets in Catalog Browser

**Goal:** Add a "Solar System" section to `screen_catalog.py` that lists all
planets, Moon, Sun, and hardcoded minor bodies with their current ephemeris
data (magnitude, distance, phase, etc.).

**Status:** Not started.  
**Depends on:** `sprint_13b_planets_skychart.md` — the solar system init
pattern is identical, copy it here too.

---

## Background

The current catalog browser lists only static objects (stars, DSO) from the
`Universe`. Solar system bodies are not in `Universe` (they are instantiated
separately with `build_solar_system()`). The catalog screen needs its own
instance of solar system bodies that it updates on entry and once per frame.

---

## Task 1 — Init solar system in CatalogScreen

**File:** `ui_new/screen_catalog.py`

```python
# ADD imports
from universe.orbital_body import build_solar_system, OrbitalBody
from universe.minor_bodies import MinorBodyCatalog
from universe.planet_physics import (
    saturn_ring_inclination_B, get_planet_physical_data
)
from core.time_controller import TimeController
from core.celestial_math import PARMA_OBSERVER, radec_to_altaz

# ADD in __init__, after existing init:
self._solar_bodies = build_solar_system()
self._sun          = next(b for b in self._solar_bodies if b.is_sun)
self._moon         = next(b for b in self._solar_bodies if b.is_moon)
self._planets      = [b for b in self._solar_bodies
                      if not b.is_sun and not b.is_moon]
self._minor_bodies = MinorBodyCatalog.get_default_bodies()
self._observer     = PARMA_OBSERVER

# Reuse the existing TimeController from state_manager if available,
# otherwise create one. CatalogScreen already has state_manager.
# NOTE: use state_manager's time controller if it exposes one,
# so time is consistent across screens.
# If not available, fall back:
self._tc = TimeController()

# Add a filter toggle for solar system section
self.show_solar_system = True
```

---

## Task 2 — Update positions on `on_enter` and every frame

**File:** `ui_new/screen_catalog.py`

```python
def on_enter(self):
    super().on_enter()
    self.update_filtered_list()
    self._update_solar_positions()   # ADD

def update(self, dt: float):
    self._tc.step(dt)
    self._update_solar_positions()   # ADD

def _update_solar_positions(self):
    """Refresh RA/Dec and ephemeris for all solar system bodies."""
    jd  = self._tc.jd
    lat = self._observer.latitude_deg
    lon = self._observer.longitude_deg
    self._sun.update_position(jd, lat, lon)
    self._moon.update_position(jd, lat, lon)
    for body in self._planets:
        body.update_position(jd, lat, lon)
    for body in self._minor_bodies:
        body.update_position(jd, lat, lon)
```

---

## Task 3 — Render solar system panel

**File:** `ui_new/screen_catalog.py`  
**Where:** `render()` method. Add a dedicated panel in the right area of the
screen (below the existing filter buttons, or as a separate column).

### Panel layout

```
┌─────────────────────────────────────────┐
│  SOLAR SYSTEM                           │
│  ─────────────────────────────────────  │
│  ☉ Sun          -26.7  1.000 AU  —      │
│  ☽ Moon          -9.4  0.003 AU  84%    │
│  ☿ Mercury       +0.2  0.812 AU  —      │
│  ♀ Venus         -3.9  0.723 AU  72%    │
│  ♂ Mars          +1.1  1.521 AU  —      │
│  ♃ Jupiter       -2.3  5.203 AU  —      │
│  ♄ Saturn        +0.7  9.537 AU  B=12°  │
│  ⛢ Uranus        +5.7 19.189 AU  —      │
│  ♆ Neptune       +7.9 30.069 AU  —      │
│  ♇ Pluto        +14.3 39.482 AU  —      │
│  ─────────────────────────────────────  │
│  Minor Bodies                           │
│  Ceres           +7.1  2.342 AU         │
│  Vesta           +6.8  2.361 AU         │
│  ...                                    │
└─────────────────────────────────────────┘
```

### Implementation

```python
def _draw_solar_system_panel(self, surface: pygame.Surface, x: int, y: int):
    """
    Draw the Solar System section of the catalog.
    x, y = top-left corner of the panel.
    """
    import pygame
    from universe.orbital_body import OrbitalBody
    from universe.planet_physics import saturn_ring_inclination_B

    W_panel = 340
    font_h = pygame.font.SysFont('monospace', 12, bold=True)
    font   = pygame.font.SysFont('monospace', 11)

    # Background
    bg = pygame.Surface((W_panel, 400), pygame.SRCALPHA)
    bg.fill((0, 18, 10, 200))
    pygame.draw.rect(bg, (0, 100, 50), (0, 0, W_panel, 400), 1)
    surface.blit(bg, (x, y))

    fy = y + 8
    surface.blit(font_h.render("SOLAR SYSTEM", True, (0, 220, 100)), (x + 8, fy))
    fy += 20
    pygame.draw.line(surface, (0, 80, 40), (x + 4, fy), (x + W_panel - 4, fy), 1)
    fy += 6

    # Symbol lookup
    SYMBOLS = {
        "SUN": "☉", "MOON": "☽", "MERCURY": "☿", "VENUS": "♀",
        "MARS": "♂", "JUPITER": "♃", "SATURN": "♄",
        "URANUS": "⛢", "NEPTUNE": "♆", "PLUTO": "♇",
    }
    COLORS = {
        "SUN": (255, 255, 180), "MOON": (200, 200, 200),
        "MERCURY": (180, 160, 140), "VENUS": (220, 210, 160),
        "MARS": (210, 100, 60), "JUPITER": (200, 170, 130),
        "SATURN": (210, 190, 140), "URANUS": (150, 210, 220),
        "NEPTUNE": (100, 130, 220), "PLUTO": (150, 140, 130),
    }

    jd = self._tc.jd

    # Order: Sun, Moon, planets (Mercury→Pluto)
    bodies_ordered = [self._sun, self._moon] + self._planets

    for body in bodies_ordered:
        sym   = SYMBOLS.get(body.uid, "●")
        color = COLORS.get(body.uid, (180, 180, 180))
        mag   = body.apparent_mag
        dist  = body.distance_au

        # Extra info column
        extra = ""
        if body.is_moon or body.has_phases:
            extra = f"{int(body.phase_fraction * 100):3d}%"
        elif body.uid == "SATURN":
            B = saturn_ring_inclination_B(jd)
            extra = f"B={B:+.0f}°"

        # Distance formatting
        if body.is_moon:
            dist_str = f"{body.distance_au * 149597870:.0f} km"
        elif body.is_sun:
            dist_str = "1.000 AU "
        else:
            dist_str = f"{dist:6.3f} AU"

        # Altitude: show above/below horizon indicator
        alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                                  self._tc.lst(self._observer.longitude_deg),
                                  self._observer.latitude_deg)
        vis_col = (0, 200, 80) if alt > 0 else (120, 80, 80)
        vis_sym = "↑" if alt > 0 else "↓"

        line = f"{sym} {body.name:<10}  {mag:+6.1f}  {dist_str}  {extra}"
        txt = font.render(line, True, color)
        surface.blit(txt, (x + 8, fy))

        # Visibility indicator on the right
        vis_txt = font.render(f"{vis_sym}{alt:+.0f}°", True, vis_col)
        surface.blit(vis_txt, (x + W_panel - 65, fy))

        # Highlight if selected
        if (self.selected_object and
                hasattr(self.selected_object, 'uid') and
                self.selected_object.uid == body.uid):
            pygame.draw.rect(surface, (0, 180, 70),
                             (x + 4, fy - 1, W_panel - 8, 15), 1)

        # Click region stored for _handle_click
        # (store rects in a list for hit detection — see Task 4)
        fy += 16

    # Minor bodies separator
    fy += 4
    pygame.draw.line(surface, (0, 60, 30), (x + 4, fy), (x + W_panel - 4, fy), 1)
    fy += 6
    surface.blit(font.render("Minor Bodies", True, (0, 140, 60)), (x + 8, fy))
    fy += 16

    for body in self._minor_bodies:
        mag   = body.apparent_mag
        dist  = body.distance_au
        alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                                  self._tc.lst(self._observer.longitude_deg),
                                  self._observer.latitude_deg)
        vis_col = (0, 180, 70) if alt > 0 else (100, 70, 70)
        vis_sym = "↑" if alt > 0 else "↓"

        line = f"● {body.name:<12}  {mag:+5.1f}  {dist:5.3f} AU"
        surface.blit(font.render(line, True, (160, 155, 140)), (x + 8, fy))
        vis_txt = font.render(f"{vis_sym}{alt:+.0f}°", True, vis_col)
        surface.blit(vis_txt, (x + W_panel - 65, fy))
        fy += 15
```

**Call it from `render()`:**
```python
# ADD in render(), after drawing the main object list and filters:
self._draw_solar_system_panel(surface, x=820, y=140)
# Adjust x, y to fit your layout — right column of the screen works well.
```

---

## Task 4 — Click selection in solar system panel

**File:** `ui_new/screen_catalog.py`

Store panel row rects during `_draw_solar_system_panel` in
`self._solar_panel_rows: list[tuple[pygame.Rect, OrbitalBody]]`, then check
them in `handle_input`:

```python
# In _draw_solar_system_panel, for each body row:
row_rect = pygame.Rect(x + 4, fy - 1, W_panel - 8, 15)
self._solar_panel_rows.append((row_rect, body))

# In handle_input, on MOUSEBUTTONDOWN:
for rect, body in getattr(self, '_solar_panel_rows', []):
    if rect.collidepoint(event.pos):
        self.selected_object = body
        break
```

---

## Task 5 — Selected info panel for OrbitalBody

**File:** `ui_new/screen_catalog.py`  
The existing info panel (bottom-right) renders `obj.name`, `obj.uid`,
`obj.mag`, etc. OrbitalBody has all of these via SpaceObject inheritance,
so the panel should display correctly for most fields.

Add a branch to show ephemeris-specific fields when the selected object is
an OrbitalBody:

```python
# In render(), in the "selected object info" section:
from universe.orbital_body import OrbitalBody
if isinstance(self.selected_object, OrbitalBody):
    body = self.selected_object
    extra_lines = []
    extra_lines.append(f"Distance: {body.distance_au:.4f} AU")
    extra_lines.append(f"Apparent mag: {body.apparent_mag:+.2f}")
    extra_lines.append(f"Diameter: {body.apparent_diameter_arcsec():.1f}\"")
    if body.has_phases:
        extra_lines.append(f"Phase: {int(body.phase_fraction * 100)}%")
    if body.uid == "SATURN":
        B = saturn_ring_inclination_B(self._tc.jd)
        extra_lines.append(f"Ring tilt B: {B:+.1f}°")
    # draw extra_lines below existing info panel ...
```

---

## Acceptance Criteria

1. Solar System panel visible in Catalog Browser with all planets, Moon, Sun.
2. Magnitude, distance, phase/ring info updated in real time with `_tc`.
3. Altitude indicator (↑↓) correct — visible planets show ↑ only when above horizon.
4. Clicking a planet in the panel populates the info panel below.
5. Minor bodies (Ceres, Vesta, etc.) listed in the sub-section.
6. No crash if `MinorBodyCatalog.get_default_bodies()` returns an empty list.

---

## Files Modified

| File | Change |
|---|---|
| `ui_new/screen_catalog.py` | Solar system panel, click handler, info display |

## Files NOT Modified

| File | Reason |
|---|---|
| `universe/orbital_body.py` | Complete — do not touch |
| `universe/minor_bodies.py` | Complete — do not touch |
| `ui_new/screen_imaging.py` | Contains `_expose()` bugfix — do not touch |
