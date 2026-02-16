"""
Imaging Screen  —  3-tab redesign
===================================
TAB 0  LIVE      — live sky, pointing data, sensor/ext temp, gain control, time controls
TAB 1  CAPTURE   — exposure/frames/gain/filter/calibration setup, acquire button
TAB 2  PROCESS   — fixed image (no auto-update), histogram sliders, calibrate+stack
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
from universe.orbital_body import build_solar_system
from core.time_controller import TimeController
from datetime import datetime, timezone as _tz


# ── Colours ──────────────────────────────────────────────────────────────────
_C  = (0,   200, 100)
_D  = (0,    80,  40)
_Y  = (200, 200,   0)
_W  = (210, 220, 210)
_BG = (3,    9,   6)
_LN = (0,   60,  30)


# ── Font cache ────────────────────────────────────────────────────────────────
_FC: dict = {}
def _f(size: int, bold: bool = False):
    k = (size, bold)
    if k not in _FC:
        _FC[k] = pygame.font.SysFont('monospace', size, bold=bold)
    return _FC[k]


# ── Draw helpers ──────────────────────────────────────────────────────────────
def _txt(surf, x, y, text, col=_C, sz=11):
    surf.blit(_f(sz).render(text, True, col), (x, y))
    return y + sz + 2

def _sec(surf, x, y, title):
    surf.blit(_f(10, bold=True).render(title, True, _D), (x, y))
    pygame.draw.line(surf, _D, (x, y+12), (x+220, y+12), 1)
    return y + 16


# ── Slider widget ─────────────────────────────────────────────────────────────
class _Slider:
    def __init__(self, x, y, w, h, lo, hi, val, label, col=_C):
        self.rect  = pygame.Rect(x, y, w, h)
        self.lo    = float(lo); self.hi = float(hi)
        self.value = float(val)
        self.label = label; self.col = col
        self._drag = False

    def set_rect(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def handle(self, ev) -> bool:
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                self._drag = True; self._px(ev.pos[0]); return True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._drag = False
        elif ev.type == pygame.MOUSEMOTION and self._drag:
            self._px(ev.pos[0]); return True
        return False

    def _px(self, mx):
        t = (mx - self.rect.x) / max(self.rect.w, 1)
        self.value = self.lo + max(0.0, min(1.0, t)) * (self.hi - self.lo)

    def draw(self, surf):
        r = self.rect
        pygame.draw.rect(surf, _D, r)
        t  = (self.value - self.lo) / max(self.hi - self.lo, 1e-9)
        fw = max(0, int(r.w * t))
        if fw: pygame.draw.rect(surf, self.col, (r.x, r.y, fw, r.h))
        pygame.draw.rect(surf, _W, (r.x + fw - 2, r.y - 1, 4, r.h + 2))
        pygame.draw.rect(surf, self.col, r, 1)
        surf.blit(_f(10).render(f"{self.label}: {self.value:.0f}", True, _W),
                  (r.x + 4, r.y + r.h + 2))


# ── Histogram draw ────────────────────────────────────────────────────────────
def _hist(surf, rect, arr, bk, wh, col=_C):
    pygame.draw.rect(surf, (2, 5, 2), rect)
    span = max(wh - bk, 1.0)
    norm = np.clip((arr.astype(np.float32) - bk) / span, 0, 1)
    counts, _ = np.histogram(norm.ravel(), bins=rect.w, range=(0, 1))
    pk = max(counts.max(), 1)
    for i, c in enumerate(counts):
        if c:
            h = int((c / pk) * (rect.h - 2))
            pygame.draw.rect(surf, col, (rect.x + i, rect.bottom - h - 1, 1, h))
    # markers
    t_bk = (bk - 0) / max(wh * 1.2, 1) * rect.w
    t_wh = wh / max(wh * 1.2, 1) * rect.w
    bx = int(rect.x + t_bk); wx = int(rect.x + t_wh)
    pygame.draw.line(surf, (80, 80, 220),  (max(bx, rect.x), rect.y), (max(bx, rect.x), rect.bottom), 1)
    pygame.draw.line(surf, (220, 220, 80), (min(wx, rect.right-1), rect.y), (min(wx, rect.right-1), rect.bottom), 1)
    pygame.draw.rect(surf, _LN, rect, 1)


# ─────────────────────────────────────────────────────────────────────────────
class ImagingScreen(BaseScreen):

    EXP_STEPS    = [1, 5, 10, 15, 30, 60, 120, 300]
    NL_STEPS     = [1, 3, 5, 10, 20, 30, 50]
    GAIN_STEPS   = [0, 50, 100, 150, 200, 300, 400]
    DARK_STEPS   = [0, 5, 10, 20, 30]
    FLAT_STEPS   = [0, 5, 10, 20, 30]
    STK_METHODS  = [StackMethod.MEAN, StackMethod.MEDIAN, StackMethod.SIGMA_CLIP]
    STK_LABELS   = ["Mean", "Median", "Sigma-clip"]

    # ── Init ─────────────────────────────────────────────────────────────────
    def __init__(self, state_manager):
        super().__init__("IMAGING")
        self.state_manager = state_manager
        self.tab = 0   # 0=LIVE 1=CAPTURE 2=PROCESS

        # ── Camera/equipment ─────────────────────────────────────────────
        state = state_manager.get_state()
        from imaging.camera import CAMERA_DATABASE
        cid = getattr(state, 'camera_id', None) or "ALLSKY_ZWO174MM"
        if cid not in CAMERA_DATABASE: cid = "ALLSKY_ZWO174MM"
        self.camera = get_camera(cid, seed=42)
        if self.camera.spec.has_cooling:
            self.camera.set_cooling(True, -10.0)
        self._loaded_camera_id    = cid
        self._loaded_telescope_id = getattr(state, 'telescope_id', None) or ''

        # ── Observer / atmosphere / time ─────────────────────────────────
        obs_lat = float(getattr(state, 'obs_latitude',  45.87) or 45.87)
        obs_lon = float(getattr(state, 'obs_longitude', 11.52) or 11.52)
        obs_alt = float(getattr(state, 'obs_altitude',  200.0) or 200.0)
        self._observer = ObserverLocation(
            latitude_deg=obs_lat, longitude_deg=obs_lon, altitude_m=obs_alt,
            name="Observatory", limiting_mag_zenith=21.5, base_seeing_arcsec=2.5)
        self._atm_model    = AtmosphericModel(self._observer)
        self._solar_bodies = build_solar_system()
        self._sun  = next(b for b in self._solar_bodies if b.is_sun)
        self._moon = next(b for b in self._solar_bodies if b.is_moon)
        self._atm_state    = None
        self._tc           = TimeController()

        # ── Renderers ────────────────────────────────────────────────────
        self.renderer        = self._make_renderer()
        self.allsky_renderer = self._make_allsky_renderer() if self.camera.spec.is_allsky else None
        self.is_allsky       = self.camera.spec.is_allsky
        self.pipeline        = self._make_pipeline()

        # ── Acquisition params ────────────────────────────────────────────
        self.exp_idx  = 4   # 30s
        self.nl_idx   = 3   # 10 lights
        self.gain_idx = 1   # 50
        self.dark_idx = 2   # 10 darks
        self.flat_idx = 2   # 10 flats
        self.stk_idx  = 2   # sigma-clip
        self.color    = True

        # ── Frame storage ─────────────────────────────────────────────────
        self.lights:  list = []
        self.darks:   list = []
        self.flats:   list = []
        self.cal:     list = []
        self.stacked: Optional[np.ndarray] = None
        self.stk_rgb: Optional[np.ndarray] = None
        self.live:    Optional[np.ndarray] = None
        self.live_rgb:Optional[np.ndarray] = None
        self.master_dark = None
        self.master_flat = None

        # ── Process/stretch state ─────────────────────────────────────────
        self.black = 0.0; self.white = 1000.0; self.gamma = 2.2
        self._proc_surf    = None   # fixed cached surface (Tab 2)
        self._proc_ck      = None
        self._proc_datagen = 0

        # ── Live update timer ─────────────────────────────────────────────
        self._live_timer    = 0.0
        self._live_interval = 2.0

        # ── Log ───────────────────────────────────────────────────────────
        self.log: list[str] = []
        self.status = "Ready"
        self._log("=== IMAGING SYSTEM READY ===")
        self._log(f"Camera: {self.camera.spec.name}")

        # ── Sliders (created lazily with screen coords) ───────────────────
        self._sl_black: Optional[_Slider] = None
        self._sl_white: Optional[_Slider] = None
        self._sl_gamma: Optional[_Slider] = None

        # ── Buttons ───────────────────────────────────────────────────────
        self._btn: dict[str, Button] = {}
        self._build_btns()

    # ── Equipment ─────────────────────────────────────────────────────────────
    def _reload_if_changed(self):
        from imaging.camera import CAMERA_DATABASE
        state = self.state_manager.get_state()
        cid = getattr(state, 'camera_id', None) or 'ALLSKY_ZWO174MM'
        tid = getattr(state, 'telescope_id', None) or ''
        if cid == self._loaded_camera_id and tid == self._loaded_telescope_id:
            return
        if cid not in CAMERA_DATABASE: cid = 'ALLSKY_ZWO174MM'
        self.camera = get_camera(cid, seed=42)
        if self.camera.spec.has_cooling: self.camera.set_cooling(True, -10.0)
        self.renderer        = self._make_renderer()
        self.allsky_renderer = self._make_allsky_renderer() if self.camera.spec.is_allsky else None
        self.is_allsky       = self.camera.spec.is_allsky
        self.pipeline        = self._make_pipeline()
        for lst in (self.lights, self.darks, self.flats, self.cal): lst.clear()
        self.stacked = self.stk_rgb = self.live = self.live_rgb = None
        self._proc_surf = None
        self._loaded_camera_id = cid; self._loaded_telescope_id = tid
        self._log(f"Equipment → {cid}")

    # ── Renderer factory ──────────────────────────────────────────────────────
    def _make_renderer(self) -> SkyRenderer:
        from imaging.equipment import get_telescope
        state  = self.state_manager.get_state()
        tel_id = getattr(state, 'telescope_id', None) or ''
        tel    = get_telescope(tel_id) if tel_id else None
        ap, fl = (tel.aperture_mm, tel.focal_length_mm) if tel else (102.0, 714.0)
        px     = self.camera.spec.pixel_size_um
        W, H   = self.camera.spec.resolution
        rW, rH = max(120, W//4), max(68, H//4)
        return SkyRenderer(aperture_mm=ap, focal_length_mm=fl,
                           pixel_size_um=px, sensor_w=W, sensor_h=H,
                           render_w=rW, render_h=rH,
                           seeing_arcsec=2.0, sky_background_mag=20.5)

    def _make_allsky_renderer(self):
        from imaging.allsky_renderer import AllSkyRenderer
        state = self.state_manager.get_state()
        lat   = float(getattr(state, 'obs_latitude',  self._observer.latitude_deg) or 45.87)
        lon   = float(getattr(state, 'obs_longitude', self._observer.longitude_deg) or 11.52)
        # 512px render buffer: upscale ~2× to display → stars are 1-2px, not blobs
        # (304px was upscaling 3.3× — turning 1px stars into 3px blobs)
        return AllSkyRenderer(self.camera.spec, lat, lon, render_size=512)

    def _make_pipeline(self) -> DisplayPipeline:
        if self.is_allsky and self.allsky_renderer:
            rW = rH = self.allsky_renderer.render_size
            pipe = DisplayPipeline(
                render_w=rW, render_h=rH, display_w=960, display_h=540,
                telescope_type="refractor",
                bloom_on=True,  spikes_on=False,
                chrom_on=False, grain_on=True,
                bloom_strength=0.06, grain_strength=0.002,
                vignette_strength=0.0,
                warmth=0.0, teal_shadows=0.0,  saturation=0.75, stretch="asinh")
            # Bilinear upscale for allsky: eliminates square pixel blobs
            pipe._smooth_upscale = True
            return pipe
        else:
            rW, rH = self.renderer.render_w, self.renderer.render_h
            return DisplayPipeline(
                render_w=rW, render_h=rH, display_w=960, display_h=540,
                telescope_type="refractor",
                bloom_on=True, spikes_on=True,
                chrom_on=True, grain_on=True,
                bloom_strength=0.35, spike_strength=0.45, spike_len=6,
                chrom_shift=0.8, grain_strength=0.018,
                vignette_strength=0.40,
                warmth=0.0, teal_shadows=0.3, saturation=1.15, stretch="asinh")

    # ── Buttons ───────────────────────────────────────────────────────────────
    def _build_btns(self):
        B = Button
        b = {}

        # ── Global ────────────────────────────────────────────────────────
        b['back']       = B(0,0,  80,18, "◄ BACK",       callback=lambda: self._nav('OBSERVATORY'))

        # ── Tab 0 LIVE — time controls ────────────────────────────────────
        b['tc_pause']   = B(0,0,  70,22, "⏸ PAUSE",      callback=lambda: self._tc.toggle_pause())
        b['tc_rt']      = B(0,0,  60,22, "⟳ RT",         callback=lambda: self._tc.realtime())
        b['tc_rev']     = B(0,0,  38,22, "◀◀",           callback=lambda: self._tc.reverse())
        b['tc_slow']    = B(0,0,  38,22, "−",            callback=lambda: self._tc.speed_down())
        b['tc_fast']    = B(0,0,  38,22, "+",            callback=lambda: self._tc.speed_up())

        # ── Tab 0 LIVE — gain ─────────────────────────────────────────────
        b['gain_dn']    = B(0,0,  32,22, "−",            callback=lambda: self._adj('gain_idx', -1, len(self.GAIN_STEPS)-1))
        b['gain_up']    = B(0,0,  32,22, "+",            callback=lambda: self._adj('gain_idx', +1, len(self.GAIN_STEPS)-1))

        # ── Tab 0 LIVE — go to capture ────────────────────────────────────
        b['to_capture'] = B(0,0, 200,28, "⊕ SET UP CAPTURE →", callback=lambda: self._set_tab(1))

        # ── Tab 1 CAPTURE — param steppers ───────────────────────────────
        b['exp_dn']     = B(0,0,32,20,"−", callback=lambda: self._adj('exp_idx',  -1, len(self.EXP_STEPS)-1))
        b['exp_up']     = B(0,0,32,20,"+", callback=lambda: self._adj('exp_idx',  +1, len(self.EXP_STEPS)-1))
        b['nl_dn']      = B(0,0,32,20,"−", callback=lambda: self._adj('nl_idx',   -1, len(self.NL_STEPS)-1))
        b['nl_up']      = B(0,0,32,20,"+", callback=lambda: self._adj('nl_idx',   +1, len(self.NL_STEPS)-1))
        b['cap_gain_dn']= B(0,0,32,20,"−", callback=lambda: self._adj('gain_idx', -1, len(self.GAIN_STEPS)-1))
        b['cap_gain_up']= B(0,0,32,20,"+", callback=lambda: self._adj('gain_idx', +1, len(self.GAIN_STEPS)-1))
        b['dark_dn']    = B(0,0,32,20,"−", callback=lambda: self._adj('dark_idx', -1, len(self.DARK_STEPS)-1))
        b['dark_up']    = B(0,0,32,20,"+", callback=lambda: self._adj('dark_idx', +1, len(self.DARK_STEPS)-1))
        b['flat_dn']    = B(0,0,32,20,"−", callback=lambda: self._adj('flat_idx', -1, len(self.FLAT_STEPS)-1))
        b['flat_up']    = B(0,0,32,20,"+", callback=lambda: self._adj('flat_idx', +1, len(self.FLAT_STEPS)-1))
        b['stk_dn']     = B(0,0,32,20,"−", callback=lambda: self._adj('stk_idx',  -1, len(self.STK_METHODS)-1))
        b['stk_up']     = B(0,0,32,20,"+", callback=lambda: self._adj('stk_idx',  +1, len(self.STK_METHODS)-1))
        b['color_tog']  = B(0,0,100,20,"RGB/MONO",    callback=self._toggle_color)

        # ── Tab 1 CAPTURE — acquire ───────────────────────────────────────
        b['acquire']    = B(0,0,220,30,"▶▶ ACQUIRE SEQUENCE", callback=self._expose)
        b['cap_darks']  = B(0,0,130,24,"⬛ CAP DARKS",        callback=self._darks)
        b['cap_flats']  = B(0,0,130,24,"▪ CAP FLATS",         callback=self._flats)
        b['reset']      = B(0,0,110,24,"✕ RESET SESSION",     callback=self._reset)

        # ── Tab 2 PROCESS — actions ───────────────────────────────────────
        b['calibrate']  = B(0,0,140,26,"⚙ CALIBRATE",  callback=self._calibrate)
        b['stack']      = B(0,0,140,26,"⊞ STACK",       callback=self._stack)
        b['save']       = B(0,0, 90,26,"⬇ SAVE",        callback=self._save)
        b['auto_str']   = B(0,0,120,22,"AUTO STRETCH",  callback=self._auto_stretch)
        b['proc_reset'] = B(0,0,110,22,"✕ RESET",       callback=self._reset)

        self._btn = b

    def _adj(self, attr, d, mx):
        setattr(self, attr, max(0, min(mx, getattr(self, attr) + d)))

    def _set_tab(self, t):
        self.tab = t
        if t == 2:
            self._proc_surf = None   # force reprocess

    def _nav(self, screen):
        self._next_screen = screen

    def _toggle_color(self):
        self.color = not self.color

    def _auto_stretch(self):
        arr = (self.stacked if self.stacked is not None
               else (self.cal[-1].data if self.cal
               else (self.lights[-1].data if self.lights else None)))
        if arr is not None:
            self.black = float(np.percentile(arr, 0.5))
            self.white = float(np.percentile(arr, 99.8))
            self._proc_surf = None
            # sync sliders
            if self._sl_black: self._sl_black.value = self.black
            if self._sl_white: self._sl_white.value = self.white

    # ── Target ────────────────────────────────────────────────────────────────
    def _target(self):
        s = self.state_manager.get_state()
        name = getattr(s, 'selected_target', None) or "No Target"
        ra   = float(getattr(s, 'selected_target_ra',  83.82) or 83.82)
        dec  = float(getattr(s, 'selected_target_dec', -5.39) or -5.39)
        return name, ra, dec

    def _log(self, msg: str):
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        if len(self.log) > 40: self.log.pop(0)

    # ── Sky signal ────────────────────────────────────────────────────────────
    def _sky_signal(self, exp_s):
        _, ra, dec = self._target()
        uni = self.state_manager.get_universe()
        if self.is_allsky and self.allsky_renderer:
            jd  = self._tc.jd
            # Realistic allsky f/1.2 lens, 0.5s: captures to ~mag 6.0
            # Stars mag 5-6 are dim single pixels; the fisheye blur in
            # _allsky_to_surface softens them naturally.
            mag = min(6.0, (self._atm_state.naked_eye_limit - 0.5)
                      if self._atm_state else 6.0)
            mag = max(4.0, mag)   # always show at least bright stars
            # Assicura che sole/luna abbiano posizione aggiornata
            if self._sun is not None:
                self._sun.update_position(jd, self._observer.latitude_deg,
                                          self._observer.longitude_deg)
            if self._moon is not None:
                self._moon.update_position(jd, self._observer.latitude_deg,
                                           self._observer.longitude_deg)
            rgb = self.allsky_renderer.render(
                jd, uni, exp_s, mag, self._atm_state,
                sun_body=self._sun, moon_body=self._moon,
                gain_sw=self.GAIN_STEPS[self.gain_idx])
            return rgb[:,:,0]*0.299 + rgb[:,:,1]*0.587 + rgb[:,:,2]*0.114, rgb

        mag_lim = min(10.0 + math.log10(max(1, exp_s)) * 1.5,
                      (self._atm_state.naked_eye_limit + 6.0)
                      if self._atm_state else 16.0)
        W, H = self.renderer.render_w, self.renderer.render_h
        if self.color:
            rf = np.zeros((H,W),np.float32); gf=rf.copy(); bf=rf.copy()
            self.renderer.render_rgb(rf,gf,bf,ra,dec,exp_s,uni,mag_lim,
                                     atm_state=self._atm_state)
            return rf*0.299+gf*0.587+bf*0.114, np.stack([rf,gf,bf],axis=-1)
        else:
            mono = self.renderer.render_field(ra,dec,exp_s,uni,mag_lim,
                                              atm_state=self._atm_state)
            return mono, None

    def _refresh_atm(self):
        now = self._tc.utc
        self._atm_state = self._atm_model.compute(now, self._sun, self._moon)
        if not self.is_allsky and self._atm_state:
            s = self._atm_state.seeing_fwhm_arcsec
            if abs(s - self.renderer.seeing_arcsec) > 0.1:
                self.renderer.seeing_arcsec = s
                self.renderer._psf_cache.clear()

    def _qe_allsky(self) -> float:
        """Return QE of current allsky camera (for stretch calibration)."""
        if self.allsky_renderer is not None:
            return self.allsky_renderer.spec.quantum_efficiency
        return 0.78

    def _live_sq_size(self) -> int:
        """Estimate the square viewer size for the current window."""
        # We don't have the window size here, so use a reasonable default.
        # The live view is called every 2s and render_size is updated dynamically
        # when the viewer rect is actually known (in _tab_live).
        return getattr(self, '_cached_sq_size', 560)

    def _allsky_to_surface(self, arr: np.ndarray, sq: int) -> 'pygame.Surface':
        """
        Luma-chroma preserving ADU tone mapping.

        Applica il log stretch SOLO alla luma, poi riscala RGB mantenendo il
        rapporto cromatico originale → i colori del tramonto/alba rimangono
        saturi (blu, arancione, giallo) invece di convergere a grigio.

        Fisicamente:
          BLACK = 1 ADU, WHITE = 65535 ADU, gamma = 0.42
          Gain scala il campo raw → stessa pipeline per qualsiasi gain
          Diurno:  luma >> 65535 → tutto satura → bianco-azzurro ✓
          Tramonto: cielo blu rimane blu, arancione rimane arancione ✓
          Notte:   sky_bg_B > R → steel-blue preservato ✓
        """
        import pygame
        from scipy.ndimage import gaussian_filter as _gf

        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)

        S = arr.shape[0]; cx_ = cy_ = S * 0.5; rad_ = S * 0.5 - 2
        yy_, xx_ = np.mgrid[0:S, 0:S]
        inside_ = ((xx_-cx_)**2 + (yy_-cy_)**2) < rad_**2

        # Luma-preserving log stretch
        # 1. Calcola luma fisica
        luma = (arr[:,:,0]*0.299 + arr[:,:,1]*0.587 + arr[:,:,2]*0.114
                ).astype(np.float64)
        luma = np.maximum(luma, 0.01)

        # 2. Stretch logaritmico sulla luma
        BLACK = 1.0; WHITE = 65535.0; GAMMA = 0.42
        _lr = math.log10(WHITE / BLACK)
        luma_m = (np.clip(np.log10(luma / BLACK) / _lr, 0.0, 2.0) ** GAMMA
                  ).astype(np.float32)

        # 3. Riscala ogni canale preservando crominanza (R/luma, G/luma, B/luma)
        out = np.zeros_like(arr, dtype=np.float32)
        for c in range(3):
            out[:,:,c] = np.clip(
                arr[:,:,c].astype(np.float64) / luma * luma_m, 0.0, 1.5
            ).astype(np.float32)
        # Clip a 1.0 (saturazione) ma permetti 1.5 prima del clip per evitare
        # artefatti nei canali dominanti quando uno satura

        # Normalizza: se qualche canale supera 1.0 (saturazione) scala giù
        # in modo da produrre bianco corretto (R=G=B=255) invece di clip asimmetrico
        peak = out.max(axis=2, keepdims=True)
        over = np.maximum(peak, 1.0)
        out = np.clip(out / over, 0.0, 1.0)

        # Layered blur (fisheye PSF softness)
        lum_post = out[:,:,0]*0.299 + out[:,:,1]*0.587 + out[:,:,2]*0.114
        bg_blur = np.zeros_like(out)
        for c in range(3): bg_blur[:,:,c] = _gf(out[:,:,c], sigma=1.8)
        bright_w = np.clip(lum_post * 2.0, 0.0, 1.0) ** 2
        out = bg_blur*(1-bright_w[:,:,np.newaxis]) + out*bright_w[:,:,np.newaxis]

        # Subtle grain
        lum2 = out[:,:,0]*0.299 + out[:,:,1]*0.587 + out[:,:,2]*0.114
        _rng = np.random.default_rng(seed=42)
        grain = _rng.standard_normal(lum2.shape).astype(np.float32) * 0.008
        for c in range(3): out[:,:,c] += grain * inside_

        u8 = (np.clip(out, 0.0, 1.0) * 255).astype(np.uint8)
        surf = pygame.surfarray.make_surface(u8.swapaxes(0, 1)).convert()
        if surf.get_width() != sq or surf.get_height() != sq:
            surf = pygame.transform.smoothscale(surf, (sq, sq))
        return surf

    def _darks(self):
        exp_s = self.EXP_STEPS[self.exp_idx]
        n     = self.DARK_STEPS[self.dark_idx]
        if n == 0: return
        rshape = ((self.allsky_renderer.render_size,)*2
                  if self.is_allsky and self.allsky_renderer
                  else (self.renderer.render_h, self.renderer.render_w))
        self._log(f"Darks: {n}×{exp_s}s …")
        self.darks = [self.camera.capture_dark_frame(exp_s, frame_seed=500+i,
                                                      render_shape=rshape)
                      for i in range(n)]
        self.status = f"✓ {n} darks"; self._log(f"  {n} darks done")

    def _flats(self):
        n = self.FLAT_STEPS[self.flat_idx]
        if n == 0: return
        if self.is_allsky and self.allsky_renderer:
            s=self.allsky_renderer.render_size; W=H=s
        else:
            W=self.renderer.render_w; H=self.renderer.render_h
        yy,xx = np.mgrid[0:H,0:W]; cx,cy=W/2,H/2
        r   = np.sqrt((xx-cx)**2+(yy-cy)**2)/(min(W,H)/2)
        sig = np.clip((1.0-0.35*r**2.5)*15000,3000,20000).astype(np.float32)
        self.flats = [
            self.camera.capture_frame(
                1.0, sig, FrameType.FLAT, frame_seed=200+i,
                metadata=FrameMetadata(frame_type=FrameType.FLAT,
                                       exposure_s=1.0, filter_name="L"))
            for i in range(n)]
        self.status = f"✓ {n} flats"; self._log(f"  {n} flats done")

    def _expose(self):
        """Acquisisci la sequenza di immagini lights."""
        exp_s = self.EXP_STEPS[self.exp_idx]
        n     = self.NL_STEPS[self.nl_idx]

        self._log(f"Light frames: {n}×{exp_s}s …")

        self.lights = []
        for i in range(n):
            # Genera il segnale sintetico del cielo
            mono, rgb = self._sky_signal(exp_s)

            # Crea il frame usando capture_frame (come in _flats e _darks)
            frame = self.camera.capture_frame(
                exp_s,
                mono if mono is not None else np.zeros((512, 512), dtype=np.float32),
                FrameType.LIGHT,
                frame_seed=1000 + i,
                metadata=FrameMetadata(
                    frame_type=FrameType.LIGHT,
                    exposure_s=exp_s,
                    filter_name="L"))
            self.lights.append(frame)

        self.status = f"✓ {n} lights"
        self._log(f"  {n} lights acquired")

    def _calibrate(self):
        if not self.lights: self._log("ERROR: no lights"); return
        self._log("Calibrating…")
        c = Calibrator()
        if self.darks:
            self.master_dark = c.create_master_dark(self.darks)
            self._log("  master dark OK")
        if self.flats:
            self.master_flat = c.create_master_flat(self.flats)
            self._log("  master flat OK")
        self.cal = c.batch_calibrate_lights(
            self.lights, master_dark=self.master_dark,
            master_flat=self.master_flat, apply_cosmetic=True)
        d = self.cal[-1].data
        self.black = float(np.percentile(d, 0.5))
        self.white = float(np.percentile(d, 99.8))
        if self._sl_black: self._sl_black.value = self.black
        if self._sl_white: self._sl_white.value = self.white
        self._proc_surf = None; self._proc_datagen += 1
        self.status = f"✓ Calibrated {len(self.cal)} frames"
        self._log(f"  {len(self.cal)} calibrated")

    def _stack(self):
        src = self.cal or self.lights
        if not src: self._log("ERROR: no frames"); return
        self._log(f"Stacking {len(src)} frames…")
        eng = StackingEngine()
        m   = self.STK_METHODS[self.stk_idx]
        self.stacked = eng.stack(src, m)
        if self.live_rgb is not None and self.live is not None:
            sc = self.stacked.mean() / max(self.live.mean(), 1e-6)
            self.stk_rgb = (self.live_rgb * sc).astype(np.float32)
        snr = eng.compute_snr_improvement(len(src), m)
        self.black = float(np.percentile(self.stacked, 0.2))
        self.white = float(np.percentile(self.stacked, 99.9))
        if self._sl_black: self._sl_black.value = self.black
        if self._sl_white: self._sl_white.value = self.white
        self._proc_surf = None; self._proc_datagen += 1
        self.status = f"✓ Stack SNR ×{snr:.1f} [{m.value}]"
        self._log(f"  stack done SNR +{snr:.1f}×")
        try:
            self.state_manager.get_career_mode().stats.research_points += 50
            self._log("  +50 RP!")
        except Exception: pass

    def _reset(self):
        for lst in (self.lights,self.darks,self.flats,self.cal): lst.clear()
        self.stacked=self.stk_rgb=self.live=self.live_rgb=None
        self.master_dark=self.master_flat=None
        self._proc_surf=None; self._proc_datagen+=1
        self.status="Session reset"; self._log("Session reset")

    def _save(self):
        """Save the current best image as PNG using the display pipeline."""
        # Priority: stacked → calibrated → raw light → live
        if   self.stacked is not None:                       arr, rgb_arr = self.stacked,       self.stk_rgb
        elif self.cal:                                       arr, rgb_arr = self.cal[-1].data,  None
        elif self.lights:                                    arr, rgb_arr = self.lights[-1].data, None
        elif self.live is not None:                          arr, rgb_arr = self.live,           self.live_rgb
        else:
            self._log("Nothing to save"); return

        try:
            # Use full render-buffer size for the saved image (no display scaling)
            S = self.allsky_renderer.render_size if self.is_allsky else None
            out_w = S if S else self.renderer.render_w * 4   # upscale 4× for saves
            out_h = S if S else self.renderer.render_h * 4

            # Temporarily set pipeline output size to save resolution
            old_dw, old_dh = self.pipeline.display_w, self.pipeline.display_h
            self.pipeline.display_w = out_w
            self.pipeline.display_h = out_h

            if self.color and rgb_arr is not None:
                surf = self.pipeline.process_rgb(rgb_arr, self.black, self.white)
            else:
                surf = self.pipeline.process(arr, self.black, self.white)

            # Restore display size
            self.pipeline.display_w = old_dw
            self.pipeline.display_h = old_dh

            # For allsky: upscale to a clean round resolution for the PNG
            if self.is_allsky:
                # Save at 1024×1024 for a nice round allsky PNG
                target = 1024
                surf = pygame.transform.smoothscale(surf, (target, target))

            fn = f"astro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            pygame.image.save(surf, fn)
            self._log(f"Saved: {fn}  ({surf.get_width()}×{surf.get_height()})")
            self.status = f"Saved {fn}"
        except Exception as e:
            self._log(f"Save error: {e}")
            import traceback; self._log(traceback.format_exc()[:120])

    # ── Live preview update ───────────────────────────────────────────────────
    def _update_live(self):
        try:
            self._refresh_atm()
            live_exp = 0.5 if self.is_allsky else 1.0
            # For allsky: render at the size that will be displayed (no upscale)
            # Estimate viewer square size: min(W - panel - 8, H - 36 - 114 - 4)
            # Default 560 covers 1280×720 and most window sizes
            if self.is_allsky and self.allsky_renderer:
                self.allsky_renderer.render_size = self._live_sq_size()
            mono, rgb = self._sky_signal(live_exp)
            self.live = mono; self.live_rgb = rgb
            if mono is not None:
                if self.is_allsky and rgb is not None:
                    # For allsky: use all three channels combined for robust stats
                    # G channel is luminance proxy; most pixels are pure sky background
                    ref = rgb[:,:,1]   # green channel
                else:
                    ref = mono

                if self.is_allsky and rgb is not None:
                    # Allsky stretch: calibrate white so sky background appears as
                    # dark indigo/blue (~25-35/255) and stars pop out clearly.
                    #
                    # Method: compute median sky level from inside-disk pixels,
                    # then solve for the white point that maps sky → target_brightness
                    # using the asinh stretch curve: f(x) = asinh(x/beta)/asinh(1/beta)
                    # with beta=0.03 (hardcoded in display_pipeline).
                    #
                    # sky_target/255 = asinh(sky/white / beta) / asinh(1/beta)
                    # → white = sky / (sinh(sky_target * asinh(1/beta)/255) * beta)
                    import math as _math
                    _beta  = 0.03
                    _asnh1 = _math.asinh(1.0 / _beta)  # ≈ 4.199
                    _sky_target = 28   # /255 — deep dark sky, slightly visible

                    # Median of green channel inside disk (most pixels are sky)
                    _ref = rgb[:,:,1]
                    _S = _ref.shape[0]; _cx = _cy = _S / 2.0; _rad = _S/2.0 - 2
                    _yy, _xx = np.mgrid[0:_S, 0:_S]
                    _inside = ((_xx-_cx)**2 + (_yy-_cy)**2) < _rad**2
                    _sky_med = float(np.median(_ref[_inside]))

                    if _sky_med > 0:
                        _t = _math.sinh(_sky_target * _asnh1 / 255.0) * _beta
                        _white = _sky_med / max(_t, 1e-9)
                        # Clamp: must not be so low stars clip, not so high sky goes black
                        self.black = 0.0
                        self.white = float(np.clip(_white, 20.0, 500.0))
                    else:
                        self.black = 0.0
                        self.white = 100.0
                else:
                    self.black = float(np.percentile(ref, 0.5))
                    self.white = float(np.percentile(ref, 99.5))
        except Exception: pass

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def on_enter(self):
        super().on_enter()
        self._reload_if_changed()
        self._next_screen = None
        if self._tc.speed_idx <= 1: self._tc.realtime()
        self._live_timer = 0.0
        self._update_live()
        name, ra, dec = self._target()
        self._log(f"Enter — target: {name} ({ra:.1f}°, {dec:+.1f}°)")

    def on_exit(self):
        super().on_exit()

    def update(self, dt: float):
        self._tc.step(dt)
        self._live_timer += dt
        if self._live_timer >= self._live_interval:
            self._live_timer = 0.0
            if self.tab == 0:
                self._update_live()

    # ── Input ─────────────────────────────────────────────────────────────────
    def handle_input(self, events) -> Optional[str]:
        if getattr(self,'_next_screen',None):
            ns=self._next_screen; self._next_screen=None; return ns

        mp = pygame.mouse.get_pos()
        for btn in self._btn.values(): btn.update(mp)

        for ev in events:
            # Sliders (Tab 2 only)
            if self.tab == 2:
                for sl in (self._sl_black, self._sl_white, self._sl_gamma):
                    if sl and sl.handle(ev):
                        self.black  = self._sl_black.value  if self._sl_black else self.black
                        self.white  = self._sl_white.value  if self._sl_white else self.white
                        self.gamma  = self._sl_gamma.value  if self._sl_gamma else self.gamma
                        self._proc_surf = None
            # Tab click strip
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i, r in enumerate(self._tab_rects):
                    if r.collidepoint(ev.pos): self._set_tab(i)
            # Buttons
            for btn in self._btn.values(): btn.handle_event(ev)
            # ESC
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return "OBSERVATORY"
        return None

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self, surface: pygame.Surface):
        W, H = surface.get_size()
        surface.fill((4, 7, 10))
        self._draw_header(surface, W, H)
        self._draw_tabbar(surface, W)
        TOP = 114
        if   self.tab == 0: self._tab_live(surface, W, H, TOP)
        elif self.tab == 1: self._tab_capture(surface, W, H, TOP)
        else:               self._tab_process(surface, W, H, TOP)
        self._draw_footer(surface, W, H)

    # ── Header (always visible) ───────────────────────────────────────────────
    def _draw_header(self, surface, W, H):
        pygame.draw.rect(surface, (0,15,8), (0,0,W,80))
        pygame.draw.line(surface, _LN, (0,80),(W,80),1)

        # Title + target
        surface.blit(_f(15,bold=True).render("◆ IMAGING SYSTEM", True, _C),(8,5))
        name,ra,dec = self._target()
        _txt(surface,180,7, f"TARGET: {name}   RA {ra:.2f}°  Dec {dec:+.2f}°", _C, 11)

        # Camera / FOV
        info = self.renderer.get_info()
        cam_s = (f"Cam: {self.camera.spec.name}  |  "
                 + ("AllSky 180°" if self.is_allsky
                    else f"FOV {info['fov_deg'][0]:.2f}°×{info['fov_deg'][1]:.2f}°  "
                         f"{info['pixel_scale_arcsec']:.2f}\"/px")
                 + f"  |  Gain {self.GAIN_STEPS[self.gain_idx]}")
        _txt(surface,8,24,cam_s,(0,150,80),10)

        # Time
        tc_c = (0,160,200) if not self._tc.paused else (180,180,60)
        _txt(surface,8,38,
             f"SIM {self._tc.utc.strftime('%Y-%m-%d  %H:%M:%S UTC')}  [{self._tc.speed_label}]",
             tc_c, 10)

        # Atmosphere line
        if self._atm_state:
            from atmosphere import get_phase_properties
            a=self._atm_state; pp=get_phase_properties(a.day_phase)
            ph=a.day_phase.value.replace('_',' ').title()
            _txt(surface,8,52,
                 f"ATM: {ph}  Sol {a.solar_alt_deg:+.0f}°  See {a.seeing_fwhm_arcsec:.1f}\"  "
                 f"Bg {a.sky_bg_g:.0f}ph", pp.ui_color, 10)

        # Sensor temp top-right
        _txt(surface, W-200, 6, f"Sensor  {self.camera.temperature_c:.0f}°C", (0,200,180), 10)

        # Status
        st=_f(11).render(f"● {self.status}",True,_C)
        surface.blit(st,(W-st.get_width()-8,22))

        # RP
        try:
            rp=self.state_manager.get_career_mode().stats.research_points
            rt=_f(10).render(f"RP: {rp}",True,_Y); surface.blit(rt,(W-rt.get_width()-8,38))
        except Exception: pass

        # Back button
        self._btn['back'].rect = pygame.Rect(W-88,56,80,18)
        self._btn['back'].draw(surface)

    # ── Tab bar ───────────────────────────────────────────────────────────────
    def _draw_tabbar(self, surface, W):
        labels = ["◉ LIVE VIEW", "⊕ CAPTURE", "⊞ PROCESS"]
        tw = 130; gap = 4
        self._tab_rects = []
        for i, lbl in enumerate(labels):
            x = 4 + i*(tw+gap)
            r = pygame.Rect(x, 82, tw, 26)
            self._tab_rects.append(r)
            active = (self.tab == i)
            pygame.draw.rect(surface, (0,55,28) if active else (0,18,9), r)
            pygame.draw.rect(surface, (_C if active else _LN), r, 1)
            t=_f(11,bold=active).render(lbl, True, _C if active else _D)
            surface.blit(t,(r.x+(tw-t.get_width())//2, r.y+5))

    # ── TAB 0 — LIVE ──────────────────────────────────────────────────────────
    def _tab_live(self, surface, W, H, TOP):
        FOOT = H-36; LP = min(270, W//4)

        # Left panel
        pygame.draw.rect(surface, _BG, (0,TOP,LP,FOOT-TOP))
        pygame.draw.line(surface, _LN,(LP,TOP),(LP,FOOT),1)

        y = TOP+6
        y = _sec(surface,6,y,"POINTING")
        name,ra,dec = self._target()
        y = _txt(surface,6,y,f"Target  {name}",_C,10)
        if self._atm_state:
            try:
                from universe.orbital_body import equatorial_to_altaz
                alt,az = equatorial_to_altaz(ra,dec,
                    self._observer.latitude_deg,
                    self._observer.longitude_deg, self._tc.jd)
                y=_txt(surface,6,y,f"Alt {alt:+.1f}°   Az {az:.1f}°",_C,10)
            except Exception: pass

        y+=4; y=_sec(surface,6,y,"SENSOR & ENVIRONMENT")
        y=_txt(surface,6,y,f"Sensor temp   {self.camera.temperature_c:.0f} °C",(0,200,180),10)
        # External temperature proxy (rough)
        if self._atm_state:
            ext_t = -5.0 + self._atm_state.solar_alt_deg*0.25
            y=_txt(surface,6,y,f"External      {ext_t:.1f} °C",(0,180,160),10)
            see=self._atm_state.seeing_fwhm_arcsec
            y=_txt(surface,6,y,f"Seeing        {see:.1f}\"",_C,10)

        y+=4; y=_sec(surface,6,y,"SENSOR GAIN")
        gv=self.GAIN_STEPS[self.gain_idx]
        y=_txt(surface,6,y,f"Gain  {gv}",_C,10)
        gx=6
        self._btn['gain_dn'].rect=pygame.Rect(gx,  y, 32,22)
        self._btn['gain_up'].rect=pygame.Rect(gx+36,y, 32,22)
        self._btn['gain_dn'].draw(surface)
        self._btn['gain_up'].draw(surface)
        y+=28

        y+=4; y=_sec(surface,6,y,"TIME CONTROL")
        tc_c=(0,160,200) if not self._tc.paused else (180,180,60)
        y=_txt(surface,6,y,
               f"{self._tc.utc.strftime('%H:%M:%S')}  {self._tc.speed_label}",tc_c,10)
        # Time buttons 2 rows
        row=[('tc_pause',0),('tc_rt',74),('tc_rev',138),('tc_slow',180),('tc_fast',222)]
        for k,ox in row:
            self._btn[k].rect=pygame.Rect(6+ox, y, *self._btn[k].rect.size)
        for k,_ in row: self._btn[k].draw(surface)
        y+=28

        y+=4; y=_sec(surface,6,y,"SESSION")
        for lbl,cnt,col in [("Lights",len(self.lights),_C),
                             ("Darks",len(self.darks),(0,160,80)),
                             ("Flats",len(self.flats),(0,160,80)),
                             ("Cal",len(self.cal),_C),
                             ("Stacked",1 if self.stacked is not None else 0,_Y)]:
            bw=min(LP-90,cnt*6)
            pygame.draw.rect(surface,(0,18,9),(6,y,LP-90,11))
            if bw: pygame.draw.rect(surface,col,(6,y,bw,11))
            _txt(surface,LP-80,y,f"{lbl}: {cnt}",col,9); y+=14

        # Bottom of left panel: SAVE (top) + CAPTURE (bottom)
        self._btn['save'].rect=pygame.Rect(6,FOOT-68,LP-12,24)
        self._btn['save'].draw(surface)
        self._btn['to_capture'].rect=pygame.Rect(6,FOOT-38,LP-12,28)
        self._btn['to_capture'].draw(surface)

        # ── Live viewer ────────────────────────────────────────────────
        vx=LP+4; vw=W-LP-8; vh=FOOT-TOP-4
        # Fill the background area
        pygame.draw.rect(surface,(0,0,0),(vx,TOP+2,vw,vh))

        img=self.live; rgb=self.live_rgb
        if img is not None:
            if self.is_allsky:
                # Allsky: SQUARE viewer, centred in available space.
                # Cache sq size so next live update renders at correct resolution.
                sq = min(vw, vh)
                self._cached_sq_size = sq
                if self.allsky_renderer: self.allsky_renderer.render_size = sq
                ox = vx + (vw - sq) // 2
                oy = TOP+2 + (vh - sq) // 2
                s = self._allsky_to_surface(rgb if (self.color and rgb is not None) else img, sq)
                surface.blit(s, (ox, oy))
                surface.blit(_f(10,bold=True).render("◉ LIVE",True,(0,255,80)),(ox+5,oy+5))
                stats=(f"{img.shape[1]}×{img.shape[0]}  "
                       f"Min:{np.min(img):.0f}  Max:{np.max(img):.0f}  Mean:{np.mean(img):.0f}")
                surface.blit(_f(10).render(stats,True,_D),(ox+4,oy+sq-13))
            else:
                vr=pygame.Rect(vx,TOP+2,vw,vh)
                self.pipeline.display_w=vr.w; self.pipeline.display_h=vr.h
                s=(self.pipeline.process_rgb(rgb,self.black,self.white)
                   if (self.color and rgb is not None)
                   else self.pipeline.process(img,self.black,self.white))
                surface.blit(s,vr.topleft)
                surface.blit(_f(10,bold=True).render("◉ LIVE",True,(0,255,80)),(vx+5,TOP+5))
                stats=(f"{img.shape[1]}×{img.shape[0]}  "
                       f"Min:{np.min(img):.0f}  Max:{np.max(img):.0f}  Mean:{np.mean(img):.0f}")
                surface.blit(_f(10).render(stats,True,_D),(vx+4,TOP+2+vh-13))
        else:
            cx,cy=vx+vw//2, TOP+2+vh//2
            surface.blit(_f(13).render("Acquiring first live frame…",True,_D),(cx-130,cy-7))

    # ── TAB 1 — CAPTURE ───────────────────────────────────────────────────────
    def _tab_capture(self, surface, W, H, TOP):
        FOOT=H-36; PW=min(360,W//3)
        pygame.draw.rect(surface,_BG,(0,TOP,PW,FOOT-TOP))
        pygame.draw.line(surface,_LN,(PW,TOP),(PW,FOOT),1)

        y=TOP+8

        y=_sec(surface,8,y,"EXPOSURE")
        y=self._param_row(surface,8,y,"Exposure",
                          f"{self.EXP_STEPS[self.exp_idx]} s",'exp_dn','exp_up')
        y=self._param_row(surface,8,y,"Light frames",
                          str(self.NL_STEPS[self.nl_idx]),'nl_dn','nl_up')
        y=self._param_row(surface,8,y,"Gain",
                          str(self.GAIN_STEPS[self.gain_idx]),'cap_gain_dn','cap_gain_up')
        # Color mode toggle
        self._btn['color_tog'].text=f"Mode: {'RGB' if self.color else 'MONO'}"
        self._btn['color_tog'].rect=pygame.Rect(8,y,110,22); self._btn['color_tog'].draw(surface)
        y+=28

        y+=4; y=_sec(surface,8,y,"CALIBRATION FRAMES")
        y=self._param_row(surface,8,y,"Darks",
                          str(self.DARK_STEPS[self.dark_idx]),'dark_dn','dark_up')
        y=self._param_row(surface,8,y,"Flats",
                          str(self.FLAT_STEPS[self.flat_idx]),'flat_dn','flat_up')
        _txt(surface,8,y,"(0 = skip)",_D,9); y+=12

        y+=4; y=_sec(surface,8,y,"STACKING METHOD")
        for i,lbl in enumerate(self.STK_LABELS):
            active=(i==self.stk_idx)
            _txt(surface,8,y,("▶ " if active else "  ")+lbl,_C if active else _D,10); y+=14
        self._btn['stk_dn'].rect=pygame.Rect(8,   y,32,20)
        self._btn['stk_up'].rect=pygame.Rect(8+36,y,32,20)
        self._btn['stk_dn'].draw(surface); self._btn['stk_up'].draw(surface); y+=28

        y+=4; y=_sec(surface,8,y,"SESSION")
        for lbl,cnt,col in [("Lights",len(self.lights),_C),
                             ("Darks",len(self.darks),(0,160,80)),
                             ("Flats",len(self.flats),(0,160,80))]:
            _txt(surface,8,y,f"{lbl}: {cnt}",col,10); y+=13

        # Action buttons at bottom
        by=FOOT-110
        self._btn['acquire'].rect=pygame.Rect(8,by,PW-16,30); self._btn['acquire'].draw(surface); by+=36
        hw=(PW-20)//2
        self._btn['cap_darks'].rect=pygame.Rect(8,   by,hw,24)
        self._btn['cap_flats'].rect=pygame.Rect(8+hw+4,by,hw,24)
        self._btn['cap_darks'].draw(surface); self._btn['cap_flats'].draw(surface); by+=30
        self._btn['reset'].rect=pygame.Rect(8,by,PW-16,22); self._btn['reset'].draw(surface)

        # Right: atmosphere + log
        rx=PW+10; ry=TOP+8
        if self._atm_state:
            from atmosphere import get_phase_properties
            a=self._atm_state; pp=get_phase_properties(a.day_phase)
            ph=a.day_phase.value.replace('_',' ').title()
            ry=_sec(surface,rx,ry,"ATMOSPHERE")
            ry=_txt(surface,rx,ry,f"Phase:    {ph}",pp.ui_color,10)
            ry=_txt(surface,rx,ry,f"Solar:    {a.solar_alt_deg:+.0f}°",_C,10)
            ry=_txt(surface,rx,ry,
                    f"Moon:     {a.moon_alt_deg:+.0f}°  {a.moon_phase_fraction:.0%}",_C,10)
            img_ok=_C if a.imaging_allowed else (220,90,0)
            ry=_txt(surface,rx,ry,
                    f"Imaging:  {'OK' if a.imaging_allowed else 'BLOCKED'}  "
                    f"See {a.seeing_fwhm_arcsec:.1f}\"",img_ok,10)
            ry+=6

        ry=_sec(surface,rx,ry,"LOG")
        ml=(FOOT-ry-8)//12
        for line in self.log[-ml:]:
            if ry>FOOT-12: break
            _txt(surface,rx,ry,line[:60],_D,10); ry+=12

    def _param_row(self, surf, x, y, label, value, btn_dn, btn_up):
        _txt(surf,x,y,f"{label}:",_D,10)
        _txt(surf,x+120,y,value,_C,11)
        self._btn[btn_dn].rect=pygame.Rect(x+185,y-1,32,20)
        self._btn[btn_up].rect=pygame.Rect(x+221,y-1,32,20)
        self._btn[btn_dn].draw(surf); self._btn[btn_up].draw(surf)
        return y+26

    # ── TAB 2 — PROCESS ───────────────────────────────────────────────────────
    def _tab_process(self, surface, W, H, TOP):
        FOOT=H-36; CP=min(290,W//4)
        pygame.draw.rect(surface,_BG,(0,TOP,CP,FOOT-TOP))
        pygame.draw.line(surface,_LN,(CP,TOP),(CP,FOOT),1)

        y=TOP+8
        # Source indicator
        if   self.stacked  is not None: src_lbl="Stacked"; src=self.stacked
        elif self.cal:                  src_lbl="Calibrated"; src=self.cal[-1].data
        elif self.lights:               src_lbl="Raw light"; src=self.lights[-1].data
        else:                           src_lbl="None"; src=None

        y=_sec(surface,8,y,"IMAGE SOURCE")
        y=_txt(surface,8,y,src_lbl,_C,11)
        if src is not None:
            y=_txt(surface,8,y,f"{src.shape[1]}×{src.shape[0]}  "
                   f"Min {np.min(src):.0f}  Max {np.max(src):.0f}",_D,10)
            y=_txt(surface,8,y,f"Mean {np.mean(src):.0f}",_D,10)
        y+=4

        # ── Sliders ──────────────────────────────────────────────────────
        max_v = float(np.max(src)) if src is not None else 65535.0
        sw = CP-16

        y=_sec(surface,8,y,"HISTOGRAM STRETCH")

        # Black slider
        if self._sl_black is None:
            self._sl_black=_Slider(8,y,sw,14,0,max_v,self.black,"Black",(80,80,220))
        self._sl_black.set_rect(8,y,sw,14); self._sl_black.hi=max_v
        self._sl_black.draw(surface); y+=30

        # White slider
        if self._sl_white is None:
            self._sl_white=_Slider(8,y,sw,14,0,max_v,self.white,"White",(220,220,80))
        self._sl_white.set_rect(8,y,sw,14); self._sl_white.hi=max_v
        self._sl_white.draw(surface); y+=30

        # Gamma slider
        if self._sl_gamma is None:
            self._sl_gamma=_Slider(8,y,sw,14,0.5,4.0,self.gamma,"Gamma",_C)
        self._sl_gamma.set_rect(8,y,sw,14)
        self._sl_gamma.draw(surface); y+=30

        # Sync slider → self (sliders are source of truth in this tab)
        self.black = self._sl_black.value
        self.white = self._sl_white.value
        self.gamma = self._sl_gamma.value

        self._btn['auto_str'].rect=pygame.Rect(8,y,120,22); self._btn['auto_str'].draw(surface); y+=28

        # ── Stack method ──────────────────────────────────────────────────
        y+=4; y=_sec(surface,8,y,"STACK METHOD")
        for i,lbl in enumerate(self.STK_LABELS):
            active=(i==self.stk_idx)
            _txt(surface,8,y,("▶ " if active else "  ")+lbl,_C if active else _D,10); y+=14
        self._btn['stk_dn'].rect=pygame.Rect(8,   y,32,20)
        self._btn['stk_up'].rect=pygame.Rect(8+36,y,32,20)
        self._btn['stk_dn'].draw(surface); self._btn['stk_up'].draw(surface); y+=28

        # ── Frame counts ──────────────────────────────────────────────────
        y+=4; y=_sec(surface,8,y,"FRAMES")
        for lbl,cnt,col in [("Lights",len(self.lights),_C),
                             ("Darks",len(self.darks),(0,160,80)),
                             ("Flats",len(self.flats),(0,160,80)),
                             ("Cal",len(self.cal),_C),
                             ("Stacked",1 if self.stacked is not None else 0,_Y)]:
            _txt(surface,8,y,f"{lbl}: {cnt}",col,10); y+=13

        # ── Log strip ─────────────────────────────────────────────────────
        y+=4; y=_sec(surface,8,y,"LOG")
        ml_log=(FOOT-y-90)//11
        for line in self.log[-max(1,ml_log):]:
            if y>FOOT-90: break
            _txt(surface,8,y,line[:38],_D,9); y+=11

        # ── Action buttons at bottom ──────────────────────────────────────
        by=FOOT-64
        self._btn['calibrate'].rect=pygame.Rect(4,  by,140,26)
        self._btn['stack'].rect    =pygame.Rect(148,by,140,26)
        self._btn['save'].rect     =pygame.Rect(292,by,90,26)
        for k in ('calibrate','stack','save'): self._btn[k].draw(surface)
        by+=32
        self._btn['proc_reset'].rect=pygame.Rect(4,by,110,22); self._btn['proc_reset'].draw(surface)

        # ── Right: FIXED image + histogram ────────────────────────────────
        vx=CP+4; vw=W-CP-8
        HIST_H=80
        img_h=FOOT-TOP-HIST_H-18
        ir=pygame.Rect(vx,TOP+2,vw,img_h)
        hr=pygame.Rect(vx,ir.bottom+4,vw,HIST_H)

        pygame.draw.rect(surface,(0,0,0),ir)

        if src is not None:
            self.pipeline.display_w=ir.w; self.pipeline.display_h=ir.h
            rgb_src=(self.stk_rgb if (self.stacked is not None and self.stk_rgb is not None)
                     else None)
            ck=(round(self.black,0),round(self.white,0),round(self.gamma,2),
                ir.w,ir.h,self._proc_datagen,id(src)&0xFFFF)

            if self._proc_surf is None or self._proc_ck!=ck:
                self._proc_surf=(self.pipeline.process_rgb(rgb_src,self.black,self.white)
                                 if (self.color and rgb_src is not None)
                                 else self.pipeline.process(src,self.black,self.white))
                self._proc_ck=ck

            surface.blit(self._proc_surf,ir.topleft)

            # Source badge (top-left of image)
            surface.blit(_f(10,bold=True).render(f"◼ {src_lbl.upper()}",True,_Y),(vx+5,TOP+5))
            # Resolution
            surface.blit(_f(9).render(f"{src.shape[1]}×{src.shape[0]}",True,_D),(vx+5,TOP+18))

            # Histogram
            if self.color and rgb_src is not None:
                for ch,col in enumerate([(160,50,50),(50,160,50),(50,60,200)]):
                    _hist(surface,hr,rgb_src[:,:,ch],self.black,self.white,col)
            else:
                _hist(surface,hr,src,self.black,self.white)
            # Histogram axis labels
            surface.blit(_f(9).render(
                f"Black {self.black:.0f}   White {self.white:.0f}   γ {self.gamma:.1f}   "
                "← drag sliders to stretch",True,_D),(vx+4,hr.bottom+2))
        else:
            cx,cy=ir.centerx,ir.centery
            for i,(ln,col) in enumerate([
                ("No image to process yet",(0,100,50)),
                ("",(0,0,0)),
                ("→ Go to CAPTURE tab and acquire lights",(0,80,40)),
                ("→ Come back here to calibrate + stack",(0,80,40))]):
                if col!=(0,0,0):
                    t=_f(12).render(ln,True,col)
                    surface.blit(t,(cx-t.get_width()//2,cy-30+i*22))

    # ── Footer ────────────────────────────────────────────────────────────────
    def _draw_footer(self, surface, W, H):
        pygame.draw.rect(surface,(0,10,5),(0,H-32,W,32))
        pygame.draw.line(surface,_LN,(0,H-32),(W,H-32),1)
        _txt(surface,8,H-22,
             "Click tabs to switch view   ESC → back to observatory",_D,10)
