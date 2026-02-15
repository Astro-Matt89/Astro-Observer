# Piano di Implementazione - Observatory Simulation Game

## 🎯 Obiettivo Principale
Creare un simulatore astronomico giocabile con:
- Sistema di imaging completo e realistico (da astro2.py)
- Cataloghi stellari e deep-sky integrati
- Modalità Career con progressione
- Stile grafico retrò DOS/VGA coerente

---

## 📋 Sprint Plan (Iterativo)

### SPRINT 1 (Settimana 1): Core Refactoring ✅ CRITICO
**Obiettivo**: Refactorizzare astro2.py e creare framework UI base

#### Task 1.1: Split Imaging System
**Priorità**: ALTA
**Tempo**: 2 giorni

File da creare:
```
imaging/
├── __init__.py
├── camera.py          # CameraSpec, Camera class
├── frames.py          # Frame, FrameMetadata
├── calibration.py     # Calibrator class
├── stacking.py        # StackingEngine
├── processing.py      # ImageProcessor
└── noise_model.py     # Noise generation utilities
```

**Specifiche**:
- Estrarre logica imaging da astro2.py
- Mantenere API compatibile
- Aggiungere tests unitari base
- Documentare tutte le funzioni

**Deliverable**: Moduli imaging funzionanti e testati

---

#### Task 1.2: Create UI Framework
**Priorità**: ALTA
**Tempo**: 2 giorni

File da creare:
```
ui/
├── base_screen.py     # BaseScreen abstract class
├── ui_components.py   # Panel, Button, TextBox, etc.
└── theme.py           # Color scheme, fonts
```

**Specifiche BaseScreen**:
```python
class BaseScreen(ABC):
    def __init__(self, state: GameState):
        self.state = state
        self.active = False
    
    @abstractmethod
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        """Returns next screen name or None"""
        pass
    
    @abstractmethod
    def update(self, dt: float):
        pass
    
    @abstractmethod
    def render(self, screen: pygame.Surface):
        pass
    
    def on_enter(self):
        """Called when screen becomes active"""
        self.active = True
    
    def on_exit(self):
        """Called when screen becomes inactive"""
        self.active = False
```

**Componenti UI da implementare**:
- `Panel`: Pannello con bordo VGA-style
- `Button`: Bottone interattivo con hover
- `TextInput`: Input text monospacer
- `ScrollableList`: Lista scrollabile (per cataloghi)
- `ProgressBar`: Barra progresso
- `InfoBox`: Box info multi-riga

**Deliverable**: Framework UI riutilizzabile per tutte le schermate

---

#### Task 1.3: Observatory Hub Screen
**Priorità**: ALTA
**Tempo**: 2 giorni

File: `ui/screen_observatory.py`

**Layout**:
```
┌────────────────────────────────────────────────────┐
│ OBSERVATORY CONTROL CENTER                         │
│ Location: Parma, IT  |  2026-02-08 19:30 UTC      │
│ LST: 14:32:45        |  Target: M42 (Orion Neb)   │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌──────────────┐  ┌──────────────┐              │
│  │  SKY CHART   │  │   IMAGING    │              │
│  │              │  │              │              │
│  │  [Navigate]  │  │  [Acquire]   │              │
│  └──────────────┘  └──────────────┘              │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐              │
│  │  CATALOGS    │  │  EQUIPMENT   │              │
│  │              │  │              │              │
│  │  [Browse]    │  │  [Manage]    │              │
│  └──────────────┘  └──────────────┘              │
│                                                    │
│  ┌────────────────────────────────┐              │
│  │ CURRENT SETUP:                 │              │
│  │ • Telescope: Newtonian 150mm   │              │
│  │ • Camera: ZWO ASI294MC         │              │
│  │ • Filter: None                 │              │
│  └────────────────────────────────┘              │
│                                                    │
│ [1] Sky Chart  [2] Imaging  [3] Catalogs         │
│ [4] Equipment  [ESC] Quit                         │
└────────────────────────────────────────────────────┘
```

**Funzionalità**:
- Navigazione tra schermate (1-4 keys)
- Display info osservatorio
- Display setup corrente
- Clock real-time
- Quick actions

**Deliverable**: Hub navigabile funzionante

---

#### Task 1.4: Game State Manager
**Priorità**: MEDIA
**Tempo**: 1 giorno

