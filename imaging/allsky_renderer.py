from atmosphere.cloud_layer import CloudLayer

# ... existing code here ...

def _apply_cloud_overlay(field: np.ndarray, cloud_layer, cx: float, cy: float, radius: float) -> None:
    """Apply cloud layer overlay to rendered field (in-place modification)."""
    H, W = field.shape[:2]
    for row in range(H):
        for col in range(W):
            dx = col - cx
            dy = row - cy
            r = math.sqrt(dx*dx + dy*dy)
            if r > radius:
                continue
            r_norm = r / radius
            alt = 90.0 * (1.0 - r_norm)
            az_rad = math.atan2(dx, -dy)
            az = math.degrees(az_rad) % 360.0
            coverage = cloud_layer.get_coverage_at(az, alt)
            if coverage > 0.01:
                cloud_rgb = np.array([200.0, 210.0, 220.0], dtype=np.float32) * coverage
                field[row, col] = field[row, col] * (1.0 - coverage * 0.9) + cloud_rgb
