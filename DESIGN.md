# Observatory Simulation Game - Design Document

## Visione del Progetto
Un simulatore astronomico retrò (stile DOS VGA, pixelart) che combina:
- Osservazione del cielo reale con cataloghi stellari (Hipparcos, Gaia)
- Sistema solare con meccaniche celesti accurate
- Oggetti procedurali da scoprire (asteroidi, comete, esopianeti)
- Sistema di imaging professionale (calibrazione, stacking, elaborazione)
- Modalità Sandbox ed Career

## Architettura Modulare

```
observatory_game/
│
├── core/                    # Moduli base già esistenti
│   ├── coords.py            # Coordinate celesti
│   ├── astro_time.py        # Gestione tempo astronomico
│   ├── catalog_index.py     # Indicizzazione cataloghi
│   └── types.py             # Dataclass base
│
├── catalogs/                # Cataloghi astronomici
│   ├── stars.py             # Gestione stelle reali (HIP, Gaia)
│   ├── deep_sky.py          # Nebulose, galassie, SNR
│   ├── solar_system.py      # Pianeti, lune, asteroidi, comete
│   └── procedural.py        # Generazione oggetti procedurali
│
├── physics/                 # Simulazione fisica
│   ├── orbital.py           # Meccaniche orbitali
│   ├── ephemeris.py         # Calcolo posizioni pianeti
│   └── discovery.py         # Sistema di scoperte
│
├── imaging/                 # Sistema imaging (da astro2.py)
│   ├── camera.py            # Simulazione CCD/CMOS
│   ├── frames.py            # Gestione frames (light, dark, flat, bias)
│   ├── calibration.py       # Calibrazione e stacking
│   ├── processing.py        # Elaborazione immagini
│   └── analysis.py          # Fotometria, astrometria
│
├── rendering/               # Rendering pixelart
│   ├── sky_renderer.py      # Rendering cielo stellato
│   ├── nebula_renderer.py   # Rendering nebulose (pixelart realistico)
│   ├── galaxy_renderer.py   # Rendering galassie
│   └── effects.py           # Effetti atmosferici, seeing, ecc.
│
├── ui/                      # Interfacce utente
│   ├── screen_skychart.py   # Carta celeste (già esistente)
│   ├── screen_planetarium.py # Planetario
│   ├── screen_imaging.py    # Interfaccia imaging (da astro2.py)
│   ├── screen_observatory.py # Gestione osservatorio
│   ├── screen_catalog.py    # Browser cataloghi
│   └── screen_career.py     # Modalità carriera
│
├── game/                    # Logica di gioco
│   ├── career_mode.py       # Progressione, task, ricerca
│   ├── sandbox_mode.py      # Modalità esplorazione libera
│   ├── equipment.py         # Telescopi, camere, filtri
│   ├── objectives.py        # Obiettivi scientifici
│   └── scoring.py           # Sistema punteggio e scoperte
│
├── data/                    # Dati del gioco
│   ├── catalogs/            # File cataloghi (HIP, Gaia, ecc.)
│   ├── equipment/           # Database strumenti
│   └── missions/            # Task e obiettivi
│
└── main.py                  # Entry point

```

## Caratteristiche Principali

### 1. Sistema di Cataloghi Multi-Livello
- **Stelle reali**: Hipparcos (mag < 7), Gaia DR3 (mag < 12)
- **Deep Sky Objects (DSO)**: 
  - Nebulose a emissione (HII regions)
  - Nebulose a riflessione
  - Nebulose planetarie
  - Supernova remnants (SNR)
  - Galassie (spirali, ellittiche, irregolari)
  - Ammassi aperti e globulari
- **Sistema Solare**: 
  - Pianeti e lune (effemeridi accurate)
  - Asteroidi della main belt (reali + procedurali)
  - NEO (Near-Earth Objects)
  - Comete (periodiche + nuove scoperte procedurali)
  - Oggetti trans-nettuniani
- **Esopianeti**: Database reale + generazione procedurale

### 2. Sistema di Imaging Realistico
Basato su astro2.py, espanso con:
- **Acquisizione**:
  - Light frames (esposizioni target)
  - Dark frames (calibrazione termica)
  - Flat frames (correzione vignettatura/polvere)
  - Bias frames (correzione elettronica)
- **Calibrazione**:
  - Master dark/flat/bias
  - Sottrazione dark, divisione flat
  - Correzione hot/cold pixels
- **Processing**:
  - Allineamento frames (star matching)
  - Stacking (mean, median, sigma-clipping)
  - Stretch istogramma
  - Filtri (sharpen, denoise)
  - Color combination (LRGB, narrowband)
