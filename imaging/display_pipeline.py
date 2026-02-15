"""
Display Pipeline — Scientific Retro Rendering
Photon array (small buffer) -> optical effects -> upscale -> pygame Surface
"""
from __future__ import annotations
import math, numpy as np
from typing import Optional, Tuple


def _asinh_stretch(data, scale, beta_frac=0.03):
    """
    Asinh stretch — compresses high values while preserving faint detail.
    beta_frac controls the "softening": smaller = stronger stretch of faint data.
    """
    beta = max(scale * beta_frac, 1e-9)
    return np.arcsinh(np.clip(data, 0, None) / beta) / np.arcsinh(scale / beta)

def tone_map(field, black=None, white=None, stretch="asinh"):
    """
    Map photon array to [0,1].

    black/white: if None, auto-detected from percentiles.
    black defaults to 20th percentile (removes most sky gradient).
    white defaults to 99.5th percentile (clips only absolute brightest stars).
    """
    data = field.astype(np.float32)

    # Auto black: use background median to set the sky to ~0.05
    if black is None:
        black = float(np.percentile(data, 20.0))
    # Auto white: set to leave dynamic range for stars
    if white is None:
        white = float(np.percentile(data, 99.5))

    data = data - black
    scale = max(white - black, 1.0)

    if   stretch == "asinh": data = _asinh_stretch(data, scale)
    elif stretch == "log":   data = np.log1p(np.clip(data,0,None)) / math.log1p(scale)
    elif stretch == "gamma": data = np.power(np.clip(data/scale,0,1), 1/2.2)
    else:                    data = data / scale

    return np.clip(data, 0.0, 1.0).astype(np.float32)

def cinematic_curve(img):
    toe = 0.04
    lifted = img*(1-toe) + toe*(1-img)*img
    s = np.where(lifted < 0.96,
                 lifted,
                 0.96 + 0.04 * np.tanh((lifted-0.96) / 0.04))
    return np.clip(s, 0.0, 1.0).astype(np.float32)

def normalize_rgb(rgb, black, white, stretch="asinh"):
    out = np.empty_like(rgb, dtype=np.float32)
    for c in range(3):
        out[:,:,c] = tone_map(rgb[:,:,c], black, white, stretch)
    return out

def mono_to_rgb(mono, r=1.0, g=1.0, b=1.0):
    return np.clip(np.stack([mono*r, mono*g, mono*b], axis=-1), 0, 1).astype(np.float32)


def add_bloom(img, threshold=0.72, strength=0.35, radius=3):
    from scipy.ndimage import uniform_filter
    is_rgb = img.ndim == 3
    lum = (img[:,:,0]*0.299+img[:,:,1]*0.587+img[:,:,2]*0.114) if is_rgb else img
    mask = np.clip(lum - threshold, 0, None) / (1-threshold+1e-9)
    sz = radius*2+1
    if is_rgb:
        glow = np.stack([uniform_filter(img[:,:,c]*mask, size=sz, mode="reflect")
                         for c in range(3)], axis=-1)
    else:
        glow = uniform_filter(img*mask, size=sz, mode="reflect")
    return np.clip(img + glow*strength, 0, 1).astype(np.float32)


def _cross_kernel(half_len):
    size = half_len*2+1; k = np.zeros((size,size), np.float32)
    p = np.exp(-np.abs(np.arange(size)-half_len)*0.6)
    k[half_len,:] = p; k[:,half_len] = p; k[half_len,half_len] = 1.0
    return k / k.sum()

def _diag_kernel(half_len):
    size = half_len*2+1; k = np.zeros((size,size), np.float32)
    for i in range(size):
        v = math.exp(-abs(i-half_len)*0.8)
        k[i,i] = v; k[i,size-1-i] = v
    k[half_len,half_len] = 1.0
    return k/k.sum()

def add_spikes(img, threshold=0.82, spike_len=6, strength=0.45, style="cross"):
    from scipy.ndimage import convolve
    is_rgb = img.ndim == 3
    lum = (img[:,:,0]*0.299+img[:,:,1]*0.587+img[:,:,2]*0.114) if is_rgb else img
    bright = np.clip(lum-threshold, 0, None) / (1-threshold+1e-9)
    kernel = _cross_kernel(spike_len) if style=="cross" else _diag_kernel(spike_len)
    if is_rgb:
        spikes = np.stack([convolve(img[:,:,c]*bright, kernel, mode="reflect")
                           for c in range(3)], axis=-1)
    else:
        spikes = convolve(img*bright, kernel, mode="reflect")
    return np.clip(img + spikes*strength, 0, 1).astype(np.float32)


