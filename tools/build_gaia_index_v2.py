#!/usr/bin/env python3
"""
Build a compact 5° tile index from one or more Gaia DR3 export files.

This is the *v2* index format recommended for the planetarium:
- Uses a visual-like magnitude (V_sim) for filtering/rendering at wide FOV.
- Keeps Gaia G (optional) for debugging.
- Keeps BP-RP color (optional) for future star color/temperature rendering.

Input files:
  CSV or Parquet with columns (case-insensitive):
    required:
      ra, dec
      v_sim   (or: mag_v / v_mag)
    optional:
      source_id
      g_mag   (or: phot_g_mean_mag / mag_g)
      bp_rp

Output NPZ (default: data/gaia_index_v2.npz):
  tile_keys:   int32  [Ntiles]   # key=(tri<<16)|(tdi&0xFFFF), tri=floor(ra/5), tdi=floor((dec+90)/5)
  tile_starts: int64  [Ntiles]
  tile_ends:   int64  [Ntiles]
  ra_deg:      float32 [N]       # sorted by tile_key, then by mag_v ascending
  dec_deg:     float32 [N]
  mag_v:       float32 [N]       # V_sim (visual-like) magnitude used by renderer
  mag_g:       float32 [N]       # Gaia G (optional; may be NaN if missing)
  bp_rp:       float32 [N]       # optional; may be NaN if missing
  source_id:   int64   [N]       # optional; may be 0 if missing

Why tiles?
- Fast pan/zoom queries: only touch the tiles intersecting your view.

Usage examples:
  # single file
  python tools/build_gaia_index_v2.py --input data/gaia_dec_-10_0_g14.csv --output data/gaia_index_v2.npz

  # many files (glob)
  python tools/build_gaia_index_v2.py --input "data/gaia_dec_*_g14.csv" --output data/gaia_index_v2.npz

Notes:
- Don't try to export all Gaia. Use a magnitude cut (e.g., G<=14) and chunk (e.g., by declination).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import glob
import numpy as np
import pandas as pd

TILE_DEG = 5.0

def _tile_key(tri: np.ndarray, tdi: np.ndarray) -> np.int32:
    # pack 2x 16-bit signed-ish indices into int32 (stable across platforms)
    return np.int32(((tri.astype(np.int64) & 0xFFFF) << 16) | (tdi.astype(np.int64) & 0xFFFF))

def _pick_col(df: pd.DataFrame, *names: str) -> str | None:
    cols = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None

def _load_one(path: Path) -> dict[str, np.ndarray]:
    if path.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    ra_c  = _pick_col(df, "ra", "ra_deg")
    dec_c = _pick_col(df, "dec", "dec_deg")
    v_c   = _pick_col(df, "v_sim", "mag_v", "v_mag")
    if ra_c is None or dec_c is None or v_c is None:
        raise SystemExit(f"{path.name}: missing required columns. Need ra, dec, v_sim (or mag_v/v_mag). Found: {list(df.columns)[:20]} ...")

    g_c   = _pick_col(df, "g_mag", "phot_g_mean_mag", "mag_g")
    c_c   = _pick_col(df, "bp_rp")
    sid_c = _pick_col(df, "source_id")

    ra  = df[ra_c].to_numpy(dtype=np.float64)
    dec = df[dec_c].to_numpy(dtype=np.float64)
    mag_v = df[v_c].to_numpy(dtype=np.float32)

    mag_g = df[g_c].to_numpy(dtype=np.float32) if g_c is not None else np.full(mag_v.shape, np.nan, dtype=np.float32)
    bp_rp = df[c_c].to_numpy(dtype=np.float32) if c_c is not None else np.full(mag_v.shape, np.nan, dtype=np.float32)
    source_id = df[sid_c].to_numpy(dtype=np.int64) if sid_c is not None else np.zeros(mag_v.shape, dtype=np.int64)

    # Basic sanity filters
    m = np.isfinite(ra) & np.isfinite(dec) & np.isfinite(mag_v)
    if m.sum() != m.size:
        ra, dec, mag_v, mag_g, bp_rp, source_id = ra[m], dec[m], mag_v[m], mag_g[m], bp_rp[m], source_id[m]

    # Normalize RA to [0,360)
    ra %= 360.0
    return dict(ra=ra.astype(np.float32), dec=dec.astype(np.float32), mag_v=mag_v.astype(np.float32),
                mag_g=mag_g.astype(np.float32), bp_rp=bp_rp.astype(np.float32), source_id=source_id.astype(np.int64))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input file path or glob (CSV/Parquet). Quote globs on Windows.")
    ap.add_argument("--output", default="data/gaia_index_v2.npz", help="Output NPZ path")
    ap.add_argument("--mag-limit", type=float, default=None, help="Optional additional cut on mag_v (V_sim)")
    args = ap.parse_args()

    paths = [Path(p) for p in glob.glob(args.input)]
    if not paths:
        p = Path(args.input)
        if p.exists():
            paths = [p]
        else:
            raise SystemExit(f"No input files matched: {args.input}")

    all_ra = []
    all_dec = []
    all_mag_v = []
    all_mag_g = []
    all_bp_rp = []
    all_sid = []

    total = 0
    for p in sorted(paths):
        data = _load_one(p)
        ra, dec, mag_v, mag_g, bp_rp, sid = data["ra"], data["dec"], data["mag_v"], data["mag_g"], data["bp_rp"], data["source_id"]
        if args.mag_limit is not None:
            mm = mag_v <= np.float32(args.mag_limit)
            ra, dec, mag_v, mag_g, bp_rp, sid = ra[mm], dec[mm], mag_v[mm], mag_g[mm], bp_rp[mm], sid[mm]

        all_ra.append(ra); all_dec.append(dec); all_mag_v.append(mag_v); all_mag_g.append(mag_g); all_bp_rp.append(bp_rp); all_sid.append(sid)
        total += ra.size
        print(f"Loaded {p.name}: {ra.size:,} rows")

    ra = np.concatenate(all_ra) if len(all_ra) > 1 else all_ra[0]
    dec = np.concatenate(all_dec) if len(all_dec) > 1 else all_dec[0]
    mag_v = np.concatenate(all_mag_v) if len(all_mag_v) > 1 else all_mag_v[0]
    mag_g = np.concatenate(all_mag_g) if len(all_mag_g) > 1 else all_mag_g[0]
    bp_rp = np.concatenate(all_bp_rp) if len(all_bp_rp) > 1 else all_bp_rp[0]
    source_id = np.concatenate(all_sid) if len(all_sid) > 1 else all_sid[0]

    # Tile indices: RA 0..360 -> 0..71, Dec -90..+90 -> 0..35
    tri = np.floor(ra.astype(np.float64) / TILE_DEG).astype(np.int64)
    tdi = np.floor((dec.astype(np.float64) + 90.0) / TILE_DEG).astype(np.int64)
    keys = _tile_key(tri, tdi)

    # Sort by tile, then by visual magnitude (ascending)
    order = np.lexsort((mag_v, keys))
    keys = keys[order]
    ra = ra[order].astype(np.float32, copy=False)
    dec = dec[order].astype(np.float32, copy=False)
    mag_v = mag_v[order].astype(np.float32, copy=False)
    mag_g = mag_g[order].astype(np.float32, copy=False)
    bp_rp = bp_rp[order].astype(np.float32, copy=False)
    source_id = source_id[order].astype(np.int64, copy=False)

    uniq, starts = np.unique(keys, return_index=True)
    ends = np.empty_like(starts, dtype=np.int64)
    ends[:-1] = starts[1:]
    ends[-1] = keys.size

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        out,
        tile_keys=uniq.astype(np.int32),
        tile_starts=starts.astype(np.int64),
        tile_ends=ends.astype(np.int64),
        ra_deg=ra,
        dec_deg=dec,
        mag_v=mag_v,
        mag_g=mag_g,
        bp_rp=bp_rp,
        source_id=source_id,
    )

    print(f"Wrote {out} | stars={keys.size:,} | tiles={uniq.size:,}")

if __name__ == "__main__":
    main()
