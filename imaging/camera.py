"""
Camera Simulation System

Realistic CCD/CMOS camera simulation including:
- Physical sensor characteristics
- Quantum efficiency
- Read noise, dark current, shot noise
- Digitization (ADC)
- Temperature effects
"""

import numpy as np
import math
from dataclasses import dataclass
from typing import Optional
from .noise_model import NoiseModel, rng_from_seed, hash_u64
from .frames import Frame, FrameMetadata, FrameType


@dataclass
class CameraSpec:
    """
    Camera technical specifications
    
    Defines physical and electronic characteristics of the imaging sensor
    """
    # Identification
    name: str
    manufacturer: str = "Generic"
    sensor_type: str = "CMOS"  # "CCD" or "CMOS"
    
    # Sensor geometry
    pixel_size_um: float = 3.76  # Pixel size in microns
    resolution: tuple[int, int] = (1920, 1080)  # (width, height) in pixels
    
    # Sensor performance
    read_noise_e: float = 2.0  # Read noise in electrons (lower is better)
    dark_current_e_per_s: float = 0.01  # Dark current at 25°C (e-/pixel/s)
    quantum_efficiency: float = 0.70  # QE: fraction of photons converted (0-1)
    full_well_capacity_e: int = 50000  # Maximum electrons per pixel
    
    # Electronics
    bit_depth: int = 16  # ADC bit depth (12, 14, or 16)
    gain_e_per_adu: float = 1.0  # Electrons per ADU (analog-digital unit)
    
    # Features
    has_cooling: bool = False  # Regulated temperature control
    min_temp_c: float = -10.0  # Minimum cooling temperature (if cooled)
    
    # Defects
    hot_pixel_rate: float = 0.0005  # Fraction of hot pixels (0.0001-0.001 typical)
    defect_rate: float = 0.0001  # Fraction of dead/defective pixels
    
    # Career mode (for compatibility with equipment system)
    price_rp: int = 500  # Research points cost
    tier: int = 1  # 1=starter, 2=intermediate, 3=advanced, 4=pro

    # Camera type flags
    is_allsky: bool = False   # True = uses fisheye projection, covers full sky

    # Legacy (kept for backward compatibility)
    price: int = 500
    tier_name: str = "BEGINNER"
    
    def __post_init__(self):
        """Validate specs after initialization"""
        assert 0.0 < self.quantum_efficiency <= 1.0, "QE must be in (0, 1]"
        assert self.bit_depth in [12, 14, 16], "Bit depth must be 12, 14, or 16"
        assert self.read_noise_e > 0, "Read noise must be positive"
    
    @property
    def sensor_diagonal_mm(self) -> float:
        """Calculate sensor diagonal in mm"""
        w_mm = self.resolution[0] * self.pixel_size_um / 1000.0
        h_mm = self.resolution[1] * self.pixel_size_um / 1000.0
        return math.sqrt(w_mm**2 + h_mm**2)
    
    @property
    def sensor_area_mm2(self) -> float:
        """Calculate sensor area in mm²"""
        w_mm = self.resolution[0] * self.pixel_size_um / 1000.0
        h_mm = self.resolution[1] * self.pixel_size_um / 1000.0
        return w_mm * h_mm
    
    @property
    def max_adu(self) -> int:
        """Maximum ADU value for this bit depth"""
        return (1 << self.bit_depth) - 1
    
    def compute_read_noise_adu(self) -> float:
        """Convert read noise from electrons to ADU"""
        return self.read_noise_e / self.gain_e_per_adu
    
    def __repr__(self) -> str:
        return (f"CameraSpec('{self.name}', {self.resolution[0]}x{self.resolution[1]}, "
                f"{self.bit_depth}bit, RN={self.read_noise_e:.1f}e)")


