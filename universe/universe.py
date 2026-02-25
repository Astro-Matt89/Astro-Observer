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

        # Bulk star arrays — Level 2 (numpy only, no SpaceObject)
        # Loaded from extended catalogs (Gaia mag<15+)
        # These stars appear in rendering but cannot be selected/labeled
        self._bulk_star_ra:  np.ndarray = np.empty(0, dtype=np.float64)
        self._bulk_star_dec: np.ndarray = np.empty(0, dtype=np.float64)
        self._bulk_star_mag: np.ndarray = np.empty(0, dtype=np.float32)
        self._bulk_star_bv:  np.ndarray = np.empty(0, dtype=np.float32)
        self._bulk_dirty: bool = False  # True when merged arrays need rebuild
        # Merged arrays cache (Level 1 + Level 2, sorted by mag)
        self._merged_ra:  np.ndarray = np.empty(0, dtype=np.float64)
        self._merged_dec: np.ndarray = np.empty(0, dtype=np.float64)
        self._merged_mag: np.ndarray = np.empty(0, dtype=np.float32)
        self._merged_bv:  np.ndarray = np.empty(0, dtype=np.float32)
        self._merged_n_named: int = 0  # count of Level 1 (named) stars in merged arrays

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

        # If bulk stars exist, merged arrays need rebuild too
        if len(self._bulk_star_mag) > 0:
            self._bulk_dirty = True

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

        star_objects: List[SpaceObject] — Level 1 named stars only (sorted by mag).
                      Length may be LESS than the arrays if bulk stars are loaded.
                      Indices 0..len(star_objects)-1 in the arrays correspond to
                      named stars. Indices beyond that are bulk (unnamed) stars.
                      NOTE: When bulk stars are loaded, the arrays are re-sorted
                      by magnitude across both levels, so array index != star_objects index.
        ra, dec: np.ndarray float64 (degrees)
        mag: np.ndarray float32
        bv: np.ndarray float32
        """
        self._rebuild_cache()
        if self._bulk_dirty or (len(self._bulk_star_mag) > 0 and len(self._merged_mag) == 0):
            self._rebuild_merged_arrays()

        if len(self._bulk_star_mag) > 0:
            return self._stars, self._merged_ra, self._merged_dec, self._merged_mag, self._merged_bv
        else:
            return self._stars, self._star_ra, self._star_dec, self._star_mag, self._star_bv

    def query_stars_in_fov(self, center_ra: float, center_dec: float,
                            fov_deg: float, mag_limit: float) -> np.ndarray:
        """
        Fast vectorized query: returns boolean mask of stars within FOV and mag limit.
        Works with unified arrays (Level 1 + Level 2 when bulk stars are loaded).

        Returns:
            np.ndarray[bool] — mask aligned with get_star_arrays() output.

        Example::

            stars, ra, dec, mag, bv = universe.get_star_arrays()
            mask = universe.query_stars_in_fov(cra, cdec, fov, mlim)
            visible_ra = ra[mask]
        """
        self._rebuild_cache()
        if self._bulk_dirty or (len(self._bulk_star_mag) > 0 and len(self._merged_mag) == 0):
            self._rebuild_merged_arrays()

        # Use merged arrays if bulk stars present, otherwise Level 1 only
        if len(self._bulk_star_mag) > 0:
            star_mag = self._merged_mag
            star_ra  = self._merged_ra
            star_dec = self._merged_dec
        else:
            star_mag = self._star_mag
            star_ra  = self._star_ra
            star_dec = self._star_dec

        n = len(star_mag)
        if n == 0:
            return np.empty(0, dtype=bool)

        # Magnitude filter — exploit pre-sort with binary search
        cutoff = int(np.searchsorted(star_mag, mag_limit, side='right'))

        mask = np.zeros(n, dtype=bool)
        if cutoff == 0:
            return mask

        # Spatial filter on the magnitude-passing subset only
        ra_sub  = star_ra[:cutoff]
        dec_sub = star_dec[:cutoff]

        half_fov = fov_deg / 2.0 + 2.0   # small margin to avoid clipping

        # Dec filter (no wrapping)
        dec_ok = np.abs(dec_sub - center_dec) <= half_fov

        # RA filter with cos(dec) correction and wraparound
        dra    = (ra_sub - center_ra + 180.0) % 360.0 - 180.0
        cos_dec = math.cos(math.radians(center_dec))
        ra_ok  = np.abs(dra * cos_dec) <= half_fov

        mask[:cutoff] = dec_ok & ra_ok
        return mask

    def load_bulk_stars(self, npz_path: str, mag_limit: float = 15.0) -> int:
        """
        Load millions of faint stars directly as numpy arrays.
        No SpaceObject overhead — pure numeric data for rendering only.

        These stars:
          ✓ Appear in SkyChart / AllSky / Imaging (as dots/points)
          ✗ Cannot be selected, labeled, or shown in info panel
          ✗ Not in Universe._objects dict

        Args:
            npz_path: Path to NPZ file with keys: ra_deg, dec_deg, mag, bv (or bp_rp)
            mag_limit: Maximum magnitude to load (default 15.0)

        Returns:
            Number of bulk stars loaded

        NPZ format expected:
            ra_deg: float64 array (degrees, J2000)
            dec_deg: float64 array (degrees, J2000)
            mag: float32 array (apparent visual magnitude, or phot_g_mean_mag)
            bp_rp: float32 array (optional, Gaia color — converted to B-V via /1.3)
            bv: float32 array (optional, B-V color index — used if bp_rp not present)
        """
        from pathlib import Path

        path = Path(npz_path)
        if not path.exists():
            print(f"Bulk catalog not found: {npz_path}")
            return 0

        print(f"Loading bulk star catalog: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)...")

        data = np.load(npz_path)

        # Extract arrays (flexible key names)
        ra  = data.get('ra_deg', data.get('ra'))
        dec = data.get('dec_deg', data.get('dec'))
        mag = data.get('mag', data.get('phot_g_mean_mag', data.get('mag_g', data.get('gmag'))))

        if ra is None or dec is None or mag is None:
            print(f"  Error: Missing required fields. Available: {list(data.keys())}")
            print(f"  Need: ra_deg/ra, dec_deg/dec, mag/phot_g_mean_mag")
            return 0

        # B-V color: from bp_rp (Gaia) or bv, or default
        bp_rp = data.get('bp_rp', data.get('bprp'))
        bv = data.get('bv', data.get('b_v'))
        if bp_rp is not None:
            bv_arr = (bp_rp / 1.3).astype(np.float32)
        elif bv is not None:
            bv_arr = bv.astype(np.float32)
        else:
            bv_arr = np.full(len(ra), 0.6, dtype=np.float32)

        # Filter by magnitude
        mask = mag < mag_limit
        # Also filter NaN
        mask &= np.isfinite(ra) & np.isfinite(dec) & np.isfinite(mag)

        ra_filtered  = ra[mask].astype(np.float64)
        dec_filtered = dec[mask].astype(np.float64)
        mag_filtered = mag[mask].astype(np.float32)
        bv_filtered  = bv_arr[mask]
        # Replace NaN in bv with 0.6 (solar)
        bv_filtered = np.where(np.isfinite(bv_filtered), bv_filtered, 0.6)

        n_raw = int(mask.sum())
        print(f"  Filtered to mag<{mag_limit}: {n_raw:,} stars")

        # Deduplicate against Level 1 stars
        # (remove bulk stars that are within 0.003° = 10 arcsec of a named star)
        self._rebuild_cache()
        if len(self._star_ra) > 0:
            n_before = len(ra_filtered)
            keep = self._deduplicate_bulk(ra_filtered, dec_filtered,
                                           self._star_ra, self._star_dec,
                                           radius_deg=0.003)
            ra_filtered  = ra_filtered[keep]
            dec_filtered = dec_filtered[keep]
            mag_filtered = mag_filtered[keep]
            bv_filtered  = bv_filtered[keep]
            n_dedup = n_before - len(ra_filtered)
            print(f"  Deduplicated: {n_dedup:,} removed (within 10\" of named stars)")

        # Sort by magnitude (brightest first, consistent with Level 1)
        order = np.argsort(mag_filtered)
        self._bulk_star_ra  = ra_filtered[order]
        self._bulk_star_dec = dec_filtered[order]
        self._bulk_star_mag = mag_filtered[order]
        self._bulk_star_bv  = bv_filtered[order]
        self._bulk_dirty = True

        print(f"  Bulk stars loaded: {len(self._bulk_star_mag):,}")
        return len(self._bulk_star_mag)

    @staticmethod
    def _deduplicate_bulk(bulk_ra: np.ndarray, bulk_dec: np.ndarray,
                           named_ra: np.ndarray, named_dec: np.ndarray,
                           radius_deg: float = 0.003) -> np.ndarray:
        """
        Return boolean mask of bulk stars that are NOT duplicates of named stars.
        Uses integer-degree bucketing for O(N+M) approximate matching.
        """
        # Build bucket set from named stars (and neighboring buckets)
        named_buckets = set()
        for i in range(len(named_ra)):
            ra_b  = int(named_ra[i])
            dec_b = int(named_dec[i])
            for dra in (-1, 0, 1):
                for ddec in (-1, 0, 1):
                    named_buckets.add(((ra_b + dra) % 360, dec_b + ddec))

        keep = np.ones(len(bulk_ra), dtype=bool)

        # For each bulk star, check if any named star is within radius
        for i in range(len(bulk_ra)):
            bucket = (int(bulk_ra[i]) % 360, int(bulk_dec[i]))
            if bucket not in named_buckets:
                continue  # No named stars nearby, definitely keep

            # Fine check: compute actual distance to all named stars in nearby buckets
            dra  = np.abs(bulk_ra[i] - named_ra)
            dra  = np.minimum(dra, 360.0 - dra)  # wraparound
            ddec = np.abs(bulk_dec[i] - named_dec)
            dist_sq = dra * dra + ddec * ddec
            if np.any(dist_sq < radius_deg * radius_deg):
                keep[i] = False

        return keep

    def _rebuild_merged_arrays(self):
        """Rebuild unified Level 1 + Level 2 arrays, sorted by magnitude."""
        self._rebuild_cache()

        n_named = len(self._star_mag)
        n_bulk  = len(self._bulk_star_mag)

        if n_bulk == 0:
            # No bulk stars — merged arrays are just Level 1
            self._merged_ra  = self._star_ra
            self._merged_dec = self._star_dec
            self._merged_mag = self._star_mag
            self._merged_bv  = self._star_bv
            self._merged_n_named = n_named
        else:
            # Concatenate and merge-sort by magnitude
            ra  = np.concatenate([self._star_ra,  self._bulk_star_ra])
            dec = np.concatenate([self._star_dec, self._bulk_star_dec])
            mag = np.concatenate([self._star_mag, self._bulk_star_mag])
            bv  = np.concatenate([self._star_bv,  self._bulk_star_bv])

            # Merge sort (both arrays already sorted → stable mergesort is optimal)
            order = np.argsort(mag, kind='mergesort')
            self._merged_ra  = ra[order]
            self._merged_dec = dec[order]
            self._merged_mag = mag[order]
            self._merged_bv  = bv[order]
            self._merged_n_named = n_named

            print(f"  Merged arrays: {n_named:,} named + {n_bulk:,} bulk = {len(mag):,} total")

        self._bulk_dirty = False

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

    @property
    def bulk_star_count(self) -> int:
        """Number of Level 2 (bulk) stars loaded."""
        return len(self._bulk_star_mag)

    def __repr__(self) -> str:
        bulk = f", {self.bulk_star_count:,} bulk" if self.bulk_star_count > 0 else ""
        return (f"<Universe: {self.total_objects} objects "
                f"({self.real_count} real, {self.procedural_count} procedural{bulk})>")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_universe() -> Universe:
    """
    Build and return the full universe loaded from real catalogues.
    Call once at startup and pass the instance everywhere.
    """
    from .catalogue_loader import load_messier, load_ngc, load_stars
    from pathlib import Path

    u = Universe()

    print("Building universe...")

    stars = load_stars()
    u.add_many(stars)
    print(f"  Stars (named): {len(stars):,}")

    messier = load_messier()
    u.add_many(messier)
    print(f"  Messier: {len(messier)}")

    ngc = load_ngc()
    u.add_many(ngc)
    print(f"  NGC:     {len(ngc)}")

    # === Load bulk star catalogs if available ===
    _project_root = Path(__file__).resolve().parent.parent
    _data_dir = _project_root / "catalogs" / "data"

    # Look for extended catalog files (loaded as bulk, not SpaceObject)
    bulk_files = [
        (_data_dir / "gaia_extended.npz", 15.0),   # Gaia DR3 extended (mag<15)
        (_data_dir / "gaia_bulk.npz",     15.0),   # Alternative name
        (_data_dir / "bulk_stars.npz",    15.0),   # Generic bulk catalog
    ]

    for bulk_path, mag_lim in bulk_files:
        if bulk_path.exists():
            n = u.load_bulk_stars(str(bulk_path), mag_limit=mag_lim)
            if n > 0:
                break  # Load only the first available bulk catalog

    print(f"  Total: {u.total_objects:,} objects" +
          (f" + {u.bulk_star_count:,} bulk stars" if u.bulk_star_count > 0 else ""))
    print(f"  Universe ready: {u}")

    return u
