"""
Procedural Generation System
Genera oggetti astronomici procedurali deterministici da scoprire
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Optional
from catalogs.deep_sky import DeepSkyObject, DSOType

# Utilities per RNG deterministico (da astro2.py)
def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF

def u01_from_u64(u: int) -> float:
    return (u >> 11) * (1.0 / (1 << 53))

def hash_u64(*vals: int) -> int:
    x = 0xA5A5A5A5A5A5A5A5
    for v in vals:
        x ^= (v & 0xFFFFFFFFFFFFFFFF)
        x = splitmix64(x)
    return x

def rng_from_seed(seed_u64: int) -> np.random.Generator:
    return np.random.default_rng(np.uint64(seed_u64))

@dataclass
class ProceduralAsteroid:
    """Asteroide procedurale"""
    id: int
    name: str
    
    # Elementi orbitali (Keplerian elements)
    a: float           # Semi-major axis (AU)
    e: float           # Eccentricity
    i_deg: float       # Inclination (deg)
    omega_deg: float   # Longitude of ascending node (deg)
    w_deg: float       # Argument of perihelion (deg)
    M0_deg: float      # Mean anomaly at epoch (deg)
    epoch_jd: float    # Epoch (Julian Date)
    
    # Proprietà fisiche
    H: float           # Absolute magnitude
    G: float           # Slope parameter
    diameter_km: float
    albedo: float
    rotation_period_h: float
    
    # Classificazione
    orbital_class: str  # "MBA" (Main Belt), "NEO", "TNO", ecc.
    spectral_type: str  # "C", "S", "M", ecc.
    
    discovered: bool = False
    discovery_date: Optional[float] = None  # JD

@dataclass
class ProceduralComet:
    """Cometa procedurale"""
    id: int
    name: str
    designation: str    # e.g. "C/2026 X1"
    
    # Elementi orbitali
    q: float           # Perihelion distance (AU)
    e: float           # Eccentricity
    i_deg: float       # Inclination (deg)
    omega_deg: float   # Longitude of ascending node (deg)
    w_deg: float       # Argument of perihelion (deg)
    T_jd: float        # Time of perihelion passage (JD)
    
    # Proprietà fisiche
    H0: float          # Total absolute magnitude
    n: float           # Slope parameter (attività)
    radius_km: float   # Nucleus radius
    
    # Tipo
    is_periodic: bool
    period_years: Optional[float] = None
    
    discovered: bool = False
    discovery_date: Optional[float] = None

class ProceduralGenerator:
    """Genera oggetti procedurali deterministici"""
    
    def __init__(self, global_seed: int):
        self.global_seed = global_seed
        
    def generate_asteroids(self, region_id: int, count: int = 100) -> list[ProceduralAsteroid]:
        """
        Genera asteroidi procedurali per una regione celeste
        Distribuiti realisticamente nella main belt (2.2 - 3.6 AU)
        """
        asteroids = []
        base_seed = hash_u64(self.global_seed, 0xA57E, region_id)
        
        for i in range(count):
            seed = hash_u64(base_seed, i)
            rng = rng_from_seed(seed)
            
            # Elementi orbitali - distribuzione realistica main belt
            # Picchi nelle risonanze di Kirkwood
            a_raw = rng.uniform(2.2, 3.6)
            # Evita le gap principali (3:1, 5:2, 7:3, 2:1 con Giove)
            gaps = [2.5, 2.82, 2.95, 3.27]
            gap_widths = [0.05, 0.03, 0.03, 0.04]
            for gap, width in zip(gaps, gap_widths):
                if abs(a_raw - gap) < width:
                    a_raw += np.sign(a_raw - gap) * width
            
            a = a_raw
            e = rng.beta(2, 5) * 0.3  # Tipicamente bassa
            i_deg = abs(rng.normal(0, 8))  # Poche inclinazioni alte
            omega_deg = rng.uniform(0, 360)
            w_deg = rng.uniform(0, 360)
            M0_deg = rng.uniform(0, 360)
            
            # Proprietà fisiche
            # Distribuzione magnitudini segue power law
            H = rng.uniform(12, 20)  # Mag assoluta
            diameter_km = 1329.0 * 10**(-H/5) / np.sqrt(0.15)  # Assumendo albedo medio
            
            albedo = rng.uniform(0.05, 0.35)  # Varia per tipo
            G = 0.15  # Slope parameter standard
            rotation_period_h = rng.lognormal(np.log(8), 0.8)  # Tipicamente 4-20h
            
            # Tipo spettrale
            r = rng.random()
            if r < 0.75:
                spectral_type = "C"  # Carbonacei (75%)
                albedo = rng.uniform(0.03, 0.10)
            elif r < 0.92:
                spectral_type = "S"  # Silicati (17%)
                albedo = rng.uniform(0.10, 0.25)
            else:
                spectral_type = "M"  # Metallici (8%)
                albedo = rng.uniform(0.15, 0.35)
            
            ast_id = (region_id << 16) | i
            
            asteroid = ProceduralAsteroid(
                id=ast_id,
                name=f"AST-{ast_id:08X}",
                a=a, e=e, i_deg=i_deg,
                omega_deg=omega_deg, w_deg=w_deg, M0_deg=M0_deg,
                epoch_jd=2460000.0,  # Epoca fissa
                H=H, G=G,
                diameter_km=diameter_km,
                albedo=albedo,
                rotation_period_h=rotation_period_h,
                orbital_class="MBA",
                spectral_type=spectral_type,
                discovered=False
            )
            
            asteroids.append(asteroid)
        
        return asteroids
    
    def generate_comets(self, year: int, count: int = 5) -> list[ProceduralComet]:
        """
        Genera comete procedurali per un anno specifico
        Include sia periodiche che non-periodiche
        """
        comets = []
        base_seed = hash_u64(self.global_seed, 0xC047, year)
        
        for i in count:
            seed = hash_u64(base_seed, i)
            rng = rng_from_seed(seed)
            
            # Decide se periodica (30%) o non-periodica (70%)
            is_periodic = rng.random() < 0.3
            
            if is_periodic:
                # Comete periodiche (P < 200 anni)
                period_years = rng.uniform(5, 200)
                q = rng.uniform(0.5, 5.0)  # Perihelion
                # Calcola a da periodo (Kepler's 3rd law)
                a = (period_years ** 2) ** (1/3)
                e = 1 - q / a
            else:
                # Comete non-periodiche (parabolic/hyperbolic)
                q = rng.uniform(0.3, 3.0)
                e = rng.uniform(0.98, 1.02)  # Quasi paraboliche
                period_years = None
                a = q / (1 - e) if e < 1 else None
            
            i_deg = rng.uniform(0, 180)  # Isotropic
            omega_deg = rng.uniform(0, 360)
            w_deg = rng.uniform(0, 360)
            
            # Perihelion passage nel futuro prossimo
            days_ahead = rng.uniform(0, 365)
            T_jd = 2460000.0 + days_ahead
            
            # Proprietà fisiche
            H0 = rng.uniform(10, 18)  # Mag assoluta
            n = rng.uniform(2, 6)     # Slope (attività)
            radius_km = rng.uniform(1, 20)
            
            comet_id = (year << 8) | i
            designation = f"{'P' if is_periodic else 'C'}/{year} X{i+1}"
            
            comet = ProceduralComet(
                id=comet_id,
                name=f"Comet {designation}",
                designation=designation,
                q=q, e=e, i_deg=i_deg,
                omega_deg=omega_deg, w_deg=w_deg,
                T_jd=T_jd,
                H0=H0, n=n, radius_km=radius_km,
                is_periodic=is_periodic,
                period_years=period_years,
                discovered=False
            )
            
            comets.append(comet)
        
        return comets
    
    def generate_nebulae(self, region_id: int, count: int = 20) -> list[DeepSkyObject]:
        """
        Genera nebulose procedurali (principalmente HII regions)
        """
        nebulae = []
        base_seed = hash_u64(self.global_seed, 0xNEB0, region_id)
        
        for i in range(count):
            seed = hash_u64(base_seed, i)
            rng = rng_from_seed(seed)
            
            # Coordinate
            ra_deg = rng.uniform(0, 360)
            dec_deg = rng.uniform(-60, 60)  # Concentrate sul piano galattico
            
            # Tipo (principalmente HII, alcune planetarie)
            r = rng.random()
            if r < 0.7:
                dso_type = DSOType.HII_REGION
                mag = rng.uniform(6, 12)
                size_arcmin = rng.uniform(5, 60)
            elif r < 0.9:
                dso_type = DSOType.PLANETARY
                mag = rng.uniform(9, 14)
                size_arcmin = rng.uniform(0.2, 3)
            else:
                dso_type = DSOType.REFLECTION
                mag = rng.uniform(8, 13)
                size_arcmin = rng.uniform(3, 20)
            
            surface_brightness = mag + 5 * np.log10(size_arcmin / 60)
            
            obj_id = (region_id << 16) | (0x8000 + i)
            
            nebula = DeepSkyObject(
                id=obj_id,
                name=f"PRO-NEB-{obj_id:08X}",
                catalog="PRO",
                catalog_num=obj_id,
                ra_deg=ra_deg,
                dec_deg=dec_deg,
                dso_type=dso_type,
                mag=mag,
                surface_brightness=surface_brightness,
                size_arcmin=size_arcmin,
                size_minor_arcmin=size_arcmin * rng.uniform(0.7, 1.0),
                pa_deg=rng.uniform(0, 180),
                distance_ly=rng.uniform(1000, 10000),
                color_index=-0.3,  # Bluish
                is_procedural=True
            )
            
            nebulae.append(nebula)
        
        return nebulae
    
    def generate_galaxies(self, volume_id: int, count: int = 50) -> list[DeepSkyObject]:
        """
        Genera galassie procedurali
        Distribuisce secondo simulazioni cosmologiche semplificate
        """
        galaxies = []
        base_seed = hash_u64(self.global_seed, 0xGA1A, volume_id)
        
        for i in range(count):
            seed = hash_u64(base_seed, i)
            rng = rng_from_seed(seed)
            
            # Coordinate
            ra_deg = rng.uniform(0, 360)
            dec_deg = rng.uniform(-90, 90)
            
            # Tipo morfologico
            r = rng.random()
            if r < 0.60:
                dso_type = DSOType.SPIRAL
                mag = rng.uniform(10, 15)
                size_arcmin = rng.uniform(1, 15)
                minor_ratio = rng.uniform(0.3, 0.7)
            elif r < 0.85:
                dso_type = DSOType.ELLIPTICAL
                mag = rng.uniform(10, 14)
                size_arcmin = rng.uniform(0.5, 8)
                minor_ratio = rng.uniform(0.6, 0.95)
            else:
                dso_type = DSOType.IRREGULAR
                mag = rng.uniform(11, 16)
                size_arcmin = rng.uniform(0.5, 5)
                minor_ratio = rng.uniform(0.5, 0.9)
            
            # Distanza e redshift
            distance_mly = rng.uniform(10, 500)  # Mega light-years
            redshift = distance_mly * 70 / 300000  # H0 = 70 km/s/Mpc
            
            surface_brightness = mag + 5 * np.log10(size_arcmin / 60)
            
            obj_id = (volume_id << 16) | (0x4000 + i)
            
            galaxy = DeepSkyObject(
                id=obj_id,
                name=f"PRO-GAL-{obj_id:08X}",
                catalog="PRO",
                catalog_num=obj_id,
                ra_deg=ra_deg,
                dec_deg=dec_deg,
                dso_type=dso_type,
                mag=mag,
                surface_brightness=surface_brightness,
                size_arcmin=size_arcmin,
                size_minor_arcmin=size_arcmin * minor_ratio,
                pa_deg=rng.uniform(0, 180),
                distance_ly=distance_mly * 1e6,
                redshift=redshift,
                color_index=rng.uniform(0.6, 1.0),  # Redder
                is_procedural=True
            )
            
            galaxies.append(galaxy)
        
        return galaxies
