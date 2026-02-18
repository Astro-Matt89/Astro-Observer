"""
Weather System — Procedural weather generation with smooth seeing and nightly conditions.

Provides:
  - WeatherCondition enum for weather states
  - NightWeather dataclass for per-night weather parameters
  - WeatherSystem class for smooth, realistic atmospheric conditions
"""

from enum import Enum
from dataclasses import dataclass
import math
import random


class WeatherCondition(Enum):
    """Weather condition categories."""
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"


@dataclass
class NightWeather:
    """Weather conditions for a single night."""
    night_jd: float              # JD at midnight
    transparency: float          # 0.0 (opaque) to 1.0 (perfectly clear)
    seeing_base: float           # Base seeing FWHM in arcsec
    cloud_coverage: float        # 0.0 (clear) to 1.0 (overcast)
    condition: WeatherCondition  # Enum value


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
        """Current atmospheric transparency (0.0 = opaque, 1.0 = perfect)."""
        return self._get_night(jd).transparency
    
    def condition(self, jd: float) -> WeatherCondition:
        """Current weather condition enum."""
        return self._get_night(jd).condition
    
    def seeing(self, jd: float) -> float:
        """
        Smooth seeing FWHM in arcsec.
        
        Uses sinusoidal interpolation over 10-minute cycles.
        No abrupt jumps like the old 5-minute discrete system.
        """
        night = self._get_night(jd)
        
        # 10-minute cycle (1/144 day)
        t = (jd % (1.0/144.0)) * 144.0  # 0..1 over 10 min
        
        # Sinusoidal variation: base ± 30%
        variation = 0.3 * math.sin(2 * math.pi * t)
        
        return night.seeing_base * (1.0 + variation)
