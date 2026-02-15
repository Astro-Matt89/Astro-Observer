# 🚀 Imaging System Demo - Quick Start

## Demo Rapido del Sistema Imaging

Questo demo mostra il **sistema imaging completo** in azione:
- Acquisizione frames (Light/Dark/Flat)
- Calibrazione professionale
- Stacking con sigma-clipping
- Processing e visualizzazione real-time

---

## 🎮 Come Avviare il Demo

### 1. Prerequisiti

```bash
# Assicurati di avere le dipendenze
pip install pygame numpy scipy
```

### 2. Avvio

```bash
# Dalla directory del progetto
python demo_imaging.py
```

Si aprirà una finestra 1400x900 con il sistema imaging!

---

## 🎯 Workflow Demo

### Step 1: Genera Dataset
**Premi `G`** per generare:
- 10 light frames (30s esposizione)
- 5 dark frames (30s esposizione)
- 5 flat frames (1s esposizione)

Il sistema creerà un campo stellare sintetico con ~300 stelle e simulerà l'acquisizione completa con noise realistico.

**Output log**:
```
Generating dataset...
Generating star field (4144x2822)...
Capturing 10 light frames (30s each)...
Capturing 5 dark frames (30s each)...
Capturing 5 flat frames (1s each)...
Dataset complete: 10L + 5D + 5F
```

---

### Step 2: Calibra
**Premi `C`** per calibrare i light frames:
- Crea master dark (median di 5 darks)
- Crea master flat (median + normalizzazione)
- Applica calibrazione: (Light - Dark) / Flat
- Correzione cosmetic (hot pixels, cosmic rays)

**Output log**:
```
Starting calibration...
Creating master dark...
Master dark: mean=1523.4 ADU
Creating master flat...
Master flat: normalized to mean=1.0
Calibrating light frames...
Calibration complete: 10 frames
```

---

### Step 3: Stacka
**Premi `K`** per stackare i frames calibrati:
- Allinea frames (se necessario)
- Stacking con sigma-clipping (rimuove outlier)
- Calcola SNR improvement

**Output log**:
```
Stacking frames...
Stacking 10 frames (sigma-clip)...
Stack complete! SNR improvement: 3.08x
```

**Risultato**: Immagine finale con SNR migliorato di ~3x!

---

## 🎛️ Controlli

### Acquisizione
| Key | Azione |
|-----|--------|
| `G` | **Generate** dataset completo |
| `C` | **Calibrate** light frames |
| `K` | Stac**k** frames calibrati |

### Visualizzazione
| Key | Azione |
|-----|--------|
| `1` | View **RAW** frames (non calibrati) |
| `2` | View **CALIBRATED** frames |
| `3` | View **STACKED** image |
| `[` | Frame **precedente** |
| `]` | Frame **successivo** |
| `H` | Toggle **histogram** |

### Processing
| Key | Azione |
|-----|--------|
| `-` | **Diminuisci** black point (più scuro) |
| `=` | **Aumenta** black point (più chiaro) |
| `,` | **Diminuisci** white point (meno contrasto) |
| `.` | **Aumenta** white point (più contrasto) |

### Salvataggio
| Key | Azione |
|-----|--------|
| `S` | **Save** immagine corrente come PNG |
| `ESC` | **Quit** demo |

---

## 📊 Cosa Vedere

### Interfaccia

