# Star Catalogs — NPZ Implementation Guide

## Overview

The game supports loading massive star catalogs (Gaia DR3, Hipparcos) from NumPy compressed archives (`.npz` files). This allows hundreds of thousands of stars with automatic deduplication and cross-referencing.

## Quick Start

### 1. Prepare your NPZ files

Place your catalog files in:
```
/home/claude/catalogs/data/hipparcos.npz
/home/claude/catalogs/data/gaia.npz
```

### 2. NPZ File Format

**Hipparcos** expected fields:
- `hip` or `hip_id`: HIP identifier (int)
- `ra` or `ra_deg`: Right Ascension in degrees (float)
- `dec` or `dec_deg`: Declination in degrees (float)
- `vmag` or `mag`: Visual magnitude (float)
- `parallax` or `plx`: Parallax in milliarcseconds (float)
- `bv` or `b_v`: B-V color index (float, optional)

**Gaia DR3** expected fields:
- `source_id` or `gaia_id`: Gaia source identifier (int64)
- `ra` or `ra_deg`: Right Ascension in degrees (float)
- `dec` or `dec_deg`: Declination in degrees (float)
- `phot_g_mean_mag` or `mag` or `gmag`: G-band magnitude (float)
- `parallax`: Parallax in milliarcseconds (float, optional)
- `bp_rp` or `bprp`: BP-RP color (float, optional)

### 3. Test the loader

```bash
python3 /home/claude/test_npz_loader.py
```

This will:
- Check if NPZ files exist
- Parse and validate structure
- Show sample data
- Test merging with Yale BSC base catalog
- Display statistics

### 4. Use in game

The game automatically detects NPZ files at startup. If found, it loads the full catalogs. Otherwise, it falls back to the embedded Yale BSC + Hipparcos subset (~4300 stars).

## Creating NPZ Files

### From Hipparcos catalog (hip_main.dat)

```python
import numpy as np
import pandas as pd

# Read Hipparcos main catalog
# Download from: https://cdsarc.cds.unistra.fr/ftp/cats/I/239/
df = pd.read_fwf('hip_main.dat', colspecs=[...])  # define column specs

# Filter and prepare
df = df[df['Vmag'] < 9.0]  # mag limit for gameplay

np.savez_compressed('hipparcos.npz',
    hip=df['HIP'].values,
    ra=df['RA'].values,
    dec=df['Dec'].values,
    vmag=df['Vmag'].values,
    parallax=df['Plx'].values,
    bv=df['B-V'].values
)
```

### From Gaia DR3

```python
import numpy as np
from astroquery.gaia import Gaia

# Query Gaia (example: bright stars)
job = Gaia.launch_job("""
    SELECT source_id, ra, dec, phot_g_mean_mag, parallax, bp_rp
    FROM gaiadr3.gaia_source
    WHERE phot_g_mean_mag < 12.0
""")
result = job.get_results()

np.savez_compressed('gaia.npz',
    source_id=result['source_id'].data,
    ra=result['ra'].data,
    dec=result['dec'].data,
    phot_g_mean_mag=result['phot_g_mean_mag'].data,
    parallax=result['parallax'].data,
    bp_rp=result['bp_rp'].data
)
```

## Merge Strategy

The loader implements smart deduplication:

1. **Yale BSC** (embedded) is loaded first — has proper star names
2. **Hipparcos** stars are matched by position (10 arcsec threshold)
   - Match found → adds cross-reference HIP ID to Yale star
   - No match → adds new star with `uid="HIP_xxxxx"`
3. **Gaia** stars are matched similarly
   - Match found → adds Gaia source_id to cross-reference
   - No match → adds new star with `uid="Gaia_xxxxx"`

Result: Every star has a unique primary ID plus cross-references to all catalogs where it appears.

## Cross-Reference Structure

```python
SpaceObject(
    uid="YBS_0001",           # Primary ID (Yale BSC)
    name="Sirius",            # Proper name from Yale
    meta={
        "catalog": "Yale BSC",
        "cross_ref": {
            "HIP": 32349,      # Hipparcos
            "Gaia": 2947050466531873024,  # Gaia DR3
        },
        "parallax_mas": 379.21,
    }
)
```

## Performance Notes

- **Spatial index**: Uses 1° grid buckets for O(1) nearby star queries
- **Magnitude filtering**: 
  - Hipparcos: mag < 9.0
  - Gaia: mag < 12.0 (gameplay limit)
- **Memory**: ~50 MB for 100k stars (NumPy arrays in SpaceObject)

## File Sizes

Typical NPZ file sizes:
- Hipparcos full (118k stars): ~2-3 MB compressed
- Gaia subset (mag<12, ~500k stars): ~15-20 MB compressed
- Gaia full (2 billion stars): impractical for real-time use

## Fallback Behavior

If no NPZ files are found, the game automatically uses embedded catalogs:
- Yale BSC: 4269 stars (proper names, constellations)
- Hipparcos subset: 130 brightest stars (mag < 5.5)
- Total: ~4300 stars, sufficient for gameplay

## Integration with Game Systems

Stars from NPZ catalogs are full `SpaceObject` instances with:
- Accurate RA/Dec positions
- Distance from parallax (3262 ly / parallax_mas)
- B-V color index for realistic rendering
- Cross-references for research/documentation
- Compatible with all existing game systems (sky chart, imaging, catalog browser)

## Troubleshooting

**"Keys: [...] — Error: Missing required fields"**
→ Check NPZ field names match expected format (see section 2)

**"Cannot auto-detect catalog type"**
→ Specify catalog_type explicitly: `load_npz_catalog(path, "gaia")`

**Stars appearing in wrong positions**
→ Verify RA/Dec are in degrees (not radians or hours)

**Memory issues with large catalogs**
→ Increase magnitude filter threshold in npz_loader.py

## Next Steps

After loading NPZ catalogs:
1. Test in Sky Chart — verify star positions
2. Check constellation rendering with more stars
3. Enable dynamic magnitude limiting based on FOV
4. Add proper motion for nearby stars (if available in catalog)
