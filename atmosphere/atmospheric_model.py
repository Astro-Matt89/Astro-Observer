"""
AtmosphericModel — simulazione fisica dell'atmosfera terrestre.

Calcola per ogni frame di imaging:
  1. DayPhase     : fase della giornata (da posizione Sole)
  2. sky_background_photons(H,W) : mappa 2D del fondo cielo (per SkyRenderer)
  3. extinction(alt_deg, bv)     : magnitudini perse per airmass + B-V
  4. seeing_fwhm_arcsec          : FWHM del seeing (varia nel tempo)
  5. moon_sky_glow               : contributo lunare al fondo

Architettura (pensata per il futuro):
  AtmosphericModel tiene un riferimento al SolarSystemCatalog.
  Quando Sun/Moon sono OrbitalBody nell'Universe, vengono cercati per UID.
  Fallback: calcolo interno se non ancora in Universe.

Fisica implementata:
  - Scattering di Rayleigh (fondo cielo blu in funzione di alt solare)
  - Estinzione Bouger-Lambert (airmass + k_ext per banda)
  - Sky glow lunare (Krisciunas & Schaefer 1991, semplificato)
  - Sky glow da inquinamento luminoso (modello radiale)
  - Seeing: modello Kolmogorov base + variazione temporale pseudo-casuale
  - Refrazione atmosferica (correzione altitudine apparente)
"""

from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple
from datetime import datetime, timezone

from .day_phase import DayPhase, get_phase_properties


# ---------------------------------------------------------------------------
# Extinction coefficients (magnitudes per unit airmass)
# ---------------------------------------------------------------------------

# Standard photometric extinction at sea level, good site
# (wavelength-dependent: shorter = more extinction)
_K_EXT = {
    'V':  0.12,   # visual (550nm)
    'B':  0.25,   # blue (440nm)
    'R':  0.07,   # red (640nm)
    'I':  0.04,   # infrared (800nm)
    'U':  0.50,   # UV (365nm)
}


def airmass(alt_deg: float) -> float:
    """
    Pickering (2002) airmass formula — accurate to horizon.
    Returns X (dimensionless), capped at 40 (horizon).
    """
    if alt_deg >= 89.9:
        return 1.0
    if alt_deg < 0.0:
        return 40.0
    # Pickering 2002
    denom = math.sin(math.radians(alt_deg + 244.0 / (165.0 + 47.0 * alt_deg**1.1)))
    return min(40.0, 1.0 / max(denom, 1e-6))


def extinction_mag(alt_deg: float, bv_color: float = 0.6,
                   altitude_m: float = 0.0) -> float:
    """
    Total atmospheric extinction in V magnitudes for a star at alt_deg
    with B-V color index.

    Args:
        alt_deg   : altitude above horizon (degrees)
        bv_color  : B-V index of star (0=blue, 1.5=red)
        altitude_m: observatory altitude in metres (reduces extinction)

    Returns:
        Delta_mag (positive = star appears fainter)
    """
    # Site altitude reduces column density
    pressure_factor = math.exp(-altitude_m / 8500.0)

    # Interpolate k_ext between B and V based on B-V color
    # Blue stars (bv<0) get more B extinction, red get more R
    t = max(0.0, min(1.0, (bv_color + 0.5) / 2.5))  # 0=blue, 1=red
    k = _K_EXT['B'] * (1-t) + _K_EXT['R'] * t
    k *= pressure_factor

    X = airmass(alt_deg)
    return k * X


# ---------------------------------------------------------------------------
# Rayleigh sky background
# ---------------------------------------------------------------------------

