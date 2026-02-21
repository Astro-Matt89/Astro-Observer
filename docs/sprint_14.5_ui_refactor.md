# Sprint 14.5 — UI Foundation Refactor

**Goal:** Riorganizzare l'architettura UI con Main Menu, Content Manager, Observable Now panel, e navigation unificata. Zero breaking changes alla fisica/rendering — solo UI layer.

**Prerequisito:** Sprint 14b completato (cloud layer funzionante).

**Durata stimata:** 3-4 giorni, ~600 righe nuove + ~400 righe refactor.

---

## Ordine di implementazione (IMPORTANTE)

Copilot DEVE seguire questo ordine per evitare import circolari e funzioni mancanti:

1. **Task 1** — `ui_new/components.py` — WeatherWidget + ObservablePanel components
2. **Task 2** — `ui_new/navigation_manager.py` — NavigationManager (nuovo)
3. **Task 3** — `ui_new/screen_main_menu.py` — MainMenuScreen (nuovo)
4. **Task 4** — `ui_new/screen_content_manager.py` — ContentManagerScreen (nuovo)
5. **Task 5** — `ui_new/screen_equipment.py` — Refactor esistente (mode switch Career/Explore)
6. **Task 6** — `ui_new/screen_observatory.py` — Aggiungi WeatherWidget + navigation hotkeys
7. **Task 7** — `ui_new/screen_skychart.py` — Aggiungi ObservablePanel + navigation hotkeys
8. **Task 8** — `ui_new/screen_imaging.py` — Aggiungi tabs + navigation hotkeys
9. **Task 9** — `main_app.py` — Wire NavigationManager + route to MainMenu

---

## Task 1 — Nuovi componenti in `ui_new/components.py`

**File:** `ui_new/components.py` (modificare esistente, aggiungere alla fine)

### 1a — WeatherWidget component

```python
# ADD at end of ui_new/components.py

class WeatherWidget:
    """
    Persistent weather widget (80x40px) shown in top-right of every screen.
    
    Usage:
        widget = WeatherWidget(x=1200, y=10, weather_system=ws)
        widget.update(jd=tc.jd)
        widget.render(surface)
    """
    
    def __init__(self, x: int, y: int, weather_system):
        """
        Args:
            x, y: top-left position (usually W-90, 10)
            weather_system: WeatherSystem instance from atmosphere.weather
        """
        self.x = x
        self.y = y
        self._weather = weather_system
        self._expanded = False
        self._transparency = 1.0
        self._seeing = 2.5
        self._condition = "clear"
    
    def update(self, jd: float) -> None:
        """Update weather data for current JD."""
        self._transparency = self._weather.transparency(jd)
        self._seeing = self._weather.seeing(jd)
        self._condition = self._weather.condition(jd).value
    
    def handle_event(self, event) -> bool:
        """
        Handle mouse click to toggle expanded view.
        Returns True if event was consumed.
        """
        import pygame
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # left click
                rect = pygame.Rect(self.x, self.y, 80, 40)
                if rect.collidepoint(event.pos):
                    self._expanded = not self._expanded
                    return True
        return False
    
    def render(self, surface: 'pygame.Surface') -> None:
        """Render compact or expanded widget."""
        import pygame
        
        if self._expanded:
            self._render_expanded(surface)
        else:
            self._render_compact(surface)
    
    def _render_compact(self, surface: 'pygame.Surface') -> None:
        """Render compact 80x40 widget."""
        import pygame
        
        # Background
        bg = pygame.Surface((80, 40), pygame.SRCALPHA)
        bg.fill((0, 18, 10, 210))
        pygame.draw.rect(bg, (0, 100, 50), (0, 0, 80, 40), 1)
        surface.blit(bg, (self.x, self.y))
        
        # Icon
        ICONS = {
            "clear": "★", "mostly_clear": "◑",
            "partly_cloudy": "◒", "cloudy": "●", "overcast": "■"
        }
        icon = ICONS.get(self._condition, "?")
        
        font = pygame.font.SysFont('monospace', 11)
        icon_surf = font.render(icon, True, (0, 220, 100))
        surface.blit(icon_surf, (self.x + 5, self.y + 5))
        
        # Transparency %
        t_text = f"{self._transparency*100:.0f}%"
        t_surf = font.render(t_text, True, (160, 210, 160))
        surface.blit(t_surf, (self.x + 25, self.y + 5))
        
        # Seeing
        s_text = f"{self._seeing:.1f}\""
        s_surf = font.render(s_text, True, (160, 210, 160))
        surface.blit(s_surf, (self.x + 25, self.y + 22))
    
    def _render_expanded(self, surface: 'pygame.Surface') -> None:
        """Render expanded 200x120 widget (full forecast)."""
        import pygame
        
        # Expanded panel
        bg = pygame.Surface((200, 120), pygame.SRCALPHA)
        bg.fill((0, 18, 10, 230))
        pygame.draw.rect(bg, (0, 100, 50), (0, 0, 200, 120), 1)
        surface.blit(bg, (self.x - 120, self.y))
        
        font = pygame.font.SysFont('monospace', 10)
        y_offset = self.y + 10
        
        # Condition
        cond_text = self._condition.replace("_", " ").upper()
        surf = font.render(f"Condition: {cond_text}", True, (0, 220, 100))
        surface.blit(surf, (self.x - 110, y_offset))
        y_offset += 18
        
        # Transparency
        surf = font.render(f"Transparency: {self._transparency*100:.0f}%", True, (160, 210, 160))
        surface.blit(surf, (self.x - 110, y_offset))
        y_offset += 18
        
        # Seeing
        surf = font.render(f"Seeing: {self._seeing:.1f}\" FWHM", True, (160, 210, 160))
        surface.blit(surf, (self.x - 110, y_offset))
        y_offset += 18
        
        # Imaging quality
        if self._transparency < 0.15:
            qual = "IMPOSSIBLE"
            col = (200, 60, 60)
        elif self._transparency < 0.45:
            qual = "POOR"
            col = (200, 150, 60)
        elif self._transparency < 0.75:
            qual = "ACCEPTABLE"
            col = (180, 200, 80)
        else:
            qual = "GOOD"
            col = (0, 220, 100)
        
        surf = font.render(f"Imaging: {qual}", True, col)
        surface.blit(surf, (self.x - 110, y_offset))
        y_offset += 25
        
        # Click to close
        surf = font.render("Click to close", True, (100, 140, 100))
        surface.blit(surf, (self.x - 110, y_offset))
```

