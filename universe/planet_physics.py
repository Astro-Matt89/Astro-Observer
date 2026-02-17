"""
planet_physics.py
=================
Fisica planetaria accurata per il rendering e la simulazione.

Contenuto:
  • Magnitudini apparenti per pianeta (formule IAU 2012 / Müller 1893)
  • Inclinazione anelli di Saturno (B) e sua influenza sulla magnitudine
  • Diametri apparenti in arcosecondi
  • Fasi per pianeti interni (Mercurio, Venere)
  • Light-time correction (ritardo di luce per pianeti lontani)
  • Colori B-V aggiustati per fase (Venere in crescent diventa più bianca)

Formule di riferimento:
  Müller 1893, rivisto Mallama & Hilton 2018 (PASP 130, 014201)
  Meeus, "Astronomical Algorithms" Cap. 41
  IAU Working Group on Cartographic Coordinates 2015

Unità:
  Distanze in AU, angoli in gradi, magnitudini in mag V.
"""

from __future__ import annotations
import math
from typing import Tuple, Optional


# ---------------------------------------------------------------------------
# Costanti fisiche
# ---------------------------------------------------------------------------

# Velocità della luce in AU/giorno (per light-time correction)
_C_AU_PER_DAY = 173.144643  # = 299792.458 km/s / (149597870.7 km/AU * 86400 s/day)

# Diametri equatoriali (km) — per calcolo diametro apparente
PLANET_EQUATORIAL_KM = {
    "MERCURY": 4879.4,
    "VENUS":   12103.6,
    "MARS":    6792.4,
    "JUPITER": 142984.0,
    "SATURN":  120536.0,   # disco equatoriale senza anelli
    "URANUS":  51118.0,
    "NEPTUNE": 49528.0,
    "PLUTO":   2376.6,
    "CERES":   939.4,
    "VESTA":   525.4,
    "PALLAS":  512.0,
    "JUNO":    233.0,
}

# Diametro anelli Saturno (km, bordo esterno anello A)
SATURN_RING_OUTER_KM = 272000.0
# Inclinazione degli anelli rispetto all'eclittica (gradi)
SATURN_RING_INCLINATION_DEG = 26.73

# km per AU
_KM_PER_AU = 149597870.7

# arcsec per radiano
_ARCSEC_PER_RAD = 206264.806


# ---------------------------------------------------------------------------
# Light-time correction
# ---------------------------------------------------------------------------

def light_time_correction_days(distance_au: float) -> float:
    """
    Ritardo di luce in giorni per un corpo a distance_au AU.
    Per Giove (5.2 AU) ≈ 0.03 giorni = 43 minuti.
    Per Nettuno (30 AU) ≈ 0.17 giorni = 4.1 ore.
    """
    return distance_au / _C_AU_PER_DAY


# ---------------------------------------------------------------------------
# Inclinazione anelli di Saturno
# ---------------------------------------------------------------------------

def saturn_ring_inclination_B(jd: float) -> float:
    """
    Calcola l'inclinazione B degli anelli di Saturno (gradi) alla data JD.

    B è l'angolo tra la Terra e il piano degli anelli (latitudine saturnocentrica
    del Sole visto dalla Terra). Varia da 0° (piano) a ±26.73° (massima apertura).

    Meeus Cap. 45, equazione semplificata.
    B ≈ 0 nel 2025.3, massimo nord ~+27° nel 2032.5.
    """
    T = (jd - 2451545.0) / 36525.0

    # Longitudine del polo nord degli anelli (J2000 ecliptic, gradi)
    # Precede lentamente: ~0.036°/anno
    N = 113.6655 + 0.8771 * T

    # Longitudine eliocentrica di Saturno (approssimata)
    L_sat = 49.9443 + 1222.4943 * T  # gradi
    L_sat %= 360.0

    # Latitudine eclittica di Saturno ≈ 0 (orbita quasi nel piano)
    # B è calcolata dalla geometria del polo degli anelli
    N_r = math.radians(N)
    L_r = math.radians(L_sat)
    i_ring = math.radians(SATURN_RING_INCLINATION_DEG)

    # Latitudine saturnocentrica della Terra
    B = math.degrees(math.asin(
        math.sin(i_ring) * math.cos(math.radians(28.0644))  # decl polo
        - math.cos(i_ring) * math.sin(math.radians(28.0644)) * math.sin(L_r - N_r)
    ))

    # Approssimazione più semplice ma accurata per uso visivo (±2°):
    # Ciclo di ~29.5 anni centrato sui nodi (2009.0 e 2025.5 ≈ apertura minima)
    period = 29.457  # anni
    epoch_node = 2025.5  # prossimo incrocio del piano nel 2025
    year = 2000.0 + T * 100.0
    phase = 2.0 * math.pi * (year - epoch_node) / period
    B_simple = SATURN_RING_INCLINATION_DEG * math.sin(phase)

    return B_simple


