"""
Catalog Browser Screen

Browse and search astronomical object catalogs:
- All objects in Universe (389k stars + DSO)
- Filter by type, magnitude, catalog source
- Search by name or ID
- Set target and navigate to imaging
"""

import pygame
from typing import Optional, List
from .base_screen import BaseScreen
from .components import Button, ScrollableList, TextInput, Checkbox
from universe.space_object import SpaceObject, ObjectClass, ObjectSubtype


class CatalogScreen(BaseScreen):
    """
    Catalog Browser - Explore astronomical objects from Universe
    
    Shows all objects: stars, DSO, galaxies from all loaded catalogs.
    """
    
    def __init__(self, state_manager):
        super().__init__("CATALOGS")
        self.state_manager = state_manager
        
        # Get universe (single source of truth)
        self.universe = state_manager.get_universe()
        self.filtered_objects: List[SpaceObject] = []
        
        # Object type filter
        self.show_stars = False  # Stars disabled by default (too many)
        self.show_dso = True     # DSO enabled by default
        
        # Catalog source filter
        self.catalog_filter = "ALL"  # ALL, Messier, NGC, Hipparcos, Gaia
        self.selected_object: Optional[SpaceObject] = None
        
        # UI Components
        self.object_list = ScrollableList(20, 180, 400, 500, item_height=24)
        self.search_input = TextInput(20, 120, 300, placeholder="Search (e.g., M42, HIP 1234)")
        
        # Filter checkboxes
        self.filters = {
            'stars': Checkbox(450, 120, "Stars", checked=False),
            'galaxies': Checkbox(450, 150, "Galaxies", checked=True),
            'nebulae': Checkbox(450, 180, "Nebulae", checked=True),
            'clusters': Checkbox(450, 210, "Clusters", checked=True),
        }
        
        # Mag limit filter
        self.mag_limit = 10.0  # Start with bright objects
        
        # Buttons
        self.buttons = {
            'set_target': Button(450, 520, 180, 40, "SET AS TARGET",
                                callback=self.set_as_target),
            'go_imaging': Button(640, 520, 180, 40, "GO TO IMAGING",
                                callback=self.go_to_imaging),
            'clear_filters': Button(450, 250, 180, 35, "CLEAR FILTERS",
                                   callback=self.clear_filters),
            'mag_up': Button(600, 288, 30, 25, "+",
                            callback=self.mag_limit_up),
            'mag_down': Button(635, 288, 30, 25, "-",
                              callback=self.mag_limit_down),
            # Catalog source filter
            'cat_all': Button(450, 320, 70, 30, "ALL",
                             callback=lambda: self.set_catalog_filter("ALL")),
            'cat_m':   Button(530, 320, 90, 30, "MESSIER",
                             callback=lambda: self.set_catalog_filter("Messier")),
            'cat_ngc': Button(630, 320, 70, 30, "NGC",
                             callback=lambda: self.set_catalog_filter("NGC")),
            'cat_hip': Button(710, 320, 70, 30, "HIP",
                             callback=lambda: self.set_catalog_filter("Hipparcos")),
            'cat_gaia': Button(450, 355, 80, 30, "GAIA",
                              callback=lambda: self.set_catalog_filter("Gaia DR3")),
        }
        
        # Sort state
        self.sort_by = "mag"  # "mag", "name", "type", "dist"
        
        # Initial population
        self.update_filtered_list()
    
    def mag_limit_up(self):
        """Increase magnitude limit (fainter objects)"""
        self.mag_limit = min(15.0, self.mag_limit + 0.5)
        self.update_filtered_list()
    
    def set_catalog_filter(self, cat: str):
        """Filter by catalog (ALL, M, NGC)"""
        self.catalog_filter = cat
        self.update_filtered_list()
    
    def mag_limit_down(self):
        """Decrease magnitude limit (brighter objects only)"""
        self.mag_limit = max(4.0, self.mag_limit - 0.5)
        self.update_filtered_list()
    
    def clear_filters(self):
        """Clear all filters"""
        for checkbox in self.filters.values():
            checkbox.set_checked(True)
        self.search_input.clear()
        self.constellation_filter = ""
        self.mag_limit = 12.0
        self.update_filtered_list()
    
    def update_filtered_list(self):
        """Update filtered object list based on current filters"""
        search_term = self.search_input.get_text().lower()
        
        # Build type filter set
        type_filters = []
        if self.filters['galaxy'].is_checked():
            type_filters.extend([DSOType.SPIRAL, DSOType.ELLIPTICAL,
                               DSOType.IRREGULAR, DSOType.LENTICULAR])
        if self.filters['nebula'].is_checked():
            type_filters.extend([DSOType.HII_REGION, DSOType.REFLECTION,
                               DSOType.PLANETARY, DSOType.SNR, DSOType.DARK])
        if self.filters['cluster'].is_checked():
            type_filters.extend([DSOType.OPEN_CLUSTER, DSOType.GLOBULAR_CLUSTER])
        if self.filters['other'].is_checked():
            type_filters.extend([DSOType.GALAXY_CLUSTER, DSOType.QUASAR])
        
        # If no filters active, show all types
        show_all_types = len(type_filters) == 0
        
        # Filter objects
        self.filtered_objects = []
        for obj in self.catalog.objects.values():
            # Catalog filter (M / NGC / ALL)
            if self.catalog_filter == "M" and obj.catalog != "M":
                continue
            if self.catalog_filter == "NGC" and obj.catalog != "NGC":
                continue
            
            # Type filter (skip only if filters are active and type not selected)
            if not show_all_types and obj.dso_type not in type_filters:
                continue
            
            # Magnitude limit
            if obj.mag and obj.mag > self.mag_limit:
                continue
            
            # Constellation filter
            if self.constellation_filter:
                constellation = getattr(obj, 'constellation', '')
                if self.constellation_filter.lower() not in constellation.lower():
                    continue
            
            # Search filter
            if search_term:
                name_match = search_term in obj.name.lower()
                messier_match = obj.catalog == "M" and search_term in f"m{obj.catalog_num}".lower()
                constellation_match = self.constellation_filter == "" and \
                    search_term in getattr(obj, 'constellation', '').lower()
                if not (name_match or messier_match or constellation_match):
                    continue
            
            self.filtered_objects.append(obj)
        
        # Sort (default: by catalog number)
        if self.sort_by == "num" or self.sort_by is None:
            self.filtered_objects.sort(key=lambda o: o.catalog_num if o.catalog_num else 999)
        elif self.sort_by == "name":
            self.filtered_objects.sort(key=lambda o: o.name)
        elif self.sort_by == "mag":
            self.filtered_objects.sort(key=lambda o: o.mag if o.mag else 99)
        elif self.sort_by == "type":
            self.filtered_objects.sort(key=lambda o: o.dso_type.value)
        elif self.sort_by == "dist":
            self.filtered_objects.sort(key=lambda o: o.distance_ly if o.distance_ly else 0)
        
        # Update list display
        items = []
        for obj in self.filtered_objects:
            mag_str = f"{obj.mag:.1f}" if obj.mag else "N/A"
            # Show catalog prefix (M or NGC)
            if obj.catalog == "M":
                cat_str = f"M{obj.catalog_num}"
            else:
                cat_str = f"N{obj.catalog_num}"
            type_str = obj.dso_type.value if hasattr(obj.dso_type, 'value') else str(obj.dso_type)
            const_str = getattr(obj, 'constellation', '')[:10]
            items.append(f"{cat_str:6s} {obj.name[:21]:21s} {type_str[:8]:8s} {mag_str:>5s} {const_str:10s}")
        
        self.object_list.set_items(items)
        
        # Update selected
        if self.object_list.get_selected_index() >= 0:
            idx = self.object_list.get_selected_index()
            if idx < len(self.filtered_objects):
                self.selected_object = self.filtered_objects[idx]
    
    def set_as_target(self):
        """Set selected object as current target"""
        if self.selected_object is None:
            return
        
        # Update global state
        state = self.state_manager.get_state()
        state.selected_target = self.selected_object.name
        state.selected_target_ra = self.selected_object.ra_deg
        state.selected_target_dec = self.selected_object.dec_deg
        
        # Update Observatory Hub if it exists
        if 'OBSERVATORY' in self.state_manager.screens:
            obs_screen = self.state_manager.screens['OBSERVATORY']
            obs_screen.set_target(self.selected_object.name)
        
        print(f"Target set: {self.selected_object.name} (RA: {self.selected_object.ra_deg:.2f}°, Dec: {self.selected_object.dec_deg:.2f}°)")
    
    def go_to_imaging(self):
        """Set target and go to imaging screen"""
        self.set_as_target()
        self._next_screen = 'IMAGING'
    
    def on_enter(self):
        super().on_enter()
        self._next_screen = None
    
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
                
                # Sort keys
                elif event.key == pygame.K_F2:
                    self.sort_by = "num"
                    self.update_filtered_list()
                elif event.key == pygame.K_n:
                    self.sort_by = "name"
                    self.update_filtered_list()
                elif event.key == pygame.K_m:
                    self.sort_by = "mag"
                    self.update_filtered_list()
                elif event.key == pygame.K_t:
                    self.sort_by = "type"
                    self.update_filtered_list()
                elif event.key == pygame.K_d:
                    self.sort_by = "dist"
                    self.update_filtered_list()
                
                # Quick target
                elif event.key == pygame.K_RETURN:
                    if self.selected_object:
                        self.go_to_imaging()
            
            # Search input
            if self.search_input.handle_event(event):
                self.update_filtered_list()
            
            # List navigation
            old_idx = self.object_list.get_selected_index()
            if self.object_list.handle_event(event):
                new_idx = self.object_list.get_selected_index()
                if new_idx != old_idx and 0 <= new_idx < len(self.filtered_objects):
                    self.selected_object = self.filtered_objects[new_idx]
            
            # Checkboxes
            for checkbox in self.filters.values():
                if checkbox.handle_event(event):
                    self.update_filtered_list()
            
            # Buttons
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
        """Update catalog screen"""
        self.search_input.update(dt)
    
    def render(self, surface: pygame.Surface):
        """Render catalog browser"""
        W, H = surface.get_width(), surface.get_height()
        
        # Header
        header = pygame.Rect(10, 10, W - 20, 60)
        m_count = sum(1 for o in self.catalog.objects.values() if o.catalog == "M")
        ngc_count = sum(1 for o in self.catalog.objects.values() if o.catalog == "NGC")
        self.draw_header(surface, header,
                        "CATALOG BROWSER",
                        f"Messier: {m_count}  NGC: {ngc_count}  |  Showing: {len(self.filtered_objects)} objects")
        
        # Left panel - List and filters
        left_panel = pygame.Rect(10, 80, 430, H - 140)
        self.theme.draw_panel(surface, left_panel, "OBJECT LIST")
        
        # Search box
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           20, 95, "Search:", self.theme.colors.FG_PRIMARY)
        self.search_input.draw(surface)
        
        # Catalog filter buttons (ALL / MESSIER / NGC)
        for btn_name, button in [('cat_all', self.buttons['cat_all']),
                                  ('cat_m',   self.buttons['cat_m']),
                                  ('cat_ngc', self.buttons['cat_ngc'])]:
            # Highlight active
            active = (btn_name == 'cat_all' and self.catalog_filter == "ALL") or \
                     (btn_name == 'cat_m'   and self.catalog_filter == "M") or \
                     (btn_name == 'cat_ngc' and self.catalog_filter == "NGC")
            if active:
                hl = pygame.Rect(button.rect.x - 2, button.rect.y - 2,
                                 button.rect.width + 4, button.rect.height + 4)
                pygame.draw.rect(surface, self.theme.colors.ACCENT_CYAN, hl, 2)
            button.draw(surface)
        
        # Column headers
        sort_indicator = {"num":"#▼", "name":"N▼", "mag":"M▼", "type":"T▼", "dist":"D▼"}
        si = sort_indicator.get(self.sort_by, "")
        self.theme.draw_text(surface, self.theme.fonts.tiny(),
                           20, 160,
                           f"Cat#    Name                   Type     Mag  Const.   {si}",
                           self.theme.colors.FG_DIM)
        
        # Object list
        self.object_list.draw(surface)
        
        # Count
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           20, 690,
                           f"Showing {len(self.filtered_objects)} of {len(self.catalog.objects)} objects",
                           self.theme.colors.FG_DIM)
        
        # Right panel - Filters and info
        right_panel = pygame.Rect(450, 80, W - 460, H - 140)
        self.theme.draw_panel(surface, right_panel, "FILTERS & INFO")
        
        # Filters
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           460, 95, "OBJECT TYPES:", self.theme.colors.ACCENT_CYAN)
        
        for checkbox in self.filters.values():
            checkbox.draw(surface)
        
        # Magnitude limit
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           460, 260, "MAGNITUDE LIMIT:", self.theme.colors.ACCENT_CYAN)
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           460, 285, f"{self.mag_limit:.1f}", self.theme.colors.ACCENT_YELLOW)
        self.buttons['mag_up'].draw(surface)
        self.buttons['mag_down'].draw(surface)
        
        # Clear filters button
        self.buttons['clear_filters'].draw(surface)
        
        # Sort info
        y = 300
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           460, y, "SORT BY:", self.theme.colors.ACCENT_CYAN)
        y += 25
        sort_text = f"Current: {self.sort_by.upper()}"
        self.theme.draw_text(surface, self.theme.fonts.small(),
                           470, y, sort_text, self.theme.colors.FG_PRIMARY)
        y += 20
        self.theme.draw_text(surface, self.theme.fonts.tiny(),
                           470, y, "[N] Name  [M] Magnitude  [T] Type",
                           self.theme.colors.FG_DIM)
        
        # Selected object info
        y = 360
        self.theme.draw_text(surface, self.theme.fonts.normal(),
                           460, y, "SELECTED OBJECT:", self.theme.colors.ACCENT_CYAN)
        y += 30
        
        if self.selected_object:
            obj = self.selected_object
            
            # Name
            name = f"M{obj.catalog_num} - " if obj.catalog == "M" else ""
            name += obj.name
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               470, y, name, self.theme.colors.ACCENT_YELLOW)
            y += 25
            
            # Type
            type_str = obj.dso_type.value if hasattr(obj.dso_type, 'value') else str(obj.dso_type)
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               470, y, f"Type: {type_str}", self.theme.colors.FG_PRIMARY)
            y += 20
            
            # Magnitude
            mag_str = f"{obj.mag:.1f}" if obj.mag else "N/A"
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               470, y, f"Magnitude: {mag_str}", self.theme.colors.FG_PRIMARY)
            y += 20
            
            # Coordinates
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               470, y, f"RA: {obj.ra_deg:.2f}°", self.theme.colors.FG_PRIMARY)
            y += 18
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               470, y, f"Dec: {obj.dec_deg:.2f}°", self.theme.colors.FG_PRIMARY)
            y += 20
            
            # Size
            if obj.size_arcmin:
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   470, y, f"Size: {obj.size_arcmin:.1f}'", self.theme.colors.FG_PRIMARY)
                y += 20
            
            # Distance
            if obj.distance_ly:
                if obj.distance_ly >= 1_000_000:
                    dist_str = f"{obj.distance_ly/1_000_000:.1f} MLy"
                elif obj.distance_ly >= 1_000:
                    dist_str = f"{obj.distance_ly/1_000:.1f} kLy"
                else:
                    dist_str = f"{obj.distance_ly:.0f} Ly"
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   470, y, f"Distance: {dist_str}", self.theme.colors.FG_PRIMARY)
                y += 20
            
            # Constellation
            if hasattr(obj, 'constellation') and obj.constellation:
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   470, y, f"Constellation: {obj.constellation}", self.theme.colors.FG_PRIMARY)
                y += 20
            
            # Description (if available)
            if hasattr(obj, 'description') and obj.description:
                y += 10
                # Word wrap description
                words = obj.description.split()
                line = ""
                for word in words:
                    test_line = line + word + " "
                    if len(test_line) > 35:
                        self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                           470, y, line.strip(), self.theme.colors.FG_DIM)
                        y += 16
                        line = word + " "
                    else:
                        line = test_line
                if line:
                    self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                       470, y, line.strip(), self.theme.colors.FG_DIM)
        else:
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               470, y, "No object selected", self.theme.colors.FG_DIM)
        
        # Action buttons
        self.buttons['set_target'].draw(surface)
        self.buttons['go_imaging'].draw(surface)
        
        # Enable/disable buttons based on selection
        has_selection = self.selected_object is not None
        self.buttons['set_target'].set_enabled(has_selection)
        self.buttons['go_imaging'].set_enabled(has_selection)
        
        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                        "[F2]# [N]ame [M]ag [T]ype [D]ist  Sort  |  [+/-] Mag Limit  |  [ENTER] Imaging  [ESC] Back")
