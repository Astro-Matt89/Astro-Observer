"""
DayPhase — stato della luce solare basato sull'altitudine del Sole.

Ogni fase definisce:
  - visibilità delle stelle (limite di magnitudine)
  - sky background base (colore + intensità)
  - flag per bloccare acquisizioni imaging
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Tuple


class DayPhase(Enum):
    """
    Fasi della giornata astronomica in ordine di altitudine solare crescente.
    I confini sono altitudini del Sole in gradi.
    """
    NIGHT             = "night"              # Sol < -18°   cielo completamente buio
    ASTRONOMICAL_TWILIGHT = "astro_twilight" # -18° < Sol < -12°
    NAUTICAL_TWILIGHT = "nautical_twilight"  # -12° < Sol < -6°
    CIVIL_TWILIGHT    = "civil_twilight"     # -6°  < Sol < -0.833°
    SUNRISE_SUNSET    = "sunrise_sunset"     # -0.833° < Sol < 0° (refrazione)
    GOLDEN_HOUR       = "golden_hour"        # 0°  < Sol < 6°
    DAY               = "day"               # Sol > 6°

    @classmethod
    def from_solar_altitude(cls, alt_deg: float) -> 'DayPhase':
        if   alt_deg < -18.0:    return cls.NIGHT
        elif alt_deg < -12.0:    return cls.ASTRONOMICAL_TWILIGHT
        elif alt_deg <  -6.0:    return cls.NAUTICAL_TWILIGHT
        elif alt_deg <  -0.833:  return cls.CIVIL_TWILIGHT
        elif alt_deg <   0.0:    return cls.SUNRISE_SUNSET
        elif alt_deg <   6.0:    return cls.GOLDEN_HOUR
        else:                    return cls.DAY


@dataclass(frozen=True)
class PhaseProperties:
    """Proprietà visive e operative di una fase."""
    # Stella più debole visibile a occhio nudo (mag limit)
    naked_eye_limit:   float
    # Imaging consentito?
    imaging_allowed:   bool
    # Sky background RGB (0-1) — moltiplicato per intensità in AtmosphericModel
    sky_color_rgb:     Tuple[float, float, float]
    # Descrizione testuale
    label:             str
    # Colore UI (R,G,B 0-255) per indicatore di fase
    ui_color:          Tuple[int, int, int]


PHASE_PROPERTIES: dict[DayPhase, PhaseProperties] = {
    DayPhase.NIGHT: PhaseProperties(
        naked_eye_limit=6.5,
        imaging_allowed=True,
        sky_color_rgb=(0.005, 0.010, 0.025),  # quasi nero, leggero teal
        label="Night",
        ui_color=(0, 40, 80),
    ),
    DayPhase.ASTRONOMICAL_TWILIGHT: PhaseProperties(
        naked_eye_limit=5.0,
        imaging_allowed=True,   # consentito ma background più alto
        sky_color_rgb=(0.012, 0.025, 0.080),  # blu profondo
        label="Astro Twilight",
        ui_color=(0, 60, 140),
    ),
    DayPhase.NAUTICAL_TWILIGHT: PhaseProperties(
        naked_eye_limit=3.0,
        imaging_allowed=False,  # background troppo alto per deepsky
        sky_color_rgb=(0.050, 0.080, 0.200),  # blu medio
        label="Nautical Twilight",
        ui_color=(20, 80, 200),
    ),
    DayPhase.CIVIL_TWILIGHT: PhaseProperties(
        naked_eye_limit=1.0,
        imaging_allowed=False,
        sky_color_rgb=(0.180, 0.220, 0.480),  # blu/indaco
        label="Civil Twilight",
        ui_color=(60, 120, 220),
    ),
    DayPhase.SUNRISE_SUNSET: PhaseProperties(
        naked_eye_limit=-1.0,
        imaging_allowed=False,
        sky_color_rgb=(0.600, 0.350, 0.120),  # arancio/dorato
        label="Sunrise / Sunset",
        ui_color=(220, 140, 40),
    ),
    DayPhase.GOLDEN_HOUR: PhaseProperties(
        naked_eye_limit=-5.0,
        imaging_allowed=False,
        sky_color_rgb=(0.850, 0.520, 0.100),  # dorato caldo
        label="Golden Hour",
        ui_color=(240, 180, 60),
    ),
    DayPhase.DAY: PhaseProperties(
        naked_eye_limit=-10.0,
        imaging_allowed=False,
        sky_color_rgb=(0.400, 0.600, 0.980),  # azzurro cielo
        label="Day",
        ui_color=(100, 180, 255),
    ),
}


def get_phase_properties(phase: DayPhase) -> PhaseProperties:
    return PHASE_PROPERTIES[phase]
