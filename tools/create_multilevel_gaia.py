#!/usr/bin/env python3
"""
Multi-Level Gaia NPZ Creator

Creates 3-level star database for dynamic loading:
- Level 1 (bright): mag < 7  → always loaded (~20k stars)
- Level 2 (medium): mag 7-10 → loaded when FOV < 60° (~400k stars)
- Level 3 (faint): mag 10-12 → loaded when FOV < 5° (~1.5M stars)

Usage:
    python3 create_multilevel_gaia.py gaia_full.npz output_dir/

Output:
    output_dir/gaia_level1.npz (~1 MB)
    output_dir/gaia_level2.npz (~15 MB)
    output_dir/gaia_level3.npz (~60 MB)
"""

import sys
import numpy as np
from pathlib import Path

def create_multilevel(input_path, output_dir):
    print(f"Loading {input_path}...")
    data = np.load(input_path)
    
    ra = data['ra_deg'] if 'ra_deg' in data else data.get('ra')
    dec = data['dec_deg'] if 'dec_deg' in data else data.get('dec')
    mag = (data.get('mag_g') if 'mag_g' in data else
           data.get('phot_g_mean_mag') if 'phot_g_mean_mag' in data else
           data.get('mag') if 'mag' in data else
           data.get('gmag'))
    source_id = data.get('source_id') if 'source_id' in data else data.get('gaia_id')
    parallax = data.get('parallax') if 'parallax' in data else None
    bp_rp = data.get('bp_rp') if 'bp_rp' in data else data.get('bprp')
    
    if ra is None or dec is None or mag is None:
        print(f"ERROR: Missing fields. Available: {list(data.keys())}")
        sys.exit(1)
    
    n_total = len(ra)
    print(f"Total: {n_total:,} stars")
    
    # Define levels
    levels = [
        ("level1_bright", mag < 7.0),
        ("level2_medium", (mag >= 7.0) & (mag < 10.0)),
        ("level3_faint",  (mag >= 10.0) & (mag < 12.0)),
    ]
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for name, mask in levels:
        n = mask.sum()
        print(f"\n{name}: {n:,} stars ({n/n_total*100:.1f}%)")
        
        level_data = {
            'ra': ra[mask].astype(np.float32),
            'dec': dec[mask].astype(np.float32),
            'phot_g_mean_mag': mag[mask].astype(np.float32),
        }
        
        if source_id is not None:
            level_data['source_id'] = source_id[mask]
        if parallax is not None:
            level_data['parallax'] = parallax[mask].astype(np.float32)
        if bp_rp is not None:
            level_data['bp_rp'] = bp_rp[mask].astype(np.float32)
        
        out_path = output_dir / f"gaia_{name}.npz"
        np.savez_compressed(out_path, **level_data)
        
        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f"  Saved: {out_path} ({size_mb:.1f} MB)")
    
    print(f"\n✓ Created 3-level database in {output_dir}/")
    print(f"  Upload all 3 files to catalogs/data/")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    create_multilevel(sys.argv[1], sys.argv[2])
