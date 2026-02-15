"""
Atmosphere package — physical atmospheric simulation.

Main exports:
    AtmosphericModel   — compute atmospheric state for datetime + location
    AtmosphericState   — result: sky background, extinction, seeing, phase
    ObserverLocation   — geographic + sky quality parameters
    DayPhase           — enum: NIGHT / ASTRO_TWILIGHT / ... / DAY
"""
from .day_phase import DayPhase, get_phase_properties, PHASE_PROPERTIES
from .atmospheric_model import (
    AtmosphericModel,
    AtmosphericState,
    ObserverLocation,
    extinction_mag,
    airmass,
    sky_background_rgb,
    seeing_fwhm_arcsec,
    refraction_correction,
)

__all__ = [
    "DayPhase",
    "get_phase_properties",
    "PHASE_PROPERTIES",
    "AtmosphericModel",
    "AtmosphericState",
    "ObserverLocation",
    "extinction_mag",
    "airmass",
    "sky_background_rgb",
    "seeing_fwhm_arcsec",
    "refraction_correction",
]
