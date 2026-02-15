"""
Catalogue Loader

Converts existing Messier/NGC catalogue data into SpaceObject instances
for the Universe. This is the bridge between the raw data files and the
3D universe representation.
"""

from __future__ import annotations
from typing import List

from .space_object import (
    SpaceObject, ObjectClass, ObjectSubtype, ObjectOrigin, DiscoveryState
)


# ---------------------------------------------------------------------------
# Type mapping from old catalog strings → new enums
# ---------------------------------------------------------------------------

# Maps old DSOType string values → (ObjectClass, ObjectSubtype)
_TYPE_MAP = {
    # Nebulae
    "HII":  (ObjectClass.NEBULA,   ObjectSubtype.EMISSION),
    "RN":   (ObjectClass.NEBULA,   ObjectSubtype.REFLECTION),
    "PN":   (ObjectClass.NEBULA,   ObjectSubtype.PLANETARY),
    "SNR":  (ObjectClass.NEBULA,   ObjectSubtype.SUPERNOVA_REMNANT),
    "DN":   (ObjectClass.NEBULA,   ObjectSubtype.DARK),
    # Galaxies
    "SG":   (ObjectClass.GALAXY,   ObjectSubtype.SPIRAL),
    "EG":   (ObjectClass.GALAXY,   ObjectSubtype.ELLIPTICAL),
    "IG":   (ObjectClass.GALAXY,   ObjectSubtype.IRREGULAR),
    "LG":   (ObjectClass.GALAXY,   ObjectSubtype.LENTICULAR),
    # Clusters
    "OC":   (ObjectClass.CLUSTER,  ObjectSubtype.OPEN_CLUSTER),
    "GC":   (ObjectClass.CLUSTER,  ObjectSubtype.GLOBULAR_CLUSTER),
    "GCL":  (ObjectClass.CLUSTER,  ObjectSubtype.GALAXY_CLUSTER),
}

def _map_type(type_str: str):
    return _TYPE_MAP.get(type_str, (ObjectClass.UNKNOWN, ObjectSubtype.UNKNOWN))


# ---------------------------------------------------------------------------
# Load Messier catalogue
# ---------------------------------------------------------------------------

def load_messier() -> List[SpaceObject]:
    """
    Load all 110 Messier objects as SpaceObject instances.
    """
    from catalogs.messier_data import MESSIER_DATA

    objects = []
    for entry in MESSIER_DATA:
        m_num, name, ra, dec, type_str, mag, size, dist, constellation, desc = entry

        obj_class, subtype = _map_type(type_str)

        obj = SpaceObject(
            uid=f"M{m_num}",
            name=name,
            ra_deg=float(ra),
            dec_deg=float(dec),
            distance_ly=float(dist),
            obj_class=obj_class,
            subtype=subtype,
            origin=ObjectOrigin.REAL,
            discovery=DiscoveryState.KNOWN,
            mag=float(mag),
            size_arcmin=float(size),
            size_minor_arcmin=float(size) * 0.7,
            constellation=constellation,
            description=desc,
            meta={"catalog": "M", "catalog_num": m_num},
        )
        objects.append(obj)

    return objects


# ---------------------------------------------------------------------------
# Load NGC catalogue
# ---------------------------------------------------------------------------

def load_ngc() -> List[SpaceObject]:
    """
    Load selected NGC objects as SpaceObject instances.
    """
    from catalogs.ngc_data import NGC_DATA

    objects = []
    for entry in NGC_DATA:
        ngc_num, name, ra, dec, type_str, mag, size, dist, constellation, desc = entry

        obj_class, subtype = _map_type(type_str)

        obj = SpaceObject(
            uid=f"NGC{ngc_num}",
            name=name,
            ra_deg=float(ra),
            dec_deg=float(dec),
            distance_ly=float(dist),
            obj_class=obj_class,
            subtype=subtype,
            origin=ObjectOrigin.REAL,
            discovery=DiscoveryState.KNOWN,
            mag=float(mag),
            size_arcmin=float(size),
            size_minor_arcmin=float(size) * 0.7,
            constellation=constellation,
            description=desc,
            meta={"catalog": "NGC", "catalog_num": ngc_num},
        )
        objects.append(obj)

    return objects


# ---------------------------------------------------------------------------
# Load star catalogue
# ---------------------------------------------------------------------------

def load_stars() -> List[SpaceObject]:
    """
    Load bright stars with automatic catalog detection.
    
    Priority:
    1. Check for NPZ catalogs (Gaia/Hipparcos) in catalogs/data/ (relative to project)
    2. Fall back to embedded Yale BSC + Hipparcos subset
    
    If NPZ files exist: loads full catalogs with deduplication
    Otherwise: uses embedded bright star subset (~4300 stars)
    """
    from pathlib import Path
    
    # Find NPZ files relative to project root (works on any OS)
    _project_root = Path(__file__).resolve().parent.parent  # universe/ -> project root
    _data_dir = _project_root / "catalogs" / "data"
    
    npz_hip  = _data_dir / "hipparcos.npz"
    npz_gaia = _data_dir / "gaia.npz"
    
    if npz_hip.exists() or npz_gaia.exists():
        # Use NPZ loader for full catalogs
        print("NPZ catalogs detected — loading full star database...")
        from universe.npz_loader import load_all_catalogs_from_npz
        return load_all_catalogs_from_npz()
    
    # Fall back to embedded catalogs
    print("Loading embedded star catalogs (Yale BSC + Hipparcos subset)...")
    return _load_embedded_stars()


