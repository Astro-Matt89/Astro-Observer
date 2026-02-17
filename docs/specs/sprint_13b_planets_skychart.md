# Sprint 13b — Planets in Sky Chart

**Goal:** Render all Solar System bodies (planets, Sun, Moon, minor bodies) in
`screen_skychart.py`, matching the visual style of the existing chart.  
**Status:** Not started.  
**Dependencies:** `universe/orbital_body.py`, `universe/planet_physics.py`,
`universe/minor_bodies.py` — all already implemented and working in
`screen_imaging.py`.

---

## Context: How screen_imaging.py does it (reference implementation)

```python
# screen_imaging.py — init (lines 153–161)
from universe.orbital_body import build_solar_system

self._solar_bodies = build_solar_system()          # [Sun, Moon, Mercury, …, Pluto]
self._sun   = next(b for b in self._solar_bodies if b.is_sun)
self._moon  = next(b for b in self._solar_bodies if b.is_moon)
self._planets = [b for b in self._solar_bodies
                 if not b.is_sun and not b.is_moon]
# update loop (every frame)
jd  = self._tc.jd
lat = self._observer.latitude_deg
lon = self._observer.longitude_deg
self._sun.update_position(jd, lat, lon)
self._moon.update_position(jd, lat, lon)
for body in self._planets:
    body.update_position(jd, lat, lon)
```

**Key OrbitalBody API** (all computed after `update_position(jd, lat, lon)`):

| Attribute / Method | Type | Notes |
|---|---|---|
| `body.ra_deg` | float | Apparent RA (degrees) |
| `body.dec_deg` | float | Apparent Dec (degrees) |
| `body.apparent_mag` | float (property) | V magnitude |
| `body.distance_au` | float (property) | Earth distance in AU |
| `body.phase_fraction` | float (property) | 0.0=new, 1.0=full |
| `body.apparent_diameter_arcsec()` | float (method) | Angular diameter |
| `body.has_phases` | bool (property) | True for Mercury, Venus |
| `body.is_sun` | bool | |
| `body.is_moon` | bool | |
| `body.uid` | str | "MERCURY", "VENUS", … "SATURN", "MOON", "SUN" |
| `body.name` | str | "Mercury", "Venus", … |
| `body.bv_color` | float | B-V index for colour |

**Saturn extra:**
```python
from universe.planet_physics import saturn_ring_inclination_B
B_deg = saturn_ring_inclination_B(jd)   # ring tilt angle, ~0° in 2025 → ~27° in 2032
```

**Minor bodies** (already in `screen_imaging.py`):
```python
from universe.minor_bodies import MinorBodyCatalog
self._minor_bodies = MinorBodyCatalog.get_default_bodies()
# Each MinorBody also has .ra_deg/.dec_deg/.apparent_mag after update_position(jd, lat, lon)
```

---

## Task 1 — Initialise solar system bodies in SkychartScreen

**File:** `ui_new/screen_skychart.py`  
**Where:** `__init__` method, after the existing init block.

```python
# ADD these imports at the top of screen_skychart.py
from universe.orbital_body import build_solar_system
from universe.minor_bodies import MinorBodyCatalog
from universe.planet_physics import saturn_ring_inclination_B

# ADD in __init__, after self._earth = EarthRenderer():
self._solar_bodies  = build_solar_system()
self._sun           = next(b for b in self._solar_bodies if b.is_sun)
self._moon          = next(b for b in self._solar_bodies if b.is_moon)
self._planets       = [b for b in self._solar_bodies
                       if not b.is_sun and not b.is_moon]
self._minor_bodies  = MinorBodyCatalog.get_default_bodies()

# Toggle for showing/hiding planets (default ON)
self.show_planets = True
```

---

## Task 2 — Update positions every frame

**File:** `ui_new/screen_skychart.py`  
**Where:** `update(self, dt: float)` method, after `self.lst_deg = ...`

```python
def update(self, dt: float):
    self._tc.step(dt)
    self.lst_deg = self._tc.lst(self.observer.longitude_deg)

    # ADD: update solar system positions
    jd  = self._tc.jd
    lat = self.observer.latitude_deg
    lon = self.observer.longitude_deg
    self._sun.update_position(jd, lat, lon)
    self._moon.update_position(jd, lat, lon)
    for body in self._planets:
        body.update_position(jd, lat, lon)
    for body in self._minor_bodies:
        body.update_position(jd, lat, lon)
```

