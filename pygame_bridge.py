"""
=============================================================================
 Astro Observer — Bridge Pygame → GPU Pipeline
=============================================================================

 Questo modulo mostra come integrare il tuo rendering Pygame esistente
 nella pipeline GPU ModernGL SENZA riscrivere il codice di generazione.

 Strategia di migrazione:
   1. I tuoi renderer attuali continuano a generare pygame.Surface
   2. Questo bridge converte Surface → numpy → texture GPU
   3. Il compositing e gli effetti girano su GPU
   4. Col tempo, migri i generatori a produrre numpy direttamente
   5. Eventualmente, i generatori C++ producono numpy via pybind11

 Questo approccio ti permette di migrare UN LAYER ALLA VOLTA.
=============================================================================
"""

import numpy as np
import pygame
try:
    import moderngl
except ImportError:
    moderngl = None


class LayerBridge:
    """
    Ponte tra il rendering software (Pygame/numpy) e la GPU (ModernGL).
    
    Ogni layer del tuo sistema può essere aggiornato indipendentemente.
    La texture GPU viene aggiornata solo quando il contenuto cambia,
    non ad ogni frame (questo è il vantaggio chiave rispetto a Pygame puro).
    """
    
    def __init__(self, ctx, width, height, name="unnamed"):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.name = name
        self.dirty = True  # flag: il contenuto è cambiato?
        
        # Crea texture GPU
        self.texture = ctx.texture((width, height), 4, dtype='f2')
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        
        # Buffer CPU (opzionale, per layer che si aggiornano incrementalmente)
        self._cpu_buffer = None
    
    def update_from_surface(self, surface: pygame.Surface):
        """
        Carica una pygame.Surface nella texture GPU.
        
        Esempio:
            # Il tuo codice esistente genera una surface
            sky_surface = render_sky_background(time, location)
            # La carichi sulla GPU
            sky_layer.update_from_surface(sky_surface)
        """
        arr = pygame.surfarray.array3d(surface)           # (W, H, 3) uint8
        arr = arr.transpose(1, 0, 2)                       # (H, W, 3)
        
        rgba = np.zeros((self.height, self.width, 4), dtype=np.float16)
        rgba[:, :, :3] = (arr / 255.0).astype(np.float16)
        rgba[:, :, 3] = np.float16(1.0)
        
        self.texture.write(rgba.tobytes())
        self.dirty = False
    
    def update_from_surface_alpha(self, surface: pygame.Surface):
        """
        Come update_from_surface ma preserva il canale alpha.
        Per layer semitrasparenti (nebulae, overlays).
        """
        arr = pygame.surfarray.pixels_alpha(surface)       # (W, H) uint8
        rgb = pygame.surfarray.array3d(surface)            # (W, H, 3) uint8
        
        rgb = rgb.transpose(1, 0, 2)                       # (H, W, 3)
        arr = arr.T                                         # (H, W)
        
        rgba = np.zeros((self.height, self.width, 4), dtype=np.float16)
        rgba[:, :, :3] = (rgb / 255.0).astype(np.float16)
        rgba[:, :, 3]  = (arr / 255.0).astype(np.float16)
        
        self.texture.write(rgba.tobytes())
        self.dirty = False
    
    def update_from_numpy(self, data: np.ndarray):
        """
        Carica un numpy array direttamente.
        Formato atteso: (H, W, 4) float32 RGBA, valori in [0, 1].
        
        Questo è il metodo che userai quando migri i generatori
        a produrre numpy direttamente (o via C++ pybind11).
        
        Esempio:
            # Generatore C++ via pybind11
            nebula_data = astro_engine.generate_nebula(params)  # → numpy f32
            nebula_layer.update_from_numpy(nebula_data)
        """
        assert data.shape == (self.height, self.width, 4), \
            f"Shape mismatch: expected ({self.height}, {self.width}, 4), got {data.shape}"
        
        data_f16 = data.astype(np.float16)
        self.texture.write(data_f16.tobytes())
        self.dirty = False
    
    def update_region(self, data: np.ndarray, x: int, y: int):
        """
        Aggiorna solo una regione della texture (per aggiornamenti incrementali).
        Utile per: UI overlay, indicatori, selezione oggetti.
        
        Molto più efficiente di ricaricare l'intera texture.
        """
        h, w = data.shape[:2]
        data_f16 = data.astype(np.float16)
        self.texture.write(data_f16.tobytes(), viewport=(x, y, w, h))
        self.dirty = False


