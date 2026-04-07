from typing import List, Tuple
from shapely.geometry import Polygon
from pyproj import Transformer
from .base import BaseGrid

class MercatorGrid(BaseGrid):
    @property
    def name(self) -> str:
        return "Web Mercator (EPSG:3857)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Simulates encoding into a square Mercator grid cell.
        'resolution' here represents the edge length in meters.
        """
        if lat > 85.05112878 or lat < -85.05112878:
            raise ValueError(f"Latitude {lat:.4f} is mathematically outside standard Web Mercator Slippy Map bounding limits.")
            
        transformer_to_merc = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        merc_x, merc_y = transformer_to_merc.transform(lon, lat)
        
        # Calculate cell origin (bottom-left corner)
        x_idx = int(merc_x // resolution)
        y_idx = int(merc_y // resolution)
        
        # Return a composite ID 
        return f"{x_idx}_{y_idx}_{resolution}"

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Decodes the ID, builds the 3857 square, and projects back to WGS84 native coordinates.
        """
        x_idx, y_idx, edge_m = map(int, cell_id.split('_'))
        
        # Reconstruct the EPSG:3857 coordinates
        min_x = x_idx * edge_m
        min_y = y_idx * edge_m
        max_x = min_x + edge_m
        max_y = min_y + edge_m
        
        corners_merc = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
            (min_x, min_y) # close
        ]
        
        transformer_to_wgs = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        corners_wgs = [transformer_to_wgs.transform(x, y) for x, y in corners_merc]
        return Polygon(corners_wgs)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the center of the Mercator square in WGS84.
        """
        x_idx, y_idx, edge_m = map(int, cell_id.split('_'))
        
        # EPSG:3857 center
        center_x = (x_idx * edge_m) + (edge_m / 2)
        center_y = (y_idx * edge_m) + (edge_m / 2)
        
        transformer_to_wgs = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        lon, lat = transformer_to_wgs.transform(center_x, center_y)
        return lat, lon

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        import math
        from shapely.ops import transform
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        poly_3857 = transform(transformer.transform, polygon)
        
        bounds = poly_3857.bounds # minx, miny, maxx, maxy
        
        min_x_idx = int(math.floor(bounds[0] / resolution))
        max_x_idx = int(math.floor(bounds[2] / resolution))
        min_y_idx = int(math.floor(bounds[1] / resolution))
        max_y_idx = int(math.floor(bounds[3] / resolution))
        
        cells = []
        for x_idx in range(min_x_idx, max_x_idx + 1):
            for y_idx in range(min_y_idx, max_y_idx + 1):
                min_x = x_idx * resolution
                min_y = y_idx * resolution
                max_x = min_x + resolution
                max_y = min_y + resolution
                
                cell_poly = Polygon([
                    (min_x, min_y), (max_x, min_y), 
                    (max_x, max_y), (min_x, max_y), 
                    (min_x, min_y)
                ])
                if cell_poly.intersects(poly_3857):
                    cells.append(f"{x_idx}_{y_idx}_{resolution}")
                    
        return cells

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Gets Moore neighborhood in a standard 2D cartesian grid.
        """
        x_idx, y_idx, edge_m = map(int, cell_id.split('_'))
        neighbors = []
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                if dx == 0 and dy == 0:
                    continue
                neighbors.append(f"{x_idx + dx}_{y_idx + dy}_{edge_m}")
        return neighbors
