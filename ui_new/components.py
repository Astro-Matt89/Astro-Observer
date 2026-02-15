"""
UI Components - Reusable UI Elements

VGA-style retro components for the Observatory game:
- Button: Interactive button with hover/click states
- Panel: Container with border
- TextInput: Text input field
- Label: Static text label
- ScrollableList: Scrollable list of items
- ProgressBar: Progress indicator
- Checkbox: Toggle checkbox
"""

import pygame
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from .theme import get_theme, Colors


@dataclass
class ButtonState:
    """Button state"""
    normal: bool = True
    hovered: bool = False
    pressed: bool = False
    disabled: bool = False


class Button:
    """
    Interactive button component
    
    VGA-style button with hover and click states.
    """
    
    def __init__(self, x: int, y: int, width: int, height: int, 
                 text: str, callback: Optional[Callable] = None):
        """
        Initialize button
        
        Args:
            x, y: Position
            width, height: Size
            text: Button text
            callback: Function to call when clicked
        """
        self._x0 = x; self._y0 = y
        self._w0 = width; self._h0 = height
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.state = ButtonState()
        self.enabled = True
        self.theme = get_theme()
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input event
        
        Args:
            event: Pygame event
            
        Returns:
            True if event was handled
        """
        if not self.enabled:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.state.pressed = True
                return True
        
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.state.pressed and self.rect.collidepoint(event.pos):
                self.state.pressed = False
                if self.callback:
                    self.callback()
                return True
            self.state.pressed = False
        
        return False
    
    def update(self, mouse_pos: Tuple[int, int]):
        """Update button state based on mouse position"""
        if not self.enabled:
            self.state.hovered = False
            return
        
        self.state.hovered = self.rect.collidepoint(mouse_pos)
    
    def draw(self, surface: pygame.Surface, x_scale: float = 1.0):
        """Draw button, optionally scaling x-position and width."""
        if x_scale != 1.0:
            self.rect = pygame.Rect(
                int(self._x0 * x_scale), self._y0,
                max(30, int(self._w0 * x_scale)), self._h0)

        # Determine colors based on state
        if not self.enabled:
            bg_color = self.theme.colors.BG_PANEL
            fg_color = self.theme.colors.BUTTON_DISABLED
            border_color = self.theme.colors.BORDER_DISABLED
        elif self.state.pressed:
            bg_color = self.theme.colors.ACCENT_YELLOW
            fg_color = self.theme.colors.BG_DARK
            border_color = self.theme.colors.ACCENT_YELLOW
        elif self.state.hovered:
            bg_color = self.theme.colors.BG_PANEL_LIGHT
            fg_color = self.theme.colors.BUTTON_HOVER
            border_color = self.theme.colors.BORDER_FOCUS
        else:
            bg_color = self.theme.colors.BG_PANEL
            fg_color = self.theme.colors.BUTTON_NORMAL
            border_color = self.theme.colors.BORDER_NORMAL
        
        # Draw background
        pygame.draw.rect(surface, bg_color, self.rect)
        
        # Draw border
        pygame.draw.rect(surface, border_color, self.rect, 2)
        
        # Draw text (centered)
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           self.rect.centerx, self.rect.centery - 8,
                           self.text, fg_color, align='center')
    
    def set_enabled(self, enabled: bool):
        """Enable/disable button"""
        self.enabled = enabled
        if not enabled:
            self.state = ButtonState(disabled=True)


class Panel:
    """
    Container panel with border
    
    Simple rectangular container with VGA-style border.
    """
    
    def __init__(self, x: int, y: int, width: int, height: int, 
                 title: str = ""):
        """
        Initialize panel
        
        Args:
            x, y: Position
            width, height: Size
            title: Optional title text
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.title = title
        self.theme = get_theme()
    
    def draw(self, surface: pygame.Surface, 
             bg_color: Optional[Tuple[int, int, int]] = None,
             fg_color: Optional[Tuple[int, int, int]] = None):
        """
        Draw panel
        
        Args:
            surface: Target surface
            bg_color: Background color (None = use theme default)
            fg_color: Border/text color (None = use theme default)
        """
        if bg_color is None:
            bg_color = self.theme.colors.BG_PANEL
        if fg_color is None:
            fg_color = self.theme.colors.FG_PRIMARY
        
        # Draw background
        pygame.draw.rect(surface, bg_color, self.rect)
        
        # Draw border
        pygame.draw.rect(surface, fg_color, self.rect, 2)
        
        # Draw title
        if self.title:
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               self.rect.x + 10, self.rect.y + 8,
                               self.title, fg_color)