def rayleigh_sky_brightness(solar_alt_deg: float,
                              target_alt_deg: float = 45.0,
                              phase_sep_deg: float = 90.0) -> float:
    """
    Approximate sky surface brightness (V mag/arcsec²) due to Rayleigh
    scattering as a function of solar altitude and target position.

    Returns: sky_mag_arcsec2 (higher = darker; typical dark site ~21-22)
    """
    # Base brightness depends on solar altitude
    # Below -18°: fully dark (dark site ~21.5 mag/arcsec²)
    # At horizon: ~15 mag/arcsec²
    # Full day: ~3 mag/arcsec²

    if solar_alt_deg < -18.0:
        base = 21.5
    elif solar_alt_deg < 0.0:
        # Twilight: rapid brightening
        frac = (solar_alt_deg + 18.0) / 18.0   # 0 at -18°, 1 at 0°
        base = 21.5 - frac * 6.5
    else:
        # Daytime: from 15 at horizon to 3 at zenith
        frac = min(solar_alt_deg / 90.0, 1.0)
        base = 15.0 - frac * 12.0

    # Target altitude correction: sky is darker toward zenith
    alt_factor = math.cos(math.radians(max(0, 90 - target_alt_deg))) * 0.5
    # Phase angle correction: sky is brighter toward Sun
    phase_factor = math.cos(math.radians(min(phase_sep_deg, 180))) * 0.3

    return base + alt_factor + phase_factor


def sky_background_rgb(solar_alt_deg: float,
                        moon_alt_deg: float = -90.0,
                        moon_phase_fraction: float = 0.0,
                        light_pollution_sqm: float = 21.5,
                        altitude_m: float = 0.0) -> Tuple[float, float, float]:
    """
    Sky background RGB in units of photons/pixel/s (relative).

    Returns a 3-tuple (R, G, B) of background photon rates per render pixel.
    These values are added to the rendered sky BEFORE camera noise.

    The values are NOT in mag/arcsec² — they're directly usable as
    sky_signal_photons in camera.capture_frame().

    Calibration reference:
        dark site, no moon: ~50 photons/s/pixel for 100mm/3.76µm setup
        full moon at zenith: ~500 photons/s/pixel
        twilight:            ~5000+ photons/s/pixel
    """
    phase = DayPhase.from_solar_altitude(solar_alt_deg)
    props = get_phase_properties(phase)

    # Base sky magnitude surface brightness
    sky_mag = rayleigh_sky_brightness(solar_alt_deg)

    # Light pollution offset (reduces sky darkness)
    lp_offset = max(0.0, light_pollution_sqm - sky_mag)
    sky_mag = min(sky_mag, light_pollution_sqm)

    # Moon contribution (Krisciunas & Schaefer 1991, simplified)
    moon_glow = 0.0
    if moon_alt_deg > -5.0 and moon_phase_fraction > 0.1:
        moon_base = -12.73 + 2.5 * math.log10(max(1e-9, moon_phase_fraction))
        moon_factor = max(0.0, math.sin(math.radians(max(0, moon_alt_deg))))
        moon_glow = moon_factor * 10 ** (-0.4 * (moon_base + 16.0))
        moon_glow = min(moon_glow, 200.0)

    # Convert mag/arcsec² → photon rate (relative, calibrated to ~50 ph/s dark)
    # Reference: dark site (21.5 mag/arcsec²) = 50 ph/pixel/s
    ref_mag = 21.5
    photon_rate = 50.0 * 10 ** (-0.4 * (sky_mag - ref_mag)) + moon_glow

    # Altitude amplification for turbulent column
    alt_factor = math.exp(-altitude_m / 8000.0)
    photon_rate *= alt_factor

    # Colour split using phase sky colour
    r_sky, g_sky, b_sky = props.sky_color_rgb

    # Normalize colour to sum=1
    total = max(r_sky + g_sky + b_sky, 1e-6)
    r_frac = r_sky / total
    g_frac = g_sky / total
    b_frac = b_sky / total

    # Scale by total photon rate
    # Night: predominantly blue (Rayleigh); twilight: orange/warm
    r = photon_rate * r_frac * 3.0   # 3 channels, each ~1/3
    g = photon_rate * g_frac * 3.0
    b = photon_rate * b_frac * 3.0

    return float(r), float(g), float(b)


# ---------------------------------------------------------------------------
# Seeing model
# ---------------------------------------------------------------------------

def seeing_fwhm_arcsec(base_seeing: float = 2.5,
                        time_s: float = 0.0,
                        seed: int = 0) -> float:
    """
    Seeing FWHM with pseudo-random temporal variation.

    Kolmogorov turbulence: seeing varies on timescales of minutes.
    Models a correlated random walk around base_seeing.

    Args:
        base_seeing: typical site seeing in arcsec
        time_s     : elapsed time in seconds (for temporal correlation)
        seed       : random seed for reproducibility (per-night)

    Returns:
        Instantaneous seeing FWHM in arcsec
    """
    import random
    rng = random.Random(seed + int(time_s / 300))   # changes every 5 min
    # Lognormal: seeing fluctuates ±50% around base
    sigma_log = 0.20
    variation = math.exp(rng.gauss(0, sigma_log))
    return max(0.5, base_seeing * variation)


