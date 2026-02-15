
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional
import numpy as np

TILE_DEG = 5.0

def _tile_key(tri: np.ndarray, tdi: np.ndarray) -> np.int32:
    return np.int32(((tri.astype(np.int64) & 0xFFFF) << 16) | (tdi.astype(np.int64) & 0xFFFF))

def _tiles_for_box(ra_min: float, ra_max: float, dec_min: float, dec_max: float) -> np.ndarray:
    """
    Return tile_keys for a RA/Dec box. Handles RA wrap by allowing ra_min>ra_max.
    """
    dec_min = max(-90.0, dec_min)
    dec_max = min( 90.0, dec_max)
    # Tile indices
    tdi0 = int(np.floor((dec_min + 90.0) / TILE_DEG))
    tdi1 = int(np.floor((dec_max + 90.0) / TILE_DEG))
    tdi0 = max(0, min(35, tdi0))
    tdi1 = max(0, min(35, tdi1))

    def ra_range_to_tris(a0: float, a1: float) -> np.ndarray:
        tri0 = int(np.floor(a0 / TILE_DEG)) % 72
        tri1 = int(np.floor(a1 / TILE_DEG)) % 72
        if tri0 <= tri1:
            return np.arange(tri0, tri1 + 1, dtype=np.int32)
        return np.concatenate([np.arange(tri0, 72, dtype=np.int32), np.arange(0, tri1 + 1, dtype=np.int32)])

    tris = ra_range_to_tris(ra_min % 360.0, ra_max % 360.0)
    tdis = np.arange(tdi0, tdi1 + 1, dtype=np.int32)
    TR, TD = np.meshgrid(tris, tdis, indexing="xy")
    return _tile_key(TR.ravel(), TD.ravel())

@dataclass(slots=True)
class CatalogIndex:
    name: str
    path: Path
    # loaded arrays
    tile_keys: np.ndarray
    tile_starts: np.ndarray
    tile_ends: np.ndarray
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    mag: np.ndarray
    obj_id: Optional[np.ndarray] = None

    @classmethod
    def load_npz(cls, name: str, npz_path: str | Path, mag_field: str = "mag_v") -> "CatalogIndex":
        npz_path = Path(npz_path)
        z = np.load(npz_path, allow_pickle=False)
        tile_keys = z["tile_keys"].astype(np.int32)
        tile_starts = z["tile_starts"].astype(np.int64)
        tile_ends = z["tile_ends"].astype(np.int64)
        ra = z["ra_deg"].astype(np.float32)
        dec = z["dec_deg"].astype(np.float32)

        if mag_field in z.files:
            mag = z[mag_field].astype(np.float32)
        elif "mag" in z.files:
            mag = z["mag"].astype(np.float32)
        elif "mag_v" in z.files:
            mag = z["mag_v"].astype(np.float32)
        elif "phot_g_mean_mag" in z.files:
            mag = z["phot_g_mean_mag"].astype(np.float32)
        else:
            raise KeyError(f"Could not find magnitude field in {npz_path.name}. Fields: {z.files}")

        obj_id = None
        for cand in ("source_id", "hip", "hip_id", "id"):
            if cand in z.files:
                obj_id = z[cand].astype(np.int64)
                break

        return cls(
            name=name,
            path=npz_path,
            tile_keys=tile_keys,
            tile_starts=tile_starts,
            tile_ends=tile_ends,
            ra_deg=ra,
            dec_deg=dec,
            mag=mag,
            obj_id=obj_id,
        )

    def _tile_lookup(self, keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        For each tile_key in keys, return (starts, ends) arrays.
        Non-existing keys will have start=end=-1.
        """
        # tile_keys sorted
        idx = np.searchsorted(self.tile_keys, keys)
        starts = np.full(keys.shape, -1, dtype=np.int64)
        ends = np.full(keys.shape, -1, dtype=np.int64)
        in_bounds = (idx >= 0) & (idx < self.tile_keys.size)
        idx2 = idx[in_bounds]
        match = in_bounds.copy()
        match[in_bounds] = (self.tile_keys[idx2] == keys[in_bounds])
        good = match
        starts[good] = self.tile_starts[idx[good]]
        ends[good] = self.tile_ends[idx[good]]
        return starts, ends

    def iter_box(self, ra_min: float, ra_max: float, dec_min: float, dec_max: float,
                 mag_limit: float | None = None, max_items: int | None = None) -> Iterator[int]:
        """
        Yield indices into the arrays for stars in an RA/Dec box.
        NOTE: This is a coarse tile pre-filter + exact box filter.
        """
        keys = _tiles_for_box(ra_min, ra_max, dec_min, dec_max)
        starts, ends = self._tile_lookup(keys)

        # box filter helper with RA wrap
        rmin = ra_min % 360.0
        rmax = ra_max % 360.0
        wrap = rmin > rmax

        count = 0
        for s, e in zip(starts, ends):
            if s < 0 or e < 0 or e <= s:
                continue
            sl = slice(int(s), int(e))
            ra = self.ra_deg[sl]
            dec = self.dec_deg[sl]
            mag = self.mag[sl]

            if wrap:
                m_ra = (ra >= rmin) | (ra <= rmax)
            else:
                m_ra = (ra >= rmin) & (ra <= rmax)
            m_dec = (dec >= dec_min) & (dec <= dec_max)
            m = m_ra & m_dec
            if mag_limit is not None:
                m = m & (mag <= mag_limit)

            idxs = np.nonzero(m)[0]
            if idxs.size == 0:
                continue

            for i in idxs:
                yield int(s) + int(i)
                count += 1
                if max_items is not None and count >= max_items:
                    return
