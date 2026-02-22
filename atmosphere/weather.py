"""
Weather System — Procedural weather generation with smooth seeing and nightly conditions.
"""

from enum import Enum
from dataclasses import dataclass, field
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
    samples: list = field(default_factory=list)  # list of (transparency, seeing) tuples, one per 10-min interval


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
    Procedural weather generation with per-night caching and smooth transitions.

    Usage:
        ws = WeatherSystem(base_seeing=2.5, seed=42)

        # Every frame:
        transp = ws.transparency(jd)    # 0.0-1.0
        seeing = ws.seeing(jd)          # arcsec FWHM (with temporal variation)
        cond   = ws.condition(jd)       # WeatherCondition enum

        # Forecast:
        forecast = ws.forecast(jd, days=7)  # list[NightWeather]
    """

    # Markov transition matrix: prob[current_condition][next_condition]
    # Rows: CLEAR, PARTLY_CLOUDY, CLOUDY, OVERCAST
    # Columns: same order
    TRANSITION_MATRIX = [
        [0.70, 0.20, 0.08, 0.02],  # CLEAR -> ...
        [0.30, 0.40, 0.25, 0.05],  # PARTLY_CLOUDY -> ...
        [0.10, 0.30, 0.45, 0.15],  # CLOUDY -> ...
        [0.05, 0.15, 0.40, 0.40],  # OVERCAST -> ...
    ]

    # Condition ranges for transparency and seeing
    CONDITION_PARAMS = {
        WeatherCondition.CLEAR:         {'transp': (0.85, 1.00), 'seeing': (1.0, 2.8)},
        WeatherCondition.PARTLY_CLOUDY: {'transp': (0.60, 0.85), 'seeing': (1.8, 4.0)},
        WeatherCondition.CLOUDY:        {'transp': (0.25, 0.60), 'seeing': (2.5, 5.5)},
        WeatherCondition.OVERCAST:      {'transp': (0.00, 0.25), 'seeing': (3.5, 7.0)},
    }

    SAMPLE_INTERVAL_MIN = 10  # Sample weather every 10 minutes
    SAMPLES_PER_NIGHT = 144   # 24h / 10min

    # Default weights for random condition selection: CLEAR, PARTLY_CLOUDY, CLOUDY, OVERCAST
    DEFAULT_CONDITION_WEIGHTS = [0.50, 0.25, 0.15, 0.10]

    # Reference site seeing used to scale base_seeing (arcsec)
    REFERENCE_SEEING = 2.5

    # Multiplier applied to night_jd when computing per-night deterministic seeds
    _SEED_JD_SCALE = 1000

    # Maximum seed value accepted by numpy RandomState (2^31 - 1)
    _MAX_NUMPY_SEED = 2**31

    def __init__(self, base_seeing: float = 2.5, seed: int = 42):
        """
        Args:
            base_seeing: Baseline seeing in arcsec (site quality)
            seed: Random seed for deterministic weather
        """
        self._base_seeing = base_seeing
        self._seed = seed
        self._rng = random.Random(seed)
        self._np_rng = np.random.RandomState(seed)
        self._night_cache = {}  # Cache: {night_jd: NightWeather}
        self._max_cache_size = 30  # Keep 30 nights in cache

    def transparency(self, jd: float) -> float:
        """
        Get atmospheric transparency at Julian Date.

        Returns:
            Transparency 0.0 (opaque) to 1.0 (perfectly clear)
        """
        night = self._get_night(jd)
        return self._interpolate_sample(jd, night, 'transparency')

    def seeing(self, jd: float) -> float:
        """
        Get seeing FWHM in arcseconds at Julian Date.
        Includes temporal variation (5-15 min modulation).

        Returns:
            Seeing FWHM in arcsec (typically 1.0-7.0")
        """
        night = self._get_night(jd)
        base_seeing = self._interpolate_sample(jd, night, 'seeing')

        # Add temporal modulation for atmospheric turbulence
        variation = self._seeing_variation(jd)

        return base_seeing * (1.0 + variation)

    def condition(self, jd: float) -> WeatherCondition:
        """
        Get weather condition at Julian Date.

        Returns:
            WeatherCondition enum (CLEAR, PARTLY_CLOUDY, CLOUDY, OVERCAST)
        """
        night = self._get_night(jd)
        return night.condition

    def forecast(self, jd_start: float, days: int = 7) -> list:
        """
        Generate weather forecast for next N days using Markov chain.

        Args:
            jd_start: Starting Julian Date
            days: Number of days to forecast (default 7)

        Returns:
            List of NightWeather for each forecasted night
        """
        forecast_nights = []

        # Start from current night's condition
        current_night = self._get_night(jd_start)
        current_condition = current_night.condition

        # Generate each future night
        for day_offset in range(1, days + 1):
            jd_night = math.floor(jd_start) + day_offset + 0.5

            # Check cache first
            if jd_night in self._night_cache:
                forecast_nights.append(self._night_cache[jd_night])
                current_condition = self._night_cache[jd_night].condition
                continue

            # Use Markov chain to predict next condition
            current_condition = self._markov_next_condition(current_condition, jd_night)

            # Generate night with predicted condition
            night = self._generate_night(jd_night, condition=current_condition)
            forecast_nights.append(night)

        return forecast_nights

    def _get_night(self, jd: float) -> NightWeather:
        """
        Get or generate NightWeather for the night containing jd.
        Caches results for performance.
        """
        # Round to midnight (JD .5)
        night_jd = math.floor(jd) + 0.5

        if night_jd in self._night_cache:
            return self._night_cache[night_jd]

        # Generate new night
        night = self._generate_night(night_jd)

        # Cache management
        self._night_cache[night_jd] = night
        if len(self._night_cache) > self._max_cache_size:
            # Remove oldest entry
            oldest_jd = min(self._night_cache.keys())
            del self._night_cache[oldest_jd]

        return night

    def _generate_night(self, night_jd: float, condition: WeatherCondition = None) -> NightWeather:
        """
        Generate a complete NightWeather profile for a single night.

        Args:
            night_jd: JD of local midnight
            condition: Force specific condition (for forecast), or None for random
        """
        # Use night_jd as seed for deterministic generation
        night_seed = self._seed + int(night_jd * self._SEED_JD_SCALE)
        rng = random.Random(night_seed)
        np_rng = np.random.RandomState(night_seed % self._MAX_NUMPY_SEED)

        # Determine condition (or use provided)
        if condition is None:
            condition = rng.choices(list(WeatherCondition), weights=self.DEFAULT_CONDITION_WEIGHTS)[0]

        # Get parameter ranges for this condition
        params = self.CONDITION_PARAMS[condition]
        transp_range = params['transp']
        seeing_range = params['seeing']

        # Base values for the night (mean around which we'll vary)
        base_transp = rng.uniform(*transp_range)
        base_seeing = rng.uniform(*seeing_range) * (self._base_seeing / self.REFERENCE_SEEING)

        # Generate smooth variation curves (samples every 10 min)
        samples = []
        for i in range(self.SAMPLES_PER_NIGHT):
            # Smooth sinusoidal variation within night
            phase = i / self.SAMPLES_PER_NIGHT * 2 * math.pi

            # Transparency variation (±15% around base)
            transp_var = 0.15 * math.sin(phase + rng.uniform(0, 2 * math.pi))
            transp = float(np.clip(base_transp * (1.0 + transp_var), 0.0, 1.0))

            # Seeing variation (±20% around base)
            seeing_var = 0.20 * math.sin(phase * 1.3 + rng.uniform(0, 2 * math.pi))
            seeing = max(0.5, base_seeing * (1.0 + seeing_var))

            samples.append((transp, float(seeing)))

        # Cloud coverage from transparency (inverse relationship)
        cloud_coverage = 1.0 - base_transp

        return NightWeather(
            night_jd=night_jd,
            transparency=base_transp,
            seeing_base=base_seeing,
            cloud_coverage=cloud_coverage,
            condition=condition,
            samples=samples,
        )

    def _interpolate_sample(self, jd: float, night: NightWeather, param: str) -> float:
        """
        Interpolate transparency or seeing from night samples.

        Args:
            jd: Julian Date to interpolate
            night: NightWeather with samples
            param: 'transparency' or 'seeing'
        """
        # Fallback to base values if samples not available
        if not night.samples:
            return night.transparency if param == 'transparency' else night.seeing_base

        # Calculate minutes since midnight
        minutes_since_midnight = ((jd - night.night_jd) * 24 * 60) % (24 * 60)

        # Find sample index (float)
        sample_idx = minutes_since_midnight / self.SAMPLE_INTERVAL_MIN

        # Get surrounding samples
        idx_low = int(math.floor(sample_idx)) % self.SAMPLES_PER_NIGHT
        idx_high = int(math.ceil(sample_idx)) % self.SAMPLES_PER_NIGHT

        col = 0 if param == 'transparency' else 1
        val_low = night.samples[idx_low][col]
        val_high = night.samples[idx_high][col]

        # Linear interpolation
        frac = sample_idx - math.floor(sample_idx)
        return val_low * (1.0 - frac) + val_high * frac

    def _seeing_variation(self, jd: float) -> float:
        """
        Temporal modulation of seeing for atmospheric turbulence.
        Multiple frequency components (5-15 min periods).

        Returns:
            Variation factor -0.15 to +0.15 (±15%)
        """
        # Convert JD to seconds for high-frequency variation
        t_s = (jd - 2451545.0) * 86400.0

        # Multiple frequency components
        phase1 = t_s / 600.0   # 10 min period
        phase2 = t_s / 420.0   # 7 min period
        phase3 = t_s / 840.0   # 14 min period

        # Combine with different amplitudes
        variation = (
            0.10 * math.sin(phase1) +
            0.05 * math.sin(phase2) +
            0.03 * math.cos(phase3)
        )

        # Clamp to ±15%
        return float(np.clip(variation, -0.15, 0.15))

    def _markov_next_condition(self, current: WeatherCondition, jd: float) -> WeatherCondition:
        """
        Predict next night's condition using Markov chain.

        Args:
            current: Current WeatherCondition
            jd: Julian Date (used as seed for determinism)
        """
        # Use JD as seed for deterministic but varied transitions
        rng = random.Random(self._seed + int(jd * self._SEED_JD_SCALE))

        condition_list = [
            WeatherCondition.CLEAR,
            WeatherCondition.PARTLY_CLOUDY,
            WeatherCondition.CLOUDY,
            WeatherCondition.OVERCAST,
        ]

        current_idx = condition_list.index(current)
        probabilities = self.TRANSITION_MATRIX[current_idx]

        return rng.choices(condition_list, weights=probabilities)[0]