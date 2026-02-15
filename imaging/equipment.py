"""
Equipment Database - Telescopes, Cameras, and Filters

Complete equipment catalog for astronomical imaging with:
- Telescopes (refractors, reflectors, SCT, etc.)
- Cameras (already defined in camera.py, this provides metadata)
- Filters (LRGB, narrowband, photometric)
- Stats calculators (FOV, pixel scale, resolution)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TelescopeType(Enum):
    """Types of telescopes"""
    REFRACTOR = "Refractor"
    REFLECTOR = "Reflector (Newtonian)"
    SCT = "Schmidt-Cassegrain"
    MAKSUTOV = "Maksutov-Cassegrain"
    RITCHEY_CHRETIEN = "Ritchey-Chrétien"


@dataclass
class TelescopeSpec:
    """Telescope specifications"""
    id: str
    name: str
    telescope_type: TelescopeType
    aperture_mm: float          # Diameter in mm
    focal_length_mm: float      # Focal length in mm
    focal_ratio: float          # f/ratio (calculated)
    obstruction_pct: float      # Central obstruction (0 for refractors)
    
    # Career mode
    price_rp: int               # Research points cost
    tier: int                   # 1=starter, 2=intermediate, 3=advanced, 4=pro
    
    # Optional specs
    weight_kg: float = 0.0
    length_mm: float = 0.0
    
    def __post_init__(self):
        """Calculate f/ratio if not provided"""
        if self.focal_ratio == 0:
            self.focal_ratio = self.focal_length_mm / self.aperture_mm
    
    def field_of_view(self, sensor_width_mm: float, sensor_height_mm: float) -> tuple[float, float]:
        """
        Calculate field of view in degrees
        
        Args:
            sensor_width_mm: Camera sensor width
            sensor_height_mm: Camera sensor height
            
        Returns:
            (fov_width_deg, fov_height_deg)
        """
        import math
        fov_w = 2 * math.degrees(math.atan(sensor_width_mm / (2 * self.focal_length_mm)))
        fov_h = 2 * math.degrees(math.atan(sensor_height_mm / (2 * self.focal_length_mm)))
        return fov_w, fov_h
    
    def pixel_scale(self, pixel_size_um: float) -> float:
        """
        Calculate pixel scale in arcsec/pixel
        
        Args:
            pixel_size_um: Camera pixel size in microns
            
        Returns:
            Pixel scale in arcsec/pixel
        """
        return 206.265 * pixel_size_um / self.focal_length_mm


# Telescope Database
TELESCOPES = {
    # Tier 1 - Starter (0-500 RP)
    "WEBCAM_LENS": TelescopeSpec(
        id="WEBCAM_LENS",
        name="Webcam Lens 50mm f/2",
        telescope_type=TelescopeType.REFRACTOR,
        aperture_mm=25,
        focal_length_mm=50,
        focal_ratio=2.0,
        obstruction_pct=0.0,
        price_rp=0,
        tier=1,
    ),
    
    "REF_80_F5": TelescopeSpec(
        id="REF_80_F5",
        name="Refractor 80mm f/5",
        telescope_type=TelescopeType.REFRACTOR,
        aperture_mm=80,
        focal_length_mm=400,
        focal_ratio=5.0,
        obstruction_pct=0.0,
        price_rp=500,
        tier=1,
        weight_kg=2.5,
    ),
    
    "NEWT_114_F4": TelescopeSpec(
        id="NEWT_114_F4",
        name="Newtonian 114mm f/4",
        telescope_type=TelescopeType.REFLECTOR,
        aperture_mm=114,
        focal_length_mm=450,
        focal_ratio=4.0,
        obstruction_pct=25.0,
        price_rp=600,
        tier=1,
        weight_kg=4.0,
    ),
    
    # Tier 2 - Intermediate (500-2000 RP)
    "NEWT_150_F5": TelescopeSpec(
        id="NEWT_150_F5",
        name="Newtonian 150mm f/5",
        telescope_type=TelescopeType.REFLECTOR,
        aperture_mm=150,
        focal_length_mm=750,
        focal_ratio=5.0,
        obstruction_pct=25.0,
        price_rp=1000,
        tier=2,
        weight_kg=7.0,
    ),
    
    "REF_102_F7": TelescopeSpec(
        id="REF_102_F7",
        name="Refractor 102mm f/7 ED",
        telescope_type=TelescopeType.REFRACTOR,
        aperture_mm=102,
        focal_length_mm=714,
        focal_ratio=7.0,
        obstruction_pct=0.0,
        price_rp=1500,
        tier=2,
        weight_kg=5.5,
    ),
    
    "SCT_6_F10": TelescopeSpec(
        id="SCT_6_F10",
        name="SCT 6\" f/10",
        telescope_type=TelescopeType.SCT,
        aperture_mm=150,
        focal_length_mm=1500,
        focal_ratio=10.0,
        obstruction_pct=35.0,
        price_rp=2000,
        tier=2,
        weight_kg=6.0,
    ),
    
    # Tier 3 - Advanced (2000-5000 RP)
    "NEWT_200_F5": TelescopeSpec(
        id="NEWT_200_F5",
        name="Newtonian 200mm f/5",
        telescope_type=TelescopeType.REFLECTOR,
        aperture_mm=200,
        focal_length_mm=1000,
        focal_ratio=5.0,
        obstruction_pct=25.0,
        price_rp=2500,
        tier=3,
        weight_kg=12.0,
    ),
    
    "SCT_8_F10": TelescopeSpec(
        id="SCT_8_F10",
        name="SCT 8\" f/10",
        telescope_type=TelescopeType.SCT,
        aperture_mm=203,
        focal_length_mm=2032,
        focal_ratio=10.0,
        obstruction_pct=35.0,
        price_rp=3500,
        tier=3,
        weight_kg=10.0,
    ),
    
    "REF_130_F7": TelescopeSpec(
        id="REF_130_F7",
        name="Refractor 130mm f/7 APO",
        telescope_type=TelescopeType.REFRACTOR,
        aperture_mm=130,
        focal_length_mm=910,
        focal_ratio=7.0,
        obstruction_pct=0.0,
        price_rp=4000,
        tier=3,
        weight_kg=9.0,
    ),
    
    # Tier 4 - Professional (5000+ RP)
    "RC_10_F8": TelescopeSpec(
        id="RC_10_F8",
        name="Ritchey-Chrétien 10\" f/8",
        telescope_type=TelescopeType.RITCHEY_CHRETIEN,
        aperture_mm=254,
        focal_length_mm=2000,
        focal_ratio=8.0,
        obstruction_pct=35.0,
        price_rp=6000,
        tier=4,
        weight_kg=18.0,
    ),
    
    "SCT_11_F10": TelescopeSpec(
        id="SCT_11_F10",
        name="SCT 11\" f/10",
        telescope_type=TelescopeType.SCT,
        aperture_mm=280,
        focal_length_mm=2800,
        focal_ratio=10.0,
        obstruction_pct=35.0,
        price_rp=7000,
        tier=4,
        weight_kg=16.0,
    ),
    
    "NEWT_300_F4": TelescopeSpec(
        id="NEWT_300_F4",
        name="Newtonian 12\" f/4",
        telescope_type=TelescopeType.REFLECTOR,
        aperture_mm=300,
        focal_length_mm=1200,
        focal_ratio=4.0,
        obstruction_pct=25.0,
        price_rp=8000,
        tier=4,
        weight_kg=25.0,
    ),
}


class FilterType(Enum):
    """Types of filters"""
    BROADBAND = "Broadband"
    NARROWBAND = "Narrowband"
    PHOTOMETRIC = "Photometric"


@dataclass
class FilterSpec:
    """Filter specifications"""
    id: str
    name: str
    filter_type: FilterType
    wavelength_nm: Optional[float]  # Central wavelength (for narrowband)
    bandwidth_nm: Optional[float]   # FWHM bandwidth
    transmission_pct: float         # Peak transmission
    
    # Career mode
    price_rp: int
    tier: int
    
    # Description
    description: str = ""


# Filter Database
FILTERS = {
    # Tier 1 - Starter (free/cheap)
    "L": FilterSpec(
        id="L",
        name="Luminance (clear)",
        filter_type=FilterType.BROADBAND,
        wavelength_nm=None,
        bandwidth_nm=None,
        transmission_pct=95.0,
        price_rp=0,
        tier=1,
        description="Clear filter, passes all visible light"
    ),
    
    "R": FilterSpec(
        id="R",
        name="Red",
        filter_type=FilterType.BROADBAND,
        wavelength_nm=650,
        bandwidth_nm=100,
        transmission_pct=90.0,
        price_rp=300,
        tier=1,
        description="Red broadband filter"
    ),
    
    "G": FilterSpec(
        id="G",
        name="Green",
        filter_type=FilterType.BROADBAND,
        wavelength_nm=530,
        bandwidth_nm=100,
        transmission_pct=90.0,
        price_rp=300,
        tier=1,
        description="Green broadband filter"
    ),
    
    "B": FilterSpec(
        id="B",
        name="Blue",
        filter_type=FilterType.BROADBAND,
        wavelength_nm=450,
        bandwidth_nm=100,
        transmission_pct=85.0,
        price_rp=300,
        tier=1,
        description="Blue broadband filter"
    ),
    
    # Tier 2 - Narrowband (1000-2000 RP)
    "HA": FilterSpec(
        id="HA",
        name="H-alpha (656nm, 7nm)",
        filter_type=FilterType.NARROWBAND,
        wavelength_nm=656.3,
        bandwidth_nm=7.0,
        transmission_pct=90.0,
        price_rp=1500,
        tier=2,
        description="Hydrogen-alpha emission line, excellent for nebulae"
    ),
    
    "OIII": FilterSpec(
        id="OIII",
        name="OIII (500nm, 10nm)",
        filter_type=FilterType.NARROWBAND,
        wavelength_nm=500.7,
        bandwidth_nm=10.0,
        transmission_pct=85.0,
        price_rp=1500,
        tier=2,
        description="Oxygen III emission line, planetary nebulae"
    ),
    
    "SII": FilterSpec(
        id="SII",
        name="SII (672nm, 8nm)",
        filter_type=FilterType.NARROWBAND,
        wavelength_nm=672.4,
        bandwidth_nm=8.0,
        transmission_pct=85.0,
        price_rp=1500,
        tier=2,
        description="Sulfur II emission line, supernova remnants"
    ),
    
    # Tier 3 - Advanced (2000+ RP)
    "LP": FilterSpec(
        id="LP",
        name="Light Pollution (LP)",
        filter_type=FilterType.BROADBAND,
        wavelength_nm=None,
        bandwidth_nm=None,
        transmission_pct=75.0,
        price_rp=800,
        tier=2,
        description="Blocks common light pollution wavelengths"
    ),
    
    "UHC": FilterSpec(
        id="UHC",
        name="Ultra High Contrast",
        filter_type=FilterType.NARROWBAND,
        wavelength_nm=None,
        bandwidth_nm=None,
        transmission_pct=70.0,
        price_rp=1200,
        tier=2,
        description="Passes H-alpha, H-beta, and OIII only"
    ),
}


def get_telescope(telescope_id: str) -> Optional[TelescopeSpec]:
    """Get telescope by ID"""
    return TELESCOPES.get(telescope_id)


def get_filter(filter_id: str) -> Optional[FilterSpec]:
    """Get filter by ID"""
    return FILTERS.get(filter_id)


def calculate_setup_stats(telescope_id: str, camera_id: str) -> dict:
    """
    Calculate imaging setup statistics
    
    Args:
        telescope_id: Telescope ID
        camera_id: Camera ID
        
    Returns:
        Dictionary with FOV, pixel scale, resolution, etc.
    """
    from imaging.camera import get_camera
    
    telescope = get_telescope(telescope_id)
    camera_spec = get_camera(camera_id).spec if camera_id else None
    
    if not telescope or not camera_spec:
        return {}
    
    # Sensor size in mm
    sensor_w_mm = camera_spec.pixel_size_um * camera_spec.resolution[0] / 1000.0
    sensor_h_mm = camera_spec.pixel_size_um * camera_spec.resolution[1] / 1000.0
    
    # FOV
    fov_w, fov_h = telescope.field_of_view(sensor_w_mm, sensor_h_mm)
    
    # Pixel scale
    pixel_scale = telescope.pixel_scale(camera_spec.pixel_size_um)
    
    # Resolution (arcsec)
    # Theoretical: 1.22 * lambda / D (assume 550nm)
    theoretical_res = 138000 / telescope.aperture_mm  # arcsec
    
    # Sampling (Nyquist)
    nyquist_sampling = theoretical_res / pixel_scale
    
    return {
        'fov_width_deg': fov_w,
        'fov_height_deg': fov_h,
        'fov_width_arcmin': fov_w * 60,
        'fov_height_arcmin': fov_h * 60,
        'pixel_scale_arcsec': pixel_scale,
        'theoretical_resolution_arcsec': theoretical_res,
        'nyquist_sampling': nyquist_sampling,
        'focal_length_mm': telescope.focal_length_mm,
        'focal_ratio': telescope.focal_ratio,
        'aperture_mm': telescope.aperture_mm,
    }
