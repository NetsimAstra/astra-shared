"""Conformance tests for the Radio adapter of the frozen A0 API (A0 plan v7, Section 6.2).

By default they test the stand-in ``a0_standin.rf_geometry``. WP2 copies this file
into astra-radio-engine ``tests/`` and runs it against the real module:

    A0_API_IMPL=real python -m pytest tests/test_a0_rf_geometry_contract.py

Expected values come from small independent calculations in this file.
"""

from __future__ import annotations

import importlib
import inspect
import math
import os

import numpy as np
import pytest

if os.environ.get("A0_API_IMPL", "standin") == "real":
    rg = importlib.import_module("rf_geometry")
else:
    rg = importlib.import_module("a0_standin.rf_geometry")

A = 6378137.0
F = 1.0 / 298.257223563
B = A * (1.0 - F)
E2 = F * (2.0 - F)
OMEGA = 7.2921158553e-5


def ref_forward(lat_deg, lon_deg, h):
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    n = A / math.sqrt(1.0 - E2 * math.sin(lat) ** 2)
    return np.array(
        [
            (n + h) * math.cos(lat) * math.cos(lon),
            (n + h) * math.cos(lat) * math.sin(lon),
            (n * (1.0 - E2) + h) * math.sin(lat),
        ]
    )


def unit(v):
    return v / np.linalg.norm(v)


def ref_frame_angles(sat, vrel, target, aim=None):
    """Independent single-beam frame: z nadir or towards the aim point, x = projected v_ref."""
    v_ref = vrel + OMEGA * np.array([-sat[1], sat[0], 0.0])
    z = unit(-sat) if aim is None else unit(aim - sat)
    x = unit(v_ref - np.dot(v_ref, z) * z)
    y = np.cross(z, x)
    q = unit(target - sat)
    psi = math.degrees(math.atan2(np.linalg.norm(np.cross(z, q)), np.dot(z, q)))
    phi = math.degrees(math.atan2(np.dot(q, y), np.dot(q, x)))
    return psi, phi


def leo_state():
    sat = ref_forward(45.0, 30.0, 550e3)
    lon = math.radians(30.0)
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north_ish = unit(np.cross(unit(sat), east))
    v_inertial = 7585.0 * unit(0.6 * east + 0.8 * north_ish)
    vrel = v_inertial - OMEGA * np.array([-sat[1], sat[0], 0.0])
    return sat, vrel


SIGNATURES = {
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


@pytest.mark.parametrize("name,params", sorted(SIGNATURES.items()))
def test_signature(name, params):
    assert list(inspect.signature(getattr(rg, name)).parameters) == params


def test_link_geometry_boresight_is_keyword_only():
    p = inspect.signature(rg.link_geometry).parameters["boresight_unit"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is None
    assert rg.MIN_LINK_RANGE_M == 1.0


# --- records ---------------------------------------------------------------------
def test_satellite_and_ground_geometry():
    assert np.allclose(rg.satellite_ecef_m(45.0, 30.0, 550.0), ref_forward(45.0, 30.0, 550e3), atol=1e-6)
    g = rg.ground_geometry(np.array([0.0, 45.0]), 30.0, 0.0)
    assert g.ecef_m.shape == (2, 3) and g.lat_deg.shape == (2,)
    la, lo = math.radians(45.0), math.radians(30.0)
    geodetic_up = [math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)]
    assert np.allclose(g.up[1], geodetic_up, atol=1e-15)


def test_link_geometry_values_and_line_of_sight_sign():
    sat = rg.satellite_ecef_m(0.0, 0.0, 550.0)
    ground = rg.ground_geometry(np.array([0.0, 1.0, 2.0]), 0.0)
    link = rg.link_geometry(sat, ground)
    assert link.range_m.shape == (3,) and link.sat_to_ground_unit.shape == (3, 3)
    assert float(link.off_axis_deg[0]) == pytest.approx(0.0, abs=1e-9)
    assert float(link.elevation_deg[0]) == pytest.approx(90.0, abs=1e-9)
    expected = unit(ground.ecef_m[2] - sat)  # from the satellite towards the ground
    assert np.allclose(link.sat_to_ground_unit[2], expected, atol=1e-15)


def test_link_geometry_default_boresight_is_geocentric_nadir():
    sat = rg.satellite_ecef_m(45.0, 30.0, 550.0)
    link = rg.link_geometry(sat, rg.ground_geometry(45.0, 30.0))  # geodetic sub-point
    assert float(link.off_axis_deg) == pytest.approx(0.177124, abs=1e-4)


def test_link_geometry_uses_an_explicit_boresight():
    sat = rg.satellite_ecef_m(45.0, 30.0, 550.0)
    ground = rg.ground_geometry(45.3, 30.0)
    aim = unit(ref_forward(44.7, 30.0, 0.0) - sat)
    link = rg.link_geometry(sat, ground, boresight_unit=aim)
    q = unit(ground.ecef_m - sat)
    expected = math.degrees(math.atan2(np.linalg.norm(np.cross(aim, q)), np.dot(aim, q)))
    assert float(link.off_axis_deg) == pytest.approx(expected, abs=1e-9)
    assert expected > 1.0  # discriminates from the nadir default


def test_nadir_centre_appendix_b():
    sat = rg.satellite_ecef_m(45.0, 30.0, 550.0)
    hit, dist, lat, lon = rg.nadir_centre(sat)
    assert lat == pytest.approx(45.015299598, abs=1e-8) and lon == pytest.approx(30.0, abs=1e-9)
    assert dist == pytest.approx(np.linalg.norm(sat - hit), abs=1e-6)
    with pytest.raises(ValueError):
        rg.nadir_centre(np.array([A - 10.0, 0.0, 0.0]))  # not outside the ellipsoid


# --- frames ----------------------------------------------------------------------
def test_orbital_axes_nadir_is_geocentric_and_right_handed():
    sat, vrel = leo_state()
    x, y, z = rg.orbital_frame_axes_vec_m(sat, vrel)
    assert np.allclose(z, unit(-sat), atol=1e-15)
    assert np.dot(np.cross(x, y), z) == pytest.approx(1.0, abs=1e-12)
    v_ref = vrel + OMEGA * np.array([-sat[1], sat[0], 0.0])
    assert np.allclose(x, unit(v_ref - np.dot(v_ref, z) * z), atol=1e-12)


def test_geo_stationary_frame_is_east():
    r = np.array([42164e3, 0.0, 0.0])
    x, y, z = rg.orbital_frame_axes_vec_m(r, np.zeros(3))
    assert x == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)
    assert z == pytest.approx([-1.0, 0.0, 0.0], abs=1e-15)


