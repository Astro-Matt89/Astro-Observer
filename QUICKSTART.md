# Quick Start Guide - Observatory Simulation Game

## 🚀 Installazione Rapida

### 1. Verifica Python
```bash
python --version  # Richiede Python 3.11 o superiore
```

### 2. Installa Dipendenze
```bash
pip install pygame numpy scipy
```

### 3. Avvia il Gioco
```bash
# Demo integrato (funziona subito!)
python main_integrated.py
```

## 🎮 Prime Mosse

### Schermata Iniziale
Vedrai l'**OBSERVATORY** screen con informazioni sul gioco.

**Controlli base:**
- `TAB` - Cambia schermata (Observatory → Skychart → Imaging → Catalog)
- `1` - Demo rendering oggetti Messier (M31 Andromeda, M42 Orion, ecc.)
- `2` - Demo rendering nebulose procedurali
- `ESC` - Esci

### Demo Rendering (Premi 1 o 2)

#### Demo 1: Oggetti Messier
Renderizza 5 oggetti famosi del catalogo Messier:
- M31 - Galassia di Andromeda (spirale)
- M42 - Nebulosa di Orione (HII region)
- M13 - Ammasso di Ercole (globulare)
- M57 - Nebulosa Anello (planetaria)
- M51 - Galassia Vortice (spirale)

Ogni oggetto è renderizzato in **tempo reale** con algoritmi procedurali che simulano:
- Bracci spirali per le galassie
- Emissione H-alpha per le nebulose
- Strutture filalose per i SNR
- Shell concentrici per le planetarie

#### Demo 2: Nebulose Procedurali
Genera e renderizza 6 nebulose **completamente procedurali**:
- Ogni nebulosa è unica ma deterministica (stesso seed = stessa nebulosa)
- Tipi: HII regions, planetarie, riflessione
- Magnitudini e dimensioni variabili

**Premi un tasto qualsiasi per chiudere la demo e tornare al menu.**

## 📋 Cosa Puoi Fare Ora

### ✅ Funziona Subito (No Setup Richiesto)
- Navigare le schermate con TAB
- Vedere il catalogo DSO (schermata CATALOG)
- Provare le demo rendering (tasti 1-2)
- Vedere info osservatore e tempo

### ⚙️ Richiede Setup Cataloghi
Per usare lo **Skychart** completo serve scaricare i cataloghi stellari:

```bash
# Crea directory data
mkdir -p data

# Scarica cataloghi (metodo manuale per ora)
# 1. Hipparcos: https://cdsarc.cds.unistra.fr/ftp/cats/I/239/
# 2. Gaia DR3: https://gea.esac.esa.int/archive/

# Build indici
python tools/build_hipparcos_index.py
python tools/build_gaia_index_v2.py

# Avvia skychart completo
python main.py
```

### 🎨 Per l'Imaging (da astro2.py)
Il prototipo imaging è standalone:

```bash
python astro2.py
```

**Controlli imaging:**
- `TAB` - Cambia schermata (Console → Targets → Imaging)
- `ENTER` - Seleziona target dalla lista
- `G` - Genera dataset (10 light + darks + flats)
- `C` - Calibra e stacka i frames
- `1/2/3` - Visualizza RAW / CAL / STACK
- `[/]` - Naviga frames
- `H` - Toggle istogramma
- `-/=` e `,/.` - Aggiusta stretch istogramma

## 🔍 Esplora il Codice

### File Principali

**main_integrated.py** - Demo integrato, punto di partenza
```python
# Sistema completo con:
# - Catalogo Messier (110 oggetti)
# - Generazione procedurale (asteroidi, comete, nebulose)
# - Rendering pixelart realistico
# - UI multi-schermata
```

**catalogs/deep_sky.py** - Gestione DSO
```python
# Classi per:
# - DeepSkyObject (dati completi)
# - DSOCatalog (query e indicizzazione)
# - Tipi: HII, PN, SNR, galassie, ammassi
```

**catalogs/procedural.py** - Generazione procedurale
```python
# ProceduralGenerator:
# - generate_asteroids() - Main belt realistici
# - generate_comets() - Periodiche e non
# - generate_nebulae() - HII regions, planetarie
# - generate_galaxies() - Spirali, ellittiche
```

**rendering/nebula_renderer.py** - Rendering oggetti
```python
# NebulaRenderer:
# - render_nebula() - Texture procedurali
# - Filtri: RGB, Ha, OIII, SII, HOO, SHO
# - Fisica: bracci spirali, filamenti, shell
```

## 💡 Prossimi Passi

### Per Iniziare a Programmare

1. **Aggiungi un nuovo tipo di nebulosa**
   - Modifica `rendering/nebula_renderer.py`
   - Aggiungi metodo `_render_your_type()`
   - Implementa algoritmo procedurale

2. **Crea nuovi oggetti procedurali**
   - Modifica `catalogs/procedural.py`
   - Aggiungi metodo `generate_your_objects()`
   - Usa RNG deterministico per riproducibilità

3. **Espandi il catalogo**
   - Modifica `catalogs/deep_sky.py`
   - Aggiungi oggetti a `load_messier_catalog()`
   - Formato: `DeepSkyObject(...)`

### Per Testare

```bash
# Test rendering singolo oggetto
python -c "
from catalogs.deep_sky import load_messier_catalog
from rendering.nebula_renderer import NebulaRenderer
import pygame

pygame.init()
catalog = load_messier_catalog()
renderer = NebulaRenderer()

m42 = catalog.get_messier(42)  # Orion Nebula
surf = renderer.render_nebula(m42, size_px=256, filter_mode='Ha')

screen = pygame.display.set_mode((300, 300))
screen.fill((0, 0, 0))
screen.blit(surf, (20, 20))
pygame.display.flip()

import time
time.sleep(5)
"
```

## 🐛 Troubleshooting

### "No module named pygame"
```bash
pip install pygame
```

### "No module named numpy"
```bash
pip install numpy
```

### "Cannot load catalogs" (main.py)
I cataloghi Hipparcos/Gaia non sono inclusi nel repository per dimensione.
Usa `main_integrated.py` che funziona senza cataloghi esterni.

### Performance Issues
Il rendering procedurale è CPU-intensive. Per migliorare:
- Riduci `size_px` nel rendering (default 128)
- Riduci cache size in `NebulaRenderer(cache_size=20)`
- Disabilita alcune texture nelle demo

## 📚 Documentazione Completa

- `README.md` - Overview progetto
- `DESIGN.md` - Design document dettagliato
- Code comments - Ogni file è documentato

## 🤝 Help & Support

Per domande o problemi:
1. Leggi i commenti nel codice
2. Controlla `DESIGN.md` per l'architettura
3. Esplora gli esempi nelle demo

## 🎯 Obiettivi Immmediati

**Per giocare:**
- Esplora le demo rendering (tasti 1-2)
- Naviga il catalogo (TAB → CATALOG)
- Prova l'imaging standalone (astro2.py)

**Per sviluppare:**
- Studia il rendering procedurale in `nebula_renderer.py`
- Crea nuovi oggetti DSO in `deep_sky.py`
- Implementa nuove distribuzioni orbitali in `procedural.py`

Buon divertimento! 🚀🔭
