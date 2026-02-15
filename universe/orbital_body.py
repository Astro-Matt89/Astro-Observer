"""
OrbitalBody — SpaceObject con parametri orbitali kepleriani reali.

Ogni corpo del sistema solare (Sole, Luna, pianeti) è un OrbitalBody.
La posizione in RA/Dec viene calcolata dinamicamente da:
  - elementi orbitali J2000
  - datetime dell'osservazione
  - posizione dell'osservatore (lat/lon/alt) per la parallasse

Architettura:
  SpaceObject          (universe/space_object.py)
      └── OrbitalBody  (universe/orbital_body.py)
              ├── Sun
              ├── Moon
              └── Planet (Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune)

I pianeti sono precaricati in SolarSystemCatalog e aggiunti all'Universe
allo stesso modo dei DSO: get_solar_system_bodies() restituisce la lista.

La posizione RA/Dec viene aggiornata tramite:
    body.update_position(jd)        # Julian Date
oppure:
    body.update_position_datetime(dt, lat_deg, lon_deg)

La posizione è quella APPARENTE (corretta per aberrazione annua + parallasse
diurna per oggetti vicini come Luna).

Nota sul Sole:
  Il Sole è un OrbitalBody con subtype=STAR/MAIN_SEQUENCE e flag is_sun=True.
  Questo permette a SkyRenderer di escluderlo dal rendering notturno e
  ad AtmosphericModel di usarlo per calcolare fase diurna/crepuscolare.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple
from datetime import datetime, timezone

from .space_object import SpaceObject, ObjectClass, ObjectSubtype, ObjectOrigin


# ---------------------------------------------------------------------------
# Julian Date helpers
# ---------------------------------------------------------------------------

def datetime_to_jd(dt: datetime) -> float:
    """Convert datetime (UTC) to Julian Date."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # J2000.0 = JD 2451545.0  (2000 Jan 1.5 TT ≈ 2000 Jan 1 12:00 UTC)
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    delta = dt - j2000
    return 2451545.0 + delta.total_seconds() / 86400.0


def jd_to_centuries(jd: float) -> float:
    """Julian centuries from J2000.0"""
    return (jd - 2451545.0) / 36525.0


# ---------------------------------------------------------------------------
# Orbital Elements (J2000 epoch, with secular rates)
# ---------------------------------------------------------------------------

@dataclass
class OrbitalElements:
    """
    Keplerian orbital elements at J2000.0 epoch, plus secular rates per century.

    Units:
        a     : semi-major axis (AU)
        e     : eccentricity (dimensionless)
        i     : inclination (degrees)
        L     : mean longitude (degrees)
        w_bar : longitude of perihelion (degrees)
        Om    : longitude of ascending node (degrees)

    Each element has a secular rate suffix _dot (per Julian century).

    Source: JPL DE430 / Standish 1992 (simplified for visual accuracy)
    """
    # Semi-major axis
    a:     float = 1.0;   a_dot:     float = 0.0
    # Eccentricity
    e:     float = 0.0;   e_dot:     float = 0.0
    # Inclination
    i:     float = 0.0;   i_dot:     float = 0.0
    # Mean longitude
    L:     float = 0.0;   L_dot:     float = 0.0
    # Longitude of perihelion
    w_bar: float = 0.0;   w_bar_dot: float = 0.0
    # Longitude of ascending node
    Om:    float = 0.0;   Om_dot:    float = 0.0

    def at_epoch(self, T: float) -> 'OrbitalElements':
        """Return elements at T Julian centuries from J2000."""
        return OrbitalElements(
            a     = self.a     + self.a_dot     * T,
            e     = self.e     + self.e_dot     * T,
            i     = self.i     + self.i_dot     * T,
            L     = self.L     + self.L_dot     * T,
            w_bar = self.w_bar + self.w_bar_dot * T,
            Om    = self.Om    + self.Om_dot    * T,
        )


# ---------------------------------------------------------------------------
# Kepler equation solver
# ---------------------------------------------------------------------------

