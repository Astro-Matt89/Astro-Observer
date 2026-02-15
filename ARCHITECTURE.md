# Observatory Simulation Game - Architettura Completa

## 🎯 Visione del Progetto

Un simulatore astronomico realistico con grafica retrò DOS/VGA che combina:
- **Astronomia Reale**: Cataloghi stellari (Hipparcos, Gaia), oggetti deep-sky, sistema solare
- **Scoperta Procedurale**: Asteroidi, comete, esopianeti da scoprire (stile Space Engine)
- **Imaging Scientifico**: Pipeline completa di acquisizione, calibrazione, stacking, analisi
- **Gameplay**: Modalità Sandbox (esplorazione) e Career (progressione telescopio)
- **Stile Pixelart Realistico**: VGA DOS style con rendering realistico di nebulose e galassie

## 🏗️ Architettura Modulare

```
observatory_game/
│
├── core/                          # ✅ Sistemi base (già implementati)
│   ├── coords.py                  # Coordinate celesti, conversioni
│   ├── astro_time.py              # Tempo astronomico (JD, LST)
│   ├── catalog_index.py           # Indicizzazione spaziale tile-based
│   └── types.py                   # Dataclass base (SkyObject, Observer)
│
├── catalogs/                      # 🔶 Cataloghi astronomici
│   ├── stars.py                   # ⚠️ DA CREARE - Gestione Hipparcos/Gaia
│   ├── deep_sky.py                # ✅ Messier + DSO (già esistente)
│   ├── solar_system.py            # ⚠️ DA CREARE - Pianeti, lune, small bodies
│   └── procedural.py              # ✅ Generazione procedurale (già esistente)
│
├── physics/                       # ⚠️ DA CREARE - Simulazione fisica
│   ├── orbital.py                 # Meccaniche orbitali (Keplero, perturbazioni)
│   ├── ephemeris.py               # Calcolo posizioni pianeti (VSOP87 semplificato)
│   └── discovery.py               # Algoritmi scoperta (blink comparator, auto-detection)
│
├── imaging/                       # 🔶 Sistema imaging (da astro2.py)
│   ├── camera.py                  # ⚠️ DA CREARE - Simulazione CCD/CMOS
│   ├── frames.py                  # ⚠️ DA CREARE - Light/Dark/Flat/Bias
│   ├── calibration.py             # ⚠️ DA CREARE - Master frames, calibrazione
│   ├── stacking.py                # ⚠️ DA CREARE - Mean, median, sigma-clip
│   ├── processing.py              # ⚠️ DA CREARE - Stretch, filters, color
│   ├── analysis.py                # ⚠️ DA CREARE - Fotometria, astrometria
│   └── imaging_session.py         # ✅ Sessione imaging (già esistente)
│
├── rendering/                     # 🔶 Rendering pixelart
│   ├── sky_renderer.py            # ⚠️ DA CREARE - Stelle, costellazioni
│   ├── nebula_renderer.py         # ✅ Nebulose procedurali (già esistente)
│   ├── galaxy_renderer.py         # ✅ Galassie procedurali (già esistente)
│   ├── solar_system_renderer.py   # ⚠️ DA CREARE - Pianeti, lune
│   └── effects.py                 # ⚠️ DA CREARE - Seeing, atmospheric
│
├── ui/                            # 🔶 Interfacce utente
│   ├── base_screen.py             # ⚠️ DA CREARE - Classe base per screen
│   ├── screen_main_menu.py        # ⚠️ DA CREARE - Menu principale
│   ├── screen_observatory.py      # ⚠️ DA CREARE - Hub centrale
│   ├── screen_skychart.py         # ✅ Carta celeste (già esistente)
│   ├── screen_planetarium.py      # ✅ Planetario (base esistente)
│   ├── screen_imaging.py          # ⚠️ DA CREARE - Interfaccia imaging completa
│   ├── screen_catalog.py          # ⚠️ DA CREARE - Browser cataloghi
│   ├── screen_equipment.py        # ⚠️ DA CREARE - Gestione equipaggiamento
│   └── screen_career.py           # ⚠️ DA CREARE - Progressione career
│
├── game/                          # ⚠️ DA CREARE - Logica di gioco
│   ├── career_mode.py             # Sistema progressione
│   ├── sandbox_mode.py            # Modalità esplorazione libera
│   ├── equipment.py               # Database telescopi, camere, filtri
│   ├── tasks.py                   # Obiettivi scientifici
│   ├── discovery_system.py        # Sistema scoperte e conferme
│   └── scoring.py                 # Punti ricerca, pubblicazioni
│
├── data/                          # Dati persistenti
│   ├── catalogs/                  # File cataloghi binari
│   │   ├── hip_index.npz          # Hipparcos (da generare)
│   │   ├── gaia_index_v2.npz      # Gaia DR3 (da generare)
│   │   └── messier.json           # Messier (embedded in code)
│   ├── equipment/                 # Database equipaggiamento
│   │   ├── telescopes.json
│   │   ├── cameras.json
│   │   └── filters.json
│   └── saves/                     # Salvataggi career mode
│
├── tools/                         # ✅ Utility per build cataloghi
│   ├── build_hipparcos_index.py
│   └── build_gaia_index_v2.py
│
├── main.py                        # Entry point principale
├── main_integrated.py             # ✅ Demo integrata (già esistente)
├── astro2.py                      # ✅ Prototipo imaging standalone
│
└── requirements.txt               # Dipendenze Python
```

