"""
Sky Chart — Altazimuth Planetarium View

Renders the sky as seen from the observer (Parma, Italy).
Uses a proper altazimuth projection:
  - Centre of screen = direction you are looking (Az, Alt)
  - Up = altitude increases
  - Horizon = straight horizontal line
  - The sky rotates with time (sidereal)

All data from Universe (single source of truth).
Real objects always visible; procedural only after catalogued.

Controls
--------
  Drag mouse / Arrows   Pan (left/right = Az, up/down = Alt)
  Scroll / +/-          Zoom (FOV)
  G                     Toggle RA/Dec grid
  C                     Toggle constellation lines
  D                     Toggle DSO symbols
  L                     Toggle labels
  H                     Toggle horizon
  T                     Jump to current target
  S                     Set selected as target
  I                     Go to Imaging
  Space                 Pause time
  F1/F2/F3              Time ×1 / ×60 / ×3600
  ESC                   Back
"""

import pygame
import math
from datetime import datetime, timezone
from typing import Optional, Tuple, List

from .base_screen import BaseScreen
from .components import Button
from core.celestial_math import (
    AltAzProjection, OrthographicProjection, ALLSKY_FOV_THRESHOLD,
    PARMA_OBSERVER,
    julian_date, local_sidereal_time,
    radec_to_altaz, altaz_to_radec,
    bv_to_rgb, magnitude_to_radius,
)
from core.earth_renderer import EarthRenderer
from core.constellation_data import get_constellation_lines, get_constellation_labels
from universe import ObjectClass, ObjectSubtype


# ---------------------------------------------------------------------------
# Constellation lines  (ra1, dec1, ra2, dec2) J2000 degrees
# ---------------------------------------------------------------------------
# Constellation lines loaded lazily from constellation_data module
_CONSTELLATION_LINES_CACHE = None

def _get_const_lines():
    global _CONSTELLATION_LINES_CACHE
    if _CONSTELLATION_LINES_CACHE is None:
        _CONSTELLATION_LINES_CACHE = get_constellation_lines()
    return _CONSTELLATION_LINES_CACHE

# DSO colours
_DSO_COLORS = {
    ObjectSubtype.EMISSION:          (220, 80,  80),
    ObjectSubtype.REFLECTION:        (80,  120, 220),
    ObjectSubtype.PLANETARY:         (80,  220, 220),
    ObjectSubtype.SUPERNOVA_REMNANT: (220, 160, 80),
    ObjectSubtype.DARK:              (80,  80,  80),
    ObjectSubtype.SPIRAL:            (160, 200, 255),
    ObjectSubtype.BARRED_SPIRAL:     (140, 180, 255),
    ObjectSubtype.ELLIPTICAL:        (200, 180, 255),
    ObjectSubtype.LENTICULAR:        (180, 180, 220),
    ObjectSubtype.IRREGULAR:         (180, 220, 200),
    ObjectSubtype.DWARF:             (150, 180, 160),
    ObjectSubtype.ACTIVE:            (255, 200, 80),
    ObjectSubtype.OPEN_CLUSTER:      (220, 220, 80),
    ObjectSubtype.GLOBULAR_CLUSTER:  (200, 180, 255),
    ObjectSubtype.GALAXY_CLUSTER:    (255, 160, 200),
}
_DSO_DEFAULT = (160, 160, 160)