def solve_kepler(M_deg: float, e: float, tol: float = 1e-9, max_iter: int = 50) -> float:
    """
    Solve Kepler's equation: M = E - e*sin(E)
    Returns eccentric anomaly E in degrees.
    """
    M = math.radians(M_deg % 360.0)
    E = M + e * math.sin(M) * (1.0 + e * math.cos(M))
    for _ in range(max_iter):
        dE = (M - E + e * math.sin(E)) / (1.0 - e * math.cos(E))
        E += dE
        if abs(dE) < tol:
            break
    return math.degrees(E)


# ---------------------------------------------------------------------------
# Coordinate transforms
# ---------------------------------------------------------------------------

def _normalize_deg(x: float) -> float:
    return x % 360.0


def heliocentric_ecliptic(elems: OrbitalElements) -> Tuple[float, float, float]:
    """
    Compute heliocentric ecliptic coordinates (x, y, z in AU) from
    orbital elements at a given epoch.
    """
    # Argument of perihelion
    w = elems.w_bar - elems.Om
    # Mean anomaly
    M = _normalize_deg(elems.L - elems.w_bar)
    # Eccentric anomaly
    E = solve_kepler(M, elems.e)
    E_r = math.radians(E)

    # True anomaly
    a, e = elems.a, elems.e
    x_orb = a * (math.cos(E_r) - e)
    y_orb = a * math.sqrt(1.0 - e*e) * math.sin(E_r)

    # Rotate to ecliptic frame
    w_r  = math.radians(w)
    Om_r = math.radians(elems.Om)
    i_r  = math.radians(elems.i)

    cos_w, sin_w   = math.cos(w_r),  math.sin(w_r)
    cos_Om, sin_Om = math.cos(Om_r), math.sin(Om_r)
    cos_i, sin_i   = math.cos(i_r),  math.sin(i_r)

    x = (cos_Om*cos_w - sin_Om*sin_w*cos_i)*x_orb + (-cos_Om*sin_w - sin_Om*cos_w*cos_i)*y_orb
    y = (sin_Om*cos_w + cos_Om*sin_w*cos_i)*x_orb + (-sin_Om*sin_w + cos_Om*cos_w*cos_i)*y_orb
    z = (sin_w*sin_i)*x_orb + (cos_w*sin_i)*y_orb

    return x, y, z


# Obliquity of ecliptic at J2000 (degrees)
_OBLIQUITY_J2000 = 23.43928

def ecliptic_to_equatorial(x_ecl: float, y_ecl: float, z_ecl: float,
                            obliquity_deg: float = _OBLIQUITY_J2000
                            ) -> Tuple[float, float, float]:
    """Rotate from ecliptic to equatorial J2000 frame."""
    eps = math.radians(obliquity_deg)
    cos_e, sin_e = math.cos(eps), math.sin(eps)
    x_eq =  x_ecl
    y_eq =  cos_e * y_ecl - sin_e * z_ecl
    z_eq =  sin_e * y_ecl + cos_e * z_ecl
    return x_eq, y_eq, z_eq


def xyz_to_radec(x: float, y: float, z: float) -> Tuple[float, float]:
    """Cartesian equatorial → RA (deg), Dec (deg)."""
    r   = math.sqrt(x*x + y*y + z*z)
    dec = math.degrees(math.asin(z / max(r, 1e-15)))
    ra  = math.degrees(math.atan2(y, x)) % 360.0
    return ra, dec


