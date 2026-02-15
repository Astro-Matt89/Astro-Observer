"""
UI Theme - DOS VGA Retro Style

Defines colors, fonts, and visual style for the game UI.
Maintains consistent retro DOS/VGA aesthetic throughout.
"""

import pygame
from typing import Tuple
from dataclasses import dataclass


# VGA-inspired color palette
class Colors:
    """
    Color palette for DOS VGA retro aesthetic
    
    Uses phosphor green as primary, with accent colors
    for warnings, highlights, and atmospheric effects.
    """
    
    # Background colors
    BG_DARK = (0, 12, 10)        # Very dark teal/black
    BG_PANEL = (0, 20, 15)       # Dark teal panel
    BG_PANEL_LIGHT = (0, 28, 20) # Lighter panel variant
    BG_INPUT = (0, 30, 25)       # Input field background
    
    # Foreground colors (phosphor green theme)
    FG_PRIMARY = (0, 255, 120)   # Bright green (main text)
    FG_DIM = (0, 180, 80)        # Dimmed green (secondary text)
    FG_DARK = (0, 120, 50)       # Dark green (disabled, borders)
    FG_BRIGHT = (120, 255, 180)  # Very bright green (highlights)
    
    # Accent colors
    ACCENT_CYAN = (0, 255, 255)    # Cyan (selection, focus)
    ACCENT_YELLOW = (255, 255, 0)  # Yellow (warnings, important)
    ACCENT_ORANGE = (255, 160, 0)  # Orange (alerts)
    ACCENT_RED = (255, 60, 60)     # Red (errors, critical)
    ACCENT_BLUE = (80, 120, 255)   # Blue (info, links)
    ACCENT_PURPLE = (200, 80, 255) # Purple (special)
    
    # Star colors (temperature-based)
    STAR_BLUE = (180, 200, 255)    # Hot stars (O, B)
    STAR_WHITE = (255, 255, 255)   # White stars (A, F)
    STAR_YELLOW = (255, 240, 180)  # Yellow stars (G, like Sun)
    STAR_ORANGE = (255, 200, 120)  # Orange stars (K)
    STAR_RED = (255, 150, 100)     # Cool stars (M)
    
    # UI element colors
    BUTTON_NORMAL = FG_PRIMARY
    BUTTON_HOVER = ACCENT_CYAN
    BUTTON_PRESSED = ACCENT_YELLOW
    BUTTON_DISABLED = FG_DARK
    
    BORDER_NORMAL = FG_PRIMARY
    BORDER_FOCUS = ACCENT_CYAN
    BORDER_DISABLED = FG_DARK
    
    # Semantic colors
    SUCCESS = (0, 255, 100)
    WARNING = ACCENT_YELLOW
    ERROR = ACCENT_RED
    INFO = ACCENT_BLUE
    
    @staticmethod
    def lerp_color(color1: Tuple[int, int, int], 
                   color2: Tuple[int, int, int], 
                   t: float) -> Tuple[int, int, int]:
        """
        Linearly interpolate between two colors
        
        Args:
            color1: Start color (RGB)
            color2: End color (RGB)
            t: Interpolation factor (0-1)
            
        Returns:
            Interpolated color
        """
        r = int(color1[0] + (color2[0] - color1[0]) * t)
        g = int(color1[1] + (color2[1] - color1[1]) * t)
        b = int(color1[2] + (color2[2] - color1[2]) * t)
        return (r, g, b)
    
    @staticmethod
    def temperature_to_color(temp_k: float) -> Tuple[int, int, int]:
        """
        Convert stellar temperature to RGB color
        
        Args:
            temp_k: Temperature in Kelvin
            
        Returns:
            RGB color tuple
        """
        if temp_k > 10000:
            return Colors.STAR_BLUE
        elif temp_k > 7500:
            return Colors.STAR_WHITE
        elif temp_k > 6000:
            return Colors.STAR_YELLOW
        elif temp_k > 5000:
            return Colors.STAR_ORANGE
        else:
            return Colors.STAR_RED


@dataclass
class FontConfig:
    """Font configuration"""
    family: str = "Consolas"
    size_title: int = 24
    size_large: int = 20
    size_normal: int = 18
    size_small: int = 14
    size_tiny: int = 12
    bold_title: bool = True