File: `game/state_manager.py`

```python
class GameStateManager:
    """Gestisce stato globale e transizioni"""
    
    def __init__(self):
        self.state = GameState()
        self.screens: dict[str, BaseScreen] = {}
        self.current_screen: Optional[str] = None
        self.screen_stack: list[str] = []  # Per back navigation
    
    def register_screen(self, name: str, screen: BaseScreen):
        self.screens[name] = screen
    
    def switch_to(self, screen_name: str, push_stack: bool = True):
        if self.current_screen and push_stack:
            self.screen_stack.append(self.current_screen)
        
        if self.current_screen:
            self.screens[self.current_screen].on_exit()
        
        self.current_screen = screen_name
        self.screens[screen_name].on_enter()
    
    def go_back(self):
        if self.screen_stack:
            prev = self.screen_stack.pop()
            self.switch_to(prev, push_stack=False)
    
    def update(self, dt: float):
        if self.current_screen:
            self.screens[self.current_screen].update(dt)
    
    def render(self, screen: pygame.Surface):
        if self.current_screen:
            self.screens[self.current_screen].render(screen)
    
    def handle_input(self, events: list[pygame.event.Event]):
        if self.current_screen:
            next_screen = self.screens[self.current_screen].handle_input(events)
            if next_screen:
                self.switch_to(next_screen)
```

**Deliverable**: State manager con screen navigation

---

### SPRINT 2 (Settimana 2): Imaging Screen Complete
**Obiettivo**: Interfaccia imaging completa e funzionale

#### Task 2.1: Imaging Screen Base
**Priorità**: ALTA
**Tempo**: 3 giorni

File: `ui/screen_imaging.py`

**Layout** (ispirato a astro2.py):
```
┌────────────────────────────────────────────────────────────────────┐
│ IMAGING SESSION                                     [ESC] Back     │
├──────────────────────┬─────────────────────────────────────────────┤
│ CONTROL PANEL        │  PREVIEW / ANALYSIS                         │
│                      │                                             │
│ Target: M42          │  ┌─────────────────────────────────────┐  │
│ RA: 05:35:16         │  │                                     │  │
│ Dec: -05:23:28       │  │         [Image Display]             │  │
│                      │  │                                     │  │
│ ┌──────────────────┐ │  │                                     │  │
│ │ ACQUISITION      │ │  └─────────────────────────────────────┘  │
│ ├──────────────────┤ │                                             │
│ │ [G] Start        │ │  Mode: RAW | CAL | STACK                   │
│ │ [S] Stop         │ │  Frame: 5/10 | Exp: 30s | SNR: 15.2       │
│ │ [C] Calibrate    │ │                                             │
│ │ [K] Stack        │ │  ┌─────────────────────────────────────┐  │
│ └──────────────────┘ │  │ HISTOGRAM                           │  │
│                      │  │ [Press H to toggle]                 │  │
│ Frames:              │  └─────────────────────────────────────┘  │
│ • Light: 10          │                                             │
│ • Dark: 5            │  Stretch: [−/=] Black [,/.] White          │
│ • Flat: 5            │  Black: 0.002  White: 0.850  Gamma: 2.2   │
│ • Bias: 10           │                                             │
│                      │                                             │
│ ┌──────────────────┐ │  [1] Raw  [2] Calibrated  [3] Stacked     │
│ │ PROCESSING       │ │  [←/→] Prev/Next Frame                     │
│ ├──────────────────┤ │  [P] Save PNG  [F] Save FITS               │
│ │ [ ] Auto-stretch │ │                                             │
│ │ [ ] Sharpen      │ │                                             │
│ │ [ ] Denoise      │ │                                             │
│ └──────────────────┘ │                                             │
└──────────────────────┴─────────────────────────────────────────────┘
```

**Funzionalità Sprint 2**:
- [x] Selezione target (from sky chart)
- [x] Generate dataset (Light/Dark/Flat/Bias)
- [x] View raw/calibrated/stacked
- [x] Frame navigation
- [x] Histogram toggle
- [x] Manual stretch controls
- [x] Export PNG

**Deliverable**: Imaging screen base funzionante

---

#### Task 2.2: Live Acquisition Mode
**Priorità**: MEDIA
**Tempo**: 2 giorni

