"""
gpu/sky_engine.py — GPU-accelerated sky rendering engine for the Sky Chart.

Replaces per-star pygame.draw calls with a ModernGL shader pipeline:
  - Star data uploaded as GPU texture (RGBA float16)
  - Bloom multi-pass (bright extract → gaussian blur → combine)
  - Twinkling shader (time-modulated per-star brightness)
  - Atmospheric scattering post-process
  - Nearest-neighbor upscale from internal to screen resolution

Architecture:
    Python orchestration (universe queries, time, UI)
    → numpy arrays
    → GPU textures
    → shader pipeline
    → screen

Graceful fallback: if ModernGL is unavailable or OpenGL 3.3 is not
supported, GPUSkyEngine raises ImportError/RuntimeError at construction
time so the caller can fall back to standard Pygame rendering.

Gnomonic star projection mirrors the logic of sky_renderer._radec_to_pixel
but is fully vectorised with numpy for 389k+ stars.
"""

from __future__ import annotations

import math
import time as _time
from typing import Optional, Tuple

import numpy as np

try:
    import moderngl
except ImportError as _mgl_err:
    raise ImportError(
        "ModernGL is not installed. "
        "Install it with:  pip install moderngl\n"
        f"Original error: {_mgl_err}"
    ) from _mgl_err

from .shaders import (
    VERTEX_SHADER,
    SCENE_FRAGMENT,
    BRIGHT_EXTRACT_FRAGMENT,
    BLUR_FRAGMENT,
    COMBINE_FRAGMENT,
    ATMOSPHERIC_SCATTER,
)

# Internal render resolution (pixel-art upscale aesthetic)
_INTERNAL_W = 640
_INTERNAL_H = 360

# Bloom defaults
_BLOOM_INTENSITY  = 0.6
_BLOOM_THRESHOLD  = 0.35
_BLOOM_BLUR_PASSES = 2


