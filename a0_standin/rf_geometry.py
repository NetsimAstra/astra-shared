"""A0 stand-in for the Radio adapter ``rf_geometry.py`` (A0 plan v7, Section 6.2).

Same names, arguments, units, shapes and errors as the frozen adapter. Built on
``a0_standin.geo_math``. At the swap, ``from a0_standin.rf_geometry import``
becomes ``from rf_geometry import`` and the ``a0_standin`` package is deleted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from a0_standin.geo_math import (
    WGS84_A_M,
    WGS84_B_M,
    _lead_shape,
    _norm,
    _out,
    _real,
    _vec3,
    ecef_to_geodetic_vec,
    enu_basis_vec,
    geodetic_to_ecef_vec,
    intersect_ray_wgs84,
    look_angles_ecef_vec,
    lvlh_reference_velocity_m_vec,
    nadir_unit_vec,
    off_axis_deg_vec,
)

__all__ = [
    "GroundGeometry",
    "LinkGeometry",
    "satellite_ecef_m",
    "ground_geometry",
    "nadir_unit",
    "link_geometry",
    "nadir_centre",
    "orbital_frame_axes_vec_m",
    "antenna_frame_angles_m",
    "antenna_frame_angles_vec_m",
    "MIN_LINK_RANGE_M",
    "link_range_ok",
]

MIN_LINK_RANGE_M = 1.0

# Today's km thresholds converted to metres (plan v7, Section 6.2).
_PROJECTED_SPEED_MIN_MPS = 1e-7  # was 1e-10 km/s
_POINT_DISTANCE_MIN_M = 1e-7  # was 1e-10 km (steered aim point, target at satellite)
_UNIT_FALLBACK_MIN = 1e-10  # dimensionless, unchanged


@dataclass(frozen=True)
class GroundGeometry:
    ecef_m: np.ndarray  # S+(3,)
    lat_deg: np.ndarray  # S
    lon_deg: np.ndarray  # S
    east: np.ndarray  # S+(3,)
    north: np.ndarray  # S+(3,)
    up: np.ndarray  # S+(3,)


@dataclass(frozen=True)
class LinkGeometry:
    range_m: np.ndarray  # S
    elevation_deg: np.ndarray  # S
    azimuth_deg: np.ndarray  # S
    off_axis_deg: np.ndarray  # S
    sat_to_ground_unit: np.ndarray  # S+(3,)


def satellite_ecef_m(lat_deg, lon_deg, alt_km) -> np.ndarray:
    """Geodetic satellite position (deg, deg, km) to ECEF metres, shape S+(3,)."""
    alt = _real("alt_km", alt_km)
    x, y, z = geodetic_to_ecef_vec(lat_deg, lon_deg, alt * 1000.0)
    return _out(np.stack([x, y, z], axis=-1))


def ground_geometry(lat_deg, lon_deg, alt_km=0.0) -> GroundGeometry:
    """Prepared WGS84 ground points (deg, deg, km), built once per grid or observer."""
    alt = _real("alt_km", alt_km)
    lat = _real("lat_deg", lat_deg)
    lon = _real("lon_deg", lon_deg)
    shape = _lead_shape("ground_geometry", lat.shape, lon.shape, alt.shape)
    lat, lon, alt = (np.broadcast_to(a, shape) for a in (lat, lon, alt))
    x, y, z = geodetic_to_ecef_vec(lat, lon, alt * 1000.0)
    east, north, up = enu_basis_vec(lat, lon)
    return GroundGeometry(
        ecef_m=_out(np.stack([x, y, z], axis=-1)),
        lat_deg=_out(lat),
        lon_deg=_out(lon),
        east=east,
        north=north,
        up=up,
    )


def nadir_unit(sat_m) -> np.ndarray:
    return nadir_unit_vec(sat_m)


def link_geometry(sat_m, ground: GroundGeometry, *, boresight_unit=None) -> LinkGeometry:
    """Range, look angles, off-axis and line of sight; no mask and no RF."""
    s = _vec3("sat_m", sat_m)
    shape = _lead_shape("link_geometry", s.shape[:-1], ground.lat_deg.shape)
    if boresight_unit is None:
        b = nadir_unit_vec(s)
    else:
        b = _vec3("boresight_unit", boresight_unit)
        shape = _lead_shape("link_geometry", shape, b.shape[:-1])
    rng, el, az = look_angles_ecef_vec(s, ground.ecef_m, ground.lat_deg, ground.lon_deg)
    g = np.broadcast_to(ground.ecef_m, shape + (3,))
    los = g - np.broadcast_to(s, shape + (3,))
    unit = los / np.broadcast_to(rng, shape)[..., None]
    psi = off_axis_deg_vec(b, s, ground.ecef_m)
    return LinkGeometry(
        range_m=_out(np.broadcast_to(rng, shape)),
        elevation_deg=_out(np.broadcast_to(el, shape)),
        azimuth_deg=_out(np.broadcast_to(az, shape)),
        off_axis_deg=_out(np.broadcast_to(psi, shape)),
        sat_to_ground_unit=_out(unit),
    )


def nadir_centre(sat_m):
    """The spec's nadir point: (hit_m (3,), distance_m, lat_deg, lon_deg)."""
    s = _vec3("sat_m", sat_m)
    if s.shape != (3,):
        raise ValueError("nadir_centre takes one satellite position of shape (3,)")
    c = (s[0] ** 2 + s[1] ** 2) / WGS84_A_M**2 + s[2] ** 2 / WGS84_B_M**2 - 1.0
    if not c > 0.0:
        raise ValueError("nadir_centre: the satellite must be outside the WGS84 ellipsoid")
    found = intersect_ray_wgs84(s, -s)
    if found is None:
        raise ValueError("nadir_centre: the geocentric nadir ray found no hit")
    hit, dist = found
    lat, lon, _h = ecef_to_geodetic_vec(hit[0], hit[1], hit[2])
    return np.array(hit, dtype=np.float64), dist, float(lat), float(lon)