**Legenda:**
- ✅ Già implementato e funzionante
- 🔶 Parzialmente implementato
- ⚠️ Da creare ex-novo

---

## 📦 Moduli Dettagliati

### 1. Core Systems (✅ Già operativi)

#### `core/coords.py`
```python
# Funzioni principali:
- radec_to_azalt(ra, dec, observer, jd) -> (az, alt)
- azalt_to_radec(az, alt, observer, jd) -> (ra, dec)
- radec_to_cartesian(ra, dec) -> (x, y, z)
- angular_separation(ra1, dec1, ra2, dec2) -> degrees
```

#### `core/astro_time.py`
```python
# Funzioni principali:
- datetime_to_julian_date(dt) -> float
- julian_date_to_lst(jd, lon_deg) -> float  # Local Sidereal Time
```

#### `core/catalog_index.py`
```python
# Spatial indexing per cataloghi
class SpatialIndex:
    - query_region(ra_center, dec_center, radius_deg) -> list[objects]
    - Tile-based, efficiente per query su regioni di cielo
```

---

### 2. Catalogs System

#### `catalogs/stars.py` ⚠️ DA CREARE
```python
"""Gestione cataloghi stellari"""

class StarCatalog:
    """Wrapper unificato per Hipparcos e Gaia"""
    
    def __init__(self):
        self.hip_index = None  # SpatialIndex per Hipparcos
        self.gaia_index = None  # SpatialIndex per Gaia DR3
    
    def load_hipparcos(self, path: str):
        """Carica indice Hipparcos (mag < 7, ~120k stelle)"""
        pass
    
    def load_gaia(self, path: str):
        """Carica indice Gaia DR3 (mag < 12, subset)"""
        pass
    
    def query_stars(self, ra_deg, dec_deg, radius_deg, mag_limit=None) -> list[Star]:
        """Query con LOD automatico:
        - FOV > 30°: solo Hipparcos
        - FOV 5-30°: Hipparcos + Gaia bright
        - FOV < 5°: Gaia completo fino a mag_limit
        """
        pass
    
    def get_star_by_id(self, catalog: str, star_id: int) -> Star:
        """Recupera stella specifica (per target imaging)"""
        pass

@dataclass
class Star:
    catalog: str  # "HIP" o "GAIA"
    star_id: int
    ra_deg: float
    dec_deg: float
    mag: float
    color_index: float  # B-V per temperatura colore
    parallax_mas: float  # Parallasse (milliarcsec)
    pm_ra: float  # Proper motion RA (mas/year)
    pm_dec: float  # Proper motion Dec (mas/year)
```

#### `catalogs/deep_sky.py` ✅ Già esistente
Contiene già:
- Catalogo Messier completo (110 oggetti)
- Classificazione nebulose/galassie
- Supporto per NGC/IC (da espandere)

