"""
Universe module — 3D simulation space.

Usage:
    from universe import build_universe
    universe = build_universe()

    # Query
    dso = universe.get_dso()
    stars = universe.get_stars()
    obj = universe.get_by_uid("M42")
    nearby = universe.query_cone(ra=83.8, dec=-5.4, radius_deg=5.0)
"""

from .space_object import (
    SpaceObject,
    ObjectClass,
    ObjectSubtype,
    ObjectOrigin,
    DiscoveryState,
)
from .universe import Universe, build_universe

__all__ = [
    "SpaceObject",
    "ObjectClass",
    "ObjectSubtype",
    "ObjectOrigin",
    "DiscoveryState",
    "Universe",
    "build_universe",
]

# Solar system bodies
from .orbital_body import (
    OrbitalBody,
    OrbitalElements,
    build_solar_system,
    datetime_to_jd,
    jd_to_centuries,
    equatorial_to_altaz,
)

from .planet_physics import (
    apparent_magnitude,
    apparent_diameter_arcsec,
    saturn_ring_inclination_B,
    get_planet_physical_data,
    illuminated_fraction,
)

from .minor_bodies import (
    MinorBody,
    MinorBodyElements,
    CometBody,
    MinorBodyCatalog,
    build_minor_bodies,
)

__all__ += [
    "OrbitalBody",
    "OrbitalElements",
    "build_solar_system",
    "datetime_to_jd",
    "jd_to_centuries",
    "equatorial_to_altaz",
    # planet_physics
    "apparent_magnitude",
    "apparent_diameter_arcsec",
    "saturn_ring_inclination_B",
    "get_planet_physical_data",
    "illuminated_fraction",
    # minor_bodies
    "MinorBody",
    "MinorBodyElements",
    "CometBody",
    "MinorBodyCatalog",
    "build_minor_bodies",
]
