# Observatory Simulation Game - Sprint 1 Deliverables

## 📦 Contenuto Archivio

Questo archivio contiene tutto il lavoro completato durante lo **Sprint 1** del progetto.

### File Inclusi:

```
observatory_game_complete_sprint1.tar.gz
├── ARCHITECTURE.md              # Architettura completa del progetto
├── IMPLEMENTATION_PLAN.md       # Piano di implementazione 6 sprint
├── SPRINT1_PROGRESS.md          # Report progressi Sprint 1
│
├── imaging/                     # Sistema imaging completo (7 moduli)
│   ├── __init__.py
│   ├── noise_model.py          # Generazione noise realistico
│   ├── frames.py               # Gestione frame e metadata
│   ├── camera.py               # Simulazione CCD/CMOS
│   ├── calibration.py          # Pipeline calibrazione
│   ├── stacking.py             # Allineamento e stacking
│   └── processing.py           # Post-processing immagini
│
└── ui_new/                      # Framework UI (parziale)
    └── theme.py                # Tema VGA e componenti base
```

---

## 🚀 Come Usare i File

### 1. Estrazione

```bash
# Estrai l'archivio
tar -xzf observatory_game_complete_sprint1.tar.gz

# Oppure su Windows con 7-Zip/WinRAR
# Click destro → Estrai qui
```

### 2. Struttura Directory Consigliata

Crea una directory per il progetto e integra i file:

```bash
mkdir observatory_game
cd observatory_game

# Copia i file estratti
cp -r path/to/extracted/* .

# Struttura finale desiderata:
observatory_game/
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── SPRINT1_PROGRESS.md
├── README.md
├── requirements.txt
│
├── core/                    # Moduli core esistenti
│   ├── coords.py
│   ├── astro_time.py
│   └── ...
│
├── catalogs/               # Cataloghi astronomici
│   ├── deep_sky.py
│   └── procedural.py
│
├── rendering/              # Rendering pixelart
│   └── nebula_renderer.py
│
├── imaging/                # ✅ NUOVO (da Sprint 1)
│   ├── __init__.py
│   ├── noise_model.py
│   ├── frames.py
│   ├── camera.py
│   ├── calibration.py
│   ├── stacking.py
│   └── processing.py
│
├── ui/                     # UI screens
│   ├── base_screen.py      # TODO: da creare
│   ├── components.py       # TODO: da creare
│   ├── theme.py            # ✅ NUOVO (da Sprint 1)
│   └── ...
│
├── game/                   # Game logic
│   └── state_manager.py    # TODO: da creare
│
└── main.py                 # Entry point
```

### 3. Setup Ambiente Python

```bash
# Crea virtual environment
python -m venv venv

# Attiva (Linux/Mac)
source venv/bin/activate

# Attiva (Windows)
venv\Scripts\activate

# Installa dipendenze
pip install pygame numpy scipy
```

### 4. Requisiti

**Python**: 3.11+ (3.10 potrebbe funzionare)

**Dipendenze**:
```txt
pygame >= 2.5.0
numpy >= 1.24.0
scipy >= 1.10.0
```

---

## 📖 Documenti da Leggere (in ordine)

### 1. **ARCHITECTURE.md** (Primo da leggere!)
- Visione completa del progetto
- Architettura modulare dettagliata
- Specifiche di ogni modulo
- Stile grafico e accuratezza scientifica

### 2. **IMPLEMENTATION_PLAN.md**
- Piano di sviluppo in 6 sprint (8 settimane)
- Task dettagliati con priorità
- Milestone e deliverable
- Quick start guide per sviluppatori

### 3. **SPRINT1_PROGRESS.md**
- Cosa è stato completato in Sprint 1
- Metriche e statistiche
- Prossimi passi
- Technical debt

---

## 🔬 Sistema Imaging - Quick Reference

Il nuovo sistema imaging è il cuore del progetto. Ecco come usarlo:

### Esempio Base: Acquisizione e Calibrazione

```python
from imaging.camera import get_camera
from imaging.frames import FrameMetadata, FrameType
from imaging.calibration import Calibrator
from imaging.stacking import StackingEngine, StackMethod
import numpy as np

# 1. Crea camera
camera = get_camera("ZWO_ASI294MC", seed=42)
camera.set_cooling(True, target_temp_c=-10.0)

# 2. Genera segnale cielo (esempio)
h, w = camera.spec.resolution[1], camera.spec.resolution[0]
sky_signal = np.random.poisson(1000, size=(h, w)).astype(np.float32)

# 3. Acquisisci frames
light_frames = []
for i in range(10):
    meta = FrameMetadata(
        frame_type=FrameType.LIGHT,
        exposure_s=30.0,
        target_name="M42"
    )
    frame = camera.capture_frame(30.0, sky_signal, FrameType.LIGHT, 
                                 frame_seed=i, metadata=meta)
    light_frames.append(frame)

# 4. Acquisisci dark frames
dark_frames = []
for i in range(5):
    dark = camera.capture_dark_frame(30.0, frame_seed=100+i)
    dark_frames.append(dark)

# 5. Crea master dark
calibrator = Calibrator()
master_dark = calibrator.create_master_dark(dark_frames)

# 6. Calibra light frames
calibrated = calibrator.batch_calibrate_lights(light_frames, 
                                               master_dark=master_dark)

# 7. Stacka
stacker = StackingEngine()
stacked = stacker.stack(calibrated, method=StackMethod.SIGMA_CLIP)

# 8. Processing
from imaging.processing import ImageProcessor
processed = ImageProcessor.auto_stretch(stacked)

print(f"Stacked image shape: {stacked.shape}")
print(f"SNR improvement: {stacker.compute_snr_improvement(10, StackMethod.SIGMA_CLIP):.2f}x")
```

