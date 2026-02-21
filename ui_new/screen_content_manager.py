"""
Content Manager Screen (Settings)

Settings screen with 3 tabs: CATALOGS, EQUIPMENT, GRAPHICS.
"""

import pygame
from typing import Optional
from .base_screen import BaseScreen
from .components import Button, Panel


class ContentManagerScreen(BaseScreen):
    """
    Settings / Content Manager — 3-tab settings screen.

    Tabs: CATALOGS, EQUIPMENT, GRAPHICS.
    """

    TABS = ['CATALOGS', 'EQUIPMENT', 'GRAPHICS']

    def __init__(self, state_manager=None):
        super().__init__("CONTENT_MANAGER")
        self._state_manager = state_manager
        self._current_tab = 0
        self._tab_buttons: list[Button] = []
        self._create_tab_buttons()

    def _create_tab_buttons(self) -> None:
        tab_w = 140
        gap = 10
        start_x = 20
        y = 100
        for i, name in enumerate(self.TABS):
            x = start_x + i * (tab_w + gap)
            self._tab_buttons.append(
                Button(x, y, tab_w, 34, name,
                       callback=lambda i=i: self._set_tab(i))
            )

    def _set_tab(self, idx: int) -> None:
        self._current_tab = idx

    def on_enter(self) -> None:
        super().on_enter()

    def on_exit(self) -> None:
        super().on_exit()

    def handle_input(self, events: list) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        for btn in self._tab_buttons:
            btn.update(mouse_pos)

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return 'MAIN_MENU'
                elif event.key == pygame.K_TAB:
                    self._current_tab = (self._current_tab + 1) % len(self.TABS)

            for btn in self._tab_buttons:
                if btn.handle_event(event):
                    break

        return None

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        W, H = surface.get_width(), surface.get_height()
        surface.fill(self.theme.colors.BG_DARK)

        # Header
        header = pygame.Rect(10, 10, W - 20, 80)
        self.draw_header(surface, header,
                         "CONTENT MANAGER",
                         "Catalogs, Equipment, and Graphics settings")

        # Tab buttons
        for i, btn in enumerate(self._tab_buttons):
            if i == self._current_tab:
                pygame.draw.rect(surface, self.theme.colors.ACCENT_CYAN,
                                 btn.rect.inflate(4, 4), 2)
            btn.draw(surface)

        # Content area
        content = pygame.Rect(10, 148, W - 20, H - 210)
        self.theme.draw_panel(surface, content, self.TABS[self._current_tab])

        tab_name = self.TABS[self._current_tab]
        msg = f"{tab_name} settings — coming soon"
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                             content.centerx, content.centery,
                             msg, self.theme.colors.FG_DIM, align='center')

        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                         "[TAB] Switch tab  [ESC] Back to Main Menu")