class VignetteMap:
    def __init__(self, W, H, strength=0.45, power=3.0):
        self._strength = strength
        self._power    = power
        self._W = W; self._H = H
        self.mask = self._build(W, H)

    def _build(self, W, H):
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx-W/2)/(max(W,1)/2))**2 + ((yy-H/2)/(max(H,1)/2))**2)
        return (1.0 - self._strength * np.clip(r,0,1)**self._power).astype(np.float32)

    def apply(self, img):
        H, W = img.shape[:2]
        # Rebuild mask if image size differs from the cached mask
        if W != self._W or H != self._H:
            self.mask = self._build(W, H)
            self._W = W; self._H = H
        m = self.mask[:,:,np.newaxis] if img.ndim==3 else self.mask
        return np.clip(img*m, 0, 1).astype(np.float32)


def add_chrom(img, shift_px=0.8):
    if img.ndim != 3: return img
    from scipy.ndimage import map_coordinates
    H, W = img.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W/2.0, H/2.0
    r_max = math.sqrt(cx**2+cy**2)
    r = np.sqrt((xx-cx)**2+(yy-cy)**2)
    s = (r/r_max)*shift_px
    dx = s*(xx-cx)/(r_max+1e-9); dy = s*(yy-cy)/(r_max+1e-9)
    def sh(c,ddx,ddy):
        return map_coordinates(img[:,:,c],[yy+ddy,xx+ddx],order=1,mode="reflect").astype(np.float32)
    return np.clip(np.stack([sh(0,dx,dy), img[:,:,1].copy(), sh(2,-dx,-dy)],axis=-1),0,1).astype(np.float32)


def add_grain(img, strength=0.018, dark_boost=2.0, seed=0):
    rng = np.random.default_rng(seed % (2**31))
    noise = rng.standard_normal(img.shape).astype(np.float32)*strength
    lum = (img[:,:,0]*0.299+img[:,:,1]*0.587+img[:,:,2]*0.114) if img.ndim==3 else img
    mask = (1.0 + dark_boost*(1.0-lum))
    if img.ndim==3: mask = mask[:,:,np.newaxis]
    return np.clip(img+noise*mask, 0, 1).astype(np.float32)


def color_grade(img, warmth=0.0, teal_shadows=0.3, saturation=1.15, contrast=1.05):
    if img.ndim != 3: return img
    out = np.clip((img-0.5)*contrast+0.5, 0, 1)
    lum = out[:,:,0]*0.299+out[:,:,1]*0.587+out[:,:,2]*0.114
    l3 = lum[:,:,np.newaxis]
    out = np.clip(l3+(out-l3)*saturation, 0, 1).astype(np.float32)
    if warmth:
        out[:,:,0] = np.clip(out[:,:,0]+warmth*0.08, 0, 1)
        out[:,:,2] = np.clip(out[:,:,2]-warmth*0.06, 0, 1)
    if teal_shadows:
        sh = (1.0-lum)**2
        out[:,:,1] = np.clip(out[:,:,1]+teal_shadows*0.05*sh, 0, 1)
        out[:,:,2] = np.clip(out[:,:,2]+teal_shadows*0.07*sh, 0, 1)
    return out.astype(np.float32)


def to_surface(img, tw, th, smooth: bool = False):
    """Convert float32 [0,1] array to pygame Surface, upscaled to (tw,th).

    smooth=True  → bilinear (smoothscale): best for allsky / circular renders
    smooth=False → nearest-neighbour (scale): HD2D pixel-art look for telescope
    """
    import pygame
    u8 = (np.clip(img,0,1)*255).astype(np.uint8)
    if u8.ndim == 2: u8 = np.stack([u8,u8,u8], axis=-1)
    surf = pygame.surfarray.make_surface(u8.swapaxes(0,1)).convert()
    if smooth:
        return pygame.transform.smoothscale(surf, (tw, th))
    return pygame.transform.scale(surf, (tw, th))


