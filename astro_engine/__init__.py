"""
astro_engine — Physical sky engine for Astro-Observer.

This package provides a sensor-independent model of the physical sky:
photon fluxes, star visibility, solar system body positions, atmospheric
effects, and Milky Way contributions — all in (alt, az) coordinates.

The key principle is **one physical sky, many sensors**.  Any renderer
(allsky camera, naked-eye view, binoculars, telescope) reads from the
same :class:`PhysicalSky` instance and applies its own sensor
characteristics (FOV, gain, pixel scale) independently.

Typical usage::

    from astro_engine import PhysicalSky

    sky = PhysicalSky(star_catalog, dso_catalog)
    sky.update(jd, lat, lon, weather_state)

    bg    = sky.background_flux(alt, az)
    stars = sky.visible_stars(alt_min=0, mag_limit=6.5)

Public API
----------
PhysicalSky
    Central orchestrator class.
compute_gmst
    GMST in degrees for a Julian Date.
compute_lst
    LST in degrees for a Julian Date and longitude.
airmass
    Airmass factor as a function of altitude.
"""

from astro_engine.physical_sky import PhysicalSky
from astro_engine.coordinates import compute_gmst, compute_lst, airmass

__all__ = [
    "PhysicalSky",
    "compute_gmst",
    "compute_lst",
    "airmass",
]