#### `catalogs/solar_system.py` ⚠️ DA CREARE
```python
"""Sistema solare: pianeti, lune, asteroidi, comete"""

class SolarSystemCatalog:
    def __init__(self):
        self.planets = self._load_planets()
        self.moons = self._load_major_moons()
        self.asteroids = AsteroidCatalog()
        self.comets = CometCatalog()
    
    def get_planetary_positions(self, jd: float) -> dict:
        """Calcola posizioni di tutti i pianeti"""
        pass

class AsteroidCatalog:
    """Gestione asteroidi reali + procedurali"""
    
    def __init__(self):
        # Main belt: ~1000 oggetti reali (numbered)
        self.known_asteroids = self._load_known()
        # Generatore procedurale per discovery
        self.procedural_gen = ProceduralAsteroidGenerator()
    
    def get_visible_asteroids(self, jd: float, observer: Observer, 
                              mag_limit: float = 15.0) -> list[Asteroid]:
        """Return asteroidi visibili in data posizione/data"""
        pass
    
    def check_for_discoveries(self, frames: list, jd: float) -> list[Asteroid]:
        """Analizza frames imaging per nuovi asteroidi (blink comparator)"""
        pass

@dataclass
class Asteroid:
    designation: str  # Es: "2024 XY123" o "(433) Eros"
    is_known: bool  # False = procedurale da scoprire
    orbital_elements: OrbitalElements
    abs_magnitude: float  # H magnitude
    diameter_km: float
    albedo: float
    discovery_date: Optional[datetime] = None
    discovered_by: Optional[str] = None

class CometCatalog:
    """Gestione comete reali + procedurali"""
    
    def __init__(self):
        self.periodic_comets = self._load_periodic()  # ~200 comete P/
        self.procedural_gen = ProceduralCometGenerator()
    
    def generate_new_comet(self, jd: float) -> Comet:
        """Genera nuova cometa procedurale (evento raro)"""
        pass

@dataclass
class Comet:
    designation: str  # Es: "C/2024 Y1" o "P/Halley"
    is_periodic: bool
    orbital_elements: OrbitalElements
    abs_magnitude: float
    perihelion_date: datetime
    activity_level: float  # Intensità coma/coda
```

#### `catalogs/procedural.py` ✅ Già esistente
Genera oggetti deep-sky procedurali (nebulose, galassie) con seed deterministico

---

### 3. Physics System

#### `physics/orbital.py` ⚠️ DA CREARE
```python
"""Meccaniche orbitali Kepleriane"""

@dataclass
class OrbitalElements:
    """Elementi orbitali Kepleriani"""
    a: float  # Semi-major axis (AU)
    e: float  # Eccentricità
    i: float  # Inclinazione (deg)
    Omega: float  # Longitudine nodo ascendente (deg)
    omega: float  # Argomento perielio (deg)
    M0: float  # Anomalia media epoca (deg)
    epoch: float  # Julian date epoca
    n: float  # Mean motion (deg/day)

class OrbitalMechanics:
    @staticmethod
    def elements_to_xyz(elements: OrbitalElements, jd: float) -> tuple[float, float, float]:
        """Converte elementi orbitali in coordinate cartesiane"""
        pass
    
    @staticmethod
    def xyz_to_radec(x, y, z, observer: Observer, jd: float) -> tuple[float, float]:
        """Coordinate cartesiane -> RA/Dec topocentriche"""
        pass
    
    @staticmethod
    def compute_apparent_magnitude(abs_mag: float, distance_au: float, 
                                   phase_angle: float = 0.0) -> float:
        """Calcola magnitudine apparente dato H e distanza"""
        pass
```

#### `physics/ephemeris.py` ⚠️ DA CREARE
```python
"""Calcolo effemeridi planetarie (VSOP87 semplificato)"""

class EphemerisCalculator:
    """Calcolo posizioni pianeti e Sole/Luna"""
    
    def __init__(self):
        self.vsop_data = self._load_vsop87_simplified()
    
    def get_planet_position(self, planet: str, jd: float) -> tuple[float, float, float]:
        """Returns (x, y, z) heliocentric ecliptic [AU]"""
        pass
    
    def get_sun_radec(self, jd: float, observer: Observer) -> tuple[float, float]:
        """RA/Dec del Sole"""
        pass
    
    def get_moon_radec(self, jd: float, observer: Observer) -> tuple[float, float]:
        """RA/Dec della Luna (ELP-2000 semplificato)"""
        pass
```

#### `physics/discovery.py` ⚠️ DA CREARE
```python
"""Algoritmi per scoperta oggetti"""

class DiscoverySystem:
    """Sistema di detection automatica"""
    
    def blink_comparator(self, frame1: np.ndarray, frame2: np.ndarray, 
                         threshold: float = 5.0) -> list[Detection]:
        """Confronta due frames per oggetti in movimento"""
        pass
    
    def track_asteroid(self, detections: list[Detection], 
                       time_deltas: list[float]) -> Optional[OrbitalElements]:
        """Determina orbita preliminare da 3+ osservazioni"""
        pass
    
    def confirm_discovery(self, candidate: Asteroid, 
                          observations: list) -> bool:
        """Verifica se scoperta è valida (follow-up, MPC submission)"""
        pass

@dataclass
class Detection:
    """Singola detection in un frame"""
    frame_id: int
    jd: float
    x_px: float  # Posizione pixel
    y_px: float
    ra_deg: float  # Coordinate celesti (dopo plate solving)
    dec_deg: float
    magnitude: float
    snr: float  # Signal-to-noise ratio
```

---

### 4. Imaging System (Core di astro2.py)