def saturn_ring_apparent_semimajor_px(distance_au: float,
                                       render_radius_px: float) -> float:
    """
    Semiasse maggiore apparente degli anelli in pixel, per il renderer.
    Il semiasse minore = semiasse_maggiore * sin(|B|).
    """
    ring_outer_au = SATURN_RING_OUTER_KM / _KM_PER_AU
    apparent_arcsec = (ring_outer_au / distance_au) * _ARCSEC_PER_RAD
    # pixel per arcsec nel renderer allsky (180° FOV su 2*radius px)
    arcsec_per_px = (180.0 * 3600.0) / (2.0 * render_radius_px)
    return apparent_arcsec / arcsec_per_px


# ---------------------------------------------------------------------------
# Diametri apparenti
# ---------------------------------------------------------------------------

def apparent_diameter_arcsec(body_uid: str, distance_au: float) -> float:
    """
    Diametro apparente in arcosecondi del corpo alla distanza distance_au.
    Restituisce 0 se il corpo non è nel catalogo.
    """
    diam_km = PLANET_EQUATORIAL_KM.get(body_uid.upper(), 0.0)
    if diam_km == 0.0 or distance_au <= 0:
        return 0.0
    diam_au = diam_km / _KM_PER_AU
    return (diam_au / distance_au) * _ARCSEC_PER_RAD


def apparent_diameter_px(body_uid: str, distance_au: float,
                          render_radius_px: float) -> float:
    """
    Diametro apparente in pixel nel renderer allsky (180° FOV).
    """
    arcsec = apparent_diameter_arcsec(body_uid, distance_au)
    arcsec_per_px = (180.0 * 3600.0) / (2.0 * render_radius_px)
    return arcsec / arcsec_per_px


# ---------------------------------------------------------------------------
# Magnitudini planetarie (Mallama & Hilton 2018 / IAU 2012)
# ---------------------------------------------------------------------------

def apparent_magnitude(body_uid: str,
                        r_sun: float,
                        delta: float,
                        phase_deg: float,
                        jd: float = 0.0,
                        extras: Optional[dict] = None) -> float:
    """
    Magnitudine apparente V del pianeta.

    Parametri:
        body_uid   : identificatore (es. "JUPITER")
        r_sun      : distanza eliocentrica in AU
        delta      : distanza geocentrica in AU
        phase_deg  : angolo di fase Sole-Pianeta-Terra (0°=opposizione, 180°=congiunzione)
        jd         : Julian Date (necessario per Saturno → inclinazione anelli)
        extras     : dati aggiuntivi per pianeti speciali

    Restituisce la magnitudine V apparente.

    Formule: Mallama & Hilton 2018, PASP 130, 014201
    """
    uid = body_uid.upper()

    if uid == "MERCURY":
        return _mag_mercury(r_sun, delta, phase_deg)
    elif uid == "VENUS":
        return _mag_venus(r_sun, delta, phase_deg)
    elif uid == "MARS":
        return _mag_mars(r_sun, delta, phase_deg)
    elif uid == "JUPITER":
        return _mag_jupiter(r_sun, delta, phase_deg)
    elif uid == "SATURN":
        B = saturn_ring_inclination_B(jd) if jd > 0 else 0.0
        return _mag_saturn(r_sun, delta, phase_deg, B)
    elif uid == "URANUS":
        return _mag_uranus(r_sun, delta, phase_deg)
    elif uid == "NEPTUNE":
        return _mag_neptune(r_sun, delta, phase_deg)
    elif uid == "PLUTO":
        return _mag_pluto(r_sun, delta, phase_deg)
    elif uid in ("CERES", "VESTA", "PALLAS", "JUNO"):
        return _mag_minor_body(uid, r_sun, delta, phase_deg)
    else:
        # Fallback H,G system
        H = extras.get("H", 10.0) if extras else 10.0
        G = extras.get("G", 0.15) if extras else 0.15
        return _hg_magnitude(H, G, r_sun, delta, phase_deg)


