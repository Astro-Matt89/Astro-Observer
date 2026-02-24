"""
astro_engine.sky_background — Physical models for diffuse sky brightness.

All functions return RGB values in **photon-flux units** (photons / pixel / second
at reference gain).  They represent the *physical* sky emission — no sensor
characteristics (pixel scale, gain, read noise) are applied here.

The models are extracted conceptually from the ``build_allsky_background``
logic in ``imaging/allsky_renderer.py`` and expressed as pure physical
functions of altitude and solar position.

Functions
---------
sky_brightness_model
    Base sky brightness (R, G, B) as a function of solar altitude and
    atmospheric transparency.
airglow_model
    Airglow contribution as a function of zenith angle and solar depression.
twilight_glow
    Twilight gradient brightness as a function of angular distance from the
    Sun and solar altitude.
"""

from __future__ import annotations

import math
from typing import Tuple


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sky_scale(solar_alt_deg: float) -> float:
    """
    Adaptive scale factor mapping solar altitude to a sky brightness multiplier.

    Calibrated so that the post-scale blue channel corresponds approximately to:

    * deep night (< −12°): ~5 ph/px
    * civil dusk (0°): ~25 ph/px
    * morning (+15°): ~140 ph/px
    * noon: ~500 ph/px
    """
    if solar_alt_deg < -12.0:
        return 0.065
    elif solar_alt_deg < 0.0:
        t = (solar_alt_deg + 12.0) / 12.0
        return 0.065 * (1.0 - t) + 0.008 * t
    elif solar_alt_deg < 15.0:
        t = solar_alt_deg / 15.0
        return 0.008 * (1.0 - t) + 0.001 * t
    else:
        return max(0.0005, 0.001 * (1.0 - (solar_alt_deg - 15.0) / 75.0))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sky_brightness_model(
    solar_alt_deg: float,
    transparency: float = 1.0,
    sky_bg_r: float = 1.0,
    sky_bg_g: float = 1.0,
    sky_bg_b: float = 1.0,
) -> Tuple[float, float, float]:
    """
    Base sky brightness at the zenith for given solar altitude and transparency.

    This is the *physical* sky brightness without any sensor gain, exposure
    time, or pixel-projection effects applied.  It encapsulates the
    day/night/twilight transition and atmospheric transparency scaling.

    Parameters
    ----------
    solar_alt_deg : float
        Altitude of the Sun in degrees.  Negative values indicate night / twilight.
    transparency : float
        Atmospheric transparency fraction in [0, 1].  1.0 = perfectly clear.
    sky_bg_r, sky_bg_g, sky_bg_b : float
        Base sky colour coefficients from an atmospheric state model
        (e.g. ``AtmosphericModel.sky_bg_*``).  Defaults to 1.0 (unit flux).

    Returns
    -------
    tuple[float, float, float]
        ``(flux_r, flux_g, flux_b)`` — photon-flux contributions per channel.
        Multiply by exposure time and sensor gain to convert to ADU.
    """
    scale = _sky_scale(solar_alt_deg)
    t = max(0.0, min(1.0, transparency))

    if solar_alt_deg > -30.0:
        flux_r = sky_bg_r * scale * t
        flux_g = sky_bg_g * scale * t
        flux_b = sky_bg_b * scale * t
    else:
        # Deep night / sensor-limited floor
        flux_r = 0.10 * t
        flux_g = 0.20 * t
        flux_b = 0.60 * t

    return flux_r, flux_g, flux_b


def airglow_model(
    zenith_angle_deg: float,
    solar_alt_deg: float,
) -> float:
    """
    Airglow brightness contribution at a given zenith angle.

    Airglow is only significant during astronomical night (solar altitude
    below −18°).  It forms a faint emission band at roughly 89° zenith angle
    (near the horizon), modelled here as a Gaussian ring.

    Parameters
    ----------
    zenith_angle_deg : float
        Zenith angle in degrees (0 = zenith, 90 = horizon).
    solar_alt_deg : float
        Altitude of the Sun in degrees.

    Returns
    -------
    float
        Fractional airglow intensity in [0, ~0.55].  Multiply by base sky
        flux to obtain the physical contribution.
    """
    if solar_alt_deg >= -18.0:
        return 0.0
    # Gaussian centred on zenith_angle = 89° (r_norm ≈ 0.89 in allsky coords)
    # Map zenith angle to normalised allsky radius: r_norm = zenith_angle / 90
    r_norm = max(0.0, min(1.0, zenith_angle_deg / 90.0))
    return float(math.exp(-((r_norm - 0.89) / 0.08) ** 2) * 0.55)


def twilight_glow(
    angle_from_sun_deg: float,
    solar_alt_deg: float,
) -> float:
    """
    Twilight glow intensity as a function of angular distance from the Sun.

    This represents the scattered sunlight that illuminates the sky during
    civil and nautical twilight (−18° < solar alt < 0°).

    Parameters
    ----------
    angle_from_sun_deg : float
        Angular distance from the Sun along the horizon circle, in degrees.
        0° means directly toward the Sun's azimuth.
    solar_alt_deg : float
        Altitude of the Sun in degrees.

    Returns
    -------
    float
        Glow intensity factor in [0, ~1].  The caller should scale this by
        the base sky flux for the appropriate channel (stronger in red).
    """
    if solar_alt_deg <= -18.0 or solar_alt_deg >= 0.0:
        return 0.0

    glow_str = ((solar_alt_deg + 18.0) / 18.0) ** 1.5
    angle_r = math.radians(angle_from_sun_deg)
    return float(math.exp(-(angle_r ** 2) / 0.5) * glow_str)