class Camera:
    """
    Camera simulator
    
    Simulates realistic image acquisition with all noise sources
    and sensor characteristics.
    """
    
    def __init__(self, spec: CameraSpec, seed: Optional[int] = None):
        """
        Initialize camera
        
        Args:
            spec: Camera specifications
            seed: Random seed for deterministic noise (optional)
        """
        self.spec = spec
        self.seed = seed if seed is not None else 0x42424242
        
        # State
        self.temperature_c = 25.0  # Current sensor temperature
        self.is_cooling = False
        self.target_temp_c = 25.0
        
        # Persistent defects (deterministic from camera seed)
        self._defect_map = None
        self._hot_pixel_map = None
        
        # Statistics
        self.total_exposures = 0
    
    def set_cooling(self, enabled: bool, target_temp_c: Optional[float] = None):
        """
        Enable/disable sensor cooling
        
        Args:
            enabled: Enable cooling
            target_temp_c: Target temperature (if enabled)
            
        Returns:
            True if successful, False if camera doesn't support cooling
        """
        if enabled and not self.spec.has_cooling:
            return False
        
        self.is_cooling = enabled
        
        if enabled and target_temp_c is not None:
            self.target_temp_c = max(self.spec.min_temp_c, target_temp_c)
            # In reality, cooling takes time, but we'll instant-set for simplicity
            self.temperature_c = self.target_temp_c
        elif not enabled:
            self.temperature_c = 25.0  # Warm up to ambient
        
        return True
    
    def _get_defect_map(self) -> np.ndarray:
        """Get persistent defect map (computed once)"""
        if self._defect_map is None:
            h, w = self.spec.resolution[1], self.spec.resolution[0]
            seed = hash_u64(self.seed, 0xDEFEC7)  # DEFECT-like value
            rng = rng_from_seed(seed)
            self._defect_map = NoiseModel.generate_defect_map(
                (h, w), self.spec.defect_rate, rng
            )
        return self._defect_map
    
    def _get_hot_pixel_map(self) -> np.ndarray:
        """Get persistent hot pixel map (computed once)"""
        if self._hot_pixel_map is None:
            h, w = self.spec.resolution[1], self.spec.resolution[0]
            n_hot = int(h * w * self.spec.hot_pixel_rate)
            seed = hash_u64(self.seed, 0x407199)  # HOTPIX-like value
            rng = rng_from_seed(seed)
            # Hot pixels contribute extra dark current
            hot_level = 100.0  # electrons/s for hot pixels
            self._hot_pixel_map = NoiseModel.generate_hot_pixels(
                (h, w), n_hot, hot_level, rng
            )
        return self._hot_pixel_map
    
    def capture_frame(self, 
                     exposure_s: float,
                     sky_signal_photons: np.ndarray,
                     frame_type: FrameType,
                     frame_seed: Optional[int] = None,
                     metadata: Optional[FrameMetadata] = None) -> Frame:
        """
        Capture a single frame with realistic noise
        
        Args:
            exposure_s: Exposure time in seconds
            sky_signal_photons: Input signal in photons per pixel
            frame_type: Type of frame (LIGHT, DARK, FLAT, BIAS)
            frame_seed: Random seed for this frame (optional)
            metadata: Frame metadata (optional, will be created if None)
            
        Returns:
            Frame object with data and metadata
        """
        # Derive h/w from the signal — may be a reduced render buffer
        h, w = sky_signal_photons.shape[:2]
        sensor_h = self.spec.resolution[1]
        sensor_w = self.spec.resolution[0]
        # Binning factor: how many sensor pixels per render pixel
        bin_x = sensor_w / w
        bin_y = sensor_h / h
        
        # Generate RNG for this frame
        if frame_seed is None:
            frame_seed = hash_u64(self.seed, self.total_exposures)
        rng = rng_from_seed(frame_seed)
        
        # Stage 1: Convert photons to electrons (Quantum Efficiency)
        signal_e = sky_signal_photons * self.spec.quantum_efficiency
        
        # Stage 2: Add shot noise (Poisson statistics)
        signal_e = NoiseModel.add_shot_noise(signal_e, rng)
        
        # Stage 3: Dark current — scale by bin factor (more area per pixel)
        dark_e = self.spec.dark_current_e_per_s * exposure_s * bin_x * bin_y
        dark_frame = np.full((h, w), dark_e, dtype=np.float32)
        
        # Hot pixels: fixed spatial map, amplitude scales with exposure.
        # Hot pixel dark-current rate: exponential distribution ~3-20 e/s typical.
        # We skip hot pixels if there are none (rate=0 or very few).
        n_hot = int(self.spec.hot_pixel_rate * h * w)
        if n_hot > 0:
            rng_hot = rng_from_seed(hash_u64(self.seed, 99999))
            hx = rng_hot.integers(0, w, n_hot)
            hy = rng_hot.integers(0, h, n_hot)
            # Rate in e-/s: exponential with mean ~8 e-/s (realistic CMOS hot pixel).
            # Hot pixels are physical sensor defects — NOT scaled by binning.
            hot_rate_e_per_s = rng_hot.exponential(8.0, n_hot).astype(np.float32)
            hot_e = hot_rate_e_per_s * exposure_s   # NO bin factor
            for i in range(n_hot):
                dark_frame[hy[i], hx[i]] += hot_e[i]
        
        # Add shot noise from dark
        dark_frame = NoiseModel.add_shot_noise(dark_frame, rng)
        
        signal_e = signal_e + dark_frame
        
        # Stage 4: Add read noise (Gaussian)
        signal_e = NoiseModel.add_read_noise(signal_e, self.spec.read_noise_e, rng)
        
        # Stage 5: Apply full well saturation
        signal_e = np.clip(signal_e, 0, self.spec.full_well_capacity_e)
        
        # Stage 6: Convert to ADU (Analog-to-Digital Units)
        signal_adu = signal_e / self.spec.gain_e_per_adu
        
        # Stage 7: Digitize (quantize to bit depth)
        signal_adu = np.clip(signal_adu, 0, self.spec.max_adu)
        signal_adu = np.round(signal_adu).astype(np.float32)
        
        # Create metadata if not provided
        if metadata is None:
            metadata = FrameMetadata(
                frame_type=frame_type,
                frame_id=self.total_exposures,
                exposure_s=exposure_s,
                camera=self.spec.name,
                temperature_c=self.temperature_c,
            )
        else:
            metadata.frame_id = self.total_exposures
            metadata.camera = self.spec.name
            metadata.temperature_c = self.temperature_c
        
        # Create frame
        frame = Frame(signal_adu, metadata)
        
        self.total_exposures += 1
        
        return frame
    
    def capture_dark_frame(self, exposure_s: float, 
                          frame_seed: Optional[int] = None,
                          render_shape: Optional[tuple] = None) -> Frame:
        """
        Capture dark frame (no signal, just noise).
        render_shape: (h, w) of the render buffer — must match light frames.
        """
        if render_shape is not None:
            h, w = render_shape
        else:
            h, w = self.spec.resolution[1], self.spec.resolution[0]
        
        # No signal for dark frame
        sky_signal = np.zeros((h, w), dtype=np.float32)
        
        metadata = FrameMetadata(
            frame_type=FrameType.DARK,
            exposure_s=exposure_s,
        )
        
        return self.capture_frame(exposure_s, sky_signal, FrameType.DARK, 
                                 frame_seed, metadata)
    
    def capture_bias_frame(self, frame_seed: Optional[int] = None) -> Frame:
        """
        Capture bias frame (zero exposure, just read noise + offset)
        
        Args:
            frame_seed: Random seed (optional)
            
        Returns:
            Bias frame
        """
        h, w = self.spec.resolution[1], self.spec.resolution[0]
        sky_signal = np.zeros((h, w), dtype=np.float32)
        
        metadata = FrameMetadata(
            frame_type=FrameType.BIAS,
            exposure_s=0.0,
        )
        
        return self.capture_frame(0.0, sky_signal, FrameType.BIAS,
                                 frame_seed, metadata)
    
    def compute_pixel_scale(self, focal_length_mm: float) -> float:
        """
        Compute pixel scale (arcsec/pixel) given focal length
        
        Args:
            focal_length_mm: Telescope focal length in mm
            
        Returns:
            Pixel scale in arcseconds per pixel
        """
        # pixel_scale = (pixel_size_um / focal_length_mm) * 206265
        # where 206265 = arcsec per radian
        return (self.spec.pixel_size_um / focal_length_mm) * 206.265
    
    def compute_fov(self, focal_length_mm: float) -> tuple[float, float]:
        """
        Compute field of view given focal length
        
        Args:
            focal_length_mm: Telescope focal length in mm
            
        Returns:
            (width_deg, height_deg) field of view in degrees
        """
        w_mm = self.spec.resolution[0] * self.spec.pixel_size_um / 1000.0
        h_mm = self.spec.resolution[1] * self.spec.pixel_size_um / 1000.0
        
        fov_w_rad = 2.0 * math.atan(w_mm / (2.0 * focal_length_mm))
        fov_h_rad = 2.0 * math.atan(h_mm / (2.0 * focal_length_mm))
        
        return (math.degrees(fov_w_rad), math.degrees(fov_h_rad))
    
    def __repr__(self) -> str:
        return (f"Camera('{self.spec.name}', temp={self.temperature_c:.1f}°C, "
                f"exposures={self.total_exposures})")