---

## Task 3 — Add toggle button for planets

**File:** `ui_new/screen_skychart.py`  
**Where:** `_create_buttons` method, in the `self._toggles` dict.

```python
# ADD to self._toggles dict (alongside 'grid', 'const', 'dso', etc.):
'planets': ('show_planets', 'PLANETS'),
```

The existing button-creation loop will handle layout automatically.

---

## Task 4 — Hook into render pipeline

**File:** `ui_new/screen_skychart.py`  
**Where:** `render(self, surface)` method, after `self._draw_dso(surface)` and
**before** the Earth horizon call.

```python
# ADD after _draw_dso, before Earth horizon:
if self.show_planets:
    self._draw_planets(surface, mag_limit)
```

---

## Task 5 — Implement `_draw_planets`

**File:** `ui_new/screen_skychart.py`  
**Add new method** in the "Draw" section (after `_draw_dso_symbol`).

### Planet symbols (dict at module level, near _DSO_COLORS)

```python
# ADD near top of file with other constants
_PLANET_COLORS = {
    "SUN":     (255, 255, 180),
    "MOON":    (200, 200, 200),
    "MERCURY": (180, 160, 140),
    "VENUS":   (220, 210, 160),
    "MARS":    (210, 100,  60),
    "JUPITER": (200, 170, 130),
    "SATURN":  (210, 190, 140),
    "URANUS":  (150, 210, 220),
    "NEPTUNE": (100, 130, 220),
    "PLUTO":   (150, 140, 130),
}

_PLANET_SYMBOLS = {
    "SUN":     "☉",
    "MOON":    "☽",
    "MERCURY": "☿",
    "VENUS":   "♀",
    "MARS":    "♂",
    "JUPITER": "♃",
    "SATURN":  "♄",
    "URANUS":  "⛢",
    "NEPTUNE": "♆",
    "PLUTO":   "♇",
}
```

### `_draw_planets` method

