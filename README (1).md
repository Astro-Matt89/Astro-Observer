# Sprint 15.5 — GPU Rendering PoC

## Astro Observer: da Pygame CPU a GPU Pipeline

---

## Quick Start

```bash
pip install pygame moderngl numpy
python bloom_poc.py
```

### Controlli
| Tasto | Azione |
|-------|--------|
| **B** | Toggle bloom on/off |
| **T** | Toggle twinkling on/off |
| **+/-** | Aumenta/diminuisci intensità bloom |
| **ESC** | Esci |

---

## Cosa dimostra questo PoC

### 1. Pygame + ModernGL coesistono
Pygame crea la finestra OpenGL, ModernGL prende il controllo del rendering.
Il tuo `main.py` resta l'entry point. Nessun cambio architetturale.

### 2. Layer → Texture GPU
Ogni layer (sky, nebula, starfield, overlay) diventa una texture GPU.
Il compositing avviene in shader — istantaneo rispetto a `pygame.blit()` con alpha.

### 3. Bloom multi-pass
Pipeline: Scena → Bright Extract → Blur H → Blur V → Combine.
Tutto sulla GPU, costo ~0.5ms a 640×360. Su CPU sarebbero 20-50ms.

### 4. Twinkling animato
Modulazione per-stella nel fragment shader, multi-frequenza per realismo.
Ogni stella ha una fase unica (memorizzata nel canale alpha della texture).

### 5. Nearest-Neighbor Upscale
La scena interna (640×360) viene scalata alla finestra (1280×720+)
con nearest-neighbor — pixel art perfetto, nessun smoothing.

---

## Struttura dei file

```
sprint15_5_poc/
├── bloom_poc.py          # PoC completo e standalone
├── pygame_bridge.py      # Bridge Pygame Surface → GPU texture  
└── README.md             # Questo file
```

---

## Come integrare nel progetto

### Fase 0: Test standalone (questo PoC)
Verifica che funzioni sulla tua macchina. Se vedi il cielo stellato con
bloom e twinkling a 60fps, sei pronto.

### Fase 1: Finestra OpenGL
```python
# Nel tuo main.py, cambia la creazione finestra:

# PRIMA:
screen = pygame.display.set_mode((W, H))

# DOPO:
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                 pygame.GL_CONTEXT_PROFILE_CORE)
screen = pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
ctx = moderngl.create_context()
```

> **NOTA**: Con `pygame.OPENGL`, non puoi più usare `screen.blit()`.
> Ma puoi ancora creare `pygame.Surface` in memoria e caricarle come texture.

### Fase 2: Un layer alla volta
Inizia col layer che beneficia di più dal GPU rendering (probabilmente lo starfield
o il sky gradient). Gli altri layer possono restare come surface Pygame e essere
caricati come texture ad ogni frame.

```python
from pygame_bridge import LayerBridge

star_layer = LayerBridge(ctx, 640, 360, "stars")

# Il tuo renderer esistente produce una surface
star_surface = my_starfield_renderer.render(camera_state)

# La carichi sulla GPU
star_layer.update_from_surface(star_surface)
```

### Fase 3: Compositing GPU
Quando tutti i layer sono su GPU, sostituisci la catena di `blit()` con
il compositing shader. A questo punto hai bloom/twinkling/effetti gratis.

### Fase 4: Elimina le Surface intermedie
Migra i generatori a produrre `numpy` array direttamente (salti la
conversione `Surface → numpy`). Questo prepara anche il terreno per i
moduli C++ pybind11.

---

## Architettura target

```
┌─────────────────────────────────────────────┐
│                Python Main Loop             │
│  (game logic, astrofisica, UI state, time)  │
└──────────┬───────────────┬──────────────────┘
           │               │
     ┌─────▼─────┐   ┌────▼─────────────┐
     │  Pygame    │   │  C++ Modules     │
     │  (input,   │   │  (pybind11)      │
     │   audio,   │   │  - nebula gen    │
     │   events)  │   │  - starfield     │
     └─────┬─────┘   │  - spatial idx   │
           │          └────┬─────────────┘
           │               │
           │    numpy arrays (layer data)
           │               │
     ┌─────▼───────────────▼──────────────┐
     │         ModernGL GPU Pipeline       │
     │  ┌──────────────────────────────┐  │
     │  │ Layer Textures               │  │
     │  │ sky → nebula → stars → UI    │  │
     │  └──────────┬───────────────────┘  │
     │  ┌──────────▼───────────────────┐  │
     │  │ Compositing Shader           │  │
     │  │ (blending, alpha, additive)  │  │
     │  └──────────┬───────────────────┘  │
     │  ┌──────────▼───────────────────┐  │
     │  │ Post-Process Shaders         │  │
     │  │ bloom, twinkling, palette,   │  │
     │  │ atmospheric scatter, vignette│  │
     │  └──────────┬───────────────────┘  │
     │  ┌──────────▼───────────────────┐  │
     │  │ Nearest-Neighbor Upscale     │  │
     │  │ 640×360 → screen resolution  │  │
     │  └──────────────────────────────┘  │
     └────────────────────────────────────┘
```

---

## Performance attese

| Operazione | CPU (Pygame) | GPU (ModernGL) |
|---|---|---|
| Layer compositing (6 layer, alpha) | 8-15ms | <0.1ms |
| Bloom (gaussian blur 9-tap) | 20-50ms | <0.5ms |
| Twinkling (2000 stelle) | 5-10ms | <0.01ms |
| Upscale 640→1280 | 2-5ms | <0.01ms |
| **Totale effetti** | **35-80ms** | **<1ms** |

Il budget liberato (~35-80ms per frame) lo puoi reinvestire nella
generazione dei contenuti (nebulae più dettagliate, più stelle, etc.)
oppure semplicemente goderti i 60fps stabili.

---

## Note per Copilot / AI-assisted development

### Prompt efficaci per GLSL shaders
```
"Write a GLSL fragment shader that applies atmospheric scattering 
to a starfield. The shader receives the star texture and a uniform 
for the sun position. Stars near the horizon should fade. The sky 
near the sun should have warm orange glow."
```

### Prompt per pybind11 modules
```
"Port this Python function to C++ with pybind11 bindings. 
Input: numpy array shape (H, W, 4) float32.
Output: numpy array same shape.
The function does [your description]."
```

### Cose che Copilot fa bene in questo contesto
- Shader GLSL per effetti specifici (bloom, blur, color grading)
- Boilerplate ModernGL (FBO setup, texture creation)
- Conversioni numpy ↔ texture
- CMake + pybind11 scaffolding

### Cose dove serve il tuo giudizio
- Scelta dei parametri visivi (threshold, intensity, kernel size)
- Ordine e blending mode dei layer
- Quando rigenerare vs riusare una texture (cache strategy)
- Tuning per l'estetica pixel-art (evitare che il bloom rompa la crispness)
