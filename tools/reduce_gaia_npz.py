#!/usr/bin/env python3
"""
Gaia NPZ Reducer

Reduces large Gaia DR3 NPZ files (300MB+) to gameplay-optimized subset (~15MB).

Usage:
    python3 reduce_gaia_npz.py input_gaia.npz output_gaia_reduced.npz

Filters:
    - Magnitude < 10.0 (bright enough for gameplay)
    - Dec > -50° (visible from mid-northern latitudes)
    - Valid parallax (distance measurements)

This reduces ~2M stars to ~50k stars while keeping all important objects.
"""

import sys
import numpy as np

def reduce_gaia_npz(input_path, output_path, mag_limit=10.0, dec_limit=-50.0):
    """
    Reduce Gaia NPZ to gameplay subset.
    
    Args:
        input_path: Input NPZ file (large)
        output_path: Output NPZ file (reduced)
        mag_limit: Maximum magnitude (default 10.0)
        dec_limit: Minimum declination (default -50°)
    """
    print(f"Loading {input_path}...")
    data = np.load(input_path)
    
    keys = list(data.keys())
    print(f"  Keys: {keys}")
    
    # Detect field names (try multiple variants)
    ra = data['ra_deg'] if 'ra_deg' in data else data.get('ra')
    dec = data['dec_deg'] if 'dec_deg' in data else data.get('dec')
    mag = (data.get('mag_g') if 'mag_g' in data else
           data.get('phot_g_mean_mag') if 'phot_g_mean_mag' in data else
           data.get('mag') if 'mag' in data else
           data.get('gmag') if 'gmag' in data else
           data.get('mag_v'))
    source_id = data.get('source_id') if 'source_id' in data else data.get('gaia_id')
    parallax = data.get('parallax') if 'parallax' in data else None
    bp_rp = data.get('bp_rp') if 'bp_rp' in data else data.get('bprp')
    
    if ra is None or dec is None or mag is None:
        print(f"  ERROR: Cannot find ra/dec/mag in keys: {keys}")
        print(f"  Tried:")
        print(f"    RA: ra_deg, ra")
        print(f"    Dec: dec_deg, dec")
        print(f"    Mag: mag_g, phot_g_mean_mag, mag, gmag, mag_v")
        sys.exit(1)
    
    n_total = len(ra)
    print(f"  Total stars: {n_total:,}")
    
    # Apply filters
    print(f"  Applying filters: mag<{mag_limit}, dec>{dec_limit}°")
    
    mask = (mag < mag_limit) & (dec > dec_limit)
    
    # Optionally filter for valid parallax
    if parallax is not None:
        print(f"    + valid parallax")
        mask = mask & (parallax > 0) & ~np.isnan(parallax)
    
    n_filtered = mask.sum()
    print(f"  Filtered: {n_filtered:,} stars ({n_filtered/n_total*100:.1f}%)")
    
    # Build output dictionary
    output_data = {}
    
    # Always include these (use consistent names)
    output_data['ra'] = ra[mask].astype(np.float32)
    output_data['dec'] = dec[mask].astype(np.float32)
    output_data['mag'] = mag[mask].astype(np.float32)  # Renamed for consistency
    
    # Optional fields
    if source_id is not None:
        output_data['source_id'] = source_id[mask]
    if parallax is not None:
        output_data['parallax'] = parallax[mask].astype(np.float32)
    if bp_rp is not None:
        output_data['bp_rp'] = bp_rp[mask].astype(np.float32)
    
    # Save compressed
    print(f"  Saving to {output_path}...")
    np.savez_compressed(output_path, **output_data)
    
    # Report file sizes
    import os
    input_size = os.path.getsize(input_path) / 1024 / 1024
    output_size = os.path.getsize(output_path) / 1024 / 1024
    
    print(f"  Input: {input_size:.1f} MB")
    print(f"  Output: {output_size:.1f} MB")
    print(f"  Reduction: {(1 - output_size/input_size)*100:.1f}%")
    print(f"\n✓ Done! Upload {output_path} to the game.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nExample:")
        print("  python3 reduce_gaia_npz.py gaia_full.npz gaia_game.npz")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    reduce_gaia_npz(input_file, output_file)
