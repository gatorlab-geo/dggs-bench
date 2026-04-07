import mercantile
from typing import List
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

        :param lat:        WGS84 latitude  (clamped to ±85.051129° by mercantile)
        :param lon:        WGS84 longitude (-180 … 180)
        :param resolution: Zoom level Z (integer, typically 0–22)
        :returns:          Tile ID string, e.g. "13/2412/3080"
        """
        # Clamp to valid Mercator latitude range — poles are undefined in Web Mercator
        lat = max(-85.051129, min(85.051129, lat))
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
