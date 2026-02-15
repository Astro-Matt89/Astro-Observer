"""
Career/Missions Screen

View missions, progress, achievements, and statistics.
"""

import pygame
from typing import Optional
from .base_screen import BaseScreen
from .components import Button, ScrollableList


class CareerScreen(BaseScreen):
    """
    Career Screen - Missions, Achievements, and Stats
    
    View your progress, complete missions, and track achievements.
    """
    
    def __init__(self, state_manager):
        super().__init__("CAREER")
        self.state_manager = state_manager
        
        # UI state
        self.view_mode = "MISSIONS"  # MISSIONS, ACHIEVEMENTS, STATS
        
        # Lists
        self.mission_list = ScrollableList(20, 180, 480, 500, item_height=28)
        
        # Category buttons
        self.category_buttons = {
            'missions': Button(20, 120, 150, 35, "MISSIONS",
                              callback=lambda: self.set_view_mode("MISSIONS")),
            'achievements': Button(180, 120, 150, 35, "ACHIEVEMENTS",
                                  callback=lambda: self.set_view_mode("ACHIEVEMENTS")),
            'stats': Button(340, 120, 150, 35, "STATISTICS",
                           callback=lambda: self.set_view_mode("STATS")),
        }
        
        # Update data
        self.update_mission_list()
    
    def set_view_mode(self, mode: str):
        """Set view mode"""
        self.view_mode = mode
        if mode == "MISSIONS":
            self.update_mission_list()
    
    def update_mission_list(self):
        """Update mission list"""
        career = self.state_manager.get_career_mode()
        
        items = []
        for mission in career.missions.values():
            # Status icon
            if mission.status.value == "Completed":
                icon = "✓"
            elif mission.status.value == "Available":
                icon = "○"
            elif mission.status.value == "In Progress":
                icon = "◐"
            else:  # Locked
                icon = "🔒"
            
            # Mission summary
            reward_str = f"+{mission.reward_rp}RP"
            items.append(f"{icon} {mission.title[:35]:35s} {reward_str:>8s}")
        
        self.mission_list.set_items(items)
    
    def on_enter(self):
        super().on_enter()
        self.update_mission_list()
    
    def on_exit(self):
        super().on_exit()
    
    def handle_input(self, events: list[pygame.event.Event]) -> Optional[str]:
        mouse_pos = pygame.mouse.get_pos()
        
        # Update buttons
        for button in self.category_buttons.values():
            button.update(mouse_pos)
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return 'OBSERVATORY'
                
                # Quick switch
                elif event.key == pygame.K_1:
                    self.set_view_mode("MISSIONS")
                elif event.key == pygame.K_2:
                    self.set_view_mode("ACHIEVEMENTS")
                elif event.key == pygame.K_3:
                    self.set_view_mode("STATS")
            
            # Lists
            if self.view_mode == "MISSIONS":
                self.mission_list.handle_event(event)
            
            # Buttons
            for button in self.category_buttons.values():
                if button.handle_event(event):
                    break
        
        return None
    
    def update(self, dt: float):
        """Update career screen"""
        pass
    
    def render(self, surface: pygame.Surface):
        """Render career screen"""
        W, H = surface.get_width(), surface.get_height()
        career = self.state_manager.get_career_mode()
        
        # Header
        header = pygame.Rect(10, 10, W - 20, 60)
        self.draw_header(surface, header,
                        "CAREER & MISSIONS",
                        f"Research Points: {career.stats.research_points} RP | Total Earned: {career.stats.research_points_earned} RP")
        
        # Left panel - List
        left_panel = pygame.Rect(10, 80, 510, H - 140)
        self.theme.draw_panel(surface, left_panel, "MISSIONS & PROGRESS")
        
        # Category buttons
        for btn_name, button in self.category_buttons.items():
            # Highlight selected
            if (btn_name == 'missions' and self.view_mode == "MISSIONS") or \
               (btn_name == 'achievements' and self.view_mode == "ACHIEVEMENTS") or \
               (btn_name == 'stats' and self.view_mode == "STATS"):
                highlight = pygame.Rect(button.rect.x - 2, button.rect.y - 2,
                                       button.rect.width + 4, button.rect.height + 4)
                pygame.draw.rect(surface, self.theme.colors.ACCENT_CYAN, highlight, 2)
            
            button.draw(surface)
        
        # Content based on view mode
        if self.view_mode == "MISSIONS":
            # Mission list
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               20, 162,
                               "   Mission                                   Reward",
                               self.theme.colors.FG_DIM)
            self.mission_list.draw(surface)
        
        elif self.view_mode == "ACHIEVEMENTS":
            # Achievements
            y = 180
            unlocked_count = sum(1 for a in career.achievements.values() if a.unlocked)
            total_count = len(career.achievements)
            
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               20, y, f"Unlocked: {unlocked_count}/{total_count}",
                               self.theme.colors.ACCENT_YELLOW)
            y += 35
            
            for achievement in career.achievements.values():
                if y > left_panel.bottom - 50:
                    break
                
                color = self.theme.colors.ACCENT_YELLOW if achievement.unlocked else self.theme.colors.FG_DIM
                icon = achievement.icon if achievement.unlocked else "🔒"
                
                self.theme.draw_text(surface, self.theme.fonts.normal(),
                                   30, y, f"{icon} {achievement.title}",
                                   color)
                y += 25
                self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                   50, y, achievement.description,
                                   self.theme.colors.FG_DIM)
                y += 30
        
        elif self.view_mode == "STATS":
            # Statistics
            y = 180
            stats = career.stats
            
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               20, y, "IMAGING STATISTICS:", self.theme.colors.ACCENT_CYAN)
            y += 30
            
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               30, y, f"Total Exposures: {stats.total_exposures}",
                               self.theme.colors.FG_PRIMARY)
            y += 22
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               30, y, f"Total Integration: {stats.total_integration_time_s/60:.1f} minutes",
                               self.theme.colors.FG_PRIMARY)
            y += 22
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               30, y, f"Sessions: {stats.total_sessions}",
                               self.theme.colors.FG_PRIMARY)
            y += 35
            
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               20, y, "QUALITY:", self.theme.colors.ACCENT_CYAN)
            y += 30
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               30, y, f"Best SNR: {stats.best_snr:.2f}x",
                               self.theme.colors.FG_PRIMARY)
            y += 22
            if stats.best_snr_target:
                self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                   50, y, f"({stats.best_snr_target})",
                                   self.theme.colors.FG_DIM)
                y += 18
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               30, y, f"Average SNR: {stats.average_snr:.2f}x",
                               self.theme.colors.FG_PRIMARY)
            y += 35
            
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               20, y, "TARGETS:", self.theme.colors.ACCENT_CYAN)
            y += 30
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               30, y, f"Objects Imaged: {len(stats.objects_imaged)}",
                               self.theme.colors.FG_PRIMARY)
            y += 25
            
            for target in list(stats.objects_imaged)[:8]:
                if y > left_panel.bottom - 50:
                    break
                self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                   50, y, f"• {target}",
                                   self.theme.colors.FG_DIM)
                y += 18
        
        # Right panel - Details
        right_panel = pygame.Rect(530, 80, W - 540, H - 140)
        self.theme.draw_panel(surface, right_panel, "DETAILS")
        
        y = 110
        
        if self.view_mode == "MISSIONS":
            # Show selected mission details
            idx = self.mission_list.get_selected_index()
            missions_list = list(career.missions.values())
            
            if 0 <= idx < len(missions_list):
                mission = missions_list[idx]
                
                # Title
                self.theme.draw_text(surface, self.theme.fonts.normal(),
                                   540, y, mission.title,
                                   self.theme.colors.ACCENT_YELLOW)
                y += 30
                
                # Status
                status_color = self.theme.colors.SUCCESS if mission.status.value == "Completed" else \
                              self.theme.colors.WARNING if mission.status.value == "Locked" else \
                              self.theme.colors.FG_PRIMARY
                
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   550, y, f"Status: {mission.status.value}",
                                   status_color)
                y += 25
                
                # Description (word wrap)
                words = mission.description.split()
                line = ""
                for word in words:
                    test_line = line + word + " "
                    if len(test_line) > 45:
                        self.theme.draw_text(surface, self.theme.fonts.small(),
                                           550, y, line.strip(),
                                           self.theme.colors.FG_PRIMARY)
                        y += 20
                        line = word + " "
                    else:
                        line = test_line
                if line:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       550, y, line.strip(),
                                       self.theme.colors.FG_PRIMARY)
                    y += 30
                
                # Requirements
                if mission.required_target:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       550, y, f"Target: {mission.required_target}",
                                       self.theme.colors.FG_DIM)
                    y += 20
                
                if mission.required_snr:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       550, y, f"Min SNR: {mission.required_snr:.1f}x",
                                       self.theme.colors.FG_DIM)
                    y += 20
                
                if mission.required_exposure_s:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       550, y, f"Total Exposure: {mission.required_exposure_s/60:.1f} min",
                                       self.theme.colors.FG_DIM)
                    y += 20
                
                if mission.required_count > 1:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       550, y, f"Count: {mission.progress}/{mission.required_count}",
                                       self.theme.colors.FG_DIM)
                    y += 20
                
                y += 15
                
                # Rewards
                self.theme.draw_text(surface, self.theme.fonts.normal(),
                                   540, y, "REWARDS:", self.theme.colors.ACCENT_CYAN)
                y += 25
                
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   550, y, f"• {mission.reward_rp} Research Points",
                                   self.theme.colors.ACCENT_YELLOW)
                y += 20
                
                if mission.reward_unlock:
                    self.theme.draw_text(surface, self.theme.fonts.small(),
                                       550, y, f"• Unlocks: {mission.reward_unlock}",
                                       self.theme.colors.ACCENT_YELLOW)
                    y += 20
                
                # Prerequisites
                if mission.requires_mission:
                    prereq = career.missions.get(mission.requires_mission)
                    if prereq:
                        y += 20
                        self.theme.draw_text(surface, self.theme.fonts.tiny(),
                                           550, y, f"Requires: {prereq.title}",
                                           self.theme.colors.FG_DIM)
        
        elif self.view_mode == "ACHIEVEMENTS":
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               540, y, "ACHIEVEMENTS",
                               self.theme.colors.ACCENT_CYAN)
            y += 30
            
            unlocked = [a for a in career.achievements.values() if a.unlocked]
            if unlocked:
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   550, y, f"You've unlocked {len(unlocked)} achievements!",
                                   self.theme.colors.FG_PRIMARY)
            else:
                self.theme.draw_text(surface, self.theme.fonts.small(),
                                   550, y, "Complete missions to unlock achievements!",
                                   self.theme.colors.FG_DIM)
        
        elif self.view_mode == "STATS":
            self.theme.draw_text(surface, self.theme.fonts.normal(),
                               540, y, "YOUR PROGRESS",
                               self.theme.colors.ACCENT_CYAN)
            y += 30
            
            # Research points breakdown
            self.theme.draw_text(surface, self.theme.fonts.small(),
                               550, y, "Research Points:",
                               self.theme.colors.FG_PRIMARY)
            y += 22
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               560, y, f"Current: {stats.research_points} RP",
                               self.theme.colors.FG_DIM)
            y += 18
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               560, y, f"Earned: {stats.research_points_earned} RP",
                               self.theme.colors.FG_DIM)
            y += 18
            self.theme.draw_text(surface, self.theme.fonts.tiny(),
                               560, y, f"Spent: {stats.research_points_spent} RP",
                               self.theme.colors.FG_DIM)
        
        # Footer
        footer = pygame.Rect(10, H - 50, W - 20, 40)
        self.draw_footer(surface, footer,
                        "[1] Missions  [2] Achievements  [3] Stats  [ESC] Back")
