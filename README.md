# Observatory Simulation Game

Un simulatore astronomico fotorealistico in stile retrò (DOS/VGA) con fisica reale, effemeridi accurate e sistema di imaging completo.

![Python](https://img.shields.io/badge/python-3.11+-green)
![Lines](https://img.shields.io/badge/codebase-~20k_lines-blue)
![Status](https://img.shields.io/badge/status-sprint_13b-brightgreen)

---

## Panoramica

Il gioco simula un osservatorio astronomico con fisica reale end-to-end: dal calcolo delle effemeridi planetarie (VSOP87, Meeus) alla simulazione del sensore CCD/CMOS (fotoni → elettroni → ADU), passando per un modello atmosferico completo (Rayleigh scattering, estinzione, sky glow lunare). L'estetica è volutamente retrò — palette VGA, font monospace, UI a pannelli — ma la fisica sotto è da planetario professionale.

**Entry point:** python main_app.py
**Dipendenze:** pip install pygame numpy scipy

---

## Architettura

```
main_app.py                  # Entry point, game loop, screen router
│
├── ui_new/                  # Schermate principali (UI framework custom)
│   ├── screen_skychart.py   # Carta celeste interattiva (~1600 righe)
│   ├── screen_imaging.py    # Sistema imaging allsky + deep sky (~1100 righe)
│   ├── screen_catalog.py    # Browser catalogo oggetti
│   ├── screen_equipment.py  # Gestione telescopi, montature, camere
│   ├── screen_observatory.py# Hub osservatorio
│   ├── screen_career.py     # Career mode
│   ├── components.py        # Widget riusabili (Button, Slider, Table...)
│   ├── base_screen.py       # Base class schermate
│   └── theme.py             # Palette colori VGA, font
│
├── universe/                # Universo e meccanica orbitale
│   ├── orbital_body.py      # OrbitalBody: Sole, Luna, pianeti (Meeus/VSOP87)
│   ├── planet_physics.py    # Magnitudini IAU 2012, anelli Saturno, diametri
│   ├── minor_bodies.py      # MinorBody, CometBody, MinorBodyCatalog (MPC)
│   ├── universe.py          # Contenitore stelle + DSO + corpi solari
│   ├── procedural_lod.py    # LOD procedurale per stelle deboli
│   ├── space_object.py      # SpaceObject base class
│   ├── catalogue_loader.py  # Loader cataloghi
│   └── npz_loader.py        # Loader NPZ (Gaia, Hipparcos)
│
├── imaging/                 # Pipeline imaging
│   ├── allsky_renderer.py   # Renderer allsky (proiezione zenitale equidistante)
│   ├── sky_renderer.py      # Renderer deep sky (FOV rettangolare)
│   ├── solar_bodies_renderer.py # Sole, Luna, pianeti, oggetti minori
│   ├── celestial_bodies.py  # Bloom fisico (fotoni → ADU → PSF)
│   ├── camera.py            # Modello camera (ZWO 174MM, QHY 5III-462C...)
│   ├── calibration.py       # Dark/Flat/Bias calibration
│   ├── stacking.py          # Stacking (mean, median, sigma-clipping)
│   ├── processing.py        # Stretch, histogram, processing
│   ├── frames.py            # Frame types (LIGHT, DARK, FLAT, BIAS)
│   ├── equipment.py         # Telescopi, ottiche, accessori
│   ├── noise_model.py       # Shot noise, read noise, dark current
│   └── display_pipeline.py  # Pipeline visualizzazione
│
├── atmosphere/              # Modello atmosferico fisico
│   ├── atmospheric_model.py # Rayleigh, Mie, DayPhase, sky glow lunare
│   └── day_phase.py         # Fase diurna/crepuscolare
│
├── catalogs/                # Cataloghi astronomici
│   ├── star_catalog.py      # BSC + Hipparcos subset (~389k stelle)
│   ├── messier_data.py      # 110 oggetti Messier
│   ├── ngc_data.py          # Catalogo NGC/IC
│   ├── deep_sky.py          # DSO loader
│   └── data/                # File NPZ cataloghi (Gaia DR3, Hipparcos)
│
├── core/                    # Utility matematiche
│   ├── time_controller.py   # TimeController (JD, velocità, reverse)
│   ├── celestial_math.py    # Coordinate, proiezioni, trasformazioni
│   ├── constellation_data.py# 33 costellazioni con linee
│   └── coords.py            # Conversioni equatoriale <-> orizzontale
│
├── game/                    # Logica di gioco
│   ├── career_mode.py       # Career mode, task, progressione
│   └── state_manager.py     # Stato globale del gioco
│
└── rendering/
    └── nebula_renderer.py   # Renderer nebulose (Sérsic, HII, clusters)
```

---

## Implementato — Stato Attuale (Sprint 13b, Feb 2026)

### Universo 3D

- 389.110 stelle reali (Gaia DR3 + Hipparcos + Yale BSC) con posizioni J2000, magnitudine V, indice B-V, distanza
- 207 oggetti deep-sky (Messier + NGC/IC) con tipo morfologico, dimensioni angolari, magnitudine superficiale
- 33 costellazioni con linee e nomi, visibilità dipendente da magnitudine limite
- LOD procedurale: stelle deboli generate deterministicamente per zona di cielo, ottimizzate per FOV e mag limit dinamica

### Sistema Solare Completo

**Pianeti (10):** Mercurio, Venere, Marte, Giove, Saturno, Urano, Nettuno, Plutone

Per ciascuno:
- Effemeridi kepleriane con elementi JPL J2000 + tassi secolari
- Light-time correction — posizione apparente corretta per il ritardo di luce (43min per Giove, 4h per Nettuno)
- Magnitudini IAU 2012 specifiche per pianeta (Mallama & Hilton 2018), non il generico H,G
- Diametro apparente in arcsec calcolato dinamicamente (Giove: 31"–50", Saturno disco: 15"–20")
- Fasi visibili per Mercurio e Venere (orbite interne)
- Saturno: inclinazione anelli B con ciclo 29.5 anni (B~0° nel 2025, B~+27° nel 2032), magnitudine dipendente da B (differenza ~1.5 mag)

**Sole:** VSOP87 low-precision (~0.01° accuratezza), limb darkening fisico, bloom multi-layer calibrato su fotoni reali, halo atmosferico, Belt of Venus anti-solare.

**Luna:** Meeus Cap. 47 (~0.1°, 14 termini principali), fase corretta da elongazione, disco con terminatore e texture mare, bloom dipendente da fase.

**Oggetti Minori (12 hardcoded + loader MPC scalabile):**
- Cerere, Vesta, Pallade, Giunone, Hygiea, Interamnia, Davida (fascia principale)
- Plutone (pianeta nano TNO)
- 433 Eros, 99942 Apophis (Near-Earth Asteroids — Apophis con avvicinamento 2029)
- 1P/Halley, 2P/Encke (comete periodiche con orbite ellittiche complete)

**Architettura MPC scalabile:** `MinorBodyElements` in formato MPC nativo, `MinorBodyCatalog.from_mpc_file(path, aperture_cm=25.0)` già implementato — carica fino a 600k+ asteroidi da MPCORB.DAT filtrati per magnitudine raggiungibile con l'apertura del telescopio attivo. `CometBody` con orbite paraboliche/ellittiche e calcolo position angle coda anti-solare.

### Atmosfera Fisica

- Rayleigh scattering — colore blu del cielo dipendente da lunghezza d'onda
- Estinzione atmosferica Bouger-Lambert, dipendente da airmass e B-V della stella
- DayPhase — 8 fasi: notte, twilight astronomico/nautico/civile, alba/tramonto, giorno
- Sky glow lunare Krisciunas-Schaefer — contributo lunare al fondo cielo
- Seeing Kolmogorov — FWHM variabile che modifica il PSF del renderer
- Rifrazione atmosferica Bennett — correzione altitudine apparente vicino all'orizzonte
- Gradiente altitudinale allsky — estinzione dipendente dall'angolo zenitale per ogni pixel
- Twilight glow direzionale — gradiente crepuscolare verso il Sole, Belt of Venus anti-solare

### Allsky Camera

**Proiezione:** zenitale equidistante 180° FOV, cerchio perfetto a qualsiasi risoluzione, render 1:1 senza upscale.

**Pipeline rendering (campo raw in fotoni fisici):**
1. Background sky fisico con gradiente altitudinale + noise organico 3 ottave
2. Atmospheric glow direzionale (Sole/Belt of Venus)
3. Stelle con PSF dipendente da magnitudine (1px deboli, 3×3 medie, 5×5 brillanti)
4. Sole con bloom multi-layer fisico (5 layer sigma 3→175px, calibrati su overflow ratio)
5. Luna con fase, terminatore, bloom 4 layer calibrato su foto reali allsky
6. Pianeti con PSF scalato su diametro apparente, maschera di fase per Mercurio/Venere, ellisse anelli per Saturno
7. Oggetti minori come punti stellari con flusso fisico

**Tone mapping luma-chroma preserving:** stretch logaritmico sulla LUMA (black=1 ADU, white=65535, gamma=0.42), colori preservati — tramonto arancione resta arancione, cielo notturno B-V preservato, cielo diurno satura naturalmente a bianco-azzurro.

**Gain software (0–400):** `gain_mult = gain_ref_e_adu / gain_eff_e_adu` applicato a stelle, background e bloom. gain=50: cielo nero, solo stelle brillanti. gain=400: cielo steel-blue, centinaia di stelle.

**Modelli camera:** ZWO ASI 174MM (mono, QE 78%, full well 14ke−), QHY 5III-462C (colore).

### Sky Chart Interattivo

- Proiezione azimuthal equidistant con zoom 1°–180° FOV
- Stelle con PSF dipendente da magnitudine, colore B-V realistico
- DSO con rendering morfologico (galassie ellisse, nebulose glow, cluster punti)
- Costellazioni: 33 pattern con linee, visibilità adattiva per mag limit
- Griglia RA/Dec, reticolo, info stelle al click
- TimeController condiviso con ImagingScreen: JD floating-point, 8 velocità (pausa → 1 settimana/s), reverse, sync real-time
- **[NEW Sprint 13b]** Pianeti visibili con dimensioni FOV-aware, colori realistici per tipo (Marte rosso, Giove tan, ecc.)
- **[NEW Sprint 13b]** Saturno con anelli ellittici dinamici, inclinazione B calcolata dal ciclo 29.5 anni
- **[NEW Sprint 13b]** Luna con shading fase tramite terminatore alpha-blended
- **[NEW Sprint 13b]** Sole con bloom a 3 layer (r×3, r×2, r) con alpha graduato
- **[NEW Sprint 13b]** Minor bodies (Cerere, Vesta, asteroidi, comete) visibili come punti stellari filtrati per magnitudine
- **[NEW Sprint 13b]** Click selection per tutti i corpi con hitbox adattivo, info panel con effemeridi real-time
- **[NEW Sprint 13b]** Toggle [P] e pulsante PLANETS per mostrare/nascondere sistema solare

### Imaging Screen (3 tab)

- TAB 0 LIVE VIEW: preview allsky real-time aggiornata ogni 2s, controlli esposizione e gain
- TAB 1 CAPTURE: acquisizione sequenza lights N×esposizione, dark/flat/bias
- TAB 2 PROCESS: calibrazione, stacking, stretch istogramma con slider Black/White/Gamma

### Sistema Imaging Deep Sky

- Pipeline fisica: mag_to_flux → fotoni → elettroni (QE) → ADU (gain)
- PSF gaussiano con FWHM dal seeing atmosferico (Kolmogorov)
- DSO rendering: profilo Sérsic per galassie, Gaussian per nebulose, punti per cluster
- Colori B-V con conversione spettrale realistica
- Noise model: shot noise √N, read noise gaussiano, dark current lineare

### Modello Fisico Bloom

- Overflow ratio: electrons/FW_electrons → dimensione PSF bloom
- Multi-layer PSF: sigma 3px core → 8px inner halo → 20px mid → 50px wide
- Gain multiplier: gain alto → più ADU → bloom più esteso e intenso

### Altre Schermate

- Career Mode: struttura task e obiettivi, progressione equipaggiamento, sistema punti ricerca
- Equipment Manager: database telescopi, camere, montature; calcolatore FOV e scala pixel
- Catalog Browser: ricerca per nome/tipo/magnitudine/costellazione, preview DSO
- **[NEW Sprint 13b]** Catalog Browser: pannello "Solar System" (340×400px) con lista completa pianeti + minor bodies
- **[NEW Sprint 13b]** Effemeridi aggiornate real-time: simbolo Unicode, nome, magnitudine, distanza, fase%/angolo B Saturno
- **[NEW Sprint 13b]** Indicatori altitudine: ↑ verde sopra orizzonte, ↓ rosso sotto orizzonte
- **[NEW Sprint 13b]** Sezione Minor Bodies separata nel catalogo
- **[NEW Sprint 13b]** Click su riga → info panel con campi tipo-specifici (pianeta/asteroide/cometa)

---

## Da Implementare — Backlog Ordinato

### Sprint 13b — Integrazione Sky Chart + Pianeti ✅ COMPLETATO

- [x] Pianeti visibili nello sky chart con simboli e label
- [x] Oggetti minori nello sky chart (Cerere, Vesta visibili a occhio nudo)
- [x] Tooltip pianeta al click: magnitudine, distanza, fase, diametro apparente
- [x] Saturno con indicazione inclinazione anelli nel tooltip
- [x] Pianeti nel Catalog Browser (sezione Solar System)
- [x] Coerenza visiva sky chart ↔ allsky: stesso oggetto, stesso simbolo/colore
- [ ] Etichette automatiche congiunzioni/opposizioni vicine nel timeframe corrente (rimandato a Sprint 14)

### Sprint 14 — Seeing e Meteo

- [ ] Seeing variabile nel tempo — modulazione temporale del FWHM (Kolmogorov + bassa frequenza)
- [ ] Scintillazione stelle — twinkling visibile nel live view come perturbazione rapida
- [ ] Modello meteo semplice — trasparenza variabile (0–100%)
- [ ] Nuvole procedurali — texture che si muovono e occultano stelle/pianeti
- [ ] Umidità e turbolenza — influenzano seeing e limiting magnitude
- [ ] Forecast meteo in-game — dati simulati per pianificare sessioni
- [ ] Rugiada/ghiaccio su ottica — riduce throughput, richiede riscaldamento

### Sprint 14.5 — UI Foundation Refactor

**Goal:** Reorganize UI architecture with proper navigation, content management, and observable filtering.

**New screens:**
- [ ] Main Menu (CAREER / EXPLORE / SETTINGS / QUIT)
- [ ] Content Manager (catalogs + equipment library + graphics settings)

**New components:**
- [ ] NavigationManager — centralized screen stack + global hotkeys (H=home, ESC=back)
- [ ] WeatherWidget — persistent widget (top-right) visible in all screens, click to expand forecast
- [ ] ObservablePanel — "Observable Now" filterable list (alt > 30°, mag < X, etc.)

**Screen updates:**
- [ ] Observatory — add WeatherWidget, navigation hotkeys
- [ ] SkyChart — add ObservablePanel (hotkey O), WeatherWidget, quick-switch to Imaging (hotkey I)
- [ ] Imaging — tabs (Live/Setup/Capture/Process), WeatherWidget, quick-switch to SkyChart (hotkey S)
- [ ] Equipment — mode switch: Career (shop + owned) vs Explore (sandbox all equipment)

**Navigation flow:**
```
MAIN_MENU
  ├→ CAREER → (future Sprint 17 tasks) → OBSERVATORY
  ├→ EXPLORE → OBSERVATORY (direct, sandbox mode)
  └→ SETTINGS → CONTENT_MANAGER
      ├→ Catalogs tab (enable/disable Gaia, Messier, NGC, MPCORB, etc.)
      ├→ Equipment Library tab (view all telescopes/cameras specs)
      └→ Graphics tab (VFX toggles, resolution)

OBSERVATORY (hub)
  ├→ SKYCHART ⟷ IMAGING (hotkey I/S quick-switch)
  ├→ EQUIPMENT (Career: shop + owned | Explore: sandbox)
  └→ STATS (future)

Global hotkeys:
  H = Home (return to OBSERVATORY)
  ESC = Back (pop navigation stack)
  O = Observable Now panel (in SkyChart/Imaging)
```

**Files:**
- NEW: `ui_new/navigation_manager.py`, `ui_new/screen_main_menu.py`, `ui_new/screen_content_manager.py`
- MODIFY: `ui_new/components.py` (WeatherWidget + ObservablePanel), `ui_new/screen_observatory.py`, `ui_new/screen_skychart.py`, `ui_new/screen_imaging.py`, `ui_new/screen_equipment.py`, `main_app.py`

**Effort:** ~870 lines total (300 new components, 390 new screens, 180 refactor).

---

### Sprint 15 — VFX e Fluidità (2 layer)

**Filosofia:** Separare fisica (accuratezza, pesante, 1–2s per frame) da estetica (bellezza, leggera, 15fps real-time). Il layer fisico genera frame accurati ma lenti. Il layer VFX li interpola/decora a 15fps per fluidità visiva.

**Architettura:**
```
Layer Fisico (1–2s interval)          Layer VFX (15fps real-time)
────────────────────────              ───────────────────────────
AllSkyRenderer.render()               VFXLayer (pygame Surface)
  ↓ (1–4 seconds compute)               ↓ (~15ms per frame)
  Stars, planets, physics               Ordered dithering pass (Bayer 8×8 o Blue Noise)
  ↓                                     ↓
  field (H,W,3) numpy                   Bloom/glow (bright stars + planets)
  ↓                                     ↓
  tone mapping → pygame Surface         Multi-layer clouds (foschia + cumuli + cirri)
  ↓                                     ↓
  [cached as last_physical_frame]       Twinkling (alpha modulation 0.5–2Hz)
                                        ↓
                                        Frame interpolation (smooth color transitions)
                                        ↓
                                        Composite → screen at 15fps
```

#### Layer fisico (invariato, 1–2s per frame)
- Frame fisicamente accurato come ora (stelle, pianeti, atmosfera, nuvole base)
- Generato solo quando necessario (nuovo JD, nuovo FOV, nuova camera)
- Cached come texture — il layer VFX ci disegna sopra senza ricomputare la fisica

#### Layer visivo real-time (15fps, ~15ms per frame)

**Core VFX:**
- [ ] **Ordered dithering** — Bayer 8×8 matrix o Blue Noise texture per transizioni smooth senza banding
  - Large scale (16×16 tiles) per gradienti colore cielo
  - Medium scale (8×8) per bordi nuvole
  - Fine scale (2×2) per noise organico stellare
  - Target: dithering "gradevole" stile fotografia analogica, non pixelato duro
- [ ] **Interpolazione inter-frame** per transizioni giorno/notte fluide
  - Blend con easing curve tra prev_frame e next_frame
  - A ×3600 (1h/s) i colori del tramonto scorrono fluidi invece di saltare
- [ ] **Twinkling stelle** — perturbazione alpha/luma su stelle già renderizzate (0.5–2Hz)
  - Solo stelle mag < 4.0 (le deboli non scintillano visibilmente)
  - Ampiezza dipendente da airmass (orizzonte scintilla di più)
- [ ] **Transizioni cromatiche** fluide del cielo durante accelerazione tempo

**Cloud layers multipli (upgrade del layer base di Sprint 14b):**
- [ ] **Low fog** (foschia bassa) — quasi trasparente, layer più basso
- [ ] **Cumulus** (cumuli medi) — layer attuale di Sprint 14b
- [ ] **Cirrus** (veli alti) — molto trasparenti, si muovono più veloci dei cumuli, sopra tutto
- [ ] Composite con alpha blending — 3 layer con velocità/altezza/opacità diverse
- [ ] Bordi nuvole con gradient smooth + dithering (no hard edges)

**Post-processing effects:**
- [ ] **Bloom sulle stelle brillanti** — stelle mag < 2.0 hanno alone realistico
  - Gaussian blur approximation (3-pass box blur)
  - Additive blend sul frame originale
  - Costo: ~5–10ms per 560×560
- [ ] **Diffraction spikes** (ottica newtoniana) — 4 spikes a croce per stelle brillanti
  - Solo se telescopio è newtoniano (non su rifrattori)
  - Length proporzionale a magnitude (più brillante = spike più lungo)
  - Alpha gradient lungo lo spike
- [ ] **Lens flare direzionale** quando Sole è vicino al bordo del cerchio allsky
- [ ] **Via Lattea procedurale** — texture 512×512 precomputed con stelle dense
  - Composite con alpha 0.3, solo di notte
  - Ruota con tempo siderale (galactic plane angle)
  - Alto impatto visivo, zero costo (texture statica)
- [ ] **Colori stelle più saturi** nell'allsky (B-V più pronunciato, stile foto reale)

**Elementi dinamici puramente grafici:**
- [ ] **Aerei in transito** — sprite animati che attraversano il campo (puramente decorativo)
- [ ] **Satelliti LEO** — punti luminosi veloci, occasionali (Starlink, ISS)
  - Non fisici (TLE tracking è Sprint 18+), ma danno vita all'immagine

#### Performance target
- Layer fisico: 1–4s per frame (invariato, OK)
- Layer VFX: 15fps stabili (66ms budget) anche a ×3600
- Dithering: <2ms (lookup table)
- Bloom: 5–10ms (box blur 3-pass)
- Cloud composite: <3ms (3 alpha blends)
- Twinkling: <1ms (alpha modulation su array pre-filtrato)
- **Total VFX overhead: <20ms → 50fps anche con tutto attivo**

### Sprint 16 — Oggetti Minori Avanzati

- [ ] Loader MPCORB.DAT attivo — già strutturato in MinorBodyCatalog.from_mpc_file(), serve il file e il collegamento all'apertura del telescopio attivo
- [ ] Asteroidi NEA come eventi in-game (avvicinamenti, missioni di osservazione)
- [ ] Comete attive con chioma e coda visibile nell'allsky e sky chart
- [ ] Effemeridi comete da file MPC aggiornabili
- [ ] Occultazioni — asteroide che transita davanti a una stella (evento raro)
- [ ] Apophis 2029 come evento fisso in-game (13 aprile, passaggio <40.000 km, mag ~+3)

### Sprint 17 — Career Mode Completo

- [ ] Missioni astronomiche strutturate (scoperta asteroidi, fotometria variabili, imaging DSO)
- [ ] Sistema reputazione e pubblicazioni scientifiche
- [ ] Upgrade telescopio progressivo (apertura, montatura, camera)
- [ ] Condizioni meteo che influenzano disponibilità notti
- [ ] Log automatico sessioni con statistiche
- [ ] Obiettivi stagionali (congiunzioni, opposizioni, comete)
- [ ] Sistema finanziamento osservatorio (grant, scoperte, imaging)

### Sprint 18 — Spettrografia e Fotometria

- [ ] Simulazione spettro stellare da tipo spettrale
- [ ] Fotometria differenziale (misura variazione magnitudine)
- [ ] Curve di luce variabili (Cefeidi, RR Lyrae, eclissanti)
- [ ] Riduzione dati spettrali
- [ ] Astrometria — misura posizione precisa asteroidi

### Lungo Termine

- [ ] Catalogo Gaia DR3 completo (1.8 miliardi di stelle, caricamento lazy per FOV)
- [ ] Multiplayer — osservatori condivisi, collaborazione su scoperte
- [ ] Modding support — telescopi custom, DSO aggiuntivi, task
- [ ] Esportazione FITS reali compatibili con AstroPixelProcessor/Siril
- [ ] Lune planetarie (Galileane, Titano) con orbite accurate

---

## Fisica e Algoritmi — Riferimenti

| Area | Fonte |
|------|-------|
| Sole (posizione) | VSOP87 low-precision, Meeus Cap. 25 |
| Luna (posizione) | Meeus Cap. 47, 14 termini principali |
| Pianeti (orbite) | JPL DE430 / Standish 1992, elementi J2000 |
| Magnitudini pianeti | Mallama & Hilton 2018, PASP 130, 014201 |
| Atmosfera Rayleigh | dipendenza λ⁻⁴, coefficienti standard |
| Estinzione | legge Bouger-Lambert, banda V |
| Sky glow lunare | Krisciunas-Schaefer (1991) |
| Seeing | turbolenza Kolmogorov, r₀ di Fried |
| Rifrazione | formula Bennett (1982) |
| Flusso stelle | f = f₀ × 10^(-0.4×mag), f₀ = 9.83×10⁷ ph/s/cm² |
| Gain ZWO | g_eff = 3.6 / (1 + gain_sw/55) e/ADU |
| Tone mapping | luma-chroma preserving, gamma=0.42 |

---

## Controlli

| Tasto | Azione |
|-------|--------|
| TAB | Prossima schermata |
| ESC | Menu / Esci |
| Space | Pausa/Riprendi tempo |
| F1–F6 | Velocità tempo (×0, ×1, ×10, ×60, ×3600, ×86400) |
| R | Reverse tempo |
| \ | Sync tempo reale |
| Mouse drag | Pan sky chart |
| Scroll | Zoom sky chart |
| Click | Seleziona/info oggetto |
| P | Toggle pianeti sky chart |

---

## Note per Sviluppo Futuro

### File critico: screen_imaging.py
`ui_new/screen_imaging.py` (~1100 righe) è il file più complesso. Gestisce sia allsky che deep sky imaging. La funzione `_expose()` ha subito un bugfix manuale dall'utente (Feb 2026) — non sovrascrivere senza integrare quella versione.

### Aggiungere un telescopio
In `imaging/equipment.py`, aggiungere a `TELESCOPE_DATABASE` con i campi: uid, name, aperture_mm, focal_length_mm, obstruction_pct.

### Aggiungere una camera
In `imaging/camera.py`, aggiungere a `CAMERA_DATABASE` con: uid, sensor_w, sensor_h, pixel_size_um, quantum_efficiency, full_well_e, read_noise_e, dark_current_e_per_s.

### Caricare asteroidi MPC
```python
from universe.minor_bodies import MinorBodyCatalog
# Scarica MPCORB.DAT da https://www.minorplanetcenter.net/iau/MPCORB.html
catalog = MinorBodyCatalog.from_mpc_file("MPCORB.DAT", aperture_cm=25.0)
# catalog.bodies contiene tutti gli asteroidi visibili con quell'apertura
```

### Allsky tone mapping
Il mapping è luma-chroma preserving: applica log stretch sulla luminanza, preserva il rapporto R:G:B. Black=1 ADU, White=65535 ADU (16-bit full scale), gamma=0.42. Non usare tone mapping per-canale separato — desatura i colori.

---

*Sprint 13b completato: integrazione pianeti in sky chart e catalog browser*
*Codebase: ~20.000 righe Python (esclusi backup e file obsoleti)*
*Ultima modifica: Febbraio 2026*