#### `imaging/camera.py` ⚠️ DA CREARE
```python
"""Simulazione fisica camera CCD/CMOS"""

@dataclass
class CameraSpec:
    """Specifiche tecniche camera"""
    name: str
    sensor_type: str  # "CCD" o "CMOS"
    pixel_size_um: float  # Dimensione pixel (micron)
    resolution: tuple[int, int]  # (width, height) pixels
    read_noise_e: float  # Read noise (electrons)
    dark_current_e_per_s: float  # Dark current (e-/pixel/s)
    quantum_efficiency: float  # QE (0.0-1.0)
    bit_depth: int  # 12, 14, 16 bit
    cooling: bool  # Regulated cooling?
    price: int  # Career mode

class Camera:
    """Simulatore camera"""
    
    def __init__(self, spec: CameraSpec):
        self.spec = spec
        self.temperature_c = 20.0  # Ambient temp
    
    def capture_frame(self, exposure_s: float, sky_signal: np.ndarray,
                      seed: int) -> np.ndarray:
        """Simula acquisizione singolo frame con tutti i noise"""
        # 1. Convert sky signal (photons) to electrons
        # 2. Add shot noise (Poisson)
        # 3. Add dark current (temperatura-dipendente)
        # 4. Add read noise (Gaussian)
        # 5. Digitize to ADU (12/14/16 bit)
        pass
    
    def set_cooling(self, target_temp_c: float):
        """Imposta temperatura cooling (se disponibile)"""
        if not self.spec.cooling:
            return False
        self.temperature_c = target_temp_c
        return True
```

#### `imaging/frames.py` ⚠️ DA CREARE
```python
"""Gestione diversi tipi di frames"""

@dataclass
class FrameMetadata:
    frame_type: str  # "LIGHT", "DARK", "FLAT", "BIAS"
    exposure_s: float
    camera: str
    telescope: str
    filter: str
    binning: int
    temperature_c: float
    jd: float
    target_name: str
    ra_deg: float
    dec_deg: float

class Frame:
    """Singolo frame con metadata"""
    
    def __init__(self, data: np.ndarray, metadata: FrameMetadata):
        self.data = data
        self.meta = metadata
    
    def save(self, path: str):
        """Salva come FITS-like format"""
        pass
    
    @classmethod
    def load(cls, path: str) -> 'Frame':
        """Carica da file"""
        pass
```

#### `imaging/calibration.py` ⚠️ DA CREARE
```python
"""Calibrazione frames"""

class Calibrator:
    """Pipeline di calibrazione"""
    
    def create_master_dark(self, darks: list[Frame]) -> Frame:
        """Crea master dark (median combining)"""
        pass
    
    def create_master_flat(self, flats: list[Frame], 
                          master_dark: Frame) -> Frame:
        """Crea master flat (median, normalizzato)"""
        pass
    
    def create_master_bias(self, biases: list[Frame]) -> Frame:
        """Crea master bias (median)"""
        pass
    
    def calibrate_light(self, light: Frame, 
                       master_dark: Frame, 
                       master_flat: Frame,
                       master_bias: Optional[Frame] = None) -> Frame:
        """Applica calibrazione: (Light - Dark - Bias) / Flat"""
        pass
    
    def cosmetic_correction(self, frame: Frame, 
                           bad_pixels: Optional[np.ndarray] = None) -> Frame:
        """Corregge hot/cold pixels"""
        pass
```

#### `imaging/stacking.py` ⚠️ DA CREARE
```python
"""Allineamento e stacking frames"""

class StackingEngine:
    """Engine per alignment e combine"""
    
    def align_frames(self, frames: list[Frame], 
                    reference_idx: int = 0) -> list[Frame]:
        """Allinea frames usando star matching (triangle algorithm)"""
        pass
    
    def stack_mean(self, frames: list[Frame]) -> np.ndarray:
        """Stack semplice (media)"""
        pass
    
    def stack_median(self, frames: list[Frame]) -> np.ndarray:
        """Stack median (robusto ai cosmici)"""
        pass
    
    def stack_sigma_clip(self, frames: list[Frame], 
                        sigma_low: float = 3.0, 
                        sigma_high: float = 3.0) -> np.ndarray:
        """Stack con sigma-clipping (rimuove outlier)"""
        pass
    
    def compute_snr_improvement(self, n_frames: int, 
                               method: str = "mean") -> float:
        """Calcola miglioramento SNR teorico"""
        # Mean: sqrt(N)
        # Median: sqrt(π/2 * N) ≈ 0.886 * sqrt(N)
        pass
```

