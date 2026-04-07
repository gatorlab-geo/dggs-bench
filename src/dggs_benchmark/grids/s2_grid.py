import s2sphere
from typing import List, Tuple
from shapely.geometry import Polygon
from .base import BaseGrid

class S2Grid(BaseGrid):
    @property
    def name(self) -> str:
        return "S2 Geometry (Google)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into an S2 square cell ID.
        Resolution in S2 is called 'level' (0-30).
        """
        ll = s2sphere.LatLng.from_degrees(lat, lon)
        cell_id = s2sphere.CellId.from_lat_lng(ll).parent(resolution)
        return str(cell_id.id())

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Returns the square cell boundary.
        """
        s2_id = s2sphere.CellId(int(cell_id))
        cell = s2sphere.Cell(s2_id)
        
        vertices = []
        for i in range(4):
            vertex_ll = s2sphere.LatLng.from_point(cell.get_vertex(i))
            vertices.append((vertex_ll.lng().degrees, vertex_ll.lat().degrees))
            
        # Close the polygon
        vertices.append(vertices[0])
        return Polygon(vertices)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the native S2 cell center Lat/Lng.
        """
        s2_id = s2sphere.CellId(int(cell_id))
        ll = s2_id.to_lat_lng()
        return ll.lat().degrees, ll.lng().degrees

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        S2 does not have a native "k-ring" in the same way Hexagons do,
        but it can get edge neighbors.
        """
        s2_id = s2sphere.CellId(int(cell_id))
        # This gets immediate neighbors (k=1)
        neighbors = s2_id.get_edge_neighbors()
        return [str(n.id()) for n in neighbors]

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        """
        Returns all cells covering the polygon at the specified level.
        """
        coverer = s2sphere.RegionCoverer()
        coverer.min_level = resolution
        coverer.max_level = resolution
        
        bounds = polygon.bounds # (minx, miny, maxx, maxy)
        rect = s2sphere.LatLngRect.from_point_pair(
            s2sphere.LatLng.from_degrees(bounds[1], bounds[0]),
            s2sphere.LatLng.from_degrees(bounds[3], bounds[2])
        )
        
        covering = coverer.get_covering(rect)
        
        from shapely.geometry import Point
        covered_cells = []
        for c in covering:
            cell_id = str(c.id())
            lat, lon = self.get_cell_center(cell_id)
            if Point(lon, lat).within(polygon):
                covered_cells.append(cell_id)
                
        if not covered_cells:
            for c in covering:
                cell_id = str(c.id())
                if self.get_cell_polygon(cell_id).intersects(polygon):
                    covered_cells.append(cell_id)
                    
        return covered_cells

    def get_parent(self, cell_id: str) -> str:
        """
        Returns the parent S2 cell ID.
        """
        s2_id = s2sphere.CellId(int(cell_id))
        return str(s2_id.parent().id())
