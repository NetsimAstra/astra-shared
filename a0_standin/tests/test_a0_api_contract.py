"""Conformance tests for the frozen A0 API (A0 plan v7, Sections 6.1 and 6.2).

By default they test the stand-in (``a0_standin``). WP1 and WP2 run the same
file against the real modules with ``A0_API_IMPL=real``:

    A0_API_IMPL=real python -m pytest a0_standin/tests/test_a0_api_contract.py

Expected values come from published controls or from small independent
calculations in this file, never from the module under test.
"""

from __future__ import annotations

import importlib
import inspect
import math
import os

import numpy as np
import pytest

if os.environ.get("A0_API_IMPL", "standin") == "real":
    gm = importlib.import_module("astra_shared.geo_math")
    rg = importlib.import_module("rf_geometry")
else:
    gm = importlib.import_module("a0_standin.geo_math")
    rg = importlib.import_module("a0_standin.rf_geometry")

A = 6378137.0
F = 1.0 / 298.257223563
B = A * (1.0 - F)
E2 = F * (2.0 - F)
OMEGA = 7.2921158553e-5


# --- independent references --------------------------------------------------
def ref_forward(lat_deg, lon_deg, h):
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    n = A / math.sqrt(1.0 - E2 * math.sin(lat) ** 2)
    return (
        (n + h) * math.cos(lat) * math.cos(lon),
        (n + h) * math.cos(lat) * math.sin(lon),
        (n * (1.0 - E2) + h) * math.sin(lat),
    )


def ref_inverse(x, y, z):
    """Iterative inverse (fixed point on latitude), independent of Bowring."""
    p = math.hypot(x, y)
    lon = math.degrees(math.atan2(y, x))
    lat = math.atan2(z, p * (1.0 - E2))
    for _ in range(50):
        n = A / math.sqrt(1.0 - E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1.0 - E2 * n / (n + h)))
    n = A / math.sqrt(1.0 - E2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), lon, h


def ref_nadir_hit_lat(sat_lat_deg, h):
    """Latitude where the geocentric nadir ray of a satellite at geodetic lat meets WGS84."""
    x, _, z = ref_forward(sat_lat_deg, 0.0, h)
    psi = math.atan2(z, x)  # geocentric latitude of the ray
    # Point on the ellipsoid at geocentric latitude psi: tan(phi) = tan(psi) / (1 - e2)
    return math.degrees(math.atan(math.tan(psi) / (1.0 - E2)))


# --- names and signatures -----------------------------------------------------
GEO_SIGNATURES = {
    "geodetic_to_ecef": ["lat_deg", "lon_deg", "alt_m"],
    "ecef_to_geodetic": ["x_m", "y_m", "z_m"],
    "geodetic_to_ecef_vec": ["lat_deg", "lon_deg", "alt_m"],
    "ecef_to_geodetic_vec": ["x_m", "y_m", "z_m"],
    "enu_basis": ["lat_deg", "lon_deg"],
    "enu_basis_vec": ["lat_deg", "lon_deg"],
    "ecef_delta_to_enu": ["delta_m", "lat_deg", "lon_deg"],
    "ecef_delta_to_enu_vec": ["delta_m", "lat_deg", "lon_deg"],
    "look_angles_ecef": ["sat_m", "ground_m", "lat_deg", "lon_deg"],
    "look_angles_ecef_vec": ["sat_m", "ground_m", "lat_deg", "lon_deg"],
    "nadir_unit_vec": ["sat_m"],
    "off_axis_deg_vec": ["boresight_unit", "sat_m", "point_m"],
    "intersect_ray_wgs84": ["origin_m", "direction"],
    "intersect_ray_wgs84_vec": ["origin_m", "direction"],
    "lvlh_reference_velocity_m": ["r_ecef_m", "vrel_mps"],
    "lvlh_reference_velocity_m_vec": ["r_ecef_m", "vrel_mps"],
}
RF_SIGNATURES = {
    "satellite_ecef_m": ["lat_deg", "lon_deg", "alt_km"],
    "ground_geometry": ["lat_deg", "lon_deg", "alt_km"],
    "nadir_unit": ["sat_m"],
    "link_geometry": ["sat_m", "ground", "boresight_unit"],
    "nadir_centre": ["sat_m"],
    "orbital_frame_axes_vec_m": ["sat_m", "vrel_mps"],
    "antenna_frame_angles_m": ["sat_m", "vrel_mps", "target_m", "boresight_m"],
    "antenna_frame_angles_vec_m": ["sat_m", "vrel_mps", "target_m", "boresight_m"],
    "link_range_ok": ["range_m"],
}


