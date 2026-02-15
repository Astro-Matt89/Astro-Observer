"""
Base Screen Class

Abstract base class for all game screens.
Provides common functionality and enforces screen interface.
"""

import pygame
from abc import ABC, abstractmethod
from typing import Optional
from .theme import get_theme


class BaseScreen(ABC):
    """
    Abstract base class for all screens
    
    All game screens (Observatory Hub, Imaging, Sky Chart, etc.)
    should inherit from this class and implement the required methods.
    """
    
    def __init__(self, screen_name: str):
        """
        Initialize base screen
        
        Args:
            screen_name: Unique identifier for this screen
        """
        self.screen_name = screen_name
        self.active = False
        self.theme = get_theme()
    
    @abstractmethod
    def on_enter(self):
        """
        Called when screen becomes active
        
        Use this to initialize or reset screen state.
        """
        self.active = True
    
    @abstractmethod
    def on_exit(self):
        """
        Called when screen becomes inactive
        
        Use this to cleanup resources or save state.
        """
        self.active = False
    
    @abstractmethod
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        """
        Handle input events
        
        Args:
            events: List of pygame events for this frame
            
        Returns:
            Name of screen to switch to, or None to stay on current screen
        """
        pass
    
    @abstractmethod
    def update(self, dt: float):
        """
        Update screen logic
        
        Args:
            dt: Delta time in seconds since last update
        """
        pass
    
    @abstractmethod
    def render(self, surface: pygame.Surface):
        """
        Render screen
        
        Args:
            surface: Main display surface to render to
        """
        pass
    
    # Utility methods (available to all screens)
    
    def draw_header(self, surface: pygame.Surface, rect: pygame.Rect, 
                   title: str, subtitle: str = ""):
        """
        Draw standard header
        
        Args:
            surface: Target surface
            rect: Header rectangle
            title: Main title
            subtitle: Optional subtitle
        """
        self.theme.draw_panel(surface, rect)
        
        self.theme.draw_text(surface, self.theme.fonts.title(),
                           rect.x + 12, rect.y + 10,
                           title, self.theme.colors.FG_PRIMARY)
        
        if subtitle:
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               rect.x + 12, rect.y + 38,
                               subtitle, self.theme.colors.FG_DIM)
    
    def draw_footer(self, surface: pygame.Surface, rect: pygame.Rect, 
                   controls: str):
        """
        Draw standard footer with controls
        
        Args:
            surface: Target surface
            rect: Footer rectangle
            controls: Control hints (e.g., "[ESC] Back  [ENTER] Select")
        """
        self.theme.draw_panel(surface, rect)
        
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           rect.x + 12, rect.y + 8,
                           controls, self.theme.colors.FG_DIM)
    
    def is_active(self) -> bool:
        """Check if screen is currently active"""
        return self.active


class EmptyScreen(BaseScreen):
    """
    Empty placeholder screen
    
    Useful for testing and as a template.
    """
    
    def __init__(self, screen_name: str = "EMPTY", title: str = "Empty Screen"):
        super().__init__(screen_name)
        self.title = title
    
    def on_enter(self):
        super().on_enter()
        print(f"Entered {self.title}")
    
    def on_exit(self):
        super().on_exit()
        print(f"Exited {self.title}")
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "OBSERVATORY"  # Go back to hub
        return None
    
    def update(self, dt: float):
        pass
    
    def render(self, surface: pygame.Surface):
        # Header
        header = pygame.Rect(10, 10, surface.get_width() - 20, 60)
        self.draw_header(surface, header, self.title, 
                        "This is a placeholder screen")
        
        # Main area
        main_area = pygame.Rect(10, 80, surface.get_width() - 20, 
                               surface.get_height() - 150)
        self.theme.draw_panel(surface, main_area)
        
        # Centered text
        text = "Screen not yet implemented"
        self.theme.draw_text(surface, self.theme.fonts.large(),
                           surface.get_width() // 2, surface.get_height() // 2,
                           text, self.theme.colors.FG_DIM, align='center')
        
        # Footer
        footer = pygame.Rect(10, surface.get_height() - 60, 
                            surface.get_width() - 20, 50)
        self.draw_footer(surface, footer, "[ESC] Back to Observatory Hub")
