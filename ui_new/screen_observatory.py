"""
Observatory Hub Screen

Main hub for the observatory simulation game.
Central interface where player can access all major features.
"""

import pygame
from datetime import datetime, timezone
from typing import Optional
from .base_screen import BaseScreen
from .components import Button, Panel, Label


class ObservatoryScreen(BaseScreen):
    """
    Observatory Hub - Central game interface
    
    Provides access to:
    - Sky Chart (celestial map and target selection)
    - Imaging (acquisition and processing)
    - Catalogs (browse objects)
    - Equipment (manage telescope/camera/filters)
    """
    
    def __init__(self, state_manager=None):
        super().__init__("OBSERVATORY")
        
        self._state_manager = state_manager
        
        # Buttons for main features
        self.buttons = {}
        self._create_buttons()
        
        # Current state info
        self.current_time = datetime.now(timezone.utc)
        self.location = "Parma, IT (44.80°N, 10.33°E)"
        self.current_target = "None selected"
        self.current_telescope = "Newtonian 150mm f/5"
        self.current_camera = "ZWO ASI294MC"
        self.current_filter = "Luminance"
    
    def _create_buttons(self):
        """Create main navigation buttons"""
        # Calculate layout (4 buttons in 2x2 grid)
        center_x = 640  # Assuming 1280 width
        center_y = 400  # Assuming 800 height
        
        button_width = 200
        button_height = 80
        spacing = 40
        
        # Sky Chart (top-left)
        self.buttons['skychart'] = Button(
            center_x - button_width - spacing // 2,
            center_y - button_height - spacing // 2,
            button_width, button_height,
            "SKY CHART",
            callback=lambda: self._navigate('SKYCHART')
        )
        
        # Imaging (top-right)
        self.buttons['imaging'] = Button(
            center_x + spacing // 2,
            center_y - button_height - spacing // 2,
            button_width, button_height,
            "IMAGING",
            callback=lambda: self._navigate('IMAGING')
        )
        
        # Catalogs (bottom-left)
        self.buttons['catalogs'] = Button(
            center_x - button_width - spacing // 2,
            center_y + spacing // 2,
            button_width, button_height,
            "CATALOGS",
            callback=lambda: self._navigate('CATALOGS')
        )
        
        # Equipment (bottom-right)
        self.buttons['equipment'] = Button(
            center_x + spacing // 2,
            center_y + spacing // 2,
            button_width, button_height,
            "EQUIPMENT",
            callback=lambda: self._navigate('EQUIPMENT')
        )
        
        # Career button (center bottom)
        self.buttons['career'] = Button(
            center_x - button_width // 2,
            center_y + button_height + spacing + 20,
            button_width, button_height - 20,
            "CAREER & MISSIONS",
            callback=lambda: self._navigate('CAREER')
        )
        
        # Save/Load buttons (compact, bottom)
        small_width = (button_width - 10) // 2
        self.buttons['save'] = Button(
            center_x - button_width // 2,
            center_y + button_height * 2 + spacing + 30,
            small_width, 40,
            "SAVE",
            callback=self.save_game
        )
        
        self.buttons['load'] = Button(
            center_x - button_width // 2 + small_width + 10,
            center_y + button_height * 2 + spacing + 30,
            small_width, 40,
            "LOAD",
            callback=self.load_game
        )
    
    def save_game(self):
        """Save game"""
        if self._state_manager:
            self._state_manager.save_game()
            print("Game saved!")
    
    def load_game(self):
        """Load game"""
        if self._state_manager:
            if self._state_manager.load_game():
                print("Game loaded!")
            else:
                print("No save file found or load failed")
    
    def _navigate(self, screen_name: str):
        """Set navigation target"""
        self._next_screen = screen_name
    
    def on_enter(self):
        super().on_enter()
        self._next_screen = None
        self.current_time = datetime.now(timezone.utc)
    
    def on_exit(self):
        super().on_exit()
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        
        # Update button hover states
        for button in self.buttons.values():
            button.update(mouse_pos)
        
        # Handle events
        for event in events:
            # Global keys
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Quit application
                    pygame.event.post(pygame.event.Event(pygame.QUIT))
                    return None
                
                # Keyboard shortcuts
                elif event.key == pygame.K_1:
                    return 'SKYCHART'
                elif event.key == pygame.K_2:
                    return 'IMAGING'
                elif event.key == pygame.K_3:
                    return 'CATALOGS'
                elif event.key == pygame.K_4:
                    return 'EQUIPMENT'
                elif event.key == pygame.K_5:
                    return 'CAREER'
                
                # Save/Load shortcuts
                elif event.key == pygame.K_F5:
                    self.save_game()
                elif event.key == pygame.K_F9:
                    self.load_game()
            
            # Button clicks
            for button in self.buttons.values():
                if button.handle_event(event):
                    break
        
        # Check if navigation was requested
        if self._next_screen:
            result = self._next_screen
            self._next_screen = None
            return result
        
        return None
    
    def update(self, dt: float):
        """Update observatory state"""
        # Update time
        self.current_time = datetime.now(timezone.utc)
    
    def render(self, surface: pygame.Surface):
        """Render observatory hub"""
        W, H = surface.get_width(), surface.get_height()
        
        # Header
        header = pygame.Rect(10, 10, W - 20, 80)
        
        # Get RP from career mode
        career_mode = None
        if self._state_manager:
            career_mode = self._state_manager.get_career_mode()
        
        subtitle = f"{self.location}  |  {self.current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        if career_mode:
            subtitle += f"  |  RP: {career_mode.stats.research_points}"
        
        self.draw_header(surface, header, 
                        "OBSERVATORY CONTROL CENTER",
                        subtitle)
        
        # Status panel (top)
        status_panel = pygame.Rect(10, 100, W - 20, 100)
        self.theme.draw_panel(surface, status_panel)
        
        # Status info (3 columns)
        col1_x = 30
        col2_x = W // 3 + 20
        col3_x = 2 * W // 3 + 10
        status_y = 120
        
        # Column 1: Target info
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           col1_x, status_y,
                           "CURRENT TARGET:", self.theme.colors.ACCENT_CYAN)
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           col1_x, status_y + 25,
                           self.current_target, self.theme.colors.FG_PRIMARY)
        
        # Column 2: Equipment
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           col2_x, status_y,
                           "EQUIPMENT:", self.theme.colors.ACCENT_CYAN)
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           col2_x, status_y + 25,
                           f"Telescope: {self.current_telescope}", self.theme.colors.FG_PRIMARY)
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           col2_x, status_y + 45,
                           f"Camera: {self.current_camera}", self.theme.colors.FG_PRIMARY)
        
        # Column 3: Filter
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           col3_x, status_y,
                           "FILTER:", self.theme.colors.ACCENT_CYAN)
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           col3_x, status_y + 25,
                           self.current_filter, self.theme.colors.FG_PRIMARY)
        
        # Main buttons area
        # (Buttons are drawn centered, so we just render them)
        for button in self.buttons.values():
            button.draw(surface)
        
        # Info box (bottom)
        info_panel = pygame.Rect(10, H - 160, W - 20, 100)
        self.theme.draw_panel(surface, info_panel)
        
        info_y = H - 145
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           30, info_y,
                           "OBSERVATORY STATUS: OPERATIONAL", self.theme.colors.SUCCESS)
        
        info_y += 30
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, info_y,
                           "Select a module to begin:", self.theme.colors.FG_DIM)
        
        info_y += 22
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           40, info_y,
                           "• Sky Chart: Navigate celestial sphere, select targets", 
                           self.theme.colors.FG_DIM)
        
        info_y += 18
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           40, info_y,
                           "• Imaging: Acquire and process astronomical images", 
                           self.theme.colors.FG_DIM)
        
        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                        "[1] Sky Chart  [2] Imaging  [3] Catalogs  [4] Equipment  [5] Career  [F5] Save  [F9] Load  [ESC] Quit")
    
    def set_target(self, target_name: str):
        """Update current target"""
        self.current_target = target_name
    
    def set_equipment(self, telescope: str, camera: str, filter_name: str):
        """Update equipment setup"""
        self.current_telescope = telescope
        self.current_camera = camera
        self.current_filter = filter_name