@pytest.mark.parametrize("name,params", sorted(GEO_SIGNATURES.items()))
def test_geo_math_signature(name, params):
    assert list(inspect.signature(getattr(gm, name)).parameters) == params


@pytest.mark.parametrize("name,params", sorted(RF_SIGNATURES.items()))
def test_rf_geometry_signature(name, params):
    assert list(inspect.signature(getattr(rg, name)).parameters) == params


def test_link_geometry_boresight_is_keyword_only():
    p = inspect.signature(rg.link_geometry).parameters["boresight_unit"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is None


def test_constants():
    assert gm.WGS84_A_M == A
    assert gm.WGS84_F == F
    assert gm.WGS84_B_M == pytest.approx(B, abs=1e-9)
    assert gm.WGS84_E2 == pytest.approx(E2, abs=1e-18)
    assert gm.OMEGA_EARTH_RAD_S == OMEGA
    assert rg.MIN_LINK_RANGE_M == 1.0


# --- converters ---------------------------------------------------------------
CASES = [
    (lat, lon, h)
    for lat in (-70.0, -45.0, 0.0, 45.0, 89.9)
    for lon in (-179.5, 0.0, 30.0)
    for h in (-1000.0, 0.0, 550e3, 35786e3)
]


@pytest.mark.parametrize("lat,lon,h", CASES)
def test_inverse_against_independent_iteration(lat, lon, h):
    x, y, z = ref_forward(lat, lon, h)
    lat_r, lon_r, h_r = ref_inverse(x, y, z)
    lat_v, lon_v, h_v = (float(a) for a in gm.ecef_to_geodetic_vec(x, y, z))
    lat_s, lon_s, h_s = gm.ecef_to_geodetic(x, y, z)
    for la, lo, hh in ((lat_v, lon_v, h_v), (lat_s, lon_s, h_s)):
        assert abs(la - lat_r) <= 1e-6
        assert abs(lo - lon_r) <= 1e-6
        assert abs(hh - h_r) <= 1e-6
        rx, ry, rz = ref_forward(la, lo, hh)
        assert math.dist((rx, ry, rz), (x, y, z)) <= 0.5


def test_forward_matches_reference_and_broadcasts():
    lat = np.array([[0.0], [45.0]])
    lon = np.array([0.0, 30.0, 180.0])
    x, y, z = gm.geodetic_to_ecef_vec(lat, lon, 550e3)
    assert x.shape == y.shape == z.shape == (2, 3)
    for i in range(2):
        for j in range(3):
            assert np.allclose((x[i, j], y[i, j], z[i, j]), ref_forward(lat[i, 0], lon[j], 550e3), atol=1e-3, rtol=0)


def test_polar_axis_and_geocentre():
    lat, lon, h = gm.ecef_to_geodetic(0.0, 0.0, B + 550e3)
    assert (lat, lon) == (90.0, 0.0) and h == pytest.approx(550e3, abs=1e-6)
    lat, lon, h = (float(a) for a in gm.ecef_to_geodetic_vec(0.0, 0.0, -(B + 10.0)))
    assert (lat, lon) == (-90.0, 0.0) and h == pytest.approx(10.0, abs=1e-6)
    assert gm.ecef_to_geodetic(0.0, 0.0, 0.0) == pytest.approx((90.0, 0.0, -B))
    with pytest.raises(ValueError):
        gm.ecef_to_geodetic_vec(0.0, 0.0, 0.0)


def test_scalar_converters_gain_no_new_errors():
    assert all(math.isnan(v) for v in gm.ecef_to_geodetic(float("nan"), 1.0, 1.0)[:1])
    gm.geodetic_to_ecef(91.0, 0.0, 0.0)  # no ValueError (Section 6.1.3)


@pytest.mark.parametrize("bad", [True, np.bool_(False), "1.0", None, 1j, float("nan"), float("inf")])
def test_vector_entries_reject_non_real_or_non_finite(bad):
    with pytest.raises(ValueError):
        gm.geodetic_to_ecef_vec(bad, 0.0, 0.0)
    if not isinstance(bad, (bool, np.bool_)):
        with pytest.raises(ValueError):
            gm.nadir_unit_vec([bad, 0.0, 7e6])


def test_bool_arrays_are_rejected():
    with pytest.raises(ValueError):
        gm.nadir_unit_vec(np.array([True, False, True]))


def test_shape_errors_and_empty():
    with pytest.raises(ValueError):
        gm.geodetic_to_ecef_vec(np.zeros(2), np.zeros(3), 0.0)
    with pytest.raises(ValueError):
        gm.nadir_unit_vec(np.zeros((2, 2)) + 7e6)
    with pytest.raises(ValueError):
        gm.geodetic_to_ecef_vec([0.0, 95.0], 0.0, 0.0)  # one bad element fails the call
    x, y, z = gm.geodetic_to_ecef_vec(np.zeros(0), np.zeros(0), 0.0)
    assert x.shape == (0,)
    out = gm.geodetic_to_ecef_vec(0.0, 0.0, 0.0)
    assert all(isinstance(a, np.ndarray) and a.shape == () for a in out)


def test_inputs_are_not_modified():
    lat = np.array([10.0, 20.0])
    lat.setflags(write=False)
    gm.geodetic_to_ecef_vec(lat, 0.0, 0.0)
    gm.enu_basis_vec(lat, 0.0)


# --- ENU and look angles --------------------------------------------------------
def test_iogp_enu_example():
    origin = (3652755.3058, 319574.6799, 5201547.3536)
    target = (3771793.968, 140253.342, 5124304.349)
    delta = np.subtract(target, origin)
    e, n, u = gm.ecef_delta_to_enu(delta, 55.0, 5.0)
    assert (e, n, u) == pytest.approx((-189013.869, -128642.040, -4220.171), abs=1e-3)


def test_look_angles_zenith_and_up_is_geodetic():
    g = ref_forward(45.0, 30.0, 0.0)
    s = ref_forward(45.0, 30.0, 550e3)  # straight up the geodetic normal
    rng, el, az = gm.look_angles_ecef(s, g, 45.0, 30.0)
    assert rng == pytest.approx(550e3, abs=1e-3) and el == 90.0 and az == 0.0
    # A point straight above along the radial direction is NOT at zenith (radial-Up control).
    radial = np.array(g) * (1.0 + 550e3 / np.linalg.norm(g))
    _, el_radial, _ = gm.look_angles_ecef(radial, g, 45.0, 30.0)
    assert 89.0 < el_radial < 89.9


def test_azimuth_range_and_zero_range_error():
    g = ref_forward(0.0, 0.0, 0.0)
    east_sat = np.array(g) + np.array([1e5, 1e6, 0.0])  # up 1e5, east 1e6
    _, _, az = gm.look_angles_ecef(east_sat, g, 0.0, 0.0)
    assert az == pytest.approx(90.0, abs=1e-9)
    _, _, az = gm.look_angles_ecef(np.array(g) + np.array([1e5, 0.0, -1e6]), g, 0.0, 0.0)
    assert 0.0 <= az < 360.0 and az == pytest.approx(180.0, abs=1e-9)
    with pytest.raises(ValueError):
        gm.look_angles_ecef(g, g, 0.0, 0.0)


# --- nadir, off-axis, intersection ------------------------------------------------
@pytest.mark.parametrize("h,expected", [(550e3, 45.015299598), (1200e3, 45.030513685)])
def test_nadir_point_appendix_b(h, expected):
    sat = rg.satellite_ecef_m(45.0, 30.0, h / 1000.0)
    hit, dist, lat, lon = rg.nadir_centre(sat)
    assert lat == pytest.approx(expected, abs=1e-8)
    assert lat == pytest.approx(ref_nadir_hit_lat(45.0, h), abs=1e-9)
    assert lon == pytest.approx(30.0, abs=1e-9)
    assert dist == pytest.approx(np.linalg.norm(sat - hit), abs=1e-6)
    resid = (hit[0] ** 2 + hit[1] ** 2) / A**2 + hit[2] ** 2 / B**2 - 1.0
    assert abs(resid) <= 1e-12


def test_ray_miss_and_strict_policy():
    o = (A + 550e3, 0.0, 0.0)
    assert gm.intersect_ray_wgs84(o, (0.0, 1.0, 0.0)) is None  # above the limb
    assert gm.intersect_ray_wgs84(o, (1.0, 0.0, 0.0)) is None  # pointing away
    hit, dist = gm.intersect_ray_wgs84(o, (-2.0, 0.0, 0.0))  # non-unit direction
    assert hit == pytest.approx((A, 0.0, 0.0), abs=1e-6) and dist == pytest.approx(550e3, abs=1e-6)
    assert gm.intersect_ray_wgs84((A, 0.0, 0.0), (1.0, 0.0, 0.0)) is None  # surface, outward
    hits, dists, ok = gm.intersect_ray_wgs84_vec(np.array([o, o]), np.array([[-1.0, 0, 0], [0, 1.0, 0]]))
    assert ok.tolist() == [True, False] and np.isnan(dists[1]) and np.all(np.isnan(hits[1]))
    with pytest.raises(ValueError):
        gm.intersect_ray_wgs84(o, (0.0, 0.0, 0.0))


def test_off_axis_and_steering():
    sat = rg.satellite_ecef_m(0.0, 0.0, 550.0)
    nadir = gm.nadir_unit_vec(sat)
    assert float(gm.off_axis_deg_vec(nadir, sat, np.zeros(3))) == pytest.approx(0.0, abs=1e-9)
    pt = sat + np.array([0.0, 1.0, 0.0]) * 1e5 + nadir * 1e5
    assert float(gm.off_axis_deg_vec(nadir, sat, pt)) == pytest.approx(45.0, abs=1e-9)
    assert float(gm.off_axis_deg_vec(nadir * 7.0, sat, pt)) == pytest.approx(45.0, abs=1e-9)
    with pytest.raises(ValueError):
        gm.off_axis_deg_vec(nadir, sat, sat)


# --- frame velocity and axes --------------------------------------------------------
def test_stationary_rebuild_is_east_without_speed_check():
    r = rg.satellite_ecef_m(0.0, 30.0, 550.0)  # fixed satellite at low altitude
    v = gm.lvlh_reference_velocity_m(r, (0.0, 0.0, 0.0))
    assert v == pytest.approx((-OMEGA * r[1], OMEGA * r[0], 0.0), rel=1e-15)
    assert math.hypot(*v) == pytest.approx(OMEGA * math.hypot(r[0], r[1]), rel=1e-12)  # ~0.51 km/s


def test_wrong_unit_velocity_is_rejected():
    r = rg.satellite_ecef_m(0.0, 0.0, 550.0)
    with pytest.raises(ValueError, match="antenna_frame_velocity_units"):
        gm.lvlh_reference_velocity_m(r, (0.0, 7.6, 0.0))  # km/s passed as m/s


def test_geo_stationary_frame_is_east():
    r = np.array([42164e3, 0.0, 0.0])
    x, y, z = rg.orbital_frame_axes_vec_m(r, np.zeros(3))
    assert x == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)
    assert z == pytest.approx([-1.0, 0.0, 0.0], abs=1e-15)
    assert np.dot(np.cross(x, y), z) == pytest.approx(1.0, abs=1e-12)


