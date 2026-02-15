"""
Observatory Simulation Game - Main Application

Complete integrated application with:
- Observatory Hub (central menu)
- Screen navigation
- State management
- Multiple screens (Observatory, Imaging, Sky Chart, etc.)
"""

import pygame
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import state manager
from game.state_manager import StateManager

# Import UI
from ui_new.theme import get_theme
from ui_new.screen_observatory import ObservatoryScreen
from ui_new.screen_imaging import ImagingScreen
from ui_new.screen_catalog import CatalogScreen
from ui_new.screen_equipment import EquipmentScreen
from ui_new.screen_career import CareerScreen
from ui_new.screen_skychart import SkychartScreen
from ui_new.base_screen import EmptyScreen

# Window settings
WIDTH, HEIGHT = 1280, 800
FPS = 60
TITLE = "Observatory Simulation - Alpha v0.2"


class ObservatoryGame:
    """
    Main game application
    
    Manages the game loop, state, and screen coordination.
    """
    
    def __init__(self):
        """Initialize game"""
        # Initialize Pygame
        pygame.init()
        
        # Window settings (can be changed with F11 or resized)
        self.fullscreen = False
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        
        # Initialize theme
        self.theme = get_theme()
        
        # Create state manager
        self.state_manager = StateManager()
        
        # Register screens
        self._register_screens()
        
        # Start at Observatory Hub
        self.state_manager.switch_to('OBSERVATORY', push_stack=False)
        
        self.running = True
        print(f"\n{TITLE}")
        print("=" * 60)
        print("Initialized successfully!")
        print("=" * 60)
    
    def _register_screens(self):
        """Register all game screens"""
        # Main observatory hub
        self.state_manager.register_screen('OBSERVATORY', ObservatoryScreen(self.state_manager))
        
        # Imaging system (COMPLETE!)
        self.state_manager.register_screen('IMAGING', ImagingScreen(self.state_manager))
        
        # Catalog browser (COMPLETE!)
        self.state_manager.register_screen('CATALOGS', CatalogScreen(self.state_manager))
        
        # Equipment manager (COMPLETE!)
        self.state_manager.register_screen('EQUIPMENT', EquipmentScreen(self.state_manager))
        
        # Career/Missions screen (COMPLETE!)
        self.state_manager.register_screen('CAREER', CareerScreen(self.state_manager))
        
        # Sky Chart (COMPLETE!)
        self.state_manager.register_screen('SKYCHART', SkychartScreen(self.state_manager))
    
    def run(self):
        """Main game loop"""
        print("\nStarting main loop...")
        print("Press ESC at Observatory Hub to quit\n")
        
        while self.running:
            # Calculate delta time
            dt = self.clock.tick(FPS) / 1000.0  # Convert to seconds
            
            # Handle events
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                
                # Toggle fullscreen with F11
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                
                # Handle window resize
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event.w, event.h)
            
            # Let state manager handle input
            self.state_manager.handle_input(events)
            
            # Update
            self.state_manager.update(dt)
            
            # Render
            self.screen.fill(self.theme.colors.BG_DARK)
            self.state_manager.render(self.screen)
            
            # Display FPS (optional, for debugging)
            if False:  # Set to True to show FPS
                fps_text = f"FPS: {int(self.clock.get_fps())}"
                font = self.theme.fonts.tiny()
                rendered = font.render(fps_text, False, self.theme.colors.FG_DARK)
                self.screen.blit(rendered, (WIDTH - 80, 10))
            
            pygame.display.flip()
        
        # Cleanup
        self.quit()
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        self.fullscreen = not self.fullscreen
        
        if self.fullscreen:
            # Get desktop size
            display_info = pygame.display.Info()
            width, height = display_info.current_w, display_info.current_h
            self.screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
            print(f"Switched to fullscreen: {width}x{height}")
        else:
            # Return to windowed mode
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
            print(f"Switched to windowed: {WIDTH}x{HEIGHT}")
    
    def handle_resize(self, width: int, height: int):
        """Handle window resize event"""
        if not self.fullscreen:
            self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
            print(f"Window resized to: {width}x{height}")
    
    def quit(self):
        """Cleanup and quit"""
        print("\nShutting down...")
        print("Thank you for using Observatory Simulation!")
        pygame.quit()
        sys.exit(0)


def main():
    """Entry point"""
    try:
        game = ObservatoryGame()
        game.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        pygame.quit()
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)


if __name__ == "__main__":
    main()
