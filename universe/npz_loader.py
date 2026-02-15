"""
NPZ Catalogue Loader

Loads large star catalogues from NumPy compressed archives (.npz).
Supports Gaia DR3 and Hipparcos catalogues with automatic schema detection.

Expected NPZ structure:
  - Gaia: ra, dec, phot_g_mean_mag, parallax, bp_rp (B-V proxy)
  - Hipparcos: ra, dec, vmag, parallax, bv

File locations:
  /home/claude/catalogs/data/gaia.npz
  /home/claude/catalogs/data/hipparcos.npz
"""

from __future__ import annotations
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class CatalogEntry:
    """Intermediate format for catalogue entries before SpaceObject conversion"""
    catalog_id: int          # HIP ID or Gaia source_id
    ra_deg: float
    dec_deg: float
    mag: float
    parallax_mas: float      # milliarcseconds
    bv_color: float          # B-V color index (or proxy)
    catalog_name: str        # "Gaia DR3" or "Hipparcos"


def load_npz_catalog(filepath: str, catalog_type: str = "auto") -> List[CatalogEntry]:
    """
    Load star catalog from NPZ file.
    
    Args:
        filepath: Path to .npz file
        catalog_type: "gaia", "hipparcos", or "auto" (detect from structure)
    
    Returns:
        List of CatalogEntry objects
    """
    path = Path(filepath)
    if not path.exists():
        print(f"Catalog file not found: {filepath}")
        return []
    
    print(f"Loading {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)...")
    
    data = np.load(filepath)
    keys = list(data.keys())
    
    # Find actual data array (not tile metadata)
    data_keys = [k for k in keys if k not in ['tile_keys', 'tile_starts', 'tile_ends']]
    if data_keys:
        n_stars = len(data[data_keys[0]])
    else:
        n_stars = len(data[keys[0]])
    
    print(f"  Keys: {keys}")
    print(f"  Stars: {n_stars:,}")
    
    # Auto-detect catalog type
    if catalog_type == "auto":
        if "phot_g_mean_mag" in keys or "source_id" in keys:
            catalog_type = "gaia"
        elif "hip" in keys or "vmag" in keys:
            catalog_type = "hipparcos"
        else:
            print(f"  Warning: Cannot auto-detect catalog type from keys: {keys}")
            catalog_type = "unknown"
    
    print(f"  Catalog type: {catalog_type}")
    
    # Parse based on type
    if catalog_type == "gaia":
        return _parse_gaia(data, n_stars)
    elif catalog_type == "hipparcos":
        return _parse_hipparcos(data, n_stars)
    else:
        print(f"  Error: Unknown catalog type '{catalog_type}'")
        return []


def _parse_gaia(data: Dict[str, np.ndarray], n_stars: int) -> List[CatalogEntry]:
    """Parse Gaia DR3 NPZ structure"""
    entries = []
    
    # Required fields (adapt to actual NPZ structure)
    ra = data['ra_deg'] if 'ra_deg' in data else data.get('ra')
    dec = data['dec_deg'] if 'dec_deg' in data else data.get('dec')
    mag = (data['mag'] if 'mag' in data else
           data.get('mag_g') if 'mag_g' in data else
           data.get('phot_g_mean_mag') if 'phot_g_mean_mag' in data else
           data.get('gmag'))
    parallax = data.get('parallax') if 'parallax' in data else None
    
    # Optional: B-V proxy from Gaia colors
    # Gaia BP-RP ≈ 1.3 * (B-V) approximately
    bp_rp = data['bp_rp'] if 'bp_rp' in data else data.get('bprp')
    if bp_rp is not None:
        bv = bp_rp / 1.3  # rough conversion
    else:
        bv = np.full(n_stars, 0.6)  # default: solar color
    
    # Source ID (if available)
    source_id = data['source_id'] if 'source_id' in data else data.get('gaia_id')
    if source_id is None:
        source_id = np.arange(n_stars)
    
    if ra is None or dec is None or mag is None:
        print(f"  Error: Missing required fields in Gaia NPZ")
        print(f"    Available: {list(data.keys())}")
        print(f"    Need: ra/ra_deg, dec/dec_deg, mag/mag_g/phot_g_mean_mag")
        return []
    
    if parallax is None:
        parallax = np.full(n_stars, 1.0)  # default 1 mas = 3262 ly
    
    # Filter: mag < 12.0 (gameplay limit)
    mask = mag < 12.0
    n_filtered = mask.sum()
    print(f"  Filtered to mag<12: {n_filtered:,} stars ({n_filtered/n_stars*100:.1f}%)")
    
    for i in np.where(mask)[0]:
        plx_val = parallax[i] if not np.isnan(parallax[i]) and parallax[i] > 0 else 1.0
        bv_val = bv[i] if not np.isnan(bv[i]) else 0.6
        
        entries.append(CatalogEntry(
            catalog_id=int(source_id[i]),
            ra_deg=float(ra[i]),
            dec_deg=float(dec[i]),
            mag=float(mag[i]),
            parallax_mas=float(plx_val),
            bv_color=float(bv_val),
            catalog_name="Gaia DR3",
        ))
    
    return entries