def equatorial_to_altaz(ra_deg: float, dec_deg: float,
                         lat_deg: float, lon_deg: float,
                         jd: float) -> Tuple[float, float]:
    """
    Convert RA/Dec (J2000) to Altitude/Azimuth for observer at lat/lon/jd.
    Returns (altitude_deg, azimuth_deg) where azimuth is N=0, E=90.
    """
    # Greenwich Mean Sidereal Time (degrees)
    T = jd_to_centuries(jd)
    gmst_deg = (280.46061837
                + 360.98564736629 * (jd - 2451545.0)
                + 0.000387933 * T*T
                - T*T*T / 38710000.0) % 360.0

    # Local Hour Angle
    lha = _normalize_deg(gmst_deg + lon_deg - ra_deg)
    lha_r = math.radians(lha)
    dec_r = math.radians(dec_deg)
    lat_r = math.radians(lat_deg)

    sin_alt = (math.sin(dec_r)*math.sin(lat_r)
               + math.cos(dec_r)*math.cos(lat_r)*math.cos(lha_r))
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))

    cos_az = ((math.sin(dec_r) - math.sin(lat_r)*sin_alt)
              / (math.cos(lat_r)*math.cos(math.radians(alt)) + 1e-12))
    az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
    if math.sin(lha_r) > 0:
        az = 360.0 - az

    return alt, az


# ---------------------------------------------------------------------------
# OrbitalBody
# ---------------------------------------------------------------------------

