"""
Navigation Manager — unified screen navigation with stack and global hotkeys.

Hotkeys:
  H   → HOME (OBSERVATORY)
  ESC → back (pop stack)
"""

import pygame
from typing import Optional


class NavigationManager:
    """
    Manages a navigation stack and handles global hotkeys (H=home, ESC=back).

    Usage:
        nav = NavigationManager(initial_screen='MAIN_MENU')
        # in game loop:
        target = nav.handle_global_hotkeys(event)
        if target:
            state_manager.switch_to(target)
    """

    def __init__(self, initial_screen: str = 'MAIN_MENU'):
        self._stack: list[str] = []
        self._current: str = initial_screen

    def push(self, screen: str) -> None:
        """Push current screen onto stack and navigate to new screen."""
        self._stack.append(self._current)
        self._current = screen

    def pop(self) -> Optional[str]:
        """Pop stack and return previous screen, or None if stack is empty."""
        if self._stack:
            self._current = self._stack.pop()
            return self._current
        return None

    def go_home(self) -> str:
        """Clear stack and return to OBSERVATORY (hub)."""
        self._stack.clear()
        self._current = 'OBSERVATORY'
        return self._current

    def handle_global_hotkeys(self, event) -> Optional[str]:
        """
        Check a single pygame event for global navigation hotkeys.

        Args:
            event: A pygame.event.Event

        Returns:
            Screen name to switch to, or None if no global hotkey matched.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_h:
                return self.go_home()
        return None