class Fonts:
    """
    Font manager
    
    Loads and caches monospaced fonts for retro DOS aesthetic.
    """
    
    _initialized = False
    _fonts: dict = {}
    _config = FontConfig()
    
    @classmethod
    def initialize(cls, config: FontConfig = None):
        """
        Initialize fonts
        
        Args:
            config: Font configuration (optional)
        """
        if config is not None:
            cls._config = config
        
        pygame.font.init()
        
        # Try to load Consolas, fall back to Courier
        families = [cls._config.family, "Courier New", "Courier", "monospace"]
        
        for family in families:
            try:
                cls._fonts['title'] = pygame.font.SysFont(
                    family, cls._config.size_title, bold=cls._config.bold_title
                )
                cls._fonts['large'] = pygame.font.SysFont(family, cls._config.size_large)
                cls._fonts['normal'] = pygame.font.SysFont(family, cls._config.size_normal)
                cls._fonts['small'] = pygame.font.SysFont(family, cls._config.size_small)
                cls._fonts['tiny'] = pygame.font.SysFont(family, cls._config.size_tiny)
                
                cls._initialized = True
                break
            except:
                continue
        
        if not cls._initialized:
            # Ultimate fallback: pygame default font
            cls._fonts['title'] = pygame.font.Font(None, cls._config.size_title)
            cls._fonts['large'] = pygame.font.Font(None, cls._config.size_large)
            cls._fonts['normal'] = pygame.font.Font(None, cls._config.size_normal)
            cls._fonts['small'] = pygame.font.Font(None, cls._config.size_small)
            cls._fonts['tiny'] = pygame.font.Font(None, cls._config.size_tiny)
            cls._initialized = True
    
    @classmethod
    def get(cls, size: str = 'normal') -> pygame.font.Font:
        """
        Get font by size name
        
        Args:
            size: 'title', 'large', 'normal', 'small', or 'tiny'
            
        Returns:
            Pygame font object
        """
        if not cls._initialized:
            cls.initialize()
        
        return cls._fonts.get(size, cls._fonts['normal'])
    
    @classmethod
    def title(cls) -> pygame.font.Font:
        return cls.get('title')
    
    @classmethod
    def large(cls) -> pygame.font.Font:
        return cls.get('large')
    
    @classmethod
    def normal(cls) -> pygame.font.Font:
        return cls.get('normal')
    
    @classmethod
    def small(cls) -> pygame.font.Font:
        return cls.get('small')
    
    @classmethod
    def tiny(cls) -> pygame.font.Font:
        return cls.get('tiny')


class Theme:
    """
    Complete theme configuration
    
    Bundles colors, fonts, and spacing into single object.
    """
    
    def __init__(self):
        """Initialize theme"""
        self.colors = Colors()
        self.fonts = Fonts()
        
        # Spacing and sizing
        self.padding = 8
        self.margin = 12
        self.border_width = 2
        
        # Component sizes
        self.button_height = 32
        self.input_height = 28
        self.scrollbar_width = 16
        
        # Animation
        self.hover_transition_ms = 100
        self.click_transition_ms = 50
    
    def draw_border(self, surface: pygame.Surface, rect: pygame.Rect,
                   color: Tuple[int, int, int], width: int = None):
        """
        Draw VGA-style border (pixelated, no antialiasing)
        
        Args:
            surface: Target surface
            rect: Rectangle to border
            color: Border color
            width: Border width (None = use theme default)
        """
        if width is None:
            width = self.border_width
        
        pygame.draw.rect(surface, color, rect, width)
    
    def draw_panel(self, surface: pygame.Surface, rect: pygame.Rect,
                  title: str = "",
                  fg_color: Tuple[int, int, int] = None,
                  bg_color: Tuple[int, int, int] = None):
        """
        Draw panel with border (standard UI element)
        
        Args:
            surface: Target surface
            rect: Panel rectangle
            title: Optional title text
            fg_color: Border color (None = use default)
            bg_color: Fill color (None = use default)
        """
        if fg_color is None:
            fg_color = self.colors.BORDER_NORMAL
        if bg_color is None:
            bg_color = self.colors.BG_PANEL
        
        # Fill background
        pygame.draw.rect(surface, bg_color, rect)
        
        # Draw border
        self.draw_border(surface, rect, fg_color)
        
        # Draw title if provided
        if title:
            self.draw_text(surface, self.fonts.normal(),
                         rect.x + 10, rect.y + 8,
                         title, fg_color)
    
    def draw_text(self, surface: pygame.Surface, font: pygame.font.Font,
                 x: int, y: int, text: str, color: Tuple[int, int, int],
                 align: str = 'left'):
        """
        Draw text (no antialiasing for pixel-perfect rendering)
        
        Args:
            surface: Target surface
            font: Font to use
            x, y: Position
            text: Text to render
            color: Text color
            align: 'left', 'center', or 'right'
        """
        rendered = font.render(text, False, color)  # False = no AA
        
        if align == 'center':
            x -= rendered.get_width() // 2
        elif align == 'right':
            x -= rendered.get_width()
        
        surface.blit(rendered, (x, y))
    
    def draw_progress_bar(self, surface: pygame.Surface, rect: pygame.Rect,
                         progress: float, color: Tuple[int, int, int] = None):
        """
        Draw progress bar
        
        Args:
            surface: Target surface
            rect: Bar rectangle
            progress: Progress value (0-1)
            color: Fill color (None = use primary)
        """
        if color is None:
            color = self.colors.FG_PRIMARY
        
        # Border
        self.draw_border(surface, rect, self.colors.BORDER_NORMAL)
        
        # Fill
        fill_width = int((rect.width - 4) * progress)
        if fill_width > 0:
            fill_rect = pygame.Rect(rect.x + 2, rect.y + 2, 
                                   fill_width, rect.height - 4)
            pygame.draw.rect(surface, color, fill_rect)


# Global theme instance
_theme = None

def get_theme() -> Theme:
    """Get global theme instance"""
    global _theme
    if _theme is None:
        _theme = Theme()
        _theme.fonts.initialize()
    return _theme
