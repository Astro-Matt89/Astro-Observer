"""
=============================================================================
 Astro Observer — Shader Recipe Book
=============================================================================

 Raccolta di fragment shader GLSL pronti all'uso per effetti astronomici.
 Ogni shader è documentato e può essere integrato nella pipeline del PoC.

 Questi shader sono il motivo principale per passare a GPU:
 ognuno di questi effetti costerebbe 10-50ms su CPU.
 Su GPU costano <0.1ms ciascuno.
=============================================================================
"""

# ---------------------------------------------------------------------------
# 1. ATMOSPHERIC SCATTERING
# ---------------------------------------------------------------------------
# Simula la diffusione atmosferica: le stelle vicino all'orizzonte si
# attenuano, il cielo ha un gradiente di luminosità.
# Usa questo come post-process DOPO il compositing dei layer.
# ---------------------------------------------------------------------------
ATMOSPHERIC_SCATTER = """
#version 330
uniform sampler2D scene;
uniform float u_horizon_y;        // posizione orizzonte in UV (0..1)
uniform float u_extinction;       // forza estinzione atmosferica (0.5-3.0)
uniform vec3  u_horizon_color;    // colore glow orizzonte (es. 0.15, 0.08, 0.05)
uniform float u_sky_brightness;   // luminosità cielo base (0.0 = notte, 0.5 = twilight)
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 color = texture(scene, uv);
    
    // Altezza sopra l'orizzonte (0 = orizzonte, 1 = zenit)
    float altitude = clamp((uv.y - u_horizon_y) / (1.0 - u_horizon_y), 0.0, 1.0);
    
    // Estinzione atmosferica — le stelle basse si attenuano
    // Segue la legge di Bemporad (airmass ~ 1/sin(alt))
    float airmass = 1.0 / max(sin(altitude * 1.5707963), 0.01);
    float extinction = exp(-u_extinction * (airmass - 1.0));
    color.rgb *= extinction;
    
    // Glow dell'orizzonte (diffusione Rayleigh/Mie)
    float horizon_glow = exp(-altitude * 8.0) * (1.0 - altitude);
    color.rgb += u_horizon_color * horizon_glow;
    
    // Luminosità base del cielo (per crepuscolo/alba)
    float sky_add = u_sky_brightness * (1.0 - altitude * 0.5);
    color.rgb += vec3(sky_add * 0.4, sky_add * 0.5, sky_add * 0.7);
    
    fragColor = vec4(color.rgb, 1.0);
}
"""

# ---------------------------------------------------------------------------
# 2. PALETTE MAPPING (Retro / DOS VGA aesthetic)
# ---------------------------------------------------------------------------
# Mappa i colori continui a una palette discreta.
# La palette è una texture 1D (256 colori) caricata come uniform.
# Il dithering Bayer preserva l'estetica pixel-art.
# ---------------------------------------------------------------------------
PALETTE_MAPPING = """
#version 330
uniform sampler2D scene;
uniform sampler1D palette;        // 256 colori, texture 1D
uniform float u_palette_size;     // numero colori nella palette (es. 64)
uniform float u_dither_strength;  // 0.0 = no dither, 1.0 = full Bayer
uniform vec2  u_resolution;       // risoluzione interna
out vec4 fragColor;
in vec2 uv;

// Matrice Bayer 4x4 per ordered dithering
float bayer4x4(ivec2 pos) {
    int idx = (pos.x & 3) + (pos.y & 3) * 4;
    // Matrice di soglia normalizzata [0, 1)
    float m[16] = float[16](
         0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
        12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
         3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
        15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
    );
    return m[idx];
}

void main() {
    vec3 color = texture(scene, uv).rgb;
    
    // Coordinate pixel per Bayer dithering
    ivec2 pixel = ivec2(uv * u_resolution);
    float dither = bayer4x4(pixel) - 0.5;  // centrato su 0
    
    // Quantizza con dithering
    float levels = u_palette_size - 1.0;
    vec3 dithered = color + dither * u_dither_strength / levels;
    vec3 quantized = floor(clamp(dithered, 0.0, 1.0) * levels + 0.5) / levels;
    
    // Lookup nella palette (opzionale — se vuoi palette custom)
    // float luma = dot(quantized, vec3(0.2126, 0.7152, 0.0722));
    // vec3 mapped = texture(palette, luma).rgb;
    
    fragColor = vec4(quantized, 1.0);
}
"""

