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
airmass_gradient
    Multiplicative brightness boost due to airmass along the line of sight,
    as a function of normalised zenith distance.
sky_noise_pattern
    Deterministic spatial noise texture for sky background, parameterised in
    sky angular coordinates rather than pixel coordinates.
"""

from __future__ import annotations

import math
from typing import Tuple, Union

import numpy as np


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


def airmass_gradient(
    zenith_distance_norm: Union[float, np.ndarray],
    solar_alt_deg: float = -90.0,
) -> Union[float, np.ndarray]:
    """
    Multiplicative sky-brightness boost due to airmass along the line of sight.

    Horizon pixels see more atmosphere than zenith pixels, so the sky appears
    brighter near the horizon.  The boost factor depends on the solar altitude
    (more scattered light during twilight and day).

    This is the *physical* brightness enhancement extracted from the
    ``alt_gradient`` calculation in ``build_allsky_background()``.

    Parameters
    ----------
    zenith_distance_norm : float or array
        Normalised zenith distance: 0.0 = zenith, 1.0 = horizon.
        Values are clamped to [0, 1].
    solar_alt_deg : float
        Solar altitude in degrees.  Controls the horizon-boost factor:

        * deep / nautical night (< −12°): 20 % horizon brightening
        * twilight (−12° to 0°): 45 % horizon brightening
        * day (≥ 0°): 80 % horizon brightening

    Returns
    -------
    float or numpy array
        Multiplicative gradient ≥ 1.0.  Multiply base sky flux by this
        value to apply the airmass horizon brightening.
    """
    if solar_alt_deg < -12.0:
        horizon_boost = 1.20
    elif solar_alt_deg < 0.0:
        horizon_boost = 1.45
    else:
        horizon_boost = 1.80

    r = np.clip(np.asarray(zenith_distance_norm, dtype=np.float64), 0.0, 1.0)
    gradient = 1.0 + r * (horizon_boost - 1.0)

    # Return scalar when input was scalar
    if np.ndim(zenith_distance_norm) == 0:
        return float(gradient)
    return gradient.astype(np.float32)


# Theoretical RMS of the three-octave sinusoidal noise sum used in
# sky_noise_pattern().  Pre-computed to allow normalisation for scalar inputs:
#   RMS ≈ sqrt(0.5 * (1.0² + 0.4² + 0.2²)) ≈ 0.7746
_NOISE_RMS: float = math.sqrt(0.5 * (1.0**2 + 0.4**2 + 0.2**2))


def sky_noise_pattern(
    alt_deg: Union[float, np.ndarray],
    az_deg: Union[float, np.ndarray],
    seed: int = 0,
) -> Union[float, np.ndarray]:
    """
    Deterministic spatial noise texture for sky background brightness.

    Produces a multi-octave sinusoidal noise field in (alt, az) sky
    coordinates.  The spatial frequencies are calibrated to match the
    pixel-space noise in ``build_allsky_background()`` at a reference
    render size of 512 × 512 pixels.

    The input coordinates are projected onto an all-sky equidistant-azimuthal
    plane (the same projection used by the allsky renderer), so the noise
    pattern is geometrically consistent with rendered images.

    Parameters
    ----------
    alt_deg : float or array
        Altitude above the horizon in degrees.
    az_deg : float or array
        Azimuth in degrees (north-through-east convention).
    seed : int
        Integer seed for a deterministic phase offset.  Different seeds
        produce independent, uncorrelated noise realisations.

    Returns
    -------
    float or numpy array
        Noise values with zero mean (for array inputs) and RMS ≈ 0.5.
        Multiply by ``noise_scale = 0.025 * max(bg_b, 0.1)`` to obtain
        the same absolute noise level as the allsky renderer.
    """
    alt_a = np.asarray(alt_deg, dtype=np.float64)
    az_a = np.asarray(az_deg, dtype=np.float64)

    # Clamp altitude to physical range before computing zenith distance
    alt_a = np.clip(alt_a, -90.0, 90.0)

    # Convert to all-sky Cartesian coordinates.
    # The equidistant-azimuthal projection maps zenith distance linearly to
    # radius.  At a reference size of 512 px, radius ≈ 256 px, so:
    #   u = zenith_dist / 90° × 256  ∈ [-256, 256]
    #   v = zenith_dist / 90° × 256  ∈ [-256, 256]
    # This gives the same numeric range as the pixel coordinates in the
    # renderer (xx, yy ∈ [0, 512]), ensuring matching spatial frequencies.
    zenith_dist = np.clip(90.0 - alt_a, 0.0, 90.0)
    az_r = np.radians(az_a)
    scale = zenith_dist / 90.0 * 256.0
    u = scale * np.sin(az_r)
    v = -scale * np.cos(az_r)

    # Deterministic phase offset from seed
    phase_offset = float(seed) * 37.13

    # Three-octave sinusoidal noise — same spatial frequencies as the renderer
    nx = np.sin(u * 0.012 + 1.3 + phase_offset) * np.cos(v * 0.015 + 0.7)
    nx = nx + 0.4 * np.sin(u * 0.031 - 2.1) * np.cos(v * 0.027 + 1.8)
    nx = nx + 0.2 * np.sin(u * 0.058 + 0.4) * np.cos(v * 0.063 - 1.2)

    # Normalise to zero mean and RMS ≈ 0.5.  For arrays with more than one
    # element use the empirical statistics; for scalar inputs use the
    # theoretical values (RMS of the three-octave sum, mean ≈ 0).
    if nx.ndim > 0 and nx.size > 1:
        nx = nx - np.mean(nx)
        std_val = float(np.std(nx))
    else:
        std_val = _NOISE_RMS
    nx = nx / (std_val + 1e-9) * 0.5

    if np.ndim(alt_deg) == 0 and np.ndim(az_deg) == 0:
        return float(nx)
    return nx.astype(np.float32)
