"""
Frame Management System

Handles different frame types with metadata for astronomical imaging:
- Light frames (science data)
- Dark frames (thermal calibration)
- Flat frames (vignetting/dust correction)
- Bias frames (electronic baseline)
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class FrameType(Enum):
    """Type of astronomical frame"""
    LIGHT = "LIGHT"
    DARK = "DARK"
    FLAT = "FLAT"
    BIAS = "BIAS"


@dataclass
class FrameMetadata:
    """
    Metadata for astronomical frame (FITS-like)
    
    Contains all necessary information for proper calibration and analysis
    """
    # Frame identification
    frame_type: FrameType
    frame_id: int = 0
    
    # Acquisition parameters
    exposure_s: float = 1.0
    gain: float = 1.0
    offset: int = 0
    binning: int = 1
    
    # Equipment
    camera: str = "Unknown"
    telescope: str = "Unknown"
    filter_name: str = "L"  # Luminance by default
    
    # Environmental
    temperature_c: float = 20.0
    
    # Time and location
    jd: float = 0.0  # Julian Date
    date_obs: Optional[datetime] = None
    
    # Target information (for light frames)
    target_name: str = ""
    ra_deg: float = 0.0
    dec_deg: float = 0.0
    
    # Image statistics (computed after acquisition)
    mean_adu: float = 0.0
    median_adu: float = 0.0
    std_adu: float = 0.0
    min_adu: float = 0.0
    max_adu: float = 0.0
    
    # Quality metrics
    fwhm_px: Optional[float] = None  # Full Width Half Maximum (seeing)
    snr: Optional[float] = None  # Signal-to-Noise Ratio
    n_stars_detected: Optional[int] = None
    
    # Processing flags
    is_calibrated: bool = False
    calibration_history: list[str] = field(default_factory=list)


class Frame:
    """
    Astronomical frame with data and metadata
    
    Represents a single image acquired by the camera, with all
    necessary information for calibration and analysis.
    """
    
    def __init__(self, data: np.ndarray, metadata: FrameMetadata):
        """
        Initialize frame
        
        Args:
            data: Image data as float32 numpy array
            metadata: Frame metadata
        """
        self.data = data.astype(np.float32)
        self.meta = metadata
        
        # Compute basic statistics if not already done
        if metadata.mean_adu == 0.0:
            self._compute_statistics()
    
    def _compute_statistics(self):
        """Compute basic image statistics"""
        self.meta.mean_adu = float(np.mean(self.data))
        self.meta.median_adu = float(np.median(self.data))
        self.meta.std_adu = float(np.std(self.data))
        self.meta.min_adu = float(np.min(self.data))
        self.meta.max_adu = float(np.max(self.data))
    
    @property
    def shape(self) -> tuple[int, int]:
        """Get image shape (height, width)"""
        return self.data.shape
    
    @property
    def width(self) -> int:
        """Get image width"""
        return self.data.shape[1]
    
    @property
    def height(self) -> int:
        """Get image height"""
        return self.data.shape[0]
    
    def copy(self) -> 'Frame':
        """Create deep copy of frame"""
        return Frame(
            data=self.data.copy(),
            metadata=FrameMetadata(**vars(self.meta))
        )
    
    def add_calibration_step(self, step_description: str):
        """Add calibration step to history"""
        self.meta.calibration_history.append(step_description)
        self.meta.is_calibrated = True
    
    def to_uint16(self, bit_depth: int = 16) -> np.ndarray:
        """
        Convert to unsigned 16-bit integer (typical camera output)
        
        Args:
            bit_depth: Effective bit depth (12, 14, or 16)
            
        Returns:
            uint16 array
        """
        max_val = (1 << bit_depth) - 1
        data_clipped = np.clip(self.data, 0, max_val)
        return data_clipped.astype(np.uint16)
    
    def to_uint8(self, black_point: float = 0.0, white_point: float = 1.0) -> np.ndarray:
        """
        Convert to 8-bit for display with stretch
        
        Args:
            black_point: Lower percentile (0-1)
            white_point: Upper percentile (0-1)
            
        Returns:
            uint8 array
        """
        # Compute percentiles for auto-stretch
        if black_point == 0.0 and white_point == 1.0:
            black = np.percentile(self.data, 0.1)
            white = np.percentile(self.data, 99.9)
        else:
            black = np.percentile(self.data, black_point * 100)
            white = np.percentile(self.data, white_point * 100)
        
        # Stretch
        stretched = (self.data - black) / (white - black + 1e-6)
        stretched = np.clip(stretched, 0, 1)
        
        return (stretched * 255).astype(np.uint8)
    
    def get_subframe(self, x: int, y: int, width: int, height: int) -> 'Frame':
        """
        Extract subframe (ROI)
        
        Args:
            x, y: Top-left corner
            width, height: Subframe dimensions
            
        Returns:
            New Frame with subframe data
        """
        x2 = min(x + width, self.width)
        y2 = min(y + height, self.height)
        
        subdata = self.data[y:y2, x:x2].copy()
        
        # Copy metadata
        submeta = FrameMetadata(**vars(self.meta))
        
        return Frame(subdata, submeta)
    
    def __repr__(self) -> str:
        return (f"Frame({self.meta.frame_type.value}, "
                f"{self.width}x{self.height}, "
                f"exp={self.meta.exposure_s}s, "
                f"mean={self.meta.mean_adu:.1f})")


class FrameSet:
    """
    Collection of frames of the same type
    
    Used for organizing and managing sets of calibration frames
    or light frames of the same target.
    """
    
    def __init__(self, frame_type: FrameType):
        """
        Initialize frame set
        
        Args:
            frame_type: Type of frames in this set
        """
        self.frame_type = frame_type
        self.frames: list[Frame] = []
    
    def add(self, frame: Frame):
        """Add frame to set"""
        if frame.meta.frame_type != self.frame_type:
            raise ValueError(f"Frame type mismatch: expected {self.frame_type}, "
                           f"got {frame.meta.frame_type}")
        self.frames.append(frame)
    
    def __len__(self) -> int:
        return len(self.frames)
    
    def __getitem__(self, idx: int) -> Frame:
        return self.frames[idx]
    
    def __iter__(self):
        return iter(self.frames)
    
    def clear(self):
        """Remove all frames"""
        self.frames.clear()
    
    def get_exposure_groups(self) -> dict[float, list[Frame]]:
        """
        Group frames by exposure time
        
        Returns:
            Dictionary mapping exposure time to list of frames
        """
        groups = {}
        for frame in self.frames:
            exp = frame.meta.exposure_s
            if exp not in groups:
                groups[exp] = []
            groups[exp].append(frame)
        return groups
    
    def get_filter_groups(self) -> dict[str, list[Frame]]:
        """
        Group frames by filter
        
        Returns:
            Dictionary mapping filter name to list of frames
        """
        groups = {}
        for frame in self.frames:
            filt = frame.meta.filter_name
            if filt not in groups:
                groups[filt] = []
            groups[filt].append(frame)
        return groups
    
    def get_statistics(self) -> dict:
        """
        Compute statistics across all frames
        
        Returns:
            Dictionary with aggregate statistics
        """
        if not self.frames:
            return {}
        
        means = [f.meta.mean_adu for f in self.frames]
        stds = [f.meta.std_adu for f in self.frames]
        
        return {
            'n_frames': len(self.frames),
            'mean_of_means': np.mean(means),
            'std_of_means': np.std(means),
            'mean_noise': np.mean(stds),
            'total_integration_s': sum(f.meta.exposure_s for f in self.frames)
        }
    
    def __repr__(self) -> str:
        return (f"FrameSet({self.frame_type.value}, "
                f"n={len(self.frames)})")


class ImagingSession:
    """
    Complete imaging session with all frame types
    
    Organizes light, dark, flat, and bias frames for a single
    target or calibration session.
    """
    
    def __init__(self, session_name: str = ""):
        """
        Initialize imaging session
        
        Args:
            session_name: Descriptive name for this session
        """
        self.session_name = session_name
        
        self.lights = FrameSet(FrameType.LIGHT)
        self.darks = FrameSet(FrameType.DARK)
        self.flats = FrameSet(FrameType.FLAT)
        self.biases = FrameSet(FrameType.BIAS)
        
        # Processed results
        self.master_dark: Optional[Frame] = None
        self.master_flat: Optional[Frame] = None
        self.master_bias: Optional[Frame] = None
        self.calibrated_lights: list[Frame] = []
        self.stacked_image: Optional[np.ndarray] = None
    
    def add_frame(self, frame: Frame):
        """Add frame to appropriate set based on type"""
        if frame.meta.frame_type == FrameType.LIGHT:
            self.lights.add(frame)
        elif frame.meta.frame_type == FrameType.DARK:
            self.darks.add(frame)
        elif frame.meta.frame_type == FrameType.FLAT:
            self.flats.add(frame)
        elif frame.meta.frame_type == FrameType.BIAS:
            self.biases.add(frame)
    
    def get_summary(self) -> dict:
        """Get summary of session"""
        return {
            'session_name': self.session_name,
            'n_lights': len(self.lights),
            'n_darks': len(self.darks),
            'n_flats': len(self.flats),
            'n_biases': len(self.biases),
            'has_master_dark': self.master_dark is not None,
            'has_master_flat': self.master_flat is not None,
            'has_master_bias': self.master_bias is not None,
            'n_calibrated': len(self.calibrated_lights),
            'has_stack': self.stacked_image is not None,
        }
    
    def __repr__(self) -> str:
        return (f"ImagingSession('{self.session_name}', "
                f"L={len(self.lights)}, D={len(self.darks)}, "
                f"F={len(self.flats)}, B={len(self.biases)})")