### Esempio: Colori Narrowband

```python
from imaging.processing import ColorProcessor
import numpy as np

# Simula canali narrowband
ha = np.random.rand(512, 512).astype(np.float32)
oiii = np.random.rand(512, 512).astype(np.float32)
sii = np.random.rand(512, 512).astype(np.float32)

# Combina in Hubble palette
rgb = ColorProcessor.combine_narrowband_SHO(sii, ha, oiii)

# Aumenta saturazione
rgb_boosted = ColorProcessor.apply_saturation(rgb, saturation=1.5)
```

---

## 🎨 UI Theme - Quick Reference

```python
from ui.theme import get_theme, Colors
import pygame

# Inizializza
pygame.init()
screen = pygame.display.set_mode((1280, 800))
theme = get_theme()

# Usa colori
bg = Colors.BG_DARK
fg = Colors.FG_PRIMARY

# Disegna pannello
rect = pygame.Rect(100, 100, 400, 300)
theme.draw_panel(screen, rect)

# Disegna testo (no antialiasing)
theme.draw_text(screen, theme.fonts.normal(), 
                120, 120, "OBSERVATORY", Colors.FG_PRIMARY)

# Progress bar
progress_rect = pygame.Rect(120, 150, 360, 20)
theme.draw_progress_bar(screen, progress_rect, 0.75)
```

---

## 🔧 Testing (TODO Sprint 1 Completion)

Unit tests da creare:

```bash
# Struttura tests
tests/
├── test_noise_model.py
├── test_frames.py
├── test_camera.py
├── test_calibration.py
├── test_stacking.py
└── test_processing.py

# Run tests
pytest tests/ -v
```

---

## 📊 Stato Attuale del Progetto

### ✅ Completato (Sprint 1, 70%)
- Sistema imaging completo (7 moduli)
- Framework UI base (theme)
- Documentazione architetturale
- Piano implementazione dettagliato

### 🔄 In Progress (Sprint 1, 30%)
- UI components (Button, Panel, TextInput, etc.)
- BaseScreen abstract class
- Observatory Hub screen
- Game State Manager

### ⚠️ TODO (Sprint 2+)
- Imaging Screen completa con preview
- Integrazione Sky Chart
- Catalog browser
- Equipment management
- Career mode
- Task system
- Discovery system
- Solar system

---

## 🎯 Next Steps

### Per Completare Sprint 1 (2-3 giorni):

1. **Creare UI Components** (`ui/components.py`)
   - Button, Panel, TextInput, ScrollList
   - BaseScreen abstract class

2. **Observatory Hub Screen** (`ui/screen_observatory.py`)
   - Layout principale con 4 bottoni
   - Status display
   - Navigation

3. **Game State Manager** (`game/state_manager.py`)
   - Screen navigation con stack
   - State persistence

4. **Demo & Testing**
   - Script demo funzionante
   - Unit tests iniziali

### Per Sprint 2 (1-2 settimane):
- Imaging Screen completa
- Live acquisition simulation
- Full processing pipeline UI
- Export capabilities

---

## 📞 Support & Resources

### Documentazione Interna:
- `ARCHITECTURE.md` - Architettura completa
- `IMPLEMENTATION_PLAN.md` - Roadmap 6 sprint
- `SPRINT1_PROGRESS.md` - Progress report

### Codice:
- `imaging/*.py` - Sistema imaging (tutto documentato con docstrings)
- `ui/theme.py` - Theme VGA

### External Resources:
- **Astronomy**: Meeus "Astronomical Algorithms"
- **Imaging**: Deep-sky imaging guides
- **Python**: NumPy, SciPy documentation
- **Game Dev**: Pygame documentation

---

## 🎮 Vision del Progetto

Un simulatore astronomico retrò (DOS/VGA style) che combina:
- **Astronomia reale**: Cataloghi stellari, DSO, sistema solare
- **Imaging scientifico**: Pipeline completa acquisizione → elaborazione
- **Gameplay**: Sandbox mode + Career mode con progressione
- **Scoperta**: Asteroidi, comete, esopianeti da trovare
- **Stile pixelart**: Realistico ma con estetica VGA

**Target**: Appassionati di astronomia + retro gaming enthusiasts

---

## 🤝 Contributi

Il progetto è in fase alpha (Sprint 1).

Aree dove contribuire:
- Unit tests (priorità alta!)
- UI components
- Additional camera specs
- Catalog data
- Sprite pixelart
- Documentation

---

## 📝 Changelog

### Sprint 1 (Current)
- ✅ Sistema imaging completo (7 moduli)
- ✅ Framework UI base (theme)
- ✅ Documentazione strategica
- 🔄 UI components (in progress)
- 🔄 Observatory Hub (in progress)

---

## 📄 License

MIT License (da confermare)

---

**Buon coding! 🚀✨**

Per domande o supporto, consulta la documentazione o apri una issue nel repository.