#### `imaging/processing.py` ⚠️ DA CREARE
```python
"""Post-processing immagini"""

class ImageProcessor:
    """Tools di processing"""
    
    def stretch_histogram(self, img: np.ndarray, 
                         black_point: float, white_point: float,
                         gamma: float = 1.0) -> np.ndarray:
        """Stretch lineare/gamma"""
        pass
    
    def auto_stretch(self, img: np.ndarray, 
                    percentile_low: float = 0.1,
                    percentile_high: float = 99.9) -> np.ndarray:
        """Auto-stretch basato su istogramma"""
        pass
    
    def sharpen(self, img: np.ndarray, amount: float = 1.0) -> np.ndarray:
        """Unsharp mask"""
        pass
    
    def denoise(self, img: np.ndarray, sigma: float = 1.0) -> np.ndarray:
        """Denoise (bilateral filter o simile)"""
        pass
    
    def combine_rgb(self, r: np.ndarray, g: np.ndarray, 
                   b: np.ndarray) -> np.ndarray:
        """Combina canali RGB"""
        pass
    
    def combine_narrowband(self, ha: np.ndarray, 
                          oiii: np.ndarray, 
                          sii: np.ndarray,
                          palette: str = "HOO") -> np.ndarray:
        """Combina narrowband (Hubble palette, HOO, ecc.)"""
        # HOO: Ha=R, OIII=G+B
        # SHO: SII=R, Ha=G, OIII=B
        pass
```

#### `imaging/analysis.py` ⚠️ DA CREARE
```python
"""Analisi scientifica frames"""

class PhotometryEngine:
    """Fotometria apertura"""
    
    def measure_star_flux(self, img: np.ndarray, 
                         x: float, y: float,
                         aperture_radius: float,
                         sky_annulus: tuple[float, float]) -> dict:
        """Misura flusso stella con aperture photometry"""
        return {
            'flux': ...,
            'flux_err': ...,
            'magnitude': ...,
            'snr': ...
        }
    
    def differential_photometry(self, target_star, comparison_stars,
                               frames: list[Frame]) -> dict:
        """Fotometria differenziale per variabili"""
        pass
    
    def create_light_curve(self, measurements: list) -> LightCurve:
        """Crea curva di luce"""
        pass

class AstrometryEngine:
    """Astrometria e plate solving"""
    
    def plate_solve(self, img: np.ndarray, 
                   approx_center_ra: float, approx_center_dec: float,
                   approx_fov_deg: float) -> PlateCalibration:
        """Determina WCS (World Coordinate System) del frame"""
        # Pattern matching con catalogo Gaia
        pass
    
    def pixel_to_radec(self, x: float, y: float,
                      calib: PlateCalibration) -> tuple[float, float]:
        """Converti coordinate pixel -> RA/Dec"""
        pass

@dataclass
class LightCurve:
    jd: np.ndarray
    magnitude: np.ndarray
    mag_err: np.ndarray
    filter_band: str
    target_name: str
    
    def period_search(self) -> dict:
        """Cerca periodicità (Lomb-Scargle)"""
        pass
    
    def fit_transit(self) -> dict:
        """Fit modello transito esoplanetario"""
        pass
```

---

### 5. Rendering System

#### `rendering/sky_renderer.py` ⚠️ DA CREARE
```python
"""Rendering cielo stellato pixelart"""

class SkyRenderer:
    """Renderer principale per sky view"""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height))
    
    def render_stars(self, stars: list[Star], projection, 
                    mag_limit: float = 12.0):
        """Render stelle con colori realistici (temperatura)"""
        # Colore da B-V index
        # Dimensione da magnitudine
        # AA antialiasing per stelle bright
        pass
    
    def render_constellation_lines(self, constellations: list):
        """Disegna linee costellazioni (opzionale)"""
        pass
    
    def render_horizon_grid(self, observer: Observer, projection):
        """Griglia Az/Alt o RA/Dec"""
        pass
    
    def render_milky_way(self, projection):
        """Rendering Via Lattea stilizzato"""
        pass
```

#### `rendering/nebula_renderer.py` ✅ Già esistente
Genera texture procedurali realistiche per:
- Nebulose HII (emissione)
- Nebulose a riflessione
- Nebulose planetarie
- Supernova remnants
Con simulazione filtri Ha, OIII, SII

#### `rendering/galaxy_renderer.py` ✅ Già esistente
Genera galassie procedurali:
- Spirali (con bracci logaritmici)
- Ellittiche
- Irregolari
Con regioni HII, bulge, dust lanes

