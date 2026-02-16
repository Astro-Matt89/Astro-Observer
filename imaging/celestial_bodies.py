"""
celestial_bodies.py — Sole e Luna come oggetti fisici nel renderer allsky.

DESIGN FISICO:
  Il flusso di Sole/Luna è calcolato in unità fisiche reali (fotoni) usando
  mag_to_flux(), identico alle stelle. Il bloom è un PSF gaussiano multi-scala
  normalizzato (somma=1) moltiplicato per il flusso totale.

  Il "full_well_capacity" della camera è il clamp naturale: il sensore satura
  e il bloom risultante è proporzionale a quanto il segnale eccede il FW.
  Il gain software abbassa il FW effettivo → più saturazione → bloom più grande.

  Questo replica fedelmente il comportamento fisico reale:
    - Gain alto (300): sole e luna saturano enormemente → bloom visibile anche
      con esposizioni brevi
    - Gain basso (50): sole mostra il disco pulito, luna piccolo alone

  I sigma dei kernel PSF sono calibrati su foto reali allsky (25s_OMEA5C,
  Alphea6CW_55s): la luna piena a ~60px di raggio a metà luminosità scala
  a 20-40px a render_size=560.
"""

from __future__ import annotations
import math
import numpy as np
from imaging.sky_renderer import mag_to_flux


# ── Costanti fisiche allsky ────────────────────────────────────────────────────
_ALLSKY_APERTURE_CM = 2.5      # 25mm di apertura (f/1.2 tipico)
_ALLSKY_AREA_CM2    = math.pi * _ALLSKY_APERTURE_CM**2
_ALLSKY_QE          = 0.78     # ZWO 174MM
_ALLSKY_FW_BASE     = 14000    # full well electrons (base)

# Gain software ZWO (0-400) → gain_e_per_adu effettivo
# Approssimazione: gain_eff ≈ 3.6 / (1 + gain_sw / 55)
# gain=0   → 3.6 e/ADU (basso guadagno, bassa saturazione)
# gain=200 → 0.4 e/ADU (sweet spot astro)
# gain=400 → 0.15 e/ADU (alto guadagno, satura presto)
def _gain_e_adu(gain_sw: int) -> float:
    return 3.6 / (1.0 + gain_sw / 55.0)

# Il FW effettivo in ADU scala con gain: FW_adu = FW_e / gain_e_adu
# Più alto il gain_sw → FW_adu più alto (paradosso: con gain alto il sensore
# satura in ELETTRONI prima, ma le ADU possono essere più):
# Usiamo FW in ELETTRONI come il clamp fisico
_FW_E = _ALLSKY_FW_BASE   # saturation in electrons (constant)


def _az_alt_to_xy(az_deg: float, alt_deg: float,
                   cx: float, cy: float, radius: float):
    r_px  = (90.0 - alt_deg) / 90.0 * radius
    az_r  = math.radians(az_deg)
    return cx + r_px * math.sin(az_r), cy - r_px * math.cos(az_r)


def _psf_kernel(shape: tuple, cx: float, cy: float,
                sigma: float) -> np.ndarray:
    """
    Normalised 2D Gaussian PSF (sum ≈ 1 over the array).
    Used to distribute total photons spatially.
    """
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d2  = (xx - cx)**2 + (yy - cy)**2
    g   = np.exp(-0.5 * d2 / (sigma * sigma))
    s   = g.sum()
    return g / s if s > 0 else g


_GAIN_REF_E_ADU = 0.4   # gain_e_adu at gain_sw=200 (reference)

