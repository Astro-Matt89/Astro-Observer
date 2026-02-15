"""
Procedural Universe with Level-of-Detail (LOD)

Space Engine-style hierarchical generation:
- Objects generate on-demand based on observer distance
- Multiple LOD levels: Galaxy clusters → Galaxies → Stars → Planets → Surface
- Deterministic: same seed always produces same universe
- Memory efficient: only active LOD levels are in RAM

Architecture:
  ProceduralZone: spatial region that generates objects when entered
  LODManager: decides which zones to load/unload based on camera
  Generator: creates objects with deterministic seed
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set
from enum import IntEnum

from universe.space_object import SpaceObject, ObjectClass, ObjectSubtype, ObjectOrigin, DiscoveryState


# ---------------------------------------------------------------------------
# LOD Levels
# ---------------------------------------------------------------------------

class LODLevel(IntEnum):
    """
    Level of detail hierarchy.
    Each level generates objects at a specific scale.
    """
    GALAXY_CLUSTER = 0    # Gpc scale: large structure of universe
    GALAXY         = 1    # Mpc scale: individual galaxies
    STAR_CLUSTER   = 2    # kpc scale: globular/open clusters
    STAR_SYSTEM    = 3    # parsec scale: individual stars + planets
    PLANET         = 4    # AU scale: planetary systems
    SURFACE        = 5    # km scale: terrain, cities, moons


# Scale thresholds: distance at which each LOD becomes active (light-years)
LOD_DISTANCE_THRESHOLDS = {
    LODLevel.GALAXY_CLUSTER: float('inf'),      # always visible
    LODLevel.GALAXY:         3.26e9,            # 1 Gpc
    LODLevel.STAR_CLUSTER:   3.26e6,            # 1 Mpc
    LODLevel.STAR_SYSTEM:    3260,              # 1 kpc
    LODLevel.PLANET:         100,               # ~30 parsec
    LODLevel.SURFACE:        0.1,               # ~0.03 parsec (6000 AU)
}


# ---------------------------------------------------------------------------
# Spatial Zones
# ---------------------------------------------------------------------------

@dataclass
class ProceduralZone:
    """
    A spatial region that generates objects on-demand.
    
    Zones are organized in a hierarchical octree:
    - Parent zone contains 8 child zones (octants)
    - Objects are generated based on zone seed + position
    - Zones load/unload based on observer distance
    """
    level: LODLevel
    seed: int                          # Deterministic seed for this zone
    center: Tuple[float, float, float] # (x, y, z) in light-years
    size: float                        # Half-width of cube
    
    # Runtime state
    loaded: bool = False
    objects: List[SpaceObject] = field(default_factory=list)
    children: List[ProceduralZone] = field(default_factory=list)
    
    def __hash__(self):
        """Make zone hashable for use in sets"""
        return hash((self.level, self.seed, self.center, self.size))
    
    def __eq__(self, other):
        """Equality based on immutable properties"""
        if not isinstance(other, ProceduralZone):
            return False
        return (self.level == other.level and 
                self.seed == other.seed and
                self.center == other.center and
                self.size == other.size)
    
    def contains_point(self, x: float, y: float, z: float) -> bool:
        """Check if point is inside this zone"""
        cx, cy, cz = self.center
        return (abs(x - cx) <= self.size and
                abs(y - cy) <= self.size and
                abs(z - cz) <= self.size)
    
    def distance_to_point(self, x: float, y: float, z: float) -> float:
        """Distance from point to nearest edge of zone"""
        cx, cy, cz = self.center
        dx = max(0, abs(x - cx) - self.size)
        dy = max(0, abs(y - cy) - self.size)
        dz = max(0, abs(z - cz) - self.size)
        return math.sqrt(dx*dx + dy*dy + dz*dz)


# ---------------------------------------------------------------------------
# Procedural Generator
# ---------------------------------------------------------------------------

class ProceduralGenerator:
    """
    Generates space objects deterministically from seeds.
    
    Each zone gets a unique seed, and all objects within that zone
    are generated using that seed + local position hash.
    """
    
    def __init__(self, universe_seed: int = 42):
        self.universe_seed = universe_seed
    
    def generate_zone_objects(self, zone: ProceduralZone) -> List[SpaceObject]:
        """
        Generate all objects for a zone at its LOD level.
        
        Returns:
            List of SpaceObject instances
        """
        rng = random.Random(zone.seed)
        objects = []
        
        if zone.level == LODLevel.GALAXY:
            objects = self._generate_galaxies(zone, rng)
        elif zone.level == LODLevel.STAR_CLUSTER:
            objects = self._generate_star_clusters(zone, rng)
        elif zone.level == LODLevel.STAR_SYSTEM:
            objects = self._generate_stars(zone, rng)
        elif zone.level == LODLevel.PLANET:
            objects = self._generate_planets(zone, rng)
        
        return objects
    
    def _generate_galaxies(self, zone: ProceduralZone, rng: random.Random) -> List[SpaceObject]:
        """Generate galaxies in this zone (Mpc scale)"""
        objects = []
        
        # Galaxy density: ~0.1 galaxies per cubic Mpc
        volume_mpc3 = (zone.size * 2 / 3.26e6) ** 3
        n_galaxies = int(volume_mpc3 * 0.1)
        
        for i in range(n_galaxies):
            # Random position within zone
            cx, cy, cz = zone.center
            x = cx + rng.uniform(-zone.size, zone.size)
            y = cy + rng.uniform(-zone.size, zone.size)
            z = cz + rng.uniform(-zone.size, zone.size)
            
            # Convert to RA/Dec/distance
            ra, dec, dist = self._xyz_to_radec(x, y, z)
            
            # Galaxy properties
            galaxy_type = rng.choice([
                ObjectSubtype.SPIRAL,
                ObjectSubtype.ELLIPTICAL,
                ObjectSubtype.IRREGULAR,
                ObjectSubtype.BARRED_SPIRAL,
            ])
            
            mag = rng.uniform(12, 18)  # apparent magnitude
            size = rng.uniform(1, 10)  # arcminutes
            
            obj = SpaceObject(
                uid=f"PROC_GAL_{zone.seed}_{i}",
                name=f"Galaxy {zone.seed}-{i}",
                ra_deg=ra,
                dec_deg=dec,
                distance_ly=dist,
                obj_class=ObjectClass.GALAXY,
                subtype=galaxy_type,
                origin=ObjectOrigin.PROCEDURAL,
                discovery=DiscoveryState.UNKNOWN,
                mag=mag,
                size_arcmin=size,
            )
            objects.append(obj)
        
        return objects
    
    def _generate_star_clusters(self, zone: ProceduralZone, rng: random.Random) -> List[SpaceObject]:
        """Generate star clusters (kpc scale)"""
        objects = []
        
        # Cluster density: ~1 per 100 cubic parsec in galactic plane
        volume_pc3 = (zone.size * 2 / 3.26) ** 3
        n_clusters = max(1, int(volume_pc3 / 100))
        
        for i in range(n_clusters):
            cx, cy, cz = zone.center
            x = cx + rng.uniform(-zone.size, zone.size)
            y = cy + rng.uniform(-zone.size, zone.size)
            z = cz + rng.uniform(-zone.size, zone.size)
            
            ra, dec, dist = self._xyz_to_radec(x, y, z)
            
            cluster_type = rng.choice([
                ObjectSubtype.OPEN_CLUSTER,
                ObjectSubtype.GLOBULAR_CLUSTER,
            ])
            
            obj = SpaceObject(
                uid=f"PROC_CL_{zone.seed}_{i}",
                name=f"Cluster {zone.seed}-{i}",
                ra_deg=ra,
                dec_deg=dec,
                distance_ly=dist,
                obj_class=ObjectClass.CLUSTER,
                subtype=cluster_type,
                origin=ObjectOrigin.PROCEDURAL,
                discovery=DiscoveryState.UNKNOWN,
                mag=rng.uniform(8, 14),
                size_arcmin=rng.uniform(5, 30),
            )
            objects.append(obj)
        
        return objects
    
    def _generate_stars(self, zone: ProceduralZone, rng: random.Random) -> List[SpaceObject]:
        """Generate stars (parsec scale)"""
        objects = []
        
        # Star density: ~0.1 stars per cubic parsec (solar neighborhood)
        volume_pc3 = (zone.size * 2 / 3.26) ** 3
        n_stars = max(1, int(volume_pc3 * 0.1))
        
        for i in range(n_stars):
            cx, cy, cz = zone.center
            x = cx + rng.uniform(-zone.size, zone.size)
            y = cy + rng.uniform(-zone.size, zone.size)
            z = cz + rng.uniform(-zone.size, zone.size)
            
            ra, dec, dist = self._xyz_to_radec(x, y, z)
            
            # Stellar population synthesis (simplified)
            mag = rng.uniform(5, 15)  # mostly faint stars
            bv = rng.gauss(0.6, 0.4)  # solar-like average
            
            obj = SpaceObject(
                uid=f"PROC_STAR_{zone.seed}_{i}",
                name=f"Star {zone.seed}-{i}",
                ra_deg=ra,
                dec_deg=dec,
                distance_ly=dist,
                obj_class=ObjectClass.STAR,
                subtype=ObjectSubtype.MAIN_SEQUENCE,
                origin=ObjectOrigin.PROCEDURAL,
                discovery=DiscoveryState.UNKNOWN,
                mag=mag,
                bv_color=bv,
            )
            objects.append(obj)
        
        return objects
    
    def _generate_planets(self, zone: ProceduralZone, rng: random.Random) -> List[SpaceObject]:
        """Generate planets around nearby stars (AU scale)"""
        # Placeholder — planets require parent star reference
        return []
    
    def _xyz_to_radec(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Convert Cartesian (x,y,z) to (RA, Dec, distance)"""
        dist = math.sqrt(x*x + y*y + z*z)
        if dist < 1e-10:
            return 0.0, 0.0, 0.0
        
        dec = math.degrees(math.asin(z / dist))
        ra = math.degrees(math.atan2(y, x))
        if ra < 0:
            ra += 360
        
        return ra, dec, dist