- **Analisi**:
  - Fotometria apertura
  - Fotometria differenziale (variabili)
  - Astrometria (plate solving)
  - Curve di luce
  - Detection automatica (asteroidi, comete)

### 3. Rendering Pixelart Realistico
- **Stelle**: Colori basati su temperatura (procedura da astro2.py)
- **Nebulose**: Texture procedurali con filtri H-alpha, OIII, SII
- **Galassie**: Forme procedurali (spirali, ellittiche) con pixelart
- **Atmosfera**: Seeing, turbolenza, inquinamento luminoso
- **Filtri**: Simulazione filtri fotografici e narrowband

### 4. Modalità di Gioco

#### Sandbox Mode
- Budget iniziale illimitato
- Accesso a tutto l'equipaggiamento
- Esplorazione libera del cielo
- Focus sulla scoperta e fotografia

#### Career Mode
- **Inizio**: Piccolo rifrattore 80mm, webcam modificata
- **Progressione**:
  - Completare task scientifici
  - Fare scoperte (comete, asteroidi, variabili)
  - Pubblicare osservazioni
  - Guadagnare punti ricerca
- **Upgrade**:
  - Telescopi più grandi (rifrattori, riflettori, SCT)
  - Camere CCD/CMOS professionali
  - Montature equatoriali motorizzate
  - Filtri narrowband
  - Spettrografi
  - Sistema goto e autoguida
- **Obiettivi**:
  - Confermare esopianeti (fotometria transiti)
  - Scoprire asteroidi/comete
  - Monitorare variabili
  - Contribuire a survey scientifici
  - Pubblicare su riviste virtuali

### 5. Meccaniche Celesti Accurate
- **Sistema Solare**:
  - Effemeridi planetarie (VSOP87 o DE440 semplificato)
  - Perturbazioni gravitazionali
  - Precessione, nutazione
- **Scoperte**:
  - Asteroidi: orbite randomiche ma realistiche
  - Comete: apparizioni periodiche e nuove
  - Algoritmi di detection automatica
  - Conferma follow-up necessaria

### 6. Stile Grafico VGA Retrò
- Palette colori limitata (256 colori in stile VGA)
- Font monospaziati (Consolas, Courier)
- UI con bordi pixelati
- Effetti CRT opzionali
- Animazioni frame-by-frame
- Dithering per gradienti

## Tecnologie
- **Python 3.11+**
- **Pygame** per rendering e input
- **NumPy** per calcoli numerici e imaging
- **Astropy** (opzionale) per calcoli astronomici avanzati
- **SciPy** per algoritmi scientifici (interpolazione, fitting)

## Pipeline di Sviluppo

### Fase 1: Integrazione Base (CORRENTE)
- [x] Struttura progetto esistente (skychart)
- [x] Prototipo imaging (astro2.py)
- [ ] Merge dei due sistemi
- [ ] Schermata osservatorio principale
- [ ] Navigazione tra screens

### Fase 2: Sistema Imaging Completo
- [ ] Integrazione imaging nel game loop
- [ ] Gestione equipaggiamento (telescopi, camere)
- [ ] Simulazione realistica acquisition
- [ ] Pipeline calibrazione completa
- [ ] Tools di processing avanzati

### Fase 3: Cataloghi Espansi
- [ ] Integrazione DSO (nebulose, galassie)
- [ ] Sistema solare completo
- [ ] Generazione procedurale oggetti
- [ ] Rendering pixelart realistico

### Fase 4: Game Mechanics
- [ ] Sistema career mode
- [ ] Task e obiettivi scientifici
- [ ] Sistema scoperte e pubblicazioni
- [ ] Progressione e upgrade
- [ ] Scoring e achievements

### Fase 5: Polish e Features
- [ ] Tutorial interattivo
- [ ] Effetti atmosferici
- [ ] Sound design (ambientale)
- [ ] Salvataggio/caricamento
- [ ] Statistiche e log osservazioni

## Note Tecniche

### Performance
- Indicizzazione spaziale per query veloci (già implementato)
- LOD (Level of Detail) per rendering stelle
- Caching texture procedurali
- Multithreading per stacking (opzionale)

### Accuratezza Scientifica
- Calcoli astrometrici accurati al secondo d'arco
- Simulazione seeing atmosferico realistica
- Modelli fotometrici calibrati
- Effemeridi accurate (errore < 1 arcmin)

### Modding
- File JSON/YAML per equipment
- Script Python per task custom
- Cataloghi estendibili
- Texture pack per stili grafici diversi
