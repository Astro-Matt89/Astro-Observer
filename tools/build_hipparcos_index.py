#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import glob
import numpy as np
import pandas as pd

TILE_DEG = 5.0


def _tile_key(tri: np.ndarray, tdi: np.ndarray) -> np.int32:
    return np.int32(((tri.astype(np.int64) & 0xFFFF) << 16) | (tdi.astype(np.int64) & 0xFFFF))


def _pick_col(df: pd.DataFrame, *names: str) -> str | None:
    cols = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None


def _read_table(path: Path) -> pd.DataFrame:
    # TSV VizieR con commenti #
    try:
        return pd.read_csv(
            path,
            sep="\t",
            comment="#",
            engine="python",
            encoding="utf-8",
            on_bad_lines="skip",
        )
    except Exception:
        pass

    # CSV fallback
    try:
        return pd.read_csv(
            path,
            sep=",",
            comment="#",
            engine="python",
            encoding="utf-8",
            on_bad_lines="skip",
        )
    except Exception:
        pass

    # CSV EU fallback
    return pd.read_csv(
        path,
        sep=";",
        comment="#",
        engine="python",
        encoding="utf-8",
        on_bad_lines="skip",
    )


def _load_one(path: Path) -> dict[str, np.ndarray]:
    df = _read_table(path)

    # --- column resolution ---
    ra_c  = _pick_col(df, "ra", "raicrs", "_ra_icrs", "raj2000", "_raj2000")
    dec_c = _pick_col(df, "dec", "deicrs", "_de_icrs", "dej2000", "_dej2000")
    mag_c = _pick_col(df, "vmag", "v_mag", "mag_v", "v")

    if ra_c is None or dec_c is None or mag_c is None:
        raise SystemExit(
            f"{path.name}: missing ra/dec/vmag columns. Found: {list(df.columns)}"
        )

    hip_c = _pick_col(df, "hip", "hip_id", "hipparcos")
    bv_c  = _pick_col(df, "b-v", "b_v", "bv", "bminusv")

    # --- sanitize (CRITICAL FIX) ---
    df[ra_c]  = pd.to_numeric(df[ra_c], errors="coerce")
    df[dec_c] = pd.to_numeric(df[dec_c], errors="coerce")
    df[mag_c] = pd.to_numeric(df[mag_c], errors="coerce")

    if hip_c is not None:
        df[hip_c] = pd.to_numeric(df[hip_c], errors="coerce")

    df = df.dropna(subset=[ra_c, dec_c, mag_c])

    # --- numpy arrays ---
    ra  = df[ra_c].to_numpy(np.float64) % 360.0
    dec = df[dec_c].to_numpy(np.float64)
    mag = df[mag_c].to_numpy(np.float32)

    hip = (
        df[hip_c].to_numpy(np.int32)
        if hip_c is not None
        else np.zeros_like(mag, dtype=np.int32)
    )

    b_v = (
        df[bv_c].to_numpy(np.float32)
        if bv_c is not None
        else np.full_like(mag, np.nan, dtype=np.float32)
    )

    return {
        "ra": ra.astype(np.float32),
        "dec": dec.astype(np.float32),
        "mag_v": mag.astype(np.float32),
        "hip": hip.astype(np.int32),
        "b_v": b_v.astype(np.float32),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="data/hipparcos_index.npz")
    args = ap.parse_args()

    paths = sorted(Path(p) for p in glob.glob(args.input))
    if not paths and Path(args.input).exists():
        paths = [Path(args.input)]

    if not paths:
        raise SystemExit(f"No input files matched: {args.input}")

    chunks = [_load_one(p) for p in paths]

    ra    = np.concatenate([c["ra"] for c in chunks])
    dec   = np.concatenate([c["dec"] for c in chunks])
    mag_v = np.concatenate([c["mag_v"] for c in chunks])
    hip   = np.concatenate([c["hip"] for c in chunks])
    b_v   = np.concatenate([c["b_v"] for c in chunks])

    # --- tiling ---
    tri = np.floor(ra / TILE_DEG).astype(np.int32)
    tdi = np.floor((dec + 90.0) / TILE_DEG).astype(np.int32)
    tile_keys = _tile_key(tri, tdi)

    order = np.lexsort((mag_v, tile_keys))
    tile_keys = tile_keys[order]
    ra, dec, mag_v, hip, b_v = ra[order], dec[order], mag_v[order], hip[order], b_v[order]

    uniq, starts = np.unique(tile_keys, return_index=True)
    ends = np.empty_like(starts)
    ends[:-1] = starts[1:]
    ends[-1] = tile_keys.size

    out = Path(args.output)
    if not out.is_absolute():
        out = Path(__file__).resolve().parents[1] / out
    out.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        out,
        tile_keys=uniq.astype(np.int32),
        tile_starts=starts.astype(np.int64),
        tile_ends=ends.astype(np.int64),
        ra_deg=ra.astype(np.float32),
        dec_deg=dec.astype(np.float32),
        mag_v=mag_v.astype(np.float32),
        hip=hip.astype(np.int32),
        b_v=b_v.astype(np.float32),
    )

    print(f"[Hipparcos] wrote {out}  stars={ra.size}  tiles={uniq.size}")


if __name__ == "__main__":
    main()