def _bloom_from_photons(shape: tuple,
                         cx: float, cy: float,
                         total_photons: float,
                         gain_sw: int,
                         alt_deg: float) -> np.ndarray:
    """
    Distribuisce total_photons su un kernel PSF multi-scala.

    Fisica del gain:
      ADU = electrons / gain_e_per_adu
      Con gain_sw alto → gain_e_adu piccolo → stesso flusso → più ADU registrate
      Il segnale visivo scala linearmente con 1/gain_e_adu.

    Gain multiplier normalizzato a gain_sw=200 (default):
      gain_mult = gain_ref_e_adu / gain_eff_e_adu
      gain=50  → mult=0.21 (segnale attenuato)
      gain=200 → mult=0.52 (riferimento)
      gain=400 → mult=0.92 (segnale amplificato)

    Il PSF cresce con l'overflow: più il segnale eccede il FW → alone più grande.
    """
    electrons     = total_photons * _ALLSKY_QE
    g_eff         = _gain_e_adu(gain_sw)
    gain_mult     = _GAIN_REF_E_ADU / g_eff  # scale relative to gain=200

    overflow      = max(1.0, electrons / _FW_E)
    overflow_log  = math.log10(overflow)

    alt_n      = max(0.02, min(1.0, alt_deg / 90.0))
    atm_spread = 1.0 + (1.0 - alt_n) * 2.5

    sigma_scale = 1.0 + overflow_log * 0.8
    sigmas_base = np.array([3.0, 8.0, 20.0, 50.0]) * sigma_scale * atm_spread
    amps_rel    = np.array([0.50, 0.28, 0.15, 0.07])

    H, W = shape
    result    = np.zeros((H, W), np.float32)
    # total_vis: cappato per evitare valori numerici astronomici nel float32
    # ma scalato per gain → gain alto = più intenso
    total_vis = min(electrons, _FW_E * overflow_log * 500) * gain_mult

    for sigma, amp_rel in zip(sigmas_base, amps_rel):
        if sigma > max(H, W) * 2:
            continue
        k = _psf_kernel(shape, cx, cy, sigma)
        result += k * (total_vis * amp_rel)

    return result


def draw_atmospheric_glow(field: np.ndarray,
                           solar_alt_deg: float,
                           solar_az_deg: float,
                           cx: float, cy: float, radius: float) -> None:
    """
    Gradiente crepuscolare direzionale + Belt of Venus.
    Attivo tra -18° e +5° di altitudine solare.
    """
    if solar_alt_deg < -18.0 or solar_alt_deg > 5.0:
        return

    H = W = field.shape[0]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx;  dy = yy - cy
    r_px   = np.sqrt(dx*dx + dy*dy)
    r_norm = np.clip(r_px / radius, 0.0, 1.0)
    inside = r_px <= radius

    az_map    = np.arctan2(dx, -dy)
    sun_az_r  = math.radians(solar_az_deg)
    angle_sun = np.abs(((az_map - sun_az_r + math.pi) % (2*math.pi)) - math.pi)

    depth      = max(0.0, -solar_alt_deg)
    glow_str   = ((18.0 - depth) / 18.0) ** 1.4
    r_center   = min(0.98, 0.90 + depth * 0.008)
    glow_width = 0.15 + depth * 0.018

    ang_w  = np.exp(-angle_sun**2 / 0.6**2)
    rad_w  = np.exp(-((r_norm - r_center) / glow_width)**2)
    glow   = ang_w * rad_w * glow_str * inside

    if   solar_alt_deg > -2:  cr, cg, cb = 8.0, 3.0, 0.2
    elif solar_alt_deg > -6:  cr, cg, cb = 4.0, 1.8, 0.3
    elif solar_alt_deg > -12: cr, cg, cb = 1.5, 0.7, 0.2
    else:                     cr, cg, cb = 0.4, 0.15, 0.08

    field[:,:,0] += glow * cr
    field[:,:,1] += glow * cg
    field[:,:,2] += glow * cb

    # Belt of Venus
    if -10.0 < solar_alt_deg < 2.0:
        belt_str  = ((10.0 + solar_alt_deg) / 12.0) * 0.35
        anti_az_r = sun_az_r + math.pi
        az_anti   = np.abs(((az_map - anti_az_r + math.pi) % (2*math.pi)) - math.pi)
        r_belt    = (90.0 - 15.0) / 90.0
        belt      = (np.exp(-az_anti**2 / 0.8**2) *
                     np.exp(-((r_norm - r_belt) / 0.10)**2) *
                     belt_str * inside)
        field[:,:,0] += belt * 0.7
        field[:,:,1] += belt * 0.3
        field[:,:,2] += belt * 0.5