# ---------------------------------------------------------------------------
# LOD Manager
# ---------------------------------------------------------------------------

class LODManager:
    """
    Manages loading/unloading of procedural zones based on observer position.
    
    Usage:
        lod = LODManager(universe_seed=42)
        lod.update_observer_position(x, y, z)
        new_objects = lod.get_active_objects()
    """
    
    def __init__(self, universe_seed: int = 42):
        self.generator = ProceduralGenerator(universe_seed)
        self.root_zone = self._create_root_zone()
        self.active_zones: Set[ProceduralZone] = set()
        self.observer_pos = (0.0, 0.0, 0.0)  # (x, y, z) in light-years
    
    def _create_root_zone(self) -> ProceduralZone:
        """Create the root zone encompassing the observable universe"""
        # Observable universe: ~46 billion light-years radius
        return ProceduralZone(
            level=LODLevel.GALAXY_CLUSTER,
            seed=self.generator.universe_seed,
            center=(0.0, 0.0, 0.0),
            size=46e9,  # 46 Gly
        )
    
    def update_observer_position(self, x: float, y: float, z: float) -> None:
        """
        Update observer position and refresh active zones.
        
        Args:
            x, y, z: Observer position in light-years from origin
        """
        self.observer_pos = (x, y, z)
        self._refresh_zones()
    
    def _refresh_zones(self) -> None:
        """
        Load/unload zones based on observer distance.
        
        Subdivision logic (Space Engine style):
        - Subdivide if zone subtends large angle (size/distance > threshold)
        - This simulates "zooming in" — nearby small zones = high detail
        """
        x, y, z = self.observer_pos
        
        zones_to_check = [self.root_zone]
        new_active = set()
        max_iterations = 1000
        iteration = 0
        
        while zones_to_check and iteration < max_iterations:
            iteration += 1
            zone = zones_to_check.pop()
            
            # Distance from observer to zone center
            cx, cy, cz = zone.center
            distance = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if distance < 1e-10:
                distance = zone.size  # Observer inside zone
            
            # Angular size of zone (radians)
            angular_size = zone.size / distance if distance > 0 else float('inf')
            
            # Get LOD threshold for this level
            threshold = LOD_DISTANCE_THRESHOLDS.get(zone.level, float('inf'))
            
            # Activate zone if observer is within threshold distance
            if distance < threshold:
                if not zone.loaded:
                    self._load_zone(zone)
                new_active.add(zone)
                
                # Subdivide if:
                # 1. Not at max LOD
                # 2. Zone subtends large angle (> 0.1 radian ~ 6°)
                # 3. Zone size > 1 ly (don't subdivide infinitely)
                should_subdivide = (
                    zone.level < LODLevel.SURFACE and
                    angular_size > 0.1 and
                    zone.size > 1.0
                )
                
                if should_subdivide:
                    if not zone.children:
                        self._subdivide_zone(zone)
                    zones_to_check.extend(zone.children)
            elif zone.loaded:
                self._unload_zone(zone)
        
        if iteration >= max_iterations:
            print(f"⚠ LOD hit {max_iterations} iterations (position:{x:.0e}, {y:.0e}, {z:.0e})")
        
        self.active_zones = new_active
    
    def _load_zone(self, zone: ProceduralZone) -> None:
        """Generate objects for this zone"""
        zone.objects = self.generator.generate_zone_objects(zone)
        zone.loaded = True
    
    def _unload_zone(self, zone: ProceduralZone) -> None:
        """Clear objects from this zone to free memory"""
        zone.objects.clear()
        zone.loaded = False
    
    def _subdivide_zone(self, zone: ProceduralZone) -> None:
        """Create 8 child zones (octree subdivision)"""
        half_size = zone.size / 2
        cx, cy, cz = zone.center
        next_level = LODLevel(zone.level + 1)
        
        for dx in [-half_size, half_size]:
            for dy in [-half_size, half_size]:
                for dz in [-half_size, half_size]:
                    child_center = (cx + dx, cy + dy, cz + dz)
                    child_seed = hash((zone.seed, dx, dy, dz)) & 0x7FFFFFFF
                    
                    child = ProceduralZone(
                        level=next_level,
                        seed=child_seed,
                        center=child_center,
                        size=half_size,
                    )
                    zone.children.append(child)
    
    def get_active_objects(self) -> List[SpaceObject]:
        """Get all objects from currently active zones"""
        objects = []
        for zone in self.active_zones:
            objects.extend(zone.objects)
        return objects
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about current LOD state"""
        return {
            'active_zones': len(self.active_zones),
            'total_objects': sum(len(z.objects) for z in self.active_zones),
            'loaded_zones_by_level': {
                level: sum(1 for z in self.active_zones if z.level == level)
                for level in LODLevel
            }
        }