class DisplayPipeline:
    """
    photon array (small render buffer) -> effects -> nearest-neighbour upscale -> Surface

    API:
        pipe.process(mono, black, white)          -> Surface
        pipe.process_rgb(rgb_HW3, black, white)   -> Surface
        pipe.process_rgb(r, g, b, black, white)   -> Surface  (legacy)
    """

    def __init__(self,
                 render_w=480, render_h=270,
                 display_w=960, display_h=540,
                 telescope_type="refractor",
                 bloom_on=True,  spikes_on=True,
                 chrom_on=True,  grain_on=True,
                 bloom_strength=0.35, spike_strength=0.45, spike_len=6,
                 chrom_shift=0.8, grain_strength=0.018,
                 vignette_strength=0.40,
                 warmth=0.0, teal_shadows=0.3, saturation=1.15,
                 stretch="asinh",
                 # legacy kwarg names
                 spikes=None, bloom=None, chroma=None,
                 spike_length=None, bloom_radius=None, chroma_shift=None,
                 vignette=None, colour_grade=None, gamma=None):

        self.render_w  = render_w
        self.render_h  = render_h
        self.display_w = display_w
        self.display_h = display_h

        self.bloom_on       = bloom_on  if bloom  is None else bloom
        self.spikes_on      = spikes_on if spikes is None else spikes
        self.chrom_on       = chrom_on  if chroma is None else chroma
        self.grain_on       = grain_on
        self.bloom_strength = bloom_strength
        self.spike_strength = spike_strength
        self.spike_len      = spike_length if spike_length is not None else spike_len
        self.chrom_shift    = chroma_shift if chroma_shift is not None else chrom_shift
        self.grain_strength = grain_strength
        self.warmth         = warmth
        self.teal_shadows   = teal_shadows
        self.saturation     = saturation
        self.stretch        = stretch

        self._spike_style = "cross" if telescope_type == "refractor" else "diagonal"
        self._vignette    = VignetteMap(render_w, render_h, vignette_strength)
        self._grain_seed  = 0

    def _fx(self, img, advance_grain: bool = True):
        """Apply visual effects pipeline.
        advance_grain=True (default): increment grain seed after use,
        so each NEW image gets different grain.
        advance_grain=False: reuse same seed (frozen frame — cached display).
        """
        if self.bloom_on:  img = add_bloom(img, strength=self.bloom_strength)
        if self.spikes_on: img = add_spikes(img, spike_len=self.spike_len,
                                             strength=self.spike_strength,
                                             style=self._spike_style)
        img = self._vignette.apply(img)
        if self.chrom_on and img.ndim==3:
            img = add_chrom(img, shift_px=self.chrom_shift)
        if self.grain_on:
            img = add_grain(img, strength=self.grain_strength, seed=self._grain_seed)
            if advance_grain:
                self._grain_seed = (self._grain_seed + 1) % 100000
        if img.ndim==3:
            img = color_grade(img, warmth=self.warmth,
                              teal_shadows=self.teal_shadows,
                              saturation=self.saturation)
        return img

    def process(self, mono, black=None, white=None,
                tint_rgb=(0.95, 0.97, 1.0)):
        """Process new image — grain seed advances (image looks different each call)."""
        if black is None: black = float(np.percentile(mono, 1.0))
        if white is None: white = float(np.percentile(mono, 99.5))
        img = tone_map(mono, black, white, self.stretch)
        img = cinematic_curve(img)
        img = mono_to_rgb(img, *tint_rgb)
        return to_surface(self._fx(img, advance_grain=True), self.display_w, self.display_h,
                           smooth=getattr(self,'_smooth_upscale',False))

    def process_rgb(self, *args, **kwargs):
        """Accepts (rgb_HW3, black, white) or legacy (r, g, b, black, white)."""
        if isinstance(args[0], np.ndarray) and args[0].ndim == 3:
            rgb   = args[0]
            black = args[1] if len(args)>1 else kwargs.get("black")
            white = args[2] if len(args)>2 else kwargs.get("white")
        else:
            r, g, b = args[0], args[1], args[2]
            rgb   = np.stack([r, g, b], axis=-1)
            black = args[3] if len(args)>3 else kwargs.get("black")
            white = args[4] if len(args)>4 else kwargs.get("white")
        lum = rgb[:,:,0]*0.299+rgb[:,:,1]*0.587+rgb[:,:,2]*0.114
        if black is None: black = float(np.percentile(lum, 1.0))
        if white is None: white = float(np.percentile(lum, 99.5))
        img = normalize_rgb(rgb, black, white, self.stretch)
        for c in range(3): img[:,:,c] = cinematic_curve(img[:,:,c])
        return to_surface(self._fx(img, advance_grain=True), self.display_w, self.display_h,
                           smooth=getattr(self,'_smooth_upscale',False))

    # legacy aliases
    def process_mono(self, *a, **kw): return self.process(*a, **kw)
    def resize_display(self, w, h): self.display_w=w; self.display_h=h

    def get_settings(self):
        return {
            "render":   f"{self.render_w}x{self.render_h}",
            "display":  f"{self.display_w}x{self.display_h}",
            "upscale":  f"x{max(1,self.display_w//self.render_w)}",
            "stretch":  self.stretch,
            "bloom":    self.bloom_on,
            "spikes":   self.spikes_on,
            "chrom":    self.chrom_on,
            "grain":    self.grain_on,
        }

    def get_info(self):
        return {
            "render_res":  (self.render_w, self.render_h),
            "display_res": (self.display_w, self.display_h),
            "scale":       (round(self.display_w/max(1,self.render_w),1),
                            round(self.display_h/max(1,self.render_h),1)),
            "effects":     {k: getattr(self, k+"_on", False)
                            for k in ["bloom","spikes","chrom","grain"]},
        }
