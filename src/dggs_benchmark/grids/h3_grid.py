import h3
from typing import List, Tuple
from shapely.geometry import Polygon
from .base import BaseGrid

class H3Grid(BaseGrid):
    @property
    def name(self) -> str:
        return "H3 (Uber)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into an H3 Hexagon ID.
        Resolution (0-15) controls cell size.
        """
        # H3 returns an integer or hex string depending on the binding version,
        # we cast to string for API consistency across all DGGS.
        return str(h3.latlng_to_cell(lat, lon, resolution))

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Returns the hexagonal boundary.
        """
        # H3 expects integer or valid hex string; we pass it back
        boundary = h3.cell_to_boundary(cell_id)
        
        # Shapely requires closed polygons (first vertex == last vertex)
        boundary_closed = tuple(boundary) + (boundary[0],)
        
        # H3 returns (lat, lon), Shapely expects (lon, lat)
        lon_lat_boundary = [(pt[1], pt[0]) for pt in boundary_closed]
        return Polygon(lon_lat_boundary)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the native H3 cell center Lat/Lng.
        """
        return h3.cell_to_latlng(cell_id)

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns k-ring neighbors.
        """
        neighbors = h3.grid_disk(cell_id, k)
        return [str(n) for n in neighbors]

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        """
        Returns all cells covering the polygon.
        """
        coords = [list(polygon.exterior.coords)]
        for interior in polygon.interiors:
            coords.append(list(interior.coords))
            
        geo = {
            "type": "Polygon",
            "coordinates": coords
        }
        cells = h3.geo_to_cells(geo, resolution)
        return [str(c) for c in cells]

    def get_parent(self, cell_id: str) -> str:
        """
        Returns the parent H3 Hexagon ID.
        """
        return str(h3.cell_to_parent(cell_id))
