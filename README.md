# Observatory Simulation Game

Un simulatore astronomico realistico in stile retrò (DOS VGA, pixelart) per l'osservazione e l'imaging del cielo profondo.

![Version](https://img.shields.io/badge/version-0.1--alpha-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## 🌟 Features

### ✅ Implementate (v0.1)

- **Cataloghi Stellari**
  - Sistema di indicizzazione spaziale per Hipparcos e Gaia DR3
  - Query veloci su regioni di cielo
  - Magnitudine limite dinamica basata su FOV

- **Deep Sky Objects**
  - Catalogo Messier (110 oggetti)
  - Supporto per nebulose (HII, planetarie, riflessione, SNR)
  - Supporto per galassie (spirali, ellittiche, irregolari)
  - Ammassi aperti e globulari

- **Generazione Procedurale**
  - Asteroidi della main belt (distribuzione realistica)
  - Comete periodiche e non-periodiche
  - Nebulose procedurali con texture deterministiche
  - Galassie procedurali

- **Rendering Pixelart Realistico**
  - Nebulose con simulazione filtri (H-alpha, OIII, SII, HOO, SHO)
  - Galassie con bracci spirali, bulge, regioni HII
  - Texture procedurali deterministiche (stesso seed = stessa texture)
  - Colori realistici basati su fisica

- **Sistema Imaging** (da astro2.py)
  - Simulazione CCD/CMOS realistica
  - Light, Dark, Flat, Bias frames
  - Calibrazione completa
  - Stacking (mean, median, sigma-clipping)
  - Stretch istogramma e processing
  - Noise realistico (shot noise, read noise, dark current)

### 🚧 In Sviluppo

- **Interfacce Complete**
  - Sky Chart interattivo (base esistente da integrare)
  - Imaging screen completo
  - Observatory management
  - Catalog browser avanzato

- **Sistema Solare**
  - Effemeridi planetarie accurate
  - Lune, asteroidi, comete
  - Meccaniche orbitali

- **Career Mode**
  - Progressione da piccolo telescopio a osservatorio professionale
  - Sistema di scoperte e pubblicazioni
  - Task scientifici
  - Upgrade equipaggiamento

## 🎮 Come Giocare

### Requisiti

```bash
Python 3.11+
pygame >= 2.5.0
numpy >= 1.24.0
```

### Installazione

```bash
# Clone repository
git clone [url]
cd observatory_game

# Install dependencies
pip install -r requirements.txt

# (Opzionale) Scarica cataloghi completi
python tools/download_catalogs.py
```

### Avvio

```bash
# Main integrato (demo corrente)
python main_integrated.py

# Sistema skychart originale (richiede cataloghi)
python main.py

# Prototipo imaging standalone
python astro2.py
```

### Controlli

#### Globali
- `TAB` - Cambia schermata
- `ESC` - Esci
- `F1` - Aiuto

#### Sky Chart
- `Mouse Wheel` - Zoom
- `+/-` - Velocità tempo
- `[/]` - Step temporale (±10 min)
- `0` - Reset velocità tempo a 1x
- `R` - Reset vista
- Click sinistro - Seleziona stella/oggetto

#### Imaging
- `G` - Genera dataset (light/dark/flat)
- `C` - Calibra e stacka
- `1/2/3` - Visualizza RAW / CAL / STACK
- `[/]` - Frame precedente/successivo
- `H` - Toggle istogramma
- `-/=` - Adjust black point
- `,/.` - Adjust white point

#### Demo
- `1` - Render Messier objects
- `2` - Render nebulose procedurali

## 📁 Struttura Progetto

```
observatory_game/
│
├── core/                      # Sistemi base
│   ├── coords.py              # Coordinate celesti, proiezioni
│   ├── astro_time.py          # Tempo astronomico (JD, LST)
│   ├── catalog_index.py       # Indicizzazione spaziale
│   └── types.py               # Dataclass base
│
├── catalogs/                  # Cataloghi astronomici
│   ├── deep_sky.py            # DSO (Messier, NGC)
│   └── procedural.py          # Generazione procedurale
│
├── rendering/                 # Rendering pixelart
│   └── nebula_renderer.py     # Nebulose, galassie
│
├── imaging/                   # Sistema imaging (da integrare)
│   └── (da astro2.py)
│
├── ui/                        # Interfacce utente
│   ├── screen_skychart.py     # Carta celeste
│   └── screen_planetarium.py  # Planetario
│
├── data/                      # Dati
│   └── catalogs/              # File cataloghi (da scaricare)
│
├── main.py                    # Entry point skychart
├── main_integrated.py         # Entry point integrato
├── astro2.py                  # Prototipo imaging standalone
└── DESIGN.md                  # Design document completo
```

## 🔬 Tecnologie e Algoritmi

### Astronomia
- **Coordinate**: Equatoriali (RA/Dec), Orizzontali (Az/Alt), Cartesiane
- **Proiezioni**: Azimuthal Equidistant per sky chart
- **Tempo**: Julian Date, Local Sidereal Time
- **Effemeridi**: VSOP87 (pianificato)

### Rendering
- **Noise Procedurale**: Multi-octave turbulence
- **Forme Ellittiche**: Con position angle
- **Bracci Spirali**: Spirali logaritmiche
- **Filtri**: Simulazione H-alpha (656nm), OIII (501nm), SII (672nm)

### Imaging
- **Noise Model**: Shot noise (√N), Read noise, Dark current
- **Calibrazione**: (Light - Dark) / Flat
- **Stacking**: Mean, Median, Sigma-clipping rejection
- **PSF**: Gaussiana con FWHM configurabile

### RNG Deterministico
- **SplitMix64** per hash
- **NumPy PCG64** per distribzioni
- Stesso seed globale = stesso universo procedurale

## 🎨 Stile Grafico

- **Palette**: VGA-inspired, 256 colori
- **Font**: Monospaziati (Consolas, Courier)
- **UI**: Bordi pixelati, panelli con outline
- **Oggetti**: Pixelart realistico ma stilizzato
- **Effetti**: Dithering per gradienti smooth

## 📊 Performance

### Ottimizzazioni Implementate
- Indicizzazione spaziale tile-based per cataloghi
- Caching texture procedurali
- LOD per rendering stelle
- Query magnitude-limited
- Hard cap su oggetti renderizzati per frame

### Benchmark Target
- 60 FPS con 50k stelle visibili
- Query catalogo < 5ms
- Rendering DSO < 10ms per oggetto
- Stacking 10 frames 512x512 < 1s

## 🗺️ Roadmap

### v0.2 - Interfacce Complete
- [ ] Integrazione completa sky chart + imaging
- [ ] Observatory management screen
- [ ] Catalog browser con filtri
- [ ] Tutorial interattivo

### v0.3 - Sistema Solare
- [ ] Effemeridi planetarie
- [ ] Visualizzazione pianeti e lune
- [ ] Tracking asteroidi/comete
- [ ] Discovery mechanics

### v0.4 - Career Mode
- [ ] Progressione equipaggiamento
- [ ] Sistema task scientifici
- [ ] Scoperte e pubblicazioni
- [ ] Research points e upgrade

### v0.5 - Polish
- [ ] Sound design
- [ ] Effetti atmosferici (seeing, turbolenza)
- [ ] Achievements
- [ ] Save/Load system
- [ ] Modding support

### v1.0 - Release
- [ ] Campagna completa career mode
- [ ] Cataloghi completi (Gaia DR3 full)
- [ ] Spettrografia
- [ ] Fotometria avanzata
- [ ] Multiplayer (osservatori condivisi?)

## 🤝 Contributi

Il progetto è in fase alpha. Contributi benvenuti per:
- Cataloghi astronomici (CSV/JSON format)
- Texture e sprite pixelart
- Algoritmi astrometrici
- Testing e bug report

## 📝 Note Tecniche

### Cataloghi Richiesti

Per il funzionamento completo servono:

1. **Hipparcos** (~120k stelle, mag < 7)
   - Build con: `python tools/build_hipparcos_index.py`
   - Output: `data/hip_index.npz`

2. **Gaia DR3** (subset, mag < 12)
   - Build con: `python tools/build_gaia_index_v2.py`
   - Output: `data/gaia_index_v2.npz`

3. **Messier** (già incluso nel codice)

4. **NGC/IC** (pianificato)
   - Sorgente: OpenNGC database

### Accuratezza

- **Coordinate**: Precisione 1 arcsec (sufficiente per imaging amatoriale)
- **Magnitudine**: ±0.1 mag (realistica per osservazioni visuali)
- **Tempo**: Ignora precessione/nutazione (errore <0.1° su 10 anni)
- **Imaging**: Modello fisico semplificato ma qualitativamente corretto

## 📚 Riferimenti

### Astronomia
- Hipparcos/Gaia catalogs (ESA)
- Messier catalog
- OpenNGC database

### Algoritmi
- Meeus, J. "Astronomical Algorithms"
- Stellarium source code (proiezioni)
- Astropy documentation

### Game Design
- Space Engine (procedural generation inspiration)
- Universe Sandbox (physics simulation)
- Kerbal Space Program (career progression)

## 📄 Licenza

MIT License - Vedi LICENSE file

## 👨‍💻 Autore

Sviluppato con passione per l'astronomia e il retro gaming!

---

**Status**: Alpha v0.1 - Core systems operational
**Last Update**: 2026-02-08