```
┌─────────────────────────────────────────────────────────────┐
│ OBSERVATORY IMAGING SYSTEM - DEMO                           │
│ Camera: ZWO ASI294MC Pro | Temp: -10.0°C | Frames: L=10... │
├──────────────────┬──────────────────────────────────────────┤
│ CONTROLS & LOG   │ IMAGE VIEWER                             │
│                  │                                          │
│ ACQUISITION:     │  ┌───────────────────────────────────┐  │
│  [G] Generate    │  │                                   │  │
│  [C] Calibrate   │  │        Displayed Image            │  │
│  [K] Stack       │  │                                   │  │
│                  │  │                                   │  │
│ VIEW:            │  └───────────────────────────────────┘  │
│  [1] RAW         │                                          │
│  [2] CAL         │  Stats: 4144x2822 | Min: 0 | Max:...   │
│  [3] STACK       │                                          │
│                  │  ┌───────────────────────────────────┐  │
│ STRETCH:         │  │ Histogram                         │  │
│  [-/=] Black     │  │ ▂▃▅▇█▇▅▄▃▂▁                      │  │
│  [,/.] White     │  └───────────────────────────────────┘  │
│                  │                                          │
│ LOG:             │                                          │
│ [12:34] System   │                                          │
│ [12:35] Dataset  │                                          │
│ ...              │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

### Pannello Sinistro
- **Controls**: Lista comandi disponibili
- **Status**: Mode corrente, frame index, parametri stretch
- **Log**: Ultimi 12 messaggi del sistema

### Pannello Destro
- **Image Viewer**: Display dell'immagine corrente (scalata per fit)
- **Stats**: Dimensioni, min/max/mean/std dell'immagine
- **Histogram**: Distribuzione valori pixel (64 bins)

---

## 🔍 Cosa Aspettarsi

### RAW Frames (Mode 1)
- Frames grezzi direttamente dalla camera
- Visibile noise (shot + read + dark)
- Vignettatura e dust shadows
- Hot pixels visibili
- **Aspetto**: Noisy, con artefatti

### Calibrated Frames (Mode 2)
- Frames dopo calibrazione
- Noise ridotto
- Vignettatura corretta
- Hot pixels rimossi
- **Aspetto**: Più pulito, flat response

### Stacked Image (Mode 3)
- Immagine finale dopo stacking
- SNR migliorato ~3x (con 10 frames)
- Dettagli più visibili
- Noise drasticamente ridotto
- **Aspetto**: Smooth, alto SNR, belle stelle!

---

## 📈 Metriche di Performance

Sul mio sistema (esempio):
- **Generate dataset**: ~2-3 secondi
- **Calibration**: ~1 secondo
- **Stacking**: ~1-2 secondi
- **Display**: 60 FPS costanti

**Totale workflow**: ~5-6 secondi per dataset completo!

---

## 💾 Output Files

Quando premi `S`, l'immagine viene salvata in:
```
output/imaging_demo_stack_20260208_193045.png
```

Formato: `imaging_demo_{mode}_{timestamp}.png`

---

## 🐛 Troubleshooting

### "ImportError: No module named 'imaging'"
**Soluzione**: Assicurati di essere nella directory corretta con i moduli imaging/

### "pygame.error: No available video device"
**Soluzione**: Sistema senza display. Il demo richiede GUI.

### Finestra troppo grande per lo schermo
**Soluzione**: Modifica `WIDTH, HEIGHT` nel file (righe 26-27)

### Performance lente
**Soluzione**: Riduci risoluzione camera o numero frames in `generate_dataset()`

---

## 🎨 Personalizzazioni

### Cambia Risoluzione
```python
# Nel file, cerca ImagingDemo.__init__()
self.camera = get_camera("WEBCAM_MOD", seed=42)  # 640x480 invece di 4144x2822
```

### Cambia Numero Stelle
```python
# In generate_dataset()
sky_signal = self.generate_star_field(w, h, n_stars=100)  # Default: 300
```

### Cambia Numero Frames
```python
# In generate_dataset()
for i in range(5):  # Invece di 10 light frames
```

### Cambia Metodo Stacking
```python
# In stack_frames()
self.stacked_image = stacker.stack(self.calibrated_frames, StackMethod.MEAN)
# Opzioni: MEAN, MEDIAN, SIGMA_CLIP
```

---

## 🚀 Next Steps

Dopo aver provato il demo:

1. **Sperimenta** con i controlli
2. **Salva** alcune immagini
3. **Modifica** i parametri per vedere l'effetto
4. **Leggi** il codice in `demo_imaging.py` per capire il workflow
5. **Integra** questo sistema nel tuo gioco completo!

---

## 📚 Codice di Riferimento

Il demo usa tutti i moduli imaging:

```python
from imaging.camera import get_camera          # Simulazione camera
from imaging.frames import Frame, FrameType    # Gestione frames
from imaging.calibration import Calibrator     # Pipeline calibrazione
from imaging.stacking import StackingEngine    # Allineamento e stack
from imaging.processing import ImageProcessor  # Post-processing
```

Ogni parte è modulare e riutilizzabile!

---

## 🎉 Enjoy!

Questo demo dimostra che il sistema imaging è **completo, funzionante e realistico**.

Ora sei pronto per integrarlo nel gioco completo! 🚀✨

**Prossimo passo**: Observatory Hub e navigazione tra schermate (Sprint 1 completion)
