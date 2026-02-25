# ASTRO OBSERVER — GPU Rendering Migration Roadmap

**Hybrid Architecture: ModernGL + C++ Performance Modules**

Version 1.0 — Febbraio 2026 — Architettura Decisionale Post-Review

---

## 1. Executive Summary

Astro Observer è un simulatore astronomico con **~26.000 righe Python/Pygame**. L'engine fisico e la parte scientifica procedono bene, ma la parte grafica incontra limiti strutturali di fluidità e rendering dovuti all'architettura CPU-only di Pygame.

Questa roadmap definisce il percorso di migrazione verso una **pipeline GPU ibrida** che mantiene Python come linguaggio primario, introduce **ModernGL** per il rendering/compositing/effetti, e prevede **moduli C++ (pybind11)** per la generazione procedurale pesante.

---

## 2. Principi Architetturali

| Principio | Decisione |
|---|---|
| Chi possiede main()? | **Python**. Il main.py attuale resta l'entry point. |
| Threading model | **Single-thread**. C++ chiamato sincrono da Python. |
| Rendering engine | **ModernGL** (OpenGL via Python). Nessun engine C++ custom. |
| Compositing | **GPU shader GLSL**. Sostituisce catena di pygame.blit(). |
| Generazione contenuti | Python (oggi) → C++ pybind11 (domani). Output: numpy array. |
| Risoluzione interna | **640×360**, upscale nearest-neighbor via GPU. |
| Strategia Pygame | Pygame resta per input/audio/events. Perde il rendering. |
| Fallback | Mantenere capacità di rendering software per debug. |

---

## 3. Architettura Target

Il sistema si organizza in tre strati con responsabilità nette. La comunicazione tra strati avviene esclusivamente tramite **numpy array** e **uniform shader**, minimizzando il coupling.

```
┌─────────────────────────────────────────────┐
│            STRATO 1: Python Orchestration    │
│  main loop, game state, astrofisica,        │
│  UI logic, time control, workflow di gioco   │
│  >>> Questo strato NON cambia <<<           │
└──────────┬───────────────┬──────────────────┘
           │               │
     ┌─────▼─────┐   ┌────▼─────────────┐
     │  Pygame    │   │  STRATO 2:       │
     │  (input,   │   │  Generazione     │
     │   audio,   │   │  Contenuti       │
     │   events)  │   │  Python/numpy    │
     └─────┬─────┘   │  → C++ pybind11  │
           │          └────┬─────────────┘
           │               │
           │    numpy arrays (H, W, 4) float32
           │               │
     ┌─────▼───────────────▼──────────────┐
     │   STRATO 3: GPU Rendering Pipeline  │
     │   ModernGL + GLSL Shaders           │
     │                                     │
     │   Layer Textures                    │
     │   → Compositing Shader              │
     │   → Post-Process Shaders            │
     │   → Nearest-Neighbor Upscale        │
     └────────────────────────────────────┘
```

### Strato 1: Python Orchestration
Possiede il main loop, il game state, l'astrofisica, la UI logic, il time control, e tutto il workflow di gioco. Questo strato non cambia nella migrazione.

### Strato 2: Generazione Contenuti
Oggi interamente Python/numpy. Progressivamente migrato a **moduli C++ esposti via pybind11**. Ogni modulo produce un **numpy array RGBA float32** che viene caricato come texture GPU. Moduli candidati alla migrazione C++: nebula generator, starfield sampler, spatial indexing, Milky Way renderer.

### Strato 3: GPU Rendering Pipeline
**ModernGL** gestisce il rendering completo: ogni layer è una texture GPU, il compositing avviene in shader GLSL, gli effetti post-process (bloom, twinkling, atmospheric scattering, palette mapping) girano sulla GPU a costo vicino a zero.

---

## 4. Flusso per Frame

| Step | Chi | Cosa | Costo |
|---|---|---|---|
| 1 | Python | Aggiorna stato (tempo, camera, visibilità layer) | ~1ms |
| 2 | Python/C++ | Se serve, rigenera layer (nebula, starfield) → numpy | 5–50ms* |
| 3 | ModernGL | Upload texture GPU (solo layer modificati) | <1ms |
| 4 | GPU Shader | Compositing layer + blending modes | <0.1ms |
| 5 | GPU Shader | Post-process: bloom, twinkling, scatter, palette | <0.5ms |
| 6 | GPU Shader | Nearest-neighbor upscale 640×360 → schermo | <0.01ms |