@dataclass
class OrbitalBody(SpaceObject):
    """
    A Solar System body with Keplerian orbital mechanics.

    Extra fields beyond SpaceObject:
        orbital_elements : OrbitalElements at J2000
        physical_radius_km: mean radius in km
        albedo            : geometric albedo
        is_sun            : True for the Sun (special rendering rules)
        is_moon           : True for Earth's Moon (geocentric orbit)
        parent_body_uid   : uid of parent body (for moons)

    Dynamic fields (updated by update_position):
        _jd               : last computed Julian Date
        _ra_computed      : computed RA (deg, J2000)
        _dec_computed     : computed Dec (deg, J2000)
        _distance_au      : distance from Earth (AU)
        _alt_deg          : altitude above horizon (deg) — needs observer
        _az_deg           : azimuth (deg N=0, E=90)      — needs observer
        _phase_angle      : Sun-body-Earth angle (deg)
        _apparent_mag     : computed apparent magnitude
    """

    orbital_elements:   Optional[OrbitalElements] = None
    physical_radius_km: float = 0.0
    albedo:             float = 0.5
    absolute_mag:       float = 0.0   # H for planets, unused for Sun
    is_sun:             bool  = False
    is_moon:            bool  = False
    parent_body_uid:    str   = ""

    # Runtime (not stored, computed on demand)
    _jd:             float = field(default=0.0,   init=False, repr=False)
    _ra_computed:    float = field(default=0.0,   init=False, repr=False)
    _dec_computed:   float = field(default=0.0,   init=False, repr=False)
    _distance_au:    float = field(default=1.0,   init=False, repr=False)
    _alt_deg:        float = field(default=-90.0, init=False, repr=False)
    _az_deg:         float = field(default=0.0,   init=False, repr=False)
    _phase_angle:    float = field(default=0.0,   init=False, repr=False)
    _apparent_mag:   float = field(default=0.0,   init=False, repr=False)

    # ------------------------------------------------------------------

    def update_position(self, jd: float,
                         observer_lat: float = 0.0,
                         observer_lon: float = 0.0) -> None:
        """
        Compute and cache RA/Dec/Alt/Az/distance/magnitude for Julian Date jd.
        observer_lat/lon in degrees (WGS84).
        """
        self._jd = jd
        T = jd_to_centuries(jd)

        if self.is_sun:
            self._compute_sun_position(T, jd, observer_lat, observer_lon)
        elif self.is_moon:
            self._compute_moon_position(T, jd, observer_lat, observer_lon)
        else:
            self._compute_planet_position(T, jd, observer_lat, observer_lon)

        # Update base class ra/dec so Universe queries work normally
        self.ra_deg  = self._ra_computed
        self.dec_deg = self._dec_computed

    def update_position_datetime(self, dt: datetime,
                                  observer_lat: float = 0.0,
                                  observer_lon: float = 0.0) -> None:
        """Convenience wrapper accepting datetime instead of JD."""
        self.update_position(datetime_to_jd(dt), observer_lat, observer_lon)

    # ------------------------------------------------------------------
    # Sun position (VSOP87 low-precision, ~0.01° accuracy)
    # ------------------------------------------------------------------

    def _compute_sun_position(self, T: float, jd: float,
                               lat: float, lon: float) -> None:
        # Geometric mean longitude of Sun (degrees)
        L0 = _normalize_deg(280.46646 + 36000.76983 * T)
        # Mean anomaly of Sun
        M  = _normalize_deg(357.52911 + 35999.05029 * T - 0.0001537 * T*T)
        M_r = math.radians(M)
        # Equation of center
        C = ((1.914602 - 0.004817*T - 0.000014*T*T) * math.sin(M_r)
             + (0.019993 - 0.000101*T) * math.sin(2*M_r)
             + 0.000289 * math.sin(3*M_r))
        # Sun's true longitude
        sun_lon = L0 + C
        # Apparent longitude (aberration + nutation quick correction)
        omega = _normalize_deg(125.04 - 1934.136 * T)
        lam   = sun_lon - 0.00569 - 0.00478 * math.sin(math.radians(omega))
        # Obliquity
        eps   = _OBLIQUITY_J2000 - 0.013004 * T + 0.00000164 * T*T
        eps_r = math.radians(eps + 0.00256 * math.cos(math.radians(omega)))
        lam_r = math.radians(lam)
        # RA and Dec
        ra_r  = math.atan2(math.cos(eps_r)*math.sin(lam_r), math.cos(lam_r))
        dec_r = math.asin(math.sin(eps_r)*math.sin(lam_r))

        self._ra_computed  = math.degrees(ra_r) % 360.0
        self._dec_computed = math.degrees(dec_r)
        self._distance_au  = 1.0   # ~1 AU, precise enough for atmospheric use
        self._apparent_mag = -26.74
        self._phase_angle  = 0.0

        alt, az = equatorial_to_altaz(self._ra_computed, self._dec_computed,
                                       lat, lon, jd)
        self._alt_deg = alt
        self._az_deg  = az

    # ------------------------------------------------------------------
    # Moon position (Jean Meeus Ch 47, truncated, ~0.1° accuracy)
    # ------------------------------------------------------------------

    def _compute_moon_position(self, T: float, jd: float,
                                lat: float, lon: float) -> None:
        # Fundamental arguments (degrees)
        L_r  = _normalize_deg(218.3164477 + 481267.88123421*T)   # Mean longitude
        D    = _normalize_deg(297.8501921 + 445267.1114034*T)    # Mean elongation
        M    = _normalize_deg(357.5291092 + 35999.0502909*T)     # Sun mean anomaly
        Mp   = _normalize_deg(134.9633964 + 477198.8675055*T)    # Moon mean anomaly
        F    = _normalize_deg(93.2720950  + 483202.0175233*T)    # Arg of latitude
        E    = 1.0 - 0.002516*T - 0.0000074*T*T

        D_r, M_r, Mp_r, F_r = (math.radians(x) for x in [D, M, Mp, F])

        # Longitude perturbations (truncated series, 8 largest terms)
        lon_sum = (6288774 * math.sin(Mp_r)
                   + 1274027 * math.sin(2*D_r - Mp_r)
                   + 658314  * math.sin(2*D_r)
                   + 213618  * math.sin(2*Mp_r)
                   -  185116 * E * math.sin(M_r)
                   -  114332 * math.sin(2*F_r)
                   +   58793 * math.sin(2*D_r - 2*Mp_r)
                   +   57066 * E * math.sin(2*D_r - M_r - Mp_r))
        lam = _normalize_deg(L_r + lon_sum / 1e6)

        # Latitude perturbations
        lat_sum = (5128122 * math.sin(F_r)
                   + 280602 * math.sin(Mp_r + F_r)
                   + 277693 * math.sin(Mp_r - F_r)
                   + 173237 * math.sin(2*D_r - F_r)
                   +  55413 * math.sin(2*D_r - Mp_r + F_r)
                   +  46271 * math.sin(2*D_r - Mp_r - F_r))
        beta = lat_sum / 1e6

        # Distance (km)
        dist_sum = (-20905355 * math.cos(Mp_r)
                    - 3699111 * math.cos(2*D_r - Mp_r)
                    - 2955968 * math.cos(2*D_r)
                    -  569925 * math.cos(2*Mp_r)
                    +   48888 * E * math.cos(M_r))
        self._distance_au = (385000.56 + dist_sum/1000.0) / 149597870.7

        # Ecliptic → equatorial
        eps   = math.radians(_OBLIQUITY_J2000 - 0.013004*T)
        lam_r = math.radians(lam)
        beta_r = math.radians(beta)

        x = math.cos(beta_r)*math.cos(lam_r)
        y = math.cos(eps)*math.cos(beta_r)*math.sin(lam_r) - math.sin(eps)*math.sin(beta_r)
        z = math.sin(eps)*math.cos(beta_r)*math.sin(lam_r) + math.cos(eps)*math.sin(beta_r)

        self._ra_computed  = math.degrees(math.atan2(y, x)) % 360.0
        self._dec_computed = math.degrees(math.asin(max(-1,min(1,z))))

        # Phase angle (Sun–Moon–Earth)
        sun_L0 = _normalize_deg(280.46646 + 36000.76983*T)
        sun_M  = _normalize_deg(357.52911 + 35999.05029*T)
        sun_lon = sun_L0 + 1.9146*math.sin(math.radians(sun_M))
        i_angle  = _normalize_deg(lam - sun_lon)
        self._phase_angle = i_angle if i_angle <= 180 else 360 - i_angle

        # Apparent magnitude (depends on phase)
        self._apparent_mag = self._moon_magnitude(self._phase_angle)

        alt, az = equatorial_to_altaz(self._ra_computed, self._dec_computed,
                                       lat, lon, jd)
        self._alt_deg = alt
        self._az_deg  = az

    @staticmethod
    def _moon_magnitude(phase_angle_deg: float) -> float:
        """Approximate Moon V magnitude from phase angle."""
        g = math.radians(phase_angle_deg)
        return -12.73 + 1.49*abs(g) + 0.043*g**4

    # ------------------------------------------------------------------
    # Planet position (JPL simplified elements)
    # ------------------------------------------------------------------

    def _compute_planet_position(self, T: float, jd: float,
                                  lat: float, lon: float) -> None:
        if self.orbital_elements is None:
            return

        elems = self.orbital_elements.at_epoch(T)

        # Heliocentric ecliptic coords of planet
        x_p, y_p, z_p = heliocentric_ecliptic(elems)

        # Heliocentric ecliptic coords of Earth (approximate)
        earth_elems = _EARTH_ELEMENTS.at_epoch(T)
        x_e, y_e, z_e = heliocentric_ecliptic(earth_elems)

        # Geocentric ecliptic
        dx = x_p - x_e
        dy = y_p - y_e
        dz = z_p - z_e
        self._distance_au = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Ecliptic → equatorial
        x_eq, y_eq, z_eq = ecliptic_to_equatorial(dx, dy, dz)
        self._ra_computed, self._dec_computed = xyz_to_radec(x_eq, y_eq, z_eq)

        # Phase angle
        r_sun = math.sqrt(x_p**2 + y_p**2 + z_p**2)
        r_earth = self._distance_au
        r_planet_sun = r_sun
        # cos(phase) = (r² + Δ² - R²) / (2rΔ)  where R=helio dist, Δ=geo dist
        cos_phase = (r_planet_sun**2 + r_earth**2 - r_sun**2) / (2*r_planet_sun*r_earth + 1e-9)
        self._phase_angle = math.degrees(math.acos(max(-1,min(1,cos_phase))))

        # Apparent magnitude (Muller 1893 / Bowell 1989 simplified)
        self._apparent_mag = self._planet_magnitude(r_planet_sun, r_earth, self._phase_angle)

        alt, az = equatorial_to_altaz(self._ra_computed, self._dec_computed,
                                       lat, lon, jd)
        self._alt_deg = alt
        self._az_deg  = az

    def _planet_magnitude(self, r_sun: float, r_earth: float,
                           phase_deg: float) -> float:
        """V magnitude from absolute magnitude H and distances."""
        g = math.radians(phase_deg)
        # H,G system (G=0.15 default)
        G = 0.15
        phi1 = math.exp(-3.33 * math.tan(g/2)**0.63)
        phi2 = math.exp(-1.87 * math.tan(g/2)**1.22)
        return (self.absolute_mag
                - 2.5 * math.log10((1-G)*phi1 + G*phi2)
                + 5.0 * math.log10(r_sun * r_earth))

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def altitude_deg(self) -> float:
        return self._alt_deg

    @property
    def azimuth_deg(self) -> float:
        return self._az_deg

    @property
    def distance_au(self) -> float:
        return self._distance_au

    @property
    def apparent_mag(self) -> float:
        return self._apparent_mag

    @property
    def is_above_horizon(self) -> bool:
        return self._alt_deg > 0.0

    @property
    def phase_fraction(self) -> float:
        """Illuminated fraction 0..1 (for Moon/planets)."""
        return (1.0 + math.cos(math.radians(self._phase_angle))) / 2.0

    def __repr__(self) -> str:
        return (f"<OrbitalBody {self.uid} '{self.name}' "
                f"alt={self._alt_deg:.1f}° mag={self._apparent_mag:.1f}>")