class SceneCompositor:
    """
    Gestisce lo stack di layer e il compositing GPU.
    
    Corrisponde al tuo sistema di layer attuale, ma il compositing
    avviene sulla GPU in un singolo draw call invece che con pygame.blit().
    
    Layer order (configurabile):
        0: Sky gradient
        1: Milky Way  
        2: Nebulae
        3: Starfield
        4: Planets/Moon/Sun
        5: Atmosphere/Clouds
        6: Instrument overlay
        7: UI overlay
    """
    
    # Blending modes disponibili
    BLEND_ALPHA   = 'alpha'     # standard alpha compositing
    BLEND_ADD     = 'additive'  # additivo (stelle, emissione)
    BLEND_SCREEN  = 'screen'    # screen (glow morbido)
    BLEND_MULT    = 'multiply'  # moltiplicativo (ombre, dust)
    
    def __init__(self, ctx, internal_w, internal_h):
        self.ctx = ctx
        self.layers = {}           # name → LayerBridge
        self.layer_order = []      # ordine di rendering
        self.layer_config = {}     # name → {visible, blend_mode, opacity}
    
    def add_layer(self, name: str, bridge: LayerBridge, 
                  blend_mode: str = 'alpha', opacity: float = 1.0,
                  position: int = -1):
        """
        Aggiunge un layer allo stack.
        
        compositor.add_layer('starfield', star_bridge, blend_mode='additive')
        compositor.add_layer('nebula', neb_bridge, blend_mode='screen', opacity=0.7)
        """
        self.layers[name] = bridge
        self.layer_config[name] = {
            'visible': True,
            'blend_mode': blend_mode,
            'opacity': opacity,
        }
        if position < 0:
            self.layer_order.append(name)
        else:
            self.layer_order.insert(position, name)
    
    def set_visible(self, name: str, visible: bool):
        self.layer_config[name]['visible'] = visible
    
    def set_opacity(self, name: str, opacity: float):
        self.layer_config[name]['opacity'] = max(0.0, min(1.0, opacity))


# ===========================================================================
# Esempio di integrazione con il codice Astro Observer esistente
# ===========================================================================

INTEGRATION_EXAMPLE = """
# =======================================================================
# ESEMPIO: Come integrare nella tua main loop attuale
# =======================================================================
#
# PRIMA (tutto Pygame):
#
#   sky_surface = render_sky(time_state, location)
#   star_surface = render_starfield(catalog, camera)
#   nebula_surface = render_nebula(params)
#   
#   screen.blit(sky_surface, (0, 0))
#   screen.blit(nebula_surface, (0, 0))    # blending CPU, lento
#   screen.blit(star_surface, (0, 0))       # blending CPU, lento
#   pygame.display.flip()
#
#
# DOPO (Pygame genera, GPU composita):
#
#   # --- Setup (una volta) ---
#   import moderngl
#   from bloom_poc import GPURenderPipeline
#   from pygame_bridge import LayerBridge
#   
#   ctx = moderngl.create_context()
#   pipeline = GPURenderPipeline(ctx, 640, 360)
#   
#   sky_layer = LayerBridge(ctx, 640, 360, "sky")
#   star_layer = LayerBridge(ctx, 640, 360, "stars")
#   nebula_layer = LayerBridge(ctx, 640, 360, "nebula")
#   
#   # --- Ogni frame ---
#   # Il tuo codice di generazione resta IDENTICO
#   sky_surface = render_sky(time_state, location)
#   star_surface = render_starfield(catalog, camera)
#   
#   # La nebulosa si rigenera solo quando serve (non ogni frame!)
#   if nebula_needs_update:
#       nebula_surface = render_nebula(params)
#       nebula_layer.update_from_surface(nebula_surface)
#   
#   # Carica i layer che cambiano ogni frame
#   sky_layer.update_from_surface(sky_surface)
#   star_layer.update_from_surface(star_surface)
#   
#   # GPU fa il compositing + bloom + twinkling + upscale
#   pipeline.render_frame(screen_w, screen_h)
#   pygame.display.flip()
#
#
# Il risultato:
#   - Bloom, twinkling, compositing → GPU (gratis)
#   - Il tuo codice di generazione → invariato
#   - Migrazione incrementale → un layer alla volta
# =======================================================================
"""

if __name__ == '__main__':
    print(INTEGRATION_EXAMPLE)