### 1b — ObservablePanel component

```python
# ADD at end of ui_new/components.py (after WeatherWidget)

class ObservablePanel:
    """
    Panel showing objects observable NOW (filtered by altitude, magnitude).
    
    Usage:
        panel = ObservablePanel(x=10, y=100, w=300, h=500)
        panel.update(jd=tc.jd, universe=univ, observer=obs, filters=filt)
        panel.render(surface)
        selected = panel.get_selected_object()  # returns SpaceObject or None
    """
    
    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self._objects = []  # list of dicts: {'obj': SpaceObject, 'alt': float, 'mag': float}
        self._selected_idx = 0
        self._scroll_offset = 0
        self._visible = False
    
    def show(self):
        """Show panel."""
        self._visible = True
    
    def hide(self):
        """Hide panel."""
        self._visible = False
    
    def toggle(self):
        """Toggle visibility."""
        self._visible = not self._visible
    
    def is_visible(self) -> bool:
        return self._visible
    
    def update(self, jd: float, universe, observer, filters: dict) -> None:
        """
        Update list of observable objects.
        
        Args:
            jd: Julian Date
            universe: Universe instance
            observer: ObserverLocation instance
            filters: dict with keys 'min_alt', 'max_mag', 'obj_type' (optional)
        """
        from core.celestial_math import radec_to_altaz
        
        min_alt = filters.get('min_alt', 0.0)
        max_mag = filters.get('max_mag', 12.0)
        obj_type = filters.get('obj_type', None)  # None = all types
        
        self._objects = []
        
        # Get LST for alt/az calculation
        from universe.orbital_body import jd_to_gmst
        gmst = jd_to_gmst(jd)
        lst = (gmst + observer.longitude_deg) % 360.0
        
        # Check all objects in universe
        for obj in universe.get_all_objects():
            # Filter by magnitude
            if obj.mag > max_mag:
                continue
            
            # Filter by type (if specified)
            if obj_type and hasattr(obj, 'obj_class'):
                if obj.obj_class != obj_type:
                    continue
            
            # Calculate altitude
            alt, az = radec_to_altaz(obj.ra_deg, obj.dec_deg, lst, observer.latitude_deg)
            
            # Filter by altitude
            if alt < min_alt:
                continue
            
            self._objects.append({
                'obj': obj,
                'alt': alt,
                'az': az,
                'mag': obj.mag
            })
        
        # Sort by altitude (highest first)
        self._objects.sort(key=lambda x: x['alt'], reverse=True)
        
        # Reset selection if list changed
        if self._selected_idx >= len(self._objects):
            self._selected_idx = 0
    
    def handle_event(self, event) -> bool:
        """
        Handle keyboard navigation (up/down arrows, enter).
        Returns True if event was consumed.
        """
        import pygame
        
        if not self._visible:
            return False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self._selected_idx = min(self._selected_idx + 1, len(self._objects) - 1)
                return True
            elif event.key == pygame.K_UP:
                self._selected_idx = max(self._selected_idx - 1, 0)
                return True
            elif event.key == pygame.K_RETURN:
                # Enter key selects object (handled by parent screen)
                return True
        
        return False
    
    def get_selected_object(self):
        """
        Returns selected SpaceObject or None.
        """
        if not self._objects or self._selected_idx >= len(self._objects):
            return None
        return self._objects[self._selected_idx]['obj']
    
    def render(self, surface: 'pygame.Surface') -> None:
        """Render panel if visible."""
        if not self._visible:
            return
        
        import pygame
        
        # Background
        bg = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        bg.fill((0, 18, 10, 240))
        pygame.draw.rect(bg, (0, 100, 50), (0, 0, self.w, self.h), 1)
        surface.blit(bg, (self.x, self.y))
        
        # Title
        font_title = pygame.font.SysFont('monospace', 12, bold=True)
        title = font_title.render("OBSERVABLE NOW", True, (0, 220, 100))
        surface.blit(title, (self.x + 10, self.y + 10))
        
        # Object list
        font = pygame.font.SysFont('monospace', 10)
        y_offset = self.y + 35
        row_height = 18
        
        # Header
        header = font.render("Object         Type  Mag   Alt", True, (160, 210, 160))
        surface.blit(header, (self.x + 10, y_offset))
        y_offset += row_height
        
        # Visible rows (scrollable)
        max_visible = (self.h - 60) // row_height
        start_idx = self._scroll_offset
        end_idx = min(start_idx + max_visible, len(self._objects))
        
        for i in range(start_idx, end_idx):
            item = self._objects[i]
            obj = item['obj']
            
            # Highlight selected row
            if i == self._selected_idx:
                highlight = pygame.Surface((self.w - 20, row_height), pygame.SRCALPHA)
                highlight.fill((0, 100, 50, 100))
                surface.blit(highlight, (self.x + 10, y_offset))
            
            # Object name (truncate to 14 chars)
            name = obj.name[:14].ljust(14)
            
            # Object type
            obj_type = getattr(obj, 'obj_class', 'Star')[:4].ljust(4)
            
            # Magnitude
            mag_str = f"{obj.mag:4.1f}"
            
            # Altitude
            alt_str = f"{item['alt']:3.0f}°"
            
            # Render row
            row_text = f"{name} {obj_type} {mag_str} {alt_str}"
            row_surf = font.render(row_text, True, (200, 220, 200))
            surface.blit(row_surf, (self.x + 10, y_offset))
            
            y_offset += row_height
        
        # Footer
        footer_y = self.y + self.h - 20
        footer = font.render(f"{len(self._objects)} objects | ↑↓ Navigate | Enter=Select", True, (100, 140, 100))
        surface.blit(footer, (self.x + 10, footer_y))
```