#### `rendering/solar_system_renderer.py` ⚠️ DA CREARE
```python
"""Rendering pianeti, lune, asteroidi"""

class PlanetRenderer:
    """Render pianeti con dettaglio procedurale"""
    
    def render_planet(self, planet_name: str, 
                     diameter_px: float, phase: float) -> pygame.Surface:
        """Render pianeta con fase (per interni)"""
        # Jupiter: bande, GRS
        # Saturn: anelli
        # Mars: calotte polari
        pass
    
    def render_moon_phases(self, phase_angle: float) -> pygame.Surface:
        """Render Luna con fase corretta"""
        pass

class SmallBodyRenderer:
    """Render asteroidi/comete"""
    
    def render_asteroid(self, size_px: float) -> pygame.Surface:
        """Asteroid come punto o piccolo disco"""
        pass
    
    def render_comet(self, coma_size: float, tail_length: float,
                    tail_angle: float) -> pygame.Surface:
        """Cometa con coma e coda"""
        pass
```

#### `rendering/effects.py` ⚠️ DA CREARE
```python
"""Effetti atmosferici e ottici"""

class AtmosphericEffects:
    """Simulazione atmosfera"""
    
    def apply_extinction(self, altitude_deg: float, mag: float) -> float:
        """Estinzione atmosferica (assorbimento)"""
        # Legge di Bouguer
        pass
    
    def apply_seeing(self, img: np.ndarray, 
                    seeing_arcsec: float, pixel_scale: float) -> np.ndarray:
        """Blur da seeing (turbolenza atmosferica)"""
        pass
    
    def apply_light_pollution(self, img: np.ndarray, 
                             sqm: float) -> np.ndarray:
        """Aggiunge sky glow (inquinamento luminoso)"""
        # sqm = Sky Quality Meter (mag/arcsec²)
        pass
    
    def apply_vignetting(self, img: np.ndarray, 
                        strength: float = 0.3) -> np.ndarray:
        """Vignettatura ottica"""
        pass
```

---

### 6. UI System

#### `ui/base_screen.py` ⚠️ DA CREARE
```python
"""Classe base per tutte le schermate"""

class BaseScreen:
    """Screen generico con gestione input e rendering"""
    
    def __init__(self, game_state: GameState):
        self.state = game_state
        self.font = pygame.font.SysFont("Consolas", 18)
        self.font_small = pygame.font.SysFont("Consolas", 14)
    
    def handle_input(self, events: list[pygame.event.Event]):
        """Gestisce input (override)"""
        pass
    
    def update(self, dt: float):
        """Update logica screen (override)"""
        pass
    
    def render(self, screen: pygame.Surface):
        """Render screen (override)"""
        pass
    
    # Utility methods comuni
    def draw_panel(self, screen, rect, fg_color, bg_color):
        """Disegna pannello stile DOS con bordo"""
        pass
    
    def draw_text(self, screen, font, x, y, text, color):
        """Render testo"""
        pass
    
    def draw_button(self, screen, rect, text, is_selected=False):
        """Bottone interattivo"""
        pass
```

#### Schermate principali:

**`screen_main_menu.py`** - Menu iniziale
- New Game (Sandbox / Career)
- Load Game
- Settings
- Exit

**`screen_observatory.py`** - Hub centrale
- Info osservatorio (location, equipaggiamento)
- Accesso alle altre schermate
- Quick status (tempo, target corrente, task attivi)
- Career mode: research points, upgrade shop

**`screen_skychart.py`** ✅ Già esistente
- Carta celeste interattiva
- Selezione target
- Info oggetti
- Planning osservazioni

**`screen_imaging.py`** - Interfaccia imaging completa
- Acquisizione frames (light/dark/flat)
- Preview live
- Calibrazione e stacking
- Processing (stretch, filters)
- Analisi (photometry, astrometry)
- Export results

**`screen_catalog.py`** - Browser cataloghi
- Filtri per tipo oggetto
- Ricerca per nome/coordinate
- Sort per magnitudine, dimensione
- Info dettagliate oggetto

**`screen_equipment.py`** - Gestione equipaggiamento
- Lista telescopi/camere/filtri disponibili
- Career: shop upgrade
- Spec tecniche dettagliate
- Confronto performance

**`screen_career.py`** - Progressione career
- Task attivi e completati
- Research points
- Discoveries log
- Achievements
- Publications

---

### 7. Game Logic

