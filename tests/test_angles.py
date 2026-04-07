from pyproj import Geod
import numpy as np

geod = Geod(ellps="WGS84")

# Square at equator
# p0 = (0,0), p1 = (1,0), p2 = (1,1), p3 = (0,1), p4 = (0,0)
coords = [(0,0), (1,0), (1,1), (0,1), (0,0)]
num_vertices = len(coords) - 1

interior_angles = []
for i in range(num_vertices):
    lon1, lat1 = coords[i-1]
    lon2, lat2 = coords[i]
    lon3, lat3 = coords[(i+1) % num_vertices]
    
    az21, _, dist1 = geod.inv(lon2, lat2, lon1, lat1)
    az23, _, dist3 = geod.inv(lon2, lat2, lon3, lat3)
    
    print(f"i={i}: p1={lon1},{lat1} p2={lon2},{lat2} p3={lon3},{lat3} dist1={dist1} dist3={dist3}")
    print(f"  az21={az21} az23={az23}")
    
    angle = (az23 - az21) % 360
    interior_angles.append(angle)

print("Angles:", interior_angles)
print("Std dev:", np.std(interior_angles, ddof=1))
