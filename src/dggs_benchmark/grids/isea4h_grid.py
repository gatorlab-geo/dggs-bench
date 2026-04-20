import warnings
import numpy as np
from shapely.geometry import Point, Polygon
from .base import BaseGrid
from typing import List, Tuple

try:
    from .dglib_bridge.isea4h_native import ISEA4HNative
    _dglib_available = True
except ImportError as e:
    _dglib_available = False
    warnings.warn(f"ISEA4H is disabled. Failed to load dglib bridge: {e}")


class ISEA4HGrid(BaseGrid):
    """
    DGGRID ISEA4H Grid mapping implementation.
    
    ISEA4H is the Aperture-4 variant of the ISEA hexagonal DGGS. Each parent
    cell subdivides into 4 children (vs 3 for ISEA3H), producing denser
    coverage per resolution level. This is the canonical equal-area hexagonal
    DGGS used in the OGC DGGS Abstract Specification (Topic 21).

    Like ISEA3H, this wrapper uses a custom C-ABI bridge directly over
    DGGRID's internal `dglib` C++ library for safe, pure in-process batch
    encoding and geometric polygon retrieval.
    """
    def __init__(self):
        if not _dglib_available:
            raise RuntimeError("ISEA4H is disabled. dglib bridge failed to load.")
            
        # Cache bridge instances per resolution to avoid re-constructing
        # the global RF network for every point.
        self._bridges = {}

    def _get_bridge(self, resolution: int) -> 'ISEA4HNative':
        if resolution not in self._bridges:
            # pts_per_edge=1 returns strict topological corners (6 for hex, 5 for pent).
            # Critical for apples-to-apples Angular Deviation comparison with H3.
            self._bridges[resolution] = ISEA4HNative(resolution, pts_per_edge=1)
        return self._bridges[resolution]

    @property
    def name(self) -> str:
        return "ISEA4H (Aperture 4 Hexagons)"

    @property
    def is_equal_area(self) -> bool:
        return True

    def prefetch_points(self, points: list[tuple[float, float]], resolution: int):
        """
        Batch encode coordinates to Z3_STRING IDs in-process using dglib.
        Polygons are so fast via the bridge we don't need to prefetch them.
        """
        if not _dglib_available or not points: 
            return
            
        print(f"    [ISEA4H] Batch-processing {len(points)} points through dglib bridge (Res {resolution})...")
        bridge = self._get_bridge(resolution)
        
        if not hasattr(self, '_prefetched_cells'):
            self._prefetched_cells = {}
            
        # Encode all
        cell_ids = bridge.encode_points(points)
        
        # Populate prefetch dictionary
        for (lat, lon), cell_id in zip(points, cell_ids):
            self._prefetched_cells[(lat, lon)] = cell_id

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into an ISEA4H Z3_STRING ID.
        """
        if hasattr(self, '_prefetched_cells') and (lat, lon) in self._prefetched_cells:
            return self._prefetched_cells[(lat, lon)]
            
        # Fallback to single-point via bridge
        bridge = self._get_bridge(resolution)
        return bridge.encode_points([(lat, lon)])[0]

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Retrieves the exact Shapely polygon for a given ISEA4H cell ID.
        """
        # Infer resolution from Z3 string length (Z3 string length = 2 + resolution)
        resolution = len(cell_id) - 2
        bridge = self._get_bridge(resolution)
        
        verts_wgs = bridge.get_cell_polygon(cell_id)
        return Polygon(verts_wgs)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the cell center using angular vertex averaging.
        This bypasses the 'planar fallacy' of standard bounding-box centroids.
        """
        poly = self.get_cell_polygon(cell_id)
        coords = list(poly.exterior.coords)[:-1] # Drop closed point
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        avg_lat = sum(lats) / len(lats)
        
        # Longitude averaging with wrap-around handling
        shifted_lons = [(lon if lon >= 0 else lon + 360) for lon in lons]
        avg_lon = sum(shifted_lons) / len(shifted_lons)
        if avg_lon > 180:
            avg_lon -= 360
        return float(avg_lat), float(avg_lon)

    def get_covering(self, polygon: Polygon, resolution: int) -> list[str]:
        """
        Returns all ISEA4H cells covering the polygon.
        Since dglib lacks a native 'polyfill', we use a dense boundary tracer
        and interior rasterizer tightly scaled to the specified resolution.
        """
        bounds = polygon.bounds # (minx, miny, maxx, maxy)
        # ISEA4H aperture 4 → cells shrink faster per resolution than ISEA3H
        step_degrees = max(0.01, 15.0 / (2.0 ** resolution))
        
        lons = np.arange(bounds[0], bounds[2] + step_degrees, step_degrees)
        lats = np.arange(bounds[1], bounds[3] + step_degrees, step_degrees)
        
        grid_points = []
        # Exquisite boundary tracing
        dense_poly = polygon.segmentize(step_degrees)
        for pt in dense_poly.exterior.coords:
            grid_points.append((pt[1], pt[0])) # lat, lon
            
        for interior in dense_poly.interiors:
            for pt in interior.coords:
                grid_points.append((pt[1], pt[0]))
                
        # Interior rasterization
        if len(lons) > 0 and len(lats) > 0:
            lon_grid, lat_grid = np.meshgrid(lons, lats)
            import geopandas as gpd
            pts = gpd.GeoSeries(gpd.points_from_xy(lon_grid.flatten(), lat_grid.flatten()))
            pts_inside = pts[pts.within(polygon)]
            for pt in pts_inside:
                grid_points.append((pt.y, pt.x))
                
        if not grid_points:
            grid_points = [(polygon.centroid.y, polygon.centroid.x)]
            
        bridge = self._get_bridge(resolution)
        cell_ids = bridge.encode_points(grid_points)
        return list(set(cell_ids))

    def get_k_ring(self, cell_id: str, k: int = 1) -> list[str]:
        """
        Returns k-ring neighbors.
        """
        # Infer resolution from Z3 string length (Z3 string length = 2 + resolution)
        resolution = len(cell_id) - 2
        bridge = self._get_bridge(resolution)
        return bridge.get_k_ring(cell_id, k)

    def get_parent(self, cell_id: str) -> str:
        raise NotImplementedError("ISEA4H hierarchy traversal is not benchmarked in this release.")