```python
def _draw_planets(self, surface: pygame.Surface, mag_limit: float):
    """
    Draw Solar System bodies (Sun, Moon, planets, minor bodies) on the sky chart.

    Visual encoding:
      - Size: scaled from apparent_diameter_arcsec, minimum 3px, maximum ~18px
      - Colour: from _PLANET_COLORS, dimmed if below mag_limit
      - Label: planet name + magnitude, shown when show_labels=True
      - Saturn: draw ring ellipse (thin line) proportional to ring size
      - Selection ring: yellow circle outline on selected body

    Bodies are drawn in order: minor bodies first, then planets, Sun, Moon last
    (so bright bodies paint over faint ones at same pixel).
    """
    font_label = pygame.font.SysFont('monospace', 10)
    font_sym   = pygame.font.SysFont('monospace', 11, bold=True)
    jd = self._tc.jd

    # --- Minor bodies (asteroids, comets hardcoded) ---
    for body in self._minor_bodies:
        if body.apparent_mag > mag_limit + 2:   # slightly more lenient than stars
            continue
        alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                                  self.lst_deg, self.observer.latitude_deg)
        if alt < -2:
            continue
        px = self.proj.project(alt, az)
        if not px or not self.proj.is_on_screen(*px):
            continue

        # Minor bodies: small dot, grey-white, like faint stars
        r = max(2, magnitude_to_radius(body.apparent_mag))
        color = (180, 180, 160)
        pygame.draw.circle(surface, color, px, r)

        if self.show_labels and self.proj.fov_deg < 40:
            lbl = font_label.render(body.name, True, (140, 140, 120))
            surface.blit(lbl, (px[0] + r + 2, px[1] - 5))

        if self.selected_obj and getattr(self.selected_obj, 'uid', None) == body.uid:
            pygame.draw.circle(surface, (255, 255, 0), px, r + 5, 1)

    # --- Planets (Mercury … Pluto) ---
    for body in self._planets:
        alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                                  self.lst_deg, self.observer.latitude_deg)
        if alt < -2:
            continue
        px = self.proj.project(alt, az)
        if not px or not self.proj.is_on_screen(*px):
            continue

        color = _PLANET_COLORS.get(body.uid, (180, 180, 180))

        # Radius: from apparent diameter scaled to current FOV
        # apparent_diameter_arcsec / (fov_arcsec_per_pixel) → pixels
        fov_arcsec = self.proj.fov_deg * 3600.0
        px_per_screen = min(self.proj.width, self.proj.height)
        arcsec_per_px = fov_arcsec / px_per_screen
        diam_px = body.apparent_diameter_arcsec() / max(1.0, arcsec_per_px)
        r = max(3, min(18, int(diam_px / 2)))

        pygame.draw.circle(surface, color, px, r)

        # Saturn rings: draw thin ellipse around the planet disk
        if body.uid == "SATURN":
            B_deg = saturn_ring_inclination_B(jd)
            # Ring outer radius in same pixel scale as planet disk
            from universe.planet_physics import SATURN_RING_OUTER_KM, PLANET_EQUATORIAL_KM
            ring_scale = SATURN_RING_OUTER_KM / PLANET_EQUATORIAL_KM["SATURN"]
            ring_rx = int(r * ring_scale)                        # horizontal semi-axis
            ring_ry = max(1, int(ring_rx * abs(math.sin(math.radians(B_deg)))))  # vertical
            ring_rect = pygame.Rect(px[0] - ring_rx, px[1] - ring_ry,
                                    ring_rx * 2, ring_ry * 2)
            ring_color = (190, 170, 120)
            pygame.draw.ellipse(surface, ring_color, ring_rect, 1)

        # Label
        if self.show_labels and self.proj.fov_deg < 120:
            lbl_text = f"{body.name} {body.apparent_mag:+.1f}"
            lbl = font_label.render(lbl_text, True, color)
            surface.blit(lbl, (px[0] + r + 3, px[1] - 5))

        # Selection
        if self.selected_obj and getattr(self.selected_obj, 'uid', None) == body.uid:
            pygame.draw.circle(surface, (255, 255, 0), px, r + 5, 1)

    # --- Moon ---
    body = self._moon
    alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                              self.lst_deg, self.observer.latitude_deg)
    if alt > -2:
        px = self.proj.project(alt, az)
        if px and self.proj.is_on_screen(*px):
            fov_arcsec = self.proj.fov_deg * 3600.0
            arcsec_per_px = fov_arcsec / min(self.proj.width, self.proj.height)
            r = max(5, min(30, int(body.apparent_diameter_arcsec() / max(1.0, arcsec_per_px) / 2)))

            color = _PLANET_COLORS["MOON"]
            pygame.draw.circle(surface, color, px, r)

            # Simple phase indicator: fill fraction of circle with dark
            phase = body.phase_fraction   # 0=new, 1=full
            # Shade the dark side (terminator approximation)
            if phase < 0.95:
                shade = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                shade_alpha = int((1.0 - phase) * 180)
                pygame.draw.circle(shade, (0, 4, 14, shade_alpha), (r + 1, r + 1), r)
                # Offset shade to simulate terminator
                offset_x = int((0.5 - phase) * r * 2)
                surface.blit(shade, (px[0] - r - 1 + offset_x, px[1] - r - 1))

            if self.show_labels:
                lbl = font_label.render(
                    f"Moon {body.apparent_mag:+.1f} ({int(phase*100)}%)",
                    True, (200, 200, 200))
                surface.blit(lbl, (px[0] + r + 3, px[1] - 5))

            if self.selected_obj and getattr(self.selected_obj, 'uid', None) == "MOON":
                pygame.draw.circle(surface, (255, 255, 0), px, r + 5, 1)

    # --- Sun (only draw if visible above horizon) ---
    body = self._sun
    alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                              self.lst_deg, self.observer.latitude_deg)
    if alt > -2:
        px = self.proj.project(alt, az)
        if px and self.proj.is_on_screen(*px):
            fov_arcsec = self.proj.fov_deg * 3600.0
            arcsec_per_px = fov_arcsec / min(self.proj.width, self.proj.height)
            r = max(6, min(35, int(body.apparent_diameter_arcsec() / max(1.0, arcsec_per_px) / 2)))

            # Glow: outer halo
            for glow_r, glow_alpha in [(r * 3, 30), (r * 2, 60), (r, 255)]:
                glow_color = (255, 240, 150) if glow_alpha < 100 else (255, 255, 180)
                glow_surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*glow_color, glow_alpha),
                                   (glow_r + 1, glow_r + 1), glow_r)
                surface.blit(glow_surf, (px[0] - glow_r - 1, px[1] - glow_r - 1))

            if self.show_labels:
                lbl = font_label.render("Sun", True, (255, 255, 180))
                surface.blit(lbl, (px[0] + r + 3, px[1] - 5))
```