class Label:
    """
    Static text label
    
    Simple text display with configurable font and color.
    """
    
    def __init__(self, x: int, y: int, text: str, 
                 font_size: str = 'normal', 
                 color: Optional[Tuple[int, int, int]] = None):
        """
        Initialize label
        
        Args:
            x, y: Position
            text: Label text
            font_size: Font size ('tiny', 'small', 'normal', 'large', 'title')
            color: Text color (None = use theme default)
        """
        self.x = x
        self.y = y
        self.text = text
        self.font_size = font_size
        self.color = color
        self.theme = get_theme()
    
    def draw(self, surface: pygame.Surface):
        """Draw label"""
        color = self.color if self.color else self.theme.colors.FG_PRIMARY
        font = self.theme.fonts.get(self.font_size)
        self.theme.draw_text(surface, font, self.x, self.y, self.text, color)
    
    def set_text(self, text: str):
        """Update label text"""
        self.text = text


class TextInput:
    """
    Text input field
    
    Single-line text input with cursor and basic editing.
    """
    
    def __init__(self, x: int, y: int, width: int, 
                 placeholder: str = "", max_length: int = 50):
        """
        Initialize text input
        
        Args:
            x, y: Position
            width: Input width
            placeholder: Placeholder text
            max_length: Maximum text length
        """
        self.rect = pygame.Rect(x, y, width, 28)
        self.text = ""
        self.placeholder = placeholder
        self.max_length = max_length
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
        self.theme = get_theme()
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input event
        
        Args:
            event: Pygame event
            
        Returns:
            True if event was handled
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            return self.active
        
        if self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif len(self.text) < self.max_length:
                if event.unicode.isprintable():
                    self.text += event.unicode
            return True
        
        return False
    
    def update(self, dt: float):
        """Update cursor blink"""
        self.cursor_timer += dt
        if self.cursor_timer > 0.5:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
    
    def draw(self, surface: pygame.Surface):
        """Draw text input"""
        # Background
        bg_color = self.theme.colors.BG_INPUT
        pygame.draw.rect(surface, bg_color, self.rect)
        
        # Border (highlighted if active)
        border_color = self.theme.colors.BORDER_FOCUS if self.active else self.theme.colors.BORDER_NORMAL
        pygame.draw.rect(surface, border_color, self.rect, 2)
        
        # Text or placeholder
        font = self.theme.fonts.small()
        if self.text:
            color = self.theme.colors.FG_PRIMARY
            text_to_draw = self.text
        else:
            color = self.theme.colors.FG_DARK
            text_to_draw = self.placeholder
        
        self.theme.draw_text(surface, font, 
                           self.rect.x + 8, self.rect.y + 6,
                           text_to_draw, color)
        
        # Cursor
        if self.active and self.cursor_visible and self.text:
            text_width = font.size(self.text)[0]
            cursor_x = self.rect.x + 8 + text_width + 2
            cursor_y = self.rect.y + 6
            pygame.draw.line(surface, self.theme.colors.FG_PRIMARY,
                           (cursor_x, cursor_y),
                           (cursor_x, cursor_y + 16), 2)
    
    def get_text(self) -> str:
        """Get current text"""
        return self.text
    
    def set_text(self, text: str):
        """Set text"""
        self.text = text[:self.max_length]
    
    def clear(self):
        """Clear text"""
        self.text = ""


