"""
=============================================================================
 Astro Observer — Sprint 15.5 Proof of Concept
 GPU Rendering Pipeline con ModernGL + Pygame
=============================================================================

 Questo PoC dimostra:
   1. Pygame crea la finestra OpenGL (transizione morbida dal tuo codice)
   2. ModernGL gestisce tutto il rendering via shader GLSL
   3. Starfield procedurale generato come numpy array → texture GPU
   4. Bloom multi-pass (bright extract → blur H → blur V → combine)
   5. Twinkling animato (modulazione temporale per-stella)
   6. Nearest-neighbor upscale da risoluzione interna a schermo
   7. Toggle degli effetti via tastiera

 Controlli:
   B  = toggle bloom on/off
   T  = toggle twinkling on/off
   +/- = intensità bloom
   ESC = esci

 Requisiti:
   pip install pygame moderngl numpy
=============================================================================
"""

import pygame
import moderngl
import numpy as np
import struct
import time
import sys

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------
INTERNAL_W, INTERNAL_H = 640, 360     # risoluzione interna (pixel-art)
SCREEN_W, SCREEN_H     = 1280, 720    # risoluzione finestra
NUM_STARS               = 2000         # stelle nel campo
BLOOM_INTENSITY         = 0.6          # intensità bloom iniziale
BLOOM_THRESHOLD         = 0.35         # soglia luminosità per bloom
BLOOM_BLUR_PASSES       = 2           # passate di blur (più = più soft)

# ---------------------------------------------------------------------------
# Shader GLSL — Vertex (condiviso da tutti i pass)
# ---------------------------------------------------------------------------
VERTEX_SHADER = """
#version 330
in vec2 in_position;
in vec2 in_texcoord;
out vec2 uv;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    uv = in_texcoord;
}
"""

