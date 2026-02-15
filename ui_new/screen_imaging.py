"""
Imaging Screen - Prima Luce

Photorealistic telescope imaging with:
- Real star catalog rendering (389k stars via SkyRenderer)
- Physical camera simulation (noise, dark current, read noise)
- Calibration pipeline (darks, flats)
- Stacking with sigma-clipping
- Live preview with histogram stretch
- Color (RGB) and monochrome modes
"""

import pygame
import numpy as np
import math
from typing import Optional
from datetime import datetime

from .base_screen import BaseScreen
from .components import Button
from imaging.camera import get_camera
from imaging.frames import Frame, FrameMetadata, FrameType
from imaging.calibration import Calibrator
from imaging.stacking import StackingEngine, StackMethod
from imaging.sky_renderer import SkyRenderer
from imaging.display_pipeline import DisplayPipeline
from atmosphere import AtmosphericModel, ObserverLocation
from universe.orbital_body import build_solar_system, datetime_to_jd
from datetime import datetime, timezone as _tz


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def _blit_image(surface, img_arr, black, white, gamma, rect, is_color=False):
    """Stretch + blit numpy array into rect. Returns actual blit rect."""
    span = max(white - black, 1.0)
    norm = np.clip((img_arr.astype(np.float32) - black) / span, 0.0, 1.0)
    norm = np.power(np.clip(norm, 1e-9, 1.0), 1.0 / max(gamma, 0.1))
    u8   = (norm * 255).astype(np.uint8)

    if is_color and u8.ndim == 3 and u8.shape[2] == 3:
        surf = pygame.surfarray.make_surface(u8.swapaxes(0, 1))
    else:
        if u8.ndim == 3:
            u8 = u8[..., 1]
        rgb = np.stack([u8, u8, u8], axis=-1)
        surf = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))

    surf = surf.convert()
    sw, sh = surf.get_size()
    scale  = min(rect.w / max(sw, 1), rect.h / max(sh, 1))
    tw, th = max(1, int(sw * scale)), max(1, int(sh * scale))
    scaled = pygame.transform.smoothscale(surf, (tw, th))
    br = pygame.Rect(rect.x + (rect.w - tw)//2, rect.y + (rect.h - th)//2, tw, th)
    surface.blit(scaled, br)
    return br


def _draw_hist(surface, rect, img_arr, black, white, color=(0,200,100)):
    pygame.draw.rect(surface, (3, 7, 3), rect)
    pygame.draw.rect(surface, (0, 60, 30), rect, 1)
    span = max(white - black, 1.0)
    norm = np.clip((img_arr.astype(np.float32) - black) / span, 0, 1)
    counts, _ = np.histogram(norm.ravel(), bins=128, range=(0, 1))
    peak = max(counts.max(), 1)
    bw = rect.w / 128.0
    for i, c in enumerate(counts):
        if c > 0:
            h = int((c / peak) * (rect.h - 2))
            pygame.draw.rect(surface, color,
                             (rect.x + int(i*bw), rect.bottom - h - 1,
                              max(1, int(bw)), h))


# ─────────────────────────────────────────────────────────────────────────────
# Screen
# ─────────────────────────────────────────────────────────────────────────────

class ImagingScreen(BaseScreen):

    EXP_PRESETS  = [1, 5, 15, 30, 60, 120, 300]
    NL_PRESETS   = [1, 3, 5, 10, 20]
    SEEING_LABELS = ["Excellent (1\")", "Good (2\")", "Average (3.5\")", "Poor (5\")"]
    SEEING_VALUES = [1.0, 2.0, 3.5, 5.0]
    STACK_METHODS = [StackMethod.MEAN, StackMethod.MEDIAN, StackMethod.SIGMA_CLIP]

    def __init__(self, state_manager):
        super().__init__("IMAGING")
        self.state_manager = state_manager

        # Camera
        state = state_manager.get_state()
        # ── Load camera from equipment state (default: allsky for dev) ──
        cid = getattr(state, 'camera_id', None) or "ALLSKY_ZWO174MM"
        if cid not in __import__('imaging.camera', fromlist=['CAMERA_DATABASE']).CAMERA_DATABASE:
            cid = "ALLSKY_ZWO174MM"
        self.camera = get_camera(cid, seed=42)
        if self.camera.spec.has_cooling:
            self.camera.set_cooling(True, -10.0)
        # Track which equipment is currently loaded (for on_enter reload check)
        self._loaded_camera_id    = cid
        self._loaded_telescope_id = getattr(state_manager.get_state(), 'telescope_id', None) or ''

        # Session params
        self.exp_idx  = 3    # 30s
        self.nl_idx   = 3    # 10 lights
        self.see_idx  = 1    # good seeing
        self.stk_idx  = 2    # sigma-clip
        self.color    = True

        # Atmospheric model + solar system bodies (must be before renderers)
        obs_lat = float(getattr(state_manager.get_state(), 'obs_latitude',  45.87) or 45.87)
        obs_lon = float(getattr(state_manager.get_state(), 'obs_longitude', 11.52) or 11.52)
        obs_alt = float(getattr(state_manager.get_state(), 'obs_altitude',  200.0) or 200.0)
        self._observer = ObserverLocation(
            latitude_deg=obs_lat, longitude_deg=obs_lon,
            altitude_m=obs_alt, name="Observatory",
            limiting_mag_zenith=21.5, base_seeing_arcsec=2.5,
        )
        self._atm_model   = AtmosphericModel(self._observer)
        self._solar_bodies = build_solar_system()
        self._sun  = next(b for b in self._solar_bodies if b.is_sun)
        self._moon = next(b for b in self._solar_bodies if b.is_moon)
        self._atm_state   = None  # computed fresh on each expose

        # Build renderer (normal telescope or allsky based on camera type)
        self.renderer        = self._make_renderer()
        self.allsky_renderer = (self._make_allsky_renderer()
                                if self.camera.spec.is_allsky else None)
        self.is_allsky       = self.camera.spec.is_allsky

        # Display pipeline — dimensioni render corrette per tipo camera
        self.pipeline = self._make_pipeline()

        # Frame storage
        self.lights:  list[Frame] = []
        self.darks:   list[Frame] = []
        self.flats:   list[Frame] = []
        self.cal:     list[Frame] = []
        self.stacked: Optional[np.ndarray] = None
        self.stk_rgb: Optional[np.ndarray] = None
        self.live:    Optional[np.ndarray] = None
        self.live_rgb:Optional[np.ndarray] = None
        self.master_dark = None
        self.master_flat = None

        # View
        self.view     = "LIVE"
        self._cached_surf = None
        self._cache_key   = None
        self._data_gen    = 0    # incremented each time new image data arrives
        self.fidx     = 0
        self.black    = 0.0
        self.white    = 1000.0
        self.gamma    = 2.2
        self.showhist = True

        # Log & status
        self.log: list[str] = []
        self.status = "Ready"
        info = self.renderer.get_info()
        self._log("=== IMAGING SYSTEM READY ===")
        self._log(f"Camera:  {self.camera.spec.name}")
        self._log(f"FOV:     {info['fov_deg'][0]:.2f}° × {info['fov_deg'][1]:.2f}°")
        self._log(f"Scale:   {info['pixel_scale_arcsec']:.2f}\"/px")
        self._log(f"PSF:     {info['psf_fwhm_arcsec']:.1f}\" FWHM")

        self.buttons: dict[str, Button] = {}
        self._build_btns()

    # ── Setup ────────────────────────────────────────────────────────────────

    def _make_renderer(self) -> SkyRenderer:
        """Build sky renderer from current equipment state.
        Se la camera è allsky standalone (telescope_id vuoto) usa
        parametri ottici fittizi — il renderer non verrà usato per il render."""
        from imaging.equipment import get_telescope
        state = self.state_manager.get_state()

        tel_id = getattr(state, 'telescope_id', None) or ''
        tel = get_telescope(tel_id) if tel_id else None
        if tel is not None:
            ap = tel.aperture_mm
            fl = tel.focal_length_mm
        else:
            # Allsky standalone o telescopio non trovato: parametri fittizi
            fl = 714.0
            ap = 102.0

        # Camera sensor
        px = self.camera.spec.pixel_size_um
        W, H = self.camera.spec.resolution

        # Render buffer: 1/4 sensor → 16× fewer pixels, fast rendering
        rW, rH = max(120, W//4), max(68, H//4)

        return SkyRenderer(
            aperture_mm=ap, focal_length_mm=fl,
            pixel_size_um=px, sensor_w=W, sensor_h=H,
            render_w=rW, render_h=rH,
            seeing_arcsec=self.SEEING_VALUES[self.see_idx],
            sky_background_mag=20.5,
        )

    def _make_allsky_renderer(self):
        """Build allsky renderer for fisheye cameras."""
        from imaging.allsky_renderer import AllSkyRenderer
        state = self.state_manager.get_state()
        lat = float(getattr(state, 'obs_latitude',  self._observer.latitude_deg)  or self._observer.latitude_deg)
        lon = float(getattr(state, 'obs_longitude', self._observer.longitude_deg) or self._observer.longitude_deg)
        size = min(self.camera.spec.resolution) // 4
        size = max(128, min(size, 512))
        return AllSkyRenderer(self.camera.spec, lat, lon, render_size=size)

    def _make_pipeline(self):
        """Build display pipeline with render dimensions matching current camera."""
        if self.is_allsky and self.allsky_renderer is not None:
            rW = rH = self.allsky_renderer.render_size
        else:
            rW, rH = self.renderer.render_w, self.renderer.render_h
        return DisplayPipeline(
            render_w=rW, render_h=rH,
            display_w=960, display_h=540,
            telescope_type="refractor",
            bloom_on=True, spikes_on=(not self.is_allsky),
            chrom_on=True, grain_on=True,
            bloom_strength=0.35, spike_strength=0.45, spike_len=6,
            chrom_shift=0.8, grain_strength=0.018,
            vignette_strength=0.40 if not self.is_allsky else 0.0,
            warmth=0.0, teal_shadows=0.3, saturation=1.15,
            stretch="asinh",
        )

    def _rebuild_seeing(self):
        sv = self.SEEING_VALUES[self.see_idx]
        self.renderer.seeing_arcsec = sv
        ap = self.renderer.aperture_mm
        ps = self.renderer.pixel_scale
        diff_s = (1.02 * 0.00055 / (ap/1000.0) * 206265.0 / 2.355) / ps
        see_s  = (sv / 2.355) / ps
        self.renderer.psf_sigma = max(0.8, math.sqrt(diff_s**2 + see_s**2))
        self.renderer._psf_cache.clear()

    def _build_btns(self):
        """Build buttons with positions relative to a 460px panel."""
        # All positions assume a ~460px wide left panel (scaled at draw time)
        X = 8
        BW = 136   # button width for 3-per-row layout in 460px
        BH = 28
        GAP = 4

        def bx(col): return X + col * (BW + GAP)   # 0,1,2 columns

        self._btn_lp = 460   # reference panel width for button layout
        self.buttons = {
            # Row 1: main acquisition actions
            'expose':    Button(bx(0), 82, BW, BH, "▶ EXPOSE",   callback=self._expose),
            'darks':     Button(bx(1), 82, BW, BH, "DARKS",       callback=self._darks),
            'flats':     Button(bx(2), 82, BW, BH, "FLATS",       callback=self._flats),
            # Row 2: processing
            'calibrate': Button(bx(0), 82+BH+GAP, BW, BH, "CALIBRATE", callback=self._calibrate),
            'stack':     Button(bx(1), 82+BH+GAP, BW, BH, "STACK",     callback=self._stack),
            'reset':     Button(bx(2), 82+BH+GAP, BW, BH, "RESET",     callback=self._reset),
            # View mode tabs (row 3)
            'v1': Button(X,       82+2*(BH+GAP), 88, 22, "LIVE",  callback=lambda: self._sv("LIVE")),
            'v2': Button(X+92,    82+2*(BH+GAP), 88, 22, "RAW",   callback=lambda: self._sv("RAW")),
            'v3': Button(X+184,   82+2*(BH+GAP), 88, 22, "CAL",   callback=lambda: self._sv("CAL")),
            'v4': Button(X+276,   82+2*(BH+GAP), 88, 22, "STACK", callback=lambda: self._sv("STACK")),
        }

    def _cy(self, p, d):
        if p == 'exp':
            self.exp_idx = max(0, min(len(self.EXP_PRESETS)-1, self.exp_idx + d))
        elif p == 'nl':
            self.nl_idx  = max(0, min(len(self.NL_PRESETS)-1,  self.nl_idx  + d))
        elif p == 'see':
            self.see_idx = max(0, min(3,                         self.see_idx + d))
            self._rebuild_seeing()

    def _tog_color(self):
        self.color = not self.color
        self.buttons['ct'].label = f"COLOR: {'ON' if self.color else 'OFF'}"
        self.live = None

    def _sv(self, v):
        self.view = v
        self.fidx = 0

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def _target(self):
        s = self.state_manager.get_state()
        name = getattr(s, 'selected_target', None) or "M42"
        ra   = float(getattr(s, 'selected_target_ra',  83.82) or 83.82)
        dec  = float(getattr(s, 'selected_target_dec', -5.39) or -5.39)
        return name, ra, dec

    def _sky_signal(self, exp_s):
        _, ra, dec = self._target()
        uni  = self.state_manager.get_universe()

        if self.is_allsky and self.allsky_renderer is not None:
            return self._sky_signal_allsky(exp_s, uni)

        mag_lim = 10.0 + math.log10(max(1, exp_s)) * 1.5
        if self._atm_state is not None:
            mag_lim = min(mag_lim, self._atm_state.naked_eye_limit + 6.0)

        W, H = self.renderer.render_w, self.renderer.render_h
        if self.color:
            rf = np.zeros((H, W), np.float32)
            gf = np.zeros((H, W), np.float32)
            bf = np.zeros((H, W), np.float32)
            self.renderer.render_rgb(rf, gf, bf, ra, dec, exp_s, uni, mag_lim,
                                     atm_state=self._atm_state)
            mono = rf*0.299 + gf*0.587 + bf*0.114
            rgb  = np.stack([rf, gf, bf], axis=-1)
        else:
            mono = self.renderer.render_field(ra, dec, exp_s, uni, mag_lim,
                                              atm_state=self._atm_state)
            rgb  = None
        return mono, rgb

    def _sky_signal_allsky(self, exp_s, universe):
        """Render full-sky hemisphere for allsky cameras."""
        from universe.orbital_body import datetime_to_jd
        from datetime import datetime, timezone as _tz2
        jd  = datetime_to_jd(datetime.now(_tz2.utc))
        mag_lim = 7.0   # allsky sees to ~magnitude 7 max
        if self._atm_state is not None:
            mag_lim = min(mag_lim, self._atm_state.naked_eye_limit + 1.0)
        rgb = self.allsky_renderer.render(jd, universe, exp_s,
                                           mag_lim, self._atm_state)
        mono = rgb[:,:,0]*0.299 + rgb[:,:,1]*0.587 + rgb[:,:,2]*0.114
        return mono, rgb

    def _expose(self):
        """
        Cattura frame light con l'esposizione selezionata.
        Il segnale sky viene ri-renderizzato alla durata corretta (non live 1s).
        Il live view continua indipendentemente via update().
        """
        name, ra, dec = self._target()
        exp_s = self.EXP_PRESETS[self.exp_idx]
        n     = self.NL_PRESETS[self.nl_idx]

        # Aggiorna stato atmosferico
        now_utc = datetime.now(_tz.utc)
        self._atm_state = self._atm_model.compute(now_utc, self._sun, self._moon)
        if not self._atm_state.imaging_allowed:
            phase_label = self._atm_state.day_phase.value.replace('_',' ').title()
            self._log(f"  ⚠ {phase_label} (Sol {self._atm_state.solar_alt_deg:+.1f}°)")

        # Aggiorna seeing
        atm_seeing = self._atm_state.seeing_fwhm_arcsec
        if not self.is_allsky and abs(atm_seeing - self.renderer.seeing_arcsec) > 0.1:
            self.renderer.seeing_arcsec = atm_seeing
            self.renderer._psf_cache.clear()

        self.status = f"Capturing {n}×{exp_s}s..."
        self._log(f"Expose {n}×{exp_s}s  target={name}  seeing={atm_seeing:.1f}\"")

        # Render segnale sky all'esposizione reale
        mono, rgb = self._sky_signal(exp_s)

        # Cattura N frame light (aggiunge rumore di camera diverso per ciascuno)
        for i in range(n):
            meta = FrameMetadata(
                frame_type=FrameType.LIGHT, exposure_s=exp_s,
                target_name=name,
                filter_name="ALLSKY" if self.is_allsky else ("RGB" if self.color else "L")
            )
            self.lights.append(self.camera.capture_frame(
                exp_s, mono, FrameType.LIGHT,
                frame_seed=len(self.lights)+i, metadata=meta
            ))

        # Passa a RAW view per mostrare i frame catturati (con rumore fisso)
        self._sv("RAW")
        d = self.lights[-1].data
        self.black = float(np.percentile(d, 0.5))
        self.white = float(np.percentile(d, 99.8))
        self._data_gen += 1
        self.status = f"✓ {n}×{exp_s}s  ({len(self.lights)} lights tot)"
        self._log(f"  Done — {len(self.lights)} lights")

    def _darks(self):
        exp_s = self.EXP_PRESETS[self.exp_idx]
        n = max(5, self.NL_PRESETS[self.nl_idx])
        if self.is_allsky and self.allsky_renderer:
            s = self.allsky_renderer.render_size
            rshape = (s, s)
        else:
            rshape = (self.renderer.render_h, self.renderer.render_w)
        self._log(f"Capturing {n} darks ({exp_s}s, {rshape[1]}×{rshape[0]})…")
        self.darks = [self.camera.capture_dark_frame(exp_s, frame_seed=500+i,
                                                      render_shape=rshape)
                      for i in range(n)]
        self.status = f"✓ {n} darks"
        self._log(f"  Done — {n} darks")

    def _flats(self):
        # Use render buffer size — must match light frames
        if self.is_allsky and self.allsky_renderer:
            s = self.allsky_renderer.render_size
            W = H = s
        else:
            W = self.renderer.render_w
            H = self.renderer.render_h
        yy, xx = np.mgrid[0:H, 0:W]
        cx, cy = W/2, H/2
        r = np.sqrt((xx-cx)**2 + (yy-cy)**2) / (min(W,H)/2)
        sig = np.clip((1.0 - 0.35*r**2.5)*15000, 3000, 20000).astype(np.float32)
        self.flats = [
            self.camera.capture_frame(
                1.0, sig, FrameType.FLAT,
                frame_seed=200+i,
                metadata=FrameMetadata(frame_type=FrameType.FLAT, exposure_s=1.0, filter_name="L")
            ) for i in range(10)
        ]
        self.status = "✓ 10 flats"
        self._log("  Done — 10 flats")

    def _calibrate(self):
        if not self.lights:
            self._log("ERROR: No lights!"); return
        self._log("Calibrating…")
        c = Calibrator()
        if self.darks:
            self.master_dark = c.create_master_dark(self.darks)
            self._log("  Master dark OK")
        if self.flats:
            self.master_flat = c.create_master_flat(self.flats)
            self._log("  Master flat OK")
        self.cal = c.batch_calibrate_lights(
            self.lights, master_dark=self.master_dark,
            master_flat=self.master_flat, apply_cosmetic=True
        )
        self._sv("CAL")
        self.status = f"✓ Calibrated {len(self.cal)} frames"
        self._log(f"  Done — {len(self.cal)} calibrated frames")

    def _stack(self):
        src = self.cal or self.lights
        if not src:
            self._log("ERROR: No frames to stack!"); return
        self._log(f"Stacking {len(src)} frames…")
        eng = StackingEngine()
        m   = self.STACK_METHODS[self.stk_idx]
        self.stacked = eng.stack(src, m)

        if self.live_rgb is not None and self.live is not None:
            scale = self.stacked.mean() / max(self.live.mean(), 1e-6)
            self.stk_rgb = (self.live_rgb * scale).astype(np.float32)

        snr = eng.compute_snr_improvement(len(src), m)
        self.black = float(np.percentile(self.stacked, 0.2))
        self.white = float(np.percentile(self.stacked, 99.9))
        self._sv("STACK")
        self.status = f"✓ Stacked — SNR ×{snr:.1f}  [{m.value}]"
        self._log(f"  Stack done  SNR +{snr:.1f}×")

        try:
            self.state_manager.get_career_mode().stats.research_points += 50
            self._log("  +50 RP awarded!")
        except Exception:
            pass

    def _reset(self):
        for lst in (self.lights, self.darks, self.flats, self.cal):
            lst.clear()
        self.stacked = self.stk_rgb = self.live = self.live_rgb = None
        self._cached_surf = None
        self._cache_key   = None
        self._sv("LIVE")
        self.status = "Session reset"
        self._log("Session reset")

    def _save(self):
        img = self._cur_img()
        if img is None:
            self._log("Nothing to save!"); return
        try:
            span = max(self.white - self.black, 1.0)
            norm = np.clip((img.astype(np.float32) - self.black) / span, 0, 1)
            norm = np.power(norm, 1.0/self.gamma)
            u8   = (norm*255).astype(np.uint8)
            if u8.ndim == 2:
                rgb = np.stack([u8]*3, axis=-1)
            else:
                rgb = u8
            surf = pygame.surfarray.make_surface(rgb.swapaxes(0,1))
            fn = f"astro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            pygame.image.save(surf, fn)
            self._log(f"Saved: {fn}")
            self.status = f"Saved {fn}"
        except Exception as e:
            self._log(f"Save error: {e}")

    # ── Image retrieval ──────────────────────────────────────────────────────

    def _cur_img(self):
        if self.view == "LIVE":   return self.live
        if self.view == "RAW"  and self.lights: return self.lights[min(self.fidx, len(self.lights)-1)].data
        if self.view == "CAL"  and self.cal:    return self.cal[min(self.fidx, len(self.cal)-1)].data
        if self.view == "STACK":  return self.stacked
        return None

    def _cur_rgb(self):
        if self.view in ("LIVE", "RAW"): return self.live_rgb
        if self.view == "STACK":          return self.stk_rgb
        return None

    def _log(self, msg):
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        if len(self.log) > 25: self.log.pop(0)

    # ── BaseScreen ───────────────────────────────────────────────────────────

    def on_enter(self):
        super().on_enter()
        self._reload_equipment_if_changed()
        name, ra, dec = self._target()
        self._log(f"Target: {name}  ({ra:.2f}°, {dec:+.2f}°)")
        # Avvia il live preview automatico
        self._live_timer = 0.0
        self._live_interval = 2.0   # secondi tra aggiornamenti live
        self._update_live_preview()  # primo frame immediato

    def _reload_equipment_if_changed(self):
        """Re-create camera and renderer if equipment selection changed."""
        from imaging.camera import CAMERA_DATABASE
        state = self.state_manager.get_state()

        # What is currently selected?
        new_cid = getattr(state, 'camera_id', None) or 'ALLSKY_ZWO174MM'
        new_tid = getattr(state, 'telescope_id', None) or ''

        # What are we currently using?
        cur_cid = self.camera.spec.name  # not ideal but camera has no id attr
        # Use a tracking attribute instead
        cur_cid = getattr(self, '_loaded_camera_id', None)
        cur_tid = getattr(self, '_loaded_telescope_id', None)

        if new_cid == cur_cid and new_tid == cur_tid:
            return   # nothing changed

        self._log(f"Equipment changed: {new_cid} + {new_tid}")

        # Re-create camera
        if new_cid not in CAMERA_DATABASE:
            new_cid = 'ALLSKY_ZWO174MM'
        self.camera = __import__('imaging.camera', fromlist=['get_camera']).get_camera(new_cid, seed=42)
        if self.camera.spec.has_cooling:
            self.camera.set_cooling(True, -10.0)

        # Re-create renderer(s)
        self.renderer        = self._make_renderer()
        self.allsky_renderer = (self._make_allsky_renderer()
                                if self.camera.spec.is_allsky else None)
        self.is_allsky = self.camera.spec.is_allsky

        # Update display pipeline with correct render dimensions
        self.pipeline = self._make_pipeline()

        # Reset session data (camera changed = incompatible frames)
        for lst in (self.lights, self.darks, self.flats, self.cal):
            lst.clear()
        self.stacked = self.stk_rgb = self.live = self.live_rgb = None
        self._cached_surf = None
        self._cache_key   = None

        # Track what we loaded
        self._loaded_camera_id    = new_cid
        self._loaded_telescope_id = new_tid
        self._log(f"  Camera: {self.camera.spec.name}  allsky={self.is_allsky}")

    def on_exit(self): super().on_exit()
    def update(self, dt):
        """Aggiorna live preview periodicamente."""
        if not hasattr(self, '_live_timer'):
            self._live_timer = 0.0
            self._live_interval = 2.0
        self._live_timer += dt
        if self._live_timer >= self._live_interval:
            self._live_timer = 0.0
            self._update_live_preview()

    def _update_live_preview(self):
        """Render live sky — usa esposizione breve, non cattura frame light."""
        try:
            uni = self.state_manager.get_universe()
            # Esposizione live breve (1s) per preview fluido
            live_exp = 1.0
            now_utc = datetime.now(_tz.utc)
            self._atm_state = self._atm_model.compute(now_utc, self._sun, self._moon)
            mono, rgb = self._sky_signal(live_exp)
            self.live     = mono
            self.live_rgb = rgb
            # Calcola stretch automatico dal segnale live
            if mono is not None:
                self.black = float(np.percentile(mono, 0.5))
                self.white = float(np.percentile(mono, 99.5))
            # Invalida cache display per mostrare il nuovo frame
            self._cached_surf = None
            self._cache_key   = None
            self._data_gen   += 1
        except Exception as e:
            pass  # live preview non blocca mai

    def handle_input(self, events) -> Optional[str]:
        mp = pygame.mouse.get_pos()
        for b in self.buttons.values(): b.update(mp)
        for event in events:
            for b in self.buttons.values(): b.handle_event(event)
            if event.type == pygame.KEYDOWN:
                k = event.key
                if   k == pygame.K_ESCAPE:        return "OBSERVATORY"
                elif k == pygame.K_g:             self._expose()
                elif k == pygame.K_c:             self._calibrate()
                elif k == pygame.K_k:             self._stack()
                elif k == pygame.K_s:             self._save()
                elif k == pygame.K_1:             self._sv("LIVE")
                elif k == pygame.K_2:             self._sv("RAW")
                elif k == pygame.K_3:             self._sv("CAL")
                elif k == pygame.K_4:             self._sv("STACK")
                elif k == pygame.K_h:             self.showhist = not self.showhist
                elif k == pygame.K_LEFTBRACKET:   self.fidx = max(0, self.fidx-1)
                elif k == pygame.K_RIGHTBRACKET:
                    mx = max(0, len(self.lights if self.view=="RAW" else self.cal)-1)
                    self.fidx = min(mx, self.fidx+1)
                elif k == pygame.K_MINUS:         self.white = max(self.black+10, self.white*0.85)
                elif k == pygame.K_EQUALS:        self.white *= 1.15
                elif k == pygame.K_COMMA:         self.black = max(0, self.black - self.white*0.03)
                elif k == pygame.K_PERIOD:        self.black += self.white*0.03
        return None

    # ── Render ───────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface):
        W, H = surface.get_size()
        surface.fill((4, 7, 10))

        LP = min(480, max(300, W // 3))  # left panel: 1/3 of screen, 300-480px
        self._draw_header(surface, W)
        self._draw_left(surface, LP, H)
        self._draw_viewer(surface, LP, W, H)

        # Footer
        f = pygame.font.SysFont('monospace', 10)
        surface.blit(
            f.render("[G] Expose  [C] Calibrate  [K] Stack  [S] Save  [1-4] View  [H] Hist  [ESC] Back",
                     True, (0, 80, 40)),
            (8, H-16)
        )

    def _draw_header(self, surface, W):
        pygame.draw.rect(surface, (0, 18, 10), (0, 0, W, 76))
        pygame.draw.line(surface, (0, 100, 50), (0, 76), (W, 76), 1)
        fb = pygame.font.SysFont('monospace', 18, bold=True)
        fs = pygame.font.SysFont('monospace', 11)

        surface.blit(fb.render("◆ IMAGING SYSTEM — PRIMA LUCE", True, (0, 220, 100)), (12, 8))

        name, ra, dec = self._target()
        surface.blit(fs.render(f"TARGET: {name}   RA {ra:.2f}°  Dec {dec:+.2f}°",
                               True, (0, 170, 80)), (12, 32))

        info = self.renderer.get_info()
        surface.blit(fs.render(
            f"Camera: {self.camera.spec.name}  |  "
            f"FOV {info['fov_deg'][0]:.2f}°×{info['fov_deg'][1]:.2f}°  |  "
            f"{info['pixel_scale_arcsec']:.2f}\"/px  |  "
            f"PSF {info['psf_fwhm_arcsec']:.1f}\" FWHM  |  "
            f"Seeing {info['seeing_arcsec']}\"  |  "
            f"Temp {self.camera.temperature_c:.0f}°C",
            True, (0, 130, 65)), (12, 52))

        stxt = fs.render(f"● {self.status}", True, (0, 200, 100))
        surface.blit(stxt, (W - stxt.get_width() - 12, 28))

        # Atmospheric phase indicator (top-right)
        if self._atm_state is not None:
            from atmosphere import get_phase_properties
            pp  = get_phase_properties(self._atm_state.day_phase)
            ac  = pp.ui_color
            phase_str = self._atm_state.day_phase.value.replace('_', ' ').title()
            sol_str   = f"Sol {self._atm_state.solar_alt_deg:+.0f}°"
            see_str   = "see " + f"{self._atm_state.seeing_fwhm_arcsec:.1f}" + chr(34)
            atm_txt   = fs.render(f"◉ {phase_str}  {sol_str}  {see_str}", True, ac)
            surface.blit(atm_txt, (W - atm_txt.get_width() - 12, 48))

        try:
            rp = self.state_manager.get_career_mode().stats.research_points
            rtxt = fs.render(f"RP: {rp}", True, (200, 200, 0))
            surface.blit(rtxt, (W - rtxt.get_width() - 12, 62))
        except Exception:
            pass

    def _draw_left(self, surface, LP, H):
        """
        Left control panel — clean vertical flow layout.
        All sections use a running `y` counter to avoid overlap.
        Buttons are scaled to fit LP.
        """
        pygame.draw.rect(surface, (3, 9, 6), (0, 77, LP, H-95))
        pygame.draw.line(surface, (0, 70, 35), (LP, 77), (LP, H-20), 1)

        f  = pygame.font.SysFont('monospace', 11)
        fb = pygame.font.SysFont('monospace', 11, bold=True)
        fl = pygame.font.SysFont('monospace', 10)
        C  = (0, 190, 100);  D = (0, 90, 45);  Y = (200, 200, 0)

        # Scale button positions to actual LP width
        ref_lp  = getattr(self, '_btn_lp', 460)
        x_scale = LP / ref_lp
        for name, btn in self.buttons.items():
            btn.draw(surface, x_scale=x_scale)

        # View mode highlight (scaled)
        row3_y = 82 + 2 * (28 + 4)
        vx = {"LIVE": 8, "RAW": 8+92, "CAL": 8+184, "STACK": 8+276}
        if self.view in vx:
            bx = int(vx[self.view] * x_scale)
            bw = int(88 * x_scale)
            pygame.draw.rect(surface, (0, 170, 80), (bx, row3_y, bw, 22), 2)

        y = row3_y + 28   # start just below view tabs

        # ── Acquisition params ───────────────────────────────────────────
        surface.blit(fb.render("ACQUISITION", True, D), (8, y)); y += 14
        exp_s = self.EXP_PRESETS[self.exp_idx]
        n_l   = self.NL_PRESETS[self.nl_idx]
        surface.blit(f.render(f"Exp  {exp_s}s   [</>]", True, C), (8, y)); y += 13
        surface.blit(f.render(f"Frames {n_l}    [</>]", True, C), (8, y)); y += 13
        mode_str = "ALLSKY" if self.is_allsky else ("RGB" if self.color else "MONO")
        surface.blit(f.render(f"Mode: {mode_str}", True, C), (8, y)); y += 16

        # ── Atmosphere ───────────────────────────────────────────────────
        if self._atm_state is not None:
            from atmosphere import get_phase_properties
            atm = self._atm_state
            pp  = get_phase_properties(atm.day_phase)
            ac  = pp.ui_color
            surface.blit(fb.render("ATMOSPHERE", True, D), (8, y)); y += 14
            phase_short = atm.day_phase.value.replace('_', ' ').title()
            surface.blit(f.render(f"Phase: {phase_short}", True, ac), (8, y)); y += 13
            surface.blit(f.render(
                f"Sol {atm.solar_alt_deg:+.0f}°  "
                f"Moon {atm.moon_alt_deg:+.0f}° {atm.moon_phase_fraction:.0%}",
                True, C), (8, y)); y += 13
            img_col = C if atm.imaging_allowed else (220, 90, 0)
            img_str = "OK" if atm.imaging_allowed else "BLOCKED"
            see_val = f"{atm.seeing_fwhm_arcsec:.1f}\""
            surface.blit(f.render(
                f"See {see_val}  Img: {img_str}", True, img_col), (8, y)); y += 16

        # ── Session status ───────────────────────────────────────────────
        surface.blit(fb.render("SESSION", True, D), (8, y)); y += 14
        for label, count, col in [
            ("Lights",     len(self.lights), C),
            ("Darks",      len(self.darks),  (0, 160, 80)),
            ("Flats",      len(self.flats),  (0, 160, 80)),
            ("Calibrated", len(self.cal),    C),
            ("Stacked",    1 if self.stacked is not None else 0, Y),
        ]:
            bw = min(80, count * 8)
            pygame.draw.rect(surface, (0, 25, 12), (8, y, 80, 12))
            if bw: pygame.draw.rect(surface, col, (8, y, bw, 12))
            surface.blit(fl.render(f"{label}: {count}", True, col), (95, y+1))
            y += 15
        y += 4

        # ── Stacking ─────────────────────────────────────────────────────
        surface.blit(fb.render("STACKING", True, D), (8, y)); y += 14
        for i, m in enumerate(self.STACK_METHODS):
            col = (0, 220, 110) if i == self.stk_idx else D
            pre = ">" if i == self.stk_idx else " "
            surface.blit(fl.render(f"{pre} {m.value}", True, col), (8, y)); y += 13
        y += 4

        # ── Stretch ──────────────────────────────────────────────────────
        surface.blit(fb.render("STRETCH", True, D), (8, y)); y += 13
        surface.blit(fl.render(f"Black {self.black:7.0f}  [,/.]", True, C), (8, y)); y += 12
        surface.blit(fl.render(f"White {self.white:7.0f}  [-/=]", True, C), (8, y)); y += 12
        surface.blit(fl.render(f"Gamma {self.gamma:.1f}  Color:{"RGB" if self.color else "MONO"}  [C]", True, C), (8, y)); y += 12

        # ── Log ──────────────────────────────────────────────────────────
        available = H - y - 28
        max_lines = max(3, available // 12)
        surface.blit(fb.render("LOG", True, D), (8, y)); y += 13
        for line in self.log[-max_lines:]:
            if y > H - 25: break
            surface.blit(fl.render(line[:58], True, D), (8, y)); y += 12


    def _draw_viewer(self, surface, LP, W, H):
        px = LP + 4
        pw = W - LP - 8
        ph = H - 100
        panel = pygame.Rect(px, 78, pw, ph)
        pygame.draw.rect(surface, (1, 4, 2), panel)
        pygame.draw.rect(surface, (0, 70, 35), panel, 1)

        fb = pygame.font.SysFont('monospace', 11, bold=True)
        fs = pygame.font.SysFont('monospace', 11)
        C  = (0, 190, 100);  D = (0, 90, 45)

        # Title
        mode_col = {
            "LIVE": (0,200,100), "RAW": (100,200,100),
            "CAL": (100,200,200), "STACK": (200,200,0)
        }.get(self.view, C)
        surface.blit(fb.render(f"[ {self.view} ]  IMAGE VIEWER", True, mode_col), (px+6, 82))

        hist_h   = 65 if self.showhist else 0
        img_rect = pygame.Rect(px+4, 98, pw-8, ph - 130 - hist_h)
        pygame.draw.rect(surface, (0, 0, 0), img_rect)

        img = self._cur_img()
        rgb = self._cur_rgb()

        if img is not None:
            # Resize pipeline display target to match viewer rect
            self.pipeline.display_w = img_rect.w
            self.pipeline.display_h = img_rect.h

            # Cache key — only reprocess when data or stretch params change
            use_rgb  = self.color and rgb is not None
            cache_key = (
                self.view, self.fidx,
                round(self.black, 1), round(self.white, 1),
                round(self.gamma, 2),
                img_rect.w, img_rect.h,
                # Use a data generation counter instead of id() —
                # id() can collide if the old array is freed and a new one
                # allocated at the same address
                getattr(self, '_data_gen', 0),
            )
            if self._cached_surf is None or self._cache_key != cache_key:
                if use_rgb:
                    proc_surf = self.pipeline.process_rgb(rgb, self.black, self.white)
                else:
                    proc_surf = self.pipeline.process(img, self.black, self.white)
                self._cached_surf = proc_surf
                self._cache_key   = cache_key
            else:
                proc_surf = self._cached_surf

            surface.blit(proc_surf, img_rect.topleft)

            # Pipeline info overlay (top-right corner)
            pinfo = self.pipeline.get_settings()
            pi_txt = (f"Render {pinfo['render']}  ↑{pinfo['upscale']}  "
                      f"{'▲spk ' if pinfo['spikes'] else ''}"
                      f"{'✦blm ' if pinfo['bloom'] else ''}"
                      f"{'⊕chr' if pinfo['chrom'] else ''}")
            pi_surf = fs.render(pi_txt, True, (0, 80, 40))
            surface.blit(pi_surf, (img_rect.right - pi_surf.get_width() - 4,
                                   img_rect.top + 3))

            # Stats
            sy = img_rect.bottom + 3
            n_frames = len(self.lights if self.view == "RAW" else self.cal)
            fi = f"  Frame {self.fidx+1}/{n_frames}" if self.view in ("RAW","CAL") and n_frames else ""
            surface.blit(fs.render(
                f"{img.shape[1]}×{img.shape[0]}  "
                f"Min:{np.min(img):.0f}  Max:{np.max(img):.0f}  "
                f"Mean:{np.mean(img):.0f}{fi}",
                True, D), (px+6, sy))

            # Histogram
            if self.showhist:
                hr = pygame.Rect(px+4, panel.bottom - hist_h - 6, pw-8, hist_h-4)
                if self.color and rgb is not None:
                    for ch, col in enumerate([(180,60,60),(60,180,60),(60,60,200)]):
                        _draw_hist(surface, hr, rgb[:,:,ch], self.black, self.white, col)
                else:
                    _draw_hist(surface, hr, img, self.black, self.white)
                surface.blit(fs.render("[H] histogram  [,/.] black  [-/=] white",
                                       True, D), (px+6, hr.bottom+2))
        else:
            # Empty
            cx, cy = img_rect.centerx, img_rect.centery
            fh = pygame.font.SysFont('monospace', 14)
            msgs = [
                ("No image — ready for first light!", (0,200,100)),
                ("", None),
                ("  1. Select a target in CATALOG BROWSER", (0,140,70)),
                ("  2. Press [G] or ▶ EXPOSE", (0,140,70)),
                ("  3. Press [C] to calibrate with darks+flats", (0,120,60)),
                ("  4. Press [K] to stack frames", (0,120,60)),
            ]
            for i, (line, col) in enumerate(msgs):
                if col:
                    t = fh.render(line, True, col)
                    surface.blit(t, (cx - t.get_width()//2, cy - 60 + i*24))