class GPUSkyEngine:
    """
    GPU-accelerated sky rendering engine for the Sky Chart.

    Usage::

        # Construction — once, at screen init
        engine = GPUSkyEngine()

        # Each frame (inside render()):
        engine.set_view(center_ra, center_dec, fov_deg)
        engine.render_stars(universe, lst_deg, lat_deg, mag_limit, current_time)
        gpu_surface = engine.render_frame(screen_w, screen_h)
        # gpu_surface is a pygame.Surface you can blit or composite over

    The engine owns no Pygame surfaces — it renders directly to the
    OpenGL framebuffer and reads back a pygame.Surface only when needed
    for compositing with Pygame UI elements.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, internal_w: int = _INTERNAL_W, internal_h: int = _INTERNAL_H,
                 ctx=None):
        """
        Create GPU context from the active Pygame OpenGL window.

        Args:
            internal_w: Internal render width in pixels.
            internal_h: Internal render height in pixels.
            ctx: Optional external ModernGL context (``moderngl.Context``) to
                 reuse.  When provided the engine shares that context instead of
                 creating a new one, which avoids the conflict that arises when
                 main_app.py has already called moderngl.create_context().  If
                 *not* provided (standalone / PoC usage) a new context is created
                 as before.

        Raises RuntimeError if the OpenGL context cannot be created.
        Must be called *after* pygame.display.set_mode(flags=OPENGL|DOUBLEBUF).
        """
        self.iw = internal_w
        self.ih = internal_h

        if ctx is not None:
            self.ctx = ctx
        else:
            # ModernGL context from current Pygame OpenGL window
            try:
                self.ctx = moderngl.create_context()
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to create ModernGL context: {exc}\n"
                    "Make sure the Pygame window was created with "
                    "pygame.OPENGL | pygame.DOUBLEBUF."
                ) from exc

        self._compile_shaders()
        self._create_buffers()
        self._create_textures()

        # Rendering state
        self.bloom_enabled   = True
        self.twinkling       = True
        self.bloom_intensity = _BLOOM_INTENSITY
        self.bloom_threshold = _BLOOM_THRESHOLD
        self._time: float    = 0.0

        # View state (set by set_view)
        self._center_ra:  float = 0.0
        self._center_dec: float = 0.0
        self._fov_deg:    float = 60.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_view(self, center_ra: float, center_dec: float, fov_deg: float) -> None:
        """Update the viewport for the next render_stars() call."""
        self._center_ra  = center_ra
        self._center_dec = center_dec
        self._fov_deg    = fov_deg

    def render_stars(self,
                     universe,
                     lst_deg: float,
                     lat_deg: float,
                     mag_limit: float,
                     current_time: Optional[float] = None) -> None:
        """
        Project stars from the Universe catalog and upload them to the GPU.

        Steps:
          1. Fetch star arrays from universe.get_star_arrays()
          2. Filter visible stars with universe.query_stars_in_fov()
          3. Convert RA/Dec → Alt/Az → screen pixels (vectorised numpy)
          4. Map B-V colour index → RGB
          5. Map magnitude → brightness
          6. Pack into RGBA float16 array and upload as GPU texture

        Parameters
        ----------
        universe    : Universe instance
        lst_deg     : Local Sidereal Time in degrees
        lat_deg     : Observer latitude in degrees
        mag_limit   : Maximum magnitude to render
        current_time: Optional wall-clock time (seconds) for twinkling
        """
        if current_time is not None:
            self._time = current_time
        else:
            self._time = _time.time()

        # ---- 1. Fetch & filter star arrays --------------------------------
        _stars, ra_arr, dec_arr, mag_arr, bv_arr = universe.get_star_arrays()
        mask = universe.query_stars_in_fov(
            self._center_ra, self._center_dec, self._fov_deg, mag_limit
        )
        idx = np.nonzero(mask)[0]

        if len(idx) == 0:
            # Upload empty (black) texture
            blank = np.zeros((self.ih, self.iw, 4), dtype=np.float16)
            self._starfield_tex.write(blank.tobytes())
            return

        ra  = ra_arr[idx]
        dec = dec_arr[idx]
        mag = mag_arr[idx]
        bv  = bv_arr[idx]

        # ---- 2. Alt/Az → pixel (vectorised) --------------------------------
        px_arr, py_arr, vis = self._radec_to_pixels_vec(
            ra, dec, lst_deg, lat_deg
        )

        # Keep only above-horizon visible stars
        if not np.any(vis):
            blank = np.zeros((self.ih, self.iw, 4), dtype=np.float16)
            self._starfield_tex.write(blank.tobytes())
            return

        px_arr = px_arr[vis]
        py_arr = py_arr[vis]
        mag    = mag[vis]
        bv     = bv[vis]

        # Clamp to texture bounds
        xi = np.clip(np.round(px_arr).astype(np.int32), 0, self.iw - 1)
        yi = np.clip(np.round(py_arr).astype(np.int32), 0, self.ih - 1)

        # ---- 3. B-V → RGB (vectorised) ------------------------------------
        r_c, g_c, b_c = self._bv_to_rgb_vec(bv)

        # ---- 4. Magnitude → normalised brightness -------------------------
        # Reference: mag 0 star → brightness 1.0; each mag step = 10^(-0.4)
        brightness = np.clip(10.0 ** (-0.4 * (mag - 1.0)), 0.0, 1.0).astype(np.float32)

        # ---- 5. Pack into RGBA float16 buffer -----------------------------
        field = np.zeros((self.ih, self.iw, 4), dtype=np.float32)
        # Alpha channel encodes per-star twinkling phase (random from bv hash)
        phase = (np.sin(ra[vis] * 127.1 + dec[vis] * 311.7) * 0.5 + 0.5).astype(np.float32)

        np.add.at(field, (yi, xi, 0), r_c * brightness)
        np.add.at(field, (yi, xi, 1), g_c * brightness)
        np.add.at(field, (yi, xi, 2), b_c * brightness)
        np.add.at(field, (yi, xi, 3), phase)

        np.clip(field, 0.0, 1.0, out=field)

        # ---- 6. Upload to GPU -----------------------------------------------
        self._starfield_tex.write(field.astype(np.float16).tobytes())

    def render_frame(self, screen_w: int, screen_h: int) -> None:
        """
        Execute the full GPU rendering pipeline and output to the screen.

        Pass order:
          1. Scene compositing (starfield + twinkling)
          2. Bright extract (bloom threshold)
          3-4. Gaussian blur ping-pong (horizontal + vertical)
          5. Atmospheric scattering post-process
          6. Combine + nearest-neighbour upscale → screen
        """
        t = self._time

        bw = self.iw // 2
        bh = self.ih // 2

        # ---- Pass 1: Scene / twinkling -----------------------------------
        self._scene_fbo.use()
        self.ctx.viewport = (0, 0, self.iw, self.ih)
        self.ctx.clear(0.01, 0.02, 0.06)   # deep-blue night sky

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)  # additive

        self._starfield_tex.use(location=0)
        self._prog_scene['starfield'].value = 0
        self._prog_scene['u_time'].value    = float(t)
        self._prog_scene['u_twinkling'].value = self.twinkling
        self._vao_scene.render(moderngl.TRIANGLE_STRIP)

        self.ctx.disable(moderngl.BLEND)

        if self.bloom_enabled:
            # ---- Pass 2: Bright extract --------------------------------------
            self._bright_fbo.use()
            self.ctx.viewport = (0, 0, bw, bh)
            self._scene_tex.use(location=0)
            self._prog_bright['scene'].value       = 0
            self._prog_bright['u_threshold'].value = self.bloom_threshold
            self._vao_bright.render(moderngl.TRIANGLE_STRIP)

            # ---- Pass 3-4: Gaussian blur ping-pong --------------------------
            current_tex = self._bright_tex
            for _ in range(_BLOOM_BLUR_PASSES):
                # Horizontal blur
                self._blur_fbo_a.use()
                self.ctx.viewport = (0, 0, bw, bh)
                current_tex.use(location=0)
                self._prog_blur['image'].value       = 0
                self._prog_blur['u_direction'].value = (1.0 / bw, 0.0)
                self._prog_blur['u_radius'].value    = 1.5
                self._vao_blur.render(moderngl.TRIANGLE_STRIP)

                # Vertical blur
                self._blur_fbo_b.use()
                self._blur_tex_a.use(location=0)
                self._prog_blur['u_direction'].value = (0.0, 1.0 / bh)
                self._vao_blur.render(moderngl.TRIANGLE_STRIP)

                current_tex = self._blur_tex_b

        # ---- Pass 5: Atmospheric scattering --------------------------------
        # Use the post-process FBO then swap references for the combine pass
        self._atmo_fbo.use()
        self.ctx.viewport = (0, 0, self.iw, self.ih)
        self._scene_tex.use(location=0)
        self._prog_atmo['scene'].value          = 0
        self._prog_atmo['u_horizon_y'].value    = 0.30
        self._prog_atmo['u_extinction'].value   = 0.25
        self._prog_atmo['u_horizon_color'].value = (0.05, 0.03, 0.02)
        self._prog_atmo['u_sky_brightness'].value = 0.0
        self._vao_atmo.render(moderngl.TRIANGLE_STRIP)

        # ---- Pass 6: Combine + upscale → screen ----------------------------
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, screen_w, screen_h)

        self._atmo_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._atmo_tex.use(location=0)
        self._prog_combine['scene'].value = 0

        if self.bloom_enabled:
            self._blur_tex_b.use(location=1)
        else:
            self._atmo_tex.use(location=1)   # dummy — bloom disabled
        self._prog_combine['bloom'].value           = 1
        self._prog_combine['u_bloom_intensity'].value = self.bloom_intensity
        self._prog_combine['u_bloom_enabled'].value   = self.bloom_enabled
        self._vao_combine.render(moderngl.TRIANGLE_STRIP)

    # ------------------------------------------------------------------
    # Internal helpers — projection
    # ------------------------------------------------------------------

    def _radec_to_pixels_vec(
        self,
        ra:  np.ndarray,
        dec: np.ndarray,
        lst_deg: float,
        lat_deg: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Vectorised RA/Dec → (internal) pixel coordinates.

        Steps:
          1. RA/Dec → Alt/Az  (via equatorial hour-angle transform)
          2. Gnomonic project centered on (center_az, center_alt) from set_view

        Returns (px, py, visible_mask).
        visible_mask is True where alt > -2° and star is in the FOV.
        """
        lat_r = math.radians(lat_deg)

        # Hour angle (degrees) — LST – RA
        ha_rad = np.radians((lst_deg - ra) % 360.0)
        dec_r  = np.radians(dec)

        sin_lat = math.sin(lat_r)
        cos_lat = math.cos(lat_r)

        # Altitude
        sin_alt = (np.sin(dec_r) * sin_lat
                   + np.cos(dec_r) * cos_lat * np.cos(ha_rad))
        alt_r   = np.arcsin(np.clip(sin_alt, -1.0, 1.0))

        # Azimuth (degrees, N=0, E=90)
        cos_az = ((np.sin(dec_r) - np.sin(alt_r) * sin_lat)
                  / (np.cos(alt_r) * cos_lat + 1e-12))
        sin_az_sign = np.sin(ha_rad)
        az_r = np.arccos(np.clip(cos_az, -1.0, 1.0))
        az_r = np.where(sin_az_sign > 0, 2 * math.pi - az_r, az_r)

        alt_deg = np.degrees(alt_r)
        az_deg  = np.degrees(az_r)

        # Visibility cut: altitude > -2°
        vis = alt_deg > -2.0

        # Gnomonic projection around the view centre ----------------------
        # Convert centre from sky-chart view (AltAz) to radians
        c_alt_r = math.radians(self._center_dec)   # use equatorial centre
        c_az_r  = math.radians(self._center_ra)

        # We project in Alt/Az gnomonic — reuse the same formula
        # (treat alt as "dec" and az as "ra" for the gnomonic maths)
        # This matches the behaviour of AltAzProjection in screen_skychart.
        alt_r_safe = alt_r[vis]
        az_r_safe  = az_r[vis]

        c_alt = math.radians(self._center_dec)   # projection centre altitude
        c_az  = math.radians(self._center_ra)    # projection centre azimuth

        cos_c = (np.sin(c_alt) * np.sin(alt_r_safe)
                 + np.cos(c_alt) * np.cos(alt_r_safe) * np.cos(az_r_safe - c_az))

        # Stars behind the projection plane (cos_c <= 0) are invisible
        in_front = cos_c > 0.0
        cos_c_safe = np.where(in_front, cos_c, 1.0)  # avoid /0

        x = (np.cos(alt_r_safe) * np.sin(az_r_safe - c_az)) / cos_c_safe
        y = ((np.cos(c_alt) * np.sin(alt_r_safe)
              - np.sin(c_alt) * np.cos(alt_r_safe) * np.cos(az_r_safe - c_az))
             / cos_c_safe)

        # Convert gnomonic radians → internal pixels
        # fov_deg / width_px  gives radians per pixel
        rad_per_px = math.radians(self._fov_deg) / self.iw
        px = self.iw / 2.0 + x / rad_per_px
        py = self.ih / 2.0 - y / rad_per_px   # y-axis flipped

        # Clip to internal resolution bounds with a 1-pixel margin
        on_screen = (
            in_front
            & (px >= 0) & (px < self.iw)
            & (py >= 0) & (py < self.ih)
        )

        # Build full-size output arrays
        full_px   = np.zeros(len(ra), dtype=np.float32)
        full_py   = np.zeros(len(ra), dtype=np.float32)
        full_vis  = np.zeros(len(ra), dtype=bool)

        full_px[vis]  = px.astype(np.float32)
        full_py[vis]  = py.astype(np.float32)

        vis_indices = np.where(vis)[0]
        full_vis[vis_indices[on_screen]] = True

        return full_px, full_py, full_vis

    @staticmethod
    def _bv_to_rgb_vec(bv: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Vectorised B-V → (R, G, B) float32, matching sky_renderer.bv_to_rgb.
        desaturate=0.55 (photographic, muted colours).
        """
        bv = np.clip(bv, -0.4, 2.0)
        r = np.ones_like(bv)
        g = np.ones_like(bv)
        b = np.ones_like(bv)

        # O/B: blue-white  (bv < 0)
        m = bv < 0.0
        t = (bv + 0.4) / 0.4
        r[m] = 0.6 + 0.2 * t[m]
        g[m] = 0.7 + 0.3 * t[m]
        b[m] = 1.0

        # A/F: white  (0 <= bv < 0.3)
        m = (bv >= 0.0) & (bv < 0.3)
        t = bv / 0.3
        r[m] = 0.8 + 0.2 * t[m]
        g[m] = 0.9 + 0.1 * t[m]
        b[m] = 1.0 - 0.2 * t[m]

        # G: warm white  (0.3 <= bv < 0.7)
        m = (bv >= 0.3) & (bv < 0.7)
        t = (bv - 0.3) / 0.4
        r[m] = 1.0
        g[m] = 0.9
        b[m] = 0.8 - 0.4 * t[m]

        # K: pale orange  (0.7 <= bv < 1.2)
        m = (bv >= 0.7) & (bv < 1.2)
        t = (bv - 0.7) / 0.5
        r[m] = 1.0
        g[m] = 0.9 - 0.4 * t[m]
        b[m] = 0.4 - 0.3 * t[m]

        # M: dusty red  (bv >= 1.2)
        m = bv >= 1.2
        t = np.clip((bv - 1.2) / 0.8, 0.0, 1.0)
        r[m] = 1.0
        g[m] = 0.5 - 0.3 * t[m]
        b[m] = 0.1

        # Desaturate toward white (photographic muted colours)
        ds = 0.55
        r = r + (1.0 - r) * ds
        g = g + (1.0 - g) * ds
        b = b + (1.0 - b) * ds

        return r.astype(np.float32), g.astype(np.float32), b.astype(np.float32)

    # ------------------------------------------------------------------
    # Internal helpers — GPU setup
    # ------------------------------------------------------------------

    def _compile_shaders(self) -> None:
        """Compile all GLSL programs."""
        self._prog_scene   = self.ctx.program(vertex_shader=VERTEX_SHADER,
                                               fragment_shader=SCENE_FRAGMENT)
        self._prog_bright  = self.ctx.program(vertex_shader=VERTEX_SHADER,
                                               fragment_shader=BRIGHT_EXTRACT_FRAGMENT)
        self._prog_blur    = self.ctx.program(vertex_shader=VERTEX_SHADER,
                                               fragment_shader=BLUR_FRAGMENT)
        self._prog_combine = self.ctx.program(vertex_shader=VERTEX_SHADER,
                                               fragment_shader=COMBINE_FRAGMENT)
        self._prog_atmo    = self.ctx.program(vertex_shader=VERTEX_SHADER,
                                               fragment_shader=ATMOSPHERIC_SCATTER)

    def _create_buffers(self) -> None:
        """Create fullscreen quad VBO and VAOs for every program."""
        vertices = np.array([
            -1, -1,   0, 0,
             1, -1,   1, 0,
            -1,  1,   0, 1,
             1,  1,   1, 1,
        ], dtype='f4')
        self._vbo = self.ctx.buffer(vertices.tobytes())

        self._vao_scene   = self._make_vao(self._prog_scene)
        self._vao_bright  = self._make_vao(self._prog_bright)
        self._vao_blur    = self._make_vao(self._prog_blur)
        self._vao_combine = self._make_vao(self._prog_combine)
        self._vao_atmo    = self._make_vao(self._prog_atmo)

    def _make_vao(self, program):
        return self.ctx.vertex_array(
            program,
            [(self._vbo, '2f 2f', 'in_position', 'in_texcoord')],
        )

    def _create_textures(self) -> None:
        """Allocate all framebuffers and textures for the pipeline."""
        iw, ih = self.iw, self.ih
        bw, bh = iw // 2, ih // 2

        def _tex(w, h, filt=moderngl.NEAREST):
            t = self.ctx.texture((w, h), 4, dtype='f2')
            t.filter = (filt, filt)
            return t

        # Scene FBO (full internal resolution)
        self._scene_tex = _tex(iw, ih, moderngl.NEAREST)
        self._scene_fbo = self.ctx.framebuffer(color_attachments=[self._scene_tex])

        # Bloom bright-pass FBO (half resolution)
        self._bright_tex = _tex(bw, bh, moderngl.LINEAR)
        self._bright_fbo = self.ctx.framebuffer(color_attachments=[self._bright_tex])

        # Bloom blur ping-pong FBOs (half resolution)
        self._blur_tex_a = _tex(bw, bh, moderngl.LINEAR)
        self._blur_fbo_a = self.ctx.framebuffer(color_attachments=[self._blur_tex_a])

        self._blur_tex_b = _tex(bw, bh, moderngl.LINEAR)
        self._blur_fbo_b = self.ctx.framebuffer(color_attachments=[self._blur_tex_b])

        # Atmospheric scatter FBO (full internal resolution)
        self._atmo_tex = _tex(iw, ih, moderngl.NEAREST)
        self._atmo_fbo = self.ctx.framebuffer(color_attachments=[self._atmo_tex])

        # Starfield input texture (written by render_stars())
        self._starfield_tex = _tex(iw, ih, moderngl.NEAREST)