---

## Task 2 — NavigationManager (nuovo file)

**File:** `ui_new/navigation_manager.py` (CREATE NEW)

```python
"""
NavigationManager — Centralized screen navigation and global hotkeys.

Manages screen stack, shortcuts, and transitions between screens.
"""

from typing import Optional


class NavigationManager:
    """
    Manages screen navigation stack and global hotkeys.
    
    Usage:
        nav = NavigationManager()
        nav.push('SKYCHART')  # go to sky chart
        nav.pop()             # back to previous screen
        nav.home()            # return to OBSERVATORY
        current = nav.current_screen()
    """
    
    def __init__(self, initial_screen: str = 'MAIN_MENU'):
        self._stack: list[str] = [initial_screen]
        self._target: Optional[str] = None  # set by screens to request navigation
    
    def push(self, screen_name: str) -> None:
        """Navigate to new screen (adds to stack)."""
        self._stack.append(screen_name)
    
    def pop(self) -> Optional[str]:
        """
        Go back to previous screen (removes from stack).
        Returns the screen we're going back to, or None if already at root.
        """
        if len(self._stack) > 1:
            self._stack.pop()
            return self._stack[-1]
        return None
    
    def replace(self, screen_name: str) -> None:
        """Replace current screen with new screen (no stack growth)."""
        if self._stack:
            self._stack[-1] = screen_name
        else:
            self._stack.append(screen_name)
    
    def home(self) -> None:
        """Return to OBSERVATORY (clear stack except root)."""
        self._stack = [self._stack[0], 'OBSERVATORY']
    
    def current_screen(self) -> str:
        """Return name of current screen."""
        return self._stack[-1] if self._stack else 'MAIN_MENU'
    
    def request_navigation(self, screen_name: str) -> None:
        """
        Request navigation to screen_name.
        This is called by screens; main loop checks get_navigation_target().
        """
        self._target = screen_name
    
    def get_navigation_target(self) -> Optional[str]:
        """
        Get pending navigation target (used by main loop).
        Returns target and clears it.
        """
        target = self._target
        self._target = None
        return target
    
    def handle_global_hotkeys(self, event) -> Optional[str]:
        """
        Handle global navigation hotkeys.
        
        Returns screen name to navigate to, or None.
        
        Global hotkeys:
            H = Home (OBSERVATORY)
            ESC = Back (pop stack)
        """
        import pygame
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_h:
                self.home()
                return 'OBSERVATORY'
            elif event.key == pygame.K_ESCAPE:
                return self.pop()
        
        return None
```

