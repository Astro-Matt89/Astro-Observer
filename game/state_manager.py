"""
Game State Manager

Manages game state and screen navigation.
Handles screen lifecycle and transitions.
"""

import pygame
from typing import Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
from .career_mode import CareerMode


@dataclass
class GameState:
    """Global game state"""
    # Mode
    mode: str = "SANDBOX"  # "SANDBOX" or "CAREER"
    
    # Time and location
    current_time: datetime = field(default_factory=datetime.now)
    observer_lat: float = 44.80  # Parma, IT
    observer_lon: float = 10.33
    observer_elevation: float = 50.0  # meters
    
    # Current selection
    selected_target: Optional[str] = None
    selected_target_ra: float = 0.0
    selected_target_dec: float = 0.0
    
    # Equipment (current setup)
    telescope_id: str = ""               # vuoto = nessun telescopio (allsky standalone)
    camera_id: str    = "ALLSKY_ZWO174MM"  # default: allsky per monitoraggio
    filter_id: str = "L"
    
    # Career mode (if applicable)
    research_points: int = 0
    owned_telescopes: list = field(default_factory=lambda: ["REF_80_F5"])
    owned_cameras: list = field(default_factory=lambda: ["WEBCAM_MOD"])
    owned_filters: list = field(default_factory=lambda: ["L"])
    
    # Statistics
    total_exposures: int = 0
    total_integration_time_s: float = 0.0
    objects_imaged: set = field(default_factory=set)
    discoveries: list = field(default_factory=list)


