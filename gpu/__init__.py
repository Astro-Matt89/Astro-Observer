"""
gpu — GPU rendering pipeline for Astro Observer (ModernGL + Pygame).

Optional dependency: pip install moderngl

If ModernGL is not available, all GPU classes gracefully degrade
and the application falls back to the standard Pygame software renderer.
"""

try:
    import moderngl  # noqa: F401
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