---

## Task 3 — MainMenuScreen (nuovo file)

**File:** `ui_new/screen_main_menu.py` (CREATE NEW)

```python
"""
Main Menu Screen — Entry point of the application.

Buttons:
  - CAREER: Start/continue career mode
  - EXPLORE: Sandbox mode (direct to OBSERVATORY)
  - SETTINGS: Game settings
  - QUIT: Exit application
"""

import pygame
from .base_screen import BaseScreen
from .components import Button


class MainMenuScreen(BaseScreen):
    """Main menu with Career, Explore, Settings, Quit."""
    
    def __init__(self, state_manager=None):
        super().__init__("MAIN MENU")
        self._state_manager = state_manager
        self.buttons = {}
        self._create_buttons()
    
    def _create_buttons(self):
        """Create main menu buttons (centered layout)."""
        W = 1280  # assume default window size
        H = 800
        
        button_width = 200
        button_height = 60
        spacing = 20
        
        center_x = W // 2 - button_width // 2
        start_y = H // 2 - (4 * button_height + 3 * spacing) // 2
        
        self.buttons['career'] = Button(
            center_x, start_y,
            button_width, button_height,
            "CAREER",
            callback=lambda: self._navigate('CAREER')
        )
        
        self.buttons['explore'] = Button(
            center_x, start_y + button_height + spacing,
            button_width, button_height,
            "EXPLORE",
            callback=lambda: self._navigate('OBSERVATORY')  # direct to hub
        )
        
        self.buttons['settings'] = Button(
            center_x, start_y + 2 * (button_height + spacing),
            button_width, button_height,
            "SETTINGS",
            callback=lambda: self._navigate('CONTENT_MANAGER')
        )
        
        self.buttons['quit'] = Button(
            center_x, start_y + 3 * (button_height + spacing),
            button_width, button_height,
            "QUIT",
            callback=self._quit
        )
    
    def _navigate(self, screen_name: str):
        """Set navigation target."""
        self._next_screen = screen_name
    
    def _quit(self):
        """Post QUIT event."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))
    
    def on_enter(self):
        super().on_enter()
        self._next_screen = None
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        
        # Update button hover
        for button in self.buttons.values():
            button.update(mouse_pos)
        
        # Handle events
        for event in events:
            # Button clicks
            for button in self.buttons.values():
                if button.handle_event(event):
                    break
        
        # Check navigation
        if self._next_screen:
            result = self._next_screen
            self._next_screen = None
            return result
        
        return None
    
    def update(self, dt: float):
        pass
    
    def render(self, surface: pygame.Surface):
        W, H = surface.get_width(), surface.get_height()
        
        # Title
        title_font = pygame.font.SysFont('monospace', 32, bold=True)
        title = title_font.render("ASTRONOMY OBSERVER", True, (0, 220, 100))
        title_rect = title.get_rect(center=(W // 2, 150))
        surface.blit(title, title_rect)
        
        # Subtitle
        subtitle_font = pygame.font.SysFont('monospace', 14)
        subtitle = subtitle_font.render("Observatory Simulation Game", True, (160, 210, 160))
        subtitle_rect = subtitle.get_rect(center=(W // 2, 190))
        surface.blit(subtitle, subtitle_rect)
        
        # Buttons
        for button in self.buttons.values():
            button.draw(surface)
        
        # Footer
        footer = pygame.Rect(10, H - 40, W - 20, 30)
        self.draw_footer(surface, footer, "Select mode to begin")
```

---

## Task 4 — ContentManagerScreen (nuovo file)

**File:** `ui_new/screen_content_manager.py` (CREATE NEW)

