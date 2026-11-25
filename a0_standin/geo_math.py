"""A0 stand-in for the WGS84 entries of ``astra_shared.geo_math``.

The frozen A0 API (A0 plan v7, Section 6.1) adds vector converters, ENU, look
angles, the ray-ellipsoid intersection, nadir, the off-axis angle and the
metre frame-velocity rebuild to ``astra_shared.geo_math``. Until A0 merges
(2 Dec 2026), Teams A1 and B1 import them from here, with the same names,
arguments, units, shapes and errors (plan v7, Section 6.6).

This module is never merged into ``main`` and never used by an A0 route. At the
swap, ``from a0_standin.geo_math import`` becomes
``from astra_shared.geo_math import`` and the ``a0_standin`` package is deleted.

Conventions (plan v7, Section 6.1.1):
- metres, m/s and degrees at the interface;
- ``bool``, strings, ``None`` and complex values raise ``ValueError``;
- non-finite values raise ``ValueError`` (not in the two scalar converters);
- Cartesian inputs have a final axis of 3; leading axes broadcast;
- one invalid element fails the whole call;
- inputs are not modified; outputs are new float64 arrays.
"""

from __future__ import annotations

import numpy as np

from astra_shared.geo_math import (  # existing names, unchanged by A0
    FRAME_VELOCITY_UNITS_ERROR,
    OMEGA_EARTH_RAD_S,
    check_inertial_speed_km_s,
)
from astra_shared import geo_math as _today

__all__ = [
    "WGS84_A_M",
    "WGS84_F",
    "WGS84_B_M",
    "WGS84_E2",
    "OMEGA_EARTH_RAD_S",
    "FRAME_VELOCITY_UNITS_ERROR",
    "geodetic_to_ecef",
    "ecef_to_geodetic",
    "geodetic_to_ecef_vec",
    "ecef_to_geodetic_vec",
    "enu_basis",
    "enu_basis_vec",
    "ecef_delta_to_enu",
    "ecef_delta_to_enu_vec",
    "look_angles_ecef",
    "look_angles_ecef_vec",
    "nadir_unit_vec",
    "off_axis_deg_vec",
    "intersect_ray_wgs84",
    "intersect_ray_wgs84_vec",
    "lvlh_reference_velocity_m",
    "lvlh_reference_velocity_m_vec",
]

# --- constants (Section 6.1.2) ------------------------------------------------
WGS84_A_M = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_B_M = WGS84_A_M * (1.0 - WGS84_F)
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)

_EP2 = (WGS84_A_M * WGS84_A_M - WGS84_B_M * WGS84_B_M) / (WGS84_B_M * WGS84_B_M)
_VERTICAL_EPS = 1e-12  # horizontal / range below which azimuth is undefined


