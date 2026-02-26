"""
Observatory Simulation Game - Main Application

GPU Bridge con auto-detection
==============================
All'avvio testa se il texture sampling funziona sul driver corrente.
Se funziona → GPU bridge (Surface → texture → quad → screen).
Se non funziona → software mode (pygame.display.flip() diretto).

In entrambi i casi, un contesto OpenGL standalone è disponibile per
gli schermi che usano GPU internamente (es. GPUSkyEngine).

Testato su:
  - NVIDIA 566.x: texture sampling rotto → auto-fallback a software
  - NVIDIA 572+: texture sampling OK → GPU bridge attivo
"""

import pygame
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import gpu

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

from game.state_manager import StateManager
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

WIDTH, HEIGHT = 1280, 800
FPS = 60
TITLE = "Observatory Simulation - Alpha v0.2"

_PASSTHROUGH_FRAGMENT = """
#version 330
uniform sampler2D u_texture;
out vec4 fragColor;
in vec2 uv;
void main() {
    fragColor = texture(u_texture, vec2(uv.x, 1.0 - uv.y));
}
"""


def _test_texture_sampling(ctx) -> bool:
    """
    Quick test: create a texture with known data, render via shader,
    readback and verify.  Returns True if texture sampling works.
    Takes ~2ms.
    """
    import moderngl

    VERT = """
    #version 330
    in vec2 in_position; in vec2 in_texcoord; out vec2 uv;
    void main() { gl_Position = vec4(in_position, 0.0, 1.0); uv = in_texcoord; }
    """
    FRAG = """
    #version 330
    uniform sampler2D u_texture; out vec4 fragColor; in vec2 uv;
    void main() { fragColor = texture(u_texture, uv); }
    """

    try:
        prog = ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
        verts = np.array([-1,-1,0,0, 1,-1,1,0, -1,1,0,1, 1,1,1,1], dtype='f4')
        vbo = ctx.buffer(verts.tobytes())
        vao = ctx.vertex_array(prog, [(vbo, '2f 2f', 'in_position', 'in_texcoord')])

        # 2x2 red texture
        data = np.array([
            255, 0, 0, 255,  255, 0, 0, 255,
            255, 0, 0, 255,  255, 0, 0, 255,
        ], dtype=np.uint8).tobytes()
        tex = ctx.texture((2, 2), 4, data=data, dtype='u1')
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        ctx.screen.use()
        ctx.viewport = (0, 0, 4, 4)
        ctx.clear(0.0, 0.0, 0.0)
        tex.use(location=0)
        prog['u_texture'].value = 0
        vao.render(moderngl.TRIANGLE_STRIP)

        px = ctx.screen.read(viewport=(1, 1, 1, 1), components=3)
        r = px[0]

        # Cleanup
        tex.release()
        vao.release()
        vbo.release()
        prog.release()

        return r > 200
    except Exception:
        return False


