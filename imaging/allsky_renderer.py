# Updated allsky_renderer.py

from universe.orbital_body import equatorial_to_altaz
from atmosphere.cloud_layer import CloudLayer

...

class AllSkyRenderer:
    ...
    def __init__(self, camera_spec, ...):
        ...
        # Cloud layer for procedural clouds (Sprint 14b)
        self.cloud_layer = CloudLayer(
            seed=42,
            wind_speed_deg_per_s=5.0,
            wind_direction_deg=270.0,  # West wind
            base_coverage=0.3
        )
        ...

    def render(self, jd, ...):
        ...
        radius  = S / 2.0 - 1.5
        # Update cloud layer with current time
        self.cloud_layer.update(jd)
        ...
        # ── Cloud overlay ────────────────────────────────────────────────
        _apply_cloud_overlay(field, self.cloud_layer, cx, cy, radius)
        return field


def _apply_cloud_overlay(field: np.ndarray, cloud_layer, cx: float, cy: float, radius: float) -> None:
    """
    Apply procedural cloud layer overlay to rendered field (in-place).
    For each pixel in the fisheye:
      - Convert (x,y) → (az, alt)
      - Query cloud_layer.get_coverage_at(az, alt) → coverage 0..1
      - Blend: darken background + add cloud color

    Cloud color: greyish-white (200, 210, 220) RGB photons
    """
    H, W = field.shape[:2]
    for row in range(H):
        for col in range(W):
            dx = col - cx
            dy = row - cy
            r = math.sqrt(dx * dx + dy * dy)
            if r > radius:
                continue  # Outside fisheye circle
            # Convert pixel to alt/az
            r_norm = r / radius
            alt = 90.0 * (1.0 - r_norm)  # 0° at edge, 90° at zenith
            az_rad = math.atan2(dx, -dy)  # N=0°, E=90°, ...
            az = math.degrees(az_rad) % 360.0
            # Get cloud coverage at this direction
            coverage = cloud_layer.get_coverage_at(az, alt)
            if coverage > 0.01:
                # Cloud color in photon units (greyish-white)
                cloud_rgb = np.array([200.0, 210.0, 220.0], dtype=np.float32) * coverage
                # Blend: darken sky + add cloud
                # coverage = 1.0 → 90% darkening + full cloud color
                # coverage = 0.5 → 45% darkening + half cloud color
                field[row, col] = field[row, col] * (1.0 - coverage * 0.9) + cloud_rgb
