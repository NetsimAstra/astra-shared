from astra_shared.param_parsing import parse_rf_params


def _versioned_rf(**overrides):
    params = {
        "rf_schema_version": 1,
        "clutter_mode": "disabled",
        "clutter_percentile": 50.0,
    }
    params.update(overrides)
    return params


def test_conjunctive_pfd_preset_preserves_both_checks():
    rf = parse_rf_params(
        _versioned_rf(compute_pfd=True, pfd_limit_band="C-6825-7075-FSS")
    )

    assert rf["pfd_checks"] == [
        {"l0": -154.0, "l25": -144.0, "ref_bw_hz": 4000.0},
        {"l0": -134.0, "l25": -124.0, "ref_bw_hz": 1000000.0},
    ]


def test_shaped_pfd_preset_preserves_shape_definition():
    rf = parse_rf_params(
        _versioned_rf(compute_pfd=True, pfd_limit_band="Q-37500-40000-GSO")
    )

    assert rf["pfd_checks"] == [
        {"ref_bw_hz": 1000000.0, "shape": "q_gso_127"}
    ]
