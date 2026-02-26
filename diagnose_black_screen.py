"""
test_fbo_blit.py — Test bridge FBO senza texture sampling.

Invece di:  Surface → texture → shader texture() → quad → screen
Usa:        Surface → texture (storage) → FBO → copy_framebuffer → screen

copy_framebuffer usa glBlitFramebuffer internamente,
che copia pixel direttamente tra framebuffer SENZA shader.

Eseguire:  python test_fbo_blit.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pygame
import numpy as np

W, H = 800, 600


def main():
    print("=" * 60)
    print("TEST FBO BLIT — Bridge senza texture sampling")
    print("=" * 60)

    pygame.init()
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                     pygame.GL_CONTEXT_PROFILE_CORE)
    screen = pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("FBO Blit Test")

    import moderngl
    ctx = moderngl.create_context()
    print(f"GPU: {ctx.info['GL_RENDERER']}")
    print(f"GL:  {ctx.info['GL_VERSION']}")
    print(f"Screen FBO glo: {ctx.screen.glo}")

    # ── Setup FBO bridge ─────────────────────────────────────────────
    # La texture serve solo come STORAGE per l'FBO, non viene mai
    # campionata da uno shader.
    tex = ctx.texture((W, H), 4, dtype='u1')
    fbo = ctx.framebuffer(color_attachments=[tex])
    print(f"FBO glo: {fbo.glo}, Tex glo: {tex.glo}")

    # ── Test 1: Upload + blit pattern procedural ─────────────────────
    print("\n── TEST 1: Procedural RGBA data → tex.write → copy_framebuffer ──")
    data = np.zeros((H, W, 4), dtype=np.uint8)
    data[:, :, 0] = 50
    data[:, :, 1] = 200
    data[:, :, 2] = 100
    data[:, :, 3] = 255
    # Yellow cross
    data[H//2-3:H//2+3, :, :3] = [255, 255, 0]
    data[:, W//2-3:W//2+3, :3] = [255, 255, 0]

    tex.write(data.tobytes())
    ctx.copy_framebuffer(ctx.screen, fbo)

    px = ctx.screen.read(viewport=(W//2, H//2, 1, 1), components=3)
    r, g, b = px[0], px[1], px[2]
    print(f"  Readback: RGB({r}, {g}, {b})")
    print(f"  Expected yellow ~(255,255,0): {'OK!' if r > 200 and g > 200 else 'FAIL'}")
    pygame.display.flip()
    pygame.time.wait(1000)

    # ── Test 2: Pygame surface → tobytes → upload → blit ─────────────
    print("\n── TEST 2: pygame Surface → tobytes(RGBA, flipped) → blit ──")
    surf = pygame.Surface((W, H))
    surf.fill((0, 180, 90))
    font = pygame.font.SysFont('monospace', 40)
    surf.blit(font.render("FBO BLIT WORKS!", False, (255, 255, 0)), (200, 260))
    pygame.draw.rect(surf, (255, 100, 0), (50, 50, W-100, H-100), 4)

    # flipped=True perché copy_framebuffer fa blit con Y invertito
    raw = pygame.image.tobytes(surf, "RGBA", True)
    tex.write(raw)
    ctx.copy_framebuffer(ctx.screen, fbo)

    px = ctx.screen.read(viewport=(W//2, H//2, 1, 1), components=3)
    r, g, b = px[0], px[1], px[2]
    print(f"  Readback: RGB({r}, {g}, {b})")
    print(f"  Expected green-ish: {'OK!' if g > 100 else 'FAIL'}")

    # Check if flipped correctly - read top and bottom
    px_top = ctx.screen.read(viewport=(W//2, 10, 1, 1), components=3)
    px_bot = ctx.screen.read(viewport=(W//2, H-10, 1, 1), components=3)
    print(f"  Top pixel: RGB({px_top[0]}, {px_top[1]}, {px_top[2]})")
    print(f"  Bot pixel: RGB({px_bot[0]}, {px_bot[1]}, {px_bot[2]})")
    pygame.display.flip()
    pygame.time.wait(1000)

    # ── Test 3: Same but flipped=False ───────────────────────────────
    print("\n── TEST 3: Same but flipped=False ──")
    raw_nf = pygame.image.tobytes(surf, "RGBA", False)
    tex.write(raw_nf)
    ctx.copy_framebuffer(ctx.screen, fbo)
    pygame.display.flip()
    pygame.time.wait(1000)
    print("  (Check visually if text is upside down vs test 2)")

    # ── Test 4: Continuous render (simulate game loop) ───────────────
    print("\n── TEST 4: Continuous render (60 frames) ──")
    offscreen = pygame.Surface((W, H))
    clock = pygame.time.Clock()

    for i in range(120):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); return

        # Render something dynamic
        offscreen.fill((0, 12 + (i % 20), 10))
        t = font.render(f"Frame {i}  FBO Blit Bridge", False, (0, 255, 120))
        offscreen.blit(t, (150, 280))
        pygame.draw.circle(offscreen, (255, 200, 0),
                           (W//2 + int(150 * np.sin(i*0.05)), H//2), 20)

        raw = pygame.image.tobytes(offscreen, "RGBA", True)
        tex.write(raw)
        ctx.copy_framebuffer(ctx.screen, fbo)
        pygame.display.flip()
        clock.tick(60)

        if i < 3:
            px = ctx.screen.read(viewport=(W//2, H//2, 1, 1), components=3)
            print(f"  Frame {i}: RGB({px[0]}, {px[1]}, {px[2]})")

    print("  Continuous render done!")

    # ── Test 5: After display recreation (simulate app flow) ─────────
    print("\n── TEST 5: Display recreation + FBO blit ──")
    pygame.quit()
    pygame.init()
    pygame.display.set_mode((W, H), pygame.RESIZABLE)
    # Simulate heavy init
    _f = [pygame.font.SysFont('monospace', s) for s in (10,14,18,24)]
    # Upgrade
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                     pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF)

    ctx2 = moderngl.create_context()
    tex2 = ctx2.texture((W, H), 4, dtype='u1')
    fbo2 = ctx2.framebuffer(color_attachments=[tex2])

    off5 = pygame.Surface((W, H))
    off5.fill((0, 180, 90))
    off5.blit(pygame.font.SysFont('monospace', 36).render(
        "TEST 5 — RECREATED!", False, (255, 255, 255)), (200, 270))
    tex2.write(pygame.image.tobytes(off5, "RGBA", True))
    ctx2.copy_framebuffer(ctx2.screen, fbo2)

    px = ctx2.screen.read(viewport=(W//2, H//2, 1, 1), components=3)
    r, g, b = px[0], px[1], px[2]
    print(f"  Readback: RGB({r}, {g}, {b})")
    print(f"  {'OK!' if g > 100 else 'FAIL'}")
    pygame.display.flip()
    pygame.time.wait(1000)

    pygame.quit()

    print("\n" + "=" * 60)
    print("Se hai visto colori e testo → FBO blit funziona!")
    print("Se tutto nero → anche glBlitFramebuffer è rotto")
    print("=" * 60)


if __name__ == "__main__":
    main()
