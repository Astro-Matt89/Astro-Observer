"""
Equipment Manager Screen

Manage telescopes, cameras, and filters:
- Browse equipment catalog
- View detailed specs
- Calculate imaging stats (FOV, pixel scale)
- Select equipment for imaging
- Career mode ready (prices, tiers, unlocks)
"""

import pygame
from typing import Optional
from .base_screen import BaseScreen
from .components import Button, ScrollableList, Label
from imaging.equipment import (
    TELESCOPES, FILTERS, get_telescope, get_filter,
    calculate_setup_stats, TelescopeType, FilterType
)
from imaging.camera import CAMERA_DATABASE


class EquipmentScreen(BaseScreen):
    """
    Equipment Manager - Select and Configure Imaging Setup
    
    Browse telescopes, cameras, and filters with detailed specs.
    """
    
    def __init__(self, state_manager):
        super().__init__("EQUIPMENT")
        self.state_manager = state_manager

        # Mode detection: Career vs Explore
        if self.state_manager:
            career_mode = getattr(self.state_manager, 'career_mode', False)
            self._mode = 'CAREER' if career_mode else 'EXPLORE'
        else:
            self._mode = 'EXPLORE'

        # Current selection
        self.category = "TELESCOPE"  # TELESCOPE, CAMERA, FILTER, ALLSKY
        self.selected_telescope_id = None
        self.selected_camera_id = None
        self.selected_filter_id = None
        
        # Load current setup from state
        state = self.state_manager.get_state()
        self.selected_telescope_id = state.telescope_id
        self.selected_camera_id = state.camera_id
        self.selected_filter_id = state.filter_id
        
        # UI Components
        self.telescope_list = ScrollableList(20, 180, 380, 420, item_height=24)
        self.camera_list    = ScrollableList(20, 180, 380, 420, item_height=24)
        self.filter_list    = ScrollableList(20, 180, 380, 420, item_height=24)
        self.allsky_list    = ScrollableList(20, 180, 380, 420, item_height=24)
        
        # Category buttons
        self.category_buttons = {
            'telescope': Button(20,  120, 100, 35, "TELESCOPE",
                               callback=lambda: self.set_category("TELESCOPE")),
            'camera':    Button(125, 120, 100, 35, "CAMERA",
                               callback=lambda: self.set_category("CAMERA")),
            'allsky':    Button(230, 120, 100, 35, "ALL-SKY",
                               callback=lambda: self.set_category("ALLSKY")),
            'filter':    Button(335, 120, 100, 35, "FILTER",
                               callback=lambda: self.set_category("FILTER")),
        }
        
        # Action buttons
        self.buttons = {
            'select': Button(420, 520, 140, 40, "SELECT",
                            callback=self.select_equipment),
            'unlock': Button(570, 520, 140, 40, "UNLOCK",
                            callback=self.unlock_equipment),
            'apply': Button(720, 520, 140, 40, "APPLY SETUP",
                           callback=self.apply_setup),
        }
        
        # Populate lists
        self.update_lists()
    
    def set_category(self, category: str):
        """Set equipment category"""
        self.category = category
    
    def update_lists(self):
        """Update equipment lists"""
        career = self.state_manager.get_career_mode()
        
        # Telescopes
        telescope_items = []
        for tid, tspec in TELESCOPES.items():
            tier_str = f"T{tspec.tier}"
            price_str = f"{tspec.price_rp}RP" if tspec.price_rp > 0 else "FREE"
            
            # Check if unlocked
            is_unlocked = career.is_unlocked(tid)
            lock_icon = "" if is_unlocked else "🔒 "
            
            telescope_items.append(
                f"{lock_icon}{tier_str} {tspec.name[:28]:28s} {tspec.aperture_mm:>4.0f}mm f/{tspec.focal_ratio:.1f} {price_str:>7s}"
            )
        self.telescope_list.set_items(telescope_items)
        
        # Cameras — only non-allsky (standard for telescope use)
        camera_items = []
        self._camera_ids = []   # track ids for index lookup
        for cid, cspec in CAMERA_DATABASE.items():
            if cspec.is_allsky: continue
            tier_str  = f"T{cspec.tier}"
            price_str = f"{cspec.price_rp}RP" if cspec.price_rp > 0 else "FREE"
            res_str   = f"{cspec.resolution[0]}x{cspec.resolution[1]}"
            is_unlocked = career.is_unlocked(cid)
            lock_icon = "" if is_unlocked else "🔒 "
            camera_items.append(
                f"{lock_icon}{tier_str} {cspec.name[:26]:26s} {res_str:>12s} {price_str:>7s}"
            )
            self._camera_ids.append(cid)
        self.camera_list.set_items(camera_items)

        # All-sky cameras — standalone, no telescope/filter
        allsky_items = []
        self._allsky_ids = []
        for cid, cspec in CAMERA_DATABASE.items():
            if not cspec.is_allsky: continue
            tier_str  = f"T{cspec.tier}"
            price_str = f"{cspec.price_rp}RP" if cspec.price_rp > 0 else "FREE"
            res_str   = f"{cspec.resolution[0]}x{cspec.resolution[1]}"
            is_unlocked = career.is_unlocked(cid)
            lock_icon = "" if is_unlocked else "🔒 "
            allsky_items.append(
                f"{lock_icon}{tier_str} {cspec.name[:26]:26s} {res_str:>12s} {price_str:>7s}"
            )
            self._allsky_ids.append(cid)
        self.allsky_list.set_items(allsky_items)

        # Filters
        filter_items = []
        for fid, fspec in FILTERS.items():
            tier_str = f"T{fspec.tier}"
            price_str = f"{fspec.price_rp}RP" if fspec.price_rp > 0 else "FREE"
            
            # Check if unlocked
            is_unlocked = career.is_unlocked(fid)
            lock_icon = "" if is_unlocked else "🔒 "
            
            filter_items.append(
                f"{lock_icon}{tier_str} {fspec.name[:33]:33s} {price_str:>7s}"
            )
        self.filter_list.set_items(filter_items)
        
        # Set selections
        if self.selected_telescope_id:
            idx = list(TELESCOPES.keys()).index(self.selected_telescope_id)
            self.telescope_list.selected_index = idx
        
        if self.selected_camera_id:
            cid = self.selected_camera_id
            cspec = CAMERA_DATABASE.get(cid)
            if cspec and cspec.is_allsky and hasattr(self, "_allsky_ids"):
                idx = self._allsky_ids.index(cid) if cid in self._allsky_ids else 0
                self.allsky_list.selected_index = idx
            elif hasattr(self, "_camera_ids") and cid in self._camera_ids:
                self.camera_list.selected_index = self._camera_ids.index(cid)
        
        if self.selected_filter_id:
            idx = list(FILTERS.keys()).index(self.selected_filter_id)
            self.filter_list.selected_index = idx
    
    def select_equipment(self):
        """Select current item"""
        if self.category == "TELESCOPE":
            idx = self.telescope_list.get_selected_index()
            if 0 <= idx < len(TELESCOPES):
                self.selected_telescope_id = list(TELESCOPES.keys())[idx]

        elif self.category == "CAMERA":
            idx = self.camera_list.get_selected_index()
            ids = getattr(self, "_camera_ids", list(CAMERA_DATABASE.keys()))
            if 0 <= idx < len(ids):
                self.selected_camera_id = ids[idx]

        elif self.category == "ALLSKY":
            idx = self.allsky_list.get_selected_index()
            ids = getattr(self, "_allsky_ids", [])
            if 0 <= idx < len(ids):
                self.selected_camera_id = ids[idx]
                # Allsky: standalone — no telescope or filter needed
                self.selected_telescope_id = None
                self.selected_filter_id    = None

        elif self.category == "FILTER":
            idx = self.filter_list.get_selected_index()
            if 0 <= idx < len(FILTERS):
                self.selected_filter_id = list(FILTERS.keys())[idx]
    
    def apply_setup(self):
        """Apply setup to global state"""
        state = self.state_manager.get_state()
        state.telescope_id = self.selected_telescope_id
        state.camera_id    = self.selected_camera_id
        state.filter_id    = self.selected_filter_id

        # Check if allsky setup
        cam_spec = CAMERA_DATABASE.get(self.selected_camera_id)
        is_allsky = cam_spec.is_allsky if cam_spec else False

        # Update Observatory Hub display
        if 'OBSERVATORY' in self.state_manager.screens:
            obs_screen = self.state_manager.screens['OBSERVATORY']
            camera_name = cam_spec.name if cam_spec else "Unknown"
            if is_allsky:
                obs_screen.set_equipment("ALL-SKY", camera_name, "—")
            else:
                telescope  = get_telescope(self.selected_telescope_id)
                filter_spec = get_filter(self.selected_filter_id)
                if telescope and filter_spec:
                    obs_screen.set_equipment(telescope.name, camera_name, filter_spec.name)

        mode = "ALL-SKY standalone" if is_allsky else "telescope"
        print(f"Equipment applied [{mode}]: {self.selected_camera_id}")
    
    def unlock_equipment(self):
        """Unlock/purchase selected equipment"""
        career = self.state_manager.get_career_mode()
        
        # Determine what's selected
        equipment_id = None
        price_rp = 0
        equipment_name = ""
        
        if self.category == "TELESCOPE" and self.selected_telescope_id:
            equipment_id = self.selected_telescope_id
            telescope = get_telescope(equipment_id)
            if telescope:
                price_rp = telescope.price_rp
                equipment_name = telescope.name
        
        elif self.category == "CAMERA" and self.selected_camera_id:
            equipment_id = self.selected_camera_id
            camera = CAMERA_DATABASE.get(equipment_id)
            if camera:
                price_rp = camera.price_rp
                equipment_name = camera.name
        
        elif self.category == "FILTER" and self.selected_filter_id:
            equipment_id = self.selected_filter_id
            filter_spec = get_filter(equipment_id)
            if filter_spec:
                price_rp = filter_spec.price_rp
                equipment_name = filter_spec.name
        
        # Check if already unlocked
        if equipment_id and career.is_unlocked(equipment_id):
            print(f"{equipment_name} is already unlocked!")
            return
        
        # Check if can afford
        if equipment_id and not career.can_afford(price_rp):
            print(f"Not enough RP! Need {price_rp}, have {career.stats.research_points}")
            return
        
        # Purchase
        if equipment_id and career.purchase_equipment(equipment_id, price_rp):
            print(f"Unlocked {equipment_name} for {price_rp} RP!")
            # Refresh lists to update lock icons
            self.update_lists()
    
    def on_enter(self):
        super().on_enter()
        self._next_screen = None
    
    def on_exit(self):
        super().on_exit()
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        
        # Update buttons
        for button in self.category_buttons.values():
            button.update(mouse_pos)
        for button in self.buttons.values():
            button.update(mouse_pos)
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return 'OBSERVATORY'
                
                # Category switch
                elif event.key == pygame.K_1:
                    self.set_category("TELESCOPE")
                elif event.key == pygame.K_2:
                    self.set_category("CAMERA")
                elif event.key == pygame.K_3:
                    self.set_category("FILTER")
                elif event.key == pygame.K_4: self.set_category("ALLSKY")

                # Quick select
                elif event.key == pygame.K_RETURN:
                    self.select_equipment()
                elif event.key == pygame.K_SPACE:
                    self.apply_setup()

            # Lists
            if self.category == "TELESCOPE":
                self.telescope_list.handle_event(event)
            elif self.category == "CAMERA":
                self.camera_list.handle_event(event)
            elif self.category == "ALLSKY":
                self.allsky_list.handle_event(event)
            elif self.category == "FILTER":
                self.filter_list.handle_event(event)
            
            # Buttons
            for button in self.category_buttons.values():
                if button.handle_event(event):
                    break
            for button in self.buttons.values():
                if button.handle_event(event):
                    break
        
        # Check if navigation was requested
        if self._next_screen:
            result = self._next_screen
            self._next_screen = None
            return result
        
        return None
    
    def update(self, dt: float):
        """Update equipment screen"""
        pass
    
    def render(self, surface: pygame.Surface):
        """Render equipment manager"""
        if self._mode == 'CAREER':
            self._render_career_mode(surface)
        else:
            self._render_explore_mode(surface)

    def _render_career_mode(self, surface: pygame.Surface):
        """Render equipment manager in career mode."""
        self._render_equipment_ui(surface)

    def _render_explore_mode(self, surface: pygame.Surface):
        """Render equipment manager in explore (sandbox) mode."""
        self._render_equipment_ui(surface)

    def _render_equipment_ui(self, surface: pygame.Surface):
        """Shared equipment rendering logic."""
        W, H = surface.get_width(), surface.get_height()
        
        # Header
        header = pygame.Rect(10, 10, W - 20, 60)
        career = self.state_manager.get_career_mode()
        self.draw_header(surface, header,
                        "EQUIPMENT MANAGER",
                        f"Research Points: {career.stats.research_points} RP | Select telescopes, cameras, and filters")
        
        # Left panel - Equipment list
        left_panel = pygame.Rect(10, 80, 410, H - 140)
        self.theme.draw_panel(surface, left_panel, "EQUIPMENT CATALOG")
        
        # Category buttons
        for btn_name, button in self.category_buttons.items():
            # Highlight selected category
            if (btn_name == 'telescope' and self.category == "TELESCOPE") or \
               (btn_name == 'camera' and self.category == "CAMERA") or \
               (btn_name == 'filter' and self.category == "FILTER"):
                # Draw highlight behind button
                highlight = pygame.Rect(button.rect.x - 2, button.rect.y - 2,
                                       button.rect.width + 4, button.rect.height + 4)
                pygame.draw.rect(surface, self.theme.colors.ACCENT_CYAN, highlight, 2)
            
            button.draw(surface)
        
        # Column headers
        y = 162
        if self.category == "TELESCOPE":
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               20, y, "T  Name                           Aper   f/  Price",
                               self.theme.colors.FG_DIM)
        elif self.category == "CAMERA":
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               20, y, "T  Name                        Resolution  Price",
                               self.theme.colors.FG_DIM)
        elif self.category == "ALLSKY":
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               20, y, "T  Name                           Resolution   Price",
                               self.theme.colors.FG_DIM)
        elif self.category == "FILTER":
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               20, y, "T  Name                                   Price",
                               self.theme.colors.FG_DIM)
        
        # Equipment list
        if self.category == "TELESCOPE":
            self.telescope_list.draw(surface)
        elif self.category == "CAMERA":
            self.camera_list.draw(surface)
        elif self.category == "ALLSKY":
            self.allsky_list.draw(surface)
        elif self.category == "FILTER":
            self.filter_list.draw(surface)

        # Count
        allsky_ids = getattr(self, "_allsky_ids", [])
        camera_ids = getattr(self, "_camera_ids", list(CAMERA_DATABASE.keys()))
        count = (len(TELESCOPES) if self.category == "TELESCOPE" else
                 len(camera_ids) if self.category == "CAMERA" else
                 len(allsky_ids) if self.category == "ALLSKY" else
                 len(FILTERS))
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           20, 610,
                           f"{count} items available",
                           self.theme.colors.FG_DIM)
        
        # Action buttons
        self.buttons['select'].draw(surface)
        self.buttons['apply'].draw(surface)
        
        # Right panel - Details and stats
        right_panel = pygame.Rect(430, 80, W - 440, H - 140)
        self.theme.draw_panel(surface, right_panel, "DETAILS & STATS")
        
        y = 110
        
        # Show selected item details
        if self.category == "TELESCOPE" and self.selected_telescope_id:
            telescope = get_telescope(self.selected_telescope_id)
            if telescope:
                self.theme.draw_text(surface, self.theme.fonts.normal(),
                                   440, y, telescope.name, self.theme.colors.ACCENT_YELLOW)
                y += 30
                
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Type: {telescope.telescope_type.value}", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Aperture: {telescope.aperture_mm:.0f}mm", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Focal Length: {telescope.focal_length_mm:.0f}mm", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Focal Ratio: f/{telescope.focal_ratio:.1f}", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Obstruction: {telescope.obstruction_pct:.0f}%", self.theme.colors.FG_PRIMARY)
                y += 20
                if telescope.weight_kg > 0:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       450, y, f"Weight: {telescope.weight_kg:.1f}kg", self.theme.colors.FG_PRIMARY)
                    y += 20
                
                y += 10
                price_str = f"{telescope.price_rp} RP" if telescope.price_rp > 0 else "FREE"
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Price: {price_str} (Tier {telescope.tier})", 
                                   self.theme.colors.ACCENT_CYAN)
        
        elif self.category == "CAMERA" and self.selected_camera_id:
            camera = CAMERA_DATABASE.get(self.selected_camera_id)
            if camera:
                self.theme.draw_text(surface, self.theme.fonts.normal(),
                                   440, y, camera.name, self.theme.colors.ACCENT_YELLOW)
                y += 30
                
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Resolution: {camera.resolution[0]}x{camera.resolution[1]}", 
                                   self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Pixel Size: {camera.pixel_size_um:.1f}µm", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Sensor: {camera.resolution[0]*camera.pixel_size_um/1000:.1f}x{camera.resolution[1]*camera.pixel_size_um/1000:.1f}mm", 
                                   self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Read Noise: {camera.read_noise_e:.1f}e-", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"QE: {camera.quantum_efficiency*100:.0f}%", self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Bit Depth: {camera.bit_depth}-bit", self.theme.colors.FG_PRIMARY)
                y += 20
                cooling_str = f"{camera.min_temp_c:.0f}°C" if camera.has_cooling else "No"
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Cooling: {cooling_str}", self.theme.colors.FG_PRIMARY)
                y += 20
                
                y += 10
                price_str = f"{camera.price_rp} RP" if camera.price_rp > 0 else "FREE"
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Price: {price_str} (Tier {camera.tier})", 
                                   self.theme.colors.ACCENT_CYAN)
        
        elif self.category == "FILTER" and self.selected_filter_id:
            filter_spec = get_filter(self.selected_filter_id)
            if filter_spec:
                self.theme.draw_text(surface, self.theme.fonts.normal(),
                                   440, y, filter_spec.name, self.theme.colors.ACCENT_YELLOW)
                y += 30
                
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Type: {filter_spec.filter_type.value}", self.theme.colors.FG_PRIMARY)
                y += 20
                if filter_spec.wavelength_nm:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       450, y, f"Wavelength: {filter_spec.wavelength_nm:.1f}nm", 
                                       self.theme.colors.FG_PRIMARY)
                    y += 20
                if filter_spec.bandwidth_nm:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       450, y, f"Bandwidth: {filter_spec.bandwidth_nm:.1f}nm", 
                                       self.theme.colors.FG_PRIMARY)
                    y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Transmission: {filter_spec.transmission_pct:.0f}%", 
                                   self.theme.colors.FG_PRIMARY)
                y += 25
                
                # Description (word wrap)
                if filter_spec.description:
                    words = filter_spec.description.split()
                    line = ""
                    for word in words:
                        test_line = line + word + " "
                        if len(test_line) > 45:
                            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                               450, y, line.strip(), self.theme.colors.FG_DIM)
                            y += 16
                            line = word + " "
                        else:
                            line = test_line
                    if line:
                        self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                           450, y, line.strip(), self.theme.colors.FG_DIM)
                        y += 20
                
                y += 10
                price_str = f"{filter_spec.price_rp} RP" if filter_spec.price_rp > 0 else "FREE"
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Price: {price_str} (Tier {filter_spec.tier})", 
                                   self.theme.colors.ACCENT_CYAN)
        
        # Current setup stats
        if self.selected_telescope_id and self.selected_camera_id:
            y = 450
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               440, y, "IMAGING SETUP STATS:", self.theme.colors.ACCENT_CYAN)
            y += 25
            
            stats = calculate_setup_stats(self.selected_telescope_id, self.selected_camera_id)
            if stats:
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"FOV: {stats['fov_width_arcmin']:.1f}' x {stats['fov_height_arcmin']:.1f}'",
                                   self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Pixel Scale: {stats['pixel_scale_arcsec']:.2f}\"/pixel",
                                   self.theme.colors.FG_PRIMARY)
                y += 20
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Resolution: {stats['theoretical_resolution_arcsec']:.2f}\"",
                                   self.theme.colors.FG_PRIMARY)
                y += 20
                sampling_color = self.theme.colors.SUCCESS if 1.5 < stats['nyquist_sampling'] < 3.0 else self.theme.colors.WARNING
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   450, y, f"Sampling: {stats['nyquist_sampling']:.2f}x Nyquist",
                                   sampling_color)
                
                y += 25
                if 1.5 < stats['nyquist_sampling'] < 3.0:
                    self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                       450, y, "✓ Excellent sampling!", self.theme.colors.SUCCESS)
                elif stats['nyquist_sampling'] < 1.5:
                    self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                       450, y, "⚠ Undersampled (need shorter FL)", self.theme.colors.WARNING)
                else:
                    self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                       450, y, "⚠ Oversampled (need longer FL)", self.theme.colors.WARNING)
        
        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                        "[1/2/3] Category  [ENTER] Select  [SPACE] Apply Setup  [ESC] Back")