def test_polar_stationary_frame_falls_back():
    r = np.array([0.0, 0.0, B + 550e3])
    x, _, _ = rg.orbital_frame_axes_vec_m(r, np.zeros(3))
    assert x == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)  # ECEF +X at a pole


def test_antenna_frame_angles_east_axis():
    r = np.array([42164e3, 0.0, 0.0])
    target = r + np.array([-1e6, 1e5, 0.0])  # off nadir towards East
    psi, phi = rg.antenna_frame_angles_m(r, np.zeros(3), target)
    assert psi == pytest.approx(math.degrees(math.atan2(1e5, 1e6)), abs=1e-9)
    assert phi == pytest.approx(0.0, abs=1e-9)
    assert rg.antenna_frame_angles_m(r, np.zeros(3), r) == (0.0, 0.0)  # target at satellite


# --- adapter records and the Q3 comparator ----------------------------------------
def test_link_geometry_shapes_and_default_nadir():
    ground = rg.ground_geometry(np.array([0.0, 1.0, 2.0]), 0.0)
    sat = rg.satellite_ecef_m(0.0, 0.0, 550.0)
    link = rg.link_geometry(sat, ground)
    assert link.range_m.shape == (3,) and link.sat_to_ground_unit.shape == (3, 3)
    assert float(link.off_axis_deg[0]) == pytest.approx(0.0, abs=1e-9)
    assert float(link.elevation_deg[0]) == pytest.approx(90.0, abs=1e-9)


def test_link_range_comparator():
    assert rg.link_range_ok(np.nextafter(1.0, 0.0)) is False
    assert rg.link_range_ok(1.0) is True
    assert rg.link_range_ok(np.nextafter(1.0, 2.0)) is True
    assert rg.link_range_ok(np.array([0.9, 1.1, np.nan])).tolist() == [False, True, False]