# --- validation helpers (Section 6.1.1) ----------------------------------------
def _real(name: str, value) -> np.ndarray:
    """Return a finite float64 array copy of ``value`` or raise ValueError."""
    if isinstance(value, (bool, np.bool_)) or value is None:
        raise ValueError(f"{name} must be a real number, not {type(value).__name__}")
    arr = np.asarray(value)
    if arr.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be real numeric (got dtype {arr.dtype})")
    arr = np.array(arr, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr


def _vec3(name: str, value) -> np.ndarray:
    arr = _real(name, value)
    if arr.ndim == 0 or arr.shape[-1] != 3:
        raise ValueError(f"{name} must have a final axis of length 3 (got shape {arr.shape})")
    return arr


def _lead_shape(name: str, *shapes) -> tuple:
    try:
        return np.broadcast_shapes(*shapes)
    except ValueError as exc:
        raise ValueError(f"{name}: incompatible shapes {shapes}") from exc


def _latitude(name: str, value) -> np.ndarray:
    arr = _real(name, value)
    if np.any(np.abs(arr) > 90.0):
        raise ValueError(f"{name} must be within [-90, 90] degrees")
    return arr


def _out(arr) -> np.ndarray:
    return np.array(arr, dtype=np.float64, copy=True)


def _norm(v: np.ndarray) -> np.ndarray:
    """Euclidean norm over the last axis, scaled against overflow and underflow."""
    scale = np.max(np.abs(v), axis=-1)
    safe = np.where(scale > 0.0, scale, 1.0)
    return scale * np.sqrt(np.sum((v / safe[..., None]) ** 2, axis=-1))


def _unit(name: str, v: np.ndarray) -> np.ndarray:
    n = _norm(v)
    if np.any(n == 0.0):
        raise ValueError(f"{name} must be non-zero")
    return v / n[..., None]


def _fold_longitude(lon_deg: np.ndarray) -> np.ndarray:
    return np.where(lon_deg == -180.0, 180.0, lon_deg)


# --- geodetic <-> ECEF (Section 6.1.3) ------------------------------------------
def _forward(lat_deg, lon_deg, alt_m):
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    n = WGS84_A_M / np.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    x = (n + alt_m) * cos_lat * np.cos(lon)
    y = (n + alt_m) * cos_lat * np.sin(lon)
    z = (n * (1.0 - WGS84_E2) + alt_m) * sin_lat
    return x, y, z


def _inverse(x, y, z):
    """Bowring latitude with the projected height; exact polar-axis branch."""
    p = np.hypot(x, y)
    on_axis = p == 0.0
    theta = np.arctan2(z * WGS84_A_M, p * WGS84_B_M)
    st = np.sin(theta)
    ct = np.cos(theta)
    lat = np.arctan2(z + _EP2 * WGS84_B_M * st**3, p - WGS84_E2 * WGS84_A_M * ct**3)
    lat = np.where(on_axis, np.copysign(np.pi / 2.0, z), lat)
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    h = p * cos_lat + z * sin_lat - WGS84_A_M * np.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    h = np.where(on_axis, np.abs(z) - WGS84_B_M, h)
    lon = np.where(on_axis, 0.0, np.arctan2(y, x))
    return np.degrees(lat), _fold_longitude(np.degrees(lon)), h


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> tuple[float, float, float]:
    """WGS84 geodetic (deg, deg, m) to ECEF metres. No new errors (Section 6.1.3)."""
    return _today.geodetic_to_ecef(lat_deg, lon_deg, alt_m)


def ecef_to_geodetic(x_m: float, y_m: float, z_m: float) -> tuple[float, float, float]:
    """ECEF metres to WGS84 (lat_deg, lon_deg, alt_m), with the A0 height formula.

    No new errors: non-finite input gives non-finite output, and the geocentre
    gives (90.0, 0.0, -b) from the polar-axis branch.
    """
    with np.errstate(invalid="ignore", over="ignore"):
        lat, lon, h = _inverse(np.float64(x_m), np.float64(y_m), np.float64(z_m))
    return float(lat), float(lon), float(h)


def geodetic_to_ecef_vec(lat_deg, lon_deg, alt_m):
    """Broadcast geodetic arrays to ECEF metres: three arrays of shape S."""
    lat = _latitude("lat_deg", lat_deg)
    lon = _real("lon_deg", lon_deg)
    alt = _real("alt_m", alt_m)
    shape = _lead_shape("geodetic_to_ecef_vec", lat.shape, lon.shape, alt.shape)
    lat, lon, alt = (np.broadcast_to(a, shape) for a in (lat, lon, alt))
    x, y, z = _forward(lat, lon, alt)
    return _out(x), _out(y), _out(z)


def ecef_to_geodetic_vec(x_m, y_m, z_m):
    """Broadcast ECEF metres to (lat_deg, lon_deg, alt_m): three arrays of shape S."""
    x = _real("x_m", x_m)
    y = _real("y_m", y_m)
    z = _real("z_m", z_m)
    shape = _lead_shape("ecef_to_geodetic_vec", x.shape, y.shape, z.shape)
    x, y, z = (np.broadcast_to(a, shape) for a in (x, y, z))
    if np.any((x == 0.0) & (y == 0.0) & (z == 0.0)):
        raise ValueError("ecef_to_geodetic_vec: the geocentre (0, 0, 0) has no geodetic position")
    lat, lon, h = _inverse(x, y, z)
    return _out(lat), _out(lon), _out(h)


# --- ENU and look angles (Section 6.1.4) ----------------------------------------
def enu_basis_vec(lat_deg, lon_deg):
    """(east, north, up) unit axes, each of shape S+(3,). Up is the geodetic normal."""
    lat_d = _latitude("lat_deg", lat_deg)
    lon_d = _real("lon_deg", lon_deg)
    shape = _lead_shape("enu_basis_vec", lat_d.shape, lon_d.shape)
    lat = np.radians(np.broadcast_to(lat_d, shape))
    lon = np.radians(np.broadcast_to(lon_d, shape))
    sl, cl = np.sin(lat), np.cos(lat)
    so, co = np.sin(lon), np.cos(lon)
    zero = np.zeros(shape)
    east = np.stack([-so, co, zero], axis=-1)
    north = np.stack([-sl * co, -sl * so, cl], axis=-1)
    up = np.stack([cl * co, cl * so, sl], axis=-1)
    return _out(east), _out(north), _out(up)


def enu_basis(lat_deg: float, lon_deg: float):
    e, n, u = enu_basis_vec(lat_deg, lon_deg)
    return tuple(map(float, e)), tuple(map(float, n)), tuple(map(float, u))


def ecef_delta_to_enu_vec(delta_m, lat_deg, lon_deg):
    """Project ECEF displacements (...,3) onto local ENU: three arrays of shape S."""
    d = _vec3("delta_m", delta_m)
    lat = _latitude("lat_deg", lat_deg)
    lon = _real("lon_deg", lon_deg)
    shape = _lead_shape("ecef_delta_to_enu_vec", d.shape[:-1], lat.shape, lon.shape)
    east, north, up = enu_basis_vec(np.broadcast_to(lat, shape), np.broadcast_to(lon, shape))
    d = np.broadcast_to(d, shape + (3,))
    return (
        _out(np.sum(d * east, axis=-1)),
        _out(np.sum(d * north, axis=-1)),
        _out(np.sum(d * up, axis=-1)),
    )


def ecef_delta_to_enu(delta_m, lat_deg: float, lon_deg: float):
    if np.shape(delta_m) != (3,):
        raise ValueError("ecef_delta_to_enu takes a 3-vector; use ecef_delta_to_enu_vec")
    e, n, u = ecef_delta_to_enu_vec(delta_m, lat_deg, lon_deg)
    return float(e), float(n), float(u)


def look_angles_ecef_vec(sat_m, ground_m, lat_deg, lon_deg):
    """(range_m, elevation_deg, azimuth_deg) from ground to satellite, each of shape S.

    ``lat_deg``/``lon_deg`` are the geodetic coordinates of ``ground_m`` (not checked).
    Elevation uses the geodetic Up. Azimuth is clockwise from North in [0, 360);
    a numerically vertical line of sight gives azimuth 0 and elevation +-90.
    No mask is applied.
    """
    s = _vec3("sat_m", sat_m)
    g = _vec3("ground_m", ground_m)
    lat = _latitude("lat_deg", lat_deg)
    lon = _real("lon_deg", lon_deg)
    shape = _lead_shape("look_angles_ecef_vec", s.shape[:-1], g.shape[:-1], lat.shape, lon.shape)
    los = np.broadcast_to(s, shape + (3,)) - np.broadcast_to(g, shape + (3,))
    rng = _norm(los)
    if np.any(rng == 0.0):
        raise ValueError("look_angles_ecef_vec: zero range (satellite at the ground point)")
    east, north, up = enu_basis_vec(np.broadcast_to(lat, shape), np.broadcast_to(lon, shape))
    e = np.sum(los * east, axis=-1)
    n = np.sum(los * north, axis=-1)
    u = np.sum(los * up, axis=-1)
    horizontal = np.hypot(e, n)
    vertical = horizontal <= _VERTICAL_EPS * rng
    el = np.degrees(np.arctan2(u, horizontal))
    el = np.where(vertical, np.copysign(90.0, u), el)
    az = np.mod(np.degrees(np.arctan2(e, n)), 360.0)
    az = np.where(az >= 360.0, 0.0, az)
    az = np.where(vertical, 0.0, az)
    return _out(rng), _out(el), _out(az)


def look_angles_ecef(sat_m, ground_m, lat_deg: float, lon_deg: float):
    if np.shape(sat_m) != (3,) or np.shape(ground_m) != (3,):
        raise ValueError("look_angles_ecef takes two 3-vectors; use look_angles_ecef_vec")
    r, el, az = look_angles_ecef_vec(sat_m, ground_m, lat_deg, lon_deg)
    return float(r), float(el), float(az)


# --- nadir and off-axis (Section 6.1.5) -----------------------------------------
def nadir_unit_vec(sat_m) -> np.ndarray:
    """Geocentric nadir -sat_m/|sat_m|, shape S+(3,)."""
    s = _vec3("sat_m", sat_m)
    return _out(-_unit("sat_m", s))


def off_axis_deg_vec(boresight_unit, sat_m, point_m) -> np.ndarray:
    """Angle in degrees [0, 180] between a boresight and the satellite-to-point direction."""
    b = _vec3("boresight_unit", boresight_unit)
    s = _vec3("sat_m", sat_m)
    p = _vec3("point_m", point_m)
    shape = _lead_shape("off_axis_deg_vec", b.shape[:-1], s.shape[:-1], p.shape[:-1])
    b = _unit("boresight_unit", np.broadcast_to(b, shape + (3,)))
    d = np.broadcast_to(p, shape + (3,)) - np.broadcast_to(s, shape + (3,))
    if np.any(_norm(d) == 0.0):
        raise ValueError("off_axis_deg_vec: point_m equals sat_m")
    q = _unit("point_m - sat_m", d)
    cross = _norm(np.cross(b, q))
    dot = np.sum(b * q, axis=-1)
    return _out(np.degrees(np.arctan2(cross, dot)))


# --- ray-ellipsoid intersection (Section 6.1.6, Q5) ------------------------------
def intersect_ray_wgs84_vec(origin_m, direction):
    """Nearest strictly positive hit of each ray on the WGS84 ellipsoid.

    Returns ``(hit_m, distance_m, is_hit)``: ``hit_m`` S+(3,), ``distance_m`` S
    (metres along the normalised direction), ``is_hit`` bool S. Misses are NaN.
    Strict policy: D < 0 or no root > 0 is a miss; no tolerance band.
    """
    o = _vec3("origin_m", origin_m)
    v = _vec3("direction", direction)
    shape = _lead_shape("intersect_ray_wgs84_vec", o.shape[:-1], v.shape[:-1])
    o = np.broadcast_to(o, shape + (3,))
    d = _unit("direction", np.broadcast_to(v, shape + (3,)))
    a2 = WGS84_A_M * WGS84_A_M
    b2 = WGS84_B_M * WGS84_B_M
    x, y, z = o[..., 0], o[..., 1], o[..., 2]
    dx, dy, dz = d[..., 0], d[..., 1], d[..., 2]
    A = (dx * dx + dy * dy) / a2 + dz * dz / b2
    B = 2.0 * ((x * dx + y * dy) / a2 + z * dz / b2)
    C = (x * x + y * y) / a2 + z * z / b2 - 1.0
    D = B * B - 4.0 * A * C
    real = D >= 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        sq = np.sqrt(np.where(real, D, 0.0))
        q = -0.5 * (B + np.copysign(sq, B))
        double = -B / (2.0 * A)
        t1 = np.where(q != 0.0, q / A, double)
        t2 = np.where(q != 0.0, C / q, double)
    t1 = np.where(real & (t1 > 0.0), t1, np.inf)
    t2 = np.where(real & (t2 > 0.0), t2, np.inf)
    t = np.minimum(t1, t2)
    is_hit = np.isfinite(t)
    dist = np.where(is_hit, t, np.nan)
    hit = o + dist[..., None] * d
    return _out(hit), _out(dist), np.array(is_hit, dtype=bool, copy=True)


def intersect_ray_wgs84(origin_m, direction):
    """Scalar form: ``None`` for no hit, else ``(hit_m 3-tuple, distance_m)``."""
    o = _vec3("origin_m", origin_m)
    v = _vec3("direction", direction)
    if o.shape != (3,) or v.shape != (3,):
        raise ValueError("intersect_ray_wgs84 takes two 3-vectors; use intersect_ray_wgs84_vec")
    hit, dist, ok = intersect_ray_wgs84_vec(o, v)
    if not bool(ok):
        return None
    return (float(hit[0]), float(hit[1]), float(hit[2])), float(dist)


# --- frame reference velocity (Section 6.1.7) -----------------------------------
def lvlh_reference_velocity_m_vec(r_ecef_m, vrel_mps) -> np.ndarray:
    """Inertial velocity on ECEF axes, m/s, shape S+(3,).

    Exact-zero ``vrel`` (stationary satellite) gives omega x r with no speed
    check. Any other ``vrel`` is rebuilt as vrel + omega x r and must pass the
    existing bound-orbit speed check.
    """
    r = _vec3("r_ecef_m", r_ecef_m)
    v = _vec3("vrel_mps", vrel_mps)
    shape = _lead_shape("lvlh_reference_velocity_m_vec", r.shape[:-1], v.shape[:-1])
    r = np.broadcast_to(r, shape + (3,))
    v = np.broadcast_to(v, shape + (3,))
    if np.any(_norm(r) == 0.0):
        raise ValueError("r_ecef_m must be non-zero")
    w = OMEGA_EARTH_RAD_S
    wxr = np.stack([-w * r[..., 1], w * r[..., 0], np.zeros(shape)], axis=-1)
    vref = v + wxr
    stationary = np.all(v == 0.0, axis=-1)
    moving = ~stationary
    if np.any(moving):
        r_km = r[moving] / 1000.0
        v_km = vref[moving] / 1000.0
        radius = _norm(r_km)
        speed = _norm(v_km)
        mu = _today._MU_KM3_S2
        lo = np.sqrt(mu * (2.0 / radius - 2.0 / (radius + _today._R_EARTH_MEAN_KM))) * 0.98
        hi = np.sqrt(2.0 * mu / radius) * 1.02
        bad = ~((lo <= speed) & (speed <= hi))
        if np.any(bad):
            i = int(np.flatnonzero(bad)[0])
            # Raise the existing diagnostic (FRAME_VELOCITY_UNITS_ERROR prefix).
            check_inertial_speed_km_s(tuple(r_km[i]), tuple(v_km[i]))
            raise ValueError(f"{FRAME_VELOCITY_UNITS_ERROR}: inertial speed out of band")
    return _out(vref)


def lvlh_reference_velocity_m(r_ecef_m, vrel_mps) -> tuple[float, float, float]:
    out = lvlh_reference_velocity_m_vec(r_ecef_m, vrel_mps)
    if out.shape != (3,):
        raise ValueError("lvlh_reference_velocity_m takes two 3-vectors; use the _vec form")
    return float(out[0]), float(out[1]), float(out[2])