# ---------------------------------------------------------------------------
# 3. STAR DIFFRACTION SPIKES
# ---------------------------------------------------------------------------
# Simula i diffraction spike tipici dei telescopi Newtoniani.
# Applicato come post-process solo sulle stelle brillanti.
# ---------------------------------------------------------------------------
DIFFRACTION_SPIKES = """
#version 330
uniform sampler2D scene;
uniform float u_spike_length;     // lunghezza spike in pixel (5-20)
uniform float u_spike_intensity;  // intensità (0.3-0.8)
uniform float u_brightness_threshold;
uniform vec2  u_texel_size;       // 1.0/resolution
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 center = texture(scene, uv);
    float luma = dot(center.rgb, vec3(0.2126, 0.7152, 0.0722));
    
    vec3 spikes = vec3(0.0);
    
    if (luma > u_brightness_threshold) {
        // 4 direzioni: verticale, orizzontale (tipico Newton 4-vane spider)
        vec2 dirs[4] = vec2[4](
            vec2(1.0, 0.0),   // orizzontale
            vec2(0.0, 1.0),   // verticale
            vec2(0.707, 0.707),   // diagonale (per 6-vane)
            vec2(-0.707, 0.707)
        );
        
        for (int d = 0; d < 4; d++) {
            for (float i = 1.0; i <= u_spike_length; i += 1.0) {
                float falloff = 1.0 / (1.0 + i * 0.5);
                vec2 offset = dirs[d] * u_texel_size * i;
                spikes += texture(scene, uv + offset).rgb * falloff;
                spikes += texture(scene, uv - offset).rgb * falloff;
            }
        }
        
        spikes *= u_spike_intensity / (u_spike_length * 2.0);
    }
    
    fragColor = vec4(center.rgb + spikes, 1.0);
}
"""

# ---------------------------------------------------------------------------
# 4. CHROMATIC ABERRATION (lens effect)
# ---------------------------------------------------------------------------
# Sottile separazione RGB ai bordi del campo — simula ottica reale.
# Effetto molto sottile ma aggiunge "profondità" alla simulazione.
# ---------------------------------------------------------------------------
CHROMATIC_ABERRATION = """
#version 330
uniform sampler2D scene;
uniform float u_intensity;   // 0.001 - 0.005 per effetto sottile
uniform vec2  u_center;      // centro ottico (tipicamente 0.5, 0.5)
out vec4 fragColor;
in vec2 uv;

void main() {
    vec2 dir = uv - u_center;
    float dist = length(dir);
    
    // L'aberrazione aumenta con la distanza dal centro
    float offset = dist * dist * u_intensity;
    
    float r = texture(scene, uv + dir * offset).r;
    float g = texture(scene, uv).g;
    float b = texture(scene, uv - dir * offset).b;
    
    fragColor = vec4(r, g, b, 1.0);
}
"""

# ---------------------------------------------------------------------------
# 5. VIGNETTE (bordi scuri)
# ---------------------------------------------------------------------------
# Oscuramento ai bordi tipico delle ottiche reali.
# Molto semplice ma aggiunge immersione.
# ---------------------------------------------------------------------------
VIGNETTE = """
#version 330
uniform sampler2D scene;
uniform float u_vignette_radius;     // 0.5 - 0.8
uniform float u_vignette_softness;   // 0.2 - 0.5
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 color = texture(scene, uv);
    
    vec2 center = uv - vec2(0.5);
    float dist = length(center);
    float vignette = smoothstep(u_vignette_radius, 
                                 u_vignette_radius - u_vignette_softness, 
                                 dist);
    
    color.rgb *= vignette;
    fragColor = color;
}
"""

