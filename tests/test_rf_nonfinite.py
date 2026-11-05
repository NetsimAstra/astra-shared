"""Regression coverage for RF-only non-finite input rejection (#88)."""

import pytest

from astra_shared.param_parsing import _RF_FLOAT_FIELDS, parse_rf_params
from astra_shared.rf_schema import RfKeyError


RF = {"rf_schema_version": 2, "clutter_mode": "disabled"}
INVALID = ("nan", "inf", "-inf", 10**400)


@pytest.mark.parametrize("field", _RF_FLOAT_FIELDS)
@pytest.mark.parametrize("value", INVALID)
def test_nonfinite_rf_input_names_its_field(field, value):
    with pytest.raises(RfKeyError) as caught:
        parse_rf_params({**RF, field: value})

    assert caught.value.key == field
    assert caught.value.codes == [f"{field}_invalid"]


@pytest.mark.parametrize("field", _RF_FLOAT_FIELDS)
def test_collect_errors_keeps_nonfinite_field_code(field):
    parsed = parse_rf_params({**RF, field: "nan"}, collect_errors=True)

    assert f"{field}_invalid" in parsed["rf_param_errors"]


@pytest.mark.parametrize("field", ("frequency_ghz", "bandwidth_mhz"))
def test_rf_unit_conversion_cannot_overflow(field):
    with pytest.raises(RfKeyError) as caught:
        parse_rf_params({**RF, field: 1e308})

    assert caught.value.key == field
