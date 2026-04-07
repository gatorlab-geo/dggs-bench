from typing import List, Tuple
from shapely.geometry import Polygon
from vgrid.dggs.rhealpixdggs.dggs import RHEALPixDGGS
from .base import BaseGrid

class RHEALPixGrid(BaseGrid):
    def __init__(self):
        self.engine = RHEALPixDGGS()

    @property
    def name(self) -> str:
        return "rHEALPix (Equal Area Square)"

    @property
    def is_equal_area(self) -> bool:
        return True

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into a rHEALPix cell ID string.
        """
        cell = self.engine.cell_from_point(resolution, (lon, lat), plane=False)
        return str(cell)

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Returns the rHEALPix boundary polygon.
        """
        # Parse the string 'N21' back to ('N', 2, 1)
        suid = tuple([cell_id[0]] + [int(x) for x in cell_id[1:]])
        cell = self.engine.cell(suid)
        
        boundary = cell.boundary(plane=False)
        
        # Shapely requires closed polygons
        if boundary[0] != boundary[-1]:
            boundary.append(boundary[0])
            
        return Polygon(boundary)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the rHEALPix cell center using angular vertex averaging.
        """
        poly = self.get_cell_polygon(cell_id)
        coords = list(poly.exterior.coords)[:-1] 
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        avg_lat = sum(lats) / len(lats)
        
        # Longitude averaging with wrap-around handling
        shifted_lons = [(lon if lon >= 0 else lon + 360) for lon in lons]
        avg_lon = sum(shifted_lons) / len(shifted_lons)
        if avg_lon > 180:
            avg_lon -= 360
        return float(avg_lat), float(avg_lon)

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns the Moore neighborhood. 
        Note: rHEALPix handles neighbors natively via cell.neighbors()
        """
        suid = tuple([cell_id[0]] + [int(x) for x in cell_id[1:]])
        cell = self.engine.cell(suid)
        
        # Fallback to k=1 for now as vgrid's native neighbors might just be immediate edge neighbors
        neighbors = cell.neighbors(plane=False)
        return [str(n) for n in neighbors.values()]

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        from vgrid.dggs.rhealpixdggs.rhp_wrappers import polyfill
        cells = polyfill(polygon, resolution, plane=False, dggs=self.engine)
        return list(cells)
