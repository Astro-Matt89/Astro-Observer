"""
Observatory Simulation Game - Imaging System

Realistic CCD/CMOS imaging simulation including:
- Camera models (noise, QE, read noise, dark current)
- Frame types (Light, Dark, Flat, Bias)
- Calibration pipeline
- Stacking algorithms
- Post-processing
- Scientific analysis (photometry, astrometry)
"""

from .camera import Camera, CameraSpec
from .frames import Frame, FrameMetadata, FrameType
from .calibration import Calibrator
from .stacking import StackingEngine, StackMethod
from .processing import ImageProcessor
from .noise_model import NoiseModel

__all__ = [
    'Camera',
    'CameraSpec',
    'Frame',
    'FrameMetadata',
    'FrameType',
    'Calibrator',
    'StackingEngine',
    'StackMethod',
    'ImageProcessor',
    'NoiseModel',
]

__version__ = '0.1.0'