# ---------------------------------------------------------------------------
# Atmospheric refraction
# ---------------------------------------------------------------------------

def refraction_correction(alt_deg: float) -> float:
    """
    Atmospheric refraction correction (Bennet 1982).
    Returns delta_alt in arcminutes (always positive, adds to apparent altitude).
    """
    if alt_deg > 85.0:
        return 0.0
    if alt_deg < -1.0:
        return 34.0 / 60.0   # approximate near horizon
    a = alt_deg + 10.3 / (alt_deg + 5.11)
    return 1.02 / (60.0 * math.tan(math.radians(a)))   # degrees


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

@dataclass
class ObserverLocation:
    """Geographic location of the observatory."""
    latitude_deg:  float = 45.0   # positive = North
    longitude_deg: float = 9.0    # positive = East (Italy default)
    altitude_m:    float = 200.0  # metres above sea level
    name:          str   = "Observatory"

    # Sky quality
    limiting_mag_zenith: float = 21.5  # sky quality in mag/arcsec² at zenith
    # Typical site seeing
    base_seeing_arcsec:  float = 2.5


@dataclass
class AtmosphericState:
    """Complete atmospheric state at a given moment."""
    jd:                  float
    datetime_utc:        datetime
    observer:            ObserverLocation

    solar_alt_deg:       float
    solar_az_deg:        float
    day_phase:           DayPhase

    moon_alt_deg:        float
    moon_az_deg:         float
    moon_phase_fraction: float

    seeing_fwhm_arcsec:  float

    # Sky background RGB photon rates (per pixel per second)
    sky_bg_r:            float
    sky_bg_g:            float
    sky_bg_b:            float

    # Extinction at zenith (mag)
    extinction_zenith_v: float

    @property
    def imaging_allowed(self) -> bool:
        return get_phase_properties(self.day_phase).imaging_allowed

    @property
    def sky_bg_rgb(self) -> Tuple[float, float, float]:
        return self.sky_bg_r, self.sky_bg_g, self.sky_bg_b

    @property
    def naked_eye_limit(self) -> float:
        return get_phase_properties(self.day_phase).naked_eye_limit

    def extinction_at(self, alt_deg: float, bv_color: float = 0.6) -> float:
        """Extinction magnitude loss for star at this altitude."""
        return extinction_mag(alt_deg, bv_color, self.observer.altitude_m)

    def sky_background_field(self, H: int, W: int,
                               exposure_s: float = 1.0) -> np.ndarray:
        """
        Build a (H, W, 3) float32 array of sky background photon counts
        for a single exposure of duration exposure_s.

        Includes:
          - Rayleigh gradient (faintly brighter toward zenith)
          - Airglow (subtle green tinge at horizon, only at night)
          - Vignette-like limb darkening
        """
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W/2.0, H/2.0
        # Normalized radial distance from centre (0=center, 1=corner)
        r = np.sqrt(((xx-cx)/cx)**2 + ((yy-cy)/cy)**2)

        # Base background per channel
        r_bg = self.sky_bg_r * exposure_s
        g_bg = self.sky_bg_g * exposure_s
        b_bg = self.sky_bg_b * exposure_s

        # Subtle Rayleigh gradient (centre slightly darker = toward zenith)
        gradient = 1.0 + 0.08 * r   # edges brighter (lower altitude)

        # Airglow: faint green tinge at night (OI 557.7nm)
        if self.day_phase == DayPhase.NIGHT:
            airglow_g = 3.0 * exposure_s * (0.5 + 0.5 * r)
            airglow_r = 1.0 * exposure_s * (0.5 + 0.5 * r)
        else:
            airglow_g = airglow_r = 0.0

        field = np.stack([
            np.full((H, W), r_bg, dtype=np.float32) * gradient + airglow_r,
            np.full((H, W), g_bg, dtype=np.float32) * gradient + airglow_g,
            np.full((H, W), b_bg, dtype=np.float32) * gradient,
        ], axis=-1)

        return np.clip(field, 0, None).astype(np.float32)


