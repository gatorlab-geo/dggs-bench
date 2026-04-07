from typing import List
from shapely.geometry import Polygon
from vgrid.dggs import qtm
from .base import BaseGrid

class QTMGrid(BaseGrid):
    @property
    def name(self) -> str:
        return "QTM (Triangles)"

    @property
    def is_equal_area(self) -> bool:
        return False

    def encode_point(self, lat: float, lon: float, resolution: int) -> str:
        """
        Encodes a coordinate into a QTM cell ID string.
        """
        # QTM's vgrid backend uses strict Shapely .contains() for face mapping.
        # This crashes if a point lands precisely on a triangle edge (like the equator).
        # We apply a micro-perturbation to ensure it falls rigidly inside a polygon.
        try:
            return qtm.latlon_to_qtm_id(lat, lon, resolution)
        except ValueError:
            # Fallback boundary perturbation
            epsilon = 1e-8
            p_lat = lat + epsilon if lat < 0 else lat - epsilon
            p_lon = lon + epsilon if lon < 0 else lon - epsilon
            try:
                return qtm.latlon_to_qtm_id(p_lat, p_lon, resolution)
            except ValueError:
                return qtm.latlon_to_qtm_id(p_lat, p_lon + epsilon, resolution)


    def get_cell_polygon(self, cell_id: str) -> Polygon:
        """
        Returns the triangular boundary.
        """
        facet = qtm.qtm_id_to_facet(cell_id)
        # constructGeometry returns a Shapely polygon correctly oriented
        geom = qtm.constructGeometry(facet)
        return geom

    def get_k_ring(self, cell_id: str, k: int) -> List[str]:
        """
        Native QTM K-Ring is complex in this vgrid backend. 
        For now we yield immediate children/parents or raise NotImplementedError.
        """
        raise NotImplementedError("K-Ring generation for QTM is not yet natively supported by the backend.")