class ObservatoryGame:
    def __init__(self):
        self._want_gpu = gpu.GPU_AVAILABLE and ('--no-gpu' not in sys.argv)
        self._force_no_bridge = '--no-bridge' in sys.argv

        pygame.init()
        self.fullscreen = False

        # GPU state
        self.gpu_enabled = False   # GPU bridge for display
        self.gpu_ctx = None        # OpenGL context (may exist even without bridge)
        self._offscreen_surface = None
        self._screen_tex = None
        self._passthrough_prog = None
        self._passthrough_vao = None
        self._gpu_frame_count = 0

        print(f"\n{TITLE}")
        print("=" * 60)

        # ── STEP 1: Software window ─────────────────────────────────
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        # ── STEP 2: Heavy initialization ────────────────────────────
        self.theme = get_theme()
        self.state_manager = StateManager()
        self.nav_manager = NavigationManager(initial_screen='MAIN_MENU')
        self._register_screens()
        self.state_manager.switch_to('MAIN_MENU', push_stack=False)
        self.running = True
        print("All screens registered.")

        # ── STEP 3: GPU setup ───────────────────────────────────────
        if self._want_gpu and not self._force_no_bridge:
            self._try_gpu_upgrade()
        elif self._want_gpu and self._force_no_bridge:
            print("GPU bridge: disabled by --no-bridge flag")
            # Create standalone context for screens that need it
            self._init_standalone_gpu()
        elif not gpu.GPU_AVAILABLE:
            print("GPU: not available (ModernGL not installed)")
        else:
            print("GPU: disabled (--no-gpu flag)")

        self.state_manager.gpu_ctx = self.gpu_ctx

        mode = 'GPU bridge' if self.gpu_enabled else 'Software'
        if not self.gpu_enabled and self.gpu_ctx is not None:
            mode += ' + GPU compute available'
        print(f"\nRender mode: {mode}")
        print("Initialized successfully!")
        print("=" * 60)

    def _init_standalone_gpu(self):
        """Create a standalone moderngl context for compute/internal use."""
        try:
            import moderngl
            self.gpu_ctx = moderngl.create_context(standalone=True)
            print(f"  GPU compute: {self.gpu_ctx.info['GL_RENDERER']}")
        except Exception as exc:
            print(f"  GPU compute init failed: {exc}")
            self.gpu_ctx = None

    def _try_gpu_upgrade(self) -> None:
        print("\nAttempting GPU upgrade...")
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
            pygame.display.set_caption(TITLE)

            import moderngl
            self.gpu_ctx = moderngl.create_context()

            renderer = self.gpu_ctx.info['GL_RENDERER']
            gl_ver = self.gpu_ctx.info['GL_VERSION']
            print(f"  GL: {renderer}")
            print(f"  OpenGL {gl_ver}")

            # ── Quick texture sampling test ─────────────────────────
            print("  Testing texture sampling...", end=" ")
            if not _test_texture_sampling(self.gpu_ctx):
                print("FAILED!")
                print(f"  ⚠ Texture sampling broken on this driver ({gl_ver})")
                print(f"  ⚠ Consider updating your GPU drivers")
                raise RuntimeError("Texture sampling not functional")

            print("OK!")

            # Warmup
            self.gpu_ctx.screen.use()
            self.gpu_ctx.viewport = (0, 0, WIDTH, HEIGHT)
            self.gpu_ctx.clear(0.0, 0.05, 0.04)
            pygame.display.flip()

            # Build bridge
            self._init_gpu_bridge(WIDTH, HEIGHT)

            # Verification render
            self._offscreen_surface.fill((0, 200, 100))
            self._blit_offscreen_to_gpu()
            px = self.gpu_ctx.screen.read(
                viewport=(WIDTH // 2, HEIGHT // 2, 1, 1), components=3
            )
            r, g, b = px[0], px[1], px[2]
            print(f"  Bridge verification: RGB({r}, {g}, {b})")

            if g < 50:
                raise RuntimeError(f"Bridge verification failed: ({r},{g},{b})")

            pygame.display.flip()
            self.gpu_enabled = True
            print("  ✓ GPU bridge active!")

        except Exception as exc:
            print(f"  GPU bridge failed: {exc}")
            self.gpu_enabled = False

            # Recreate software window
            pygame.display.quit()
            pygame.display.init()
            self.screen = pygame.display.set_mode(
                (WIDTH, HEIGHT), pygame.RESIZABLE
            )
            pygame.display.set_caption(TITLE)
            self.theme.fonts.initialize()

            # Try standalone context for compute
            if self.gpu_ctx is None:
                self._init_standalone_gpu()
            print("  → Software rendering mode")

    def _register_screens(self):
        self.state_manager.register_screen('MAIN_MENU',
            MainMenuScreen(self.state_manager))
        self.state_manager.register_screen('CONTENT_MANAGER',
            ContentManagerScreen(self.state_manager))
        self.state_manager.register_screen('OBSERVATORY',
            ObservatoryScreen(self.state_manager))
        self.state_manager.register_screen('IMAGING',
            ImagingScreen(self.state_manager))
        self.state_manager.register_screen('CATALOGS',
            CatalogScreen(self.state_manager))
        self.state_manager.register_screen('EQUIPMENT',
            EquipmentScreen(self.state_manager))
        self.state_manager.register_screen('CAREER',
            CareerScreen(self.state_manager))
        self.state_manager.register_screen('SKYCHART',
            SkychartScreen(self.state_manager))

    # ───────────────────────────────────────────────────────────────────
    # GPU bridge
    # ───────────────────────────────────────────────────────────────────

    def _init_gpu_bridge(self, width: int, height: int) -> None:
        import moderngl
        from gpu.shaders import VERTEX_SHADER

        self._offscreen_surface = pygame.Surface((width, height), depth=32)
        self._bridge_w = width
        self._bridge_h = height

        self._passthrough_prog = self.gpu_ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=_PASSTHROUGH_FRAGMENT,
        )

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

        self._screen_tex = self.gpu_ctx.texture(
            (width, height), 4, dtype='u1'
        )
        self._screen_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def _resize_gpu_bridge(self, width: int, height: int) -> None:
        import moderngl

        self._offscreen_surface = pygame.Surface((width, height), depth=32)
        self._bridge_w = width
        self._bridge_h = height
        if self._screen_tex is not None:
            self._screen_tex.release()
        self._screen_tex = self.gpu_ctx.texture(
            (width, height), 4, dtype='u1'
        )
        self._screen_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def _blit_offscreen_to_gpu(self) -> None:
        import moderngl

        try:
            raw = pygame.image.tobytes(self._offscreen_surface, "RGBA", False)
        except AttributeError:
            raw = pygame.image.tostring(self._offscreen_surface, "RGBA", False)

        self._screen_tex.write(raw)

        if self._gpu_frame_count < 3:
            max_byte = max(raw[:min(len(raw), 4000)])
            print(f"[GPU frame {self._gpu_frame_count}] "
                  f"raw len={len(raw)}, max_byte={max_byte}")

        sw, sh = pygame.display.get_surface().get_size()
        self.gpu_ctx.screen.use()
        self.gpu_ctx.viewport = (0, 0, sw, sh)
        self.gpu_ctx.clear(0.0, 0.0, 0.0)
        self._screen_tex.use(location=0)
        self._passthrough_prog['u_texture'].value = 0
        self._passthrough_vao.render(moderngl.TRIANGLE_STRIP)

        self._gpu_frame_count += 1

    def _disable_gpu_and_fallback(self) -> None:
        print("\n⚠ GPU bridge runtime error — switching to software")
        self.gpu_enabled = False
        self._offscreen_surface = None

        w, h = pygame.display.get_surface().get_size()
        pygame.display.quit()
        pygame.display.init()
        flags = pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption(TITLE)
        self.theme.fonts.initialize()

    # ───────────────────────────────────────────────────────────────────
    # Main loop
    # ───────────────────────────────────────────────────────────────────

    def run(self):
        print("\nStarting main loop...")
        print("Press ESC at Observatory Hub to quit\n")

        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event.w, event.h)
                else:
                    nav_target = self.nav_manager.handle_global_hotkeys(event)
                    if nav_target:
                        self.state_manager.switch_to(nav_target)

            self.state_manager.handle_input(events)
            self.state_manager.update(dt)

            # Render
            render_target = (self._offscreen_surface
                             if self.gpu_enabled else self.screen)
            render_target.fill(self.theme.colors.BG_DARK)
            self.state_manager.render(render_target)

            if self.gpu_enabled:
                try:
                    self._blit_offscreen_to_gpu()
                except Exception as exc:
                    print(f"\n⚠ GPU bridge error: {exc}")
                    self._disable_gpu_and_fallback()
                    self.screen.fill(self.theme.colors.BG_DARK)
                    self.state_manager.render(self.screen)

            pygame.display.flip()

        self.quit()

    # ───────────────────────────────────────────────────────────────────
    # Window management
    # ───────────────────────────────────────────────────────────────────

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            di = pygame.display.Info()
            w, h = di.current_w, di.current_h
            flags = pygame.FULLSCREEN
        else:
            w, h = WIDTH, HEIGHT
            flags = pygame.RESIZABLE

        if self.gpu_enabled:
            flags |= pygame.OPENGL | pygame.DOUBLEBUF

        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption(TITLE)

        if self.gpu_enabled:
            try:
                import moderngl
                self.gpu_ctx = moderngl.create_context()
                self._init_gpu_bridge(w, h)
            except Exception:
                self._disable_gpu_and_fallback()

    def handle_resize(self, width: int, height: int):
        if not self.fullscreen:
            if self.gpu_enabled:
                self._resize_gpu_bridge(width, height)
            else:
                self.screen = pygame.display.set_mode(
                    (width, height), pygame.RESIZABLE
                )

    def quit(self):
        print("\nShutting down...")
        print("Thank you for using Observatory Simulation!")
        pygame.quit()
        sys.exit(0)


def main():
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