def _load_embedded_stars() -> List[SpaceObject]:
    """
    Load embedded star catalogs (Yale BSC + Hipparcos bright subset).
    This is the fallback when NPZ files are not available.
    """
    from catalogs.star_catalog import STAR_CATALOG
    from catalogs.hipparcos_data import HIPPARCOS_BRIGHT

    # Known distances for brightest stars (ly)
    KNOWN_DISTANCES = {
        "Sirius":     8.6,   "Canopus":    310,   "Arcturus":   37,
        "Vega":       25,    "Capella":    43,    "Rigel":      860,
        "Procyon":    11.5,  "Achernar":   139,   "Betelgeuse": 700,
        "Hadar":      390,   "Altair":     17,    "Acrux":      320,
        "Aldebaran":  65,    "Antares":    550,   "Spica":      250,
        "Pollux":     34,    "Fomalhaut":  25,    "Deneb":      2600,
        "Mimosa":     280,   "Regulus":    79,    "Adhara":     430,
        "Castor":     51,    "Shaula":     700,   "Gacrux":     88,
        "Bellatrix":  240,   "Elnath":     130,   "Miaplacidus":110,
        "Alnilam":    2000,  "Alnitak":    1200,  "Mintaka":    900,
        "Saiph":      720,   "Meissa":     1100,  "Dubhe":      124,
        "Merak":      79,    "Phecda":     84,    "Megrez":     81,
        "Alioth":     82,    "Mizar":      78,    "Alkaid":     101,
        "Denebola":   36,    "Algieba":    130,   "Zosma":      58,
    }

    # === PART 1: Load Yale BSC ===
    yale_objects = []
    for i, (name, ra, dec, mag, bv) in enumerate(STAR_CATALOG):
        dist = KNOWN_DISTANCES.get(name, 200.0)
        
        obj = SpaceObject(
            uid=f"YBS_{i:04d}",
            name=name,
            ra_deg=float(ra),
            dec_deg=float(dec),
            distance_ly=dist,
            obj_class=ObjectClass.STAR,
            subtype=ObjectSubtype.MAIN_SEQUENCE,
            origin=ObjectOrigin.REAL,
            discovery=DiscoveryState.KNOWN,
            mag=float(mag),
            bv_color=float(bv),
            meta={"catalog": "Yale BSC", "ybs_index": i},
        )
        yale_objects.append(obj)

    # === PART 2: Load Hipparcos and merge ===
    # Build spatial index for fast matching (simple O(n²) for now)
    def find_yale_match(hip_ra, hip_dec, threshold_deg=0.003):
        """Find Yale star within 10 arcsec (0.003°) of Hipparcos position"""
        best = None
        best_dist = threshold_deg
        for ybs in yale_objects:
            dist = ((ybs.ra_deg - hip_ra)**2 + (ybs.dec_deg - hip_dec)**2)**0.5
            if dist < best_dist:
                best_dist = dist
                best = ybs
        return best

    hip_added = 0
    hip_cross_ref = 0
    
    for hip_id, ra, dec, mag, parallax_mas, bv in HIPPARCOS_BRIGHT:
        # Check for existing Yale match
        yale_match = find_yale_match(ra, dec)
        
        if yale_match:
            # Star already in Yale — add cross-reference
            if "cross_ref" not in yale_match.meta:
                yale_match.meta["cross_ref"] = {}
            yale_match.meta["cross_ref"]["HIP"] = hip_id
            if parallax_mas > 0:
                yale_match.meta["parallax_mas"] = parallax_mas
            hip_cross_ref += 1
        else:
            # New star — add to catalog
            dist = 3262.0 / parallax_mas if parallax_mas > 0 else 500.0
            
            obj = SpaceObject(
                uid=f"HIP_{hip_id}",
                name=f"HIP {hip_id}",
                ra_deg=float(ra),
                dec_deg=float(dec),
                distance_ly=dist,
                obj_class=ObjectClass.STAR,
                subtype=ObjectSubtype.MAIN_SEQUENCE,
                origin=ObjectOrigin.REAL,
                discovery=DiscoveryState.KNOWN,
                mag=float(mag),
                bv_color=float(bv),
                meta={
                    "catalog": "Hipparcos",
                    "cross_ref": {"HIP": hip_id},
                    "parallax_mas": parallax_mas,
                },
            )
            yale_objects.append(obj)
            hip_added += 1

    print(f"  Yale BSC: {len(STAR_CATALOG)} stars")
    print(f"  Hipparcos cross-ref: {hip_cross_ref}")
    print(f"  Hipparcos added: {hip_added}")
    print(f"  Total: {len(yale_objects)} stars")
    
    return yale_objects
