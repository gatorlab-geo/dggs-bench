import mercantile
from typing import List, Tuple
from shapely.geometry import Polygon
from .base import BaseGrid


class XYZTileGrid(BaseGrid):
    """
    Wraps the XYZ slippy-map tile schema used by web mapping platforms
    (OpenStreetMap, Google Maps, Mapbox, etc.), also formalised as WMTS
    (Web Map Tile Service) in the OGC standard.

    The coordinate system:
        Z (zoom)   : 0 = whole world in one tile; each +1 doubles resolution
        X (column) : 0 → 2^Z - 1, left to right
        Y (row)    : 0 → 2^Z - 1, top (north) to bottom (south)

    The projection is Web Mercator (EPSG:3857), but the resolution parameter
    here is the zoom level Z rather than an edge length in metres — making
    it directly comparable to other hierarchical DGGS systems.

    Tile IDs are encoded as the string  "{z}/{x}/{y}"  for human readability
    and to avoid integer overflow at high zoom levels.

    Note: XYZ tiles are NOT equal-area. Polar tiles become arbitrarily
    stretched at high latitudes — this is the 'Planar Fallacy' in action.
    mercantile clips input latitudes to the valid Mercator range [-85.051129°, 85.051129°].
    """

    @property
    def name(self) -> str:
        return "XYZ Tiles (WMTS / Slippy Map)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a WGS84 coordinate into an XYZ tile ID string "{z}/{x}/{y}".

        :param lat:        WGS84 latitude  (must be within ±85.051129°)
        :param lon:        WGS84 longitude (-180 … 180)
        :param resolution: Zoom level Z (integer, typically 0–22)
        :returns:          Tile ID string, e.g. "13/2412/3080"
        """
        # Web Mercator is undefined beyond ±85.051129° — reject polar coordinates.
        # Experiments that expect polar points should catch this per-point.
        if lat > 85.05112878 or lat < -85.05112878:
            raise ValueError(
                f"Latitude {lat:.4f} is outside the Web Mercator range (±85.05°)."
            )
        
        tile = mercantile.tile(lon, lat, resolution)
        return f"{tile.z}/{tile.x}/{tile.y}"

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Converts an XYZ tile ID string back to its WGS84 bounding rectangle.

        The four corners are derived from the tile's lng/lat bounding box and
        returned as a closed Shapely Polygon in (lon, lat) order.
        """
        z_str, x_str, y_str = cell_id.split("/")
        tile = mercantile.Tile(x=int(x_str), y=int(y_str), z=int(z_str))
        b = mercantile.bounds(tile)

        # Build a closed rectangle: SW → SE → NE → NW → SW
        return Polygon([
            (b.west,  b.south),
            (b.east,  b.south),
            (b.east,  b.north),
            (b.west,  b.north),
            (b.west,  b.south),   # close
        ])

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns all tiles within a Moore neighborhood of radius k.

        XYZ tiles share borders but do NOT have the topological k-ring of
        true DGGS hexagonal systems — this is a simple 2D Cartesian grid walk,
        ignoring the anti-meridian and polar singularities.
        """
        z_str, x_str, y_str = cell_id.split("/")
        z     = int(z_str)
        x_c   = int(x_str)
        y_c   = int(y_str)
        max_xy = 2 ** z - 1

        neighbors = []
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                if dx == 0 and dy == 0:
                    continue
                # Wrap X around the anti-meridian; clamp Y at poles
                nx = (x_c + dx) % (max_xy + 1)
                ny = y_c + dy
                if 0 <= ny <= max_xy:
                    neighbors.append(f"{z}/{nx}/{ny}")
        return neighbors

    def get_parent(self, cell_id: str) -> str:
        """
        Returns the parent tile at zoom level Z-1.
        """
        z_str, x_str, y_str = cell_id.split("/")
        z = int(z_str)
        if z == 0:
            raise ValueError(f"Tile {cell_id} is already at Z=0 and has no parent.")
        x = int(x_str)
        y = int(y_str)
        return f"{z-1}/{x//2}/{y//2}"

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the center lat/lon of the XYZ tile.
        """
        z_str, x_str, y_str = cell_id.split("/")
        tile = mercantile.Tile(x=int(x_str), y=int(y_str), z=int(z_str))
        b = mercantile.bounds(tile)
        center_lat = (b.north + b.south) / 2.0
        center_lon = (b.east + b.west) / 2.0
        return center_lat, center_lon

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        """
        Returns all XYZ tiles covering the given polygon at the specified zoom level.

        Uses mercantile.tiles() to enumerate all tiles within the polygon's bounding
        box, then filters to those that actually intersect the polygon geometry.
        """
        from shapely.geometry import box
        from shapely.prepared import prep

        bounds = polygon.bounds  # (minx, miny, maxx, maxy) = (west, south, east, north)
        # Clamp to Mercator latitude limits
        south = max(bounds[1], -85.05112878)
        north = min(bounds[3],  85.05112878)

        if south >= north:
            return []

        prepared_poly = prep(polygon)
        cells = []
        for tile in mercantile.tiles(bounds[0], south, bounds[2], north, zooms=resolution):
            tb = mercantile.bounds(tile)
            tile_box = box(tb.west, tb.south, tb.east, tb.north)
            if prepared_poly.intersects(tile_box):
                cells.append(f"{tile.z}/{tile.x}/{tile.y}")

        return cells
