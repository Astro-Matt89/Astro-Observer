"""
Cloud Layer — Procedural animated clouds for atmospheric rendering.

Generates realistic cloud coverage using Perlin noise with wind animation.
Used by AllSkyRenderer to composite cloud overlay over stars and solar bodies.

Architecture:
  - Perlin noise (3 octaves) generates base cloud pattern
  - Wind animation: clouds drift over time based on wind_speed and wind_direction
  - Coverage threshold: cloud_base_coverage determines overall cloud amount
  - Altitude gradient: clouds fade above 70° elevation

Usage:
    cloud_layer = CloudLayer(seed=42, wind_speed=5.0, wind_direction=270.0, cloud_base_coverage=0.3)
    cloud_layer.step(dt)  # Update wind offset
    coverage = cloud_layer.get_coverage_at(az_deg=180.0, alt_deg=45.0)
    cloud_map = cloud_layer.generate_cloud_map(w=800, h=800, az_center=180.0, alt_center=90.0, fov_deg=180.0)
"""

import math
import numpy as np
from typing import Tuple

# ---------------------------------------------------------------------------
# Perlin Noise 2D (simplified, 3 octaves)
# ---------------------------------------------------------------------------

def _perlin_noise_2d(x: float, y: float, seed: int = 0) -> float:
    """
    Simplified 2D Perlin-like noise with smoothstep interpolation.
    Returns value in range [0, 1].
    
    Args:
        x, y: coordinates
        seed: random seed for reproducibility
    
    Returns:
        noise value 0..1
    """
    np.random.seed(seed)
    
    # Grid cell coordinates
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = x0 + 1
    y1 = y0 + 1
    
    # Fractional part
    fx = x - x0
    fy = y - y0
    
    # Smoothstep interpolation
    def smoothstep(t):
        return t * t * (3.0 - 2.0 * t)
    
    sx = smoothstep(fx)
    sy = smoothstep(fy)
    
    # Generate pseudo-random gradients for grid corners
    def hash_coord(ix, iy, s):
        h = (ix * 374761393 + iy * 668265263 + s * 123456789) & 0x7fffffff
        return (h / float(0x7fffffff)) * 2.0 - 1.0
    
    # Gradient vectors at corners
    g00 = hash_coord(x0, y0, seed)
    g10 = hash_coord(x1, y0, seed)
    g01 = hash_coord(x0, y1, seed)
    g11 = hash_coord(x1, y1, seed)
    
    # Dot products
    d00 = g00 * fx + g00 * fy
    d10 = g10 * (fx - 1) + g10 * fy
    d01 = g01 * fx + g01 * (fy - 1)
    d11 = g11 * (fx - 1) + g11 * (fy - 1)
    
    # Bilinear interpolation
    a = d00 + sx * (d10 - d00)
    b = d01 + sx * (d11 - d01)
    result = a + sy * (b - a)
    
    # Normalize to [0, 1]
    return (result + 1.0) * 0.5

def _perlin_octaves(x: float, y: float, octaves: int = 3, persistence: float = 0.5, seed: int = 0) -> float:
    """
    Multi-octave Perlin noise.
    
    Args:
        x, y: coordinates
        octaves: number of octaves (layers of detail)
        persistence: amplitude falloff per octave
        seed: random seed
    
    Returns:
        noise value 0..1
    """
    total = 0.0
    frequency = 1.0
    amplitude = 1.0
    max_value = 0.0
    
    for i in range(octaves):
        total += _perlin_noise_2d(x * frequency, y * frequency, seed + i) * amplitude
        max_value += amplitude
        amplitude *= persistence
        frequency *= 2.0
    
    return total / max_value

# ---------------------------------------------------------------------------
# CloudLayer
# ---------------------------------------------------------------------------