**Features**:
- Simulazione acquisizione real-time
- Progress bar per esposizione
- Preview frame durante capture
- Abort capability
- Auto-save frames

**Pseudo-codice**:
```python
class AcquisitionSession:
    def __init__(self, target, camera, telescope):
        self.target = target
        self.camera = camera
        self.telescope = telescope
        self.is_running = False
        self.frames_captured = 0
    
    def start_light_sequence(self, n_frames: int, exposure_s: float):
        self.is_running = True
        for i in range(n_frames):
            if not self.is_running:
                break
            
            # Simulate exposure delay
            yield {"status": "EXPOSING", "progress": 0.0, "frame": i+1}
            
            for t in range(int(exposure_s * 10)):  # 0.1s steps
                if not self.is_running:
                    break
                yield {"status": "EXPOSING", "progress": t/(exposure_s*10), "frame": i+1}
                time.sleep(0.1)
            
            # Capture frame
            frame = self.camera.capture_frame(...)
            yield {"status": "READOUT", "frame": i+1, "data": frame}
            
            self.frames_captured += 1
        
        self.is_running = False
        yield {"status": "COMPLETE", "total_frames": self.frames_captured}
    
    def abort(self):
        self.is_running = False
```

**Deliverable**: Live acquisition mode funzionante

---

#### Task 2.3: Analysis Tools
**Priorità**: BASSA (può slittare a Sprint 3)
**Tempo**: 2 giorni

**Features**:
- Aperture photometry (click su stella)
- FWHM measurement (seeing quality)
- Star count histogram
- SNR map

**UI Addition**:
```
┌─────────────────────────────────────┐
│ ANALYSIS TOOLS                      │
├─────────────────────────────────────┤
│ [A] Aperture Photometry             │
│ [M] Measure FWHM                    │
│ [D] Detect Stars                    │
│ [B] Background Statistics           │
└─────────────────────────────────────┘

Analysis Results:
• Detected stars: 342
• Median FWHM: 2.8 px (3.1")
• Background: 1523 ADU (σ=125)
• Peak SNR: 45.2
```

**Deliverable**: Basic analysis tools

---

### SPRINT 3 (Settimana 3): Catalogs & Sky Chart Integration
**Obiettivo**: Cataloghi completi e integrazione con imaging

#### Task 3.1: Star Catalog Implementation
**Priorità**: ALTA
**Tempo**: 3 giorni

File: `catalogs/stars.py`

**Features**:
- Caricamento Hipparcos index
- Caricamento Gaia DR3 index
- LOD query automatico
- Colori da temperatura (B-V)

```python
class StarCatalog:
    def query_stars(self, ra_center, dec_center, radius_deg, 
                   fov_deg=None, mag_limit=None) -> list[Star]:
        """Smart query con LOD"""
        
        if fov_deg is None:
            # Auto-determine LOD from radius
            if radius_deg > 30:
                # Wide field: only brightest
                return self._query_hipparcos(ra_center, dec_center, radius_deg, mag_limit=6.0)
            elif radius_deg > 5:
                # Medium field: Hipparcos + bright Gaia
                hip = self._query_hipparcos(ra_center, dec_center, radius_deg, mag_limit=8.0)
                gaia = self._query_gaia(ra_center, dec_center, radius_deg, mag_limit=9.0)
                return hip + gaia
            else:
                # Narrow field: Full Gaia
                return self._query_gaia(ra_center, dec_center, radius_deg, mag_limit=mag_limit or 12.0)
        
        # Manual LOD override
        if fov_deg > 30:
            return self._query_hipparcos(ra_center, dec_center, radius_deg, mag_limit)
        else:
            return self._query_gaia(ra_center, dec_center, radius_deg, mag_limit)
```

**Deliverable**: Star catalog funzionante con Hipparcos + Gaia

---

#### Task 3.2: Enhanced Sky Chart
**Priorità**: ALTA
**Tempo**: 2 giorni

Miglioramenti a `ui/screen_skychart.py`:
- Integrazione StarCatalog
- Render stelle con colori temperatura
- Click su stella → Set as target
- Info panel con dati stella
- Export target to imaging