# ---------------------------------------------------------------------------
# Earth orbital elements (needed for planet position calc)
# ---------------------------------------------------------------------------

_EARTH_ELEMENTS = OrbitalElements(
    a=1.00000261,   a_dot= 0.00000562,
    e=0.01671022,   e_dot=-0.00003804,
    i= 0.00005,     i_dot=-46.94/3600,
    L=100.46457166, L_dot=35999.37244981,
    w_bar=102.93768193, w_bar_dot=0.32327364,
    Om= -11.26064,  Om_dot=-18228.25/3600,
)


# ---------------------------------------------------------------------------
# Solar System Catalog — all default bodies
# ---------------------------------------------------------------------------

def build_solar_system() -> list[OrbitalBody]:
    """
    Return the default Solar System bodies as OrbitalBody instances.
    These should be added to the Universe alongside stars/DSO.
    """

    # ── Sun ────────────────────────────────────────────────────────────────
    sun = OrbitalBody(
        uid="SUN", name="Sun",
        ra_deg=0.0, dec_deg=0.0, distance_ly=0.0,   # updated dynamically
        obj_class=ObjectClass.STAR,
        subtype=ObjectSubtype.MAIN_SEQUENCE,
        origin=ObjectOrigin.REAL,
        mag=-26.74, bv_color=0.63,
        physical_radius_km=695700.0,
        albedo=1.0,
        is_sun=True,
        description="The Sun — G2V main sequence star, age ~4.6 Gyr",
    )

    # ── Moon ───────────────────────────────────────────────────────────────
    moon = OrbitalBody(
        uid="MOON", name="Moon",
        ra_deg=0.0, dec_deg=0.0, distance_ly=0.0,
        obj_class=ObjectClass.SOLAR_SYSTEM,
        subtype=ObjectSubtype.PLANET,
        origin=ObjectOrigin.REAL,
        mag=-12.7, bv_color=0.92,
        physical_radius_km=1737.4,
        albedo=0.12,
        is_moon=True,
        description="Earth's Moon — rocky satellite, synchronous rotation",
    )

    # ── Planets ────────────────────────────────────────────────────────────
    # Elements from JPL Planetary Fact Sheet / Standish 1992 (J2000 epoch)
    # Format: (a, a_dot, e, e_dot, i, i_dot, L, L_dot, w_bar, w_bar_dot, Om, Om_dot)

    def planet(uid, name, bv, r_km, albedo, abs_mag, description, elems_data):
        a,ad, e,ed, i,id_, L,Ld, wp,wpd, Om,Omd = elems_data
        return OrbitalBody(
            uid=uid, name=name,
            ra_deg=0.0, dec_deg=0.0, distance_ly=0.0,
            obj_class=ObjectClass.SOLAR_SYSTEM,
            subtype=ObjectSubtype.PLANET,
            origin=ObjectOrigin.REAL,
            bv_color=bv,
            physical_radius_km=r_km,
            albedo=albedo,
            absolute_mag=abs_mag,
            description=description,
            orbital_elements=OrbitalElements(
                a=a, a_dot=ad, e=e, e_dot=ed,
                i=i, i_dot=id_, L=L, L_dot=Ld,
                w_bar=wp, w_bar_dot=wpd,
                Om=Om, Om_dot=Omd,
            ),
        )

    mercury = planet("MERCURY","Mercury", 0.93, 2439.7, 0.142, -0.6,
        "Mercury — innermost rocky planet, extreme temperature swings",
        (0.38709927, 0.00000037,
         0.20563593, 0.00001906,
         7.00497902,-0.00594749,
         252.25032350, 149472.67411175,
         77.45779628, 0.16047689,
         48.33076593,-0.12534081))

    venus = planet("VENUS","Venus", 0.82, 6051.8, 0.689, -4.4,
        "Venus — thick CO₂ atmosphere, retrograde rotation",
        (0.72333566, 0.00000390,
         0.00677672,-0.00004107,
         3.39467605,-0.00078890,
         181.97909950, 58517.81538729,
         131.60246718, 0.00268329,
         76.67984255,-0.27769418))

    mars = planet("MARS","Mars", 1.36, 3389.5, 0.170, -1.52,
        "Mars — thin CO₂ atmosphere, polar ice caps, Olympus Mons",
        (1.52371034, 0.00001847,
         0.09339410, 0.00007882,
         1.84969142,-0.00813131,
         -4.55343205, 19140.30268499,
         -23.94362959, 0.44441088,
         49.55953891,-0.29257343))

    jupiter = planet("JUPITER","Jupiter", 0.83, 69911.0, 0.538, -9.4,
        "Jupiter — largest planet, Great Red Spot, 95 known moons",
        (5.20288700,-0.00011607,
         0.04838624,-0.00013253,
         1.30439695,-0.00183714,
         34.39644051, 3034.74612775,
         14.72847983, 0.21252668,
         100.47390909, 0.20469106))

    saturn = planet("SATURN","Saturn", 1.04, 58232.0, 0.499, -8.88,
        "Saturn — ring system, 146 known moons, lowest density of any planet",
        (9.53667594,-0.00125060,
         0.05386179,-0.00050991,
         2.48599187, 0.00193609,
         49.95424423,  1222.49362201,
         92.59887831,-0.41897216,
         113.66242448,-0.28867794))

    uranus = planet("URANUS","Uranus", 0.51, 25362.0, 0.488, -7.19,
        "Uranus — ice giant, rotates on its side (97.8° axial tilt)",
        (19.18916464,-0.00196176,
         0.04725744,-0.00004397,
         0.77263783,-0.00242939,
         313.23810451,  428.48202785,
         170.95427630, 0.40805281,
         74.01692503, 0.04240589))

    neptune = planet("NEPTUNE","Neptune", 0.41, 24622.0, 0.442, -6.87,
        "Neptune — ice giant, strongest winds in Solar System, 16 moons",
        (30.06992276, 0.00026291,
         0.00859048, 0.00005105,
         1.77004347, 0.00035372,
         -55.12002969,  218.45945325,
         44.96476227,-0.32241464,
         131.78422574,-0.00508664))

    return [sun, moon, mercury, venus, mars, jupiter, saturn, uranus, neptune]
