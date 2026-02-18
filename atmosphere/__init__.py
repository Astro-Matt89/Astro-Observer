"""
Atmosphere package — physical atmospheric simulation.

Main exports:
    AtmosphericModel   — compute atmospheric state for datetime + location
    AtmosphericState   — result: sky background, extinction, seeing, phase
    ObserverLocation   — geographic + sky quality parameters
    DayPhase           — enum: NIGHT / ASTRO_TWILIGHT / ... / DAY
    WeatherSystem      — procedural weather generator (Sprint 14a)
    WeatherCondition   — weather state enum (Sprint 14a)
    NightWeather       — per-night weather data (Sprint 14a)
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
from .weather import WeatherSystem, WeatherCondition, NightWeather

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
    "WeatherSystem",
    "WeatherCondition",
    "NightWeather",
]