**UI Addition**:
```
┌─────────────────────────────────────┐
│ SELECTED: HIP 27989 (Betelgeuse)    │
├─────────────────────────────────────┤
│ RA: 05:55:10.3  Dec: +07:24:25.4   │
│ Mag: 0.42 (variable)                │
│ Spectral type: M1-2 Ia-Iab          │
│ Distance: 548 ly                    │
│                                     │
│ [I] Image Target                    │
│ [M] More Info                       │
└─────────────────────────────────────┘
```

**Deliverable**: Sky chart integrato con catalogo stelle

---

#### Task 3.3: Catalog Browser Screen
**Priorità**: MEDIA
**Tempo**: 2 giorni

File: `ui/screen_catalog.py`

**Layout**:
```
┌────────────────────────────────────────────────────────────────────┐
│ CATALOG BROWSER                                    [ESC] Back      │
├──────────────────────┬─────────────────────────────────────────────┤
│ FILTERS              │  RESULTS (234 objects)                      │
│                      │                                             │
│ Type:                │  Name         Type    Mag    Size    Dist   │
│ [x] Stars            │  ───────────────────────────────────────────│
│ [x] Nebulae          │  M42          Neb-E   4.0    85'    1344ly │
│ [x] Galaxies         │  M31          Gal-Sb  3.4    178'   2.5Mly │
│ [ ] Clusters         │  Sirius       Star    -1.46  -      8.6ly  │
│ [ ] Planets          │  Betelgeuse   Star    0.42   -      548ly  │
│                      │  M13          Glo-Cl  5.8    20'    22kly  │
│ Magnitude:           │  ...                                        │
│ Min: [ 0.0 ]         │                                             │
│ Max: [12.0 ]         │  ▲ Scroll ▼                                │
│                      │                                             │
│ Sort by:             │                                             │
│ ( ) Name             │  ┌─────────────────────────────────────┐  │
│ (•) Magnitude        │  │ SELECTED: M42 (Orion Nebula)        │  │
│ ( ) Distance         │  ├─────────────────────────────────────┤  │
│ ( ) Size             │  │ Type: Emission Nebula (HII region)  │  │
│                      │  │ RA/Dec: 05:35:17 / -05:23:28        │  │
│ Search:              │  │ Magnitude: 4.0                      │  │
│ [______________]     │  │ Size: 85' × 60'                     │  │
│                      │  │ Distance: 1344 light-years          │  │
│ [Apply Filters]      │  │                                     │  │
│                      │  │ [V] View in Sky Chart               │  │
│                      │  │ [I] Image Target                    │  │
│                      │  └─────────────────────────────────────┘  │
└──────────────────────┴─────────────────────────────────────────────┘
```

**Deliverable**: Catalog browser funzionante

---

### SPRINT 4 (Settimana 4): Equipment & Career Foundation
**Obiettivo**: Sistema equipaggiamento e base career mode

#### Task 4.1: Equipment System
**Priorità**: ALTA
**Tempo**: 3 giorni

Files:
- `game/equipment.py` - Specs e database
- `data/equipment/telescopes.json`
- `data/equipment/cameras.json`
- `data/equipment/filters.json`

**Telescope Database** (esempio):
```json
{
  "telescopes": [
    {
      "id": "REF_80_F5",
      "name": "Refractor 80mm f/5",
      "type": "REFRACTOR",
      "aperture_mm": 80,
      "focal_length_mm": 400,
      "focal_ratio": 5.0,
      "obstruction_pct": 0.0,
      "weight_kg": 3.0,
      "price": 500,
      "tier": "BEGINNER",
      "unlocked_at_start": true
    },
    {
      "id": "NEWT_150_F5",
      "name": "Newtonian 150mm f/5",
      "type": "REFLECTOR",
      "aperture_mm": 150,
      "focal_length_mm": 750,
      "focal_ratio": 5.0,
      "obstruction_pct": 20.0,
      "weight_kg": 8.0,
      "price": 2000,
      "tier": "INTERMEDIATE",
      "unlocked_at_start": false
    }
  ]
}
```

**Deliverable**: Equipment system con database

---

#### Task 4.2: Equipment Screen
**Priorità**: ALTA
**Tempo**: 2 giorni

File: `ui/screen_equipment.py`

