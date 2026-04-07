"""
isea3h_native.py — Python ctypes wrapper for isea3h_bridge.so (dglib direct).

Drop this file next to isea3h_bridge.so, or set ISEA3H_BRIDGE_SO env var.

Usage:
    from isea3h_native import ISEA3HNative
    grid = ISEA3HNative(resolution=16)
    ids = grid.encode_points([(lat1, lon1), (lat2, lon2)])
    poly_verts = grid.get_cell_polygon(ids[0])  # -> list of (lon, lat)
"""

import os
import ctypes
from pathlib import Path

# ------------------------------------------------------------------
# Locate the shared library
# ------------------------------------------------------------------
_SO_PATH = os.environ.get(
    "ISEA3H_BRIDGE_SO",
    str(Path(__file__).parent / "isea3h_bridge.so")
)

try:
    _lib = ctypes.CDLL(_SO_PATH)
except OSError as e:
    raise ImportError(
        f"Cannot load isea3h_bridge.so from '{_SO_PATH}'. "
        f"Build it first with build.sh. Original error: {e}"
    )

# ------------------------------------------------------------------
# C function signatures
# ------------------------------------------------------------------
_lib.encode_points_batch.restype  = ctypes.c_int
_lib.encode_points_batch.argtypes = [
    ctypes.POINTER(ctypes.c_double),   # lats
    ctypes.POINTER(ctypes.c_double),   # lons
    ctypes.c_int,                       # n_points
    ctypes.c_int,                       # resolution
    ctypes.POINTER(ctypes.c_char_p),   # out_ids (array of char*)
]

_lib.get_cell_polygon.restype  = ctypes.c_int
_lib.get_cell_polygon.argtypes = [
    ctypes.c_char_p,                   # cell_id_str
    ctypes.c_int,                       # resolution
    ctypes.POINTER(ctypes.c_double),   # out_lons
    ctypes.POINTER(ctypes.c_double),   # out_lats
    ctypes.POINTER(ctypes.c_int),      # out_n_verts
    ctypes.c_int,                       # pts_per_edge
]

_lib.get_k_ring.restype  = ctypes.c_int
_lib.get_k_ring.argtypes = [
    ctypes.c_char_p,                   # cell_id_str
    ctypes.c_int,                       # resolution
    ctypes.c_int,                       # k
    ctypes.POINTER(ctypes.c_char_p),   # out_ids
    ctypes.POINTER(ctypes.c_int),      # out_count
    ctypes.c_int,                       # max_out
]

_lib.free_string_array.restype  = None
_lib.free_string_array.argtypes = [
    ctypes.POINTER(ctypes.c_char_p),
    ctypes.c_int,
]

_lib.reset_grid_state.restype  = None
_lib.reset_grid_state.argtypes = []

# ------------------------------------------------------------------
# Max polygon vertices: hexagon with pts_per_edge=3 → 6*3 = 18 pts
# Pentagon (at icosahedron vertices) with pts_per_edge=3 → 5*3 = 15 pts
# Use 64 as a safe upper bound.
# ------------------------------------------------------------------
_MAX_VERTS = 64


class ISEA3HNative:
    """
    In-process ISEA3H encoder/polygon-retriever backed by dglib.

    Parameters
    ----------
    resolution : int
        ISEA3H resolution level (e.g. 16 → ~1.18 km² cells).
    pts_per_edge : int
        Densification of polygon edges (1 = bare corners only,
        3 = 3 intermediate pts per edge for smoother boundary).
    """

    def __init__(self, resolution: int = 16, pts_per_edge: int = 3):
        self.resolution  = resolution
        self.pts_per_edge = pts_per_edge

    def encode_points(self, points: list[tuple[float, float]]) -> list[str]:
        """
        Batch encode (lat, lon) pairs → Z3_STRING cell IDs.
        Returns a list of strings, one per input point.
        """
        n = len(points)
        if n == 0:
            return []

        lats = (ctypes.c_double * n)(*[p[0] for p in points])
        lons = (ctypes.c_double * n)(*[p[1] for p in points])
        out  = (ctypes.c_char_p * n)()

        rc = _lib.encode_points_batch(lats, lons, n, self.resolution, out)
        if rc != 0:
            raise RuntimeError("encode_points_batch returned error")

        result = [out[i].decode("utf-8") for i in range(n)]
        _lib.free_string_array(out, n)
        return result

    def get_cell_polygon(self, cell_id: str) -> list[tuple[float, float]]:
        """
        Return polygon boundary as list of (lon, lat) tuples (WGS84 degrees).
        """
        out_lons    = (ctypes.c_double * _MAX_VERTS)()
        out_lats    = (ctypes.c_double * _MAX_VERTS)()
        out_n_verts = ctypes.c_int(0)

        rc = _lib.get_cell_polygon(
            cell_id.encode("utf-8"),
            self.resolution,
            out_lons, out_lats,
            ctypes.byref(out_n_verts),
            self.pts_per_edge,
        )
        if rc != 0:
            raise RuntimeError(f"get_cell_polygon failed for cell_id={cell_id!r}")

        n = out_n_verts.value
        return [(out_lons[i], out_lats[i]) for i in range(n)]

    def get_k_ring(self, cell_id: str, k: int = 1) -> list[str]:
        """
        Return the k-ring neighbors of the given cell.
        Currently only k=1 is supported.
        """
        if k > 1:
            raise NotImplementedError("ISEA3H bridge only supports k=1 currently.")
            
        max_out = 16  # safely enough for 1-ring neighbors
        out_ids = (ctypes.c_char_p * max_out)()
        out_count = ctypes.c_int(0)
        
        rc = _lib.get_k_ring(
            cell_id.encode("utf-8"),
            self.resolution,
            k,
            out_ids,
            ctypes.byref(out_count),
            max_out,
        )
        if rc != 0:
            raise RuntimeError(f"get_k_ring failed for cell_id={cell_id!r}")
            
        n = out_count.value
        result = [out_ids[i].decode("utf-8") for i in range(n)]
        _lib.free_string_array(out_ids, n)
        return result

    def reset(self):
        """Flush the cached grid state (needed if you change resolution)."""
        _lib.reset_grid_state()
