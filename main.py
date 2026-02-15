
import pygame
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from ui.screen_planetarium import PlanetariumScreen
from core.types import SkyObject

W, H = 1200, 720

@dataclass
class AppState:
    current_screen: str = "SKYCHART"
    selected: Optional[SkyObject] = None

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Astronomy Game - SkyChart (rewrite)")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Tahoma", 20)
    small = pygame.font.SysFont("Verdana", 14)

    app = AppState()
    skychart = PlanetariumScreen(data_dir=Path("data"))

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            else:
                skychart.handle_event(ev, app)

        skychart.update(dt, app)
        skychart.draw(screen, app, (font, small))
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
