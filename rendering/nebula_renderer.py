"""
Nebula Renderer - Rendering pixelart realistico di nebulose
Genera texture procedurali deterministiche per nebulose, SNR, ecc.
"""

from __future__ import annotations
import numpy as np
import pygame
from typing import Optional
from catalogs.deep_sky import DeepSkyObject, DSOType

def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF

def hash_u64(*vals: int) -> int:
    x = 0xA5A5A5A5A5A5A5A5
    for v in vals:
        x ^= (v & 0xFFFFFFFFFFFFFFFF)
        x = splitmix64(x)
    return x

def rng_from_seed(seed_u64: int) -> np.random.Generator:
    return np.random.default_rng(np.uint64(seed_u64))

class NebulaRenderer:
    """
    Renderer procedurale per nebulose in stile pixelart realistico
    Simula aspetto in filtri H-alpha, OIII, SII, RGB
    """
    
    def __init__(self, cache_size: int = 100):
        self._cache: dict[int, pygame.Surface] = {}
        self._cache_size = cache_size
        
    def render_nebula(self, obj: DeepSkyObject, 
                     size_px: int = 128,
                     filter_mode: str = "RGB") -> pygame.Surface:
        """
        Renderizza una nebulosa come superficie pygame
        
        Args:
            obj: Oggetto DeepSkyObject
            size_px: Dimensione della texture in pixel
            filter_mode: "RGB", "Ha", "OIII", "SII", "LRGB", "HOO", "SHO"
        
        Returns:
            pygame.Surface con la nebulosa renderizzata
        """
        # Check cache
        cache_key = (obj.id, size_px, filter_mode)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Genera texture basata sul tipo
        if obj.dso_type == DSOType.HII_REGION:
            surf = self._render_hii_region(obj, size_px, filter_mode)
        elif obj.dso_type == DSOType.PLANETARY:
            surf = self._render_planetary(obj, size_px, filter_mode)
        elif obj.dso_type == DSOType.SNR:
            surf = self._render_snr(obj, size_px, filter_mode)
        elif obj.dso_type == DSOType.REFLECTION:
            surf = self._render_reflection(obj, size_px, filter_mode)
        else:
            surf = self._render_generic(obj, size_px)
        
        # Salva in cache
        if len(self._cache) >= self._cache_size:
            # Rimuovi il più vecchio
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = surf
        
        return surf
    
    def _render_hii_region(self, obj: DeepSkyObject, size: int, filter_mode: str) -> pygame.Surface:
        """
        Renderizza regione HII (nebulosa a emissione)
        Struttura filiforme con zone di alta/bassa densità
        """
        rng = rng_from_seed(hash_u64(obj.id, 0xH11))
        
        # Crea campo di densità con noise multi-scala
        density = np.zeros((size, size), dtype=np.float32)
        
        # Noise a diverse scale (turbolenza)
        scales = [0.02, 0.05, 0.1, 0.2, 0.4]
        weights = [1.0, 0.6, 0.4, 0.25, 0.15]
        
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        for scale, weight in zip(scales, weights):
            # Perlin-like noise (semplificato)
            freq = scale
            phase_x = rng.uniform(0, 100)
            phase_y = rng.uniform(0, 100)
            
            noise = np.sin((xx * freq + phase_x) * 0.1) * np.sin((yy * freq + phase_y) * 0.1)
            density += noise * weight
        
        # Forma complessiva ellittica
        r_max = size * 0.45
        r_min = r_max * (obj.size_minor_arcmin / obj.size_arcmin)
        angle = np.radians(obj.pa_deg)
        
        # Rotazione
        dx = xx - cx
        dy = yy - cy
        dx_rot = dx * np.cos(angle) - dy * np.sin(angle)
        dy_rot = dx * np.sin(angle) + dy * np.cos(angle)
        
        r_ellipse = np.sqrt((dx_rot / r_max)**2 + (dy_rot / r_min)**2)
        envelope = np.exp(-(r_ellipse ** 2))
        
        density = density * envelope
        density = np.clip(density, 0, 1)
        
        # Aggiungi filamenti (caratteristico delle HII)
        n_filaments = rng.integers(5, 15)
        for _ in range(n_filaments):
            fx = rng.uniform(cx - r_max, cx + r_max)
            fy = rng.uniform(cy - r_min, cy + r_min)
            fw = rng.uniform(2, 8)
            strength = rng.uniform(0.3, 0.8)
            
            d = np.sqrt((xx - fx)**2 + (yy - fy)**2)
            filament = np.exp(-(d ** 2) / (2 * fw ** 2)) * strength
            density += filament * envelope
        
        density = np.clip(density, 0, 1)
        
        # Converte in colore basato sul filtro
        surf = self._density_to_surface(density, filter_mode, "HII")
        
        return surf
    
    def _render_planetary(self, obj: DeepSkyObject, size: int, filter_mode: str) -> pygame.Surface:
        """
        Renderizza nebulosa planetaria
        Struttura simmetrica con shell multipli
        """
        rng = rng_from_seed(hash_u64(obj.id, 0xP14N))
        
        density = np.zeros((size, size), dtype=np.float32)
        
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        # Shell principale
        r_inner = rng.uniform(0.15, 0.25) * size
        r_outer = rng.uniform(0.35, 0.45) * size
        
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        
        # Shell con gradiente
        shell = np.zeros_like(r)
        mask_inner = r < r_inner
        mask_outer = r > r_outer
        mask_shell = ~mask_inner & ~mask_outer
        
        shell[mask_shell] = 1.0 - abs(r[mask_shell] - (r_inner + r_outer)/2) / ((r_outer - r_inner)/2)
        shell[r < r_inner] = 0.2  # Cavity centrale (tipico)
        
        density = shell
        
        # Aggiungi ansae (lobi)
        if rng.random() < 0.6:  # 60% hanno lobi
            lobe_angle = rng.uniform(0, np.pi)
            lobe_dist = rng.uniform(r_outer * 1.2, r_outer * 1.5)
            lobe_size = rng.uniform(r_outer * 0.3, r_outer * 0.5)
            
            for sign in [-1, 1]:
                lx = cx + sign * lobe_dist * np.cos(lobe_angle)
                ly = cy + sign * lobe_dist * np.sin(lobe_angle)
                d = np.sqrt((xx - lx)**2 + (yy - ly)**2)
                lobe = np.exp(-(d ** 2) / (2 * lobe_size ** 2))
                density += lobe * 0.6
        
        density = np.clip(density, 0, 1)
        
        surf = self._density_to_surface(density, filter_mode, "PN")
        
        return surf
    
    def _render_snr(self, obj: DeepSkyObject, size: int, filter_mode: str) -> pygame.Surface:
        """
        Renderizza supernova remnant
        Struttura filiforme e caotica
        """
        rng = rng_from_seed(hash_u64(obj.id, 0x5NR))
        
        density = np.zeros((size, size), dtype=np.float32)
        
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        # Shell principale espanso
        r_shell = rng.uniform(0.35, 0.45) * size
        thickness = rng.uniform(0.08, 0.15) * size
        
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        
        # Shell con turbolenza
        shell = np.exp(-((r - r_shell) ** 2) / (2 * thickness ** 2))
        
        # Aggiungi filamenti radiali (caratteristici SNR)
        n_filaments = rng.integers(15, 30)
        for _ in range(n_filaments):
            angle = rng.uniform(0, 2 * np.pi)
            r_start = rng.uniform(r_shell * 0.8, r_shell * 1.2)
            length = rng.uniform(0.1, 0.3) * size
            width = rng.uniform(1, 3)
            
            # Filamento radiale
            dx_fil = (xx - cx) - r_start * np.cos(angle)
            dy_fil = (yy - cy) - r_start * np.sin(angle)
            
            # Distanza dal raggio
            d_perp = abs(dx_fil * np.sin(angle) - dy_fil * np.cos(angle))
            d_along = dx_fil * np.cos(angle) + dy_fil * np.sin(angle)
            
            fil_mask = (d_along > 0) & (d_along < length) & (d_perp < width)
            density[fil_mask] += rng.uniform(0.3, 0.7)
        
        density += shell
        density = np.clip(density, 0, 1)
        
        surf = self._density_to_surface(density, filter_mode, "SNR")
        
        return surf
    
    def _render_reflection(self, obj: DeepSkyObject, size: int, filter_mode: str) -> pygame.Surface:
        """
        Renderizza nebulosa a riflessione
        Più smooth e bluastra
        """
        rng = rng_from_seed(hash_u64(obj.id, 0xR3F1))
        
        density = np.zeros((size, size), dtype=np.float32)
        
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        # Distribuzione smooth
        r_max = size * 0.4
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        
        density = np.exp(-(r ** 2) / (2 * r_max ** 2))
        
        # Aggiungi variazioni locali
        n_clouds = rng.integers(3, 8)
        for _ in range(n_clouds):
            cloud_x = rng.normal(cx, r_max * 0.5)
            cloud_y = rng.normal(cy, r_max * 0.5)
            cloud_r = rng.uniform(r_max * 0.2, r_max * 0.4)
            cloud_strength = rng.uniform(0.3, 0.6)
            
            d = np.sqrt((xx - cloud_x)**2 + (yy - cloud_y)**2)
            cloud = np.exp(-(d ** 2) / (2 * cloud_r ** 2)) * cloud_strength
            density += cloud
        
        density = np.clip(density, 0, 1)
        
        surf = self._density_to_surface(density, filter_mode, "RN")
        
        return surf
    
    def _render_generic(self, obj: DeepSkyObject, size: int) -> pygame.Surface:
        """Rendering generico per oggetti sconosciuti"""
        density = np.zeros((size, size), dtype=np.float32)
        
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        
        r_max = size * 0.3
        density = np.exp(-(r ** 2) / (2 * r_max ** 2))
        
        return self._density_to_surface(density, "RGB", "GENERIC")
    
    def _density_to_surface(self, density: np.ndarray, filter_mode: str, obj_type: str) -> pygame.Surface:
        """
        Converte campo di densità in superficie pygame colorata
        
        Args:
            density: Array 2D float32 [0-1]
            filter_mode: "RGB", "Ha", "OIII", "SII", ecc.
            obj_type: "HII", "PN", "SNR", "RN", ecc.
        """
        h, w = density.shape
        
        # Palette colori per diversi filtri e tipi
        if filter_mode == "Ha":
            # H-alpha (rosso)
            r = (density * 255).astype(np.uint8)
            g = (density * 60).astype(np.uint8)
            b = (density * 60).astype(np.uint8)
        
        elif filter_mode == "OIII":
            # OIII (ciano-verde)
            r = (density * 80).astype(np.uint8)
            g = (density * 255).astype(np.uint8)
            b = (density * 180).astype(np.uint8)
        
        elif filter_mode == "SII":
            # SII (rosso scuro)
            r = (density * 200).astype(np.uint8)
            g = (density * 40).astype(np.uint8)
            b = (density * 40).astype(np.uint8)
        
        elif filter_mode == "HOO":
            # H-alpha + OIII (Hubble palette style)
            r = (density * 255).astype(np.uint8)
            g = (density * 180).astype(np.uint8)
            b = (density * 120).astype(np.uint8)
        
        elif filter_mode == "SHO":
            # Sulphur-Hydrogen-Oxygen (false color)
            r = (density * 255).astype(np.uint8)
            g = (density * 220).astype(np.uint8)
            b = (density * 120).astype(np.uint8)
        
        else:  # RGB o default
            if obj_type == "HII":
                # HII regions - rosso-rosa
                r = (density * 255).astype(np.uint8)
                g = (density * 120).astype(np.uint8)
                b = (density * 140).astype(np.uint8)
            
            elif obj_type == "PN":
                # Planetarie - verde-blu
                r = (density * 120).astype(np.uint8)
                g = (density * 255).astype(np.uint8)
                b = (density * 200).astype(np.uint8)
            
            elif obj_type == "SNR":
                # SNR - mix rosso-verde
                r = (density * 240).astype(np.uint8)
                g = (density * 180).astype(np.uint8)
                b = (density * 100).astype(np.uint8)
            
            elif obj_type == "RN":
                # Riflessione - blu
                r = (density * 120).astype(np.uint8)
                g = (density * 160).astype(np.uint8)
                b = (density * 255).astype(np.uint8)
            
            else:
                # Default
                gray = (density * 255).astype(np.uint8)
                r = g = b = gray
        
        # Crea superficie RGBA
        alpha = (density * 255).astype(np.uint8)
        
        # Stack RGB + A
        rgba = np.stack([r, g, b, alpha], axis=-1)
        
        # Crea superficie pygame
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.surfarray.blit_array(surf, rgba.transpose(1, 0, 2))
        
        return surf

