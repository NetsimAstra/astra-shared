from astra_shared.coverage_identity import (
    build_fixed_manifest,
    build_walker_manifest,
    canonical_coverage_cell_key,
    canonical_coverage_sat_id,
)


def test_coverage_ids_and_manifests_are_deterministic():
    assert canonical_coverage_sat_id({"id": "  SAT-1  "}, source="static") == "SAT-1"
    assert canonical_coverage_cell_key({"row": 2, "col": 4}) == (2, 4)
    assert build_fixed_manifest(1, 2, 550)[0]["id"] == "fixed-0"
    first = build_walker_manifest(2, 3, 550, 53, 30, 0, "delta")
    second = build_walker_manifest(2, 3, 550, 53, 30, 0, "delta")
    assert first == second
    assert len({row["id"] for row in first}) == 6


def test_rf_identity_tracks_versioned_clutter_configuration():
    from astra_shared.coverage_identity import build_earth_fixed_rf_identity_v1

    off = build_earth_fixed_rf_identity_v1(
        {"clutter_mode": "disabled", "clutter_percentile": 50.0}
    )
    p50 = build_earth_fixed_rf_identity_v1(
        {"clutter_mode": "worldcover_p2108_p833", "clutter_percentile": 50.0}
    )
    p90 = build_earth_fixed_rf_identity_v1(
        {"clutter_mode": "worldcover_p2108_p833", "clutter_percentile": 90.0}
    )
    assert off != p50 != p90
    assert off["clutter_percentile"] is None
    assert "clutter_enable" not in p50


def test_rf_identity_treats_null_min_elevation_deg_as_not_supplied():
    from astra_shared.coverage_identity import build_earth_fixed_rf_identity_v1

    legacy = build_earth_fixed_rf_identity_v1({"min_el_deg": 12.0})
    null_canonical = build_earth_fixed_rf_identity_v1(
        {"min_elevation_deg": None, "min_el_deg": 12.0}
    )
    canonical = build_earth_fixed_rf_identity_v1({"min_elevation_deg": 12.0})
    assert (
        legacy["min_elevation_deg"]
        == null_canonical["min_elevation_deg"]
        == canonical["min_elevation_deg"]
        == 12.0
    )
    both = build_earth_fixed_rf_identity_v1(
        {"min_elevation_deg": 20.0, "min_el_deg": 12.0}
    )
    assert both["min_elevation_deg"] == 20.0


def test_rf_identity_tracks_normalized_version_2_digital_link_values():
    from astra_shared.coverage_identity import build_earth_fixed_rf_identity_v1

    link_off = build_earth_fixed_rf_identity_v1(
        {"digital_link": False, "mcs_selection": "fixed", "overhead_percent": 0}
    )
    auto_alpha_low = build_earth_fixed_rf_identity_v1(
        {
            "digital_link": True,
            "mcs_selection": "auto",
            "shannon_attenuation_factor": 0.6,
            "overhead_percent": 14,
        }
    )
    auto_alpha_high = build_earth_fixed_rf_identity_v1(
        {
            "digital_link": True,
            "mcs_selection": "auto",
            "shannon_attenuation_factor": 1.0,
            "overhead_percent": 14,
        }
    )

    assert link_off != auto_alpha_low != auto_alpha_high
    assert "data_rate_bps" not in auto_alpha_low


def test_walker_id_is_the_engines_one_based_pl_id():
    # Plane and slot indexes are 0-based; the id is 1-based, as the
    # constellation engine names Walker satellites (PL-<plane>-SAT-<slot>).
    assert canonical_coverage_sat_id({"plane_index": 0, "sat_index": 0}, source="walker") == "PL-1-SAT-1"
    assert canonical_coverage_sat_id({"plane_index": 16, "sat_index": 2}, source="walker") == "PL-17-SAT-3"
    # Without sat_index, the slot comes from slot_index, then order_index.
    assert canonical_coverage_sat_id({"plane_index": 1}, source="walker", slot_index=4) == "PL-2-SAT-5"
    assert canonical_coverage_sat_id({}, source="walker", order_index=3) == "PL-1-SAT-4"
    # An explicit id still wins over the generated one.
    assert canonical_coverage_sat_id({"id": "custom-7", "plane_index": 0, "sat_index": 0}, source="walker") == "custom-7"


def test_walker_manifest_ids_match_the_engine_ids_in_engine_order():
    manifest = build_walker_manifest(2, 3, 550, 53, 30, 0, "delta")
    # The engine builds plane by plane, slot by slot, with id PL-{p+1}-SAT-{s+1}.
    engine_ids = [f"PL-{p + 1}-SAT-{s + 1}" for p in range(2) for s in range(3)]
    assert [row["id"] for row in manifest] == engine_ids
    assert [row["order_index"] for row in manifest] == list(range(6))
    assert not any(row["id"].startswith("walker-plane-") for row in manifest)