def _mag_mercury(r: float, delta: float, phase: float) -> float:
    """Mercurio: Mallama 2017, max -2.5 all'elongazione massima."""
    ph = phase
    # Polynomial fit valido per 0° ≤ phase ≤ 180°
    mag = (-0.613
           + 6.328e-2 * ph
           - 1.6336e-3 * ph**2
           + 3.1870e-6 * ph**3
           + 5.0 * math.log10(r * delta))
    return mag


def _mag_venus(r: float, delta: float, phase: float) -> float:
    """Venere: Mallama & Hilton 2018. Max -4.92 a crescent ~130°."""
    ph = phase
    if ph < 163.7:
        mag = (-4.384
               - 1.044e-3 * ph
               + 3.687e-4 * ph**2
               - 2.814e-6 * ph**3
               + 8.938e-9 * ph**4
               + 5.0 * math.log10(r * delta))
    else:
        # Vicino alla congiunzione inferiore: fit diverso
        mag = (-4.384
               + 5.0 * math.log10(r * delta)
               + 0.02 * (ph - 163.7))
    return mag


def _mag_mars(r: float, delta: float, phase: float) -> float:
    """Marte: Mallama & Hilton 2018. Max -3.0 alla grande opposizione."""
    ph = phase
    mag = (-1.601
           + 2.267e-2 * ph
           - 1.302e-4 * ph**2
           + 5.0 * math.log10(r * delta))
    return mag


def _mag_jupiter(r: float, delta: float, phase: float) -> float:
    """Giove: Mallama & Hilton 2018. Max -2.94 all'opposizione."""
    ph = phase
    mag = (-9.395
           + 3.7e-4 * ph
           + 6.16e-4 * ph**2
           + 5.0 * math.log10(r * delta))
    return mag


def _mag_saturn(r: float, delta: float, phase: float, B_deg: float) -> float:
    """
    Saturno: Mallama & Hilton 2018.
    B = inclinazione degli anelli (latitudine saturnocentrica della Terra).
    B=0° → anelli di taglio (mag ~+1.0), B=26.7° → massima apertura (mag ~-0.5).
    """
    ph = phase
    B_r = math.radians(abs(B_deg))
    # Termine anelli: contributo dipendente da B
    ring_term = (-2.6 * math.sin(B_r)
                 + 1.25 * math.sin(B_r)**2)
    mag = (-8.914
           - ring_term
           + 6.9e-4 * ph
           - 4.0e-5 * ph**2
           + 5.0 * math.log10(r * delta))
    return mag


def _mag_uranus(r: float, delta: float, phase: float) -> float:
    """Urano: Mallama & Hilton 2018. Max -0.1 all'opposizione."""
    ph = phase
    mag = (-7.110
           + 6.587e-3 * ph
           + 1.045e-4 * ph**2
           + 5.0 * math.log10(r * delta))
    return mag


def _mag_neptune(r: float, delta: float, phase: float) -> float:
    """Nettuno: Mallama & Hilton 2018. Max +7.67 all'opposizione."""
    ph = phase
    mag = (-6.871
           + 2.28e-3 * ph**2
           + 5.0 * math.log10(r * delta))
    return mag


def _mag_pluto(r: float, delta: float, phase: float) -> float:
    """Plutone: H=1.0 nel sistema H,G. Max ~+13.6."""
    return _hg_magnitude(1.0, 0.15, r, delta, phase)


def _mag_minor_body(uid: str, r: float, delta: float, phase: float) -> float:
    """Oggetti minori principali — H,G calibrati su osservazioni storiche."""
    HG = {
        "CERES":  (3.34, 0.12),   # max ~+6.6 all'opposizione
        "VESTA":  (3.20, 0.32),   # max ~+5.2 (il più brillante)
        "PALLAS": (4.13, 0.11),   # max ~+6.5
        "JUNO":   (5.33, 0.12),   # max ~+7.4
    }
    H, G = HG.get(uid, (10.0, 0.15))
    return _hg_magnitude(H, G, r, delta, phase)


