from typing import List
from shapely.geometry import Polygon
import a5
from .base import BaseGrid

class A5Grid(BaseGrid):
    @property
    def name(self) -> str:
        return "A5 (Pentagon / Dodecahedron)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into an A5 cell ID.
        """
        cell_id = a5.lonlat_to_cell((lon, lat), resolution)
        return str(cell_id)

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Returns the A5 polygonal boundary.
        """
        boundary = a5.cell_to_boundary(int(cell_id))
        
        # Shapely requires closed polygons (first vertex == last vertex)
        if boundary[0] != boundary[-1]:
            boundary.append(boundary[0])
            
        # a5 cell_to_boundary already returns (lon, lat)
        return Polygon(boundary)

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns k-ring neighbors.
        """
        neighbors = a5.grid_disk(int(cell_id), k)
        return [str(n) for n in neighbors]
