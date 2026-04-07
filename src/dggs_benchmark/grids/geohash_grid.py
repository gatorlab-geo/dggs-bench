import geohash
import polygon_geohasher
from typing import List, Tuple
from shapely.geometry import Polygon
from .base import BaseGrid

class GeohashGrid(BaseGrid):
    @property
    def name(self) -> str:
        return "Geohash"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into a Geohash string.
        Resolution (usually 1-12) controls cell size/string length.
        """
        lat = max(-90.0, min(89.9999999, lat))
        lon = max(-180.0, min(179.9999999, lon))
        return geohash.encode(lat, lon, precision=resolution)

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Returns the rectangular boundary of the Geohash cell.
        """
        return polygon_geohasher.geohash_to_polygon(cell_id)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the native Geohash cell center Lat/Lng.
        """
        lat, lon = geohash.decode(cell_id)
        return lat, lon

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns k-ring neighbors. 
        """
        if k == 0:
            return [cell_id]
            
        visited = set([cell_id])
        current_ring = set([cell_id])
        
        for _ in range(k):
            next_ring = set()
            for cell in current_ring:
                neighbors = geohash.neighbors(cell)
                for n in neighbors:
                    if n not in visited:
                        visited.add(n)
                        next_ring.add(n)
            current_ring = next_ring
            
        return list(visited)

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        """
        Returns all cells covering the polygon.
        """
        covering = polygon_geohasher.polygon_to_geohashes(polygon, resolution, inner=False)
        return list(covering)

    def get_parent(self, cell_id: str) -> str:
        """
        Returns the parent Geohash ID, which is the string minus the last character.
        """
        if len(cell_id) <= 1:
            raise ValueError(f"Geohash {cell_id} has no parent (resolution 1).")
        return cell_id[:-1]