#### `game/equipment.py` ⚠️ DA CREARE
```python
"""Database equipaggiamento"""

@dataclass
class TelescopeSpec:
    name: str
    type: str  # "REFRACTOR", "REFLECTOR", "SCT", "RC"
    aperture_mm: float
    focal_length_mm: float
    focal_ratio: float  # f/#
    obstruction_pct: float  # Ostruzione centrale (0 per rifrattori)
    weight_kg: float
    price: int  # Career mode
    
    def compute_resolution_arcsec(self) -> float:
        """Risoluzione teorica (limite diffrazione)"""
        return 138.0 / self.aperture_mm  # Rayleigh criterion
    
    def compute_limiting_magnitude(self, exposure_s: float = 1.0) -> float:
        """Magnitudine limite visuale"""
        # Formula approssimata
        return 2.0 + 5.0 * math.log10(self.aperture_mm) + 2.5 * math.log10(exposure_s)

# Database telescopi
TELESCOPES = {
    "BEGINNER_80": TelescopeSpec("Refractor 80mm f/5", "REFRACTOR", 80, 400, 5.0, 0, 3, 500),
    "ADVANCED_150": TelescopeSpec("Newtonian 150mm f/5", "REFLECTOR", 150, 750, 5.0, 20, 8, 2000),
    # ... molti altri ...
}

@dataclass
class FilterSpec:
    name: str
    type: str  # "LRGB", "Ha", "OIII", "SII", "UHC", etc.
    transmission_pct: float
    bandwidth_nm: float
    central_wavelength_nm: float
    price: int

FILTERS = {
    "L": FilterSpec("Luminance", "LRGB", 95, 400, 550, 100),
    "Ha": FilterSpec("H-alpha 7nm", "NARROWBAND", 90, 7, 656, 300),
    # ...
}
```

#### `game/career_mode.py` ⚠️ DA CREARE
```python
"""Sistema progressione career"""

@dataclass
class CareerState:
    """Stato progressione giocatore"""
    research_points: int = 0
    owned_telescopes: list[str] = None
    owned_cameras: list[str] = None
    owned_filters: list[str] = None
    current_setup: dict = None  # Setup attualmente montato
    
    completed_tasks: list[str] = None
    active_tasks: list[str] = None
    
    discoveries: list[Discovery] = None
    publications: list[Publication] = None
    
    def __post_init__(self):
        if self.owned_telescopes is None:
            self.owned_telescopes = ["BEGINNER_80"]
        if self.owned_cameras is None:
            self.owned_cameras = ["WEBCAM_MOD"]
        # ...

@dataclass
class Task:
    """Obiettivo scientifico"""
    task_id: str
    title: str
    description: str
    task_type: str  # "IMAGING", "DISCOVERY", "PHOTOMETRY", "ASTROMETRY"
    difficulty: str  # "EASY", "MEDIUM", "HARD"
    requirements: dict  # Es: {"target": "M42", "filters": ["Ha"], "exposure_total": 3600}
    rewards: dict  # {"research_points": 50, "unlock": "FILTER_OIII"}
    
    def check_completion(self, player_data: dict) -> bool:
        """Verifica se task è completato"""
        pass

class TaskManager:
    """Gestore task e progressione"""
    
    def __init__(self):
        self.available_tasks = self._load_tasks_database()
    
    def get_available_tasks(self, career_state: CareerState) -> list[Task]:
        """Task disponibili per livello giocatore"""
        pass
    
    def complete_task(self, task_id: str, career_state: CareerState):
        """Completa task e assegna ricompense"""
        pass

@dataclass
class Discovery:
    """Scoperta scientifica"""
    discovery_id: str
    object_type: str  # "ASTEROID", "COMET", "VARIABLE", "EXOPLANET"
    designation: str  # Es: "2024 AB123"
    discovery_date: datetime
    confirmation_date: Optional[datetime]
    confirmed: bool
    research_points_awarded: int
    object_data: dict  # Dati specifici dell'oggetto

@dataclass
class Publication:
    """Pubblicazione scientifica virtuale"""
    pub_id: str
    title: str
    journal: str  # "Minor Planet Circular", "AAVSO", etc.
    publish_date: datetime
    objects: list[str]  # ID oggetti coinvolti
    citation_count: int  # Citazioni ricevute
```

---

## 🎮 Game Flow

### Sandbox Mode
```
START
  ↓
[Main Menu] → Select "Sandbox"
  ↓
[Observatory Hub]
  ├─→ [Sky Chart] → Select target → Back to Hub
  ├─→ [Imaging] → Acquire data → Process → Analyze → Save results
  ├─→ [Catalog Browser] → Search objects → Set as target
  └─→ [Equipment] → Change telescope/camera/filters
```

### Career Mode
```
START
  ↓
[Main Menu] → Select "Career" (New/Load)
  ↓
[Observatory Hub] (mostra research points, active tasks)
  ├─→ [Tasks] → Accept task → Back to Hub
  ├─→ [Sky Chart] → Plan observation
  ├─→ [Imaging] → Complete task objective → Gain points
  ├─→ [Equipment] → Buy upgrade (if enough points)
  ├─→ [Discoveries] → Log discoveries → Submit for confirmation
  └─→ [Publications] → Review published work
  
PROGRESSION:
  Task completion → Research points → Buy better equipment
  Discoveries → Bonus points + Achievements
  Publications → Prestige + Unlock advanced tasks
```

