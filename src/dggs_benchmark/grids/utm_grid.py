from typing import List, Tuple
from shapely.geometry import Polygon
from pyproj import Transformer, CRS
from .base import BaseGrid

class UTMGrid(BaseGrid):
    """
    Simulates a Universal Transverse Mercator (UTM) raster grid.
    
    UTM divides the world into 60 longitudinal zones (6° each), 
    each projected with a transverse Mercator projection. This is 
    what cutting-edge geospatial foundation models like AlphaEarth use.
    
    The 'resolution' parameter here represents the grid cell edge length in meters.
    """
    @staticmethod
    def _get_utm_zone_epsg(lon: float, lat: float) -> int:
        """
        Determines the appropriate UTM zone EPSG code for a given coordinate.
        Handles Svalbard and Norway special zones.
        """
        zone_number = int((lon + 180) / 6) + 1

        # Special zones for Svalbard
        if 72.0 <= lat <= 84.0:
            if 0.0 <= lon < 9.0:
                zone_number = 31
            elif 9.0 <= lon < 21.0:
                zone_number = 33
            elif 21.0 <= lon < 33.0:
                zone_number = 35
            elif 33.0 <= lon < 42.0:
                zone_number = 37

        if lat >= 0:
            return 32600 + zone_number  # WGS84 Northern hemisphere UTM
        else:
            return 32700 + zone_number  # WGS84 Southern hemisphere UTM

    @property
    def name(self) -> str:
        return "UTM (Universal Transverse Mercator)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Takes a WGS84 coordinate and encodes it into a UTM grid cell ID.
        The grid cell size is controlled by `resolution` (cell edge in meters).
        """
        # UTM strictly rejects polar domains mathematically
        if lat > 84.0 or lat < -80.0:
            raise ValueError(f"Latitude {lat:.4f} falls strictly outside valid UTM Zone bounds (84N to 80S).")

        epsg = self._get_utm_zone_epsg(lon, lat)
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        
        utm_x, utm_y = transformer.transform(lon, lat)
        
        # Compute cell indices
        x_idx = int(utm_x // resolution)
        y_idx = int(utm_y // resolution)
        
        return f"{epsg}_{x_idx}_{y_idx}_{resolution}"

    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Decodes the UTM cell ID back into a WGS84 polygon.
        """
        epsg_str, x_idx_str, y_idx_str, edge_m_str = cell_id.split("_", 3)
        epsg = int(epsg_str)
        x_idx = int(x_idx_str)
        y_idx = int(y_idx_str)
        edge_m = int(edge_m_str)
        
        # Reconstruct the UTM square
        min_x = x_idx * edge_m
        min_y = y_idx * edge_m
        max_x = min_x + edge_m
        max_y = min_y + edge_m
        
        corners_utm = [
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
            (min_x, min_y), # close
        ]
        
        transformer_to_wgs = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
        corners_wgs = [transformer_to_wgs.transform(x, y) for x, y in corners_utm]
        return Polygon(corners_wgs)

    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Returns the center of the UTM square in WGS84.
        """
        epsg_str, x_idx_str, y_idx_str, edge_m_str = cell_id.split("_", 3)
        epsg = int(epsg_str)
        x_idx = int(x_idx_str)
        y_idx = int(y_idx_str)
        edge_m = int(edge_m_str)
        
        # UTM center
        center_x = (x_idx * edge_m) + (edge_m / 2)
        center_y = (y_idx * edge_m) + (edge_m / 2)
        
        transformer_to_wgs = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
        lon, lat = transformer_to_wgs.transform(center_x, center_y)
        return lat, lon

    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        import math
        from shapely.ops import transform
        
        epsg = self._get_utm_zone_epsg(polygon.centroid.x, polygon.centroid.y)
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        poly_utm = transform(transformer.transform, polygon)
        
        bounds = poly_utm.bounds # minx, miny, maxx, maxy
        
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
                if cell_poly.intersects(poly_utm):
                    cells.append(f"{epsg}_{x_idx}_{y_idx}_{resolution}")
                    
        return cells

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns the Moore neighborhood (all neighboring cells within k steps)
        in this 2D cartesian UTM grid.
        """
        epsg_str, x_idx_str, y_idx_str, edge_m_str = cell_id.split("_", 3)
        epsg = int(epsg_str)
        x_idx = int(x_idx_str)
        y_idx = int(y_idx_str)
        
        neighbors = []
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                if dx == 0 and dy == 0:
                    continue
                neighbors.append(f"{epsg}_{x_idx + dx}_{y_idx + dy}_{edge_m_str}")
        return neighbors