class AtmosphericModel:
    """
    Computes atmospheric conditions for a given observer and datetime.

    Usage:
        model = AtmosphericModel(observer)
        state = model.compute(datetime_utc, sun_body, moon_body)
        # sun_body / moon_body: OrbitalBody (or None for internal calc)

        # In SkyRenderer:
        sky_bg = state.sky_background_field(H, W, exp_s)
        ext    = state.extinction_at(star_alt, bv)
    """

    def __init__(self, observer: Optional[ObserverLocation] = None):
        self.observer = observer or ObserverLocation()
        self._seeing_seed = 42

    def compute(self, dt: datetime,
                sun_body=None,
                moon_body=None) -> AtmosphericState:
        """
        Compute full atmospheric state for datetime dt.

        sun_body / moon_body: OrbitalBody instances (optional).
        If None, positions are computed internally.
        """
        from universe.orbital_body import datetime_to_jd

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        jd = datetime_to_jd(dt)

        lat = self.observer.latitude_deg
        lon = self.observer.longitude_deg

        # Solar position
        if sun_body is not None:
            sun_body.update_position(jd, lat, lon)
            sol_alt = sun_body.altitude_deg
            sol_az  = sun_body.azimuth_deg
        else:
            # Internal quick calc
            sol_alt, sol_az = self._quick_solar_position(jd, lat, lon)

        phase = DayPhase.from_solar_altitude(sol_alt)

        # Lunar position
        if moon_body is not None:
            moon_body.update_position(jd, lat, lon)
            moon_alt    = moon_body.altitude_deg
            moon_az     = moon_body.azimuth_deg
            moon_phase  = moon_body.phase_fraction
        else:
            moon_alt, moon_az, moon_phase = -90.0, 0.0, 0.0

        # Sky background
        r_bg, g_bg, b_bg = sky_background_rgb(
            solar_alt_deg        = sol_alt,
            moon_alt_deg         = moon_alt,
            moon_phase_fraction  = moon_phase,
            light_pollution_sqm  = self.observer.limiting_mag_zenith,
            altitude_m           = self.observer.altitude_m,
        )

        # Seeing
        elapsed_s = (dt - datetime(2000,1,1,tzinfo=timezone.utc)).total_seconds()
        fwhm = seeing_fwhm_arcsec(
            self.observer.base_seeing_arcsec,
            time_s = elapsed_s,
            seed   = self._seeing_seed,
        )

        # Zenith extinction
        ext_z = extinction_mag(90.0, 0.6, self.observer.altitude_m)

        return AtmosphericState(
            jd                   = jd,
            datetime_utc         = dt,
            observer             = self.observer,
            solar_alt_deg        = sol_alt,
            solar_az_deg         = sol_az,
            day_phase            = phase,
            moon_alt_deg         = moon_alt,
            moon_az_deg          = moon_az,
            moon_phase_fraction  = moon_phase,
            seeing_fwhm_arcsec   = fwhm,
            sky_bg_r             = r_bg,
            sky_bg_g             = g_bg,
            sky_bg_b             = b_bg,
            extinction_zenith_v  = ext_z,
        )

    @staticmethod
    def _quick_solar_position(jd: float, lat: float, lon: float):
        """Internal solar position (no dependency on OrbitalBody)."""
        from universe.orbital_body import (
            _normalize_deg, _OBLIQUITY_J2000, jd_to_centuries,
            equatorial_to_altaz,
        )
        import math
        T  = jd_to_centuries(jd)
        L0 = _normalize_deg(280.46646 + 36000.76983*T)
        M  = _normalize_deg(357.52911 + 35999.05029*T)
        M_r = math.radians(M)
        C  = (1.914602 - 0.004817*T)*math.sin(M_r) + 0.019993*math.sin(2*M_r)
        lam = _normalize_deg(L0 + C)
        eps = math.radians(_OBLIQUITY_J2000 - 0.013004*T)
        lam_r = math.radians(lam)
        ra  = math.degrees(math.atan2(math.cos(eps)*math.sin(lam_r), math.cos(lam_r))) % 360
        dec = math.degrees(math.asin(math.sin(eps)*math.sin(lam_r)))
        return equatorial_to_altaz(ra, dec, lat, lon, jd)