> *Step 2 non avviene ogni frame. Le texture persistono sulla GPU e vengono aggiornate solo quando il contenuto cambia (cambio camera, tempo, etc.)*

---

## 5. Layer Stack e Blending

Ogni layer è una texture GPU indipendente con toggle di visibilità, opacità configurabile, e blending mode dedicato. Ordine di compositing (dal basso verso l'alto):

| # | Layer | Blending | Aggiornamento | Note |
|---|---|---|---|---|
| 0 | Sky Gradient | Replace | Ogni cambio tempo/location | Gradiente atmosferico |
| 1 | Milky Way | Additive | Ogni cambio camera | Texture pre-computed |
| 2 | Nebulae / DSO | Screen | Su richiesta (raro) | Candidato migrazione C++ |
| 3 | Starfield | Additive | Ogni cambio camera | Candidato migrazione C++ |
| 4 | Planets / Moon / Sun | Alpha | Ogni frame | Oggetti dinamici |
| 5 | Atmosphere / Clouds | Alpha | Ogni cambio meteo | Weather system |
| 6 | Instrument Overlay | Alpha | Su interazione | Telescope/finder view |
| 7 | UI Overlay | Alpha | Su interazione | Menu, HUD, labels |

---

## 6. Pipeline Effetti Post-Process

Questi effetti sono il motivo principale della migrazione a GPU. Su CPU (Pygame) costerebbero 35–80ms per frame. Su GPU costano complessivamente **<1ms**. L'ordine di applicazione è critico per la qualità visiva:

| Ordine | Effetto | Shader | Parametri Chiave | Modalità |
|---|---|---|---|---|
| 1 | Bloom / Glow | Multi-pass gaussian blur | threshold, intensity, radius | Sempre attivo |
| 2 | Twinkling | Per-star temporal modulation | frequenze, ampiezza, fase | Vista cielo |
| 3 | Diffraction Spikes | Directional sampling | spike_length, n_vanes | Vista telescopio |
| 4 | Atmospheric Scattering | Extinction + horizon glow | airmass, horizon_color | Vista cielo |
| 5 | Chromatic Aberration | RGB channel offset | intensity (molto sottile) | Vista telescopio |
| 6 | Vignette | Radial darkening | radius, softness | Opzionale |
| 7 | CCD Noise | Read + shot + pattern noise | gain, exposure, read_noise | Solo imaging mode |
| 8 | Palette Mapping | LUT + Bayer dithering | palette_id, dither_strength | Retro mode |

---

## 7. Roadmap Sprint per Sprint

---

### Sprint 15.5 — GPU Proof of Concept `[READY]`

**Durata stimata:** 1 settimana

**Obiettivo:** Validare che ModernGL + Pygame coesistono e che bloom/twinkling funzionano a 60fps sulla macchina di sviluppo.

**Task:**
1. Eseguire il PoC standalone (`bloom_poc.py`) e verificare 60fps stabili
2. Verificare compatibilità OpenGL 3.3 sulla macchina target
3. Testare il bridge `pygame_bridge.py` con una Surface esistente dal progetto
4. Documentare eventuali incompatibilità hardware/driver

**Deliverable:** Demo funzionante con starfield + bloom + twinkling. Go/No-Go per proseguire.

**Rischio principale:** Driver OpenGL non supportato o performance GPU insufficiente. In quel caso, valutare SDL2_gpu come alternativa.

---

### Sprint 16 — Finestra OpenGL e Primo Layer `[PLANNED]`

**Durata stimata:** 2 settimane

**Obiettivo:** Sostituire la finestra Pygame con una finestra OpenGL. Rendere il primo layer (sky gradient) via GPU mantenendo tutto il resto funzionante.

**Task:**
1. Modificare la creazione finestra in `main.py`: aggiungere flag `pygame.OPENGL | pygame.DOUBLEBUF`
2. Inizializzare `moderngl.create_context()` dal contesto Pygame
3. Creare `GPURenderPipeline` come classe nel progetto (basata sul PoC)
4. Implementare `LayerBridge` per il sky gradient: il renderer Python produce la Surface, il bridge la carica come texture
5. Tutti gli altri layer: rendering temporaneo su Surface offscreen, caricamento come texture GPU via bridge
6. Verificare che input Pygame (mouse, tastiera) funzioni correttamente con finestra OpenGL

**Deliverable:** Il gioco funziona con finestra OpenGL. Aspetto visivo identico al pre-migrazione, ma il compositing è su GPU.

**Breaking change:** `pygame.display.get_surface().blit()` non funziona più con OPENGL flag. Tutto il rendering deve passare per il pipeline GPU.

**Integrazione nel codice esistente:**
```python
# PRIMA (in main.py):
screen = pygame.display.set_mode((W, H))

# DOPO:
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                 pygame.GL_CONTEXT_PROFILE_CORE)
screen = pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
ctx = moderngl.create_context()
```

---

### Sprint 17 — Layer System Completo `[PLANNED]`

**Durata stimata:** 2–3 settimane

**Obiettivo:** Migrare tutti gli 8 layer al sistema GPU. Ogni layer ha blending mode, visibilità, e opacità indipendenti.

**Task:**
- Implementare `SceneCompositor` con stack di layer configurabile
- Shader compositing con blending modes: alpha, additive, screen, multiply
- Smart update: texture GPU aggiornata solo quando il contenuto del layer cambia (dirty flag)
- Migrare layer uno alla volta: sky → Milky Way → starfield → nebulae → planets → atmosphere → overlays → UI
- Nearest-neighbor upscale alla risoluzione della finestra

**Deliverable:** Rendering completamente su GPU. Nessun `pygame.blit()` nel render path. Performance visibilmente migliori.

**Milestone:** Da questo punto, il budget CPU liberato (~35–80ms/frame) è disponibile per contenuti più ricchi.

---

### Sprint 18 — Bloom e Twinkling in Produzione `[PLANNED]`

**Durata stimata:** 2 settimane

**Obiettivo:** Integrare gli effetti post-process principali (bloom e twinkling) nel gioco reale, con parametri calibrati sulle magnitudini stellari.

**Task:**
- Bloom multi-pass: bright extract → gaussian blur H/V → additive combine
- Calibrazione threshold bloom su magnitudini reali (mag < 3 = bloom visibile)
- Twinkling multi-frequenza con ampiezza proporzionale all'airmass (realistico)
- Toggle effetti via UI settings (B per bloom, T per twinkling come nel PoC)
- Performance profiling: verificare che l'intera catena post-process stia sotto 2ms

**Deliverable:** Primo effetto "wow" visibile. Stelle con bloom e twinkling realistico a 60fps.

---

### Sprint 19 — Atmospheric Scattering e Palette `[PLANNED]`

**Durata stimata:** 2 settimane

**Obiettivo:** Aggiungere profondità atmosferica e l'estetica retro DOS/VGA al rendering GPU.

**Task:**
- Shader atmospheric scattering: estinzione per airmass + glow orizzonte
- Integrazione con il physical sky model esistente (parametri da Python → uniform shader)
- Palette mapping shader con Bayer 4×4 dithering (estetica DOS/VGA)
- Sistema palette selezionabili (CGA, EGA, VGA, custom astronomiche)
- Vignette shader per vista telescopio

**Deliverable:** Il cielo ha profondità atmosferica. Modalità retro con palette + dithering funzionante.

---

### Sprint 20 — Imaging Mode Effects `[PLANNED]`

**Durata stimata:** 2 settimane

**Obiettivo:** Effetti specifici per la modalità imaging/telescopio: rumore CCD, diffraction spikes, chromatic aberration.

**Task:**
- CCD noise simulation: read noise + shot noise + fixed pattern (colonna)
- Diffraction spikes per stelle brillanti (4 o 6 vane, configurabile)
- Chromatic aberration ottica (molto sottile, solo ai bordi del campo)
- Smooth zoom shader per transizione sky chart → vista telescopio

**Deliverable:** Modalità imaging con simulazione ottica realistica. Effetto wow completo.

---

### Sprint 21+ — Moduli C++ Performance `[FUTURE]`

**Durata stimata:** 3–6 settimane (incrementale)

**Obiettivo:** Portare i generatori procedurali più pesanti in C++ per liberare ulteriore budget CPU e permettere contenuti più ricchi.

#### Modulo 1: Nebula Generator
- Setup progetto CMake + pybind11
- Port del generatore procedurale nebulae Python → C++
- Input: parametri di configurazione. Output: numpy array RGBA float32
- Speedup atteso: 10–50x rispetto a Python/numpy

#### Modulo 2: Starfield Sampler
- Spatial indexing (KD-tree) per query veloci di stelle visibili
- LOD management per densità stellare a diversi livelli di zoom

#### Modulo 3: Milky Way Renderer
- Generazione texture Milky Way con star clouds, dust lanes, emission
- Pre-computation + cache per evitare rigenerazione ad ogni frame

**Nota:** Questa fase è opzionale. Se dopo Sprint 20 le performance sono soddisfacenti con la sola GPU pipeline, i moduli C++ possono essere rimandati.

---

## 8. Timeline Complessiva

| Sprint | Contenuto | Durata | Dipendenze | Status |
|---|---|---|---|---|
| 15.5 | GPU PoC — Validazione | 1 sett. | Nessuna | `[READY]` |
| 16 | Finestra OpenGL + primo layer | 2 sett. | 15.5 ✔ | `[PLANNED]` |
| 17 | Layer system completo | 2–3 sett. | 16 ✔ | `[PLANNED]` |
| 18 | Bloom + twinkling produzione | 2 sett. | 17 ✔ | `[PLANNED]` |
| 19 | Atmospheric + palette retro | 2 sett. | 18 ✔ | `[PLANNED]` |
| 20 | Imaging mode effects | 2 sett. | 18 ✔ | `[PLANNED]` |
| 21+ | C++ performance modules | 3–6 sett. | 17 ✔ | `[FUTURE]` |

**Tempo totale stimato:** 11–16 settimane (Sprint 15.5–20). I moduli C++ (Sprint 21+) sono indipendenti e opzionali.

**Primo risultato visibile:** Sprint 18 (circa settimana 7–8). Stelle con bloom e twinkling realistico a 60fps.

---

## 9. API Boundary: Python ↔ GPU

Le strutture dati che attraversano il confine Python/GPU devono essere definite con precisione.

### Strutture di Stato (Python → Shader Uniforms)

| Struttura | Campi | Frequenza Update | Destinazione Shader |
|---|---|---|---|
| CameraState | az, alt, fov, zoom_level | Ogni frame | Tutti i layer shader |
| TimeState | jd, lst, utc_offset, elapsed | Ogni frame | Twinkling, atmosphere |
| RenderConfig | layer_visibility[8], internal_w/h, palette_id | Su interazione | Compositor |
| BloomConfig | enabled, threshold, intensity, radius | Su interazione | Bloom shader |
| AtmoConfig | horizon_y, extinction, horizon_color, sky_brightness | Ogni cambio tempo | Atmospheric shader |

### Strutture Layer (Generatori → GPU Texture)

Ogni generatore (Python o C++) produce un **numpy array (H, W, 4) float32**, valori in [0, 1], formato RGBA. Questo array viene caricato come texture GPU tramite il `LayerBridge`. Il canale alpha può essere usato per informazioni aggiuntive (es. fase twinkling per le stelle).

### Python Data Classes corrispondenti

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class CameraState:
    az: float           # azimuth (degrees)
    alt: float          # altitude (degrees)
    fov: float          # field of view (degrees)
    zoom_level: float   # 1.0 = no zoom

@dataclass
class TimeState:
    jd: float           # Julian Date
    lst: float          # Local Sidereal Time (hours)
    utc_offset: float   # UTC offset (hours)
    elapsed: float      # seconds since start (for animations)

@dataclass
class RenderConfig:
    layer_visibility: list[bool]  # 8 flags
    internal_w: int     # 640
    internal_h: int     # 360
    palette_id: int     # 0 = no palette, 1 = CGA, 2 = EGA, etc.

@dataclass
class BloomConfig:
    enabled: bool
    threshold: float    # 0.0–1.0, default 0.35
    intensity: float    # 0.0–2.0, default 0.6
    radius: float       # blur radius, default 1.5

@dataclass
class AtmoConfig:
    horizon_y: float        # 0.0–1.0, posizione orizzonte in UV
    extinction: float       # 0.5–3.0, forza estinzione
    horizon_color: tuple    # (r, g, b) glow orizzonte
    sky_brightness: float   # 0.0 = notte, 0.5 = twilight
```

---

## 10. Strategia di Sviluppo con GitHub Copilot

### Dove Copilot eccelle

| Area | Efficacia | Prompt Pattern |
|---|---|---|
| Shader GLSL | **Eccellente** | "Write a GLSL fragment shader that [effetto] for a pixel-art astronomy sim" |
| Boilerplate ModernGL | **Eccellente** | "Create a ModernGL framebuffer with [specs] for [scopo]" |
| pybind11 bindings | **Eccellente** | "Expose this C++ class to Python via pybind11, input/output numpy" |
| CMake configuration | **Buono** | "CMakeLists.txt for pybind11 module with SDL2 and numpy" |
| numpy ↔ texture | **Buono** | "Convert pygame.Surface to ModernGL texture via numpy" |
| Port Python → C++ | **Buono** | Incollare la funzione Python e chiedere "port to C++" |
| Tuning parametri | **Limitato** | I valori estetici vanno calibrati manualmente |
| Debug cross-language | **Limitato** | Problemi al boundary Python/C++ richiedono analisi manuale |

### Workflow Consigliato per Sprint

1. **Definire l'API prima del codice.** Scrivi le struct/interfacce (CameraState, TimeState, RenderConfig) come commenti. Copilot genera l'implementazione.
2. **Uno shader alla volta.** Chiedi a Copilot un singolo effetto con parametri chiari. Testa isolato prima di integrare.
3. **Reference code nel prompt.** Quando porti codice Python in C++, includi la funzione originale nel prompt. Copilot mappa numpy → loop C++ molto bene.
4. **Non fidarti del tuning.** Copilot genera valori plausibili per threshold, intensity, etc. Ma il tuning visivo va fatto a occhio sul tuo rendering reale.

---

## 11. Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| OpenGL 3.3 non supportato su macchina target | Bassa | Alto | Sprint 15.5 è il go/no-go. Fallback: SDL2_gpu o Vulkan via sokol |
| Pygame OPENGL mode rompe funzionalità esistenti | Media | Medio | Sprint 16 affronta questo. Il bridge permette migrazione graduale |
| Performance texture upload > budget frame | Bassa | Medio | Smart update: upload solo layer dirty. PBO per upload asincrono |
| Complessità shader cresce ingestibile | Media | Basso | Ogni effetto è un pass isolato. Aggiungere/rimuovere è semplice |
| Moduli C++ rallentano il ciclo di sviluppo | Media | Medio | C++ è opzionale e rimandabile. Python resta sempre il fallback |
| Scope creep sugli effetti visivi | Alta | Medio | Sprint rigorosi. Ogni effetto completato e testato prima di passare al successivo |

---

## 12. Stack Tecnologico

| Componente | Tecnologia | Versione Minima | Ruolo |
|---|---|---|---|
| Linguaggio primario | Python | 3.10+ | Game logic, orchestrazione, astrofisica |
| GPU rendering | ModernGL | 5.8+ | OpenGL context, texture, shader, FBO |
| Shading language | GLSL | 330 core | Compositing, post-process, effetti |
| Windowing | Pygame | 2.5+ | Finestra OpenGL, input, audio, events |
| Numeric | NumPy | 1.24+ | Bridge dati tra Python/C++ e GPU |
| C++ bindings | pybind11 | 2.11+ | Espone moduli C++ come extension Python |
| C++ build | CMake | 3.20+ | Build system per moduli C++ |
| C++ standard | C++17 | — | Moduli performance-critical |

---

## 13. Prossimi Passi Immediati

1. **Oggi:** Eseguire `bloom_poc.py` sulla macchina di sviluppo. Verificare 60fps e qualità visiva.
2. **Questa settimana:** Testare `pygame_bridge.py` con una Surface reale dal progetto (es. sky gradient attuale).
3. **Decisione Go/No-Go:** Se il PoC funziona, iniziare Sprint 16. Se no, analizzare il fallback SDL2_gpu.

---

## 14. File di Riferimento del PoC

| File | Descrizione |
|---|---|
| `bloom_poc.py` | PoC standalone. Starfield + bloom + twinkling a 60fps. Entry point per validazione. |
| `pygame_bridge.py` | Bridge `pygame.Surface` → texture GPU. Metodi: `update_from_surface()`, `update_from_numpy()`, `update_region()`. |
| `shader_recipes.py` | 7 shader GLSL pronti: atmospheric scattering, palette mapping, diffraction spikes, chromatic aberration, vignette, CCD noise, smooth zoom. |

---

*Fine del documento*