```python
"""
Content Manager Screen — Manage catalogs and equipment library.

Tabs:
  - Catalogs: Enable/disable loaded catalogs, view stats
  - Equipment Library: View all available equipment specs
  - Graphics: VFX settings, performance mode
"""

import pygame
from .base_screen import BaseScreen
from .components import Button


class ContentManagerScreen(BaseScreen):
    """Settings / Content Manager."""
    
    def __init__(self, state_manager=None):
        super().__init__("CONTENT MANAGER")
        self._state_manager = state_manager
        self.tabs = ['CATALOGS', 'EQUIPMENT', 'GRAPHICS']
        self.current_tab = 0
    
    def on_enter(self):
        super().on_enter()
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        for event in events:
            if event.type == pygame.KEYDOWN:
                # ESC = back to main menu
                if event.key == pygame.K_ESCAPE:
                    return 'MAIN_MENU'
                # Tab navigation
                elif event.key == pygame.K_TAB:
                    self.current_tab = (self.current_tab + 1) % len(self.tabs)
        
        return None
    
    def update(self, dt: float):
        pass
    
    def render(self, surface: pygame.Surface):
        W, H = surface.get_width(), surface.get_height()
        
        # Header
        header = pygame.Rect(10, 10, W - 20, 80)
        self.draw_header(surface, header, "CONTENT MANAGER", "Catalogs • Equipment • Graphics")
        
        # Tab bar
        self._draw_tabs(surface, W)
        
        # Content area
        content_rect = pygame.Rect(10, 120, W - 20, H - 180)
        
        if self.tabs[self.current_tab] == 'CATALOGS':
            self._render_catalogs_tab(surface, content_rect)
        elif self.tabs[self.current_tab] == 'EQUIPMENT':
            self._render_equipment_tab(surface, content_rect)
        elif self.tabs[self.current_tab] == 'GRAPHICS':
            self._render_graphics_tab(surface, content_rect)
        
        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer, "[ESC] Back  [TAB] Next Tab")
    
    def _draw_tabs(self, surface: pygame.Surface, W: int):
        """Draw tab bar."""
        tab_width = 150
        tab_height = 30
        tab_y = 100
        
        for i, tab_name in enumerate(self.tabs):
            tab_x = 10 + i * (tab_width + 10)
            
            # Tab background
            if i == self.current_tab:
                color = (0, 100, 50)
            else:
                color = (0, 50, 25)
            
            pygame.draw.rect(surface, color, (tab_x, tab_y, tab_width, tab_height))
            pygame.draw.rect(surface, (0, 150, 75), (tab_x, tab_y, tab_width, tab_height), 1)
            
            # Tab label
            font = pygame.font.SysFont('monospace', 11, bold=(i == self.current_tab))
            label = font.render(tab_name, True, (0, 220, 100) if i == self.current_tab else (120, 160, 120))
            label_rect = label.get_rect(center=(tab_x + tab_width // 2, tab_y + tab_height // 2))
            surface.blit(label, label_rect)
    
    def _render_catalogs_tab(self, surface: pygame.Surface, rect: pygame.Rect):
        """Render catalogs management tab."""
        self.theme.draw_panel(surface, rect)
        
        font = pygame.font.SysFont('monospace', 11)
        y = rect.y + 20
        
        # Title
        title = font.render("LOADED CATALOGS", True, (0, 220, 100))
        surface.blit(title, (rect.x + 20, y))
        y += 30
        
        # Catalog list (placeholder)
        catalogs = [
            ("Gaia DR3 Lvl 0-5", "2.1M stars", "45 MB", True),
            ("Hipparcos", "118k stars", "8 MB", True),
            ("Messier", "110 objects", "1 MB", True),
            ("NGC/IC", "13k objects", "12 MB", True),
            ("MPCORB Asteroids", "600k objects", "250 MB", False),
        ]
        
        for name, count, size, enabled in catalogs:
            checkbox = "✓" if enabled else "☐"
            text = f"{checkbox} {name.ljust(20)} {count.ljust(15)} {size.rjust(8)}"
            color = (0, 200, 80) if enabled else (100, 100, 100)
            surf = font.render(text, True, color)
            surface.blit(surf, (rect.x + 20, y))
            y += 20
        
        # Note
        y += 20
        note = font.render("Note: Catalog changes require restart", True, (160, 180, 160))
        surface.blit(note, (rect.x + 20, y))
    
    def _render_equipment_tab(self, surface: pygame.Surface, rect: pygame.Rect):
        """Render equipment library tab."""
        self.theme.draw_panel(surface, rect)
        
        font = pygame.font.SysFont('monospace', 11)
        y = rect.y + 20
        
        title = font.render("EQUIPMENT LIBRARY", True, (0, 220, 100))
        surface.blit(title, (rect.x + 20, y))
        y += 30
        
        # Placeholder equipment list
        text = font.render("Telescopes: 12 available", True, (160, 210, 160))
        surface.blit(text, (rect.x + 20, y))
        y += 20
        
        text = font.render("Cameras: 8 available", True, (160, 210, 160))
        surface.blit(text, (rect.x + 20, y))
        y += 20
        
        text = font.render("Filters: 5 available", True, (160, 210, 160))
        surface.blit(text, (rect.x + 20, y))
    
    def _render_graphics_tab(self, surface: pygame.Surface, rect: pygame.Rect):
        """Render graphics settings tab."""
        self.theme.draw_panel(surface, rect)
        
        font = pygame.font.SysFont('monospace', 11)
        y = rect.y + 20
        
        title = font.render("GRAPHICS SETTINGS", True, (0, 220, 100))
        surface.blit(title, (rect.x + 20, y))
        y += 30
        
        # Placeholder settings
        text = font.render("Resolution: 1280x800", True, (160, 210, 160))
        surface.blit(text, (rect.x + 20, y))
        y += 20
        
        text = font.render("VFX: Enabled (bloom, dithering)", True, (160, 210, 160))
        surface.blit(text, (rect.x + 20, y))
```