def _frame_axes(s: np.ndarray, vref: np.ndarray, z: np.ndarray):
    """Today's projection and fallbacks, in metres (link_budget.antenna_frame_angles)."""
    v_dot_z = np.sum(vref * z, axis=-1)
    xv = vref - v_dot_z[..., None] * z
    x_mag = _norm(xv)
    use_v = x_mag >= _PROJECTED_SPEED_MIN_MPS
    north = np.zeros_like(z)
    north[..., 2] = 1.0
    n_dot_z = z[..., 2]
    xn = north - n_dot_z[..., None] * z
    xn_mag = _norm(xn)
    use_n = xn_mag >= _UNIT_FALLBACK_MIN
    plus_x = np.zeros_like(z)
    plus_x[..., 0] = 1.0
    with np.errstate(invalid="ignore", divide="ignore"):
        xv_u = xv / x_mag[..., None]
        xn_u = xn / xn_mag[..., None]
    x = np.where(use_v[..., None], xv_u, np.where(use_n[..., None], xn_u, plus_x))
    # Re-orthogonalise the chosen axis once against z and normalise it. This projects the
    # ECEF +X fallback perpendicular to z near a pole (+X itself at an exact pole) and
    # removes the rounding loss of the other branches near their thresholds (plan review
    # of 25 Nov, rev 2, P2-3, and its check round).
    x = x - np.sum(x * z, axis=-1)[..., None] * z
    x = x / _norm(x)[..., None]
    y = np.cross(z, x)
    return x, y


def orbital_frame_axes_vec_m(sat_m, vrel_mps):
    """(x_L, y_L, z_L), each S+(3,): along-track, cross-track, geocentric nadir."""
    s = _vec3("sat_m", sat_m)
    v = _vec3("vrel_mps", vrel_mps)
    shape = _lead_shape("orbital_frame_axes_vec_m", s.shape[:-1], v.shape[:-1])
    s = np.broadcast_to(s, shape + (3,))
    vref = lvlh_reference_velocity_m_vec(s, np.broadcast_to(v, shape + (3,)))
    z = nadir_unit_vec(s)
    x, y = _frame_axes(s, vref, z)
    return _out(x), _out(y), _out(z)


def antenna_frame_angles_vec_m(sat_m, vrel_mps, target_m, boresight_m=None):
    """(psi_deg, phi_deg), each of shape S, in today's convention.

    ``boresight_m`` is an aim point (ECEF metres), not a direction. An aim point
    within 1e-7 m of the satellite keeps the nadir axis, and a target within
    1e-7 m of the satellite gives (0, 0), as today.
    """
    s = _vec3("sat_m", sat_m)
    v = _vec3("vrel_mps", vrel_mps)
    t = _vec3("target_m", target_m)
    shapes = [s.shape[:-1], v.shape[:-1], t.shape[:-1]]
    if boresight_m is not None:
        bm = _vec3("boresight_m", boresight_m)
        shapes.append(bm.shape[:-1])
    shape = _lead_shape("antenna_frame_angles_vec_m", *shapes)
    s = np.broadcast_to(s, shape + (3,))
    vref = lvlh_reference_velocity_m_vec(s, np.broadcast_to(v, shape + (3,)))
    z = nadir_unit_vec(s)
    if boresight_m is not None:
        bvec = np.broadcast_to(bm, shape + (3,)) - s
        b_mag = _norm(bvec)
        steer = b_mag >= _POINT_DISTANCE_MIN_M
        with np.errstate(invalid="ignore", divide="ignore"):
            z = np.where(steer[..., None], bvec / b_mag[..., None], z)
    x, y = _frame_axes(s, vref, z)
    d = np.broadcast_to(t, shape + (3,)) - s
    d_mag = _norm(d)
    at_sat = d_mag < _POINT_DISTANCE_MIN_M
    with np.errstate(invalid="ignore", divide="ignore"):
        q = d / d_mag[..., None]
    cross = _norm(np.cross(z, q))
    psi = np.degrees(np.arctan2(cross, np.sum(q * z, axis=-1)))
    phi = np.degrees(np.arctan2(np.sum(q * y, axis=-1), np.sum(q * x, axis=-1)))
    psi = np.where(at_sat, 0.0, psi)
    phi = np.where(at_sat, 0.0, phi)
    return _out(psi), _out(phi)


def antenna_frame_angles_m(sat_m, vrel_mps, target_m, boresight_m=None):
    for name, value in (("sat_m", sat_m), ("vrel_mps", vrel_mps), ("target_m", target_m)):
        if np.shape(value) != (3,):
            raise ValueError(f"antenna_frame_angles_m: {name} must be a 3-vector")
    if boresight_m is not None and np.shape(boresight_m) != (3,):
        raise ValueError("antenna_frame_angles_m: boresight_m must be a 3-vector")
    psi, phi = antenna_frame_angles_vec_m(sat_m, vrel_mps, target_m, boresight_m)
    return float(psi), float(phi)


def link_range_ok(range_m):
    """True where the range is finite and at least MIN_LINK_RANGE_M (Q3)."""
    r = np.asarray(range_m, dtype=np.float64)
    ok = np.isfinite(r) & (r >= MIN_LINK_RANGE_M)
    return bool(ok) if ok.ndim == 0 else ok
