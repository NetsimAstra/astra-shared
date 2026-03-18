"""
geo_math.py

Pure-math geodetic coordinate utilities shared across Astra services.
No external dependencies — stdlib math only.

Functions:
- ecef_to_geodetic() - Convert ECEF (metres) to WGS84 lat/lon/alt
"""

from __future__ import annotations

import math


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """
    Convert ECEF coordinates to geodetic (lat, lon, alt).

    Uses WGS84 reference ellipsoid.

    Args:
        x, y, z: ECEF position in metres

    Returns:
        Tuple of (latitude_deg, longitude_deg, altitude_m)
    """
    a = 6378137.0  # WGS84 semi-major axis
    e2 = 6.69437999014e-3
    b = a * math.sqrt(1 - e2)
    ep2 = (a * a - b * b) / (b * b)
    p = math.sqrt(x * x + y * y)
    if p == 0:
        lon = 0.0
    else:
        lon = math.atan2(y, x)
    theta = math.atan2(z * a, p * b)
    st = math.sin(theta)
    ct = math.cos(theta)
    lat = math.atan2(z + ep2 * b * st * st * st, p - e2 * a * ct * ct * ct)
    sin_lat = math.sin(lat)
    n = a / math.sqrt(1 - e2 * sin_lat * sin_lat)
    alt = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), alt
