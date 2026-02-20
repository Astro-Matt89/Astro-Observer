"""
Weather System — Procedural weather generation with smooth seeing and nightly conditions.
"""

from enum import Enum
from dataclasses import dataclass
import math
import random
import numpy as np


class WeatherCondition(Enum):
    """Weather condition categories."""
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"


@dataclass
class NightWeather:
    """Weather conditions for a single night."""
    night_jd: float
    transparency: float
    seeing_base: float
    cloud_coverage: float
    condition: WeatherCondition


class CloudLayer:
    """
    Procedural cloud map generator with caching.
    """
    
    def __init__(self, size: int = 512, scale: float = 0.008, seed: int = 42):
        """
        Args:
            size: Cloud map resolution (square)
            scale: Perlin noise frequency (0.004-0.012 typical)
            seed: Random seed for deterministic clouds
        """
        self.size = size
        self.scale = scale
        self.seed = seed
        self._cache = {}  # Cache maps by (size, seed, scale, jd_key)
        self._max_cache_size = 20  # Keep last 20 unique maps
    
    def _jd_cache_key(self, jd: float) -> int:
        """Round JD to nearest hour for cache stability."""
        return int(jd * 24)  # changes every hour
    
    def generate_cloud_map(self, jd: float, coverage: float) -> np.ndarray:
        """
        Generate procedural cloud map (CACHED PER HOUR).
        
        Args:
            jd: Julian Date (used as time seed)
            coverage: Cloud coverage 0.0 (clear) to 1.0 (overcast)
            
        Returns:
            Cloud transparency map [0,1] where:
              1.0 = clear sky
              0.0 = opaque cloud
        """
        if coverage < 0.05:
            # Clear sky - return full transparency (no computation needed)
            return np.ones((self.size, self.size), dtype=np.float32)
        
        # Check cache
        cache_key = (self.size, self.seed, self.scale, self._jd_cache_key(jd))
        if cache_key in self._cache:
            base_clouds = self._cache[cache_key]
        else:
            # Generate new cloud map (EXPENSIVE - only once per hour)
            base_clouds = self._generate_perlin_clouds()
            
            # Cache management
            self._cache[cache_key] = base_clouds
            if len(self._cache) > self._max_cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
        
        # Apply coverage threshold (fast operation)
        threshold = 1.0 - coverage
        cloud_mask = base_clouds > threshold
        
        # Smooth transition at cloud edges
        transparency = np.where(cloud_mask,
                                1.0 - (base_clouds - threshold) / (1.0 - threshold + 1e-6),
                                1.0)
        
        return transparency.astype(np.float32)
    
    def _generate_perlin_clouds(self) -> np.ndarray:
        """
        Generate base Perlin noise cloud pattern.
        This is the slow function - called only once per hour.
        """
        try:
            from perlin_numpy import generate_perlin_noise_2d
            
            # Perlin noise at base scale
            noise1 = generate_perlin_noise_2d(
                (self.size, self.size),
                (int(self.size * self.scale), int(self.size * self.scale)),
                tileable=(True, True))
            
            # Add detail layer (higher frequency)
            noise2 = generate_perlin_noise_2d(
                (self.size, self.size),
                (int(self.size * self.scale * 2), int(self.size * self.scale * 2)),
                tileable=(True, True))
            
            # Combine layers
            clouds = 0.7 * noise1 + 0.3 * noise2
            
            # Normalize to [0, 1]
            clouds = (clouds - clouds.min()) / (clouds.max() - clouds.min() + 1e-9)
            
            return clouds
            
        except ImportError:
            # Fallback: simple random clouds if perlin_numpy not available
            rng = np.random.RandomState(self.seed + int(self.size * self.scale * 1000))
            return rng.rand(self.size, self.size).astype(np.float32)
    
    def clear_cache(self):
        """Clear the cloud map cache."""
        self._cache.clear()


