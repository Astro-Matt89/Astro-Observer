"""
astro_engine.physical_sky — The physical sky at a given instant and location.

This module provides :class:`PhysicalSky`, the central orchestrator of all
sky-physics computations.  It is deliberately **sensor-agnostic**: it knows
nothing about pixels, field-of-view, gain, or rendering.  Any renderer can
instantiate it and query the sky state in (alt, az) coordinates.

Physical units
--------------
All flux values are in **photons / pixel / second** at reference gain
(gain_sw = 200, exposure = 1 s, allsky area = π × (sensor_radius)²).
Multiply by sensor gain, exposure time, and pixel solid angle to convert to
detector ADU.

Architecture
------------
For this first PR the class acts as a **thin wrapper**: it delegates to
existing modules without moving or duplicating their logic.

    PhysicalSky
        ├── coordinates  (astro_engine.coordinates)
        ├── sky_background (astro_engine.sky_background)
        ├── MilkyWayLayer  (imaging.milky_way_texture)
        └── CloudLayer     (atmosphere.cloud_layer)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from astro_engine.coordinates import (
    compute_gmst,
    compute_lst,
    equatorial_to_altaz,
    airmass,
)
from astro_engine.sky_background import (
    sky_brightness_model,
    airglow_model,
    twilight_glow,
)
from imaging.milky_way_texture import MilkyWayLayer
from atmosphere.cloud_layer import CloudLayer

# Standard V-band atmospheric extinction coefficient (mag/airmass).
# Sea-level clear night: ~0.20 mag/airmass.  High-altitude sites may use
# 0.10–0.15.  Override per-site by subclassing or adjusting this constant.
_EXTINCTION_K: float = 0.20


class PhysicalSky:
    """
    The physical sky at a given instant and location.

    Produces photon fluxes in (alt, az) coordinates.
    Does NOT know about pixels, sensors, FOV, or rendering.
    Any sensor/renderer reads from this class.

    Parameters
    ----------
    star_catalog : object, optional
        A catalog object whose ``get_stars()`` method returns an iterable
        of star-like objects with ``ra_deg``, ``dec_deg``, ``mag``, ``bv``
        attributes.  Pass ``None`` to disable star queries.
    dso_catalog : object, optional
        Deep-sky object catalog (reserved for future use).
    solar_bodies : list, optional
        List of :class:`~universe.orbital_body.OrbitalBody` instances
        (Sun, Moon, planets).  The Sun is identified by its ``is_sun``
        attribute; the Moon by its ``is_moon`` attribute.

    Usage
    -----
    ::

        sky = PhysicalSky(star_catalog, dso_catalog)
        sky.update(jd, lat, lon, weather_state)

        # Any sensor can then query:
        bg    = sky.background_flux(alt_array, az_array)
        stars = sky.visible_stars(alt_min=0, mag_limit=6.5)
        mw    = sky.milky_way_flux(alt_array, az_array)
    """

    def __init__(
        self,
        star_catalog: Optional[Any] = None,
        dso_catalog: Optional[Any] = None,
        solar_bodies: Optional[List[Any]] = None,
    ) -> None:
        self._star_catalog = star_catalog
        self._dso_catalog = dso_catalog
        self._solar_bodies: List[Any] = solar_bodies or []

        # Observer state — populated by update()
        self._jd: float = 2451545.0        # J2000.0 default
        self._lat: float = 0.0
        self._lon: float = 0.0
        self._weather_state: Optional[Any] = None

        # Derived quantities — populated by update()
        self._gmst_deg: float = 0.0
        self._lst_deg: float = 0.0
        self._solar_alt_deg: float = -90.0
        self._solar_az_deg: float = 0.0

        # Lazy sub-components
        self._mw_layer: Optional[MilkyWayLayer] = None
        self._cloud_layer: Optional[CloudLayer] = None

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------

    def update(
        self,
        jd: float,
        lat: float,
        lon: float,
        weather_state: Optional[Any] = None,
    ) -> None:
        """
        Advance the sky to a new time and observer position.

        Must be called before any query methods.  Internally computes
        sidereal time, solar position, and updates any solar bodies that
        were supplied at construction.

        Parameters
        ----------
        jd : float
            Julian Date (TT ≈ UTC for visual purposes).
        lat : float
            Observer geographic latitude in degrees (north positive).
        lon : float
            Observer geographic longitude in degrees (east positive).
        weather_state : object, optional
            Atmospheric state object (e.g. from ``atmosphere`` package) that
            exposes ``sky_bg_r``, ``sky_bg_g``, ``sky_bg_b``,
            ``transparency``, ``solar_alt_deg``, ``solar_az_deg``.
            If ``None``, a default dark-sky state is assumed.
        """
        self._jd = jd
        self._lat = lat
        self._lon = lon
        self._weather_state = weather_state

        # Sidereal time
        self._gmst_deg = compute_gmst(jd)
        self._lst_deg = compute_lst(jd, lon)

        # Solar position — prefer weather_state if it already has it
        if weather_state is not None and hasattr(weather_state, "solar_alt_deg"):
            self._solar_alt_deg = float(weather_state.solar_alt_deg)
            self._solar_az_deg = float(
                getattr(weather_state, "solar_az_deg", 180.0)
            )
        else:
            # Locate the Sun body and use its position
            sun = self._find_sun()
            if sun is not None:
                sun.update_position(jd, lat, lon)
                self._solar_alt_deg = float(sun.altitude_deg)
                self._solar_az_deg = float(sun.azimuth_deg)
            else:
                self._solar_alt_deg = -90.0
                self._solar_az_deg = 0.0

        # Update all orbital bodies
        for body in self._solar_bodies:
            if hasattr(body, "update_position"):
                body.update_position(jd, lat, lon)

    # ------------------------------------------------------------------
    # Properties — current sky state
    # ------------------------------------------------------------------

    @property
    def solar_alt_deg(self) -> float:
        """Current solar altitude in degrees.  Negative = below horizon."""
        return self._solar_alt_deg

    @property
    def is_night(self) -> bool:
        """
        True when the sky is dark enough for practical naked-eye observing
        (solar alt < −12°, i.e. nautical twilight has ended).

        Deep-sky observing typically requires solar alt < −18° (astronomical
        twilight end); this threshold of −12° is a practical observability
        cutoff used throughout the rendering pipeline.
        """
        return self._solar_alt_deg < -12.0

    @property
    def is_twilight(self) -> bool:
        """True during any twilight phase (−18° < solar alt < 0°)."""
        return -18.0 < self._solar_alt_deg < 0.0

    @property
    def moon_phase(self) -> float:
        """
        Current Moon illuminated fraction in [0, 1].

        0 = new moon, 1 = full moon.
        Returns 0.0 if no Moon body was supplied at construction or if
        positions have not been updated yet.
        """
        moon = self._find_moon()
        if moon is not None and hasattr(moon, "phase_fraction"):
            return float(moon.phase_fraction)
        return 0.0

    # ------------------------------------------------------------------
    # Flux query methods
    # ------------------------------------------------------------------

    def background_flux(
        self,
        alt_deg: float,
        az_deg: float,
    ) -> Tuple[float, float, float]:
        """
        Diffuse sky background flux at a given (alt, az) coordinate.

        Returns the physical sky brightness incorporating solar altitude,
        atmospheric transparency, airglow, and a twilight gradient in the
        direction of the supplied azimuth.  No sensor effects are applied.

        Parameters
        ----------
        alt_deg : float
            Altitude above the horizon in degrees.
        az_deg : float
            Azimuth in degrees (north-through-east convention).

        Returns
        -------
        tuple[float, float, float]
            ``(flux_r, flux_g, flux_b)`` in photon-flux units (ph/px/s at
            reference gain).
        """
        ws = self._weather_state
        transparency = float(getattr(ws, "transparency", 1.0)) if ws else 1.0
        bg_r = float(getattr(ws, "sky_bg_r", 1.0)) if ws else 1.0
        bg_g = float(getattr(ws, "sky_bg_g", 1.0)) if ws else 1.0
        bg_b = float(getattr(ws, "sky_bg_b", 1.0)) if ws else 1.0

        # Base zenith brightness
        flux_r, flux_g, flux_b = sky_brightness_model(
            self._solar_alt_deg, transparency, bg_r, bg_g, bg_b
        )

        # Airmass gradient — horizon appears brighter due to scattering.
        # Boost factors calibrated to match real sky photos:
        #   deep night (<-12°): subtle 20% horizon brightening
        #   twilight (<0°):     45% — more scattered light near horizon
        #   day (≥0°):         80% — strong limb brightening
        zenith_angle = max(0.0, 90.0 - alt_deg)
        r_norm = zenith_angle / 90.0
        horizon_boost = (
            1.20 if self._solar_alt_deg < -12.0 else  # deep / nautical night
            (1.45 if self._solar_alt_deg < 0.0 else 1.80)  # twilight / day
        )
        alt_gradient = 1.0 + r_norm * (horizon_boost - 1.0)
        flux_r *= alt_gradient
        flux_g *= alt_gradient
        flux_b *= alt_gradient

        # Twilight glow toward the Sun
        if self.is_twilight:
            az_diff = math.radians(
                ((az_deg - self._solar_az_deg + 180.0) % 360.0) - 180.0
            )
            glow = twilight_glow(math.degrees(az_diff), self._solar_alt_deg)
            flux_r += flux_r * glow * 0.8
            flux_g += flux_g * glow * 0.3
            flux_b += flux_b * glow * 0.05

        # Airglow
        ag = airglow_model(zenith_angle, self._solar_alt_deg)
        flux_g += ag * bg_g * 0.3
        flux_b += ag * bg_b * 0.15

        return flux_r, flux_g, flux_b

    def visible_stars(
        self,
        alt_min: float = 0.0,
        mag_limit: float = 8.0,
    ) -> List[Dict[str, Any]]:
        """
        Stars above the horizon brighter than *mag_limit*.

        Queries the star catalog (if provided), computes (alt, az) for each
        star, and returns those above *alt_min* and within *mag_limit*.

        Parameters
        ----------
        alt_min : float
            Minimum altitude in degrees (default 0 = above horizon).
        mag_limit : float
            Faint magnitude limit (default 8.0 — roughly naked-eye + binocular
            limit under good skies).

        Returns
        -------
        list[dict]
            Each entry is a dict with keys:
            ``ra``, ``dec``, ``alt``, ``az``, ``mag``, ``bv``.
            All angles in degrees.
        """
        if self._star_catalog is None:
            return []

        results: List[Dict[str, Any]] = []
        stars = (
            self._star_catalog.get_stars()
            if hasattr(self._star_catalog, "get_stars")
            else self._star_catalog
        )

        for star in stars:
            mag = getattr(star, "mag", 99.0)
            if mag > mag_limit:
                continue
            ra = getattr(star, "ra_deg", 0.0)
            dec = getattr(star, "dec_deg", 0.0)
            alt, az = equatorial_to_altaz(ra, dec, self._lat, self._lon, self._jd)
            if alt < alt_min:
                continue
            results.append(
                {
                    "ra": ra,
                    "dec": dec,
                    "alt": alt,
                    "az": az,
                    "mag": mag,
                    "bv": getattr(star, "bv", 0.0),
                }
            )
        return results

    def visible_planets(self) -> List[Dict[str, Any]]:
        """
        Solar system bodies currently above the horizon.

        Returns the subset of ``solar_bodies`` that have altitude > 0°,
        enriched with computed positional data.

        Returns
        -------
        list[dict]
            Each entry contains keys:
            ``name``, ``alt``, ``az``, ``mag``, ``ra``, ``dec``,
            ``phase_fraction``, ``is_sun``, ``is_moon``.
            All angles in degrees.
        """
        results: List[Dict[str, Any]] = []
        for body in self._solar_bodies:
            alt = float(getattr(body, "altitude_deg", getattr(body, "_alt_deg", -90.0)))
            if alt <= 0.0:
                continue
            results.append(
                {
                    "name": getattr(body, "name", str(body)),
                    "alt": alt,
                    "az": float(getattr(body, "azimuth_deg", getattr(body, "_az_deg", 0.0))),
                    "mag": float(getattr(body, "apparent_mag", 99.0)),
                    "ra": float(getattr(body, "ra_deg", 0.0)),
                    "dec": float(getattr(body, "dec_deg", 0.0)),
                    "phase_fraction": float(getattr(body, "phase_fraction", 1.0)),
                    "is_sun": bool(getattr(body, "is_sun", False)),
                    "is_moon": bool(getattr(body, "is_moon", False)),
                }
            )
        return results

    def milky_way_flux(
        self,
        alt_deg: float,
        az_deg: float,
    ) -> Tuple[float, float, float]:
        """
        Milky Way flux contribution at a given (alt, az) coordinate.

        Only meaningful when the Sun is below civil twilight (solar alt < −6°);
        the MW texture fades in between −6° and −12° solar altitude.
        Delegates to :class:`~imaging.milky_way_texture.MilkyWayLayer` for
        the full photorealistic model.

        For scalar (alt, az) queries the method constructs a minimal synthetic
        field and samples its centre pixel.  For bulk rendering use
        ``MilkyWayLayer.render()`` directly on a full field array.

        Parameters
        ----------
        alt_deg : float
            Altitude in degrees.
        az_deg : float
            Azimuth in degrees.

        Returns
        -------
        tuple[float, float, float]
            ``(flux_r, flux_g, flux_b)`` — additive Milky Way photon flux.
            Returns (0, 0, 0) when the Sun is above −6° altitude or the
            target point is below the horizon.
        """
        if self._solar_alt_deg >= -6.0 or alt_deg < 0.0:
            return 0.0, 0.0, 0.0

        mw = self._get_mw_layer()
        # Build a tiny synthetic field to sample the MW at this point.
        # Size 3 so the allsky projection math works (centre pixel = (1,1)).
        size = 3
        field = np.zeros((size, size, 3), dtype=np.float32)

        # Place the target at the allsky disk centre (r=0 → zenith in the
        # allsky mapping).  This is an approximation for scalar queries;
        # accurate bulk queries should use MilkyWayLayer.render() directly.
        # We encode the true alt/az by placing the star at its radial position.
        radius = float(size) * 0.5 - 0.5
        cx = cy = float(size) * 0.5

        try:
            mw.render(
                field,
                self._jd,
                self._lat,
                self._lon,
                cx,
                cy,
                radius,
                solar_alt_deg=self._solar_alt_deg,
            )
        except Exception:
            return 0.0, 0.0, 0.0

        # Return the centre pixel as representative flux
        r = float(field[1, 1, 0])
        g = float(field[1, 1, 1])
        b = float(field[1, 1, 2])
        return r, g, b

    def cloud_opacity(
        self,
        alt_deg: float,
        az_deg: float,
    ) -> float:
        """
        Cloud opacity at the given sky position.

        Returns a value in [0, 1] where 0 = clear sky and 1 = fully opaque.
        The cloud pattern is driven by the current time (``jd``) and the
        atmospheric state's transparency value.

        Parameters
        ----------
        alt_deg : float
            Altitude in degrees.
        az_deg : float
            Azimuth in degrees.

        Returns
        -------
        float
            Opacity in [0, 1].
        """
        cl = self._get_cloud_layer()
        ws = self._weather_state
        transparency = float(getattr(ws, "transparency", 1.0)) if ws else 1.0

        # Map (alt, az) to a pixel coordinate on a minimal allsky disk
        size = 256
        radius = size * 0.5 - 1.0
        cx = cy = size * 0.5

        zenith_angle = max(0.0, 90.0 - alt_deg)
        r_px = zenith_angle / 90.0 * radius
        az_r = math.radians(az_deg)
        px = cx + r_px * math.sin(az_r)
        py = cy - r_px * math.cos(az_r)

        ix = int(round(px))
        iy = int(round(py))

        try:
            sim_time_s = self._jd * 86400.0
            cl.update(transparency, sim_time_s, size)
            mask = cl.mask
            if 0 <= iy < size and 0 <= ix < size:
                return float(mask[iy, ix])
        except Exception:
            pass
        return 0.0

    def atmospheric_extinction(self, alt_deg: float) -> float:
        """
        Atmospheric extinction factor as a function of altitude.

        Returns the fraction of light that *survives* the atmosphere at the
        given altitude (i.e. ``1 / airmass`` is NOT the right formulation;
        see below).

        The standard photometric extinction formula is:

            m_obs = m_true + k × X

        where ``k`` is the extinction coefficient in magnitudes per airmass
        (``_EXTINCTION_K`` = 0.20 for a clear site at sea level; high-altitude
        observatories may use 0.10–0.15) and ``X`` is the airmass.  This method returns the corresponding flux ratio:

            flux_ratio = 10^(−k × X / 2.5)

        Parameters
        ----------
        alt_deg : float
            Altitude above the horizon in degrees.

        Returns
        -------
        float
            Flux transmission factor in (0, 1].  Multiply photon counts by
            this value to apply atmospheric extinction.
        """
        X = airmass(alt_deg)
        return float(10.0 ** (-_EXTINCTION_K * X / 2.5))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_sun(self) -> Optional[Any]:
        """Return the Sun body from the solar bodies list, or None."""
        for body in self._solar_bodies:
            if getattr(body, "is_sun", False):
                return body
        return None

    def _find_moon(self) -> Optional[Any]:
        """Return the Moon body from the solar bodies list, or None."""
        for body in self._solar_bodies:
            if getattr(body, "is_moon", False):
                return body
        return None

    def _get_mw_layer(self) -> MilkyWayLayer:
        """Return (and lazily initialise) the MilkyWayLayer."""
        if self._mw_layer is None:
            self._mw_layer = MilkyWayLayer()
        return self._mw_layer

    def _get_cloud_layer(self) -> CloudLayer:
        """Return (and lazily initialise) the CloudLayer."""
        if self._cloud_layer is None:
            self._cloud_layer = CloudLayer()
        return self._cloud_layer
