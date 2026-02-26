# ASTRO OBSERVER — Development Pivot: GPU Rendering Migration

**Documento operativo — Febbraio 2026**

---

## 1. Stato Attuale

Riepilogo di quanto completato prima del pivot:

- **Sprint 13b completato:** pianeti in sky chart + catalog browser
- **Sprint 14a/14b completati:** weather/seeing model, cloud layer procedurale
- **Codebase:** ~20.000 righe Python, 389k stelle reali (Gaia DR3 + Hipparcos + Yale BSC)
- **Vectorized star queries già implementate** in `universe/universe.py` (numpy arrays, `get_star_arrays()`, `query_stars_in_fov()` con binary search + spatial filter)
- **NPZ catalog loader operativo** (`universe/npz_loader.py`)
- **GPU PoC validato** (`bloom_poc.py`) — ModernGL + Pygame coesistono, bloom a 60fps

---

## 2. Perché il Pivot

- La pipeline rendering attuale (pygame.blit chain) è il bottleneck: **35-80ms per frame** per effetti che sulla GPU costerebbero <1ms
- Bloom, twinkling, atmospheric scattering, diffraction spikes sono impossibili a 15fps su CPU
- Il PoC ha dimostrato che ModernGL + Pygame coesistono senza problemi
- La struttura layer-based dell'allsky renderer (`imaging/allsky_renderer.py`) mappa direttamente su texture GPU
- Le ottimizzazioni vectorized della Universe (numpy arrays pre-sorted by mag) preparano il terreno per upload GPU efficiente

---

## 3. Cosa NON Cambia

- `main_app.py` resta l'entry point
- Pygame resta per input, audio, events
- La fisica (effemeridi, atmosfera, noise model) resta in Python/numpy
- `SpaceObject`, `Universe`, catalogue loaders restano invariati
- Il fallback software rendering resta disponibile per debug
- Career mode, equipment, catalog browser non vengono toccati

---

## 4. Piano Operativo Sprint per Sprint

Vedi anche: [`docs/AstroObserver_GPU_Migration_Roadmap (1).md`](./AstroObserver_GPU_Migration_Roadmap%20(1).md)

### Sprint 15.5 — GPU PoC Validation (1 settimana)

- [ ] Eseguire `bloom_poc.py` e verificare 60fps stabili
- [ ] Testare compatibilità OpenGL 3.3 sulla macchina target
- [ ] Testare bridge `pygame_bridge.py` con Surface esistente
- [ ] Documentare incompatibilità hardware/driver
- [ ] Go/No-Go decision

### Sprint 16 — OpenGL Window + First Layer (2 settimane)

- [ ] Modificare `main_app.py`: `pygame.OPENGL | pygame.DOUBLEBUF`
- [ ] Inizializzare `moderngl.create_context()`
- [ ] Creare `rendering/gpu_pipeline.py` (basata su PoC)
- [ ] Implementare `LayerBridge` per sky gradient
- [ ] Tutti gli altri layer via bridge temporaneo (Surface → texture GPU)
- [ ] **Deliverable:** finestra OpenGL funzionante, primo layer GPU, tutto il resto invariato

### Sprint 17 — Complete Layer System (2-3 settimane)

- [ ] `SceneCompositor` con stack di 8 layer configurabile
- [ ] Blending modes: alpha, additive, screen, multiply
- [ ] Smart update con dirty flags
- [ ] Migrare layer: sky → Milky Way → starfield → nebulae → planets → atmosphere → overlays → UI
- [ ] Nearest-neighbor upscale (640×360 → screen resolution)
- [ ] **Deliverable:** zero `pygame.blit()` nel render path

### Sprint 18 — Bloom + Twinkling in Production (2 settimane)

- [ ] Multi-pass gaussian blur bloom (dal PoC alla produzione)
- [ ] Per-star twinkling con frequenze individuali (0.5-2Hz)
- [ ] Diffraction spikes per ottica newtoniana
- [ ] **Deliverable:** primo effetto "wow" visibile — stelle con bloom realistico a 60fps

### Sprint 19 — Atmospheric Scattering + Retro Palette (2 settimane)

- [ ] Atmospheric extinction shader
- [ ] Horizon glow GPU
- [ ] CRT/VGA palette mapping shader (estetica retro)
- [ ] **Deliverable:** rendering atmosferico completo su GPU

---

## 5. File Critici da NON Toccare

I seguenti file non devono essere modificati senza una revisione di integrazione dedicata:

| File | Motivo |
|------|--------|
| `ui_new/screen_imaging.py` | Bugfix manuale utente (Feb 2026) — non sovrascrivere |
| `universe/space_object.py` | Base class usata ovunque — modifiche richiedono audit completo |
| `catalogs/` | Dati astronomici reali — non generare mai dati fake |

---

## 6. File da Creare

| File | Descrizione |
|------|-------------|
| `rendering/gpu_pipeline.py` | `GPURenderPipeline` class (evoluzione di `bloom_poc.py`) |
| `rendering/layer_bridge.py` | Bridge numpy/pygame → GPU texture |
| `rendering/shaders/` | Directory per GLSL shaders |
| `rendering/scene_compositor.py` | Layer stack compositing |

---

## 7. Dipendenze Nuove

```
moderngl>=5.8
```

Già validata nel PoC. Nessuna altra dipendenza nuova richiesta.

---

## 8. Metriche di Successo

| Metrica | Attuale (CPU) | Target (GPU) |
|---------|---------------|--------------|
| Frame time effetti | 35-80ms | <1ms |
| FPS con bloom | impossibile | 60fps |
| FPS con twinkling | ~5fps | 60fps |
| Upload texture (389k stars) | N/A | <5ms |
| Memory overhead GPU | 0 | ~50MB VRAM |

---

## 9. Rischi e Mitigazioni

- **Rischio:** Driver OpenGL non supportato → **Mitigazione:** fallback SDL2_gpu o software rendering
- **Rischio:** Regressione visiva durante migrazione → **Mitigazione:** A/B comparison con screenshot prima/dopo
- **Rischio:** Performance numpy→GPU upload → **Mitigazione:** dirty flags, upload solo layer modificati
