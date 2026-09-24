#!/usr/bin/env python3
"""One-time converter for pre-versioned Astra clutter RF settings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RF_SCHEMA_VERSION = 1
CLUTTER_MODE_DISABLED = "disabled"
CLUTTER_MODE_WORLDCOVER = "worldcover_p2108_p833"
DEFAULT_CLUTTER_PERCENTILE = 50.0
OLD_CLUTTER_FIELDS = {
    "clutter_enable",
    "clutter_enabled",
    "clutter_values",
    "clutter_fallback",
}
RF_BLOCK_KEYS = {"rf", "rf_params", "rf_settings"}
RF_FIELD_MARKERS = {"frequency_ghz", "freq_hz", "eirp_dbw", "rx_gain_dbi"}


class ConverterError(ValueError):
    """Raised when a clutter RF block cannot be converted safely."""


def _old_clutter_enabled(block: dict[str, Any]) -> bool:
    if "clutter_mode" in block:
        value = block["clutter_mode"]
    elif "clutter_enable" in block:
        value = block["clutter_enable"]
    elif "clutter_enabled" in block:
        value = block["clutter_enabled"]
    else:
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on", "enable", "enabled"}:
        return True
    if normalized in {"false", "0", "no", "off", "disable", "disabled"}:
        return False
    raise ConverterError(f"unsupported old clutter boolean {value!r}")


def _convert_rf_block(block: dict[str, Any], is_rf_block: bool) -> tuple[bool, bool]:
    if type(block.get("rf_schema_version")) in (int, str) and block.get("rf_schema_version") in (
        RF_SCHEMA_VERSION,
        "1",
    ):
        return False, False
    if "rf_schema_version" in block:
        raise ConverterError(
            f"unsupported rf_schema_version {block.get('rf_schema_version')!r}"
        )
    has_old_field = bool(OLD_CLUTTER_FIELDS.intersection(block)) or block.get("clutter_mode") in {
        "enable",
        "disable",
        "enabled",
        "disabled",
        "yes",
        "no",
        "on",
        "off",
        "true",
        "false",
        "1",
        "0",
    }
    if not has_old_field and not is_rf_block:
        return False, False

    if "clutter_mode" in block:
        for field in ("clutter_enable", "clutter_enabled"):
            if field in block and _old_clutter_enabled({field: block[field]}) != _old_clutter_enabled(
                {"clutter_mode": block["clutter_mode"]}
            ):
                print(f"clutter_mode={block['clutter_mode']!r} overrides {field}={block[field]!r}")
    enabled = _old_clutter_enabled(block)
    for key in OLD_CLUTTER_FIELDS:
        block.pop(key, None)
    block["rf_schema_version"] = RF_SCHEMA_VERSION
    block["clutter_mode"] = (
        CLUTTER_MODE_WORLDCOVER if enabled else CLUTTER_MODE_DISABLED
    )
    if block.get("clutter_percentile") is None:
        block["clutter_percentile"] = DEFAULT_CLUTTER_PERCENTILE
    return True, enabled


def convert_payload(value: Any, parent_key: str | None = None) -> tuple[bool, bool]:
    """Convert every clutter RF block inside a decoded JSON payload.

    Returns ``(changed, moved_to_worldcover)``. A ``clutter_values`` block alone
    never enables clutter.
    """
    changed = False
    moved_to_worldcover = False
    if isinstance(value, dict):
        is_rf_block = parent_key in RF_BLOCK_KEYS
        block_changed, block_enabled = _convert_rf_block(value, is_rf_block)
        changed = changed or block_changed
        moved_to_worldcover = moved_to_worldcover or block_enabled
        for key, child in value.items():
            child_changed, child_enabled = convert_payload(child, key)
            changed = changed or child_changed
            moved_to_worldcover = moved_to_worldcover or child_enabled
    elif isinstance(value, list):
        for child in value:
            child_changed, child_enabled = convert_payload(child)
            changed = changed or child_changed
            moved_to_worldcover = moved_to_worldcover or child_enabled
    return changed, moved_to_worldcover


def convert_file(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed, moved_to_worldcover = convert_payload(payload)
    if not changed:
        return False
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if moved_to_worldcover:
        print(f"{path}: moved to {CLUTTER_MODE_WORLDCOVER}")
    return True


def iter_json_files(paths: list[Path]):
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.json"))
        elif path.suffix.lower() == ".json":
            yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert old Astra clutter RF settings to schema version 1."
    )
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)

    changed = 0
    for path in iter_json_files(args.paths):
        if convert_file(path):
            changed += 1
    print(f"converted {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
