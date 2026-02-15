"""
Noise Model Utilities

Handles all noise generation for realistic imaging simulation:
- Shot noise (Poisson/Gaussian approximation)
- Read noise (Gaussian)
- Dark current (temperature-dependent)
- Hot/cold pixels
"""

import numpy as np
from typing import Optional


class NoiseModel:
    """Realistic noise generation for astronomical imaging"""
    
    @staticmethod
    def add_shot_noise(signal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """
        Add shot noise (Poisson noise from photon statistics)
        
        For high counts (>20), Poisson ≈ Gaussian with σ = √N
        
        Args:
            signal: Input signal in electrons or ADU
            rng: NumPy random generator
            
        Returns:
            Signal with shot noise added
        """
        # Clip to non-negative (required for sqrt)
        signal_clipped = np.clip(signal, 0.0, None)
        
        # Shot noise: σ = sqrt(signal)
        # Use Gaussian approximation (faster than Poisson for large N)
        noise_sigma = np.sqrt(signal_clipped)
        noise = rng.normal(0.0, noise_sigma).astype(np.float32)
        
        return signal + noise
    
    @staticmethod
    def add_read_noise(image: np.ndarray, read_noise_e: float, 
                      rng: np.random.Generator) -> np.ndarray:
        """
        Add read noise (Gaussian noise from electronics)
        
        Args:
            image: Input image
            read_noise_e: Read noise in electrons (typical: 5-15e for CCD, 1-3e for CMOS)
            rng: Random generator
            
        Returns:
            Image with read noise added
        """
        h, w = image.shape
        noise = rng.normal(0.0, read_noise_e, size=(h, w)).astype(np.float32)
        return image + noise
    
    @staticmethod
    def add_dark_current(image: np.ndarray, exposure_s: float, 
                        dark_current_e_per_s: float, temperature_c: float,
                        rng: np.random.Generator) -> np.ndarray:
        """
        Add dark current (temperature-dependent thermal noise)
        
        Dark current doubles approximately every 6-7°C
        
        Args:
            image: Input image
            exposure_s: Exposure time in seconds
            dark_current_e_per_s: Dark current at reference temp (e-/pixel/s)
            temperature_c: Sensor temperature in Celsius
            rng: Random generator
            
        Returns:
            Image with dark current added
        """
        # Temperature correction (doubles every 6.3°C)
        reference_temp_c = 25.0
        temp_factor = 2.0 ** ((temperature_c - reference_temp_c) / 6.3)
        
        # Total dark electrons
        dark_e = dark_current_e_per_s * temp_factor * exposure_s
        
        # Add uniform dark + shot noise from dark
        h, w = image.shape
        dark_frame = rng.normal(dark_e, np.sqrt(max(1.0, dark_e)), 
                               size=(h, w)).astype(np.float32)
        
        return image + dark_frame
    
    @staticmethod
    def generate_hot_pixels(shape: tuple[int, int], n_hot: int,
                           hot_level: float, rng: np.random.Generator) -> np.ndarray:
        """
        Generate hot pixel map
        
        Args:
            shape: Image shape (height, width)
            n_hot: Number of hot pixels
            hot_level: Hot pixel signal level (electrons)
            rng: Random generator
            
        Returns:
            Hot pixel map (mostly zeros, with hot pixels)
        """
        h, w = shape
        hot_map = np.zeros((h, w), dtype=np.float32)
        
        if n_hot > 0:
            # Random positions
            ys = rng.integers(0, h, size=n_hot)
            xs = rng.integers(0, w, size=n_hot)
            
            # Random levels (between hot_level/2 and hot_level*2)
            levels = rng.uniform(hot_level * 0.5, hot_level * 2.0, size=n_hot)
            
            hot_map[ys, xs] = levels
        
        return hot_map
    
    @staticmethod
    def generate_defect_map(shape: tuple[int, int], defect_rate: float,
                           rng: np.random.Generator) -> np.ndarray:
        """
        Generate sensor defect map (hot/cold/dead pixels)
        
        Args:
            shape: Image shape
            defect_rate: Fraction of defective pixels (typical: 0.0001-0.001)
            rng: Random generator
            
        Returns:
            Binary mask (1=defective, 0=good)
        """
        h, w = shape
        n_defects = int(h * w * defect_rate)
        
        defect_map = np.zeros((h, w), dtype=np.uint8)
        
        if n_defects > 0:
            ys = rng.integers(0, h, size=n_defects)
            xs = rng.integers(0, w, size=n_defects)
            defect_map[ys, xs] = 1
        
        return defect_map


def splitmix64(x: int) -> int:
    """
    SplitMix64 hash function for deterministic RNG seeding
    
    Args:
        x: Input seed (64-bit integer)
        
    Returns:
        Hashed 64-bit integer
    """
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF


def hash_u64(*vals: int) -> int:
    """
    Hash multiple 64-bit integers into one
    
    Args:
        *vals: Variable number of integers to hash
        
    Returns:
        Combined hash
    """
    x = 0xA5A5A5A5A5A5A5A5
    for v in vals:
        x ^= (v & 0xFFFFFFFFFFFFFFFF)
        x = splitmix64(x)
    return x


def rng_from_seed(seed_u64: int) -> np.random.Generator:
    """
    Create NumPy random generator from 64-bit seed
    
    Args:
        seed_u64: 64-bit integer seed
        
    Returns:
        NumPy Generator instance
    """
    return np.random.default_rng(np.uint64(seed_u64))