class WeatherSystem:
    """
    Procedural weather generator with smooth seeing and nightly conditions.
    
    Seed consistency: Use seed=42 everywhere until Sprint 17 centralises in GameState.
    """
    
    def __init__(self, base_seeing: float = 2.5, seed: int = 42):
        """
        Args:
            base_seeing: Median seeing FWHM in arcsec (default 2.5" for Parma)
            seed: Random seed for reproducibility (MUST be 42 everywhere)
        """
        self.base_seeing = base_seeing
        self.seed = seed
        self._rng = random.Random(seed)
        self._night_cache: dict[int, NightWeather] = {}
        
    def _night_id(self, jd: float) -> int:
        """Convert JD to integer night ID (0 = 2000-01-01)."""
        return int(jd - 2451545.0)
    
    def _generate_night(self, night_id: int) -> NightWeather:
        """Generate weather for a given night using seeded RNG."""
        # Reset RNG state for this night (deterministic)
        rng = random.Random(self.seed + night_id)
        
        # Transparency: 0.3 (poor) to 1.0 (perfect)
        transparency = 0.3 + 0.7 * rng.random()
        
        # Seeing base: median ± 50%
        seeing_base = self.base_seeing * (0.5 + rng.random())
        
        # Cloud coverage
        if transparency > 0.85:
            cloud_coverage = 0.0
            condition = WeatherCondition.CLEAR
        elif transparency > 0.65:
            cloud_coverage = 0.3
            condition = WeatherCondition.PARTLY_CLOUDY
        elif transparency > 0.45:
            cloud_coverage = 0.7
            condition = WeatherCondition.CLOUDY
        else:
            cloud_coverage = 0.95
            condition = WeatherCondition.OVERCAST
        
        night_jd = 2451545.0 + night_id
        return NightWeather(night_jd, transparency, seeing_base, cloud_coverage, condition)
    
    def _get_night(self, jd: float) -> NightWeather:
        """Get weather for night containing jd (cached)."""
        night_id = self._night_id(jd)
        if night_id not in self._night_cache:
            self._night_cache[night_id] = self._generate_night(night_id)
        return self._night_cache[night_id]
    
    def transparency(self, jd: float) -> float:
        """
        Get atmospheric transparency at given JD.
        
        Args:
            jd: Julian Date
            
        Returns:
            Transparency 0.0 (opaque) to 1.0 (perfect)
        """
        night = self._get_night(jd)
        return night.transparency
    
    def seeing(self, jd: float, smooth_minutes: float = 5.0) -> float:
        """
        Get seeing FWHM in arcsec with smooth temporal variation.
        
        Args:
            jd: Julian Date
            smooth_minutes: Timescale for seeing variations (minutes)
            
        Returns:
            Seeing FWHM in arcseconds
        """
        night = self._get_night(jd)
        base = night.seeing_base
        
        # Smooth variation using sine wave
        # Period ~ smooth_minutes, amplitude ~ ±20% of base
        t = (jd - night.night_jd) * 1440.0  # Convert to minutes
        freq = 2.0 * math.pi / smooth_minutes
        variation = 0.2 * math.sin(freq * t + self.seed)
        
        seeing = base * (1.0 + variation)
        return max(0.5, min(10.0, seeing))  # Clamp to reasonable range
    
    def condition(self, jd: float) -> WeatherCondition:
        """
        Get weather condition category at given JD.
        
        Args:
            jd: Julian Date
            
        Returns:
            WeatherCondition enum value
        """
        night = self._get_night(jd)
        return night.condition
    
    def cloud_coverage(self, jd: float) -> float:
        """
        Get cloud coverage at given JD.
        
        Args:
            jd: Julian Date
            
        Returns:
            Cloud coverage 0.0 (clear) to 1.0 (overcast)
        """
        night = self._get_night(jd)
        return night.cloud_coverage
    
    def get_seeing(self, jd: float, smooth_minutes: float = 5.0) -> float:
        """
        Alias for seeing() for backward compatibility.
        """
        return self.seeing(jd, smooth_minutes)