# ---------------------------------------------------------------------------
# Shader — Rendering scena + twinkling
# ---------------------------------------------------------------------------
SCENE_FRAGMENT = """
#version 330
uniform sampler2D starfield;
uniform sampler2D twinkle_data;   // 1D texture con fasi per-stella
uniform float u_time;
uniform bool  u_twinkling;
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 color = texture(starfield, uv);
    
    if (u_twinkling && color.r > 0.05) {
        // Modula luminosità usando il canale alpha come "fase" dello scintillio
        // Le stelle più brillanti scintillano di più
        float phase = color.a * 6.2831853;  // fase unica per stella
        float brightness = color.r;
        
        // Scintillio multi-frequenza per realismo
        float twinkle = 1.0
            + 0.15 * sin(u_time * 3.7 + phase)
            + 0.10 * sin(u_time * 7.3 + phase * 1.3)
            + 0.05 * sin(u_time * 13.1 + phase * 2.7);
        
        // Le stelle dim scintillano di più (realistico — seeing atmosferico)
        float scintillation = mix(0.3, 0.05, smoothstep(0.1, 0.9, brightness));
        twinkle = mix(1.0, twinkle, scintillation);
        
        color.rgb *= twinkle;
    }
    
    // Mantieni alpha a 1 per il compositing
    fragColor = vec4(color.rgb, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Shader — Estrazione pixel brillanti (bright pass)
# ---------------------------------------------------------------------------
BRIGHT_EXTRACT_FRAGMENT = """
#version 330
uniform sampler2D scene;
uniform float u_threshold;
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 color = texture(scene, uv);
    float luma = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
    
    // Soft knee — transizione morbida invece di cutoff netto
    float knee = 0.1;
    float soft = luma - u_threshold + knee;
    soft = clamp(soft / (2.0 * knee), 0.0, 1.0);
    soft = soft * soft;
    float contribution = max(soft, step(u_threshold, luma));
    
    fragColor = vec4(color.rgb * contribution, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Shader — Gaussian Blur (singola direzione, configurabile)
# ---------------------------------------------------------------------------
BLUR_FRAGMENT = """
#version 330
uniform sampler2D image;
uniform vec2 u_direction;   // (1/w, 0) per H, (0, 1/h) per V
uniform float u_radius;
out vec4 fragColor;
in vec2 uv;

void main() {
    // Kernel gaussiano 9-tap
    float weights[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    
    vec3 result = texture(image, uv).rgb * weights[0];
    
    for (int i = 1; i < 5; i++) {
        vec2 offset = u_direction * float(i) * u_radius;
        result += texture(image, uv + offset).rgb * weights[i];
        result += texture(image, uv - offset).rgb * weights[i];
    }
    
    fragColor = vec4(result, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Shader — Combinazione finale (scene + bloom) con upscale
# ---------------------------------------------------------------------------
COMBINE_FRAGMENT = """
#version 330
uniform sampler2D scene;
uniform sampler2D bloom;
uniform float u_bloom_intensity;
uniform bool  u_bloom_enabled;
out vec4 fragColor;
in vec2 uv;

void main() {
    vec3 scene_color = texture(scene, uv).rgb;
    vec3 bloom_color = texture(bloom, uv).rgb;
    
    vec3 final_color = scene_color;
    if (u_bloom_enabled) {
        // Additive bloom
        final_color += bloom_color * u_bloom_intensity;
    }
    
    // Tone mapping semplice (evita clipping)
    final_color = final_color / (final_color + vec3(1.0));
    
    // Gamma correction
    final_color = pow(final_color, vec3(1.0 / 2.2));
    
    fragColor = vec4(final_color, 1.0);
}
"""


# ===========================================================================
# Generazione Starfield procedurale
# ===========================================================================
def generate_starfield(width, height, num_stars, seed=42):
    """
    Genera uno starfield come numpy array RGBA float32.
    Simula distribuzione realistica di magnitudini.
    Il canale alpha memorizza la "fase" per il twinkling.
    
    Questo è il punto dove collegherai il tuo renderer attuale:
    basta convertire la tua pygame.Surface in numpy array.
    """
    rng = np.random.default_rng(seed)
    
    # Buffer nero
    field = np.zeros((height, width, 4), dtype=np.float32)
    
    # Genera posizioni stelle
    x = rng.integers(0, width, num_stars)
    y = rng.integers(0, height, num_stars)
    
    # Distribuzione di magnitudine (power law — più stelle dim che bright)
    magnitudes = rng.power(3.0, num_stars)  # 0..1, skewed verso dim
    brightness = magnitudes ** 0.5           # curva di risposta
    
    # Colori stellari (temperatura → colore)
    temps = rng.uniform(0.3, 1.0, num_stars)  # proxy temperatura
    r = np.clip(brightness * (0.8 + 0.4 * temps), 0, 1)
    g = np.clip(brightness * (0.7 + 0.3 * (1 - np.abs(temps - 0.5))), 0, 1)
    b = np.clip(brightness * (0.6 + 0.6 * (1 - temps)), 0, 1)
    
    # Fase random per twinkling (memorizzata in alpha)
    phase = rng.uniform(0, 1, num_stars).astype(np.float32)
    
    # Scrivi nel buffer
    field[y, x, 0] = r.astype(np.float32)
    field[y, x, 1] = g.astype(np.float32)
    field[y, x, 2] = b.astype(np.float32)
    field[y, x, 3] = phase
    
    # Aggiungi qualche stella brillante (per test bloom evidente)
    n_bright = 20
    bx = rng.integers(50, width - 50, n_bright)
    by = rng.integers(50, height - 50, n_bright)
    for i in range(n_bright):
        # Stella brillante con alone di 1px (simula PSF minima)
        bright = 0.7 + rng.random() * 0.3
        color_t = rng.random()
        sr = bright * (0.9 + 0.1 * color_t)
        sg = bright * (0.85 + 0.1 * (1 - abs(color_t - 0.5)))
        sb = bright * (0.7 + 0.3 * (1 - color_t))
        ph = rng.random()
        
        field[by[i], bx[i]] = [sr, sg, sb, ph]
        # Alone cross-shaped (estetica pixel art)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = bx[i]+dx, by[i]+dy
            if 0 <= nx < width and 0 <= ny < height:
                field[ny, nx] = [sr*0.3, sg*0.3, sb*0.3, ph]
    
    return field


# ===========================================================================
# Simulazione Layer Nebulosa (placeholder — qui colleghi il tuo generatore)
# ===========================================================================
def generate_nebula_layer(width, height, seed=123):
    """
    Genera un layer di nebulosa semplificato per il PoC.
    In produzione, qui va il tuo generatore procedurale (o il modulo C++).
    Restituisce RGBA float32.
    """
    rng = np.random.default_rng(seed)
    
    nebula = np.zeros((height, width, 4), dtype=np.float32)
    
    # 3 "blob" nebulari con colori diversi
    blobs = [
        (width * 0.3, height * 0.4, 80, [0.4, 0.05, 0.1]),   # rosso (H-alpha)
        (width * 0.6, height * 0.5, 100, [0.05, 0.1, 0.35]),  # blu (riflessione)
        (width * 0.45, height * 0.55, 60, [0.1, 0.3, 0.1]),   # verde (OIII)
    ]
    
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    
    for cx, cy, radius, color in blobs:
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        intensity = np.exp(-(dist**2) / (2 * radius**2))
        # Aggiungi rumore per struttura
        noise = rng.random((height, width)).astype(np.float32) * 0.3 + 0.7
        intensity *= noise
        
        for c in range(3):
            nebula[:, :, c] += intensity * color[c]
    
    nebula[:, :, 3] = np.clip(np.max(nebula[:, :, :3], axis=2) * 2, 0, 0.6)
    nebula[:, :, :3] = np.clip(nebula[:, :, :3], 0, 1)
    
    return nebula


# ===========================================================================
# Classe principale del rendering pipeline
# ===========================================================================
class GPURenderPipeline:
    """
    Pipeline di rendering GPU per Astro Observer.
    
    Flusso:
        numpy arrays (layer) → texture GPU → shader compositing → bloom → output
    
    Questa classe è il nucleo di quello che diventerà il tuo engine grafico.
    """
    
    def __init__(self, ctx: moderngl.Context, internal_w: int, internal_h: int):
        self.ctx = ctx
        self.iw = internal_w
        self.ih = internal_h
        
        # --- Geometria fullscreen quad ---
        vertices = np.array([
            # position    texcoord
            -1, -1,       0, 0,
             1, -1,       1, 0,
            -1,  1,       0, 1,
             1,  1,       1, 1,
        ], dtype='f4')
        
        self.vbo = ctx.buffer(vertices.tobytes())
        
        # --- Compila shader programs ---
        self.prog_scene   = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=SCENE_FRAGMENT)
        self.prog_bright  = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=BRIGHT_EXTRACT_FRAGMENT)
        self.prog_blur    = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=BLUR_FRAGMENT)
        self.prog_combine = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=COMBINE_FRAGMENT)
        
        # --- Crea VAO per ogni program ---
        self.vao_scene   = self._make_vao(self.prog_scene)
        self.vao_bright  = self._make_vao(self.prog_bright)
        self.vao_blur    = self._make_vao(self.prog_blur)
        self.vao_combine = self._make_vao(self.prog_combine)
        
        # --- Framebuffer per ogni pass ---
        # Scene FBO (output del rendering scena)
        self.scene_tex = ctx.texture((internal_w, internal_h), 4, dtype='f2')
        self.scene_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.scene_fbo = ctx.framebuffer(color_attachments=[self.scene_tex])
        
        # Bright pass FBO
        # Bloom lavora a metà risoluzione (performance + blur più ampio)
        bw, bh = internal_w // 2, internal_h // 2
        self.bright_tex = ctx.texture((bw, bh), 4, dtype='f2')
        self.bright_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.bright_fbo = ctx.framebuffer(color_attachments=[self.bright_tex])
        
        # Ping-pong FBO per blur
        self.blur_tex_a = ctx.texture((bw, bh), 4, dtype='f2')
        self.blur_tex_a.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.blur_fbo_a = ctx.framebuffer(color_attachments=[self.blur_tex_a])
        
        self.blur_tex_b = ctx.texture((bw, bh), 4, dtype='f2')
        self.blur_tex_b.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.blur_fbo_b = ctx.framebuffer(color_attachments=[self.blur_tex_b])
        
        # --- Texture per i layer della scena ---
        self.starfield_tex = self._create_layer_texture(internal_w, internal_h)
        self.nebula_tex    = self._create_layer_texture(internal_w, internal_h)
        
        # --- Stato ---
        self.bloom_enabled   = True
        self.twinkling       = True
        self.bloom_intensity = BLOOM_INTENSITY
        self.bloom_threshold = BLOOM_THRESHOLD
        self.time            = 0.0
    
    def _make_vao(self, program):
        return self.ctx.vertex_array(
            program,
            [(self.vbo, '2f 2f', 'in_position', 'in_texcoord')],
        )
    
    def _create_layer_texture(self, w, h):
        tex = self.ctx.texture((w, h), 4, dtype='f2')
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        return tex
    
    def upload_layer(self, texture, data: np.ndarray):
        """
        Carica un numpy array RGBA float32 come texture GPU.
        Questo è il bridge tra il tuo codice Python e la GPU.
        
        Uso tipico:
            pipeline.upload_layer(pipeline.starfield_tex, my_numpy_array)
        """
        # Converti a float16 per la GPU (dimezza bandwidth, qualità ok per display)
        data_f16 = data.astype(np.float16)
        texture.write(data_f16.tobytes())
    
    def upload_pygame_surface(self, texture, surface: pygame.Surface):
        """
        Carica direttamente una pygame.Surface come texture GPU.
        
        QUESTO È IL METODO CHIAVE PER LA MIGRAZIONE:
        Prendi le tue surface esistenti e le carichi così come sono.
        """
        # Converti surface → numpy → float16
        arr = pygame.surfarray.array3d(surface)           # (W, H, 3) uint8
        arr = arr.transpose(1, 0, 2)                       # (H, W, 3)
        rgba = np.zeros((*arr.shape[:2], 4), dtype=np.float32)
        rgba[:, :, :3] = arr / 255.0
        rgba[:, :, 3] = 1.0
        self.upload_layer(texture, rgba)
    
    def render_frame(self, screen_w: int, screen_h: int):
        """
        Esegue l'intera pipeline di rendering per un frame.
        """
        self.time = time.time()
        
        # === PASS 1: Render scena (compositing dei layer) ===
        self.scene_fbo.use()
        self.ctx.viewport = (0, 0, self.iw, self.ih)
        self.ctx.clear(0.0, 0.0, 0.02)  # quasi nero, leggera tinta blue
        
        # Abilita blending per compositing layer
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
        
        # Layer 1: Nebulosa (sotto le stelle)
        self.nebula_tex.use(location=0)
        self.prog_scene['starfield'].value = 0
        self.prog_scene['u_time'].value = self.time
        self.prog_scene['u_twinkling'].value = False  # niente twinkling per nebula
        self.vao_scene.render(moderngl.TRIANGLE_STRIP)
        
        # Layer 2: Starfield (sopra la nebulosa, con twinkling)
        # Blending additivo per le stelle (realistico)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE)
        self.starfield_tex.use(location=0)
        self.prog_scene['u_twinkling'].value = self.twinkling
        self.vao_scene.render(moderngl.TRIANGLE_STRIP)
        
        self.ctx.disable(moderngl.BLEND)
        
        if self.bloom_enabled:
            # === PASS 2: Estrai pixel brillanti ===
            bw, bh = self.iw // 2, self.ih // 2
            self.bright_fbo.use()
            self.ctx.viewport = (0, 0, bw, bh)
            self.scene_tex.use(location=0)
            self.prog_bright['scene'].value = 0
            self.prog_bright['u_threshold'].value = self.bloom_threshold
            self.vao_bright.render(moderngl.TRIANGLE_STRIP)
            
            # === PASS 3-4: Gaussian Blur ping-pong ===
            current_tex = self.bright_tex
            for _ in range(BLOOM_BLUR_PASSES):
                # Blur orizzontale
                self.blur_fbo_a.use()
                self.ctx.viewport = (0, 0, bw, bh)
                current_tex.use(location=0)
                self.prog_blur['image'].value = 0
                self.prog_blur['u_direction'].value = (1.0 / bw, 0.0)
                self.prog_blur['u_radius'].value = 1.5
                self.vao_blur.render(moderngl.TRIANGLE_STRIP)
                
                # Blur verticale
                self.blur_fbo_b.use()
                self.blur_tex_a.use(location=0)
                self.prog_blur['u_direction'].value = (0.0, 1.0 / bh)
                self.vao_blur.render(moderngl.TRIANGLE_STRIP)
                
                current_tex = self.blur_tex_b
        
        # === PASS FINALE: Combine + output a schermo ===
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, screen_w, screen_h)
        
        self.scene_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)  # pixel-art!
        self.scene_tex.use(location=0)
        self.prog_combine['scene'].value = 0
        
        if self.bloom_enabled:
            self.blur_tex_b.use(location=1)
        else:
            self.scene_tex.use(location=1)  # dummy
        self.prog_combine['bloom'].value = 1
        self.prog_combine['u_bloom_intensity'].value = self.bloom_intensity
        self.prog_combine['u_bloom_enabled'].value = self.bloom_enabled
        
        self.vao_combine.render(moderngl.TRIANGLE_STRIP)


# ===========================================================================
# Main — Entry point del PoC
# ===========================================================================
def main():
    # --- Init Pygame con contesto OpenGL ---
    pygame.init()
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, 
                                     pygame.GL_CONTEXT_PROFILE_CORE)
    
    screen = pygame.display.set_mode(
        (SCREEN_W, SCREEN_H), 
        pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
    )
    pygame.display.set_caption("Astro Observer — GPU Bloom PoC [Sprint 15.5]")
    
    # --- Init ModernGL dal contesto Pygame ---
    ctx = moderngl.create_context()
    ctx.enable(moderngl.NOTHING)
    
    print(f"OpenGL: {ctx.info['GL_RENDERER']}")
    print(f"Version: {ctx.info['GL_VERSION']}")
    print(f"Internal resolution: {INTERNAL_W}x{INTERNAL_H}")
    print(f"Screen resolution: {SCREEN_W}x{SCREEN_H}")
    print()
    print("Controlli:")
    print("  B = toggle bloom")
    print("  T = toggle twinkling")
    print("  +/- = bloom intensity")
    print("  ESC = esci")
    
    # --- Crea pipeline ---
    pipeline = GPURenderPipeline(ctx, INTERNAL_W, INTERNAL_H)
    
    # --- Genera e carica layer ---
    print("\nGenerazione starfield...")
    starfield_data = generate_starfield(INTERNAL_W, INTERNAL_H, NUM_STARS)
    pipeline.upload_layer(pipeline.starfield_tex, starfield_data)
    
    print("Generazione nebulosa...")
    nebula_data = generate_nebula_layer(INTERNAL_W, INTERNAL_H)
    pipeline.upload_layer(pipeline.nebula_tex, nebula_data)
    
    print("Pronto!\n")
    
    # --- Main loop ---
    clock = pygame.time.Clock()
    running = True
    frame_count = 0
    fps_timer = time.time()
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_b:
                    pipeline.bloom_enabled = not pipeline.bloom_enabled
                    print(f"Bloom: {'ON' if pipeline.bloom_enabled else 'OFF'}")
                elif event.key == pygame.K_t:
                    pipeline.twinkling = not pipeline.twinkling
                    print(f"Twinkling: {'ON' if pipeline.twinkling else 'OFF'}")
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    pipeline.bloom_intensity = min(2.0, pipeline.bloom_intensity + 0.1)
                    print(f"Bloom intensity: {pipeline.bloom_intensity:.1f}")
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    pipeline.bloom_intensity = max(0.0, pipeline.bloom_intensity - 0.1)
                    print(f"Bloom intensity: {pipeline.bloom_intensity:.1f}")
            elif event.type == pygame.VIDEORESIZE:
                pass  # ModernGL gestisce il resize via viewport
        
        # --- Render ---
        w, h = pygame.display.get_surface().get_size()
        pipeline.render_frame(w, h)
        
        pygame.display.flip()
        clock.tick(60)
        
        # --- FPS counter ---
        frame_count += 1
        now = time.time()
        if now - fps_timer >= 2.0:
            fps = frame_count / (now - fps_timer)
            pygame.display.set_caption(
                f"Astro Observer — GPU Bloom PoC — {fps:.0f} FPS "
                f"[Bloom: {'ON' if pipeline.bloom_enabled else 'OFF'} "
                f"({pipeline.bloom_intensity:.1f}x) | "
                f"Twinkle: {'ON' if pipeline.twinkling else 'OFF'}]"
            )
            frame_count = 0
            fps_timer = now
    
    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