def _parse_hipparcos(data: Dict[str, np.ndarray], n_stars: int) -> List[CatalogEntry]:
    """Parse Hipparcos NPZ structure"""
    entries = []
    
    # Required fields (adapt to actual structure)
    hip = data.get("hip", data.get("hip_id", None))
    ra = data.get("ra_deg", data.get("ra", None))
    dec = data.get("dec_deg", data.get("dec", None))
    mag = data.get("mag_v", data.get("vmag", data.get("mag", None)))
    bv = data.get("b_v", data.get("bv", data.get("b_v_color", None)))
    
    # Parallax might not be present in this format
    # We'll compute distance from known bright stars or use default
    parallax = data.get("parallax", data.get("plx", None))
    
    if ra is None or dec is None or mag is None or hip is None:
        print(f"  Error: Missing required fields in Hipparcos NPZ")
        print(f"    Available: {list(data.keys())}")
        return []
    
    if parallax is None:
        # No parallax data — we'll compute distance later or use defaults
        parallax = np.full(n_stars, 1.0)
    
    if bv is None:
        bv = np.full(n_stars, 0.6)  # solar color default
    
    # Filter: mag < 9.0 for gameplay
    mask = mag < 9.0
    n_filtered = mask.sum()
    print(f"  Filtered to mag<9: {n_filtered:,} stars ({n_filtered/n_stars*100:.1f}%)")
    
    for i in np.where(mask)[0]:
        # Handle NaN in parallax
        plx_val = parallax[i] if not np.isnan(parallax[i]) and parallax[i] > 0 else 1.0
        bv_val = bv[i] if not np.isnan(bv[i]) else 0.6
        
        entries.append(CatalogEntry(
            catalog_id=int(hip[i]),
            ra_deg=float(ra[i]),
            dec_deg=float(dec[i]),
            mag=float(mag[i]),
            parallax_mas=float(plx_val),
            bv_color=float(bv_val),
            catalog_name="Hipparcos",
        ))
    
    return entries


def build_spatial_index(entries: List[CatalogEntry], 
                        resolution_deg: float = 1.0) -> Dict[tuple, List[int]]:
    """
    Build simple spatial hash index for fast nearby star queries.
    
    Args:
        entries: List of catalog entries
        resolution_deg: Grid cell size in degrees
    
    Returns:
        Dict mapping (ra_bucket, dec_bucket) -> [entry indices]
    """
    index = {}
    for i, entry in enumerate(entries):
        bucket = (
            int(entry.ra_deg / resolution_deg),
            int(entry.dec_deg / resolution_deg)
        )
        if bucket not in index:
            index[bucket] = []
        index[bucket].append(i)
    return index


def find_nearby_stars(entries: List[CatalogEntry], 
                      spatial_index: Dict[tuple, List[int]],
                      ra_deg: float, 
                      dec_deg: float, 
                      radius_deg: float = 0.003,
                      resolution_deg: float = 1.0) -> List[int]:
    """
    Find stars within radius of target position using spatial index.
    
    Args:
        entries: Catalog entries
        spatial_index: Precomputed spatial hash
        ra_deg: Target RA
        dec_deg: Target Dec  
        radius_deg: Search radius (default 10 arcsec = 0.003°)
        resolution_deg: Grid resolution used in index
    
    Returns:
        List of entry indices within radius
    """
    # Check neighboring buckets
    center_bucket = (int(ra_deg / resolution_deg), int(dec_deg / resolution_deg))
    candidates = []
    
    for dra in [-1, 0, 1]:
        for ddec in [-1, 0, 1]:
            bucket = (center_bucket[0] + dra, center_bucket[1] + ddec)
            if bucket in spatial_index:
                candidates.extend(spatial_index[bucket])
    
    # Refine with actual distance
    nearby = []
    for idx in candidates:
        entry = entries[idx]
        # Simple Euclidean distance (small angles)
        dist = ((entry.ra_deg - ra_deg)**2 + (entry.dec_deg - dec_deg)**2)**0.5
        if dist <= radius_deg:
            nearby.append(idx)
    
    return nearby