def draw_sun(field: np.ndarray,
             solar_alt_deg: float,
             solar_az_deg: float,
             cx: float, cy: float, radius: float,
             render_size: int,
             gain_sw: int = 200,
             exposure_s: float = 0.5) -> None:
    """
    Sole con bloom fisicamente basato su flusso reale e gain camera.

    Con gain=200, exp=0.5s: overflow ≈ 2.6×10¹⁰ → bloom enorme, schermo bianco
    Con gain=0,   exp=0.001s: overflow ≈ 1×10⁴  → alone moderato visibile
    """
    if solar_alt_deg < -5.0:
        return

    px, py = _az_alt_to_xy(solar_az_deg, solar_alt_deg, cx, cy, radius)
    H = W = render_size
    if not (-100 <= px < W+100 and -100 <= py < H+100):
        return

    alt_n = max(0.02, min(1.0, solar_alt_deg / 90.0))

    # Flusso fisico reale
    total_ph = mag_to_flux(-26.74, _ALLSKY_AREA_CM2, exposure_s)

    # Bloom in unità campo (stessa scala del background e stelle)
    bloom = _bloom_from_photons((H, W), px, py, total_ph, gain_sw, solar_alt_deg)

    # Colore: bianco-giallo alto, arancione-rosso orizzonte
    col_r = 1.0 + (1.0 - alt_n) * 1.5
    col_g = 1.0 + (1.0 - alt_n) * 0.2
    col_b = alt_n * 0.7

    field[:,:,0] += bloom * col_r
    field[:,:,1] += bloom * col_g
    field[:,:,2] += bloom * col_b

    # Disco fisico (limb darkening, sempre 1-2px)
    arcsec_per_px = 90.0 / (render_size * 0.5)
    sun_r_px = max(0.5, 0.265 / arcsec_per_px)
    yy, xx   = np.mgrid[0:H, 0:W].astype(np.float32)
    dist     = np.sqrt((xx - px)**2 + (yy - py)**2)
    r_n      = np.clip(dist / sun_r_px, 0.0, 1.0)
    mu       = np.sqrt(np.clip(1.0 - r_n**2, 0.0, 1.0))
    limb     = (1.0 - 0.6 * (1.0 - mu)) * (r_n < 1.0)

    # Il disco fisico al centro del bloom
    disk_brightness = total_ph * _ALLSKY_QE * 0.1  # contributo del disco
    field[:,:,0] += limb * disk_brightness * col_r
    field[:,:,1] += limb * disk_brightness * col_g
    field[:,:,2] += limb * disk_brightness * col_b


def draw_moon(field: np.ndarray,
              moon_alt_deg: float,
              moon_az_deg: float,
              phase_angle_deg: float,
              cx: float, cy: float, radius: float,
              render_size: int,
              gain_sw: int = 200,
              exposure_s: float = 0.5) -> None:
    """
    Luna con disco, fase corretta e bloom fisicamente calibrato.

    Luna piena (mag -12.7), gain=200, exp=0.5s:
      overflow ≈ 6.3×10⁴  → bloom visibile, alone ~30px a 560px render
    Quarto (mag -9.7), gain=200:
      overflow ≈ 4×10³  → alone più piccolo
    """
    if moon_alt_deg < 0.5:
        return

    px, py = _az_alt_to_xy(moon_az_deg, moon_alt_deg, cx, cy, radius)
    H = W = render_size
    if not (-50 <= px < W+50 and -50 <= py < H+50):
        return

    illuminated = (1.0 + math.cos(math.radians(phase_angle_deg))) / 2.0
    if illuminated < 0.005:
        return

    # Magnitudine effettiva della luna in base alla fase
    # mag_full = -12.73, si riduce di ~2.5log10(illuminated)
    mag_moon = -12.73 + 2.5 * math.log10(max(illuminated, 0.01))
    total_ph  = mag_to_flux(mag_moon, _ALLSKY_AREA_CM2, exposure_s)

    # Bloom fisico
    bloom = _bloom_from_photons((H, W), px, py, total_ph, gain_sw, moon_alt_deg)

    # Colore lunare: grigio-bianco freddo
    field[:,:,0] += bloom * 0.78
    field[:,:,1] += bloom * 0.82
    field[:,:,2] += bloom * 0.95

    # Disco fisico con terminatore
    arcsec_per_px = 90.0 / (render_size * 0.5)
    moon_r_px = max(0.5, 0.26 / arcsec_per_px)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dist   = np.sqrt((xx - px)**2 + (yy - py)**2)
    r_n    = np.clip(dist / moon_r_px, 0.0, 1.0)
    disk   = (r_n < 1.0).astype(np.float32)

    disk_bright = total_ph * _ALLSKY_QE * 0.05
    field[:,:,0] += disk * disk_bright * 0.78
    field[:,:,1] += disk * disk_bright * 0.82
    field[:,:,2] += disk * disk_bright * 0.95

    # Terminatore
    if illuminated < 0.92 and moon_r_px > 0.3:
        phase_r = math.radians(phase_angle_deg)
        dx_l = xx - px;  dy_l = yy - py
        proj  = dx_l * math.sin(phase_r * 0.5) + dy_l * math.cos(phase_r * 0.5)
        shadow = (proj > math.cos(phase_r) * moon_r_px) * disk
        field[:,:,0] -= shadow * disk_bright * 0.78
        field[:,:,1] -= shadow * disk_bright * 0.82
        field[:,:,2] -= shadow * disk_bright * 0.95
