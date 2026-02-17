"""
minor_bodies.py
===============
Asteroidi, pianeti nani e comete nel sistema solare.

ARCHITETTURA SCALABILE:
  Ora:   ~15 oggetti hardcoded (i più brillanti, visibili ad occhio nudo/binocolo)
  Dopo:  loader da file MPC MPCORB.DAT (600k+ asteroidi numerati)
         → MinorBodyCatalog.from_mpc_file(path, max_H=18.0, aperture_cm=None)
         → filtro automatico per magnitudine massima raggiungibile

FORMATO MPC:
  Gli elementi sono in formato MPC packed/unpacked standard.
  MinorBodyElements è compatibile con il formato ASCII MPCORB.DAT.

STRUTTURA:
  MinorBodyElements  — elementi orbitali formato MPC (epoca + anomalia media)
  MinorBody          — corpo minore con elementi + fisica
  CometBody          — cometa con elementi parabolici/ellittici + coda
  MinorBodyCatalog   — catalogo con loader lazy

INTEGRAZIONE:
  build_minor_bodies() → lista di MinorBody/CometBody
  Usato da build_solar_system() insieme ai pianeti.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from .space_object import SpaceObject, ObjectClass, ObjectSubtype, ObjectOrigin
from .orbital_body import (
    OrbitalElements, OrbitalBody, datetime_to_jd, jd_to_centuries,
    solve_kepler, ecliptic_to_equatorial, xyz_to_radec,
    equatorial_to_altaz, _EARTH_ELEMENTS, _normalize_deg,
    heliocentric_ecliptic, _OBLIQUITY_J2000
)
from .planet_physics import apparent_magnitude, apparent_diameter_arcsec


# ---------------------------------------------------------------------------
# Elementi orbitali formato MPC
# ---------------------------------------------------------------------------

@dataclass
class MinorBodyElements:
    """
    Elementi orbitali per asteroidi/comete nel formato MPC.

    Differenza da OrbitalElements (JPL):
      • epoch_jd: JD dell'epoca degli elementi (non J2000)
      • M0: anomalia media all'epoca (non longitudine media)
      • omega: argomento del perielio (non longitudine del perielio)
      • i, Om: uguali
      • a, e: uguali

    Questo è il formato standard MPCORB.DAT e può essere letto
    direttamente dai dati MPC senza conversione.
    """
    epoch_jd: float = 2451545.0   # Epoca JD (default J2000)
    a:        float = 1.0         # Semiasse maggiore (AU)
    e:        float = 0.0         # Eccentricità
    i:        float = 0.0         # Inclinazione (deg)
    omega:    float = 0.0         # Argomento del perielio (deg)
    Om:       float = 0.0         # Longitudine nodo ascendente (deg)
    M0:       float = 0.0         # Anomalia media all'epoca (deg)
    H:        float = 10.0        # Magnitudine assoluta
    G:        float = 0.15        # Slope parameter

    @property
    def n(self) -> float:
        """Moto medio in gradi/giorno (legge di Keplero)."""
        return 0.9856076686 / (self.a ** 1.5)

    def mean_anomaly_at(self, jd: float) -> float:
        """Anomalia media alla data JD."""
        return _normalize_deg(self.M0 + self.n * (jd - self.epoch_jd))

    def heliocentric_ecliptic(self, jd: float) -> Tuple[float, float, float]:
        """Coordinate eclittiche eliocentriche (AU) alla data JD."""
        M = self.mean_anomaly_at(jd)
        E = solve_kepler(M, self.e)
        E_r = math.radians(E)

        a, e = self.a, self.e
        x_orb = a * (math.cos(E_r) - e)
        y_orb = a * math.sqrt(1.0 - e*e) * math.sin(E_r)

        omega_r = math.radians(self.omega)
        Om_r    = math.radians(self.Om)
        i_r     = math.radians(self.i)

        cos_w = math.cos(omega_r); sin_w = math.sin(omega_r)
        cos_O = math.cos(Om_r);    sin_O = math.sin(Om_r)
        cos_i = math.cos(i_r);     sin_i = math.sin(i_r)

        x = (cos_O*cos_w - sin_O*sin_w*cos_i)*x_orb + (-cos_O*sin_w - sin_O*cos_w*cos_i)*y_orb
        y = (sin_O*cos_w + cos_O*sin_w*cos_i)*x_orb + (-sin_O*sin_w + cos_O*cos_w*cos_i)*y_orb
        z = (sin_w*sin_i)*x_orb + (cos_w*sin_i)*y_orb

        return x, y, z

    @classmethod
    def from_mpc_line(cls, line: str) -> Optional['MinorBodyElements']:
        """
        Parse una riga del formato MPCORB.DAT (ASCII, colonne fisse).
        Restituisce None se la riga non è valida.

        Formato colonne (da MPC documentation):
          0-6:   numero/designazione
          8-13:  H (magnitudine assoluta)
          14-19: G (slope)
          20-25: epoca (packed MPC format)
          26-35: M (anomalia media, deg)
          37-46: omega (argomento perielio, deg)
          48-57: Om (nodo ascendente, deg)
          59-67: i (inclinazione, deg)
          70-79: e (eccentricità)
          92-102: a (semiasse maggiore, AU)
        """
        if len(line) < 103 or line.startswith('#'):
            return None
        try:
            H     = float(line[8:13].strip() or '10.0')
            G     = float(line[14:19].strip() or '0.15')
            epoch = _unpack_mpc_epoch(line[20:25].strip())
            M0    = float(line[26:35].strip())
            omega = float(line[37:46].strip())
            Om    = float(line[48:57].strip())
            i     = float(line[59:67].strip())
            e     = float(line[70:79].strip())
            a     = float(line[92:102].strip())
            return cls(epoch_jd=epoch, a=a, e=e, i=i,
                       omega=omega, Om=Om, M0=M0, H=H, G=G)
        except (ValueError, IndexError):
            return None


def _unpack_mpc_epoch(packed: str) -> float:
    """
    Decodifica l'epoca MPC packed (5 caratteri) in Julian Date.
    Formato: K234A = 2023 Jan 10 → JD
    Caratteri speciali: I=1800, J=1900, K=2000; A=10, B=11, ..., V=31
    """
    if len(packed) < 5:
        return 2451545.0
    century_map = {'I': 1800, 'J': 1900, 'K': 2000}
    alpha_map = {c: 10 + i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUV')}

    century = century_map.get(packed[0], 2000)
    year = century + int(packed[1:3])
    month_c = packed[3]
    day_c   = packed[4]
    month = alpha_map.get(month_c, int(month_c)) if month_c.isalpha() else int(month_c)
    day   = alpha_map.get(day_c,   int(day_c))   if day_c.isalpha()   else int(day_c)

    # Conversione data → JD (formula standard)
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
    return jd


# ---------------------------------------------------------------------------
# MinorBody — asteroide o pianeta nano
# ---------------------------------------------------------------------------

@dataclass
class MinorBody:
    """
    Corpo minore del sistema solare (asteroide, pianeta nano).

    Gestisce il proprio calcolo di posizione in modo indipendente da OrbitalBody
    perché usa elementi MPC (anomalia media + argomento perielio) invece dei
    parametri JPL (longitudine media + longitudine perielio).

    Scalabilità:
      • Stesso formato per oggetti hardcoded e file MPC
      • min_mag_limit: magnitudine minima di rendering (skip se troppo debole)
      • Usato dal MinorBodyCatalog per filtrare per apertura telescopio
    """
    uid:              str
    name:             str
    mpc_number:       str = ""           # numero MPC (es. "1" per Cerere)
    elements:         Optional[MinorBodyElements] = None
    description:      str = ""

    # Fisica
    physical_radius_km: float = 0.0
    albedo:             float = 0.15
    bv_base:            float = 0.72

    # Runtime (aggiornati da update_position)
    _jd:           float = field(default=0.0,   init=False, repr=False)
    _ra_deg:       float = field(default=0.0,   init=False, repr=False)
    _dec_deg:      float = field(default=0.0,   init=False, repr=False)
    _alt_deg:      float = field(default=-90.0, init=False, repr=False)
    _az_deg:       float = field(default=0.0,   init=False, repr=False)
    _distance_au:  float = field(default=3.0,   init=False, repr=False)
    _r_sun_au:     float = field(default=3.0,   init=False, repr=False)
    _phase_deg:    float = field(default=0.0,   init=False, repr=False)
    _apparent_mag: float = field(default=15.0,  init=False, repr=False)

    # Flags (compatibilità con il sistema di rendering)
    is_sun:  bool = field(default=False, init=False)
    is_moon: bool = field(default=False, init=False)

    # Proprietà lette dal renderer
    @property
    def ra_deg(self)  -> float: return self._ra_deg
    @property
    def dec_deg(self) -> float: return self._dec_deg
    @property
    def altitude_deg(self) -> float: return self._alt_deg
    @property
    def azimuth_deg(self)  -> float: return self._az_deg
    @property
    def distance_au(self)  -> float: return self._distance_au
    @property
    def apparent_mag(self) -> float: return self._apparent_mag
    @property
    def phase_fraction(self) -> float:
        return (1.0 + math.cos(math.radians(self._phase_deg))) / 2.0
    @property
    def mag(self) -> float: return self._apparent_mag

    def update_position(self, jd: float,
                         observer_lat: float = 0.0,
                         observer_lon: float = 0.0) -> None:
        """Calcola posizione e magnitudine alla data JD."""
        if self.elements is None:
            return
        self._jd = jd
        T = jd_to_centuries(jd)

        # Coordinate eliocentriche eclittiche del corpo
        x_b, y_b, z_b = self.elements.heliocentric_ecliptic(jd)
        r_sun = math.sqrt(x_b**2 + y_b**2 + z_b**2)
        self._r_sun_au = r_sun

        # Coordinate Terra
        earth_elems = _EARTH_ELEMENTS.at_epoch(T)
        x_e, y_e, z_e = heliocentric_ecliptic(earth_elems)

        # Geocentrico
        dx = x_b - x_e; dy = y_b - y_e; dz = z_b - z_e
        delta = math.sqrt(dx**2 + dy**2 + dz**2)
        self._distance_au = delta

        # Angolo di fase
        cos_ph = (r_sun**2 + delta**2 - (x_e**2+y_e**2+z_e**2)) / (2*r_sun*delta + 1e-15)
        self._phase_deg = math.degrees(math.acos(max(-1.0, min(1.0, cos_ph))))

        # Magnitudine
        self._apparent_mag = apparent_magnitude(
            self.uid, r_sun, delta, self._phase_deg, jd
        )

        # RA/Dec
        eps = math.radians(_OBLIQUITY_J2000 - 0.013004 * T)
        x_eq =  dx
        y_eq =  math.cos(eps)*dy - math.sin(eps)*dz
        z_eq =  math.sin(eps)*dy + math.cos(eps)*dz
        self._ra_deg, self._dec_deg = xyz_to_radec(x_eq, y_eq, z_eq)

        # Alt/Az
        self._alt_deg, self._az_deg = equatorial_to_altaz(
            self._ra_deg, self._dec_deg, observer_lat, observer_lon, jd
        )

    def apparent_diameter_arcsec(self) -> float:
        return apparent_diameter_arcsec(self.uid, self._distance_au)

    def __repr__(self) -> str:
        return (f"<MinorBody {self.uid} '{self.name}' "
                f"mag={self._apparent_mag:.1f} alt={self._alt_deg:.1f}°>")


# ---------------------------------------------------------------------------
# CometBody — cometa con coda
# ---------------------------------------------------------------------------

@dataclass
class CometBody:
    """
    Cometa con orbita ellittica o parabolica e coda visiva.

    La magnitudine delle comete è molto variabile e dipende dall'attività
    del nucleo. Usiamo la formula empirica:
        m = H + 5*log10(delta) + 2.5*n*log10(r)
    dove n (tipicamente 3-5) descrive l'attività cometaria.

    La coda è sempre diretta anti-solare (spinta dal vento solare).
    """
    uid:    str
    name:   str
    mpc_id: str = ""

    # Elementi parabolici (q=distanza al perielio, T_peri=JD del perielio)
    q_au:      float = 1.0    # distanza al perielio (AU)
    e:         float = 1.0    # eccentricità (1.0=parabolica, <1=ellittica)
    i:         float = 0.0    # inclinazione (deg)
    omega:     float = 0.0    # argomento perielio (deg)
    Om:        float = 0.0    # nodo ascendente (deg)
    T_peri_jd: float = 2451545.0  # JD del passaggio al perielio

    # Parametri cometari
    H0:    float = 8.0        # magnitudine assoluta nucleo
    n_act: float = 4.0        # esponente attività (3=bassa, 5=alta)
    tail_length_au: float = 0.0   # lunghezza coda massima (AU, 0=non attiva)

    # Fisica nucleo
    nucleus_radius_km: float = 5.0
    active:            bool  = True   # cometa attiva (con chioma)
    description:       str   = ""

    # Runtime
    _ra_deg:       float = field(default=0.0,   init=False, repr=False)
    _dec_deg:      float = field(default=0.0,   init=False, repr=False)
    _alt_deg:      float = field(default=-90.0, init=False, repr=False)
    _az_deg:       float = field(default=0.0,   init=False, repr=False)
    _distance_au:  float = field(default=5.0,   init=False, repr=False)
    _r_sun_au:     float = field(default=5.0,   init=False, repr=False)
    _apparent_mag: float = field(default=20.0,  init=False, repr=False)
    _tail_pa_deg:  float = field(default=0.0,   init=False, repr=False)  # position angle coda

    is_sun:  bool = field(default=False, init=False)
    is_moon: bool = field(default=False, init=False)

    @property
    def ra_deg(self)  -> float: return self._ra_deg
    @property
    def dec_deg(self) -> float: return self._dec_deg
    @property
    def altitude_deg(self) -> float: return self._alt_deg
    @property
    def azimuth_deg(self)  -> float: return self._az_deg
    @property
    def distance_au(self)  -> float: return self._distance_au
    @property
    def apparent_mag(self) -> float: return self._apparent_mag
    @property
    def mag(self) -> float: return self._apparent_mag
    @property
    def tail_pa_deg(self)  -> float: return self._tail_pa_deg  # position angle coda (gradi, N=0, E=90)

    def _heliocentric_ecliptic(self, jd: float) -> Tuple[float, float, float]:
        """Posizione eliocentrica eclittica per orbita generica (Danby method)."""
        dt = jd - self.T_peri_jd

        if abs(self.e - 1.0) < 1e-6:
            # Orbita parabolica: formula di Barker
            W = 0.03649116 * dt / self.q_au**1.5
            G_ = W / 2.0
            Y = (G_ + math.sqrt(G_**2 + 1.0))**(1.0/3.0)
            s = Y - 1.0/Y
            nu = 2.0 * math.atan(s)
        else:
            # Orbita ellittica: semiasse maggiore e moto medio
            a = self.q_au / (1.0 - self.e)
            n = 0.9856076686 / a**1.5
            M = _normalize_deg(n * dt)
            E = math.radians(solve_kepler(M, self.e))
            nu = 2.0 * math.atan2(math.sqrt(1+self.e)*math.sin(E/2),
                                   math.sqrt(1-self.e)*math.cos(E/2))

        r = self.q_au * (1.0 + self.e) / (1.0 + self.e * math.cos(nu))

        omega_r = math.radians(self.omega)
        Om_r    = math.radians(self.Om)
        i_r     = math.radians(self.i)
        nu_r    = nu

        u = omega_r + nu_r
        cos_O = math.cos(Om_r); sin_O = math.sin(Om_r)
        cos_u = math.cos(u);    sin_u = math.sin(u)
        cos_i = math.cos(i_r);  sin_i = math.sin(i_r)

        x = r*(cos_O*cos_u - sin_O*sin_u*cos_i)
        y = r*(sin_O*cos_u + cos_O*sin_u*cos_i)
        z = r*(sin_i*sin_u)
        return x, y, z

    def update_position(self, jd: float,
                         observer_lat: float = 0.0,
                         observer_lon: float = 0.0) -> None:
        T = jd_to_centuries(jd)
        try:
            x_c, y_c, z_c = self._heliocentric_ecliptic(jd)
        except (ValueError, ZeroDivisionError):
            return

        r_sun = math.sqrt(x_c**2 + y_c**2 + z_c**2)
        self._r_sun_au = r_sun

        earth_elems = _EARTH_ELEMENTS.at_epoch(T)
        x_e, y_e, z_e = heliocentric_ecliptic(earth_elems)

        dx = x_c - x_e; dy = y_c - y_e; dz = z_c - z_e
        delta = math.sqrt(dx**2 + dy**2 + dz**2)
        self._distance_au = delta

        # Magnitudine cometaria
        self._apparent_mag = (self.H0
                               + 5.0 * math.log10(max(delta, 0.001))
                               + 2.5 * self.n_act * math.log10(max(r_sun, 0.001)))

        # RA/Dec
        eps = math.radians(_OBLIQUITY_J2000 - 0.013004*T)
        x_eq =  dx
        y_eq =  math.cos(eps)*dy - math.sin(eps)*dz
        z_eq =  math.sin(eps)*dy + math.cos(eps)*dz
        self._ra_deg, self._dec_deg = xyz_to_radec(x_eq, y_eq, z_eq)

        # Alt/Az
        self._alt_deg, self._az_deg = equatorial_to_altaz(
            self._ra_deg, self._dec_deg, observer_lat, observer_lon, jd
        )

        # Position angle della coda (direzione anti-solare proiettata sul cielo)
        # Vettore sole→cometa in equatoriale
        sx_eq, sy_eq, sz_eq = ecliptic_to_equatorial(-x_e, -y_e, -z_e)
        # Approssimazione: coda punta nella direzione opposta al sole nel cielo
        sun_ra  = math.degrees(math.atan2(sy_eq, sx_eq)) % 360.0
        sun_dec = math.degrees(math.asin(sz_eq / max(math.sqrt(sx_eq**2+sy_eq**2+sz_eq**2), 1e-9)))
        # PA (Nord attraverso Est) dalla posizione della cometa verso il sole → inverti
        d_ra  = math.radians(self._ra_deg - sun_ra)
        d_dec = math.radians(self._dec_deg - sun_dec)
        self._tail_pa_deg = math.degrees(math.atan2(
            math.sin(d_ra),
            math.cos(math.radians(self._dec_deg)) * math.tan(math.radians(sun_dec))
            - math.sin(math.radians(self._dec_deg)) * math.cos(d_ra)
        )) % 360.0

    def __repr__(self) -> str:
        return (f"<CometBody {self.uid} '{self.name}' "
                f"mag={self._apparent_mag:.1f} r_sun={self._r_sun_au:.2f}AU>")


# ---------------------------------------------------------------------------
# MinorBodyCatalog — catalogo con loader scalabile
# ---------------------------------------------------------------------------

class MinorBodyCatalog:
    """
    Catalogo di oggetti minori.

    Uso base:
        catalog = MinorBodyCatalog.default()   # 15 oggetti hardcoded
        bodies = catalog.bodies

    Uso avanzato (futuro, quando si avrà MPCORB.DAT):
        catalog = MinorBodyCatalog.from_mpc_file(
            path="MPCORB.DAT",
            max_H=18.0,              # magnitudine assoluta limite
            aperture_cm=25.0,        # apertura telescopio (cm)
            min_sky_coverage=True    # includi solo osservabili da lat 45°N
        )
    """

    def __init__(self):
        self.bodies: List[MinorBody | CometBody] = []

    @classmethod
    def default(cls) -> 'MinorBodyCatalog':
        """Crea catalogo con oggetti hardcoded (visibili occhio nudo / binocolo)."""
        cat = cls()
        cat.bodies = _build_default_minor_bodies()
        return cat

    @classmethod
    def from_mpc_file(cls, path: str,
                       max_H: float = 16.0,
                       aperture_cm: Optional[float] = None,
                       max_objects: int = 10000) -> 'MinorBodyCatalog':
        """
        Carica asteroidi da file MPCORB.DAT (formato MPC ASCII).

        Parametri:
            path         : percorso file MPCORB.DAT
            max_H        : magnitudine assoluta massima da includere
                           (H=16 → visibile con telescopio da 25cm)
                           (H=18 → visibile con telescopio da 60cm+)
            aperture_cm  : apertura telescopio in cm (override max_H)
            max_objects  : limite massimo oggetti caricati (performance)

        Se aperture_cm è fornito, calcola max_H automaticamente:
            H_max ≈ 5.0 + 5.0*log10(aperture_cm) + 2.5  (empirico)
        """
        if aperture_cm is not None:
            # Stima della limiting magnitude per apertura data
            # Formula empirica: mag_lim ≈ 2.1 + 5*log10(D_mm)
            D_mm = aperture_cm * 10.0
            mag_lim = 2.1 + 5.0 * math.log10(max(D_mm, 1.0))
            # H_max: asteroide a 1AU dal Sole e 1AU dalla Terra in opposizione
            # V ≈ H + 5*log10(r*delta) - correction ≈ H per r=delta=1
            max_H = mag_lim - 1.5  # margine per asteroidi lontani

        cat = cls()
        # Inizia sempre con gli oggetti default (garantiscono completezza)
        cat.bodies = _build_default_minor_bodies()
        default_uids = {b.uid for b in cat.bodies}

        try:
            with open(path, 'r', encoding='ascii', errors='ignore') as f:
                for line in f:
                    if len(cat.bodies) >= max_objects:
                        break
                    elems = MinorBodyElements.from_mpc_line(line)
                    if elems is None or elems.H > max_H:
                        continue
                    # Estrai nome/numero dalla riga
                    desig = line[:7].strip()
                    name_field = line[166:194].strip() if len(line) > 194 else desig
                    uid = f"MPC_{desig}"
                    if uid in default_uids:
                        continue
                    body = MinorBody(
                        uid=uid,
                        name=name_field or desig,
                        mpc_number=desig,
                        elements=elems,
                        description=f"Asteroide MPC {desig}",
                    )
                    cat.bodies.append(body)
        except FileNotFoundError:
            pass  # Fallback silenzioso agli oggetti default

        return cat

    def update_all(self, jd: float,
                    observer_lat: float = 0.0,
                    observer_lon: float = 0.0,
                    mag_limit: float = 20.0) -> None:
        """Aggiorna posizioni di tutti i corpi (con filtro magnitudine)."""
        for body in self.bodies:
            body.update_position(jd, observer_lat, observer_lon)

    def visible_bodies(self, mag_limit: float = 15.0,
                        min_alt: float = 0.0) -> List:
        """Restituisce oggetti visibili sopra l'orizzonte con mag <= mag_limit."""
        return [b for b in self.bodies
                if b._alt_deg >= min_alt and b._apparent_mag <= mag_limit]

    def __len__(self) -> int:
        return len(self.bodies)


