"""
Universe — the single source of truth for all objects in the simulation.

Architecture
------------
The Universe holds every SpaceObject (real + procedural).
All other systems (SkyChart, Imaging, Career) query the Universe —
they never hold their own object lists.

Query interface
---------------
  universe.get_all()                   → all visible objects
  universe.get_dso()                   → DSOs only (no stars)
  universe.get_stars()                 → stars only
  universe.get_by_uid("M42")           → single object
  universe.query_cone(ra, dec, r_deg)  → objects within angular radius
  universe.query_class(ObjectClass.NEBULA) → by class

Visibility rules
----------------
  Real objects      → always returned by queries
  Procedural        → returned only if discovery == CATALOGUED
                      (unless include_unknown=True is passed)
"""

from __future__ import annotations
import math
from typing import List, Optional, Dict, Callable
import numpy as np

from .space_object import SpaceObject, ObjectClass, ObjectSubtype, ObjectOrigin, DiscoveryState


class Universe:
    """
    Central repository of all SpaceObjects.

    Populated at startup from real catalogues; procedural objects
    are added at runtime by the LOD generation engine.
    """

    def __init__(self, enable_procedural: bool = False, universe_seed: int = 42):
        # Main store: uid → SpaceObject
        self._objects: Dict[str, SpaceObject] = {}

        # Cached partitions (rebuilt when objects are added)
        self._stars: List[SpaceObject] = []
        self._dso:   List[SpaceObject] = []
        self._dirty  = True

        # Numpy arrays parallel to self._stars (pre-sorted by magnitude)
        self._star_ra:  np.ndarray = np.empty(0, dtype=np.float64)
        self._star_dec: np.ndarray = np.empty(0, dtype=np.float64)
        self._star_mag: np.ndarray = np.empty(0, dtype=np.float32)
        self._star_bv:  np.ndarray = np.empty(0, dtype=np.float32)
        
        # Procedural LOD system (disabled by default for now)
        self.enable_procedural = enable_procedural
        self.lod_manager = None
        self.observer_position_ly = (0.0, 0.0, 0.0)  # Observer at origin (Sun)
        
        if enable_procedural:
            from .procedural_lod import LODManager
            self.lod_manager = LODManager(universe_seed)
            print(f"Procedural LOD enabled (seed={universe_seed})")

    # -----------------------------------------------------------------------
    # Mutation
    # -----------------------------------------------------------------------

    def add(self, obj: SpaceObject) -> None:
        """Add or replace an object"""
        self._objects[obj.uid] = obj
        self._dirty = True

    def add_many(self, objects: List[SpaceObject]) -> None:
        """Bulk add"""
        for obj in objects:
            self._objects[obj.uid] = obj
        self._dirty = True

    def catalogue_procedural(self, uid: str) -> bool:
        """
        Mark a procedural object as catalogued (discovered by player).
        Returns True if found and updated.
        """
        obj = self._objects.get(uid)
        if obj and obj.origin == ObjectOrigin.PROCEDURAL:
            obj.discovery = DiscoveryState.CATALOGUED
            self._dirty = True
            return True
        return False
    
    # -----------------------------------------------------------------------
    # Procedural LOD System
    # -----------------------------------------------------------------------
    
    def update_observer_position(self, x_ly: float, y_ly: float, z_ly: float) -> None:
        """
        Update observer position for procedural generation.
        
        Args:
            x_ly, y_ly, z_ly: Position in light-years from origin (Sun)
        
        This triggers LOD zone loading/unloading based on distance.
        For gameplay, observer is typically at origin (0, 0, 0).
        For future space travel: set actual ship position.
        """
        if not self.enable_procedural or not self.lod_manager:
            return
        
        self.observer_position_ly = (x_ly, y_ly, z_ly)
        self.lod_manager.update_observer_position(x_ly, y_ly, z_ly)
        
        # Get newly generated procedural objects
        procedural_objs = self.lod_manager.get_active_objects()
        
        # Add to universe (merge with existing)
        for obj in procedural_objs:
            if obj.uid not in self._objects:
                self.add(obj)
    
    def get_procedural_stats(self) -> Dict:
        """Get statistics about procedural generation"""
        if not self.enable_procedural or not self.lod_manager:
            return {'enabled': False}
        
        stats = self.lod_manager.get_stats()
        stats['enabled'] = True
        stats['observer_pos_ly'] = self.observer_position_ly
        return stats

    # -----------------------------------------------------------------------
    # Internal cache
    # -----------------------------------------------------------------------

    def _rebuild_cache(self):
        if not self._dirty:
            return
        self._stars = [o for o in self._objects.values()
                       if o.obj_class == ObjectClass.STAR]
        self._dso   = [o for o in self._objects.values()
                       if o.obj_class != ObjectClass.STAR]

        # Build numpy arrays pre-sorted by magnitude (brightest first → early exit)
        n = len(self._stars)
        if n > 0:
            self._stars.sort(key=lambda s: s.mag)
            self._star_ra  = np.array([s.ra_deg   for s in self._stars], dtype=np.float64)
            self._star_dec = np.array([s.dec_deg  for s in self._stars], dtype=np.float64)
            self._star_mag = np.array([s.mag       for s in self._stars], dtype=np.float32)
            self._star_bv  = np.array([s.bv_color  for s in self._stars], dtype=np.float32)
        else:
            self._star_ra  = np.empty(0, dtype=np.float64)
            self._star_dec = np.empty(0, dtype=np.float64)
            self._star_mag = np.empty(0, dtype=np.float32)
            self._star_bv  = np.empty(0, dtype=np.float32)

        self._dirty = False

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    def get_all(self, include_unknown: bool = False) -> List[SpaceObject]:
        """All objects, applying visibility rules"""
        return [o for o in self._objects.values()
                if include_unknown or o.is_visible_in_chart]

    def get_stars(self) -> List[SpaceObject]:
        """All real stars (sorted by magnitude, brightest first)"""
        self._rebuild_cache()
        return self._stars

    def get_star_arrays(self) -> tuple:
        """
        Returns (star_objects, ra, dec, mag, bv) — all pre-sorted by magnitude.

        star_objects: List[SpaceObject] sorted by mag (for name/uid lookups)
        ra, dec: np.ndarray float64 (degrees)
        mag: np.ndarray float32
        bv: np.ndarray float32

        Usage for vectorized filtering::

            stars, ra, dec, mag, bv = universe.get_star_arrays()
            mask = mag <= 6.5          # vectorized — instant for 389k
            visible_ra  = ra[mask]
            visible_dec = dec[mask]
        """
        self._rebuild_cache()
        return self._stars, self._star_ra, self._star_dec, self._star_mag, self._star_bv

    def query_stars_in_fov(self, center_ra: float, center_dec: float,
                            fov_deg: float, mag_limit: float) -> np.ndarray:
        """
        Fast vectorized query: returns boolean mask of stars within FOV and mag limit.

        Returns:
            np.ndarray[bool] — mask aligned with get_star_arrays() output.

        Example::

            stars, ra, dec, mag, bv = universe.get_star_arrays()
            mask = universe.query_stars_in_fov(cra, cdec, fov, mlim)
            visible_ra = ra[mask]
        """
        self._rebuild_cache()
        n = len(self._star_mag)
        if n == 0:
            return np.empty(0, dtype=bool)

        # Magnitude filter — exploit pre-sort with binary search
        cutoff = int(np.searchsorted(self._star_mag, mag_limit, side='right'))

        mask = np.zeros(n, dtype=bool)
        if cutoff == 0:
            return mask

        # Spatial filter on the magnitude-passing subset only
        ra_sub  = self._star_ra[:cutoff]
        dec_sub = self._star_dec[:cutoff]

        half_fov = fov_deg / 2.0 + 2.0   # small margin to avoid clipping

        # Dec filter (no wrapping)
        dec_ok = np.abs(dec_sub - center_dec) <= half_fov

        # RA filter with cos(dec) correction and wraparound
        dra    = (ra_sub - center_ra + 180.0) % 360.0 - 180.0
        cos_dec = math.cos(math.radians(center_dec))
        ra_ok  = np.abs(dra * cos_dec) <= half_fov

        mask[:cutoff] = dec_ok & ra_ok
        return mask

    def get_dso(self, include_unknown: bool = False) -> List[SpaceObject]:
        """All DSOs (non-stars), applying visibility rules"""
        self._rebuild_cache()
        return [o for o in self._dso
                if include_unknown or o.is_visible_in_chart]

    def get_by_uid(self, uid: str) -> Optional[SpaceObject]:
        return self._objects.get(uid)

    def get_by_class(self, obj_class: ObjectClass,
                     include_unknown: bool = False) -> List[SpaceObject]:
        return [o for o in self._objects.values()
                if o.obj_class == obj_class
                and (include_unknown or o.is_visible_in_chart)]

    def get_by_subtype(self, subtype: ObjectSubtype) -> List[SpaceObject]:
        return [o for o in self._objects.values()
                if o.subtype == subtype and o.is_visible_in_chart]

    def query_cone(self, center_ra: float, center_dec: float,
                   radius_deg: float,
                   include_unknown: bool = False) -> List[SpaceObject]:
        """
        Return all visible objects within angular radius of (ra, dec).
        Uses fast great-circle approximation.
        """
        results = []
        cos_r = math.cos(math.radians(radius_deg))
        ra0  = math.radians(center_ra)
        dec0 = math.radians(center_dec)

        for obj in self._objects.values():
            if not include_unknown and not obj.is_visible_in_chart:
                continue
            ra  = math.radians(obj.ra_deg)
            dec = math.radians(obj.dec_deg)
            # Dot product for angular separation
            dot = (math.sin(dec0) * math.sin(dec) +
                   math.cos(dec0) * math.cos(dec) * math.cos(ra - ra0))
            dot = max(-1.0, min(1.0, dot))
            if dot >= cos_r:
                results.append(obj)

        return results

    def query_fov(self, center_ra: float, center_dec: float,
                  fov_width_deg: float, fov_height_deg: float,
                  include_unknown: bool = False) -> List[SpaceObject]:
        """
        Return objects within a rectangular FOV (for imaging).
        """
        half_w = fov_width_deg  / 2.0
        half_h = fov_height_deg / 2.0

        results = []
        for obj in self._objects.values():
            if not include_unknown and not obj.is_visible_in_chart:
                continue

            # RA difference (handle wrap)
            dra = (obj.ra_deg - center_ra + 180) % 360 - 180
            # Correct for declination compression
            dra_corr = dra * math.cos(math.radians(center_dec))
            ddec = obj.dec_deg - center_dec

            if abs(dra_corr) <= half_w and abs(ddec) <= half_h:
                results.append(obj)

        return results

    def find_nearest(self, ra: float, dec: float,
                     max_dist_deg: float = 2.0,
                     only_dso: bool = False) -> Optional[SpaceObject]:
        """Find the nearest visible object to (ra, dec)"""
        best     = None
        best_sep = max_dist_deg

        ra0  = math.radians(ra)
        dec0 = math.radians(dec)

        for obj in self._objects.values():
            if not obj.is_visible_in_chart:
                continue
            if only_dso and obj.obj_class == ObjectClass.STAR:
                continue

            r  = math.radians(obj.ra_deg)
            d  = math.radians(obj.dec_deg)
            dot = (math.sin(dec0) * math.sin(d) +
                   math.cos(dec0) * math.cos(d) * math.cos(r - ra0))
            dot = max(-1.0, min(1.0, dot))
            sep = math.degrees(math.acos(dot))

            if sep < best_sep:
                best_sep = sep
                best     = obj

        return best

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    @property
    def total_objects(self) -> int:
        return len(self._objects)

    @property
    def real_count(self) -> int:
        return sum(1 for o in self._objects.values()
                   if o.origin == ObjectOrigin.REAL)

    @property
    def procedural_count(self) -> int:
        return sum(1 for o in self._objects.values()
                   if o.origin == ObjectOrigin.PROCEDURAL)

    @property
    def catalogued_procedural_count(self) -> int:
        return sum(1 for o in self._objects.values()
                   if o.origin == ObjectOrigin.PROCEDURAL
                   and o.discovery == DiscoveryState.CATALOGUED)

    def __repr__(self) -> str:
        return (f"<Universe: {self.total_objects} objects "
                f"({self.real_count} real, {self.procedural_count} procedural)>")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_universe() -> Universe:
    """
    Build and return the full universe loaded from real catalogues.
    Call once at startup and pass the instance everywhere.
    """
    from .catalogue_loader import load_messier, load_ngc, load_stars

    u = Universe()

    print("Building universe...")

    stars = load_stars()
    u.add_many(stars)
    print(f"  Stars:   {len(stars)}")

    messier = load_messier()
    u.add_many(messier)
    print(f"  Messier: {len(messier)}")

    ngc = load_ngc()
    u.add_many(ngc)
    print(f"  NGC:     {len(ngc)}")

    print(f"  Total:   {u.total_objects} objects")
    print(f"  Universe ready: {u}")

    return u