class CloudLayer:
    """
    Procedural animated cloud layer.
    
    Features:
    - Perlin noise-based cloud pattern (3 octaves)
    - Wind animation (clouds drift over time)
    - Altitude gradient (clouds fade above 70° elevation)
    - Configurable coverage threshold
    
    Attributes:
        seed: random seed for reproducibility
        wind_speed: wind speed in degrees per second (azimuth drift)
        wind_direction: wind direction in degrees (0=N, 90=E, 180=S, 270=W)
        cloud_base_coverage: base cloud coverage 0..1 (threshold for noise)
        _wind_offset_x: accumulated wind offset in x (updated by step)
        _wind_offset_y: accumulated wind offset in y (updated by step)
    """
    
    def __init__(self, seed: int = 42, wind_speed: float = 5.0, wind_direction: float = 270.0, cloud_base_coverage: float = 0.3):
        """
        Initialize cloud layer.
        
        Args:
            seed: random seed for Perlin noise
            wind_speed: wind speed in degrees/second (sky dome rotation)
            wind_direction: wind direction in degrees (0=N, 90=E, 180=S, 270=W)
            cloud_base_coverage: base coverage 0..1 (0=clear, 1=overcast)
        """
        self.seed = seed
        self.wind_speed = wind_speed
        self.wind_direction = wind_direction
        self.cloud_base_coverage = cloud_base_coverage
        
        # Wind animation state
        self._wind_offset_x = 0.0
        self._wind_offset_y = 0.0
    
    def step(self, dt: float) -> None:
        """
        Update wind animation.
        
        Args:
            dt: time step in seconds
        """
        # Convert wind direction to radians
        wind_rad = math.radians(self.wind_direction)
        
        # Update wind offset (clouds drift in wind direction)
        # Scale factor 0.01 converts degrees/s to noise space units
        dx = math.cos(wind_rad) * self.wind_speed * dt * 0.01
        dy = math.sin(wind_rad) * self.wind_speed * dt * 0.01
        
        self._wind_offset_x += dx
        self._wind_offset_y += dy
    
    def get_coverage_at(self, az_deg: float, alt_deg: float) -> float:
        """
        Get cloud coverage at a specific sky position.
        
        Args:
            az_deg: azimuth in degrees (0=N, 90=E, 180=S, 270=W)
            alt_deg: altitude in degrees (0=horizon, 90=zenith)
        
        Returns:
            cloud coverage 0..1 (0=clear, 1=opaque cloud)
        """
        # Convert to noise space coordinates
        # Scale: 0.02 gives ~50° cloud features
        x = az_deg * 0.02 + self._wind_offset_x
        y = alt_deg * 0.02 + self._wind_offset_y
        
        # Generate Perlin noise (3 octaves)
        noise = _perlin_octaves(x, y, octaves=3, persistence=0.5, seed=self.seed)
        
        # Apply coverage threshold
        # noise > threshold → cloud, else clear
        coverage = max(0.0, (noise - (1.0 - self.cloud_base_coverage)) / self.cloud_base_coverage)
        
        # Altitude gradient: fade clouds above 70° elevation
        if alt_deg > 70.0:
            fade = 1.0 - (alt_deg - 70.0) / 20.0  # linear fade 70°→90°
            coverage *= max(0.0, fade)
        
        return coverage
    
    def generate_cloud_map(self, w: int, h: int, az_center: float, alt_center: float, fov_deg: float) -> np.ndarray:
        """
        Generate 2D cloud coverage map for a rectangular FOV.
        
        Args:
            w, h: width and height in pixels
            az_center: center azimuth in degrees
            alt_center: center altitude in degrees
            fov_deg: field of view in degrees (square FOV)
        
        Returns:
            numpy array (h, w) with cloud coverage 0..1
        """
        cloud_map = np.zeros((h, w), dtype=np.float32)
        
        # Pixel to degrees conversion
        deg_per_pixel = fov_deg / max(w, h)
        
        for row in range(h):
            for col in range(w):
                # Pixel offset from center
                dx = (col - w / 2) * deg_per_pixel
                dy = (h / 2 - row) * deg_per_pixel  # flip Y axis
                
                # Sky position
                az = az_center + dx
                alt = alt_center + dy
                
                # Clamp altitude to valid range
                alt = max(0.0, min(90.0, alt))
                
                # Get coverage
                cloud_map[row, col] = self.get_coverage_at(az, alt)
        
        return cloud_map
    
    def __repr__(self) -> str:
        return (f"CloudLayer(seed={self.seed}, wind_speed={self.wind_speed:.1f}°/s, "
                f"wind_dir={self.wind_direction:.0f}°, coverage={self.cloud_base_coverage:.2f})")