# ---------------------------------------------------------------------------
# 6. CCD NOISE SIMULATION
# ---------------------------------------------------------------------------
# Simula il rumore di un sensore CCD/CMOS per il modo imaging.
# Include: read noise, shot noise (Poisson), pattern noise.
# ---------------------------------------------------------------------------
CCD_NOISE = """
#version 330
uniform sampler2D scene;
uniform float u_time;
uniform float u_read_noise;       // 0.01 - 0.05
uniform float u_gain;             // ISO simulation
uniform float u_exposure;         // tempo esposizione
uniform vec2  u_resolution;
out vec4 fragColor;
in vec2 uv;

// Hash per rumore pseudo-random
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec4 signal = texture(scene, uv);
    
    // Coordinate pixel
    vec2 pixel = uv * u_resolution;
    
    // Read noise (gaussiano approssimato via Box-Muller semplificato)
    float n1 = hash(pixel + u_time * 0.1);
    float n2 = hash(pixel + u_time * 0.1 + vec2(127.1, 311.7));
    float gaussian = sqrt(-2.0 * log(max(n1, 0.001))) * cos(6.2831853 * n2);
    vec3 read_noise = vec3(gaussian) * u_read_noise;
    
    // Shot noise (proporzionale al segnale — Poisson approssimato)
    float shot = hash(pixel + u_time * 0.3 + vec2(269.5, 183.3)) - 0.5;
    vec3 shot_noise = signal.rgb * shot * 0.1 * inversesqrt(max(u_exposure, 0.1));
    
    // Fixed pattern noise (struttura colonna tipica CCD)
    float column_noise = hash(vec2(pixel.x, 0.0)) * 0.01;
    
    vec3 noisy = signal.rgb * u_gain + read_noise + shot_noise + column_noise;
    
    fragColor = vec4(max(noisy, 0.0), 1.0);
}
"""

# ---------------------------------------------------------------------------
# 7. SMOOTH ZOOM (per transizioni)
# ---------------------------------------------------------------------------
# Zoom con centro configurabile e interpolazione controllata.
# Utile per transizione da sky chart a vista telescopio.
# ---------------------------------------------------------------------------
SMOOTH_ZOOM = """
#version 330
uniform sampler2D scene;
uniform vec2  u_zoom_center;    // centro zoom in UV
uniform float u_zoom_level;     // 1.0 = no zoom, 2.0 = 2x, etc.
out vec4 fragColor;
in vec2 uv;

void main() {
    // Zoom centrato sul punto specificato
    vec2 zoomed_uv = (uv - u_zoom_center) / u_zoom_level + u_zoom_center;
    
    // Clamp per evitare wrapping
    zoomed_uv = clamp(zoomed_uv, 0.0, 1.0);
    
    // Nearest neighbor (pixel art preserving)
    fragColor = texture(scene, zoomed_uv);
}
"""

# ---------------------------------------------------------------------------
# Come usare questi shader nella pipeline
# ---------------------------------------------------------------------------
USAGE_GUIDE = """
Per aggiungere uno di questi shader alla pipeline:

1. Nel GPURenderPipeline.__init__(), compila il program:
   
   self.prog_vignette = ctx.program(
       vertex_shader=VERTEX_SHADER,
       fragment_shader=VIGNETTE
   )
   self.vao_vignette = self._make_vao(self.prog_vignette)

2. Aggiungi un FBO intermedio se serve (per catena di effetti):
   
   self.post_tex = ctx.texture((w, h), 4, dtype='f2')
   self.post_fbo = ctx.framebuffer(color_attachments=[self.post_tex])

3. Nel render_frame(), aggiungi il pass dopo il combine:
   
   # Vignette pass
   self.post_fbo.use()
   self.combined_tex.use(location=0)
   self.prog_vignette['scene'].value = 0
   self.prog_vignette['u_vignette_radius'].value = 0.7
   self.prog_vignette['u_vignette_softness'].value = 0.3
   self.vao_vignette.render(moderngl.TRIANGLE_STRIP)

L'ordine tipico degli effetti post-process:
   Scene compositing
   → Bloom
   → Diffraction spikes
   → Atmospheric scattering
   → Chromatic aberration (sottilissimo)
   → Vignette
   → CCD noise (solo in imaging mode)
   → Palette mapping (se in retro mode)
   → Upscale to screen
"""

if __name__ == '__main__':
    print("Shader Recipe Book — Astro Observer")
    print("=" * 50)
    print(USAGE_GUIDE)
    
    # Lista shader disponibili
    shaders = {
        'Atmospheric Scattering': ATMOSPHERIC_SCATTER,
        'Palette Mapping (Bayer dither)': PALETTE_MAPPING,
        'Diffraction Spikes': DIFFRACTION_SPIKES,
        'Chromatic Aberration': CHROMATIC_ABERRATION,
        'Vignette': VIGNETTE,
        'CCD Noise Simulation': CCD_NOISE,
        'Smooth Zoom': SMOOTH_ZOOM,
    }
    
    print("\nShader disponibili:")
    for name in shaders:
        print(f"  • {name}")