---

## Task 5 — Equipment screen refactor

**File:** `ui_new/screen_equipment.py` (MODIFY existing)

Add mode switch at top of `__init__`:

```python
# ADD to EquipmentScreen.__init__, after super().__init__():

# Detect mode from state_manager
if self._state_manager:
    career_mode = self._state_manager.get_career_mode()
    self._mode = 'CAREER' if career_mode else 'EXPLORE'
else:
    self._mode = 'EXPLORE'  # default to sandbox
```

Add mode-specific rendering in `render()`:

```python
# In EquipmentScreen.render(), replace body with:

if self._mode == 'CAREER':
    self._render_career_mode(surface)
else:
    self._render_explore_mode(surface)
```

Add two new methods:

```python
# ADD to EquipmentScreen class:

def _render_career_mode(self, surface: pygame.Surface):
    """Render equipment shop + owned items (Career)."""
    W, H = surface.get_width(), surface.get_height()
    
    # Header
    header = pygame.Rect(10, 10, W - 20, 80)
    self.draw_header(surface, header, "EQUIPMENT MANAGEMENT", "Career Mode • Buy/Sell/Equip")
    
    # Content (placeholder for now)
    font = pygame.font.SysFont('monospace', 11)
    text = font.render("Career mode equipment (TODO Sprint 17)", True, (160, 210, 160))
    surface.blit(text, (30, 120))

def _render_explore_mode(self, surface: pygame.Surface):
    """Render equipment sandbox selector (Explore)."""
    W, H = surface.get_width(), surface.get_height()
    
    # Header
    header = pygame.Rect(10, 10, W - 20, 80)
    self.draw_header(surface, header, "EQUIPMENT SELECTION", "Explore Mode • All equipment available")
    
    # Content (placeholder for now)
    font = pygame.font.SysFont('monospace', 11)
    text = font.render("Explore mode equipment (TODO Sprint 14.5)", True, (160, 210, 160))
    surface.blit(text, (30, 120))
```

---

## Task 6 — ObservatoryScreen updates

**File:** `ui_new/screen_observatory.py` (MODIFY existing)

Add WeatherWidget and hotkeys.

### 6a — Add imports and init WeatherWidget

```python
# ADD to imports at top of file:
from atmosphere.weather import WeatherSystem
from .components import WeatherWidget

# ADD to ObservatoryScreen.__init__, after existing init:
self._weather = WeatherSystem(base_seeing=2.5, seed=42)
self._weather_widget = WeatherWidget(x=0, y=10, weather_system=self._weather)  # x will be set in render
```

### 6b — Update weather widget in update()

```python
# ADD to ObservatoryScreen.update(), before end of method:
from universe.orbital_body import datetime_to_jd
jd = datetime_to_jd(self.current_time)
self._weather_widget.update(jd)
```

### 6c — Render weather widget

```python
# ADD to ObservatoryScreen.render(), AFTER drawing all buttons, BEFORE footer:
W, H = surface.get_width(), surface.get_height()
self._weather_widget.x = W - 90  # position in top-right
self._weather_widget.render(surface)
```

### 6d — Handle weather widget clicks

```python
# ADD to ObservatoryScreen.handle_input(), in event loop:
# Weather widget clicks
if self._weather_widget.handle_event(event):
    continue
```

---

## Task 7 — SkyChart updates

**File:** `ui_new/screen_skychart.py` (MODIFY existing)

Add ObservablePanel and hotkeys.

### 7a — Add imports and init ObservablePanel