def merge_with_existing(catalog_entries: List[CatalogEntry],
                        existing_stars: List[Any],
                        catalog_name: str) -> tuple[List[Any], int, int]:
    """
    Merge new catalog with existing stars, avoiding duplicates.
    
    Args:
        catalog_entries: New catalog entries to merge
        existing_stars: List of existing SpaceObject instances
        catalog_name: "Gaia DR3" or "Hipparcos"
    
    Returns:
        (merged_stars, n_cross_ref, n_added)
    """
    from universe.space_object import SpaceObject, ObjectClass, ObjectSubtype, ObjectOrigin, DiscoveryState
    
    print(f"\nMerging {catalog_name} with {len(existing_stars)} existing stars...")
    
    # Build spatial index of existing stars
    print("  Building spatial index...")
    existing_index = {}
    for i, star in enumerate(existing_stars):
        bucket = (int(star.ra_deg), int(star.dec_deg))
        if bucket not in existing_index:
            existing_index[bucket] = []
        existing_index[bucket].append(i)
    
    n_cross_ref = 0
    n_added = 0
    total = len(catalog_entries)
    last_progress = 0
    
    for idx, entry in enumerate(catalog_entries):
        # Progress bar (every 10%)
        progress = int((idx / total) * 100)
        if progress >= last_progress + 10:
            print(f"  Progress: {progress}% ({idx:,}/{total:,})")
            last_progress = progress
        
        # Find nearby existing stars
        bucket = (int(entry.ra_deg), int(entry.dec_deg))
        candidates = []
        for dra in [-1, 0, 1]:
            for ddec in [-1, 0, 1]:
                b = (bucket[0] + dra, bucket[1] + ddec)
                if b in existing_index:
                    candidates.extend(existing_index[b])
        
        # Check for match (10 arcsec = 0.003°)
        matched = False
        for idx_star in candidates:
            star = existing_stars[idx_star]
            dist = ((star.ra_deg - entry.ra_deg)**2 + 
                   (star.dec_deg - entry.dec_deg)**2)**0.5
            if dist < 0.003:
                # Match found — add cross-reference
                if "cross_ref" not in star.meta:
                    star.meta["cross_ref"] = {}
                
                if catalog_name == "Gaia DR3":
                    star.meta["cross_ref"]["Gaia"] = entry.catalog_id
                elif catalog_name == "Hipparcos":
                    star.meta["cross_ref"]["HIP"] = entry.catalog_id
                
                if entry.parallax_mas > 0:
                    star.meta["parallax_mas"] = entry.parallax_mas
                
                n_cross_ref += 1
                matched = True
                break
        
        if not matched:
            # New star — add to catalog
            distance_ly = 3262.0 / entry.parallax_mas if entry.parallax_mas > 0 else 1000.0
            
            if catalog_name == "Gaia DR3":
                uid = f"Gaia_{entry.catalog_id}"
                name = f"Gaia {entry.catalog_id}"
            else:
                uid = f"HIP_{entry.catalog_id}"
                name = f"HIP {entry.catalog_id}"
            
            new_star = SpaceObject(
                uid=uid,
                name=name,
                ra_deg=entry.ra_deg,
                dec_deg=entry.dec_deg,
                distance_ly=distance_ly,
                obj_class=ObjectClass.STAR,
                subtype=ObjectSubtype.MAIN_SEQUENCE,
                origin=ObjectOrigin.REAL,
                discovery=DiscoveryState.KNOWN,
                mag=entry.mag,
                bv_color=entry.bv_color,
                meta={
                    "catalog": catalog_name,
                    "cross_ref": {
                        "Gaia" if catalog_name == "Gaia DR3" else "HIP": entry.catalog_id
                    },
                    "parallax_mas": entry.parallax_mas,
                },
            )
            existing_stars.append(new_star)
            n_added += 1
    
    print(f"  Cross-referenced: {n_cross_ref:,}")
    print(f"  Added new: {n_added:,}")
    print(f"  Total: {len(existing_stars):,} stars")
    
    return existing_stars, n_cross_ref, n_added


# Example usage function
def load_all_catalogs_from_npz() -> List[Any]:
    """
    Load all available NPZ catalogs and merge them.
    
    Returns:
        List of SpaceObject instances with full cross-referencing
    """
    from universe.catalogue_loader import _load_embedded_stars
    
    # Start with Yale BSC (embedded, has proper names)
    print("Loading Yale BSC base catalog...")
    stars = _load_embedded_stars()
    
    # Find data dir relative to project root (works on any OS)
    _data_dir = Path(__file__).resolve().parent.parent / "catalogs" / "data"
    
    # Try to load Hipparcos NPZ
    hip_path = _data_dir / "hipparcos.npz"
    if hip_path.exists():
        hip_entries = load_npz_catalog(str(hip_path), "hipparcos")
        if hip_entries:
            stars, n_ref, n_add = merge_with_existing(hip_entries, stars, "Hipparcos")
    else:
        print(f"Hipparcos NPZ not found at {hip_path}")
    
    # Try to load Gaia NPZ
    gaia_path = _data_dir / "gaia.npz"
    if gaia_path.exists():
        gaia_entries = load_npz_catalog(str(gaia_path), "gaia")
        if gaia_entries:
            stars, n_ref, n_add = merge_with_existing(gaia_entries, stars, "Gaia DR3")
    else:
        print(f"Gaia NPZ not found at {gaia_path}")
    
    return stars