class GalaxyRenderer:
    """Renderer per galassie in stile pixelart"""
    
    def __init__(self):
        self._cache: dict[int, pygame.Surface] = {}
    
    def render_galaxy(self, obj: DeepSkyObject, size_px: int = 64) -> pygame.Surface:
        """Renderizza una galassia"""
        
        if obj.id in self._cache:
            return self._cache[obj.id]
        
        if obj.dso_type == DSOType.SPIRAL:
            surf = self._render_spiral(obj, size_px)
        elif obj.dso_type == DSOType.ELLIPTICAL:
            surf = self._render_elliptical(obj, size_px)
        else:
            surf = self._render_irregular(obj, size_px)
        
        self._cache[obj.id] = surf
        return surf
    
    def _render_spiral(self, obj: DeepSkyObject, size: int) -> pygame.Surface:
        """Galassia spirale con bracci"""
        rng = rng_from_seed(hash_u64(obj.id, 0x5P1RA))
        
        density = np.zeros((size, size), dtype=np.float32)
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        # Bulge centrale
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        bulge_r = size * 0.15
        bulge = np.exp(-(r ** 2) / (2 * bulge_r ** 2))
        density += bulge * 1.5
        
        # Disco
        disk_r = size * 0.4
        disk = np.exp(-(r ** 1.5) / disk_r)
        density += disk * 0.8
        
        # Bracci spirali (2-4 bracci)
        n_arms = rng.integers(2, 5)
        pitch_angle = rng.uniform(10, 35)  # Gradi
        
        for arm_id in range(n_arms):
            base_angle = (arm_id / n_arms) * 2 * np.pi
            
            # Spirale logaritmica
            theta = np.arctan2(yy - cy, xx - cx)
            r_spiral = r * np.exp(-np.tan(np.radians(pitch_angle)) * (theta - base_angle))
            
            arm_width = size * 0.05
            arm_mask = np.exp(-((r - r_spiral) ** 2) / (2 * arm_width ** 2))
            
            # Aggiungi regioni HII nei bracci
            n_hii = rng.integers(5, 12)
            for _ in range(n_hii):
                hii_r = rng.uniform(bulge_r, disk_r)
                hii_theta = rng.uniform(base_angle, base_angle + 2 * np.pi / n_arms)
                hii_x = cx + hii_r * np.cos(hii_theta)
                hii_y = cy + hii_r * np.sin(hii_theta)
                hii_size = rng.uniform(1, 3)
                
                d_hii = np.sqrt((xx - hii_x)**2 + (yy - hii_y)**2)
                hii = np.exp(-(d_hii ** 2) / (2 * hii_size ** 2))
                density += hii * 0.5
            
            density += arm_mask * 0.6
        
        density = np.clip(density, 0, 1)
        
        # Colore giallastro
        surf = self._density_to_galaxy_surface(density, color_temp=5500)
        return surf
    
    def _render_elliptical(self, obj: DeepSkyObject, size: int) -> pygame.Surface:
        """Galassia ellittica - smooth e simmetrica"""
        density = np.zeros((size, size), dtype=np.float32)
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        # Profilo de Vaucouleurs (semplificato)
        r_eff = size * 0.3
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        
        density = np.exp(-7.67 * ((r / r_eff) ** 0.25 - 1))
        density = np.clip(density, 0, 1)
        
        # Colore rossastro (stelle vecchie)
        surf = self._density_to_galaxy_surface(density, color_temp=4500)
        return surf
    
    def _render_irregular(self, obj: DeepSkyObject, size: int) -> pygame.Surface:
        """Galassia irregolare - caotica"""
        rng = rng_from_seed(hash_u64(obj.id, 0x1RR36))
        
        density = np.zeros((size, size), dtype=np.float32)
        yy, xx = np.mgrid[0:size, 0:size]
        cx, cy = size / 2, size / 2
        
        # Più regioni di formazione stellare
        n_regions = rng.integers(5, 15)
        for _ in range(n_regions):
            rx = rng.normal(cx, size * 0.2)
            ry = rng.normal(cy, size * 0.2)
            rr = rng.uniform(size * 0.05, size * 0.15)
            strength = rng.uniform(0.3, 1.0)
            
            d = np.sqrt((xx - rx)**2 + (yy - ry)**2)
            region = np.exp(-(d ** 2) / (2 * rr ** 2)) * strength
            density += region
        
        density = np.clip(density, 0, 1)
        
        surf = self._density_to_galaxy_surface(density, color_temp=6000)
        return surf
    
    def _density_to_galaxy_surface(self, density: np.ndarray, color_temp: float) -> pygame.Surface:
        """Converte densità in superficie con colore basato su temperatura"""
        # Approssimazione colore da temperatura (K)
        if color_temp < 5000:
            r_factor = 1.0
            g_factor = 0.7
            b_factor = 0.5
        elif color_temp < 6000:
            r_factor = 1.0
            g_factor = 0.9
            b_factor = 0.7
        else:
            r_factor = 0.9
            g_factor = 0.95
            b_factor = 1.0
        
        r = (density * 255 * r_factor).astype(np.uint8)
        g = (density * 255 * g_factor).astype(np.uint8)
        b = (density * 255 * b_factor).astype(np.uint8)
        alpha = (density * 255).astype(np.uint8)
        
        rgba = np.stack([r, g, b, alpha], axis=-1)
        
        h, w = density.shape
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.surfarray.blit_array(surf, rgba.transpose(1, 0, 2))
        
        return surf
