"""Validation for Supabase-backed saved sketches.

The live sketch configuration remains owned by ``st.session_state``.  This
module is deliberately Streamlit- and database-free so snapshots can be
validated before they cross either boundary.
"""

from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import sketch_state as ss


APP_SCOPE = "drawing-debbie"
SCHEMA_VERSION = 1
MAX_NAME_LENGTH = 80
MAX_TEXT_LENGTH = 200
MAX_ABS_NUMBER = 1_000_000_000
UAE_TIMEZONE = timezone(timedelta(hours=4))

_SECTION_SOURCE_RE = re.compile(r"^c\d+-b[12]-\d+$")

_DEFAULT_CONFIG = ss.make_default_config()
_TOP_LEVEL_KEYS = frozenset(_DEFAULT_CONFIG)
_CORE_KEYS = frozenset(_DEFAULT_CONFIG["cores"][0])
_LIFT_KEYS = frozenset(_DEFAULT_CONFIG["cores"][0]["bank1_lifts"][0])
# Required section keys. The floor-label keys are optional: snapshots saved
# before they existed omit them (blank = generic landing labels).
_SECTION_KEYS = frozenset(_DEFAULT_CONFIG["section"]) - ss.FLOOR_LABEL_KEYS

_TOP_LEVEL_BOOL_FIELDS = frozenset(
    key for key, value in _DEFAULT_CONFIG.items() if isinstance(value, bool)
)
_LIFT_BOOL_FIELDS = frozenset({"double_entrance", "swap_brackets"})
_LIFT_STRING_FIELDS = frozenset(
    {"type", "lift_id", "door_opening_type", "door_offset_direction"}
)
_REQUIRED_LIFT_NUMERIC_FIELDS = frozenset(
    {
        "width",
        "depth",
        "cabin_height",
        "shaft_width",
        "shaft_depth",
        "door_width",
        "door_height",
        "structural_opening_width",
        "structural_opening_height",
        "door_offset_mm",
    }
)


class SavedSketchError(ValueError):
    """A saved configuration is malformed, unsafe, or incompatible."""