# Predefined camera database (for career mode)
CAMERA_DATABASE = {
    "WEBCAM_MOD": CameraSpec(
        name="Modified Webcam",
        manufacturer="Generic",
        sensor_type="CMOS",
        pixel_size_um=5.6,
        resolution=(640, 480),
        read_noise_e=12.0,
        dark_current_e_per_s=0.5,
        quantum_efficiency=0.40,
        full_well_capacity_e=15000,
        bit_depth=12,
        gain_e_per_adu=2.0,
        has_cooling=False,
        price_rp=0,
        tier=1,
        price=100,
        tier_name="BEGINNER"
    ),
    
    "ZWO_ASI294MC": CameraSpec(
        name="ZWO ASI294MC Pro",
        manufacturer="ZWO",
        sensor_type="CMOS",
        pixel_size_um=4.63,
        resolution=(4144, 2822),
        read_noise_e=1.5,
        dark_current_e_per_s=0.005,
        quantum_efficiency=0.80,
        full_well_capacity_e=63000,
        bit_depth=14,
        gain_e_per_adu=0.5,
        has_cooling=True,
        min_temp_c=-10.0,
        hot_pixel_rate=0.0001,
        defect_rate=0.00005,
        price_rp=1500,
        tier=2,
        price=1500,
        tier_name="ADVANCED"
    ),
    
    "QHY600M": CameraSpec(
        name="QHY600M",
        manufacturer="QHYCCD",
        sensor_type="CMOS",
        pixel_size_um=3.76,
        resolution=(9576, 6388),
        read_noise_e=1.3,
        dark_current_e_per_s=0.002,
        quantum_efficiency=0.85,
        full_well_capacity_e=90000,
        bit_depth=16,
        gain_e_per_adu=0.3,
        has_cooling=True,
        min_temp_c=-20.0,
        hot_pixel_rate=0.00005,
        defect_rate=0.00002,
        price_rp=5000,
        tier=4,
        price=5000,
        tier_name="PRO"
    ),
    # ── All-sky cameras ───────────────────────────────────────────────────────
    "ALLSKY_ZWO174MM": CameraSpec(
        name="ZWO ASI174MM AllSky",
        manufacturer="ZWO",
        sensor_type="CMOS",
        pixel_size_um=5.86,
        resolution=(1936, 1216),
        read_noise_e=3.0,
        dark_current_e_per_s=0.04,
        quantum_efficiency=0.78,
        full_well_capacity_e=32000,
        bit_depth=12,
        gain_e_per_adu=1.2,
        has_cooling=False,
        hot_pixel_rate=0.0003,
        price_rp=800,
        tier=2,
        price=800,
        tier_name="INTERMEDIATE",
        is_allsky=True,
    ),

    "ALLSKY_QHY5III462C": CameraSpec(
        name="QHY5III-462C AllSky",
        manufacturer="QHYCCD",
        sensor_type="CMOS",
        pixel_size_um=2.90,
        resolution=(1920, 1080),
        read_noise_e=1.0,
        dark_current_e_per_s=0.02,
        quantum_efficiency=0.91,
        full_well_capacity_e=14000,
        bit_depth=12,
        gain_e_per_adu=0.4,
        has_cooling=False,
        hot_pixel_rate=0.0002,
        price_rp=1200,
        tier=3,
        price=1200,
        tier_name="ADVANCED",
        is_allsky=True,
    ),
}


def get_camera(camera_id: str, seed: Optional[int] = None) -> Camera:
    """
    Get camera instance from database
    
    Args:
        camera_id: Camera identifier (e.g., "ZWO_ASI294MC")
        seed: Random seed for deterministic behavior
        
    Returns:
        Camera instance
    """
    if camera_id not in CAMERA_DATABASE:
        raise ValueError(f"Unknown camera: {camera_id}")
    
    spec = CAMERA_DATABASE[camera_id]
    return Camera(spec, seed)