# ---------------------------------------------------------------------------
# Oggetti hardcoded: i più brillanti e significativi
# ---------------------------------------------------------------------------

def _build_default_minor_bodies() -> List[MinorBody | CometBody]:
    """
    Costruisce la lista degli oggetti minori principali.
    Elementi da MPC/JPL Horizons, epoca 2024-11-18 (JD 2460632.5).
    """
    EPOCH = 2460632.5  # 2024 Nov 18

    def asteroid(uid, name, mpc_num, H, G, a, e, i, omega, Om, M0,
                 r_km, albedo, bv, desc):
        return MinorBody(
            uid=uid, name=name, mpc_number=mpc_num,
            elements=MinorBodyElements(
                epoch_jd=EPOCH, a=a, e=e, i=i,
                omega=omega, Om=Om, M0=M0, H=H, G=G,
            ),
            physical_radius_km=r_km, albedo=albedo, bv_base=bv,
            description=desc,
        )

    bodies: List[MinorBody | CometBody] = [

        # ── Pianeti nani ──────────────────────────────────────────────────────

        asteroid("CERES", "Ceres", "1",
                 H=3.34, G=0.12,
                 a=2.7658, e=0.0785, i=10.594,
                 omega=73.115, Om=80.327, M0=291.4,
                 r_km=476.2, albedo=0.090, bv=0.72,
                 desc="Pianeta nano nella fascia principale. "
                      "Scoperto da Piazzi nel 1801. Mag max ~+6.6."),

        asteroid("VESTA", "Vesta", "4",
                 H=3.20, G=0.32,
                 a=2.3615, e=0.0887, i=7.141,
                 omega=151.198, Om=103.851, M0=20.9,
                 r_km=262.7, albedo=0.423, bv=0.78,
                 desc="Asteroide più brillante della fascia principale. "
                      "Visitato da Dawn 2011-2012. Mag max ~+5.2."),

        asteroid("PALLAS", "Pallas", "2",
                 H=4.13, G=0.11,
                 a=2.7736, e=0.2313, i=34.841,
                 omega=310.156, Om=173.100, M0=215.6,
                 r_km=256.0, albedo=0.101, bv=0.64,
                 desc="Secondo asteroide scoperto (1802). Orbita inclinata. "
                      "Mag max ~+6.5."),

        asteroid("JUNO", "Juno", "3",
                 H=5.33, G=0.12,
                 a=2.6692, e=0.2563, i=12.991,
                 omega=247.885, Om=169.869, M0=113.2,
                 r_km=116.5, albedo=0.238, bv=0.82,
                 desc="Terzo asteroide scoperto (1804). Superficie rocciosa. "
                      "Mag max ~+7.4."),

        asteroid("HYGIEA", "Hygiea", "10",
                 H=5.43, G=0.15,
                 a=3.1417, e=0.1126, i=3.838,
                 omega=312.328, Om=283.416, M0=348.9,
                 r_km=216.5, albedo=0.072, bv=0.67,
                 desc="Quarto oggetto più grande della fascia principale. "
                      "Potenziale pianeta nano. Mag max ~+9.5."),

        asteroid("INTERAMNIA", "Interamnia", "704",
                 H=6.00, G=0.15,
                 a=3.0635, e=0.1512, i=17.307,
                 omega=95.508, Om=280.373, M0=156.3,
                 r_km=164.0, albedo=0.056, bv=0.69,
                 desc="Asteroide di Classe F, sesto per dimensione. Mag max ~+10.9."),

        asteroid("DAVIDA", "Davida", "511",
                 H=6.22, G=0.15,
                 a=3.1761, e=0.1857, i=15.937,
                 omega=339.105, Om=107.575, M0=195.4,
                 r_km=148.0, albedo=0.054, bv=0.67,
                 desc="Grande asteroide di Classe C. Mag max ~+10.8."),

        # ── Pianeta nano trans-nettuniano ─────────────────────────────────────

        asteroid("PLUTO", "Pluto", "134340",
                 H=1.00, G=0.15,
                 a=39.4817, e=0.2488, i=17.142,
                 omega=112.597, Om=110.299, M0=25.2,
                 r_km=1188.3, albedo=0.575, bv=0.87,
                 desc="Pianeta nano trans-nettuniano. Visitato da New Horizons 2015. "
                      "Mag attuale ~+14.1."),

        # ── Asteroidi Near-Earth notevoli ─────────────────────────────────────

        asteroid("EROS", "433 Eros", "433",
                 H=11.16, G=0.25,
                 a=1.4580, e=0.2228, i=10.828,
                 omega=178.875, Om=304.421, M0=359.0,
                 r_km=8.42, albedo=0.250, bv=0.88,
                 desc="Primo NEA scoperto (1898). Visitato da NEAR-Shoemaker 2001. "
                      "Mag max ~+8.9 alle opposizioni favorevoli."),

        asteroid("APOPHIS", "99942 Apophis", "99942",
                 H=19.09, G=0.24,
                 a=0.9224, e=0.1914, i=3.339,
                 omega=126.393, Om=204.446, M0=201.6,
                 r_km=0.185, albedo=0.301, bv=0.85,
                 desc="Near-Earth Asteroid, flyby ravvicinato nel 2029 (< 40000 km). "
                      "Mag max ~+3.1 durante l'approccio del 13 apr 2029."),

        # ── Comete periodiche ─────────────────────────────────────────────────
    ]

    # Cometa di Halley (prossimo perielio ~2061)
    halley = CometBody(
        uid="HALLEY", name="1P/Halley",
        mpc_id="0001P",
        q_au=0.5860,      # distanza perielio (AU)
        e=0.9671,         # orbita molto ellittica
        i=162.26,         # orbita retrograda
        omega=111.33,
        Om=58.42,
        T_peri_jd=2447919.0,  # 9 febbraio 1986; prossimo ~2061 JD≈2473648
        H0=5.5,
        n_act=4.0,
        tail_length_au=0.1,   # quasi inattiva fino al 2055
        nucleus_radius_km=5.5,
        active=False,   # inattiva ora (lontana dal Sole)
        description="Cometa di Halley. Periodo ~75 anni. Prossimo perielio ~2061. "
                    "Visibile a occhio nudo alle opposizioni favorevoli.",
    )
    bodies.append(halley)

    # Cometa Encke (periodo più corto conosciuto, 3.3 anni)
    encke = CometBody(
        uid="ENCKE", name="2P/Encke",
        mpc_id="0002P",
        q_au=0.3363,
        e=0.8483,
        i=11.78,
        omega=186.54,
        Om=334.57,
        T_peri_jd=2460373.0,  # 25 febbraio 2024; si ripete ogni ~3.3 anni
        H0=10.0,
        n_act=3.5,
        tail_length_au=0.05,
        nucleus_radius_km=2.4,
        active=True,
        description="Cometa con periodo più corto (3.3 anni). "
                    "Mag max ~+8 al perielio.",
    )
    bodies.append(encke)

    return bodies


# ---------------------------------------------------------------------------
# Entry point principale — aggiunge oggetti minori al sistema solare
# ---------------------------------------------------------------------------

def build_minor_bodies() -> List[MinorBody | CometBody]:
    """
    Restituisce tutti gli oggetti minori del catalogo default.
    Da usare insieme a build_solar_system() in screen_imaging.py.

    Uso futuro con file MPC:
        if Path("MPCORB.DAT").exists():
            return MinorBodyCatalog.from_mpc_file("MPCORB.DAT",
                       aperture_cm=current_telescope_aperture).bodies
        return MinorBodyCatalog.default().bodies
    """
    return MinorBodyCatalog.default().bodies