def test_fallback_order_projected_north_then_plus_x():
    # Velocity parallel to nadir off the pole: the frame uses projected North.
    r = rg.satellite_ecef_m(45.0, 30.0, 550.0)
    k = 8000.0 / np.linalg.norm(r)
    vrel = k * r - OMEGA * np.array([-r[1], r[0], 0.0])  # v_ref = k r, radial, 8 km/s
    x, _, z = rg.orbital_frame_axes_vec_m(r, vrel)
    north = np.array([0.0, 0.0, 1.0])
    assert np.allclose(x, unit(north - np.dot(north, z) * z), atol=1e-9)
    # Stationary on the polar axis: omega x r = 0, North is undefined, so ECEF +X.
    x, _, _ = rg.orbital_frame_axes_vec_m(np.array([0.0, 0.0, B + 550e3]), np.zeros(3))
    assert x == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)


def test_antenna_frame_angles_nadir_frame():
    sat, vrel = leo_state()
    target = ref_forward(45.4, 30.5, 0.0)
    psi, phi = rg.antenna_frame_angles_m(sat, vrel, target)
    assert (psi, phi) == pytest.approx(ref_frame_angles(sat, vrel, target), abs=1e-9)


def test_antenna_frame_angles_steered_frame_uses_aim_point():
    sat, vrel = leo_state()
    aim = ref_forward(44.0, 31.0, 0.0)  # Earth-fixed serving target
    target = ref_forward(44.3, 31.4, 0.0)
    psi, phi = rg.antenna_frame_angles_m(sat, vrel, target, aim)
    assert (psi, phi) == pytest.approx(ref_frame_angles(sat, vrel, target, aim), abs=1e-9)
    nadir_psi, nadir_phi = ref_frame_angles(sat, vrel, target)
    assert abs(psi - nadir_psi) > 0.5  # steering is applied
    psi_v, phi_v = rg.antenna_frame_angles_vec_m(sat[None, :], vrel[None, :], target[None, :], aim[None, :])
    assert (float(psi_v[0]), float(phi_v[0])) == pytest.approx((psi, phi), abs=1e-12)


def test_antenna_frame_angles_edge_cases():
    r = np.array([42164e3, 0.0, 0.0])
    target = r + np.array([-1e6, 1e5, 0.0])  # off nadir towards East
    psi, phi = rg.antenna_frame_angles_m(r, np.zeros(3), target)
    assert psi == pytest.approx(math.degrees(math.atan2(1e5, 1e6)), abs=1e-9)
    assert phi == pytest.approx(0.0, abs=1e-9)
    assert rg.antenna_frame_angles_m(r, np.zeros(3), r) == (0.0, 0.0)  # target at the satellite
    # An aim point at the satellite leaves the frame on nadir.
    assert rg.antenna_frame_angles_m(r, np.zeros(3), target, r) == pytest.approx((psi, phi), abs=1e-12)


# --- Q3 comparator ----------------------------------------------------------------
def test_link_range_comparator():
    assert rg.link_range_ok(np.nextafter(1.0, 0.0)) is False
    assert rg.link_range_ok(1.0) is True
    assert rg.link_range_ok(np.nextafter(1.0, 2.0)) is True
    assert rg.link_range_ok(np.array([0.9, 1.1, np.nan])).tolist() == [False, True, False]


def test_frame_functions_apply_the_speed_guard():
    sat = rg.satellite_ecef_m(0.0, 0.0, 550.0)
    wrong_unit = np.array([0.0, 7.6, 0.0])  # km/s passed as m/s
    with pytest.raises(ValueError, match="antenna_frame_velocity_units"):
        rg.orbital_frame_axes_vec_m(sat, wrong_unit)
    with pytest.raises(ValueError, match="antenna_frame_velocity_units"):
        rg.antenna_frame_angles_vec_m(sat, wrong_unit, np.zeros(3))


def test_propagated_geo_frame_is_about_east():
    r = np.array([42164e3, 0.0, 0.0])
    x, _, _ = rg.orbital_frame_axes_vec_m(r, np.array([0.1, -0.2, 0.05]))
    assert np.dot(x, [0.0, 1.0, 0.0]) > 0.9999


def test_ground_height_is_in_km():
    g = rg.ground_geometry(45.0, 30.0, 1.0)
    assert np.allclose(g.ecef_m, ref_forward(45.0, 30.0, 1000.0), atol=1e-6)
    assert rg.link_range_ok(np.inf) is False