---

## 🎨 Stile Grafico DOS/VGA

### Palette Colori
```python
# Palette principale (VGA-inspired)
COLORS = {
    'bg_dark': (0, 12, 10),
    'bg_panel': (0, 20, 15),
    'fg_green': (0, 255, 120),      # Testo principale
    'fg_dim': (0, 180, 80),         # Testo secondario
    'accent_cyan': (0, 255, 255),   # Highlights
    'accent_yellow': (255, 255, 0), # Warnings/important
    'accent_red': (255, 60, 60),    # Errors/critical
    
    # Stelle (temperatura colore)
    'star_blue': (180, 200, 255),
    'star_white': (255, 255, 255),
    'star_yellow': (255, 240, 180),
    'star_orange': (255, 200, 120),
    'star_red': (255, 150, 100),
}
```

### UI Elements
- Font monospaziato (Consolas 14-20px)
- Bordi pannelli pixelati 2px
- Bottoni con outline e highlight on-hover
- Progress bars con dithering
- ASCII art per loghi/decorazioni

### Rendering Oggetti
- Stelle: 1-4 pixel, colori temperatura
- Nebulose: Texture 64x64 o 128x128, procedural noise
- Galassie: 32x32 a 256x256, forme geometriche + noise
- Pianeti: 8x8 a 64x64, sprite stylizzati
- Comete: Trail procedurale

---

## 🔬 Accuratezza Scientifica

### Coordinate e Tempo
- Precisione: 1 arcsec (sufficiente per amatoriale)
- Ignora precessione/nutazione (errore <0.1° su 10 anni)
- JD accuracy: 1 secondo

### Imaging
- Noise model fisicamente plausibile
- Calibrazione standard professionale
- Stacking algorithms corretti
- Magnitudes accurate ±0.1 mag

### Orbite
- Keplerian elements (no relatività)
- Perturbazioni ordine 1 (Sole-Giove per asteroidi)
- Effemeridi planetarie VSOP87 semplificato (accuracy ~1 arcmin)

---

## 📊 Performance Targets

- **Framerate**: 60 FPS costanti
- **Star queries**: < 5ms per region (100k stars)
- **Rendering DSO**: < 10ms per object (cached textures)
- **Imaging stacking**: < 2s per 10 frames 512x512
- **Orbit calculation**: < 1ms per oggetto
- **Memory footprint**: < 500MB (con cataloghi)

---

## 🗺️ Roadmap Implementazione

### Phase 1: Core Integration (2-3 settimane)
✅ Merge astro2.py imaging system
✅ Create base UI framework (BaseScreen)
✅ Implement Observatory Hub
✅ Integrate Sky Chart with Imaging
✅ Basic catalog browser

### Phase 2: Catalogs & Rendering (2-3 settimane)
⚠️ Implement StarCatalog (Hipparcos + Gaia)
⚠️ Expand DSO rendering (all types)
⚠️ Solar system basic (planets + moon)
⚠️ Procedural asteroids/comets
⚠️ Sky renderer complete

### Phase 3: Imaging Complete (2 settimane)
⚠️ Full camera simulation
⚠️ Calibration pipeline
⚠️ Stacking engine
⚠️ Post-processing tools
⚠️ Basic photometry/astrometry

### Phase 4: Physics & Discovery (2 settimane)
⚠️ Orbital mechanics
⚠️ Ephemeris calculator
⚠️ Discovery system (blink comparator)
⚠️ Track & confirm algorithm

### Phase 5: Career Mode (3 settimane)
⚠️ Equipment database
⚠️ Task system
⚠️ Progression mechanics
⚠️ Discovery tracking
⚠️ Publications

### Phase 6: Polish (2 settimane)
⚠️ Tutorial system
⚠️ Sound effects (ambient)
⚠️ Atmospheric effects
⚠️ Save/Load system
⚠️ Achievements

**TOTAL ESTIMATED**: 12-15 settimane sviluppo

---

## 🚀 Next Steps Immediati

1. **Refactor astro2.py** → Split in moduli `imaging/*`
2. **Create BaseScreen** → Framework UI comune
3. **Implement ObservatoryScreen** → Hub centrale
4. **Integrate imaging** → Screen imaging con pipeline completa
5. **Test workflow** → Flow completo Sky Chart → Target → Imaging

---

Questa architettura fornisce una **base solida e scalabile** per costruire il tuo simulatore astronomico. Ogni modulo è **indipendente e testabile**, e l'integrazione è **progressiva**.

Vuoi che proceda con l'implementazione di una fase specifica? Consiglio di iniziare con **Phase 1** (Core Integration).