class ScrollableList:
    """
    Scrollable list of items
    
    Displays a list of items with scrolling support.
    """
    
    def __init__(self, x: int, y: int, width: int, height: int,
                 item_height: int = 24):
        """
        Initialize scrollable list
        
        Args:
            x, y: Position
            width, height: Size
            item_height: Height of each item
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.item_height = item_height
        self.items: List[str] = []
        self.selected_index = -1
        self.scroll_offset = 0
        self.max_visible_items = height // item_height
        self.theme = get_theme()
    
    def set_items(self, items: List[str]):
        """Set list items"""
        self.items = items
        self.selected_index = 0 if items else -1
        self.scroll_offset = 0
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input event
        
        Args:
            event: Pygame event
            
        Returns:
            True if event was handled
        """
        if not self.items:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                # Check which item was clicked
                relative_y = event.pos[1] - self.rect.y
                item_index = relative_y // self.item_height + self.scroll_offset
                
                if 0 <= item_index < len(self.items):
                    self.selected_index = item_index
                    return True
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._ensure_visible(self.selected_index)
                return True
            elif event.key == pygame.K_DOWN:
                if self.selected_index < len(self.items) - 1:
                    self.selected_index += 1
                    self._ensure_visible(self.selected_index)
                return True
            elif event.key == pygame.K_PAGEUP:
                self.selected_index = max(0, self.selected_index - self.max_visible_items)
                self._ensure_visible(self.selected_index)
                return True
            elif event.key == pygame.K_PAGEDOWN:
                self.selected_index = min(len(self.items) - 1, 
                                        self.selected_index + self.max_visible_items)
                self._ensure_visible(self.selected_index)
                return True
        
        return False
    
    def _ensure_visible(self, index: int):
        """Ensure item at index is visible"""
        if index < self.scroll_offset:
            self.scroll_offset = index
        elif index >= self.scroll_offset + self.max_visible_items:
            self.scroll_offset = index - self.max_visible_items + 1
    
    def draw(self, surface: pygame.Surface):
        """Draw list"""
        # Background
        pygame.draw.rect(surface, self.theme.colors.BG_PANEL, self.rect)
        
        # Border
        pygame.draw.rect(surface, self.theme.colors.BORDER_NORMAL, self.rect, 2)
        
        # Items
        font = self.theme.fonts.small()
        visible_start = self.scroll_offset
        visible_end = min(len(self.items), self.scroll_offset + self.max_visible_items)
        
        for i in range(visible_start, visible_end):
            y = self.rect.y + (i - self.scroll_offset) * self.item_height + 4
            
            # Highlight selected item
            if i == self.selected_index:
                highlight_rect = pygame.Rect(self.rect.x + 2, y - 2,
                                            self.rect.width - 4, self.item_height)
                pygame.draw.rect(surface, self.theme.colors.BG_PANEL_LIGHT, highlight_rect)
                color = self.theme.colors.ACCENT_CYAN
            else:
                color = self.theme.colors.FG_PRIMARY
            
            # Draw item text
            text = self.items[i][:40]  # Truncate if too long
            self.theme.draw_text(surface, font, self.rect.x + 8, y, text, color)
        
        # Scrollbar (if needed)
        if len(self.items) > self.max_visible_items:
            scrollbar_height = max(20, (self.max_visible_items / len(self.items)) * self.rect.height)
            scrollbar_y = self.rect.y + (self.scroll_offset / len(self.items)) * self.rect.height
            
            scrollbar_rect = pygame.Rect(self.rect.right - 8, int(scrollbar_y),
                                        6, int(scrollbar_height))
            pygame.draw.rect(surface, self.theme.colors.FG_DARK, scrollbar_rect)
    
    def get_selected_item(self) -> Optional[str]:
        """Get currently selected item"""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None
    
    def get_selected_index(self) -> int:
        """Get selected index"""
        return self.selected_index


class Checkbox:
    """
    Toggle checkbox
    
    Simple checkbox for boolean options.
    """
    
    def __init__(self, x: int, y: int, label: str, checked: bool = False):
        """
        Initialize checkbox
        
        Args:
            x, y: Position
            label: Checkbox label
            checked: Initial state
        """
        self.rect = pygame.Rect(x, y, 20, 20)
        self.label = label
        self.checked = checked
        self.theme = get_theme()
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input event
        
        Args:
            event: Pygame event
            
        Returns:
            True if state changed
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check if clicked on checkbox or label
            label_rect = pygame.Rect(self.rect.right + 8, self.rect.y,
                                    200, self.rect.height)
            if self.rect.collidepoint(event.pos) or label_rect.collidepoint(event.pos):
                self.checked = not self.checked
                return True
        return False
    
    def draw(self, surface: pygame.Surface):
        """Draw checkbox"""
        # Box
        pygame.draw.rect(surface, self.theme.colors.BG_INPUT, self.rect)
        pygame.draw.rect(surface, self.theme.colors.BORDER_NORMAL, self.rect, 2)
        
        # Check mark
        if self.checked:
            # Draw X
            pygame.draw.line(surface, self.theme.colors.ACCENT_CYAN,
                           (self.rect.x + 4, self.rect.y + 4),
                           (self.rect.right - 4, self.rect.bottom - 4), 2)
            pygame.draw.line(surface, self.theme.colors.ACCENT_CYAN,
                           (self.rect.right - 4, self.rect.y + 4),
                           (self.rect.x + 4, self.rect.bottom - 4), 2)
        
        # Label
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           self.rect.right + 8, self.rect.y + 2,
                           self.label, self.theme.colors.FG_PRIMARY)
    
    def is_checked(self) -> bool:
        """Get checked state"""
        return self.checked
    
    def set_checked(self, checked: bool):
        """Set checked state"""
        self.checked = checked
