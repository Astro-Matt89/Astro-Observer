"""
Sky Chart Screen

Geocentric star chart with:
- Real stars from Yale BSC (4000+)
- DSO from combined Messier+NGC catalog
- Fog of war: DSO locked until imaged
- Constellation lines (unlockable)
- RA/Dec grid
- Real-time geocentric projection (Parma, Italy)
- Pan/zoom navigation
- Object selection and info
"""

import pygame
import math
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from .base_screen import BaseScreen
from .components import Button
from core.celestial_math import (
    SkyProjection, Observer, PARMA_OBSERVER,
    julian_date, local_sidereal_time,
    radec_to_altaz, bv_to_rgb, magnitude_to_radius
)
from catalogs.deep_sky import load_combined_catalog, DeepSkyObject, DSOType
from catalogs.star_catalog import STAR_CATALOG


# Constellation lines - pairs of star names (RA, Dec of endpoints)
# Format: list of (ra1, dec1, ra2, dec2) in degrees
CONSTELLATION_LINES = {
    "Orion": [
        (81.283, 6.350, 84.053, -1.202),   # Bellatrix - Alnilam
        (84.053, -1.202, 88.793, 7.407),    # Alnilam - Betelgeuse
        (84.053, -1.202, 78.634, -8.202),   # Alnilam - Rigel
        (85.190, -1.943, 84.053, -1.202),   # Alnitak - Alnilam
        (85.190, -1.943, 83.002, -0.299),   # Alnitak - Mintaka
        (83.002, -0.299, 81.283, 6.350),    # Mintaka - Bellatrix
        (86.939, -9.670, 78.634, -8.202),   # Saiph - Rigel
        (86.939, -9.670, 85.190, -1.943),   # Saiph - Alnitak
        (83.858, 9.934, 88.793, 7.407),     # Meissa - Betelgeuse
        (83.858, 9.934, 81.283, 6.350),     # Meissa - Bellatrix
    ],
    "Ursa Major": [
        (165.460, 56.383, 178.458, 53.695), # Merak - Phecda
        (178.458, 53.695, 183.857, 57.033), # Phecda - Megrez
        (183.857, 57.033, 165.460, 56.383), # Megrez - Merak
        (183.857, 57.033, 193.507, 55.960), # Megrez - Alioth
        (193.507, 55.960, 200.981, 54.926), # Alioth - Mizar
        (200.981, 54.926, 206.886, 49.313), # Mizar - Alkaid
    ],
    "Cassiopeia": [
        (2.295, 59.150, 10.127, 56.537),    # Caph - Schedar
        (10.127, 56.537, 14.177, 60.717),   # Schedar - Gamma Cas
        (14.177, 60.717, 21.454, 60.235),   # Gamma - Delta
        (21.454, 60.235, 28.599, 63.670),   # Delta - Epsilon
    ],
    "Leo": [
        (152.093, 11.967, 154.993, 19.842), # Regulus - Algieba
        (154.993, 19.842, 154.174, 23.418), # Algieba - Adhafera
        (152.093, 11.967, 168.527, 20.524), # Regulus - Zosma
        (168.527, 20.524, 177.265, 14.572), # Zosma - Denebola
        (168.527, 20.524, 168.560, 15.430), # Zosma - Chertan
    ],
    "Cygnus": [
        (310.358, 45.280, 305.557, 40.257), # Deneb - Sadr
        (305.557, 40.257, 296.244, 45.131), # Sadr - Fawaris
        (305.557, 40.257, 307.365, 51.730), # Sadr - Rukh
        (305.557, 40.257, 311.553, 33.970), # Sadr - Gienah
        (305.557, 40.257, 292.680, 27.960), # Sadr - Albireo
    ],
    "Scorpius": [
        (240.083, -22.622, 247.352, -26.432), # Dschubba - Antares
        (247.352, -26.432, 253.085, -34.293), # Antares - Epsilon Sco
        (253.085, -34.293, 256.440, -37.103), # Epsilon - Mu Sco
        (256.440, -37.103, 263.402, -37.103), # Mu - Shaula
        (263.402, -37.103, 264.330, -37.296), # Shaula - Lesath
        (241.359, -19.806, 240.083, -22.622), # Graffias - Dschubba
    ],
    "Bootes": [
        (213.915, 19.182, 208.671, 18.398), # Arcturus - Muphrid
        (213.915, 19.182, 221.247, 27.074), # Arcturus - Izar
        (221.247, 27.074, 218.019, 38.308), # Izar - Seginus
        (213.915, 19.182, 217.952, 30.371), # Arcturus - Rho Boo
    ],
    "Virgo": [
        (201.298, -11.161, 190.415, -1.449), # Spica - Porrima
        (190.415, -1.449, 195.544, 10.959),  # Porrima - Vindemiatrix
        (195.544, 10.959, 177.674, 0.667),   # Vindemiatrix - Zavijava
    ],
    "Lyra": [
        (279.235, 38.784, 282.520, 33.363),  # Vega - Sheliak
        (282.520, 33.363, 284.736, 32.690),  # Sheliak - Sulafat
        (284.736, 32.690, 279.235, 38.784),  # Sulafat - Vega
    ],
    "Gemini": [
        (113.649, 31.888, 116.329, 28.026),  # Castor - Pollux
        (113.649, 31.888, 95.740, 25.132),   # Castor - Mebsuda
        (116.329, 28.026, 97.241, 20.570),   # Pollux - Mekbuda
        (99.428, 16.399, 97.241, 20.570),    # Alhena - Mekbuda
        (99.428, 16.399, 95.740, 25.132),    # Alhena - Mebsuda
    ],
    "Perseus": [
        (51.081, 49.861, 47.042, 40.956),    # Mirphak - Algol
        (51.081, 49.861, 52.913, 47.713),    # Mirphak - Delta Per
        (52.913, 47.713, 58.468, 39.997),    # Delta - Epsilon Per
    ],
}

