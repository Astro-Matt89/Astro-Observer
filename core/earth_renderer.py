"""
EarthRenderer — numpy ray-sphere intersection for sky chart horizon.

The observer is on the surface of a unit sphere (Earth).
Ray direction's Z component (Up) determines ground vs sky:
  dz < 0  → ray hits Earth  → ground pixel
  dz >= 0 → ray escapes     → sky pixel

~3ms per cache-miss (STEP=4), 0ms when camera is still.
"""

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame
    from core.celestial_math import AltAzProjection

_GROUND_SURF  = np.array([8,  30,  9],  dtype=np.float32)
_GROUND_DEEP  = np.array([3,  15,  4],  dtype=np.float32)
_ATMO_BAND    = np.array([8,  35, 18],  dtype=np.float32)
_HORIZON_LINE = (35, 130, 35)
ATMO_THRESH   = 0.06   # ~3.4° above horizon


class EarthRenderer:
    """
    Renders the Earth ground via numpy ray casting.
    Only pixels with ray.z < 0 are painted — stars above horizon are untouched.
    """

    STEP = 4   # ray grid downscale (320×180 → scaled to 1280×720)

    def __init__(self):
        self._cache_key   = None
        self._ground_surf = None   # cached pygame.Surface (SRCALPHA)

    def render(self, target, proj, show_fill: bool = True, show_line: bool = True):
        """Call AFTER stars/DSO so ground occludes them."""
        import pygame

        W = target.get_width()
        H = target.get_height()

        key = (round(proj.center_az, 2), round(proj.center_alt, 2),
               round(proj.fov_deg,   2), W, H)
        if key != self._cache_key:
            self._ground_surf = self._build(proj, W, H)
            self._cache_key   = key

        if show_fill and self._ground_surf is not None:
            target.blit(self._ground_surf, (0, 0))

        if show_line:
            self._draw_line(target, proj)

    # ------------------------------------------------------------------
    def _build(self, proj, W: int, H: int):
        import pygame

        S    = self.STEP
        cols = W // S
        rows = H // S

        # Pixel grid (centre of each super-pixel)
        xs_1d = np.arange(cols, dtype=np.float32) * S + S * 0.5
        ys_1d = np.arange(rows, dtype=np.float32) * S + S * 0.5
        gx, gy = np.meshgrid(xs_1d, ys_1d)   # shape (rows, cols)

        rays = proj.pixel_to_ray_array(gx.ravel(), gy.ravel())
        dz   = rays[:, 2].reshape(rows, cols)

        is_ground = dz < 0.0
        if not np.any(is_ground):
            return None   # entire screen is sky

        # ---- Build RGBA array (rows, cols, 4) ----
        rgba = np.zeros((rows, cols, 4), dtype=np.uint8)

        # Ground: colour lerped by depth below horizon
        depth = np.sqrt(np.clip(-dz, 0.0, 1.0))   # 0 at horizon, 1 at nadir
        for ch in range(3):
            lerped = _GROUND_SURF[ch] + depth * (_GROUND_DEEP[ch] - _GROUND_SURF[ch])
            rgba[:, :, ch] = np.where(is_ground,
                                      np.clip(lerped, 0, 255).astype(np.uint8), 0)
        rgba[:, :, 3] = np.where(is_ground, 235, 0).astype(np.uint8)

        # Atmosphere glow: sky pixels just above horizon
        is_atmo = (~is_ground) & (dz < ATMO_THRESH) & (dz >= 0)
        if np.any(is_atmo):
            atmo_frac = np.clip(1.0 - dz / ATMO_THRESH, 0, 1)
            for ch in range(3):
                rgba[:, :, ch] = np.where(is_atmo,
                    np.clip(_ATMO_BAND[ch], 0, 255).astype(np.uint8),
                    rgba[:, :, ch])
            rgba[:, :, 3] = np.where(is_atmo,
                np.clip(atmo_frac * 60, 0, 60).astype(np.uint8),
                rgba[:, :, 3])

        # ---- Convert to pygame Surface via frombuffer ----
        # frombuffer expects a bytes-like object in row-major (rows, cols, 4)
        raw = np.ascontiguousarray(rgba)   # shape (rows, cols, 4)
        small = pygame.image.frombuffer(raw.tobytes(), (cols, rows), "RGBA")
        small = small.convert_alpha()

        # Scale to full resolution
        if S == 1:
            return small
        return pygame.transform.scale(small, (W, H))

    def _draw_line(self, surface, proj):
        """Crisp horizon line on top of fill."""
        import pygame
        prev = None
        for az in range(0, 361, 2):
            px = proj.project(0.0, float(az))
            if px and proj.is_on_screen(*px, margin=2):
                if (prev
                        and abs(px[1] - prev[1]) < 30
                        and abs(px[0] - prev[0]) < 40):
                    pygame.draw.line(surface, _HORIZON_LINE, prev, px, 2)
                prev = px
            else:
                prev = None
