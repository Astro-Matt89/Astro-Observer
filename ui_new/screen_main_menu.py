"""
Main Menu Screen

Entry point for the game with buttons:
  CAREER   → Career mode (CAREER screen)
  EXPLORE  → Observatory sandbox (OBSERVATORY screen)
  SETTINGS → Content manager (CONTENT_MANAGER screen)
  QUIT     → Exit application
"""

import pygame
import sys
from typing import Optional
from .base_screen import BaseScreen
from .components import Button, Panel


class MainMenuScreen(BaseScreen):
    """
    Main Menu — entry point of the game.

    Buttons: CAREER, EXPLORE, SETTINGS, QUIT.
    EXPLORE goes directly to OBSERVATORY (sandbox mode).
    """

    def __init__(self, state_manager=None):
        super().__init__("MAIN_MENU")
        self._state_manager = state_manager
        self._next_screen: Optional[str] = None
        self._buttons: dict[str, Button] = {}
        self._create_buttons()

    def _create_buttons(self) -> None:
        cx, cy = 640, 400
        bw, bh = 220, 60
        gap = 20

        self._buttons['career'] = Button(
            cx - bw // 2, cy - bh * 2 - gap,
            bw, bh, "CAREER",
            callback=lambda: self._navigate('CAREER')
        )
        self._buttons['explore'] = Button(
            cx - bw // 2, cy - bh - gap // 2,
            bw, bh, "EXPLORE",
            callback=lambda: self._navigate('OBSERVATORY')
        )
        self._buttons['settings'] = Button(
            cx - bw // 2, cy + gap // 2,
            bw, bh, "SETTINGS",
            callback=lambda: self._navigate('CONTENT_MANAGER')
        )
        self._buttons['quit'] = Button(
            cx - bw // 2, cy + bh + gap,
            bw, bh, "QUIT",
            callback=self._quit
        )

    def _navigate(self, screen: str) -> None:
        self._next_screen = screen

    def _quit(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def on_enter(self) -> None:
        super().on_enter()
        self._next_screen = None

    def on_exit(self) -> None:
        super().on_exit()

    def handle_input(self, events: list) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        for btn in self._buttons.values():
            btn.update(mouse_pos)

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._quit()

            for btn in self._buttons.values():
                if btn.handle_event(event):
                    break

        if self._next_screen:
            result = self._next_screen
            self._next_screen = None
            return result
        return None

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        W, H = surface.get_width(), surface.get_height()
        surface.fill(self.theme.colors.BG_DARK)

        # Title
        header = pygame.Rect(10, 10, W - 20, 80)
        self.draw_header(surface, header,
                         "OBSERVATORY SIMULATION",
                         "Alpha v0.2  —  Select a mode to begin")

        # Buttons
        for btn in self._buttons.values():
            btn.draw(surface)

        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                         "[EXPLORE] Sandbox mode  [CAREER] Structured play  [SETTINGS] Configure  [ESC/QUIT] Exit")
