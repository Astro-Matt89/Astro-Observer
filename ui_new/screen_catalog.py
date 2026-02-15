"""
Catalog Browser Screen - Universe Edition

Browse all 389k+ astronomical objects from loaded catalogs:
- Stars: Yale BSC, Hipparcos, Gaia DR3  
- DSO: Messier, NGC
- Filter by type, magnitude, catalog
- Search by name or ID
"""

import pygame
from typing import Optional, List
from .base_screen import BaseScreen
from .components import Button, ScrollableList, TextInput, Checkbox
from universe.space_object import SpaceObject, ObjectClass


class CatalogScreen(BaseScreen):
    """Catalog Browser - Explore all Universe objects"""
    
    def __init__(self, state_manager):
        super().__init__("CATALOGS")
        self.state_manager = state_manager
        self.universe = state_manager.get_universe()
        
        self.filtered_objects: List[SpaceObject] = []
        self.selected_object: Optional[SpaceObject] = None
        
        # Filters
        self.show_stars = False  # Off by default (too many)
        self.show_dso = True
        self.catalog_filter = "ALL"
        self.mag_limit = 10.0
        
        # UI
        self.object_list = ScrollableList(20, 220, 450, 460, item_height=22)
        self.search_input = TextInput(20, 170, 450, placeholder="Search: M42, Sirius, HIP 32349...")
        
        self.filters = {
            'stars': Checkbox(500, 170, "Stars", checked=False),
            'galaxies': Checkbox(500, 200, "Galaxies", checked=True),
            'nebulae': Checkbox(500, 230, "Nebulae", checked=True),
            'clusters': Checkbox(500, 260, "Clusters", checked=True),
        }
        
        self.buttons = {
            'set_target': Button(500, 600, 150, 40, "SET TARGET", callback=self.set_as_target),
            'go_imaging': Button(660, 600, 150, 40, "IMAGING", callback=self.go_to_imaging),
            'clear': Button(500, 300, 150, 30, "CLEAR FILTERS", callback=self.clear_filters),
            
            # Mag buttons
            'mag_up': Button(660, 300, 50, 30, "MAG+", callback=self.mag_limit_up),
            'mag_down': Button(720, 300, 50, 30, "MAG-", callback=self.mag_limit_down),
            
            # Catalog filters
            'cat_all': Button(500, 350, 60, 28, "ALL", callback=lambda: self.set_catalog("ALL")),
            'cat_m': Button(570, 350, 90, 28, "MESSIER", callback=lambda: self.set_catalog("Messier")),
            'cat_ngc': Button(670, 350, 60, 28, "NGC", callback=lambda: self.set_catalog("NGC")),
            'cat_hip': Button(740, 350, 70, 28, "HIP", callback=lambda: self.set_catalog("Hipparcos")),
            'cat_gaia': Button(500, 385, 70, 28, "GAIA", callback=lambda: self.set_catalog("Gaia DR3")),
        }
        
        self.update_filtered_list()
    
    def set_catalog(self, cat: str):
        self.catalog_filter = cat
        self.update_filtered_list()
    
    def clear_filters(self):
        for cb in self.filters.values():
            cb.set_checked(True)
        self.filters['stars'].set_checked(False)
        self.search_input.clear()
        self.mag_limit = 10.0
        self.catalog_filter = "ALL"
        self.update_filtered_list()
    
    def mag_limit_up(self):
        self.mag_limit = min(15.0, self.mag_limit + 1.0)
        self.update_filtered_list()
    
    def mag_limit_down(self):
        self.mag_limit = max(1.0, self.mag_limit - 1.0)
        self.update_filtered_list()
    
    def update_filtered_list(self):
        """Filter objects from Universe"""
        search = self.search_input.get_text().lower()
        
        # Collect objects
        all_objs = []
        if self.filters['stars'].is_checked():
            all_objs.extend(self.universe.get_stars())
        if any([self.filters['galaxies'].is_checked(),
                self.filters['nebulae'].is_checked(),
                self.filters['clusters'].is_checked()]):
            all_objs.extend(self.universe.get_dso())
        
        self.filtered_objects = []
        for obj in all_objs:
            # Mag limit
            if obj.mag > self.mag_limit:
                continue
            
            # Type filter
            if obj.obj_class == ObjectClass.STAR and not self.filters['stars'].is_checked():
                continue
            if obj.obj_class == ObjectClass.GALAXY and not self.filters['galaxies'].is_checked():
                continue
            if obj.obj_class == ObjectClass.NEBULA and not self.filters['nebulae'].is_checked():
                continue
            if obj.obj_class == ObjectClass.CLUSTER and not self.filters['clusters'].is_checked():
                continue
            
            # Catalog filter
            if self.catalog_filter != "ALL":
                if self.catalog_filter == "Messier" and not obj.uid.startswith("M"):
                    continue
                if self.catalog_filter == "NGC" and not obj.uid.startswith("NGC"):
                    continue
                if self.catalog_filter == "Hipparcos":
                    if "HIP" not in obj.meta.get("cross_ref", {}):
                        continue
                if self.catalog_filter == "Gaia DR3":
                    if "Gaia" not in obj.meta.get("cross_ref", {}):
                        continue
            
            # Search
            if search:
                searchable = f"{obj.name} {obj.uid}".lower()
                if "cross_ref" in obj.meta:
                    for k, v in obj.meta["cross_ref"].items():
                        searchable += f" {k} {v}"
                if search not in searchable:
                    continue
            
            self.filtered_objects.append(obj)
        
        # Sort by magnitude (brightest first)
        self.filtered_objects.sort(key=lambda o: o.mag)
        
        # Limit to 10000 for performance
        if len(self.filtered_objects) > 10000:
            self.filtered_objects = self.filtered_objects[:10000]
        
        # Update list items
        items = []
        for obj in self.filtered_objects:
            # Format: "M42  Orion Nebula  mag 4.0  2500ly"
            name = obj.name[:25].ljust(25)
            mag_str = f"mag {obj.mag:4.1f}"
            dist_str = f"{obj.distance_ly:6.0f}ly" if obj.distance_ly < 1e6 else ">1Mly"
            items.append(f"{obj.uid:12s} {name} {mag_str} {dist_str}")
        
        self.object_list.set_items(items)
    
    def set_as_target(self):
        if self.selected_object:
            state = self.state_manager.get_state()
            state.selected_target = self.selected_object.name
            state.selected_target_ra = self.selected_object.ra_deg
            state.selected_target_dec = self.selected_object.dec_deg
    
    def go_to_imaging(self):
        self.set_as_target()
        self._next_screen = "IMAGING"
    
    def on_enter(self):
        super().on_enter()
        self._next_screen = None
        self.update_filtered_list()
    
    def on_exit(self):
        super().on_exit()
    
    def update(self, dt: float):
        pass
    
    def handle_input(self, events) -> Optional[str]:
        mp = pygame.mouse.get_pos()
        for btn in self.buttons.values():
            btn.update(mp)
        
        for event in events:
            # Buttons — check after each, return pending screen
            for btn in self.buttons.values():
                if btn.handle_event(event):
                    if hasattr(self, '_next_screen') and self._next_screen:
                        ns = self._next_screen
                        self._next_screen = None
                        return ns
                    return None
            
            # Checkboxes
            changed = False
            for cb in self.filters.values():
                if cb.handle_event(event):
                    changed = True
            if changed:
                self.update_filtered_list()
                return None
            
            # Search input
            self.search_input.handle_event(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                self.update_filtered_list()
            
            # List mousewheel scroll
            if event.type == pygame.MOUSEWHEEL:
                if self.object_list.rect.collidepoint(mp):
                    self.object_list.scroll_offset = max(0,
                        self.object_list.scroll_offset - event.y)
            
            # List click selection
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.object_list.handle_event(event):
                    idx = self.object_list.selected_index
                    if 0 <= idx < len(self.filtered_objects):
                        self.selected_object = self.filtered_objects[idx]
            
            # ESC → back
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "OBSERVATORY"
        
        return None
    
    def render(self, surface: pygame.Surface):
        W, H = surface.get_width(), surface.get_height()
        surface.fill((8, 12, 20))
        
        # Title
        font_title = pygame.font.SysFont('monospace', 24, bold=True)
        title = font_title.render("CATALOG BROWSER", True, (0, 220, 100))
        surface.blit(title, (W//2 - title.get_width()//2, 30))
        
        # Stats
        font = pygame.font.SysFont('monospace', 12)
        total = len(self.filtered_objects)
        if total > 10000:
            stats = f"Showing 10,000 of {total:,} objects (mag<{self.mag_limit:.1f}) — increase mag or search"
        else:
            stats = f"Showing {total:,} objects (mag<{self.mag_limit:.1f})"
        surface.blit(font.render(stats, True, (0, 180, 80)), (20, 140))
        
        # Search input
        font_sm = pygame.font.SysFont('monospace', 11)
        surface.blit(font_sm.render("SEARCH:", True, (0, 150, 70)), (20, 150))
        self.search_input.draw(surface)
        
        # Object list
        self.object_list.draw(surface)
        
        # Selected object info
        if self.selected_object:
            obj = self.selected_object
            y = 500
            pygame.draw.rect(surface, (0, 30, 15), (500, y, 310, 90))
            
            font_b = pygame.font.SysFont('monospace', 13, bold=True)
            surface.blit(font_b.render(obj.name[:30], True, (0, 220, 100)), (510, y+10))
            
            info = [
                f"UID: {obj.uid}",
                f"Type: {obj.obj_class.value.title()}",
                f"Mag: {obj.mag:.2f}  Dist: {obj.distance_ly:.0f} ly",
                f"RA: {obj.ra_deg:.2f}°  Dec: {obj.dec_deg:+.2f}°",
            ]
            
            # Show cross-refs if available
            if "cross_ref" in obj.meta:
                xref = obj.meta["cross_ref"]
                xref_str = "  ".join([f"{k}:{v}" for k, v in list(xref.items())[:3]])
                info.append(f"IDs: {xref_str[:40]}")
            
            for i, line in enumerate(info):
                surface.blit(font_sm.render(line, True, (0, 180, 80)), (510, y+30+i*14))
        
        # Filters
        font_label = pygame.font.SysFont('monospace', 11, bold=True)
        surface.blit(font_label.render("OBJECT TYPES:", True, (0, 150, 70)), (500, 150))
        for cb in self.filters.values():
            cb.draw(surface)
        
        surface.blit(font_label.render(f"MAG LIMIT: {self.mag_limit:.1f}", True, (0, 150, 70)), (660, 280))
        
        surface.blit(font_label.render("CATALOG SOURCE:", True, (0, 150, 70)), (500, 330))
        
        # Active catalog indicator
        cat_labels = {
            "ALL": (500, 350), "Messier": (570, 350), "NGC": (670, 350),
            "Hipparcos": (740, 350), "Gaia DR3": (500, 385)
        }
        if self.catalog_filter in cat_labels:
            x, y = cat_labels[self.catalog_filter]
            pygame.draw.rect(surface, (0, 100, 50), (x-2, y-2, 64, 32), 2)
        
        # Buttons
        for btn in self.buttons.values():
            btn.draw(surface)
        
        # Help text
        help_text = "ESC: Back  |  Click: Select  |  Scroll: Navigate"
        surface.blit(font_sm.render(help_text, True, (0, 100, 50)), (20, H-25))
