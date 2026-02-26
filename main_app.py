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

# GPU support (optional — graceful fallback if ModernGL is not installed)
import gpu

# numpy is used by the GPU bridge (Surface → texture upload); import once here
# so the per-frame path in _blit_offscreen_to_gpu() pays no import cost.
try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

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
from ui_new.navigation_manager import NavigationManager
from ui_new.screen_main_menu import MainMenuScreen
from ui_new.screen_content_manager import ContentManagerScreen

# Window settings
WIDTH, HEIGHT = 1280, 800
FPS = 60
TITLE = "Observatory Simulation - Alpha v0.2"

# ---------------------------------------------------------------------------
# Passthrough fragment shader — uploads offscreen Pygame Surface to the
# OpenGL window via a fullscreen quad.  Y-axis is flipped because Pygame
# surfaces have Y=0 at the top while OpenGL has Y=0 at the bottom.
# ---------------------------------------------------------------------------
_PASSTHROUGH_FRAGMENT = """
#version 330
uniform sampler2D u_texture;
out vec4 fragColor;
in vec2 uv;
void main() {
    fragColor = texture(u_texture, vec2(uv.x, 1.0 - uv.y));
}
"""


class ObservatoryGame:
    """
    Main game application
    
    Manages the game loop, state, and screen coordination.
    """
    
    def __init__(self):
        """Initialize game"""
        # Parse command line flags
        no_gpu = '--no-gpu' in sys.argv

        # Initialize Pygame
        pygame.init()

        # Window settings (can be changed with F11 or resized)
        self.fullscreen = False

        # GPU state
        self.gpu_enabled = False
        self.gpu_ctx = None
        self._offscreen_surface = None
        self._rgba_buf = None
        self._screen_tex = None
        self._passthrough_prog = None
        self._passthrough_vao = None

        print(f"\n{TITLE}")
        print("=" * 60)

        if gpu.GPU_AVAILABLE and not no_gpu:
            try:
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
                pygame.display.gl_set_attribute(
                    pygame.GL_CONTEXT_PROFILE_MASK,
                    pygame.GL_CONTEXT_PROFILE_CORE,
                )
                self.screen = pygame.display.set_mode(
                    (WIDTH, HEIGHT),
                    pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE,
                )
                import moderngl
                self.gpu_ctx = moderngl.create_context()
                self._init_gpu_bridge(WIDTH, HEIGHT)
                self.gpu_enabled = True
                print(f"GPU: enabled — {self.gpu_ctx.info['GL_RENDERER']}")
                print(f"     OpenGL {self.gpu_ctx.info['GL_VERSION']}")
            except Exception as exc:
                print(f"GPU: disabled (OpenGL init failed: {exc})")
                self.gpu_ctx = None
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        elif not gpu.GPU_AVAILABLE and not no_gpu:
            print("GPU: disabled (ModernGL not installed)")
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        else:
            print("GPU: disabled (--no-gpu flag)")
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        # Initialize theme
        self.theme = get_theme()

        # Create state manager
        self.state_manager = StateManager()

        # Share the GPU context so screens can reuse it instead of creating
        # a second ModernGL context (which would cause a black-screen conflict).
        self.state_manager.gpu_ctx = self.gpu_ctx

        # Navigation manager
        self.nav_manager = NavigationManager(initial_screen='MAIN_MENU')

        # Register screens
        self._register_screens()

        # Start at Main Menu
        self.state_manager.switch_to('MAIN_MENU', push_stack=False)

        self.running = True
        print("Initialized successfully!")
        print("=" * 60)
    
    def _register_screens(self):
        """Register all game screens"""
        # Main menu
        self.state_manager.register_screen('MAIN_MENU', MainMenuScreen(self.state_manager))
        
        # Settings / content manager
        self.state_manager.register_screen('CONTENT_MANAGER', ContentManagerScreen(self.state_manager))
        
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

    # -----------------------------------------------------------------------
    # GPU bridge helpers
    # -----------------------------------------------------------------------

    def _init_gpu_bridge(self, width: int, height: int) -> None:
        """Set up the offscreen Surface → GPU texture passthrough bridge.

        Must be called after moderngl.create_context() so that self.gpu_ctx
        is valid.  Safe to call again after a context re-creation (fullscreen
        toggle) — old GL objects are already freed by the driver.
        """
        import moderngl
        from gpu.shaders import VERTEX_SHADER

        self._offscreen_surface = pygame.Surface((width, height))
        # Pre-allocated RGBA buffer reused every frame to avoid per-frame alloc
        self._rgba_buf = np.empty((height, width, 4), dtype=np.uint8)
        self._rgba_buf[:, :, 3] = 255  # alpha always opaque

        # Compile passthrough shader program
        self._passthrough_prog = self.gpu_ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=_PASSTHROUGH_FRAGMENT,
        )

        # Fullscreen quad: position (x, y) + texcoord (u, v)
        _verts = np.array([
            -1, -1,  0, 0,
             1, -1,  1, 0,
            -1,  1,  0, 1,
             1,  1,  1, 1,
        ], dtype='f4')
        _vbo = self.gpu_ctx.buffer(_verts.tobytes())
        self._passthrough_vao = self.gpu_ctx.vertex_array(
            self._passthrough_prog,
            [(_vbo, '2f 2f', 'in_position', 'in_texcoord')],
        )

        # RGBA uint8 GPU texture (matches window size; recreated on resize)
        self._screen_tex = self.gpu_ctx.texture((width, height), 4, dtype='u1')
        self._screen_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

    def _resize_gpu_bridge(self, width: int, height: int) -> None:
        """Resize the offscreen surface and GPU texture after a window resize."""
        import moderngl

        self._offscreen_surface = pygame.Surface((width, height))
        self._rgba_buf = np.empty((height, width, 4), dtype=np.uint8)
        self._rgba_buf[:, :, 3] = 255
        if self._screen_tex is not None:
            self._screen_tex.release()
        self._screen_tex = self.gpu_ctx.texture((width, height), 4, dtype='u1')
        self._screen_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

    def _blit_offscreen_to_gpu(self) -> None:
        """Upload the offscreen surface to a GPU texture and render it to screen.

        Pipeline: pygame.Surface → numpy RGBA → GPU texture → fullscreen quad.
        The RGBA buffer is pre-allocated in _init_gpu_bridge / _resize_gpu_bridge
        so this path makes no heap allocations beyond the surfarray view.
        """
        import moderngl

        arr = pygame.surfarray.array3d(self._offscreen_surface)  # (W, H, 3) uint8
        self._rgba_buf[:, :, :3] = arr.transpose(1, 0, 2)        # (H, W, 3) → in-place
        self._screen_tex.write(self._rgba_buf.tobytes())

        sw, sh = pygame.display.get_surface().get_size()
        self.gpu_ctx.screen.use()
        self.gpu_ctx.viewport = (0, 0, sw, sh)
        self.gpu_ctx.clear(0.0, 0.0, 0.0)
        self._screen_tex.use(location=0)
        self._passthrough_prog['u_texture'].value = 0
        self._passthrough_vao.render(moderngl.TRIANGLE_STRIP)
    
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
                
                # Global navigation hotkeys (H=home) BEFORE screen handles input
                nav_target = self.nav_manager.handle_global_hotkeys(event)
                if nav_target:
                    self.state_manager.switch_to(nav_target)
            
            # Let state manager handle input
            self.state_manager.handle_input(events)
            
            # Update
            self.state_manager.update(dt)
            
            # Render
            render_target = self._offscreen_surface if self.gpu_enabled else self.screen
            render_target.fill(self.theme.colors.BG_DARK)
            self.state_manager.render(render_target)
            
            # Display FPS (optional, for debugging)
            if False:  # Set to True to show FPS
                fps_text = f"FPS: {int(self.clock.get_fps())}"
                font = self.theme.fonts.tiny()
                rendered = font.render(fps_text, False, self.theme.colors.FG_DARK)
                render_target.blit(rendered, (WIDTH - 80, 10))

            # GPU mode: upload offscreen Surface → texture → fullscreen quad
            if self.gpu_enabled:
                self._blit_offscreen_to_gpu()
            
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
            flags = pygame.FULLSCREEN
            if self.gpu_enabled:
                flags |= pygame.OPENGL | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode((width, height), flags)
            print(f"Switched to fullscreen: {width}x{height}")
        else:
            # Return to windowed mode
            width, height = WIDTH, HEIGHT
            flags = pygame.RESIZABLE
            if self.gpu_enabled:
                flags |= pygame.OPENGL | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode((width, height), flags)
            print(f"Switched to windowed: {width}x{height}")

        if self.gpu_enabled:
            try:
                import moderngl
                self.gpu_ctx = moderngl.create_context()
                self._init_gpu_bridge(width, height)
            except Exception as exc:
                print(f"GPU: context lost during fullscreen toggle ({exc}), falling back to software")
                self.gpu_enabled = False
                self.gpu_ctx = None
    
    def handle_resize(self, width: int, height: int):
        """Handle window resize event"""
        if not self.fullscreen:
            if self.gpu_enabled:
                # OpenGL viewport updates automatically; just resize the bridge
                self._resize_gpu_bridge(width, height)
            else:
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