```python
# ADD to imports:
from .components import ObservablePanel, WeatherWidget
from atmosphere.weather import WeatherSystem

# ADD to SkychartScreen.__init__, after existing init:
self._weather = WeatherSystem(base_seeing=2.5, seed=42)
self._weather_widget = WeatherWidget(x=0, y=10, weather_system=self._weather)
self._observable_panel = ObservablePanel(x=10, y=100, w=300, h=600)
self._observable_panel.hide()  # hidden by default
```

### 7b — Update panels

```python
# ADD to SkychartScreen.update():
from universe.orbital_body import datetime_to_jd
jd = datetime_to_jd(self._tc.utc)
self._weather_widget.update(jd)

# Update observable panel if visible
if self._observable_panel.is_visible():
    from atmosphere.atmospheric_model import ObserverLocation
    from core.coords import PARMA_OBSERVER
    
    filters = {
        'min_alt': 30.0,
        'max_mag': 10.0,
        'obj_type': None  # all types
    }
    
    self._observable_panel.update(
        jd=jd,
        universe=self._universe,
        observer=PARMA_OBSERVER,
        filters=filters
    )
```

### 7c — Handle hotkeys

```python
# ADD to SkychartScreen.handle_input(), in KEYDOWN section:

elif event.key == pygame.K_o:
    # Toggle Observable Now panel
    self._observable_panel.toggle()

elif event.key == pygame.K_i:
    # Quick switch to Imaging
    return 'IMAGING'
```

### 7d — Handle observable panel events

```python
# ADD to SkychartScreen.handle_input(), in event loop BEFORE keyboard handling:

# Observable panel navigation
if self._observable_panel.handle_event(event):
    # Check if object was selected (Enter key)
    if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
        selected = self._observable_panel.get_selected_object()
        if selected:
            self._current_target = selected.name
            self._observable_panel.hide()
    continue

# Weather widget clicks
if self._weather_widget.handle_event(event):
    continue
```

### 7e — Render panels

```python
# ADD to SkychartScreen.render(), AFTER drawing planets, BEFORE footer:
W, H = surface.get_width(), surface.get_height()

# Weather widget
self._weather_widget.x = W - 90
self._weather_widget.render(surface)

# Observable panel
self._observable_panel.render(surface)
```

---

## Task 8 — Imaging screen tabs

**File:** `ui_new/screen_imaging.py` (MODIFY existing)

Add tab system for Live/Setup/Capture/Process.

### 8a — Add tabs to __init__

```python
# ADD to ImagingScreen.__init__, after existing init:
self.tabs = ['LIVE', 'SETUP', 'CAPTURE', 'PROCESS']
self.current_tab = 0  # default to LIVE

from atmosphere.weather import WeatherSystem
from ui_new.components import WeatherWidget
self._weather = WeatherSystem(base_seeing=2.5, seed=42)
self._weather_widget = WeatherWidget(x=0, y=10, weather_system=self._weather)
```

### 8b — Handle tab switching

```python
# ADD to ImagingScreen.handle_input(), in KEYDOWN section:

elif event.key == pygame.K_TAB:
    # Cycle through tabs
    self.current_tab = (self.current_tab + 1) % len(self.tabs)

elif event.key == pygame.K_s:
    # Quick switch to SkyChart
    return 'SKYCHART'

# Weather widget
if self._weather_widget.handle_event(event):
    continue
```

### 8c — Render tabs

```python
# ADD to ImagingScreen.render(), AFTER header, BEFORE existing content:

W, H = surface.get_width(), surface.get_height()

# Tab bar
tab_y = 100
tab_width = 120
tab_height = 30

for i, tab_name in enumerate(self.tabs):
    tab_x = 10 + i * (tab_width + 5)
    
    if i == self.current_tab:
        color = (0, 100, 50)
    else:
        color = (0, 50, 25)
    
    pygame.draw.rect(surface, color, (tab_x, tab_y, tab_width, tab_height))
    pygame.draw.rect(surface, (0, 150, 75), (tab_x, tab_y, tab_width, tab_height), 1)
    
    font = pygame.font.SysFont('monospace', 11, bold=(i == self.current_tab))
    label = font.render(tab_name, True, (0, 220, 100) if i == self.current_tab else (120, 160, 120))
    label_rect = label.get_rect(center=(tab_x + tab_width // 2, tab_y + tab_height // 2))
    surface.blit(label, label_rect)

# Weather widget
self._weather_widget.x = W - 90
self._weather_widget.update(self._tc.jd)
self._weather_widget.render(surface)

# Content area depends on active tab
content_y = tab_y + tab_height + 10

if self.tabs[self.current_tab] == 'LIVE':
    # EXISTING live view code goes here (keep as is)
    pass
elif self.tabs[self.current_tab] == 'SETUP':
    # Placeholder for now
    font = pygame.font.SysFont('monospace', 11)
    text = font.render("Setup tab (TODO)", True, (160, 210, 160))
    surface.blit(text, (30, content_y))
elif self.tabs[self.current_tab] == 'CAPTURE':
    font = pygame.font.SysFont('monospace', 11)
    text = font.render("Capture tab (TODO)", True, (160, 210, 160))
    surface.blit(text, (30, content_y))
elif self.tabs[self.current_tab] == 'PROCESS':
    font = pygame.font.SysFont('monospace', 11)
    text = font.render("Process tab (TODO)", True, (160, 210, 160))
    surface.blit(text, (30, content_y))
```