---

## Task 6 — Click selection for planets

**File:** `ui_new/screen_skychart.py`  
**Where:** `_handle_click` method.

Add a planet check **before** the DSO check (planets have priority over
background objects at same pixel).

```python
def _handle_click(self, pos):
    # ... existing code ...
    best_dist = 20
    best_obj  = None

    # ADD: check planets first (higher priority)
    if self.show_planets:
        all_solar = self._planets + [self._moon, self._sun] + list(self._minor_bodies)
        for body in all_solar:
            alt, az = radec_to_altaz(body.ra_deg, body.dec_deg,
                                      self.lst_deg, self.observer.latitude_deg)
            if alt < -2:
                continue
            px = self.proj.project(alt, az)
            if px and self.proj.is_on_screen(*px):
                # Hitbox = max(8, displayed radius + 4)
                fov_arcsec = self.proj.fov_deg * 3600.0
                arcsec_per_px = fov_arcsec / min(self.proj.width, self.proj.height)
                diam_px = body.apparent_diameter_arcsec() / max(1.0, arcsec_per_px)
                r_hit = max(8, int(diam_px / 2) + 4)
                d = math.hypot(pos[0] - px[0], pos[1] - px[1])
                if d < r_hit and d < best_dist:
                    best_dist, best_obj = d, body

    # ... existing DSO / star checks follow unchanged ...
```

---

## Task 7 — Info panel for planets

**File:** `ui_new/screen_skychart.py`  
**Where:** `_draw_info_panel` method.

The selected object may now be an `OrbitalBody` (planet) instead of a
`SpaceObject`. OrbitalBody inherits from SpaceObject, so `name`, `uid`,
`ra_deg`, `dec_deg` work as before. Add a branch for solar system bodies.

```python
def _draw_info_panel(self, surface, W, H):
    if not self.selected_obj:
        return
    obj = self.selected_obj

    # ... existing panel setup (bg rect, fonts) ...

    # ADD: solar system body branch
    from universe.orbital_body import OrbitalBody
    from universe.planet_physics import saturn_ring_inclination_B, get_planet_physical_data

    if isinstance(obj, OrbitalBody):
        # Header: name
        surface.blit(fn.render(obj.name, True, (0, 255, 120)), (px+8, fy)); fy += 22

        if obj.is_sun:
            row(f"The Sun — G2V star")
            row(f"Mag: {obj.apparent_mag:+.2f}")
            row(f"Distance: 1.000 AU")
            row(f"Diameter: {obj.apparent_diameter_arcsec():.0f}\"")
        elif obj.is_moon:
            row(f"Earth's Moon")
            row(f"Mag: {obj.apparent_mag:+.2f}")
            row(f"Distance: {obj.distance_au * 149597870:.0f} km")
            row(f"Phase: {int(obj.phase_fraction * 100)}%  ({obj.phase_fraction:.2f})")
            row(f"Diameter: {obj.apparent_diameter_arcsec():.0f}\"")
        else:
            phys = get_planet_physical_data(obj.uid)
            row(f"Planet  mag {obj.apparent_mag:+.2f}")
            row(f"Distance: {obj.distance_au:.3f} AU")
            row(f"Diameter: {obj.apparent_diameter_arcsec():.1f}\"")
            if obj.has_phases:
                row(f"Phase: {int(obj.phase_fraction * 100)}%")
            if obj.uid == "SATURN":
                B = saturn_ring_inclination_B(self._tc.jd)
                row(f"Ring tilt B: {B:+.1f}°")
            if obj.description:
                row(obj.description[:55], (100, 150, 100))

        # Alt/Az + radec
        row(obj.radec_str(), (125, 190, 125))
        alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg,
                                  self.lst_deg, self.observer.latitude_deg)
        vc = (0,255,0) if alt > 20 else (255,200,0) if alt > 0 else (200,80,80)
        vis = "above horizon" if alt > 0 else "below horizon"
        row(f"Alt {alt:+.1f}°  Az {az:.1f}°  — {vis}", vc)
        return   # skip the existing star/DSO branch

    # ... existing star / DSO branches unchanged ...
```