**Layout**:
```
┌────────────────────────────────────────────────────────────────────┐
│ EQUIPMENT MANAGER                                  [ESC] Back      │
├──────────────────────┬─────────────────────────────────────────────┤
│ OWNED EQUIPMENT      │  SPECIFICATIONS                             │
│                      │                                             │
│ TELESCOPES:          │  ┌─────────────────────────────────────┐  │
│ > Refractor 80mm f/5 │  │ Newtonian 150mm f/5                 │  │
│   Newtonian 150mm f/5│  ├─────────────────────────────────────┤  │
│   (locked)           │  │ Type: Newtonian Reflector           │  │
│                      │  │ Aperture: 150mm (6")                │  │
│ CAMERAS:             │  │ Focal Length: 750mm                 │  │
│ > Webcam Modified    │  │ Focal Ratio: f/5.0                  │  │
│   ZWO ASI294MC       │  │ Obstruction: 20%                    │  │
│   (locked)           │  │                                     │  │
│                      │  │ Performance:                        │  │
│ FILTERS:             │  │ • Resolution: 0.92 arcsec           │  │
│   None owned         │  │ • Light grasp: 459x eye             │  │
│                      │  │ • Limiting mag: 13.2 (60s)          │  │
│ ┌──────────────────┐ │  │                                     │  │
│ │ SHOP (Career)    │ │  │ Price: 2000 RP                      │  │
│ ├──────────────────┤ │  │ Status: LOCKED                      │  │
│ │ Research Points: │ │  │ Unlock: Complete 5 tasks            │  │
│ │ 1250 RP          │ │  │                                     │  │
│ │                  │ │  │ [B] Buy (not enough RP)             │  │
│ │ [Browse Shop]    │ │  │ [E] Equip (if owned)                │  │
│ └──────────────────┘ │  └─────────────────────────────────────┘  │
└──────────────────────┴─────────────────────────────────────────────┘
```

**Deliverable**: Equipment screen con shop (career mode)

---

#### Task 4.3: Career State & Progression
**Priorità**: MEDIA
**Tempo**: 2 giorni

File: `game/career_mode.py`

**CareerState**:
```python
@dataclass
class CareerState:
    # Resources
    research_points: int = 0
    
    # Equipment
    owned_telescopes: list[str] = field(default_factory=lambda: ["REF_80_F5"])
    owned_cameras: list[str] = field(default_factory=lambda: ["WEBCAM_MOD"])
    owned_filters: list[str] = field(default_factory=list)
    
    current_telescope: str = "REF_80_F5"
    current_camera: str = "WEBCAM_MOD"
    current_filter: Optional[str] = None
    
    # Progress
    tasks_completed: list[str] = field(default_factory=list)
    tasks_active: list[str] = field(default_factory=list)
    
    # Discoveries
    asteroids_discovered: list[str] = field(default_factory=list)
    comets_discovered: list[str] = field(default_factory=list)
    variables_discovered: list[str] = field(default_factory=list)
    
    # Stats
    total_exposures: int = 0
    total_integration_time_s: float = 0.0
    objects_imaged: set[str] = field(default_factory=set)
    
    # Unlocks
    unlocked_features: set[str] = field(default_factory=set)
```

**Progression Formulas**:
```python
def calculate_research_points(action: str, **kwargs) -> int:
    """Calculate RP for various actions"""
    
    if action == "COMPLETE_TASK":
        difficulty = kwargs['difficulty']
        return {'EASY': 50, 'MEDIUM': 150, 'HARD': 300}[difficulty]
    
    elif action == "DISCOVER_ASTEROID":
        return 200
    
    elif action == "DISCOVER_COMET":
        return 500
    
    elif action == "CONFIRM_VARIABLE":
        return 100
    
    elif action == "IMAGE_DEEP_SKY":
        # Bonus for difficult targets
        target_mag = kwargs['magnitude']
        integration_hours = kwargs['integration_time_s'] / 3600
        return int(10 * integration_hours * (12 - target_mag))
```

**Deliverable**: Career progression system base

---

### SPRINT 5 (Settimana 5-6): Solar System & Discovery
**Obiettivo**: Sistema solare e meccanica scoperta asteroidi

*(Dettagli in documento separato se necessario)*

Key features:
- Orbital mechanics (Keplero)
- Ephemeris calculator (pianeti)
- Procedural asteroids
- Blink comparator
- Discovery confirmation

---

### SPRINT 6 (Settimana 7-8): Tasks & Career Polish
**Obiettivo**: Task system completo e gameplay loop

*(Dettagli in documento separato)*