# DSO rendering symbols by type
DSO_SYMBOLS = {
    DSOType.OPEN_CLUSTER:     "oc",     # circle with dots
    DSOType.GLOBULAR_CLUSTER: "gc",     # circle with cross
    DSOType.HII_REGION:       "hii",    # square
    DSOType.REFLECTION:       "rn",     # square dashed
    DSOType.PLANETARY:        "pn",     # circle with outer ring
    DSOType.SNR:              "snr",    # broken circle
    DSOType.SPIRAL:           "sg",     # ellipse
    DSOType.ELLIPTICAL:       "eg",     # ellipse filled
    DSOType.IRREGULAR:        "ig",     # irregular
    DSOType.LENTICULAR:       "lg",     # ellipse+line
    DSOType.GALAXY_CLUSTER:   "gcl",    # dots pattern
    DSOType.DARK:             "dn",     # dashed square
}


class SkychartScreen(BaseScreen):
    """
    Geocentric Sky Chart
    
    Real-time star chart showing the sky as seen from the observer's
    location (Parma, Italy by default).
    """
    
    def __init__(self, state_manager):
        super().__init__("SKYCHART")
        self.state_manager = state_manager
        
        # Observer (Parma, Italy)
        self.observer = PARMA_OBSERVER
        
        # Projection (initial: show southern sky facing south)
        self.projection = SkyProjection(
            center_ra=180.0,    # RA center (degrees)
            center_dec=20.0,    # Dec center
            scale_deg_per_px=0.08,
            width=1280,
            height=720
        )
        
        # Time
        self.time_utc = datetime.now(timezone.utc)
        self.time_paused = False
        self.time_speed = 1.0  # Real-time
        self._last_time_update = 0.0
        self._time_elapsed = 0.0
        
        # Computed LST
        self.lst_deg = 0.0
        self._update_lst()
        
        # Navigation state
        self.dragging = False
        self.drag_start = None
        self.drag_ra = 0.0
        self.drag_dec = 0.0
        
        # Stars (loaded once)
        self.stars = STAR_CATALOG  # List of (name, ra, dec, mag, bv)
        
        # DSO catalog
        self.dso_catalog = load_combined_catalog()
        
        # Selected object
        self.selected_star = None    # (name, ra, dec, mag, bv)
        self.selected_dso = None     # DeepSkyObject
        
        # Display options
        self.show_grid       = True
        self.show_const      = True
        self.show_dso        = True
        self.show_labels     = True
        self.show_horizon    = True
        self.magnitude_limit = 6.5
        
        # Render cache
        self._star_cache = []
        self._dso_cache  = []
        self._cache_valid = False
        
        # Buttons
        self._create_buttons()
    
    def _create_buttons(self):
        """Create UI buttons"""
        self.buttons = {
            'zoom_in':    Button(10, 100, 40, 30, "+",        callback=lambda: self._zoom(0.7)),
            'zoom_out':   Button(10, 140, 40, 30, "-",        callback=lambda: self._zoom(1.4)),
            'north':      Button(10, 200, 80, 30, "N ↑",      callback=self._goto_north),
            'south':      Button(10, 240, 80, 30, "S ↓",      callback=self._goto_south),
            'tonight':    Button(10, 300, 80, 30, "NOW",       callback=self._goto_transit),
            'set_target': Button(10, 360, 130, 30, "SET TARGET", callback=self._set_selected_as_target),
            'go_imaging': Button(10, 400, 130, 30, "→ IMAGING", callback=self._go_to_imaging),
        }
        self._next_screen = None
    
    def _zoom(self, factor: float):
        self.projection.zoom(factor)
        self._cache_valid = False
    
    def _set_selected_as_target(self):
        """Set the selected DSO as the imaging target"""
        if self.selected_dso:
            state = self.state_manager.get_state()
            state.selected_target = self.selected_dso.name
            state.selected_target_ra = self.selected_dso.ra_deg
            state.selected_target_dec = self.selected_dso.dec_deg
    
    def _go_to_imaging(self):
        """Set target and navigate to imaging"""
        self._set_selected_as_target()
        if self.selected_dso:
            self._next_screen = 'IMAGING'
    
    def _handle_click(self, pos):
        """Handle click on sky chart - select nearest object"""
        min_dist = 15  # pixels
        self.selected_dso  = None
        self.selected_star = None

        # Check DSOs first
        if self.show_dso:
            for dso in self.dso_catalog.objects.values():
                px = self.projection.project(dso.ra_deg, dso.dec_deg)
                if px and self.projection.is_on_screen(px[0], px[1]):
                    d = math.sqrt((pos[0]-px[0])**2 + (pos[1]-px[1])**2)
                    if d < min_dist:
                        min_dist = d
                        self.selected_dso = dso

        # Check bright stars (only up to mag 4.0 for click detection)
        for name, ra, dec, mag, bv in self.stars:
            if mag > 4.0:
                continue
            px = self.projection.project(ra, dec)
            if px and self.projection.is_on_screen(px[0], px[1]):
                d = math.sqrt((pos[0]-px[0])**2 + (pos[1]-px[1])**2)
                if d < min_dist:
                    min_dist = d
                    self.selected_star = (name, ra, dec, mag, bv)
                    self.selected_dso  = None

    def _update_lst(self):
        """Update Local Sidereal Time"""
        jd = julian_date(self.time_utc)
        self.lst_deg = local_sidereal_time(jd, self.observer.longitude_deg)
    
    def _goto_north(self):
        self.projection.center_dec = 60.0
        self.projection.center_ra = 0.0
        self._cache_valid = False
    
    def _goto_south(self):
        self.projection.center_dec = -30.0
        self.projection.center_ra = 180.0
        self._cache_valid = False
    
    def _goto_transit(self):
        """Center on meridian at observer latitude"""
        self.projection.center_ra = self.lst_deg
        self.projection.center_dec = self.observer.latitude_deg
        self._cache_valid = False
    
    def _goto_target(self):
        """Center on selected target"""
        state = self.state_manager.get_state()
        if state.selected_target_ra is not None:
            self.projection.center_ra = state.selected_target_ra
            self.projection.center_dec = state.selected_target_dec or 0.0
            self._cache_valid = False
    
    def on_enter(self):
        super().on_enter()
        self.time_utc = datetime.now(timezone.utc)
        self._update_lst()
        self._cache_valid = False
        self._next_screen = None
        # Update projection size to actual screen size
        # (will be updated in first render call)
    
    def on_exit(self):
        super().on_exit()
    
    def handle_input(self, events: list) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        
        for btn in self.buttons.values():
            btn.update(mouse_pos)
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                # Navigation
                if event.key == pygame.K_ESCAPE:
                    return 'OBSERVATORY'
                
                # Zoom
                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    self.projection.zoom(0.7)
                    self._cache_valid = False
                elif event.key == pygame.K_MINUS:
                    self.projection.zoom(1.4)
                    self._cache_valid = False
                
                # Pan
                pan_step = self.projection.scale * 50
                if event.key == pygame.K_LEFT:
                    self.projection.pan(-pan_step, 0)
                    self._cache_valid = False
                elif event.key == pygame.K_RIGHT:
                    self.projection.pan(pan_step, 0)
                    self._cache_valid = False
                elif event.key == pygame.K_UP:
                    self.projection.pan(0, pan_step)
                    self._cache_valid = False
                elif event.key == pygame.K_DOWN:
                    self.projection.pan(0, -pan_step)
                    self._cache_valid = False
                
                # Toggles
                elif event.key == pygame.K_g:
                    self.show_grid = not self.show_grid
                elif event.key == pygame.K_c:
                    self.show_const = not self.show_const
                elif event.key == pygame.K_d:
                    self.show_dso = not self.show_dso
                elif event.key == pygame.K_l:
                    self.show_labels = not self.show_labels
                elif event.key == pygame.K_h:
                    self.show_horizon = not self.show_horizon
                
                # Go to current target
                elif event.key == pygame.K_t:
                    self._goto_target()
                
                # Set selected as target
                elif event.key == pygame.K_s:
                    self._set_selected_as_target()
                
                # Go to imaging with selected target
                elif event.key == pygame.K_i:
                    self._go_to_imaging()
                
                # Time speed
                elif event.key == pygame.K_SPACE:
                    self.time_paused = not self.time_paused
                elif event.key == pygame.K_F1:
                    self.time_speed = 1.0
                elif event.key == pygame.K_F2:
                    self.time_speed = 60.0      # 1 min/sec
                elif event.key == pygame.K_F3:
                    self.time_speed = 3600.0    # 1 hr/sec
            
            # Mouse scroll = zoom
            elif event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    self.projection.zoom(0.85)
                else:
                    self.projection.zoom(1.15)
                self._cache_valid = False
            
            # Mouse drag = pan
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Check buttons first
                    clicked_btn = False
                    for btn in self.buttons.values():
                        if btn.handle_event(event):
                            clicked_btn = True
                            self._cache_valid = False
                            break
                    
                    if not clicked_btn:
                        # Check for DSO/star click
                        self._handle_click(event.pos)
                        
                        self.dragging = True
                        self.drag_start = event.pos
                        self.drag_ra  = self.projection.center_ra
                        self.drag_dec = self.projection.center_dec
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging = False
            
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging and self.drag_start:
                    dx = event.pos[0] - self.drag_start[0]
                    dy = event.pos[1] - self.drag_start[1]
                    delta_ra  = -dx * self.projection.scale
                    delta_dec =  dy * self.projection.scale
                    self.projection.center_ra  = (self.drag_ra  + delta_ra)  % 360.0
                    self.projection.center_dec = max(-85.0, min(85.0, self.drag_dec + delta_dec))
                    self._cache_valid = False
        
        return self._next_screen or None
        """Handle click on sky chart - select nearest object"""
        min_dist = 15  # pixels
        self.selected_dso  = None
        self.selected_star = None
        
        # Check DSOs first
        if self.show_dso:
            for dso in self.dso_catalog.objects.values():
                px = self.projection.project(dso.ra_deg, dso.dec_deg)
                if px and self.projection.is_on_screen(px[0], px[1]):
                    d = math.sqrt((pos[0]-px[0])**2 + (pos[1]-px[1])**2)
                    if d < min_dist:
                        min_dist = d
                        self.selected_dso = dso
        
        # Check bright stars
        for name, ra, dec, mag, bv in self.stars:
            if mag > 4.0:
                continue
            px = self.projection.project(ra, dec)
            if px and self.projection.is_on_screen(px[0], px[1]):
                d = math.sqrt((pos[0]-px[0])**2 + (pos[1]-px[1])**2)
                if d < min_dist:
                    min_dist = d
                    self.selected_star = (name, ra, dec, mag, bv)
                    self.selected_dso  = None
    
    def update(self, dt: float):
        """Update time and LST"""
        if not self.time_paused:
            self._time_elapsed += dt * self.time_speed
            if self._time_elapsed >= 1.0:
                import datetime as dtmod
                secs = int(self._time_elapsed)
                self.time_utc = self.time_utc + dtmod.timedelta(seconds=secs)
                self._time_elapsed -= secs
                self._update_lst()
                self._cache_valid = False
    
    def render(self, surface: pygame.Surface):
        """Render sky chart"""
        W, H = surface.get_width(), surface.get_height()
        
        # Update projection size if needed
        if self.projection.width != W or self.projection.height != H:
            self.projection.width  = W
            self.projection.height = H
            self.projection.cx = W // 2
            self.projection.cy = H // 2
            self._cache_valid = False
        
        # Black sky background
        surface.fill((0, 0, 0))
        
        # Draw layers
        if self.show_grid:
            self._draw_grid(surface)
        
        if self.show_horizon:
            self._draw_horizon(surface)
        
        if self.show_const:
            self._draw_constellations(surface)
        
        self._draw_stars(surface)
        
        if self.show_dso:
            self._draw_dso(surface)
        
        # Info overlay
        self._draw_info_panel(surface, W, H)
        self._draw_hud(surface, W, H)
        
        # Buttons
        for btn in self.buttons.values():
            btn.draw(surface)
    
    def _draw_grid(self, surface: pygame.Surface):
        """Draw RA/Dec grid"""
        color = (0, 50, 25)  # Dark green
        
        # Dec lines (horizontal)
        for dec in range(-80, 90, 10):
            prev_px = None
            for ra in range(0, 365, 2):
                px = self.projection.project(float(ra), float(dec))
                if px and self.projection.is_on_screen(px[0], px[1]):
                    if prev_px:
                        # Only draw if close (no wraparound)
                        if abs(px[0] - prev_px[0]) < 100:
                            pygame.draw.line(surface, color, prev_px, px, 1)
                    prev_px = px
                else:
                    prev_px = None
        
        # RA lines (vertical)
        for ra in range(0, 360, 15):  # Every hour
            prev_px = None
            for dec in range(-90, 91, 2):
                px = self.projection.project(float(ra), float(dec))
                if px and self.projection.is_on_screen(px[0], px[1]):
                    if prev_px:
                        if abs(px[1] - prev_px[1]) < 100:
                            pygame.draw.line(surface, color, prev_px, px, 1)
                    prev_px = px
                else:
                    prev_px = None
        
        # Grid labels
        font = pygame.font.SysFont('monospace', 10)
        for ra in range(0, 360, 30):
            px = self.projection.project(float(ra), self.projection.center_dec - 5)
            if px and self.projection.is_on_screen(px[0], px[1]):
                h = ra // 15
                label = f"{h}h"
                txt = font.render(label, True, (0, 80, 40))
                surface.blit(txt, (px[0] - 8, px[1]))
    
    def _draw_horizon(self, surface: pygame.Surface):
        """Draw local horizon"""
        color = (30, 100, 30)  # Green
        
        prev_px = None
        for az in range(0, 362, 2):
            # Horizon = alt 0°
            # Convert Az/Alt to RA/Dec via inverse transform
            alt = 0.0
            a  = math.radians(az)
            la = math.radians(self.observer.latitude_deg)
            ha = math.atan2(-math.sin(a), math.tan(la) * math.cos(0) - math.cos(a) * math.sin(0))
            dec = math.asin(math.sin(la) * math.sin(0) + math.cos(la) * math.cos(0) * math.cos(a))
            ra = math.degrees(math.radians(self.lst_deg) - ha) % 360.0
            
            px = self.projection.project(ra, math.degrees(dec))
            if px and self.projection.is_on_screen(px[0], px[1], margin=50):
                if prev_px and abs(px[0] - prev_px[0]) < 200:
                    pygame.draw.line(surface, color, prev_px, px, 2)
                prev_px = px
            else:
                prev_px = None
        
        # North label on horizon
        px = self.projection.project(
            (self.lst_deg + 180) % 360.0,
            self.observer.latitude_deg - 90
        )
        if px and self.projection.is_on_screen(px[0], px[1], margin=20):
            font = pygame.font.SysFont('monospace', 11)
            txt = font.render("N", True, color)
            surface.blit(txt, (px[0]-4, px[1]-10))
    
    def _draw_constellations(self, surface: pygame.Surface):
        """Draw constellation lines"""
        color = (40, 40, 80)  # Dark blue
        
        for const_name, lines in CONSTELLATION_LINES.items():
            for ra1, dec1, ra2, dec2 in lines:
                p1 = self.projection.project(ra1, dec1)
                p2 = self.projection.project(ra2, dec2)
                if p1 and p2:
                    if (self.projection.is_on_screen(p1[0], p1[1]) or
                        self.projection.is_on_screen(p2[0], p2[1])):
                        # Don't draw if too far apart (wraparound)
                        if abs(p1[0]-p2[0]) < 400 and abs(p1[1]-p2[1]) < 400:
                            pygame.draw.line(surface, color, p1, p2, 1)
        
        # Constellation name labels
        if self.show_labels and self.projection.scale < 0.3:
            font = pygame.font.SysFont('monospace', 10)
            const_centers = {
                "Orion":      (83.8, 5.0),
                "Ursa Major": (185.0, 57.0),
                "Cassiopeia": (10.0, 60.0),
                "Leo":        (165.0, 15.0),
                "Cygnus":     (305.0, 43.0),
                "Scorpius":   (250.0, -28.0),
                "Bootes":     (215.0, 30.0),
                "Virgo":      (190.0, 0.0),
                "Gemini":     (107.0, 25.0),
            }
            for name, (ra, dec) in const_centers.items():
                px = self.projection.project(ra, dec)
                if px and self.projection.is_on_screen(px[0], px[1]):
                    txt = font.render(name.upper(), True, (50, 50, 100))
                    surface.blit(txt, (px[0] - len(name)*3, px[1]))
    
    def _draw_stars(self, surface: pygame.Surface):
        """Draw stars from catalog"""
        mag_limit = min(self.magnitude_limit, 6.5)
        
        for name, ra, dec, mag, bv in self.stars:
            if mag > mag_limit:
                continue
            
            px = self.projection.project(ra, dec)
            if not px or not self.projection.is_on_screen(px[0], px[1]):
                continue
            
            # Check if above horizon
            alt, az = radec_to_altaz(ra, dec, self.lst_deg, self.observer.latitude_deg)
            if alt < -1.0:
                continue
            
            # Star color and size
            color = bv_to_rgb(bv)
            r = magnitude_to_radius(mag, scale=1.2)
            
            # Dim below horizon (atmospheric effect)
            if alt < 5.0:
                factor = (alt + 1.0) / 6.0
                color = tuple(int(c * factor) for c in color)
            
            pygame.draw.circle(surface, color, px, r)
            
            # Labels for bright stars
            if self.show_labels and mag < 2.5 and self.projection.scale < 0.2:
                font = pygame.font.SysFont('monospace', 10)
                txt = font.render(name, True, (150, 150, 100))
                surface.blit(txt, (px[0] + r + 2, px[1] - 5))
    
    def _draw_dso(self, surface: pygame.Surface):
        """Draw DSO objects"""
        career = self.state_manager.get_career_mode()
        
        for dso in self.dso_catalog.objects.values():
            px = self.projection.project(dso.ra_deg, dso.dec_deg)
            if not px or not self.projection.is_on_screen(px[0], px[1]):
                continue
            
            # Check if above horizon
            alt, az = radec_to_altaz(dso.ra_deg, dso.dec_deg,
                                      self.lst_deg, self.observer.latitude_deg)
            
            # Check fog of war
            dso_name = dso.name
            is_discovered = dso_name in career.stats.objects_imaged
            is_below = alt < -5.0
            
            # Determine symbol size based on zoom
            base_size = max(4, int(dso.size_arcmin / self.projection.scale / 60 * 0.5))
            base_size = min(20, base_size)
            
            if is_discovered:
                self._draw_dso_symbol(surface, dso, px, base_size, alt)
            else:
                # Unknown: show as faint question mark (if above horizon)
                if not is_below:
                    self._draw_dso_unknown(surface, px, base_size)
    
    def _draw_dso_symbol(self, surface, dso, px, size, alt):
        """Draw a specific DSO symbol based on type"""
        # Color by type
        type_colors = {
            DSOType.OPEN_CLUSTER:     (200, 200, 100),  # Yellow
            DSOType.GLOBULAR_CLUSTER: (200, 150, 200),  # Purple
            DSOType.HII_REGION:       (200, 80,  80),   # Red
            DSOType.REFLECTION:       (80,  120, 200),  # Blue
            DSOType.PLANETARY:        (80,  200, 200),  # Cyan
            DSOType.SNR:              (200, 100, 200),  # Magenta
            DSOType.SPIRAL:           (150, 200, 150),  # Green
            DSOType.ELLIPTICAL:       (150, 150, 200),  # Light blue
            DSOType.IRREGULAR:        (180, 180, 100),  # Yellow-green
            DSOType.LENTICULAR:       (150, 180, 200),  # Light cyan
        }
        color = type_colors.get(dso.dso_type, (180, 180, 180))
        
        # Dim if low on horizon
        if alt < 10.0:
            factor = max(0.3, alt / 10.0)
            color = tuple(int(c * factor) for c in color)
        
        s = size
        x, y = px
        
        sym = DSO_SYMBOLS.get(dso.dso_type, "sg")
        
        if sym == "oc":
            # Open cluster: dashed circle
            pygame.draw.circle(surface, color, (x, y), s, 1)
            for i in range(6):
                a = i * math.pi / 3
                dx, dy = int(s * 0.5 * math.cos(a)), int(s * 0.5 * math.sin(a))
                pygame.draw.circle(surface, color, (x+dx, y+dy), 1)
        
        elif sym == "gc":
            # Globular cluster: circle with cross
            pygame.draw.circle(surface, color, (x, y), s, 1)
            pygame.draw.line(surface, color, (x-s, y), (x+s, y), 1)
            pygame.draw.line(surface, color, (x, y-s), (x, y+s), 1)
        
        elif sym == "hii":
            # Emission nebula: square
            pygame.draw.rect(surface, color, (x-s, y-s, s*2, s*2), 1)
        
        elif sym == "pn":
            # Planetary: circle with outer ring
            pygame.draw.circle(surface, color, (x, y), max(2, s//2), 1)
            pygame.draw.circle(surface, color, (x, y), s, 1)
        
        elif sym == "sg" or sym == "eg" or sym == "lg":
            # Galaxy: ellipse
            ratio = 0.5 if sym == "sg" else 0.7
            pygame.draw.ellipse(surface, color,
                               (x-s, y-int(s*ratio), s*2, int(s*ratio*2)), 1)
        
        elif sym == "snr":
            # SNR: broken circle
            for i in range(0, 360, 45):
                a = math.radians(i)
                dx1 = int(s * 0.8 * math.cos(a))
                dy1 = int(s * 0.8 * math.sin(a))
                dx2 = int(s * math.cos(a))
                dy2 = int(s * math.sin(a))
                pygame.draw.line(surface, color, (x+dx1, y+dy1), (x+dx2, y+dy2), 1)
        
        else:
            # Default: small circle
            pygame.draw.circle(surface, color, (x, y), max(3, s), 1)
        
        # Label
        if self.show_labels and self.projection.scale < 0.15:
            font = pygame.font.SysFont('monospace', 9)
            label = f"M{dso.catalog_num}" if dso.catalog == "M" else f"NGC{dso.catalog_num}"
            txt = font.render(label, True, color)
            surface.blit(txt, (x + s + 2, y - 5))
        
        # Highlight if selected
        if self.selected_dso and self.selected_dso.id == dso.id:
            pygame.draw.circle(surface, (255, 255, 0), (x, y), s + 4, 1)
    
    def _draw_dso_unknown(self, surface, px, size):
        """Draw unknown (fog of war) DSO"""
        color = (60, 60, 60)
        x, y = px
        font = pygame.font.SysFont('monospace', 10)
        txt = font.render("?", True, color)
        surface.blit(txt, (x - 4, y - 6))
    
    def _draw_info_panel(self, surface: pygame.Surface, W: int, H: int):
        """Draw info panel for selected object"""
        if not self.selected_dso and not self.selected_star:
            # Hide action buttons when nothing selected
            self.buttons['set_target'].visible = False if hasattr(self.buttons['set_target'], 'visible') else True
            self.buttons['go_imaging'].visible = False if hasattr(self.buttons['go_imaging'], 'visible') else True
            return
        
        career = self.state_manager.get_career_mode()
        
        panel_w, panel_h = 310, 200
        panel_x = W - panel_w - 10
        panel_y = 80
        
        # Background
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((0, 20, 10, 210))
        pygame.draw.rect(panel_surf, (0, 180, 90), (0, 0, panel_w, panel_h), 1)
        surface.blit(panel_surf, (panel_x, panel_y))
        
        font_n = pygame.font.SysFont('monospace', 13)
        font_s = pygame.font.SysFont('monospace', 11)
        y = panel_y + 10
        
        if self.selected_dso:
            dso = self.selected_dso
            is_discovered = dso.name in career.stats.objects_imaged
            
            label = f"M{dso.catalog_num}" if dso.catalog == "M" else f"NGC {dso.catalog_num}"
            name_txt = font_n.render(f"{label}: {dso.name}", True, (0, 255, 128))
            surface.blit(name_txt, (panel_x + 8, y)); y += 20
            
            if is_discovered:
                type_txt = font_s.render(f"Type: {dso.dso_type.value}", True, (180, 255, 180))
                surface.blit(type_txt, (panel_x + 8, y)); y += 16
                
                mag_txt = font_s.render(f"Mag: {dso.mag:.1f}  Size: {dso.size_arcmin:.1f}'",
                                        True, (180, 255, 180))
                surface.blit(mag_txt, (panel_x + 8, y)); y += 16
                
                ra_h = int(dso.ra_deg / 15)
                ra_m = int((dso.ra_deg / 15 - ra_h) * 60)
                coord_txt = font_s.render(f"RA:{ra_h:02d}h{ra_m:02d}m  Dec:{dso.dec_deg:+.1f}°",
                                          True, (180, 255, 180))
                surface.blit(coord_txt, (panel_x + 8, y)); y += 16
                
                dist = dso.distance_ly or 0
                if dist > 1e6:
                    dist_str = f"{dist/1e6:.1f} Mly"
                elif dist > 1000:
                    dist_str = f"{dist/1000:.1f} kly"
                else:
                    dist_str = f"{dist:.0f} ly"
                dist_txt = font_s.render(f"Dist: {dist_str}", True, (180, 255, 180))
                surface.blit(dist_txt, (panel_x + 8, y)); y += 16
                
                # Altitude
                alt, az = radec_to_altaz(dso.ra_deg, dso.dec_deg,
                                          self.lst_deg, self.observer.latitude_deg)
                vis_color = (0, 255, 0) if alt > 20 else (255, 200, 0) if alt > 0 else (200, 80, 80)
                alt_txt = font_s.render(f"Alt: {alt:.1f}°  Az: {az:.1f}°", True, vis_color)
                surface.blit(alt_txt, (panel_x + 8, y)); y += 16
                
                const = getattr(dso, 'constellation', '')
                const_txt = font_s.render(f"Const: {const}", True, (120, 200, 120))
                surface.blit(const_txt, (panel_x + 8, y)); y += 16
                
                disc_txt = font_s.render("✓ DISCOVERED", True, (0, 255, 0))
                surface.blit(disc_txt, (panel_x + 8, y))
            else:
                unk_txt = font_s.render("Unknown object", True, (100, 100, 100))
                surface.blit(unk_txt, (panel_x + 8, y)); y += 16
                
                # Show coords even for undiscovered (so player can aim)
                ra_h = int(dso.ra_deg / 15)
                ra_m = int((dso.ra_deg / 15 - ra_h) * 60)
                coord_txt = font_s.render(f"RA:{ra_h:02d}h{ra_m:02d}m  Dec:{dso.dec_deg:+.1f}°",
                                          True, (120, 120, 80))
                surface.blit(coord_txt, (panel_x + 8, y)); y += 16
                
                alt, az = radec_to_altaz(dso.ra_deg, dso.dec_deg,
                                          self.lst_deg, self.observer.latitude_deg)
                vis_color = (0, 200, 0) if alt > 20 else (180, 150, 0) if alt > 0 else (150, 60, 60)
                alt_txt = font_s.render(f"Alt: {alt:.1f}°", True, vis_color)
                surface.blit(alt_txt, (panel_x + 8, y)); y += 16
                
                img_txt = font_s.render("→ Image it to reveal!", True, (150, 150, 50))
                surface.blit(img_txt, (panel_x + 8, y))
            
            # Action buttons: reposition near panel
            btn_y = panel_y + panel_h + 8
            self.buttons['set_target'].rect.x = panel_x
            self.buttons['set_target'].rect.y = btn_y
            self.buttons['go_imaging'].rect.x = panel_x
            self.buttons['go_imaging'].rect.y = btn_y + 36
            
            # Draw action buttons
            self.buttons['set_target'].draw(surface)
            self.buttons['go_imaging'].draw(surface)
            
            # Check if this is current target (highlight set_target)
            state = self.state_manager.get_state()
            if state.selected_target == dso.name:
                pygame.draw.rect(surface, (0, 255, 128),
                                 self.buttons['set_target'].rect.inflate(4, 4), 2)
        
        elif self.selected_star:
            name, ra, dec, mag, bv = self.selected_star
            name_txt = font_n.render(name, True, (255, 255, 200))
            surface.blit(name_txt, (panel_x + 8, y)); y += 20
            
            mag_txt = font_s.render(f"Magnitude: {mag:.2f}", True, (200, 200, 150))
            surface.blit(mag_txt, (panel_x + 8, y)); y += 16
            
            color_str = "Blue-White" if bv < 0.1 else "White" if bv < 0.4 else \
                       "Yellow-White" if bv < 0.8 else "Orange" if bv < 1.4 else "Red"
            col_txt = font_s.render(f"Color: {color_str} (B-V={bv:.2f})", True, (200, 200, 150))
            surface.blit(col_txt, (panel_x + 8, y)); y += 16
            
            ra_h = int(ra / 15)
            ra_m = int((ra / 15 - ra_h) * 60)
            coord_txt = font_s.render(f"RA:{ra_h:02d}h{ra_m:02d}m  Dec:{dec:+.1f}°",
                                      True, (200, 200, 150))
            surface.blit(coord_txt, (panel_x + 8, y)); y += 16
            
            alt, az = radec_to_altaz(ra, dec, self.lst_deg, self.observer.latitude_deg)
            vis_color = (0, 255, 0) if alt > 20 else (255, 200, 0) if alt > 0 else (200, 80, 80)
            alt_txt = font_s.render(f"Alt: {alt:.1f}°  Az: {az:.1f}°", True, vis_color)
            surface.blit(alt_txt, (panel_x + 8, y))
    
    def _draw_hud(self, surface: pygame.Surface, W: int, H: int):
        """Draw HUD: time, LST, cursor coordinates"""
        font = pygame.font.SysFont('monospace', 11)
        
        # Top bar background
        hud_surf = pygame.Surface((W, 25), pygame.SRCALPHA)
        hud_surf.fill((0, 30, 15, 180))
        surface.blit(hud_surf, (0, 0))
        
        # Time info
        time_str = self.time_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        lst_h = int(self.lst_deg / 15)
        lst_m = int((self.lst_deg / 15 - lst_h) * 60)
        
        txt = font.render(
            f"⏱ {time_str}  |  LST: {lst_h:02d}h{lst_m:02d}m  |  "
            f"Center: RA={self.projection.center_ra:.1f}° Dec={self.projection.center_dec:+.1f}°  |  "
            f"FOV: {self.projection.fov_deg:.1f}°  |  "
            f"{'⏸' if self.time_paused else '▶'} x{self.time_speed:.0f}",
            True, (0, 200, 100)
        )
        surface.blit(txt, (5, 5))
        
        # Mouse coordinates
        mx, my = pygame.mouse.get_pos()
        ra, dec = self.projection.unproject(mx, my)
        ra_h = int(ra / 15)
        ra_m = int((ra / 15 - ra_h) * 60)
        mouse_txt = font.render(
            f"Cursor: RA {ra_h:02d}h{ra_m:02d}m  Dec {dec:+.1f}°",
            True, (0, 150, 80)
        )
        surface.blit(mouse_txt, (5, H - 20))
        
        # Controls legend
        ctrl_txt = font.render(
            "[+/-/Scroll] Zoom  [Drag/Arrows] Pan  [G]rid  [C]onst  [D]SO  [L]abels  [H]orizon  "
            "[Space] Pause  [T] Target  [S] Set  [I] Imaging  [ESC] Back",
            True, (0, 100, 60)
        )
        surface.blit(ctrl_txt, (5, H - 35))
        
        # Title
        title_font = pygame.font.SysFont('monospace', 13, bold=True)
        title = title_font.render("SKY CHART  —  Parma, Italy  44.8°N  10.3°E", True, (0, 200, 100))
        surface.blit(title, (W//2 - title.get_width()//2, 5))
        
        # Legend (top right)
        legend_x = W - 160
        legend_y = 30
        legend_items = [
            ("●", (200, 200, 100), "Open Cluster"),
            ("⊕", (200, 150, 200), "Globular Cluster"),
            ("□", (200, 80,  80),  "Emission Neb."),
            ("○", (80,  200, 200), "Planetary Neb."),
            ("○", (150, 200, 150), "Galaxy"),
            ("?", (60,  60,  60),  "Undiscovered"),
        ]
        lfont = pygame.font.SysFont('monospace', 10)
        for sym, col, label in legend_items:
            sym_txt = lfont.render(f"{sym} {label}", True, col)
            surface.blit(sym_txt, (legend_x, legend_y))
            legend_y += 14
