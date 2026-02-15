"""
Career Mode System

Complete progression system with:
- Research Points (RP) earning and spending
- Equipment unlocking
- Missions and objectives
- Statistics tracking
- Achievements
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime
import json


class MissionType(Enum):
    """Types of missions"""
    IMAGE_TARGET = "Image a specific target"
    ACHIEVE_SNR = "Achieve minimum SNR"
    TOTAL_EXPOSURE = "Total integration time"
    USE_FILTER = "Image with specific filter"
    USE_EQUIPMENT = "Use specific equipment"
    IMAGE_MULTIPLE = "Image multiple targets"


class MissionStatus(Enum):
    """Mission status"""
    LOCKED = "Locked"
    AVAILABLE = "Available"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


@dataclass
class Mission:
    """Single mission/objective"""
    id: str
    title: str
    description: str
    mission_type: MissionType
    
    # Requirements
    required_target: Optional[str] = None
    required_snr: Optional[float] = None
    required_exposure_s: Optional[float] = None
    required_filter: Optional[str] = None
    required_equipment: Optional[str] = None
    required_count: int = 1
    
    # Rewards
    reward_rp: int = 100
    reward_unlock: Optional[str] = None  # Equipment ID to unlock
    
    # Status
    status: MissionStatus = MissionStatus.AVAILABLE
    progress: int = 0
    completed_date: Optional[datetime] = None
    
    # Prerequisites
    requires_mission: Optional[str] = None  # Must complete this mission first
    
    def check_completion(self, stats: 'CareerStats') -> bool:
        """
        Check if mission is completed based on stats
        
        Args:
            stats: Career statistics
            
        Returns:
            True if mission completed
        """
        if self.status == MissionStatus.COMPLETED:
            return True
        
        if self.mission_type == MissionType.IMAGE_TARGET:
            if self.required_target in stats.objects_imaged:
                self.progress = 1
                return self.progress >= self.required_count
        
        elif self.mission_type == MissionType.ACHIEVE_SNR:
            if stats.best_snr >= self.required_snr:
                self.progress = 1
                return True
        
        elif self.mission_type == MissionType.TOTAL_EXPOSURE:
            self.progress = int(stats.total_integration_time_s)
            return stats.total_integration_time_s >= self.required_exposure_s
        
        elif self.mission_type == MissionType.IMAGE_MULTIPLE:
            self.progress = len(stats.objects_imaged)
            return len(stats.objects_imaged) >= self.required_count
        
        return False
    
    def complete(self):
        """Mark mission as completed"""
        self.status = MissionStatus.COMPLETED
        self.completed_date = datetime.now()


@dataclass
class Achievement:
    """Achievement/badge"""
    id: str
    title: str
    description: str
    icon: str  # Emoji or symbol
    unlocked: bool = False
    unlock_date: Optional[datetime] = None


@dataclass
class CareerStats:
    """Career mode statistics"""
    # Imaging stats
    total_exposures: int = 0
    total_integration_time_s: float = 0.0
    total_sessions: int = 0
    
    # Targets
    objects_imaged: set = field(default_factory=set)
    favorite_target: Optional[str] = None
    
    # Quality
    best_snr: float = 0.0
    best_snr_target: Optional[str] = None
    average_snr: float = 0.0
    
    # Equipment usage
    telescopes_used: set = field(default_factory=set)
    cameras_used: set = field(default_factory=set)
    filters_used: set = field(default_factory=set)
    
    # Progression
    research_points: int = 0
    research_points_earned: int = 0
    research_points_spent: int = 0
    
    # Time
    total_play_time_s: float = 0.0
    first_session_date: Optional[datetime] = None
    last_session_date: Optional[datetime] = None
    
    def update_after_imaging(self, target: str, snr: float, 
                            exposure_time_s: float, num_frames: int,
                            telescope_id: str, camera_id: str, filter_id: str):
        """
        Update stats after imaging session
        
        Args:
            target: Target name
            snr: Achieved SNR
            exposure_time_s: Single frame exposure
            num_frames: Number of frames
            telescope_id, camera_id, filter_id: Equipment used
        """
        # Update counts
        self.total_exposures += num_frames
        self.total_integration_time_s += exposure_time_s * num_frames
        self.total_sessions += 1
        
        # Update targets
        self.objects_imaged.add(target)
        
        # Update quality
        if snr > self.best_snr:
            self.best_snr = snr
            self.best_snr_target = target
        
        # Update average SNR (simple moving average)
        self.average_snr = (self.average_snr * (self.total_sessions - 1) + snr) / self.total_sessions
        
        # Update equipment usage
        self.telescopes_used.add(telescope_id)
        self.cameras_used.add(camera_id)
        self.filters_used.add(filter_id)
        
        # Update dates
        now = datetime.now()
        if self.first_session_date is None:
            self.first_session_date = now
        self.last_session_date = now
    
    def calculate_rp_reward(self, snr: float, exposure_time_s: float, 
                           num_frames: int, is_new_target: bool) -> int:
        """
        Calculate RP reward for imaging session
        
        Args:
            snr: Achieved SNR
            exposure_time_s: Exposure time per frame
            num_frames: Number of frames
            is_new_target: True if this is a new target
            
        Returns:
            RP reward amount
        """
        # Base reward
        base_rp = 10
        
        # SNR bonus (exponential)
        snr_bonus = int(snr ** 1.5 * 5)
        
        # Frame count bonus
        frame_bonus = num_frames * 2
        
        # Exposure bonus
        exposure_bonus = int(exposure_time_s / 10)
        
        # New target bonus
        new_target_bonus = 50 if is_new_target else 0
        
        total_rp = base_rp + snr_bonus + frame_bonus + exposure_bonus + new_target_bonus
        
        return max(total_rp, 10)  # Minimum 10 RP


class CareerMode:
    """
    Career mode manager
    
    Manages progression, missions, achievements, and unlocks.
    """
    
    def __init__(self):
        """Initialize career mode"""
        self.stats = CareerStats()
        self.missions: Dict[str, Mission] = {}
        self.achievements: Dict[str, Achievement] = {}
        self.unlocked_equipment: set = set()
        
        # Initialize starter equipment (tier 1)
        self.unlocked_equipment.add("WEBCAM_LENS")
        self.unlocked_equipment.add("REF_80_F5")
        self.unlocked_equipment.add("NEWT_114_F4")
        self.unlocked_equipment.add("WEBCAM_MOD")
        self.unlocked_equipment.add("L")
        self.unlocked_equipment.add("R")
        self.unlocked_equipment.add("G")
        self.unlocked_equipment.add("B")
        
        # Create missions
        self._create_missions()
        
        # Create achievements
        self._create_achievements()
    
    def _create_missions(self):
        """Create mission list"""
        # Tutorial missions
        self.missions["MISSION_001"] = Mission(
            id="MISSION_001",
            title="First Light",
            description="Acquire your first image of any target",
            mission_type=MissionType.IMAGE_TARGET,
            required_count=1,
            reward_rp=50,
            status=MissionStatus.AVAILABLE
        )
        
        self.missions["MISSION_002"] = Mission(
            id="MISSION_002",
            title="Quality Matters",
            description="Achieve SNR of 3.0 or better",
            mission_type=MissionType.ACHIEVE_SNR,
            required_snr=3.0,
            reward_rp=100,
            reward_unlock="NEWT_150_F5",
            requires_mission="MISSION_001"
        )
        
        self.missions["MISSION_003"] = Mission(
            id="MISSION_003",
            title="The Great Nebula",
            description="Image M42 (Orion Nebula)",
            mission_type=MissionType.IMAGE_TARGET,
            required_target="Orion Nebula",
            reward_rp=150,
            requires_mission="MISSION_001"
        )
        
        # Intermediate missions
        self.missions["MISSION_004"] = Mission(
            id="MISSION_004",
            title="Patience is Key",
            description="Accumulate 5 minutes of total integration time",
            mission_type=MissionType.TOTAL_EXPOSURE,
            required_exposure_s=300,
            reward_rp=200,
            reward_unlock="ZWO_ASI294MC",
            requires_mission="MISSION_002"
        )
        
        self.missions["MISSION_005"] = Mission(
            id="MISSION_005",
            title="Galaxy Hunter",
            description="Image a spiral galaxy (M31 or M51)",
            mission_type=MissionType.IMAGE_TARGET,
            required_target="Andromeda Galaxy",  # Can be either M31 or M51
            reward_rp=250,
            reward_unlock="SCT_6_F10",
            requires_mission="MISSION_003"
        )
        
        # Advanced missions
        self.missions["MISSION_006"] = Mission(
            id="MISSION_006",
            title="Master Observer",
            description="Image 3 different targets",
            mission_type=MissionType.IMAGE_MULTIPLE,
            required_count=3,
            reward_rp=300,
            reward_unlock="HA",
            requires_mission="MISSION_005"
        )
        
        self.missions["MISSION_007"] = Mission(
            id="MISSION_007",
            title="Professional Quality",
            description="Achieve SNR of 5.0 or better",
            mission_type=MissionType.ACHIEVE_SNR,
            required_snr=5.0,
            reward_rp=500,
            reward_unlock="RC_10_F8",
            requires_mission="MISSION_006"
        )
        
        # Update mission availability based on prerequisites
        self._update_mission_availability()
    
    def _create_achievements(self):
        """Create achievements list"""
        self.achievements["ACH_FIRST_IMAGE"] = Achievement(
            id="ACH_FIRST_IMAGE",
            title="First Light",
            description="Acquire your first image",
            icon="🌟"
        )
        
        self.achievements["ACH_10_IMAGES"] = Achievement(
            id="ACH_10_IMAGES",
            title="Observer",
            description="Acquire 10 images",
            icon="🔭"
        )
        
        self.achievements["ACH_100_IMAGES"] = Achievement(
            id="ACH_100_IMAGES",
            title="Veteran Observer",
            description="Acquire 100 images",
            icon="🏆"
        )
        
        self.achievements["ACH_5_TARGETS"] = Achievement(
            id="ACH_5_TARGETS",
            title="Sky Explorer",
            description="Image 5 different targets",
            icon="🌌"
        )
        
        self.achievements["ACH_SNR_10"] = Achievement(
            id="ACH_SNR_10",
            title="Image Master",
            description="Achieve SNR of 10.0",
            icon="✨"
        )
        
        self.achievements["ACH_1000_RP"] = Achievement(
            id="ACH_1000_RP",
            title="Research Pioneer",
            description="Earn 1000 total RP",
            icon="🎓"
        )
    
    def _update_mission_availability(self):
        """Update which missions are available based on prerequisites"""
        for mission in self.missions.values():
            if mission.status == MissionStatus.COMPLETED:
                continue
            
            # Check if prerequisite mission is completed
            if mission.requires_mission:
                prereq = self.missions.get(mission.requires_mission)
                if prereq and prereq.status == MissionStatus.COMPLETED:
                    mission.status = MissionStatus.AVAILABLE
                else:
                    mission.status = MissionStatus.LOCKED
            else:
                mission.status = MissionStatus.AVAILABLE
    
    def complete_imaging_session(self, target: str, snr: float, 
                                 exposure_time_s: float, num_frames: int,
                                 telescope_id: str, camera_id: str, filter_id: str):
        """
        Complete imaging session and award RP
        
        Args:
            target: Target name
            snr: Achieved SNR
            exposure_time_s: Exposure per frame
            num_frames: Number of frames
            telescope_id, camera_id, filter_id: Equipment used
            
        Returns:
            RP reward amount
        """
        # Check if new target
        is_new_target = target not in self.stats.objects_imaged
        
        # Calculate RP reward
        rp_reward = self.stats.calculate_rp_reward(snr, exposure_time_s, 
                                                   num_frames, is_new_target)
        
        # Update stats
        self.stats.update_after_imaging(target, snr, exposure_time_s, num_frames,
                                       telescope_id, camera_id, filter_id)
        
        # Award RP
        self.stats.research_points += rp_reward
        self.stats.research_points_earned += rp_reward
        
        # Check missions
        self._check_missions()
        
        # Check achievements
        self._check_achievements()
        
        return rp_reward
    
    def _check_missions(self):
        """Check and complete missions"""
        for mission in self.missions.values():
            if mission.status in [MissionStatus.AVAILABLE, MissionStatus.IN_PROGRESS]:
                if mission.check_completion(self.stats):
                    self._complete_mission(mission)
        
        # Update availability
        self._update_mission_availability()
    
    def _complete_mission(self, mission: Mission):
        """
        Complete a mission and award rewards
        
        Args:
            mission: Mission to complete
        """
        mission.complete()
        
        # Award RP
        self.stats.research_points += mission.reward_rp
        self.stats.research_points_earned += mission.reward_rp
        
        # Unlock equipment
        if mission.reward_unlock:
            self.unlocked_equipment.add(mission.reward_unlock)
        
        print(f"Mission completed: {mission.title} (+{mission.reward_rp} RP)")
        if mission.reward_unlock:
            print(f"Unlocked: {mission.reward_unlock}")
    
    def _check_achievements(self):
        """Check and unlock achievements"""
        # First image
        if self.stats.total_exposures >= 1 and not self.achievements["ACH_FIRST_IMAGE"].unlocked:
            self._unlock_achievement("ACH_FIRST_IMAGE")
        
        # 10 images
        if self.stats.total_exposures >= 10 and not self.achievements["ACH_10_IMAGES"].unlocked:
            self._unlock_achievement("ACH_10_IMAGES")
        
        # 100 images
        if self.stats.total_exposures >= 100 and not self.achievements["ACH_100_IMAGES"].unlocked:
            self._unlock_achievement("ACH_100_IMAGES")
        
        # 5 targets
        if len(self.stats.objects_imaged) >= 5 and not self.achievements["ACH_5_TARGETS"].unlocked:
            self._unlock_achievement("ACH_5_TARGETS")
        
        # SNR 10
        if self.stats.best_snr >= 10.0 and not self.achievements["ACH_SNR_10"].unlocked:
            self._unlock_achievement("ACH_SNR_10")
        
        # 1000 RP
        if self.stats.research_points_earned >= 1000 and not self.achievements["ACH_1000_RP"].unlocked:
            self._unlock_achievement("ACH_1000_RP")
    
    def _unlock_achievement(self, achievement_id: str):
        """Unlock an achievement"""
        achievement = self.achievements.get(achievement_id)
        if achievement:
            achievement.unlocked = True
            achievement.unlock_date = datetime.now()
            print(f"Achievement unlocked: {achievement.icon} {achievement.title}")
    
    def can_afford(self, price_rp: int) -> bool:
        """Check if player can afford something"""
        return self.stats.research_points >= price_rp
    
    def purchase_equipment(self, equipment_id: str, price_rp: int) -> bool:
        """
        Purchase equipment
        
        Args:
            equipment_id: Equipment to unlock
            price_rp: Cost in RP
            
        Returns:
            True if purchased successfully
        """
        if not self.can_afford(price_rp):
            return False
        
        self.stats.research_points -= price_rp
        self.stats.research_points_spent += price_rp
        self.unlocked_equipment.add(equipment_id)
        
        return True
    
    def is_unlocked(self, equipment_id: str) -> bool:
        """Check if equipment is unlocked"""
        return equipment_id in self.unlocked_equipment
    
    def save_to_file(self, filepath: str):
        """Save career state to file"""
        data = {
            'stats': {
                'total_exposures': self.stats.total_exposures,
                'total_integration_time_s': self.stats.total_integration_time_s,
                'total_sessions': self.stats.total_sessions,
                'objects_imaged': list(self.stats.objects_imaged),
                'best_snr': self.stats.best_snr,
                'best_snr_target': self.stats.best_snr_target,
                'average_snr': self.stats.average_snr,
                'research_points': self.stats.research_points,
                'research_points_earned': self.stats.research_points_earned,
                'research_points_spent': self.stats.research_points_spent,
            },
            'unlocked_equipment': list(self.unlocked_equipment),
            'missions': {
                mid: {
                    'status': mission.status.value,
                    'progress': mission.progress,
                    'completed_date': mission.completed_date.isoformat() if mission.completed_date else None
                }
                for mid, mission in self.missions.items()
            },
            'achievements': {
                aid: {
                    'unlocked': achievement.unlocked,
                    'unlock_date': achievement.unlock_date.isoformat() if achievement.unlock_date else None
                }
                for aid, achievement in self.achievements.items()
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_file(self, filepath: str) -> bool:
        """
        Load career state from file
        
        Returns:
            True if loaded successfully
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Load stats
            stats_data = data['stats']
            self.stats.total_exposures = stats_data['total_exposures']
            self.stats.total_integration_time_s = stats_data['total_integration_time_s']
            self.stats.total_sessions = stats_data['total_sessions']
            self.stats.objects_imaged = set(stats_data['objects_imaged'])
            self.stats.best_snr = stats_data['best_snr']
            self.stats.best_snr_target = stats_data.get('best_snr_target')
            self.stats.average_snr = stats_data['average_snr']
            self.stats.research_points = stats_data['research_points']
            self.stats.research_points_earned = stats_data['research_points_earned']
            self.stats.research_points_spent = stats_data['research_points_spent']
            
            # Load unlocked equipment
            self.unlocked_equipment = set(data['unlocked_equipment'])
            
            # Load missions
            for mid, mission_data in data['missions'].items():
                if mid in self.missions:
                    mission = self.missions[mid]
                    mission.status = MissionStatus(mission_data['status'])
                    mission.progress = mission_data['progress']
                    if mission_data['completed_date']:
                        mission.completed_date = datetime.fromisoformat(mission_data['completed_date'])
            
            # Load achievements
            for aid, ach_data in data['achievements'].items():
                if aid in self.achievements:
                    achievement = self.achievements[aid]
                    achievement.unlocked = ach_data['unlocked']
                    if ach_data['unlock_date']:
                        achievement.unlock_date = datetime.fromisoformat(ach_data['unlock_date'])
            
            return True
        
        except Exception as e:
            print(f"Failed to load career save: {e}")
            return False