Key features:
- Task database
- Task screen UI
- Completion detection
- Reward system
- Achievement tracking

---

## 🎯 Milestone Targets

### Milestone 1: "Playable Imaging Demo" (End Sprint 2)
✅ Può fare:
- Navigare tra Observatory → Sky Chart → Imaging
- Selezionare target dal cielo
- Acquisire frames (light/dark/flat)
- Calibrare e stackare
- Visualizzare risultati
- Salvare immagini

### Milestone 2: "Catalog Explorer" (End Sprint 3)
✅ Può fare:
- Browse cataloghi (stelle, DSO)
- Filtrare per tipo/magnitudine
- Visualizzare dettagli oggetti
- Export target a imaging
- Query intelligente stelle (LOD)

### Milestone 3: "Career Foundation" (End Sprint 4)
✅ Può fare:
- Gestire equipaggiamento
- Vedere shop upgrade
- Track research points
- Sistema progressione base
- Unlock telescopi migliori

### Milestone 4: "Discovery System" (End Sprint 5)
✅ Può fare:
- Scoprire asteroidi procedurali
- Tracking orbite
- Conferma scoperte
- Logging discoveries
- Submit per pubblicazione

### Milestone 5: "Full Career Loop" (End Sprint 6)
✅ Può fare:
- Completare task scientifici
- Guadagnare RP
- Comprare upgrade
- Fare scoperte
- Pubblicare risultati
- Achievement unlocking

---

## 🔧 Technical Debt Management

### After Each Sprint:
- [ ] Unit tests per nuovi moduli
- [ ] Documentazione funzioni
- [ ] Refactoring codice duplicato
- [ ] Performance profiling
- [ ] Memory leak check

### Code Review Checklist:
- [ ] Naming conventions consistent
- [ ] Type hints everywhere
- [ ] Docstrings per classi/funzioni
- [ ] No hardcoded magic numbers
- [ ] Error handling appropriato
- [ ] Logging where needed

---

## 📊 Success Metrics

### Performance:
- Framerate: ≥ 60 FPS costanti
- Catalog query: < 10ms
- Imaging stack 10x512x512: < 2s
- Memory usage: < 500MB

### Code Quality:
- Test coverage: > 70%
- No critical bugs
- Consistent style (PEP 8)
- Clear documentation

### User Experience:
- Tutorial completabile < 5 min
- Career progression feels rewarding
- Controls intuitive
- Visual style consistent

---

## 🚀 Quick Start (Per sviluppatore)

### Setup Ambiente:
```bash
# Clone repo
git clone [url]
cd observatory_game

# Virtual env
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install deps
pip install -r requirements.txt

# Download catalogs (optional, procedural fallback)
python tools/build_hipparcos_index.py
python tools/build_gaia_index_v2.py
```

### Development Workflow:
```bash
# Run main game
python main.py

# Run specific demo
python demos/demo_imaging.py
python demos/demo_catalog_browser.py

# Run tests
pytest tests/

# Run with profiling
python -m cProfile -o profile.stats main.py
python -c "import pstats; p=pstats.Stats('profile.stats'); p.sort_stats('cumtime').print_stats(20)"
```

### Git Workflow:
```bash
# Feature branch
git checkout -b feature/imaging-screen
# ... develop ...
git add .
git commit -m "feat(imaging): Add live acquisition mode"
git push origin feature/imaging-screen
# Create PR
```

---

## 📞 Support & Communication

### Issues Tracking:
- **Bug**: Qualcosa non funziona
- **Feature**: Nuova funzionalità
- **Enhancement**: Miglioramento esistente
- **Question**: Dubbio implementazione
- **Documentation**: Docs mancante/errata

### Priority Labels:
- `P0-CRITICAL`: Blocca sviluppo
- `P1-HIGH`: Importante, da fare presto
- `P2-MEDIUM`: Importante ma non urgente
- `P3-LOW`: Nice to have
- `P4-SOMEDAY`: Backlog

---

## 🎉 Conclusione

Questo piano fornisce una **roadmap chiara e iterativa** per sviluppare il gioco in **6-8 settimane** di lavoro full-time (o 3-4 mesi part-time).

Ogni sprint è **autocontenuto** e produce **deliverable testabili**.

La priorità è sempre **gameplay loop funzionante** prima di feature avanzate.

**Prosegui quando sei pronto per Sprint 1!**
