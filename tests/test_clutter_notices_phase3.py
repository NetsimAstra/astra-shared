import numpy as np

from astra_shared.clutter import LOOKUP_STATE_TO_CODE, LookupState
from astra_shared.clutter_config import ClutterTally, build_clutter_envelope


def _rf(mode="worldcover_p2108_p833", frequency_ghz=12.0):
    return {
        "rf_schema_version": 1,
        "clutter_mode": mode,
        "clutter_percentile": 50.0,
        "freq_hz": frequency_ghz * 1e9,
    }


def test_disabled_clutter_has_no_notices():
    tally = ClutterTally()
    tally.add_state(LookupState.TILE_MISSING)
    assert build_clutter_envelope(_rf("disabled", 0.1), tally) == {
        "model": "disabled",
        "rf_schema_version": 1,
        "percentile": None,
        "notices": [],
    }


def test_frequency_notices_and_data_notice_compose():
    tally = ClutterTally()
    tally.add_grid(
        np.array([
            LOOKUP_STATE_TO_CODE[LookupState.TILE_MISSING],
            LOOKUP_STATE_TO_CODE[LookupState.CLASS],
            LOOKUP_STATE_TO_CODE[LookupState.READ_FAILED],
        ]),
        np.array([True, True, False]),
    )
    envelope = build_clutter_envelope(_rf(frequency_ghz=6.0), tally)
    assert [notice["code"] for notice in envelope["notices"]] == [
        "clutter.interim_sub10ghz",
        "clutter.data_unavailable",
    ]
    assert envelope["notices"][1]["count"] == 1
    assert envelope["notices"][1]["total"] == 2


def test_rasterio_unavailable_takes_precedence_over_missing_data():
    tally = ClutterTally()
    tally.add_state(LookupState.TILE_MISSING)
    tally.add_state(LookupState.RASTERIO_UNAVAILABLE)
    envelope = build_clutter_envelope(_rf(frequency_ghz=120.0), tally)
    assert [notice["code"] for notice in envelope["notices"]] == [
        "clutter.above_100ghz",
        "clutter.rasterio_unavailable",
    ]


def test_below_window_notice():
    notices = build_clutter_envelope(_rf(frequency_ghz=0.4))["notices"]
    assert [notice["code"] for notice in notices] == ["clutter.below_0p5ghz"]
