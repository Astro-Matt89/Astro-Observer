"""
Imaging Screen - Complete Acquisition and Processing Interface

Integrated imaging system with:
- Live acquisition simulation
- Calibration pipeline
- Stacking with multiple methods
- Real-time processing and preview
- Export capabilities
"""

import pygame
import numpy as np
from typing import Optional
from datetime import datetime
import os

from .base_screen import BaseScreen
from .components import Button, Panel, Label
from imaging.camera import get_camera, Camera
from imaging.frames import Frame, FrameMetadata, FrameType, ImagingSession
from imaging.calibration import Calibrator
from imaging.stacking import StackingEngine, StackMethod
from imaging.processing import ImageProcessor, StretchMethod


class ImagingScreen(BaseScreen):
    """
    Complete imaging interface
    
    Full-featured astronomical imaging with acquisition, 
    calibration, stacking, and processing.
    """
    
    def __init__(self, state_manager):
        super().__init__("IMAGING")
        self.state_manager = state_manager
        
        # Camera setup - use camera from game state
        self._init_camera()
        
        # Imaging session
        self.session = ImagingSession("Current_Session")
        
        # Generated data
        self.light_frames = []
        self.dark_frames = []
        self.flat_frames = []
        self.calibrated_frames = []
        self.stacked_image = None
        
        self.master_dark = None
        self.master_flat = None
        
        # View state
        self.view_mode = "RAW"  # RAW, CAL, STACK
        self.current_frame_idx = 0
        self.show_histogram = True
        
        # Stretch parameters
        self.black_point = 0.0
        self.white_point = 0.3
        self.gamma = 2.2
        
        # UI state
        self.acquiring = False
        self.processing = False
        self.progress = 0.0
        self.status_message = "Ready"
        
        # Buttons
        self.buttons = {}
        self._create_buttons()
        
        # Log
        self.log = []
        self.add_log("Imaging system initialized")
    
    def _init_camera(self):
        """Initialize camera from game state"""
        state = self.state_manager.get_state()
        camera_id = state.camera_id if state.camera_id else "ZWO_ASI294MC"
        
        self.camera = get_camera(camera_id, seed=42)
        
        # Enable cooling if available
        if self.camera.spec.has_cooling:
            self.camera.set_cooling(True, -10.0)
    
    def _create_buttons(self):
        """Create UI buttons"""
        # Generate dataset
        self.buttons['generate'] = Button(
            20, 120, 150, 35, "GENERATE",
            callback=self.generate_dataset
        )
        
        # Calibrate
        self.buttons['calibrate'] = Button(
            180, 120, 150, 35, "CALIBRATE",
            callback=self.calibrate_frames
        )
        
        # Stack
        self.buttons['stack'] = Button(
            340, 120, 150, 35, "STACK",
            callback=self.stack_frames
        )
        
        # View modes
        self.buttons['view_raw'] = Button(
            20, 170, 100, 30, "RAW",
            callback=lambda: self.set_view_mode("RAW")
        )
        
        self.buttons['view_cal'] = Button(
            130, 170, 100, 30, "CAL",
            callback=lambda: self.set_view_mode("CAL")
        )
        
        self.buttons['view_stack'] = Button(
            240, 170, 100, 30, "STACK",
            callback=lambda: self.set_view_mode("STACK")
        )
        
        # Save
        self.buttons['save'] = Button(
            20, 210, 150, 35, "SAVE PNG",
            callback=self.save_image
        )
    
    def add_log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {message}")
        if len(self.log) > 15:
            self.log.pop(0)
    
    def set_view_mode(self, mode: str):
        """Set view mode"""
        self.view_mode = mode
        self.current_frame_idx = 0
        self.add_log(f"View mode: {mode}")
    
    def generate_star_field(self, width: int, height: int, n_stars: int = 300) -> np.ndarray:
        """Generate synthetic star field"""
        rng = np.random.default_rng(42)
        
        field = np.zeros((height, width), dtype=np.float32)
        
        # Generate stars
        xs = rng.uniform(0, width, size=n_stars)
        ys = rng.uniform(0, height, size=n_stars)
        brightness = (rng.pareto(2.5, size=n_stars) + 1.0)
        brightness = brightness / np.max(brightness)
        brightness = 500 + 5000 * (brightness ** 3)
        
        # Add stars as gaussians
        sigma = 1.5
        for x, y, b in zip(xs, ys, brightness):
            ix, iy = int(x), int(y)
            size = 7
            yy, xx = np.ogrid[-size:size+1, -size:size+1]
            g = np.exp(-(xx*xx + yy*yy) / (2 * sigma * sigma))
            g = g / g.sum() * b
            
            y0, y1 = max(0, iy-size), min(height, iy+size+1)
            x0, x1 = max(0, ix-size), min(width, ix+size+1)
            
            gy0 = size - (iy - y0)
            gy1 = gy0 + (y1 - y0)
            gx0 = size - (ix - x0)
            gx1 = gx0 + (x1 - x0)
            
            if y0 < y1 and x0 < x1:
                field[y0:y1, x0:x1] += g[gy0:gy1, gx0:gx1]
        
        return field
    
    def generate_flat_field(self, width: int, height: int) -> np.ndarray:
        """Generate synthetic flat with vignetting"""
        yy, xx = np.mgrid[0:height, 0:width]
        cx, cy = width / 2, height / 2
        
        r = np.sqrt((xx - cx)**2 + (yy - cy)**2) / (min(width, height) / 2)
        vignette = 1.0 - 0.4 * (r ** 2.5)
        vignette = np.clip(vignette, 0.3, 1.0)
        
        # Add dust
        rng = np.random.default_rng(123)
        for _ in range(5):
            mx, my = rng.uniform(0, width), rng.uniform(0, height)
            mr = rng.uniform(15, 30)
            strength = rng.uniform(0.05, 0.15)
            d = ((xx - mx)**2 + (yy - my)**2) / (2 * mr * mr)
            vignette *= (1.0 - strength * np.exp(-d))
        
        flat = vignette.astype(np.float32)
        flat = flat / flat.mean() * 10000
        
        return flat
    
    def generate_dataset(self):
        """Generate complete dataset"""
        self.add_log("Generating dataset...")
        self.acquiring = True
        self.progress = 0.0
        
        h, w = self.camera.spec.resolution[1], self.camera.spec.resolution[0]
        
        # Generate signals
        sky_signal = self.generate_star_field(w, h, n_stars=300)
        flat_signal = self.generate_flat_field(w, h)
        
        # Generate lights
        self.light_frames = []
        for i in range(10):
            meta = FrameMetadata(
                frame_type=FrameType.LIGHT,
                exposure_s=30.0,
                target_name="M42",
                filter_name="L"
            )
            frame = self.camera.capture_frame(
                30.0, sky_signal, FrameType.LIGHT,
                frame_seed=i, metadata=meta
            )
            self.light_frames.append(frame)
            self.progress = (i + 1) / 25.0  # 10/25 total frames
        
        # Generate darks
        self.dark_frames = []
        for i in range(5):
            dark = self.camera.capture_dark_frame(30.0, frame_seed=100+i)
            self.dark_frames.append(dark)
            self.progress = (10 + i + 1) / 25.0
        
        # Generate flats
        self.flat_frames = []
        for i in range(10):
            meta = FrameMetadata(
                frame_type=FrameType.FLAT,
                exposure_s=1.0,
                filter_name="L"
            )
            frame = self.camera.capture_frame(
                1.0, flat_signal, FrameType.FLAT,
                frame_seed=200+i, metadata=meta
            )
            self.flat_frames.append(frame)
            self.progress = (15 + i + 1) / 25.0
        
        self.acquiring = False
        self.progress = 1.0
        self.view_mode = "RAW"
        self.current_frame_idx = 0
        
        self.add_log(f"Dataset complete: {len(self.light_frames)}L + {len(self.dark_frames)}D + {len(self.flat_frames)}F")
        self.status_message = "Dataset ready"
    
    def calibrate_frames(self):
        """Calibrate light frames"""
        if not self.light_frames:
            self.add_log("ERROR: No light frames!")
            return
        
        self.add_log("Calibrating...")
        self.processing = True
        
        calibrator = Calibrator()
        
        # Create masters
        if self.dark_frames:
            self.master_dark = calibrator.create_master_dark(self.dark_frames)
            self.add_log(f"Master dark created")
        
        if self.flat_frames:
            self.master_flat = calibrator.create_master_flat(self.flat_frames, master_dark=None)
            self.add_log(f"Master flat created")
        
        # Calibrate
        self.calibrated_frames = calibrator.batch_calibrate_lights(
            self.light_frames,
            master_dark=self.master_dark,
            master_flat=self.master_flat,
            apply_cosmetic=True
        )
        
        self.processing = False
        self.view_mode = "CAL"
        self.current_frame_idx = 0
        
        self.add_log(f"Calibration complete: {len(self.calibrated_frames)} frames")
        self.status_message = "Frames calibrated"
    
    def stack_frames(self):
        """Stack calibrated frames"""
        if not self.calibrated_frames:
            self.add_log("ERROR: No calibrated frames!")
            return
        
        self.add_log("Stacking...")
        self.processing = True
        
        stacker = StackingEngine()
        self.stacked_image = stacker.stack(self.calibrated_frames, StackMethod.SIGMA_CLIP)
        
        snr_gain = stacker.compute_snr_improvement(len(self.calibrated_frames), StackMethod.SIGMA_CLIP)
        
        # Auto-adjust stretch
        self.black_point = float(np.percentile(self.stacked_image, 0.5))
        self.white_point = float(np.percentile(self.stacked_image, 99.5))
        
        self.processing = False
        self.view_mode = "STACK"
        
        self.add_log(f"Stack complete! SNR: {snr_gain:.2f}x")
        self.status_message = f"Stacked (SNR +{snr_gain:.1f}x)"
        
        # Award RP for imaging session
        state = self.state_manager.get_state()
        career = self.state_manager.get_career_mode()
        
        target = state.selected_target if state.selected_target else "Unknown"
        exposure_time = 30.0  # From generate (hardcoded for now)
        num_frames = len(self.calibrated_frames)
        
        rp_reward = career.complete_imaging_session(
            target=target,
            snr=snr_gain,
            exposure_time_s=exposure_time,
            num_frames=num_frames,
            telescope_id=state.telescope_id if state.telescope_id else "WEBCAM_LENS",
            camera_id=state.camera_id if state.camera_id else "WEBCAM_MOD",
            filter_id=state.filter_id if state.filter_id else "L"
        )
        
        self.add_log(f"Earned {rp_reward} RP!")
        self.status_message = f"Stacked (SNR +{snr_gain:.1f}x) +{rp_reward}RP"
    
    def save_image(self):
        """Save current image"""
        img = self.get_current_image()
        if img is None:
            self.add_log("ERROR: No image to save!")
            return
        
        # Process
        stretched = ImageProcessor.stretch_linear(img, self.black_point, self.white_point)
        stretched = ImageProcessor.stretch_gamma(stretched, 0, 1, self.gamma)
        uint8 = ImageProcessor.to_uint8(stretched)
        
        # Save
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/imaging_{self.view_mode.lower()}_{timestamp}.png"
        
        # Convert to RGB and save
        h, w = uint8.shape
        rgb_array = np.stack([uint8, uint8, uint8], axis=-1)
        surface = pygame.surfarray.make_surface(rgb_array.swapaxes(0, 1))
        pygame.image.save(surface, filename)
        
        self.add_log(f"Saved: {filename}")
    
    def get_current_image(self) -> Optional[np.ndarray]:
        """Get current image based on view mode"""
        if self.view_mode == "RAW":
            if self.light_frames and self.current_frame_idx < len(self.light_frames):
                return self.light_frames[self.current_frame_idx].data
        
        elif self.view_mode == "CAL":
            if self.calibrated_frames and self.current_frame_idx < len(self.calibrated_frames):
                return self.calibrated_frames[self.current_frame_idx].data
        
        elif self.view_mode == "STACK":
            return self.stacked_image
        
        return None
    
    def on_enter(self):
        super().on_enter()
        self.add_log("Imaging screen activated")
        
        # Reload camera if it changed in equipment manager
        state = self.state_manager.get_state()
        if state.camera_id and state.camera_id != self.camera.spec.name.replace(" ", "_").replace("-", "_").upper():
            self._init_camera()
            self.add_log(f"Camera updated: {self.camera.spec.name}")
    
    def on_exit(self):
        super().on_exit()
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        
        # Update buttons
        for button in self.buttons.values():
            button.update(mouse_pos)
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return 'OBSERVATORY'
                
                # Quick keys
                elif event.key == pygame.K_g:
                    self.generate_dataset()
                elif event.key == pygame.K_c:
                    self.calibrate_frames()
                elif event.key == pygame.K_k:
                    self.stack_frames()
                
                # View modes
                elif event.key == pygame.K_1:
                    self.set_view_mode("RAW")
                elif event.key == pygame.K_2:
                    self.set_view_mode("CAL")
                elif event.key == pygame.K_3:
                    self.set_view_mode("STACK")
                
                # Navigation
                elif event.key == pygame.K_LEFTBRACKET:
                    if self.view_mode in ["RAW", "CAL"]:
                        self.current_frame_idx = max(0, self.current_frame_idx - 1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    if self.view_mode == "RAW":
                        self.current_frame_idx = min(len(self.light_frames) - 1, self.current_frame_idx + 1)
                    elif self.view_mode == "CAL":
                        self.current_frame_idx = min(len(self.calibrated_frames) - 1, self.current_frame_idx + 1)
                
                # Stretch
                elif event.key == pygame.K_MINUS:
                    self.black_point = max(0, self.black_point - 10)
                elif event.key == pygame.K_EQUALS:
                    self.black_point = min(self.white_point - 1, self.black_point + 10)
                elif event.key == pygame.K_COMMA:
                    self.white_point = max(self.black_point + 1, self.white_point - 50)
                elif event.key == pygame.K_PERIOD:
                    self.white_point = self.white_point + 50
                
                # Histogram
                elif event.key == pygame.K_h:
                    self.show_histogram = not self.show_histogram
                
                # Save
                elif event.key == pygame.K_s:
                    self.save_image()
            
            # Buttons
            for button in self.buttons.values():
                if button.handle_event(event):
                    break
        
        return None
    
    def update(self, dt: float):
        """Update imaging screen"""
        pass
    
    def render(self, surface: pygame.Surface):
        """Render imaging screen"""
        W, H = surface.get_width(), surface.get_height()
        
        # Header
        header = pygame.Rect(10, 10, W - 20, 60)
        career = self.state_manager.get_career_mode()
        self.draw_header(surface, header, 
                        "IMAGING SYSTEM",
                        f"Camera: {self.camera.spec.name} | Temp: {self.camera.temperature_c:.1f}°C | {self.status_message} | RP: {career.stats.research_points}")
        
        # Left panel - Controls
        left_panel = pygame.Rect(10, 80, 500, H - 140)
        self.theme.draw_panel(surface, left_panel, "CONTROLS & STATUS")
        
        # Buttons
        for button in self.buttons.values():
            button.draw(surface)
        
        # Status info
        y = 260
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           20, y, "STATUS:", self.theme.colors.ACCENT_CYAN)
        y += 25
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"Lights: {len(self.light_frames)}", self.theme.colors.FG_PRIMARY)
        y += 20
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"Darks: {len(self.dark_frames)}", self.theme.colors.FG_PRIMARY)
        y += 20
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"Flats: {len(self.flat_frames)}", self.theme.colors.FG_PRIMARY)
        y += 20
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"Calibrated: {len(self.calibrated_frames)}", self.theme.colors.FG_PRIMARY)
        
        y += 35
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           20, y, "VIEW:", self.theme.colors.ACCENT_CYAN)
        y += 25
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"Mode: {self.view_mode}", self.theme.colors.ACCENT_YELLOW)
        
        if self.view_mode in ["RAW", "CAL"]:
            y += 20
            max_frames = len(self.light_frames) if self.view_mode == "RAW" else len(self.calibrated_frames)
            if max_frames > 0:
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   30, y, f"Frame: {self.current_frame_idx + 1}/{max_frames}", 
                                   self.theme.colors.FG_PRIMARY)
        
        y += 35
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           20, y, "STRETCH:", self.theme.colors.ACCENT_CYAN)
        y += 25
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"Black: {self.black_point:.0f}", self.theme.colors.FG_PRIMARY)
        y += 20
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           30, y, f"White: {self.white_point:.0f}", self.theme.colors.FG_PRIMARY)
        
        # Log
        y += 35
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           20, y, "LOG:", self.theme.colors.ACCENT_CYAN)
        y += 25
        for line in self.log[-10:]:
            if y > left_panel.bottom - 30:
                break
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               30, y, line[:55], self.theme.colors.FG_DIM)
            y += 16
        
        # Right panel - Image display
        right_panel = pygame.Rect(520, 80, W - 530, H - 140)
        self.theme.draw_panel(surface, right_panel, "IMAGE VIEWER")
        
        img_rect = pygame.Rect(530, 110, right_panel.w - 20, right_panel.h - 120)
        
        # Get and display image
        img = self.get_current_image()
        if img is not None:
            # Process for display
            stretched = ImageProcessor.stretch_linear(img, self.black_point, self.white_point)
            stretched = ImageProcessor.stretch_gamma(stretched, 0, 1, self.gamma)
            uint8 = ImageProcessor.to_uint8(stretched)
            
            # Create RGB surface
            h, w = uint8.shape
            rgb_array = np.stack([uint8, uint8, uint8], axis=-1)
            surf = pygame.surfarray.make_surface(rgb_array.swapaxes(0, 1))
            surf = surf.convert()
            
            # Scale to fit
            sw, sh = surf.get_width(), surf.get_height()
            scale = min(img_rect.w / sw, img_rect.h / sh)
            tw, th = int(sw * scale), int(sh * scale)
            
            scaled = pygame.transform.smoothscale(surf, (tw, th))
            
            # Center
            x = img_rect.x + (img_rect.w - tw) // 2
            y = img_rect.y + (img_rect.h - th) // 2
            
            surface.blit(scaled, (x, y))
            
            # Stats
            stats_y = right_panel.bottom - 90
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               530, stats_y,
                               f"Image: {img.shape[1]}x{img.shape[0]} | "
                               f"Min: {np.min(img):.0f} | Max: {np.max(img):.0f} | "
                               f"Mean: {np.mean(img):.0f}",
                               self.theme.colors.FG_DIM)
            
            # Histogram
            if self.show_histogram:
                hist_rect = pygame.Rect(530, right_panel.bottom - 70, right_panel.w - 20, 50)
                pygame.draw.rect(surface, (0, 10, 8), hist_rect)
                pygame.draw.rect(surface, self.theme.colors.FG_PRIMARY, hist_rect, 1)
                
                img_norm = np.clip((img - self.black_point) / (self.white_point - self.black_point + 1e-9), 0, 1)
                counts, _ = np.histogram(img_norm.ravel(), bins=64, range=(0, 1))
                
                max_count = max(counts.max(), 1)
                bin_width = hist_rect.w / 64
                
                for i, count in enumerate(counts):
                    if count > 0:
                        x = hist_rect.x + int(i * bin_width)
                        h = int((count / max_count) * (hist_rect.h - 4))
                        pygame.draw.rect(surface, self.theme.colors.FG_PRIMARY,
                                       pygame.Rect(x, hist_rect.bottom - h - 2, max(1, int(bin_width) - 1), h))
        else:
            # No image
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               img_rect.centerx, img_rect.centery,
                               "No image - Press G to generate dataset",
                               self.theme.colors.FG_DIM, align='center')
        
        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                        "[G] Generate  [C] Calibrate  [K] Stack  [S] Save  [1/2/3] View  [ESC] Back")