---

## Task 8 — Add planets to legend in HUD

**File:** `ui_new/screen_skychart.py`  
**Where:** `_draw_hud` method, in the `legend` list.

```python
# ADD to the legend list (after existing DSO entries):
("●", (210, 190, 140), "Planet"),
("●", (200, 200, 200), "Moon"),
```

---

## Task 9 — Keybinding for planets toggle

**File:** `ui_new/screen_skychart.py`  
**Where:** `handle_input` keyboard section.

```python
# ADD alongside the other toggle keys (G, C, D, L, H):
elif k == pygame.K_p: self._toggle('show_planets')
```

Update hint string in `_draw_hud`:
```python
# Change the existing hint line to include [P]lanets:
hint = (f"  [+/-/Scroll] Zoom  [Drag/Arrows] Pan  "
        f"[G]rid [C]onst [D]SO [L]abels [H]orizon [P]lanets  "
        f"[T]arget [I]maging  |  {hint_time}  |  [ESC] Back")
```

---

## Task 10 — Keyboard shortcut "P" — jump to planet

**Stretch goal, implement after Tasks 1–9 are working.**

When user presses P (and no planet toggle is assigned), cycle through visible
planets and centre the view on each. Keep a `_planet_cursor` int index, increment
on each P press, wrap at end.

---

## Visual Style Reference

- **Consistent with existing chart:** same dark green (`(0, 185, 85)`) for labels, same monospace font, no anti-aliasing on circles.
- **Planet disk colour** matches `_PLANET_COLORS` (warm for inner rocky, blue-grey for ice giants).
- **Saturn rings** should be visible and recognisable even at small size (1px line ellipse).
- **Sun** should have a visible glow but not overwhelm the chart (use alpha blending, 2–3 concentric circles).
- **Labels** only shown when `show_labels = True` (already a toggle).
- **Do not render planets below −2° altitude** (they're behind the Earth fill).

---

## Acceptance Criteria

1. All 8 planets + Moon + Sun visible at correct sky positions in the chart.
2. Saturn shows ring ellipse at any FOV < 90°.
3. Clicking a planet opens the info panel with magnitude, distance, diameter, phase (where applicable).
4. `[P]` key and PLANETS toggle button hide/show all solar system bodies.
5. Planets move correctly when time is accelerated (F2/F3 keys).
6. No performance regression: frame rate stable at 60fps with planets enabled.
7. Cerere and Vesta visible as faint star-like dots when above horizon and within mag_limit.

---

## Files Modified

| File | Change |
|---|---|
| `ui_new/screen_skychart.py` | Main work: init, update, render, click, info panel |

## Files NOT Modified

| File | Reason |
|---|---|
| `universe/orbital_body.py` | Already complete — do not touch |
| `universe/planet_physics.py` | Already complete — do not touch |
| `universe/minor_bodies.py` | Already complete — do not touch |
| `ui_new/screen_imaging.py` | Contains `_expose()` bugfix — do not touch |
| `imaging/allsky_renderer.py` | Not involved in sky chart |

---

## ⚠️ Critical Notes for Copilot

1. **`screen_imaging.py`** has a manual bugfix in `_expose()` (Feb 2026).
   Do NOT modify this file or copy from it carelessly.

2. `OrbitalBody` inherits from `SpaceObject`, so `isinstance(obj, OrbitalBody)`
   is the correct check in `_draw_info_panel` and `_handle_click`.

3. **`update_position(jd, lat, lon)`** must be called every frame before reading
   `ra_deg`, `dec_deg`, `apparent_mag`. Reading stale values (before the first
   update call) will give position (0, 0) for all planets.

4. The `saturn_ring_inclination_B(jd)` function returns degrees, not radians.
   B ≈ 0° in 2025, B ≈ +27° in 2032. Use `abs(math.sin(math.radians(B_deg)))`
   for the vertical axis of the ring ellipse.

5. `body.apparent_diameter_arcsec()` is a **method call** (parentheses required),
   not a property.

6. `MinorBodyCatalog.get_default_bodies()` returns a list of `MinorBody` objects.
   They have `.ra_deg`, `.dec_deg`, `.apparent_mag`, `.name`, `.uid`, and
   `.update_position(jd, lat, lon)` — same interface as `OrbitalBody`.