---

## Task 9 — Wire NavigationManager in main_app.py

**File:** `main_app.py` (MODIFY existing)

### 9a — Add NavigationManager import and init

```python
# ADD to imports at top:
from ui_new.navigation_manager import NavigationManager
from ui_new.screen_main_menu import MainMenuScreen
from ui_new.screen_content_manager import ContentManagerScreen

# ADD to ObservatoryGame.__init__, BEFORE _register_screens():
self.nav_manager = NavigationManager(initial_screen='MAIN_MENU')
```

### 9b — Register new screens

```python
# ADD to _register_screens():
self.state_manager.register_screen('MAIN_MENU', MainMenuScreen(self.state_manager))
self.state_manager.register_screen('CONTENT_MANAGER', ContentManagerScreen(self.state_manager))
```

### 9c — Handle global navigation

```python
# ADD to main() game loop, in event handling BEFORE screen.handle_input():

# Global navigation hotkeys
nav_target = self.nav_manager.handle_global_hotkeys(event)
if nav_target:
    next_screen = nav_target
    # Don't break, let screen finish handling events
```

### 9d — Start at MAIN_MENU instead of OBSERVATORY

```python
# FIND this line in main():
current_screen_name = 'OBSERVATORY'

# REPLACE with:
current_screen_name = 'MAIN_MENU'
```

---

## Testing Checklist

After implementation, verify:

- [ ] Game starts at MAIN_MENU
- [ ] EXPLORE button → OBSERVATORY directly
- [ ] SETTINGS button → CONTENT_MANAGER
- [ ] ESC in CONTENT_MANAGER → MAIN_MENU
- [ ] Hotkey H anywhere → OBSERVATORY
- [ ] Weather widget visible in Observatory, SkyChart, Imaging
- [ ] Weather widget click → expands forecast
- [ ] Hotkey O in SkyChart → Observable Now panel
- [ ] Observable panel ↑↓ navigation works
- [ ] Hotkey I in SkyChart → IMAGING
- [ ] Hotkey S in Imaging → SKYCHART
- [ ] TAB in Imaging → cycles tabs
- [ ] All imports resolve (no "module not found" errors)
- [ ] No crashes when switching screens rapidly

---

## Common Pitfalls (for Copilot)

### ❌ DO NOT do these things:

1. **DO NOT import from future screens** — e.g., don't import MainMenuScreen in BaseScreen
2. **DO NOT call undefined methods** — all method signatures are in this spec, copy exactly
3. **DO NOT use `self._next_screen` in screens that don't define it** — only MainMenuScreen uses it
4. **DO NOT forget Optional return type** — handle_input() returns `Optional[str]`, not `str`
5. **DO NOT modify protected files** — screen_imaging.py has manual bugfix, only add specified code

### ✅ DO these things:

1. **DO follow import order** — Task 1 first (components), then Task 2 (nav manager), etc.
2. **DO copy signatures exactly** — parameter names and types matter
3. **DO use getattr with defaults** — `getattr(obj, 'attr', default)` for safety
4. **DO test each task** — don't implement all 9 tasks then test, test incrementally
5. **DO preserve existing code** — only modify specified sections

---

## Files Modified Summary

| File | Status | Lines Changed |
|------|--------|---------------|
| `ui_new/components.py` | MODIFY | +300 (WeatherWidget + ObservablePanel) |
| `ui_new/navigation_manager.py` | NEW | +90 |
| `ui_new/screen_main_menu.py` | NEW | +120 |
| `ui_new/screen_content_manager.py` | NEW | +180 |
| `ui_new/screen_equipment.py` | MODIFY | +40 |
| `ui_new/screen_observatory.py` | MODIFY | +20 |
| `ui_new/screen_skychart.py` | MODIFY | +60 |
| `ui_new/screen_imaging.py` | MODIFY | +50 |
| `main_app.py` | MODIFY | +10 |
| **TOTAL** | — | **~870 lines** |