def _hg_magnitude(H: float, G: float,
                   r: float, delta: float, phase: float) -> float:
    """
    Sistema H,G standard (IAU 1985).
    H: magnitudine assoluta, G: slope parameter.
    """
    ph_r = math.radians(phase)
    tan_half = math.tan(ph_r / 2.0)
    # Evita tan(0)=0 per opposizione esatta
    if tan_half < 1e-10:
        phi1 = phi2 = 1.0
    else:
        phi1 = math.exp(-3.33  * tan_half**0.63)
        phi2 = math.exp(-1.87  * tan_half**1.22)
    return (H
            - 2.5 * math.log10((1.0 - G) * phi1 + G * phi2)
            + 5.0 * math.log10(r * delta))


# ---------------------------------------------------------------------------
# Fase visiva (illuminated fraction + orientation)
# ---------------------------------------------------------------------------

def illuminated_fraction(phase_deg: float) -> float:
    """Frazione illuminata 0..1 dal phase_angle."""
    return (1.0 + math.cos(math.radians(phase_deg))) / 2.0


def phase_bv_correction(base_bv: float, phase_deg: float,
                         body_uid: str) -> float:
    """
    Aggiustamento B-V per fase: i pianeti in crescent diventano leggermente
    più rossi per scattering atmosferico (Venere) o più blu (Giove per
    forward scattering nelle nubi).
    Solo Venere e Marte hanno correzione significativa.
    """
    uid = body_uid.upper()
    if uid == "VENUS":
        # Venere in crescent (phase > 120°): leggermente più bianca/fredda
        if phase_deg > 120.0:
            return base_bv - 0.05 * (phase_deg - 120.0) / 60.0
    elif uid == "MARS":
        # Marte a grande fase (vicino alla congiunzione): arrossamento
        if phase_deg > 40.0:
            return base_bv + 0.03 * (phase_deg - 40.0) / 140.0
    return base_bv


# ---------------------------------------------------------------------------
# Tabella riassuntiva proprietà fisiche (per uso del renderer)
# ---------------------------------------------------------------------------

def get_planet_physical_data(uid: str) -> dict:
    """
    Restituisce un dict con proprietà fisiche fisse del pianeta.
    Usato dal renderer per decidere come disegnare l'oggetto.
    """
    _DATA = {
        "MERCURY": dict(
            has_rings=False, has_phases=True,
            oblateness=0.000,
            bv_base=0.93, albedo=0.142,
            max_elongation_deg=28.3,
        ),
        "VENUS": dict(
            has_rings=False, has_phases=True,
            oblateness=0.000,
            bv_base=0.82, albedo=0.689,
            max_elongation_deg=47.8,
        ),
        "MARS": dict(
            has_rings=False, has_phases=False,
            oblateness=0.006,
            bv_base=1.36, albedo=0.170,
            max_elongation_deg=180.0,
        ),
        "JUPITER": dict(
            has_rings=False, has_phases=False,
            oblateness=0.065,
            bv_base=0.83, albedo=0.538,
            max_elongation_deg=180.0,
        ),
        "SATURN": dict(
            has_rings=True,  has_phases=False,
            oblateness=0.098,
            bv_base=1.04, albedo=0.499,
            max_elongation_deg=180.0,
        ),
        "URANUS": dict(
            has_rings=True,  has_phases=False,
            oblateness=0.023,
            bv_base=0.51, albedo=0.488,
            max_elongation_deg=180.0,
        ),
        "NEPTUNE": dict(
            has_rings=False, has_phases=False,
            oblateness=0.017,
            bv_base=0.41, albedo=0.442,
            max_elongation_deg=180.0,
        ),
        "PLUTO": dict(
            has_rings=False, has_phases=False,
            oblateness=0.000,
            bv_base=0.87, albedo=0.575,
            max_elongation_deg=180.0,
        ),
        "CERES":  dict(has_rings=False, has_phases=False, oblateness=0.079, bv_base=0.72, albedo=0.090, max_elongation_deg=180.0),
        "VESTA":  dict(has_rings=False, has_phases=False, oblateness=0.220, bv_base=0.78, albedo=0.423, max_elongation_deg=180.0),
        "PALLAS": dict(has_rings=False, has_phases=False, oblateness=0.100, bv_base=0.64, albedo=0.101, max_elongation_deg=180.0),
        "JUNO":   dict(has_rings=False, has_phases=False, oblateness=0.060, bv_base=0.82, albedo=0.238, max_elongation_deg=180.0),
    }
    return _DATA.get(uid.upper(), {})