class StateManager:
    """
    Manages game state and screen navigation
    
    Responsibilities:
    - Screen registration and lifecycle
    - Navigation between screens
    - Global state management
    - Screen stack for back navigation
    """
    
    def __init__(self):
        """Initialize state manager"""
        self.state = GameState()
        self.screens: Dict[str, 'BaseScreen'] = {}
        self.current_screen: Optional[str] = None
        self.screen_stack: list[str] = []  # For back navigation
        
        # Initialize career mode
        self.career_mode = CareerMode()
        
        # Initialize universe (single instance shared by all screens)
        from universe import build_universe
        self.universe = build_universe()
    
    def register_screen(self, name: str, screen: 'BaseScreen'):
        """
        Register a screen
        
        Args:
            name: Screen identifier
            screen: Screen instance
        """
        self.screens[name] = screen
        print(f"Registered screen: {name}")
    
    def switch_to(self, screen_name: str, push_stack: bool = True):
        """
        Switch to a screen
        
        Args:
            screen_name: Name of screen to switch to
            push_stack: If True, push current screen to stack (for back nav)
        """
        if screen_name not in self.screens:
            print(f"Warning: Screen '{screen_name}' not registered!")
            return
        
        # Exit current screen
        if self.current_screen and push_stack:
            self.screen_stack.append(self.current_screen)
            self.screens[self.current_screen].on_exit()
        elif self.current_screen:
            self.screens[self.current_screen].on_exit()
        
        # Enter new screen
        self.current_screen = screen_name
        self.screens[screen_name].on_enter()
        
        print(f"Switched to screen: {screen_name}")
    
    def go_back(self) -> bool:
        """
        Go back to previous screen
        
        Returns:
            True if went back, False if no previous screen
        """
        if not self.screen_stack:
            return False
        
        previous = self.screen_stack.pop()
        self.switch_to(previous, push_stack=False)
        return True
    
    def update(self, dt: float):
        """
        Update current screen
        
        Args:
            dt: Delta time in seconds
        """
        if self.current_screen:
            self.screens[self.current_screen].update(dt)
    
    def render(self, surface: pygame.Surface):
        """
        Render current screen
        
        Args:
            surface: Display surface
        """
        if self.current_screen:
            self.screens[self.current_screen].render(surface)
    
    def handle_input(self, events: list[pygame.event.Event]):
        """
        Handle input for current screen
        
        Args:
            events: List of pygame events
        """
        if not self.current_screen:
            return
        
        # Let current screen handle input
        next_screen = self.screens[self.current_screen].handle_input(events)
        
        # Check if screen requested navigation
        if next_screen:
            self.switch_to(next_screen)
    
    def get_state(self) -> GameState:
        """Get global game state"""
        return self.state
    
    def get_career_mode(self) -> CareerMode:
        """Get career mode manager"""
        return self.career_mode
    
    def get_universe(self):
        """Get the universe (single source of truth for all space objects)"""
        return self.universe
    
    def save_game(self, filepath: str = "savegame.json"):
        """
        Save complete game state
        
        Args:
            filepath: Path to save file
        """
        # Save game state
        self.save_state(filepath.replace('.json', '_state.json'))
        
        # Save career mode
        self.career_mode.save_to_file(filepath.replace('.json', '_career.json'))
        
        print(f"Game saved successfully!")
    
    def load_game(self, filepath: str = "savegame.json") -> bool:
        """
        Load complete game state
        
        Args:
            filepath: Path to save file
            
        Returns:
            True if loaded successfully
        """
        # Load game state
        state_loaded = self.load_state(filepath.replace('.json', '_state.json'))
        
        # Load career mode
        career_loaded = self.career_mode.load_from_file(filepath.replace('.json', '_career.json'))
        
        if state_loaded and career_loaded:
            print(f"Game loaded successfully!")
            return True
        else:
            print(f"Failed to load game")
            return False
    
    def save_state(self, filepath: str):
        """
        Save game state to file
        
        Args:
            filepath: Path to save file
        """
        import json
        
        # Convert state to dict (simplified version)
        state_dict = {
            'mode': self.state.mode,
            'telescope_id': self.state.telescope_id,
            'camera_id': self.state.camera_id,
            'filter_id': self.state.filter_id,
            'research_points': self.state.research_points,
            'owned_telescopes': self.state.owned_telescopes,
            'owned_cameras': self.state.owned_cameras,
            'owned_filters': self.state.owned_filters,
            'total_exposures': self.state.total_exposures,
            'total_integration_time_s': self.state.total_integration_time_s,
            'objects_imaged': list(self.state.objects_imaged),
        }
        
        with open(filepath, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        # Save career mode separately
        career_filepath = filepath.replace('.json', '_career.json')
        self.career_mode.save_to_file(career_filepath)
        
        print(f"Game saved to: {filepath}")
    
    def load_state(self, filepath: str) -> bool:
        """
        Load game state from file
        
        Args:
            filepath: Path to save file
            
        Returns:
            True if loaded successfully
        """
        import json
        
        try:
            with open(filepath, 'r') as f:
                state_dict = json.load(f)
            
            # Restore state
            self.state.mode = state_dict.get('mode', 'SANDBOX')
            self.state.telescope_id = state_dict.get('telescope_id', '')
            self.state.camera_id = state_dict.get('camera_id', 'ALLSKY_ZWO174MM')
            self.state.filter_id = state_dict.get('filter_id', 'L')
            self.state.research_points = state_dict.get('research_points', 0)
            self.state.owned_telescopes = state_dict.get('owned_telescopes', [])
            self.state.owned_cameras = state_dict.get('owned_cameras', [])
            self.state.owned_filters = state_dict.get('owned_filters', [])
            self.state.total_exposures = state_dict.get('total_exposures', 0)
            self.state.total_integration_time_s = state_dict.get('total_integration_time_s', 0.0)
            self.state.objects_imaged = set(state_dict.get('objects_imaged', []))
            
            # Load career mode
            career_filepath = filepath.replace('.json', '_career.json')
            self.career_mode.load_from_file(career_filepath)
            
            print(f"Game loaded from: {filepath}")
            return True
        
        except Exception as e:
            print(f"Failed to load game: {e}")
            return False
