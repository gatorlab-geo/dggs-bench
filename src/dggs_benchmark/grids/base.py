from abc import ABC, abstractmethod
from typing import List, Tuple
from shapely.geometry import Polygon

class BaseGrid(ABC):
    """
    Abstract base class enforcing a uniform API across all Discrete Global Grid Systems
    and standard map projections within the benchmarking framework.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human readable name of the grid (e.g., 'H3 (Uber)')"""
        pass
        
    @property
    @abstractmethod
    def is_equal_area(self) -> bool:
        """Does this grid mathematically guarantee equal area cells?"""
        pass
        
    @abstractmethod
    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Takes a WGS84 coordinate and returns the Grid Cell ID as a string.
        Resolution mapping differs by grid (e.g. H3=8, S2=13) and must be
        handled by the concrete implementation.
        """
        pass
        
    @abstractmethod
    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Takes a Grid Cell ID and returns its true boundary as a Shapely Polygon
        in WGS84 (EPSG:4326) coordinates format (lon, lat).
        """
        pass

    @abstractmethod
    def get_cell_center(self, cell_id: str) -> Tuple[float, float]:
        """
        Takes a Grid Cell ID and returns its representative center point
        as (lat, lon) in WGS84 (EPSG:4326).
        """
        pass
        
    @abstractmethod
    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Returns a list of Cell IDs that form the k-ring (neighbors) around
        the target cell. k=1 is immediate neighbors.
        """
        pass
        
    @abstractmethod
    def get_covering(self, polygon: Polygon, resolution: int) -> List[str]:
        """
        Returns a list of all Cell IDs that cover/contain the provided Shapely Polygon
        at the specified resolution. 
        """
        pass

    def get_parent(self, cell_id: str) -> str:
        """
        Returns the Parent Cell ID at the next coarsest resolution.
        Raises NotImplementedError if the grid is not hierarchical.
        """
        raise NotImplementedError(f"{self.name} does not support native hierarchical aggregation.")