class SkychartScreen(BaseScreen):
    """Altazimuth planetarium chart."""

    def __init__(self, state_manager):
        super().__init__("SKYCHART")
        self.state_manager = state_manager
        self.observer = PARMA_OBSERVER

        # Start looking South, 30° altitude — orizzonte visibile a 1/3 dal basso
        self.proj = AltAzProjection(
            center_az=180.0, center_alt=30.0,
            fov_deg=80.0, width=1280, height=720,
        )

        # Allsky mode state
        self._allsky_mode  = False       # True when OrthographicProjection active
        self._pre_allsky_az  = 180.0     # az/alt to restore when exiting allsky
        self._pre_allsky_alt = 30.0
        self._pre_allsky_fov = 80.0

        # Time
        self.time_utc    = datetime.now(timezone.utc)
        self.time_paused = False
        self.time_speed  = 1.0
        self._time_accum = 0.0
        self.lst_deg     = 0.0
        self._update_lst()

        # Drag state
        self.dragging    = False
        self.drag_start  = None
        self.drag_az     = 0.0
        self.drag_alt    = 0.0
        self._click_moved = False

        # Selection
        self.selected_obj  = None
        self._next_screen  = None

        # Toggles
        self.show_grid         = True
        self.show_const        = True
        self.show_const_labels = False    # constellation name labels (off by default)
        self.show_dso          = True
        self.show_labels       = True
        self.show_horizon      = True
        self.show_horizon_fill = True
        self.show_cardinals    = True

        # 3D Earth renderer
        self._earth = EarthRenderer()

        self._create_buttons()

    # -----------------------------------------------------------------------
    # Setup
    # -----------------------------------------------------------------------

    def _create_buttons(self):
        self.buttons = {
            'zoom_in':    Button(10, 30, 35, 26, "+",            callback=lambda: self._zoom(0.8)),
            'zoom_out':   Button(50, 30, 35, 26, "-",            callback=lambda: self._zoom(1.25)),
            'north':      Button(10, 65, 80, 26, "NORTH",        callback=lambda: self._look(0,   30)),
            'south':      Button(10, 98, 80, 26, "SOUTH",        callback=lambda: self._look(180, 30)),
            'zenith':     Button(10,131, 80, 26, "ZENITH",       callback=lambda: self._look(self.proj.center_az, 89)),
            'allsky':     Button(10,164, 80, 26, "ALL SKY",      callback=self._goto_allsky),
            'set_target': Button(10,205,130, 26, "SET TARGET",   callback=self._set_as_target),
            'go_imaging': Button(10,238,130, 26, "\u2192 IMAGING", callback=self._go_imaging),
        }
        self._toggles = {
            'grid':         ('show_grid',         "GRID"),
            'const':        ('show_const',        "CONST"),
            'const_labels': ('show_const_labels', "CONST.L"),
            'dso':          ('show_dso',          "DSO"),
            'labels':       ('show_labels',       "LABELS"),
            'horizon':      ('show_horizon',      "HORIZON"),
            'horiz_fill':   ('show_horizon_fill', "H.FILL"),
            'cardinals':    ('show_cardinals',    "COMPASS"),
        }
        self._tbtn = {}
        y = 280
        for key, (attr, label) in self._toggles.items():
            self._tbtn[key] = Button(10, y, 80, 22, label,
                                     callback=lambda a=attr: self._toggle(a))
            y += 27

    def _zoom(self, f: float):
        """
        Zoom in (f < 1) or out (f > 1).
        Transition rules:
          - Normal mode zoom-out past ALLSKY_FOV_THRESHOLD → enter allsky
          - Allsky mode zoom-in → exit allsky, restore previous view
        """
        if self._allsky_mode:
            if f < 1.0:   # zoom in → exit allsky
                self._exit_allsky()
        else:
            new_fov = self.proj.fov_deg * f
            if new_fov >= ALLSKY_FOV_THRESHOLD:
                self._enter_allsky()
            else:
                self.proj.zoom(f)

    def _enter_allsky(self):
        """Transition to allsky orthographic mode."""
        # Save current view so we can restore it
        self._pre_allsky_az  = self.proj.center_az
        self._pre_allsky_alt = self.proj.center_alt
        self._pre_allsky_fov = self.proj.fov_deg
        # Switch to orthographic
        W = getattr(self.proj, 'width',  1280)
        H = getattr(self.proj, 'height', 720)
        self.proj        = OrthographicProjection(W, H)
        self._allsky_mode = True

    def _exit_allsky(self):
        """Transition back to normal perspective mode."""
        W = self.proj.width
        H = self.proj.height
        # Restore the FOV just below the threshold
        restore_fov = min(self._pre_allsky_fov, ALLSKY_FOV_THRESHOLD * 0.95)
        self.proj = AltAzProjection(
            center_az  = self._pre_allsky_az,
            center_alt = self._pre_allsky_alt,
            fov_deg    = restore_fov,
            width=W, height=H,
        )
        self._allsky_mode = False

    def _goto_allsky(self):
        """Button: enter allsky mode explicitly."""
        if not self._allsky_mode:
            self._enter_allsky()

    def _goto_normal(self):
        """Button: exit allsky mode (also bound to zoom-in from allsky)."""
        if self._allsky_mode:
            self._exit_allsky()

    def _toggle(self, attr: str):
        setattr(self, attr, not getattr(self, attr))

    # -----------------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------------

    def _look(self, az: float, alt: float):
        self.proj.center_az  = az % 360
        self.proj.center_alt = max(-90.0, min(90.0, alt))

    def _goto_target(self):
        state = self.state_manager.get_state()
        if state.selected_target_ra is not None:
            alt, az = radec_to_altaz(
                state.selected_target_ra, state.selected_target_dec or 0.0,
                self.lst_deg, self.observer.latitude_deg)
            self._look(az, alt)

    def _set_as_target(self):
        if self.selected_obj:
            state = self.state_manager.get_state()
            state.selected_target     = self.selected_obj.name
            state.selected_target_ra  = self.selected_obj.ra_deg
            state.selected_target_dec = self.selected_obj.dec_deg

    def _go_imaging(self):
        self._set_as_target()
        if self.selected_obj and self.selected_obj.obj_class != ObjectClass.STAR:
            self._next_screen = 'IMAGING'

    # -----------------------------------------------------------------------
    # Time
    # -----------------------------------------------------------------------

    def _update_lst(self):
        jd = julian_date(self.time_utc)
        self.lst_deg = local_sidereal_time(jd, self.observer.longitude_deg)

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self):
        super().on_enter()
        self.time_utc     = datetime.now(timezone.utc)
        self._update_lst()
        self._next_screen = None

    def on_exit(self):
        super().on_exit()

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_input(self, events) -> Optional[str]:
        mp = pygame.mouse.get_pos()
        for btn in self.buttons.values():  btn.update(mp)
        for btn in self._tbtn.values():    btn.update(mp)

        for event in events:
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_ESCAPE: return 'OBSERVATORY'
                elif k in (pygame.K_EQUALS, pygame.K_PLUS,  pygame.K_KP_PLUS):  self._zoom(0.8)
                elif k in (pygame.K_MINUS,  pygame.K_KP_MINUS):                  self._zoom(1.25)

                step = self.proj.fov_deg * 0.15
                if not self._allsky_mode:   # pan locked in allsky
                    if   k == pygame.K_LEFT:  self.proj.pan(-step, 0)
                    elif k == pygame.K_RIGHT: self.proj.pan( step, 0)
                    elif k == pygame.K_UP:    self.proj.pan(0,  step)
                    elif k == pygame.K_DOWN:  self.proj.pan(0, -step)

                if k == pygame.K_g: self._toggle('show_grid')
                elif k == pygame.K_c: self._toggle('show_const')
                elif k == pygame.K_d: self._toggle('show_dso')
                elif k == pygame.K_l: self._toggle('show_labels')
                elif k == pygame.K_h: self._toggle('show_horizon')
                elif k == pygame.K_t: self._goto_target()
                elif k == pygame.K_s: self._set_as_target()
                elif k == pygame.K_i: self._go_imaging()
                elif k == pygame.K_SPACE: self.time_paused = not self.time_paused
                elif k == pygame.K_F1: self.time_speed = 1.0
                elif k == pygame.K_F2: self.time_speed = 60.0
                elif k == pygame.K_F3: self.time_speed = 3600.0

            elif event.type == pygame.MOUSEWHEEL:
                self._zoom(0.85 if event.y > 0 else 1.15)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                consumed = (any(b.handle_event(event) for b in self.buttons.values()) or
                            any(b.handle_event(event) for b in self._tbtn.values()))
                if not consumed:
                    self.dragging     = True
                    self.drag_start   = event.pos
                    self.drag_az      = self.proj.center_az
                    self.drag_alt     = self.proj.center_alt
                    self._click_moved = False   # track if mouse moved during drag

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Pass UP to buttons
                for b in self.buttons.values(): b.handle_event(event)
                for b in self._tbtn.values():   b.handle_event(event)
                # If mouse didn't move much → it was a click, not a drag
                if self.dragging and not self._click_moved:
                    self._handle_click(event.pos)
                self.dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if self.dragging and self.drag_start:
                    dx = event.pos[0] - self.drag_start[0]
                    dy = event.pos[1] - self.drag_start[1]
                    if abs(dx) > 3 or abs(dy) > 3:
                        self._click_moved = True
                    if not self._allsky_mode:   # pan disabled in allsky
                        self.proj.center_az  = (self.drag_az  + dx * self.proj.scale) % 360
                        self.proj.center_alt = max(-90.0, min(90.0,
                                                self.drag_alt - dy * self.proj.scale))

        result, self._next_screen = self._next_screen, None
        return result

    # -----------------------------------------------------------------------
    # Click selection
    # -----------------------------------------------------------------------

    def _handle_click(self, pos: Tuple[int, int]):
        universe  = self.state_manager.get_universe()
        best_dist = 20  # hitbox aumentata da 18 a 20 pixel
        best_obj  = None
        
        # Get current magnitude limit for context
        fov = self.proj.fov_deg
        if self._allsky_mode:
            mag_limit = 5.0
        elif fov > 90: mag_limit = 6.0
        elif fov > 60: mag_limit = 7.0
        elif fov > 30: mag_limit = 8.5
        elif fov > 15: mag_limit = 9.5
        elif fov > 5:  mag_limit = 10.5
        elif fov > 1:  mag_limit = 11.5
        else:          mag_limit = 12.0

        if self.show_dso:
            for obj in universe.get_dso():
                alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg,
                                          self.lst_deg, self.observer.latitude_deg)
                px = self.proj.project(alt, az)
                if px and self.proj.is_on_screen(*px):
                    d = math.hypot(pos[0]-px[0], pos[1]-px[1])
                    if d < best_dist:
                        best_dist, best_obj = d, obj

        # Check stars up to current magnitude limit (not all 389k)
        for obj in universe.get_stars():
            if obj.mag > mag_limit: continue  # Use dynamic limit instead of fixed 4.5
            alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg,
                                      self.lst_deg, self.observer.latitude_deg)
            if alt < -5: continue
            px = self.proj.project(alt, az)
            if px and self.proj.is_on_screen(*px):
                # Hitbox: minimum 3 pixels for faint stars
                r = max(3, magnitude_to_radius(obj.mag))
                d = math.hypot(pos[0]-px[0], pos[1]-px[1])
                if d < best_dist + r:  # Expand hitbox by star radius
                    best_dist, best_obj = d, obj

        self.selected_obj = best_obj

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float):
        if not self.time_paused:
            import datetime as dtmod
            self._time_accum += dt * self.time_speed
            if self._time_accum >= 1.0:
                secs = int(self._time_accum)
                self.time_utc    = self.time_utc + dtmod.timedelta(seconds=secs)
                self._time_accum -= secs
                self._update_lst()

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface):
        W, H = surface.get_width(), surface.get_height()

        # Resize projection if window size changed
        if self.proj.width != W or self.proj.height != H:
            if self._allsky_mode:
                self.proj._resize(W, H)
            else:
                self.proj.width  = W
                self.proj.height = H
                self.proj.cx = W // 2
                self.proj.cy = H // 2

        # Dynamic magnitude limit — con 389k stelle (Gaia+Hipparcos) mostriamo molto di più
        fov = self.proj.fov_deg
        if self._allsky_mode:
            mag_limit = 5.0   # allsky: stelle fino a mag 5 (costellazioni chiarissime)
        elif fov > 90: mag_limit = 6.0   # wide: più stelle per contesto
        elif fov > 60: mag_limit = 7.0   # medium-wide
        elif fov > 30: mag_limit = 8.5   # medium
        elif fov > 15: mag_limit = 9.5   # narrow
        elif fov > 5:  mag_limit = 10.5  # very narrow: inizia a vedere stelle deboli
        elif fov > 1:  mag_limit = 11.5  # extreme zoom: mostra quasi tutto
        else:          mag_limit = 12.0  # maximum zoom: tutte le 389k stelle

        # Sky background
        surface.fill((2, 4, 14))

        if self.show_grid:    self._draw_grid(surface, W, H)
        if self.show_const:   self._draw_constellations(surface)
        if self.show_const and self.show_const_labels:
            self._draw_constellation_labels(surface)
        visible_stars = self._draw_stars(surface, mag_limit)
        if self.show_dso:     self._draw_dso(surface)

        # 3D Earth — occludes stars below horizon
        if self.show_horizon:
            self._earth.render(surface, self.proj,
                               show_fill=self.show_horizon_fill,
                               show_line=not self._allsky_mode)

        # Allsky: draw hemisphere circle border + N/S/E/W labels on rim
        if self._allsky_mode:
            self._draw_allsky_circle(surface, W, H)

        if self.show_cardinals: self._draw_cardinals(surface, W, H)
        self._draw_info_panel(surface, W, H)
        self._draw_hud(surface, W, H, visible_stars, mag_limit)

        # Left panel buttons
        for btn in self.buttons.values():
            btn.draw(surface)

        # Toggle buttons with active highlight
        for key, (attr, _) in self._toggles.items():
            btn = self._tbtn[key]
            btn.draw(surface)
            if getattr(self, attr):
                pygame.draw.rect(surface, (0, 210, 90),
                                 btn.rect.inflate(4, 4), 2)

    # -----------------------------------------------------------------------
    # Draw: grid
    # -----------------------------------------------------------------------

    def _draw_grid(self, surface, W, H):
        """Draw altitude circles and azimuth lines"""
        col_alt = (0, 50, 28)
        col_az  = (0, 35, 55)
        font    = pygame.font.SysFont('monospace', 9)

        # In allsky (stereo) use more altitude circles; in normal use fewer
        if self.proj._use_stereo():
            alt_steps = range(0, 90, 15)
            az_steps  = range(0, 360, 30)
        else:
            alt_steps = range(0, 90, 15)
            az_steps  = range(0, 360, 30)

        # Altitude circles
        for alt in alt_steps:
            prev = None
            for az in range(0, 362, 2):
                px = self.proj.project(float(alt), float(az))
                if px and self.proj.is_on_screen(*px, margin=5):
                    if prev and math.hypot(px[0]-prev[0], px[1]-prev[1]) < 60:
                        pygame.draw.line(surface, col_alt, prev, px, 1)
                    prev = px
                else:
                    prev = None
            # Label: place at the azimuth pointing toward screen centre
            # (so label is visible regardless of view direction)
            label_az = self.proj.center_az
            px_lbl = self.proj.project(float(alt), label_az)
            if px_lbl and self.proj.is_on_screen(*px_lbl, margin=-5):
                surface.blit(font.render(f"{alt}°", True, (0, 80, 42)),
                             (px_lbl[0]+3, px_lbl[1]-8))

        # Azimuth lines
        for az in az_steps:
            prev = None
            for alt in range(0, 91, 2):
                px = self.proj.project(float(alt), float(az))
                if px and self.proj.is_on_screen(*px, margin=5):
                    if prev and math.hypot(px[0]-prev[0], px[1]-prev[1]) < 60:
                        pygame.draw.line(surface, col_az, prev, px, 1)
                    prev = px
                else:
                    prev = None

    # -----------------------------------------------------------------------
    # Draw: constellations
    # -----------------------------------------------------------------------

    def _draw_constellations(self, surface):
        color = (0, 55, 90)
        for lines in _get_const_lines().values():
            for ra1, dec1, ra2, dec2 in lines:
                alt1, az1 = radec_to_altaz(ra1, dec1, self.lst_deg,
                                            self.observer.latitude_deg)
                alt2, az2 = radec_to_altaz(ra2, dec2, self.lst_deg,
                                            self.observer.latitude_deg)
                if alt1 < -10 and alt2 < -10:
                    continue
                p1 = self.proj.project(alt1, az1)
                p2 = self.proj.project(alt2, az2)
                if p1 and p2:
                    on1 = self.proj.is_on_screen(*p1, margin=60)
                    on2 = self.proj.is_on_screen(*p2, margin=60)
                    if (on1 or on2) and math.hypot(p1[0]-p2[0], p1[1]-p2[1]) < 500:
                        pygame.draw.line(surface, color, p1, p2, 1)

    def _draw_constellation_labels(self, surface):
        """Draw constellation name labels at their geometric centres."""
        font  = pygame.font.SysFont('monospace', 11, bold=False)
        color = (0, 90, 120)   # blue-teal, distinct from star labels (green)
        for name, (ra, dec) in get_constellation_labels().items():
            alt, az = radec_to_altaz(ra, dec, self.lst_deg,
                                      self.observer.latitude_deg)
            if alt < -5:
                continue
            px = self.proj.project(alt, az)
            if px and self.proj.is_on_screen(*px, margin=-10):
                txt = font.render(name.upper(), True, color)
                surface.blit(txt, (px[0] - txt.get_width()//2,
                                   px[1] - txt.get_height()//2))

    # -----------------------------------------------------------------------
    # Draw: stars
    # -----------------------------------------------------------------------

    def _draw_stars(self, surface, mag_limit: float) -> int:
        """Draw stars. Returns count of visible stars."""
        universe = self.state_manager.get_universe()
        font = pygame.font.SysFont('monospace', 9)
        
        # Pre-compute FOV bounds in RA/Dec for fast rejection
        # (rough bounding box — slightly oversized to avoid clipping)
        fov = self.proj.fov_deg
        center_alt = self.proj.center_alt
        center_az  = self.proj.center_az
        
        # Convert center alt/az to RA/Dec for bounding box
        from core.celestial_math import altaz_to_radec
        center_ra, center_dec = altaz_to_radec(center_alt, center_az,
                                                self.lst_deg,
                                                self.observer.latitude_deg)
        
        # Bounding box: FOV/2 + margin in each direction
        margin = fov / 2.0 + 5.0
        dec_min = max(-90, center_dec - margin)
        dec_max = min(+90, center_dec + margin)
        
        # RA wrapping: expand by margin
        ra_margin = min(180, margin / max(0.01, math.cos(math.radians(center_dec))))
        ra_min = (center_ra - ra_margin) % 360
        ra_max = (center_ra + ra_margin) % 360
        ra_wraps = ra_min > ra_max  # Crosses 0/360 boundary
        
        visible_count = 0
        for obj in universe.get_stars():
            if obj.mag > mag_limit: continue
            
            # Fast RA/Dec bounding box rejection (avoids expensive projection)
            dec = obj.dec_deg
            if dec < dec_min or dec > dec_max: continue
            
            ra = obj.ra_deg
            if not ra_wraps:
                if ra < ra_min or ra > ra_max: continue
            else:
                if ra_min < ra < ra_max: continue  # Outside wrap-around range
            
            alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg,
                                      self.lst_deg, self.observer.latitude_deg)
            if alt < -2: continue
            px = self.proj.project(alt, az)
            if not px or not self.proj.is_on_screen(*px): continue
            
            visible_count += 1
            r     = magnitude_to_radius(obj.mag)
            color = bv_to_rgb(obj.bv_color)
            if r <= 1:
                surface.set_at(px, color)
            else:
                pygame.draw.circle(surface, color, px, r)

            if self.show_labels and obj.mag < 2.2 and fov < 80:
                surface.blit(font.render(obj.name, True, (160, 160, 120)),
                             (px[0]+r+2, px[1]-5))

        # Highlight selected star
        if self.selected_obj and self.selected_obj.obj_class == ObjectClass.STAR:
            alt, az = radec_to_altaz(self.selected_obj.ra_deg,
                                      self.selected_obj.dec_deg,
                                      self.lst_deg, self.observer.latitude_deg)
            px = self.proj.project(alt, az)
            if px and self.proj.is_on_screen(*px):
                pygame.draw.circle(surface, (255, 255, 0), px,
                                   magnitude_to_radius(self.selected_obj.mag)+4, 1)
        
        return visible_count

    # -----------------------------------------------------------------------
    # Draw: DSO
    # -----------------------------------------------------------------------

    def _draw_dso(self, surface):
        universe = self.state_manager.get_universe()
        font = pygame.font.SysFont('monospace', 9)

        for obj in universe.get_dso():
            alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg,
                                      self.lst_deg, self.observer.latitude_deg)
            if alt < -2: continue
            px = self.proj.project(alt, az)
            if not px or not self.proj.is_on_screen(*px): continue

            color = _DSO_COLORS.get(obj.subtype, _DSO_DEFAULT)
            s = max(4, min(20, int(obj.size_arcmin /
                           max(0.1, self.proj.fov_deg / self.proj.height * 60) * 3)))

            self._draw_dso_symbol(surface, px, s, color, obj)

            if self.show_labels and self.proj.fov_deg < 60:
                cat = obj.meta.get("catalog", "")
                num = obj.meta.get("catalog_num", "")
                lbl = f"{cat}{num}" if cat else obj.uid
                surface.blit(font.render(lbl, True, color), (px[0]+s+2, px[1]-5))

            if self.selected_obj and self.selected_obj.uid == obj.uid:
                pygame.draw.circle(surface, (255, 255, 0), px, s+5, 1)

    def _draw_dso_symbol(self, surface, px, s, color, obj):
        x, y = px
        sub  = obj.subtype
        if sub == ObjectSubtype.OPEN_CLUSTER:
            pygame.draw.circle(surface, color, px, s, 1)
            for i in range(0, 360, 60):
                a = math.radians(i)
                pygame.draw.circle(surface, color,
                    (int(x+s*0.6*math.cos(a)), int(y+s*0.6*math.sin(a))), 1)
        elif sub == ObjectSubtype.GLOBULAR_CLUSTER:
            pygame.draw.circle(surface, color, px, s, 1)
            pygame.draw.line(surface, color, (x-s,y), (x+s,y), 1)
            pygame.draw.line(surface, color, (x,y-s), (x,y+s), 1)
        elif sub in (ObjectSubtype.EMISSION, ObjectSubtype.SUPERNOVA_REMNANT,
                     ObjectSubtype.DARK, ObjectSubtype.PROTOSTELLAR):
            pygame.draw.rect(surface, color, pygame.Rect(x-s, y-s, s*2, s*2), 1)
        elif sub == ObjectSubtype.REFLECTION:
            pygame.draw.rect(surface, color, pygame.Rect(x-s, y-s, s*2, s*2), 1)
            pygame.draw.line(surface, color, (x-s//2,y-s//2), (x+s//2,y+s//2), 1)
        elif sub == ObjectSubtype.PLANETARY:
            pygame.draw.circle(surface, color, px, s, 1)
            pygame.draw.circle(surface, color, px, max(1, s//2), 1)
        elif sub in (ObjectSubtype.SPIRAL, ObjectSubtype.BARRED_SPIRAL,
                     ObjectSubtype.ELLIPTICAL, ObjectSubtype.LENTICULAR,
                     ObjectSubtype.IRREGULAR, ObjectSubtype.DWARF,
                     ObjectSubtype.ACTIVE, ObjectSubtype.GALAXY_CLUSTER):
            pygame.draw.ellipse(surface, color,
                                pygame.Rect(x-s, y-s//2, s*2, s), 1)
        else:
            pygame.draw.circle(surface, color, px, max(3, s), 1)

    # -----------------------------------------------------------------------
    # Draw: horizon
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Draw: cardinal points
    # -----------------------------------------------------------------------

    def _draw_cardinals(self, surface, W, H):
        """N / S / E / W labels on the horizon"""
        font = pygame.font.SysFont('monospace', 13, bold=True)
        cardinals = [("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
                     ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)]
        for label, az in cardinals:
            px = self.proj.project(1.0, float(az))
            if px and self.proj.is_on_screen(*px, margin=5):
                color = (0, 220, 80) if label in ("N","S","E","W") else (0, 130, 50)
                txt = font.render(label, True, color)
                surface.blit(txt, (px[0] - txt.get_width()//2,
                                   px[1] - txt.get_height()//2))

    # -----------------------------------------------------------------------
    # Draw: info panel
    # -----------------------------------------------------------------------

    def _draw_info_panel(self, surface, W, H):
        if not self.selected_obj:
            return
        obj = self.selected_obj

        pw, ph = 315, 215
        px, py = W - pw - 10, 30

        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((0, 16, 10, 215))
        pygame.draw.rect(bg, (0, 150, 70), (0, 0, pw, ph), 1)
        surface.blit(bg, (px, py))

        fn = pygame.font.SysFont('monospace', 13)
        fs = pygame.font.SysFont('monospace', 11)
        fy = py + 8

        def row(text, col=(175, 255, 175)):
            nonlocal fy
            surface.blit(fs.render(text, True, col), (px+8, fy))
            fy += 16

        cat = obj.meta.get("catalog", "")
        num = obj.meta.get("catalog_num", "")
        uid_lbl = f"{cat}{num}" if cat else obj.uid
        surface.blit(fn.render(f"{uid_lbl}: {obj.name}", True, (0, 255, 120)),
                     (px+8, fy)); fy += 22

        if obj.obj_class == ObjectClass.STAR:
            bv = obj.bv_color
            col_str = ("Blue-white" if bv < 0.0 else "White" if bv < 0.4 else
                       "Yellow-white" if bv < 0.8 else "Orange" if bv < 1.4 else "Red")
            row(f"Star  mag {obj.mag:.2f}  B-V {bv:.2f}")
            row(f"Colour: {col_str}")
        else:
            row(f"Type: {obj.subtype.value.replace('_',' ').title()}")
            row(f"Mag: {obj.mag:.1f}   Size: {obj.size_arcmin:.1f}'")
            row(f"Dist: {obj.distance_str()}")
            if obj.constellation:
                row(f"Const: {obj.constellation}")

        row(obj.radec_str(), (125, 190, 125))

        alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg,
                                  self.lst_deg, self.observer.latitude_deg)
        vc = (0,255,0) if alt > 20 else (255,200,0) if alt > 0 else (200,80,80)
        vis = "above horizon" if alt > 0 else "below horizon"
        row(f"Alt {alt:+.1f}°  Az {az:.1f}°  — {vis}", vc)

        if obj.description:
            words = obj.description.split()
            line, lines = "", []
            for w in words:
                if len(line)+len(w)+1 > 42:
                    lines.append(line); line = w
                else:
                    line = (line+" "+w).strip()
            if line: lines.append(line)
            for l in lines[:3]:
                row(l, (100, 150, 100))

        # Highlight set_target button if already selected
        state = self.state_manager.get_state()
        if state.selected_target == obj.name:
            pygame.draw.rect(surface, (0, 255, 100),
                             self.buttons['set_target'].rect.inflate(4, 4), 2)

    # -----------------------------------------------------------------------
    # Draw: allsky circle
    # -----------------------------------------------------------------------

    def _draw_allsky_circle(self, surface, W, H):
        """
        In allsky mode: draw the hemisphere border circle + N/E/S/W labels on rim,
        and darken outside the circle.
        """
        cx = self.proj.cx
        cy = self.proj.cy
        R  = int(self.proj.radius)

        # Darken the area outside the circle (letterbox effect)
        mask = pygame.Surface((W, H), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 200))
        pygame.draw.circle(mask, (0, 0, 0, 0), (cx, cy), R)
        surface.blit(mask, (0, 0))

        # Circle border
        pygame.draw.circle(surface, (0, 140, 60), (cx, cy), R, 2)

        # Cardinal labels on the rim
        font = pygame.font.SysFont('monospace', 14, bold=True)
        for label, az in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
            px = self.proj.project(0.5, float(az))
            if px:
                col = (0, 255, 100)
                txt = font.render(label, True, col)
                # Nudge label outward from the rim
                dx = px[0] - cx; dy = px[1] - cy
                nx = px[0] + int(dx * 0.07) - txt.get_width() // 2
                ny = px[1] + int(dy * 0.07) - txt.get_height() // 2
                surface.blit(txt, (nx, ny))

        # Altitude circles: 30°, 60° rings
        for alt in [30, 60]:
            pts = []
            for az in range(0, 361, 3):
                p = self.proj.project(float(alt), float(az))
                if p:
                    pts.append(p)
            if len(pts) > 2:
                pygame.draw.lines(surface, (0, 55, 30), True, pts, 1)

        # "ALLSKY" label + hint top-left
        f = pygame.font.SysFont('monospace', 11)
        surface.blit(f.render("◉ ALLSKY — scroll up or [+] to return", True,
                               (0, 180, 80)), (80, 35))

    # -----------------------------------------------------------------------
    # Draw: HUD
    # -----------------------------------------------------------------------

    def _draw_hud(self, surface, W, H, visible_stars: int, mag_limit: float):
        font = pygame.font.SysFont('monospace', 11)

        # Top strip
        strip = pygame.Surface((W, 26), pygame.SRCALPHA)
        strip.fill((0, 22, 10, 195))
        surface.blit(strip, (0, 0))

        lst_h = int(self.lst_deg / 15)
        lst_m = int((self.lst_deg / 15 - lst_h) * 60)
        sp    = "PAUSED" if self.time_paused else f"x{self.time_speed:.0f}"

        if self._allsky_mode:
            info = (f"  {self.time_utc.strftime('%Y-%m-%d %H:%M UTC')}  |  "
                    f"LST {lst_h:02d}h{lst_m:02d}m  |  "
                    f"ALLSKY — zenith centred  |  {sp}  |  "
                    f"Stars: {visible_stars:,} (mag<{mag_limit:.1f})")
        else:
            info = (f"  {self.time_utc.strftime('%Y-%m-%d %H:%M UTC')}  |  "
                    f"LST {lst_h:02d}h{lst_m:02d}m  |  "
                    f"Az {self.proj.center_az:.1f}°  Alt {self.proj.center_alt:+.1f}°  |  "
                    f"FOV {self.proj.fov_deg:.1f}°  |  {sp}  |  "
                    f"Stars: {visible_stars:,} (mag<{mag_limit:.1f})")
        surface.blit(font.render(info, True, (0, 185, 85)), (0, 5))

        title = pygame.font.SysFont('monospace', 12, bold=True)
        t = title.render("SKY CHART  —  Parma 44.8°N 10.3°E", True, (0, 195, 85))
        surface.blit(t, (W//2 - t.get_width()//2, 5))

        if self._allsky_mode:
            hint = "  [+/Scroll up] Zoom in to exit  |  [Space] Pause  [ESC] Back"
        else:
            hint = ("  [+/-/Scroll] Zoom  [Drag/Arrows] Pan  "
                    "[G]rid [C]onst [D]SO [L]abels [H]orizon  "
                    "[T] Target  [S] Set  [I] Imaging  [Space] Pause  [ESC] Back")
        surface.blit(font.render(hint, True, (0, 80, 45)), (0, H-16))

        # Cursor Alt/Az + RA/Dec
        mx, my = pygame.mouse.get_pos()
        alt_c, az_c = self.proj.unproject(mx, my)
        ra_c, dec_c = altaz_to_radec(alt_c, az_c, self.lst_deg,
                                      self.observer.latitude_deg)
        rh = int(ra_c/15); rm = int((ra_c/15-rh)*60)
        cursor = (f"  Cursor  Az {az_c:.1f}°  Alt {alt_c:+.1f}°  "
                  f"|  RA {rh:02d}h{rm:02d}m  Dec {dec_c:+.1f}°")
        surface.blit(font.render(cursor, True, (0, 110, 58)), (0, H-30))

        # Legend
        legend = [
            ("●", (220, 220, 80),  "Open Cluster"),
            ("⊕", (200, 180, 255), "Globular Cluster"),
            ("□", (220, 80,  80),  "Emission Nebula"),
            ("○", (80,  220, 220), "Planetary Nebula"),
            ("○", (160, 200, 255), "Galaxy"),
        ]
        lf = pygame.font.SysFont('monospace', 10)
        lx, ly = W - 165, 30
        for sym, col, lbl in legend:
            surface.blit(lf.render(f"{sym} {lbl}", True, col), (lx, ly))
            ly += 14
