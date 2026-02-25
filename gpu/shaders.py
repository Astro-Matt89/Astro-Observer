"""
gpu/shaders.py — Consolidated GLSL shaders for the Astro Observer GPU pipeline.

Sources:
  - VERTEX_SHADER, SCENE_FRAGMENT, BRIGHT_EXTRACT_FRAGMENT, BLUR_FRAGMENT,
    COMBINE_FRAGMENT  →  from bloom_poc.py (Sprint 15.5 PoC)
  - ATMOSPHERIC_SCATTER  →  from shader_recipes.py
"""

# ---------------------------------------------------------------------------
# Vertex shader — shared by all passes (fullscreen quad)
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
# Scene pass — starfield compositing + twinkling
# ---------------------------------------------------------------------------
SCENE_FRAGMENT = """
#version 330
uniform sampler2D starfield;
uniform float u_time;
uniform bool  u_twinkling;
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 color = texture(starfield, uv);

    if (u_twinkling && color.r > 0.05) {
        // Modulate brightness using alpha channel as per-star phase
        float phase = color.a * 6.2831853;
        float brightness = color.r;

        // Multi-frequency twinkling for realism
        float twinkle = 1.0
            + 0.15 * sin(u_time * 3.7 + phase)
            + 0.10 * sin(u_time * 7.3 + phase * 1.3)
            + 0.05 * sin(u_time * 13.1 + phase * 2.7);

        // Dim stars twinkle more (realistic — atmospheric seeing)
        float scintillation = mix(0.3, 0.05, smoothstep(0.1, 0.9, brightness));
        twinkle = mix(1.0, twinkle, scintillation);

        color.rgb *= twinkle;
    }

    // Keep alpha=1 for compositing
    fragColor = vec4(color.rgb, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Bright extract pass — isolates pixels above bloom threshold
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

    // Soft knee — smooth transition instead of hard cutoff
    float knee = 0.1;
    float soft = luma - u_threshold + knee;
    soft = clamp(soft / (2.0 * knee), 0.0, 1.0);
    soft = soft * soft;
    float contribution = max(soft, step(u_threshold, luma));

    fragColor = vec4(color.rgb * contribution, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Gaussian blur pass — single direction, configurable radius
# ---------------------------------------------------------------------------
BLUR_FRAGMENT = """
#version 330
uniform sampler2D image;
uniform vec2 u_direction;   // (1/w, 0) horizontal  |  (0, 1/h) vertical
uniform float u_radius;
out vec4 fragColor;
in vec2 uv;

void main() {
    // 9-tap Gaussian kernel
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
# Combine pass — scene + bloom, tone mapping, upscale to screen
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

    // Simple tone mapping (avoid clipping)
    final_color = final_color / (final_color + vec3(1.0));

    // Gamma correction
    final_color = pow(final_color, vec3(1.0 / 2.2));

    fragColor = vec4(final_color, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Atmospheric scattering post-process pass
# From shader_recipes.py — atmospheric extinction + horizon glow
# ---------------------------------------------------------------------------
ATMOSPHERIC_SCATTER = """
#version 330
uniform sampler2D scene;
uniform float u_horizon_y;        // horizon UV position (0..1)
uniform float u_extinction;       // atmospheric extinction strength (0.5-3.0)
uniform vec3  u_horizon_color;    // horizon glow colour (e.g. 0.15, 0.08, 0.05)
uniform float u_sky_brightness;   // base sky brightness (0.0=night, 0.5=twilight)
out vec4 fragColor;
in vec2 uv;

void main() {
    vec4 color = texture(scene, uv);

    // Altitude above horizon (0=horizon, 1=zenith)
    float altitude = clamp((uv.y - u_horizon_y) / (1.0 - u_horizon_y), 0.0, 1.0);

    // Atmospheric extinction — stars near horizon are attenuated
    // Follows Bemporad's law (airmass ~ 1/sin(alt))
    float airmass = 1.0 / max(sin(altitude * 1.5707963), 0.01);
    float extinction = exp(-u_extinction * (airmass - 1.0));
    color.rgb *= extinction;

    // Horizon glow (Rayleigh/Mie diffusion)
    float horizon_glow = exp(-altitude * 8.0) * (1.0 - altitude);
    color.rgb += u_horizon_color * horizon_glow;

    // Base sky brightness (twilight/dawn)
    float sky_add = u_sky_brightness * (1.0 - altitude * 0.5);
    color.rgb += vec3(sky_add * 0.4, sky_add * 0.5, sky_add * 0.7);

    fragColor = vec4(color.rgb, 1.0);
}
"""