def normalize_name(value: Any) -> str:
    """Validate and trim a user-facing saved configuration name."""
    if not isinstance(value, str):
        raise SavedSketchError("Sketch name must be text.")
    name = " ".join(value.strip().split())
    if not name:
        raise SavedSketchError("Enter a name for this sketch.")
    if len(name) > MAX_NAME_LENGTH:
        raise SavedSketchError(
            f"Sketch name must be {MAX_NAME_LENGTH} characters or fewer."
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise SavedSketchError("Sketch name contains unsupported characters.")
    return name


def available_copy_name(value: Any, existing_names: list[str]) -> str:
    """Return a conventional, case-insensitively unique copy name."""
    name = normalize_name(value)
    existing = {
        normalized.casefold()
        for item in existing_names
        if isinstance(item, str)
        for normalized in [normalize_name(item)]
    }
    for number in range(1, 10_001):
        suffix = " copy" if number == 1 else f" copy {number}"
        base = name[: MAX_NAME_LENGTH - len(suffix)].rstrip()
        candidate = f"{base}{suffix}"
        if candidate.casefold() not in existing:
            return candidate
    raise SavedSketchError("Could not choose an available copy name.")


def make_view_state(
    active_core: int = 0,
    plan_variant: str = "all",
    section_source: str = "c0-b1-0",
) -> dict:
    """Build the small, non-geometric context saved beside the config."""
    return {
        "active_core": active_core,
        "plan_variant": plan_variant,
        "section_source": section_source,
    }


def build_snapshot(
    name: str,
    config: dict,
    view_state: dict,
) -> dict:
    """Validate and deep-copy the fields persisted in Supabase."""
    clean_name = normalize_name(name)
    validate_config(config)
    validate_view_state(view_state)
    return {
        "name": clean_name,
        "schema_version": SCHEMA_VERSION,
        "config": copy.deepcopy(config),
        "view_state": copy.deepcopy(view_state),
    }


def validate_snapshot(snapshot: Any) -> dict:
    """Return a deep-copied snapshot after complete schema validation."""
    _expect_mapping(snapshot, "snapshot")
    _expect_exact_keys(
        snapshot,
        {"name", "schema_version", "config", "view_state"},
        "snapshot",
    )
    version = snapshot["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise SavedSketchError("schema_version must be an integer.")
    if version > SCHEMA_VERSION:
        raise SavedSketchError(
            "This sketch was created by a newer version of Drawing Debbie."
        )
    if version < SCHEMA_VERSION:
        raise SavedSketchError("This sketch uses an older unsupported format.")

    clean_name = normalize_name(snapshot["name"])
    validate_config(snapshot["config"])
    validate_view_state(snapshot["view_state"])
    result = copy.deepcopy(snapshot)
    result["name"] = clean_name
    return result


def record_from_row(row: Any) -> dict:
    """Validate a full Supabase row before it is loaded into app state."""
    _expect_mapping(row, "saved sketch")
    required = {
        "id",
        "name",
        "schema_version",
        "config",
        "view_state",
        "created_at",
        "updated_at",
    }
    missing = sorted(required - set(row))
    if missing:
        raise SavedSketchError(f"Saved sketch is missing: {', '.join(missing)}.")
    try:
        UUID(str(row["id"]))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SavedSketchError("Saved sketch has an invalid ID.") from exc
    _validate_timestamp(row["created_at"], "created_at")
    _validate_timestamp(row["updated_at"], "updated_at")
    snapshot = validate_snapshot(
        {
            "name": row["name"],
            "schema_version": row["schema_version"],
            "config": row["config"],
            "view_state": row["view_state"],
        }
    )
    return {
        "id": str(row["id"]),
        **snapshot,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def validate_config(config: Any) -> None:
    """Validate the complete canonical sketch config without recalculating it."""
    _expect_mapping(config, "config")
    _expect_exact_keys(config, _TOP_LEVEL_KEYS, "config")

    if config["machine_type"] not in {"mrl", "mra"}:
        raise SavedSketchError("config.machine_type must be 'mrl' or 'mra'.")

    cores = config["cores"]
    if not isinstance(cores, list):
        raise SavedSketchError("config.cores must be a list.")
    if not 1 <= len(cores) <= ss.MAX_CORES:
        raise SavedSketchError(
            f"config.cores must contain between 1 and {ss.MAX_CORES} cores."
        )
    for index, core in enumerate(cores):
        _validate_core(core, index, config["machine_type"])

    for field in _TOP_LEVEL_BOOL_FIELDS:
        _expect_bool(config[field], f"config.{field}")
    _expect_positive_number(
        config["dimension_font_scale"], "config.dimension_font_scale"
    )
    _expect_positive_number(
        config["section_dimension_font_scale"],
        "config.section_dimension_font_scale",
    )
    _validate_section(config["section"])


def validate_view_state(view_state: Any) -> None:
    _expect_mapping(view_state, "view_state")
    _expect_exact_keys(
        view_state,
        {"active_core", "plan_variant", "section_source"},
        "view_state",
    )
    active_core = view_state["active_core"]
    if (
        not isinstance(active_core, int)
        or isinstance(active_core, bool)
        or active_core < 0
        or active_core >= ss.MAX_CORES
    ):
        raise SavedSketchError("view_state.active_core is invalid.")
    if view_state["plan_variant"] not in {"all", "passenger", "fire"}:
        raise SavedSketchError("view_state.plan_variant is invalid.")
    section_source = view_state["section_source"]
    if not isinstance(section_source, str) or not _SECTION_SOURCE_RE.fullmatch(
        section_source
    ):
        raise SavedSketchError("view_state.section_source is invalid.")


def config_summary(config: dict) -> str:
    """Short human-readable summary for the sidebar selector."""
    cores = config.get("cores") or []
    lift_count = sum(
        len(core.get("bank1_lifts") or []) + len(core.get("bank2_lifts") or [])
        for core in cores
        if isinstance(core, dict)
    )
    core_word = "core" if len(cores) == 1 else "cores"
    lift_word = "lift" if lift_count == 1 else "lifts"
    machine = str(config.get("machine_type", "")).upper() or "Unknown"
    return f"{machine} · {len(cores)} {core_word} · {lift_count} {lift_word}"


def _validate_core(core: Any, index: int, machine_type: str) -> None:
    path = f"config.cores[{index}]"
    _expect_mapping(core, path)
    _expect_exact_keys(core, _CORE_KEYS, path)
    _expect_text(core["name"], f"{path}.name", max_length=MAX_NAME_LENGTH)
    if core["arrangement"] not in {"Inline", "Facing"}:
        raise SavedSketchError(f"{path}.arrangement is invalid.")
    _expect_bool(core["common_shaft"], f"{path}.common_shaft")
    _expect_positive_number(core["wall_thickness_mm"], f"{path}.wall_thickness_mm")
    _expect_positive_number(core["lobby_width_mm"], f"{path}.lobby_width_mm")

    bank1 = core["bank1_lifts"]
    bank2 = core["bank2_lifts"]
    if not isinstance(bank1, list) or not 1 <= len(bank1) <= ss.MAX_LIFTS_PER_BANK:
        raise SavedSketchError(
            f"{path}.bank1_lifts must contain between 1 and "
            f"{ss.MAX_LIFTS_PER_BANK} lifts."
        )
    if not isinstance(bank2, list) or not 0 <= len(bank2) <= ss.MAX_LIFTS_PER_BANK:
        raise SavedSketchError(
            f"{path}.bank2_lifts must contain at most {ss.MAX_LIFTS_PER_BANK} lifts."
        )
    if core["arrangement"] == "Facing" and not bank2:
        raise SavedSketchError(f"{path}.bank2_lifts cannot be empty for a Facing core.")

    for bank_name, lifts in (("bank1_lifts", bank1), ("bank2_lifts", bank2)):
        for lift_index, lift in enumerate(lifts):
            _validate_lift(
                lift,
                f"{path}.{bank_name}[{lift_index}]",
                machine_type,
            )

    for separator_field, lifts in (
        ("separator_types_bank1", bank1),
        ("separator_types_bank2", bank2),
    ):
        separators = core[separator_field]
        expected_length = max(0, len(lifts) - 1)
        if not isinstance(separators, list) or len(separators) != expected_length:
            raise SavedSketchError(
                f"{path}.{separator_field} must contain {expected_length} entries."
            )
        if any(value not in {"rcc_wall", "steel_beam"} for value in separators):
            raise SavedSketchError(
                f"{path}.{separator_field} contains an invalid value."
            )


def _validate_lift(lift: Any, path: str, machine_type: str) -> None:
    _expect_mapping(lift, path)
    _expect_exact_keys(lift, _LIFT_KEYS, path)
    if lift["type"] not in {"passenger", "fire"}:
        raise SavedSketchError(f"{path}.type is invalid.")
    if lift["door_opening_type"] not in {"centre", "telescopic"}:
        raise SavedSketchError(f"{path}.door_opening_type is invalid.")
    if lift["door_offset_direction"] not in {"left", "right"}:
        raise SavedSketchError(f"{path}.door_offset_direction is invalid.")
    _expect_text(lift["lift_id"], f"{path}.lift_id", max_length=MAX_NAME_LENGTH)
    for field in _LIFT_BOOL_FIELDS:
        _expect_bool(lift[field], f"{path}.{field}")

    for field in _LIFT_KEYS - _LIFT_BOOL_FIELDS - _LIFT_STRING_FIELDS:
        value = lift[field]
        field_path = f"{path}.{field}"
        if value is None:
            if field in _REQUIRED_LIFT_NUMERIC_FIELDS:
                raise SavedSketchError(f"{field_path} is required.")
            continue
        allow_zero = field == "door_offset_mm"
        _expect_number(value, field_path, allow_zero=allow_zero)

    # Retain machine-specific dormant values exactly; only ensure the machine
    # selector itself is a supported value.
    if machine_type not in {"mrl", "mra"}:
        raise SavedSketchError(f"{path} has an unsupported machine type.")


def _validate_section(section: Any) -> None:
    path = "config.section"
    _expect_mapping(section, path)
    floor_fields = ss.FLOOR_LABEL_KEYS & set(section)
    _expect_exact_keys(
        {key: value for key, value in section.items() if key not in floor_fields},
        _SECTION_KEYS,
        path,
    )
    for field in _SECTION_KEYS:
        value = section[field]
        field_path = f"{path}.{field}"
        if value is None and field == "machine_room_height":
            continue
        _expect_positive_number(value, field_path)
    for field in floor_fields:
        value = section[field]
        err = (ss.top_floor_error(value) if field.endswith("_top_floor_number")
               else ss.lowest_floor_error(value))
        if err:
            raise SavedSketchError(f"{path}.{field} {err}.")


def _expect_mapping(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise SavedSketchError(f"{path} must be an object.")


def _expect_exact_keys(value: dict, expected: set | frozenset, path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise SavedSketchError(f"{path} is missing: {', '.join(missing)}.")
    if extra:
        raise SavedSketchError(
            f"{path} contains unsupported fields: {', '.join(extra)}."
        )


def _expect_bool(value: Any, path: str) -> None:
    if not isinstance(value, bool):
        raise SavedSketchError(f"{path} must be true or false.")


def _expect_text(value: Any, path: str, *, max_length: int = MAX_TEXT_LENGTH) -> None:
    if not isinstance(value, str):
        raise SavedSketchError(f"{path} must be text.")
    if len(value) > max_length:
        raise SavedSketchError(f"{path} is too long.")
    if any(ord(char) < 32 and char not in "\t" for char in value):
        raise SavedSketchError(f"{path} contains unsupported characters.")


def _expect_positive_number(value: Any, path: str) -> None:
    _expect_number(value, path, allow_zero=False)


def _expect_number(value: Any, path: str, *, allow_zero: bool) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SavedSketchError(f"{path} must be a number.")
    if isinstance(value, float) and math.isnan(value):
        raise SavedSketchError(
            f"{path} is blank. Fill blank inputs before saving the sketch."
        )
    if not math.isfinite(value):
        raise SavedSketchError(f"{path} must be a finite number.")
    if abs(value) > MAX_ABS_NUMBER:
        raise SavedSketchError(f"{path} is outside the supported range.")
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "zero or greater" if allow_zero else "greater than zero"
        raise SavedSketchError(f"{path} must be {qualifier}.")


def format_uae_timestamp(value: Any) -> str:
    """Format an ISO-8601 timestamp as UAE local date and time."""
    return _parse_timestamp(value, "updated_at").astimezone(UAE_TIMEZONE).strftime(
        "%Y-%m-%d %H:%M"
    )


def _parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise SavedSketchError(f"{path} must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SavedSketchError(f"{path} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise SavedSketchError(f"{path} must include a timezone.")
    return parsed


def _validate_timestamp(value: Any, path: str) -> None:
    _parse_timestamp(value, path)
