"""Versioned, portable snapshots for the standalone Streamlit app.

The live sketch configuration remains owned by ``st.session_state``.  This
module is deliberately Streamlit-free so saved files can be validated before
they are allowed anywhere near the UI state.
"""

from __future__ import annotations

import copy
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

import sketch_state as ss


FILE_FORMAT = "drawing-debbie-config"
SCHEMA_VERSION = 1
MAX_FILE_BYTES = 1_000_000
MAX_NAME_LENGTH = 80
MAX_TEXT_LENGTH = 200
MAX_ABS_NUMBER = 1_000_000_000

_SECTION_SOURCE_RE = re.compile(r"^c\d+-b[12]-\d+$")
_SAFE_FILENAME_RE = re.compile(r"[^a-z0-9]+")
_WINDOWS_RESERVED_FILENAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}

_DEFAULT_CONFIG = ss.make_default_config()
_TOP_LEVEL_KEYS = frozenset(_DEFAULT_CONFIG)
_CORE_KEYS = frozenset(_DEFAULT_CONFIG["cores"][0])
_LIFT_KEYS = frozenset(_DEFAULT_CONFIG["cores"][0]["bank1_lifts"][0])
_SECTION_KEYS = frozenset(_DEFAULT_CONFIG["section"])

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


class SavedConfigError(ValueError):
    """A saved configuration is malformed, unsafe, or incompatible."""


def utc_now() -> str:
    """Return a compact UTC timestamp suitable for saved-file metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_name(value: Any) -> str:
    """Validate and trim a user-facing saved configuration name."""
    if not isinstance(value, str):
        raise SavedConfigError("Configuration name must be text.")
    name = " ".join(value.strip().split())
    if not name:
        raise SavedConfigError("Enter a name for this configuration.")
    if len(name) > MAX_NAME_LENGTH:
        raise SavedConfigError(
            f"Configuration name must be {MAX_NAME_LENGTH} characters or fewer."
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise SavedConfigError("Configuration name contains unsupported characters.")
    return name


def filename_for_name(name: str) -> str:
    """Create a safe, readable filename without changing the display name."""
    normalized = unicodedata.normalize("NFKD", normalize_name(name))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SAFE_FILENAME_RE.sub("-", ascii_name).strip("-")[:60]
    if slug in _WINDOWS_RESERVED_FILENAMES:
        slug = ""
    return f"{slug or 'sketch-configuration'}.debbie.json"


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


def build_payload(
    name: str,
    config: dict,
    view_state: dict,
    *,
    saved_at: str | None = None,
    updated_at: str | None = None,
) -> dict:
    """Validate and snapshot a configuration into the public file envelope."""
    clean_name = normalize_name(name)
    validate_config(config)
    validate_view_state(view_state)
    created = saved_at or utc_now()
    updated = updated_at or created
    _validate_timestamp(created, "metadata.saved_at")
    _validate_timestamp(updated, "metadata.updated_at")
    return {
        "format": FILE_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "name": clean_name,
            "saved_at": created,
            "updated_at": updated,
        },
        "config": copy.deepcopy(config),
        "view_state": copy.deepcopy(view_state),
    }


def rename_payload(payload: dict, name: str) -> dict:
    """Return a renamed snapshot while preserving its original save time."""
    validated = validate_payload(payload)
    return build_payload(
        name,
        validated["config"],
        validated["view_state"],
        saved_at=validated["metadata"]["saved_at"],
        updated_at=utc_now(),
    )


def payload_to_bytes(payload: dict) -> bytes:
    """Serialize a validated payload as deterministic, strict UTF-8 JSON."""
    validated = validate_payload(payload)
    try:
        text = json.dumps(
            validated,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise SavedConfigError(f"Configuration could not be serialized: {exc}") from exc
    return (text + "\n").encode("utf-8")


def parse_payload(data: bytes | bytearray) -> dict:
    """Parse and validate a user-supplied saved configuration file."""
    if not isinstance(data, (bytes, bytearray)):
        raise SavedConfigError("Configuration file must contain JSON data.")
    if not data:
        raise SavedConfigError("The selected configuration file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise SavedConfigError("Configuration file is larger than the 1 MB limit.")
    try:
        text = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SavedConfigError("Configuration file must use UTF-8 text.") from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except SavedConfigError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise SavedConfigError("Configuration file is not valid JSON.") from exc
    return validate_payload(payload)


def validate_payload(payload: Any) -> dict:
    """Return a deep-copied payload after complete v1 validation."""
    _expect_mapping(payload, "file")
    _expect_exact_keys(
        payload,
        {"format", "schema_version", "metadata", "config", "view_state"},
        "file",
    )
    if payload["format"] != FILE_FORMAT:
        raise SavedConfigError("This is not a Drawing Debbie configuration file.")
    version = payload["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise SavedConfigError("schema_version must be an integer.")
    if version > SCHEMA_VERSION:
        raise SavedConfigError(
            "This configuration was created by a newer version of Drawing Debbie."
        )
    if version < SCHEMA_VERSION:
        raise SavedConfigError(
            "This configuration uses an older unsupported format."
        )

    metadata = payload["metadata"]
    _expect_mapping(metadata, "metadata")
    _expect_exact_keys(metadata, {"name", "saved_at", "updated_at"}, "metadata")
    clean_name = normalize_name(metadata["name"])
    _validate_timestamp(metadata["saved_at"], "metadata.saved_at")
    _validate_timestamp(metadata["updated_at"], "metadata.updated_at")
    validate_config(payload["config"])
    validate_view_state(payload["view_state"])
    result = copy.deepcopy(payload)
    result["metadata"]["name"] = clean_name
    return result


def validate_config(config: Any) -> None:
    """Validate the complete canonical sketch config without recalculating it."""
    _expect_mapping(config, "config")
    _expect_exact_keys(config, _TOP_LEVEL_KEYS, "config")

    if config["machine_type"] not in {"mrl", "mra"}:
        raise SavedConfigError("config.machine_type must be 'mrl' or 'mra'.")

    cores = config["cores"]
    if not isinstance(cores, list):
        raise SavedConfigError("config.cores must be a list.")
    if not 1 <= len(cores) <= ss.MAX_CORES:
        raise SavedConfigError(
            f"config.cores must contain between 1 and {ss.MAX_CORES} cores."
        )
    for index, core in enumerate(cores):
        _validate_core(core, index, config["machine_type"])

    for field in _TOP_LEVEL_BOOL_FIELDS:
        _expect_bool(config[field], f"config.{field}")
    _expect_positive_number(config["dimension_font_scale"], "config.dimension_font_scale")
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
        raise SavedConfigError("view_state.active_core is invalid.")
    if view_state["plan_variant"] not in {"all", "passenger", "fire"}:
        raise SavedConfigError("view_state.plan_variant is invalid.")
    section_source = view_state["section_source"]
    if not isinstance(section_source, str) or not _SECTION_SOURCE_RE.fullmatch(
        section_source
    ):
        raise SavedConfigError("view_state.section_source is invalid.")


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
        raise SavedConfigError(f"{path}.arrangement is invalid.")
    _expect_bool(core["common_shaft"], f"{path}.common_shaft")
    _expect_positive_number(core["wall_thickness_mm"], f"{path}.wall_thickness_mm")
    _expect_positive_number(core["lobby_width_mm"], f"{path}.lobby_width_mm")

    bank1 = core["bank1_lifts"]
    bank2 = core["bank2_lifts"]
    if not isinstance(bank1, list) or not 1 <= len(bank1) <= ss.MAX_LIFTS_PER_BANK:
        raise SavedConfigError(
            f"{path}.bank1_lifts must contain between 1 and "
            f"{ss.MAX_LIFTS_PER_BANK} lifts."
        )
    if not isinstance(bank2, list) or not 0 <= len(bank2) <= ss.MAX_LIFTS_PER_BANK:
        raise SavedConfigError(
            f"{path}.bank2_lifts must contain at most {ss.MAX_LIFTS_PER_BANK} lifts."
        )
    if core["arrangement"] == "Facing" and not bank2:
        raise SavedConfigError(f"{path}.bank2_lifts cannot be empty for a Facing core.")

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
            raise SavedConfigError(
                f"{path}.{separator_field} must contain {expected_length} entries."
            )
        if any(value not in {"rcc_wall", "steel_beam"} for value in separators):
            raise SavedConfigError(f"{path}.{separator_field} contains an invalid value.")


def _validate_lift(lift: Any, path: str, machine_type: str) -> None:
    _expect_mapping(lift, path)
    _expect_exact_keys(lift, _LIFT_KEYS, path)
    if lift["type"] not in {"passenger", "fire"}:
        raise SavedConfigError(f"{path}.type is invalid.")
    if lift["door_opening_type"] not in {"centre", "telescopic"}:
        raise SavedConfigError(f"{path}.door_opening_type is invalid.")
    if lift["door_offset_direction"] not in {"left", "right"}:
        raise SavedConfigError(f"{path}.door_offset_direction is invalid.")
    _expect_text(lift["lift_id"], f"{path}.lift_id", max_length=MAX_NAME_LENGTH)
    for field in _LIFT_BOOL_FIELDS:
        _expect_bool(lift[field], f"{path}.{field}")

    for field in _LIFT_KEYS - _LIFT_BOOL_FIELDS - _LIFT_STRING_FIELDS:
        value = lift[field]
        field_path = f"{path}.{field}"
        if value is None:
            if field in _REQUIRED_LIFT_NUMERIC_FIELDS:
                raise SavedConfigError(f"{field_path} is required.")
            continue
        allow_zero = field == "door_offset_mm"
        _expect_number(value, field_path, allow_zero=allow_zero)

    # Retain machine-specific dormant values exactly; only ensure the machine
    # selector itself is a supported value.
    if machine_type not in {"mrl", "mra"}:
        raise SavedConfigError(f"{path} has an unsupported machine type.")


def _validate_section(section: Any) -> None:
    path = "config.section"
    _expect_mapping(section, path)
    _expect_exact_keys(section, _SECTION_KEYS, path)
    for field in _SECTION_KEYS:
        value = section[field]
        field_path = f"{path}.{field}"
        if value is None and field == "machine_room_height":
            continue
        _expect_positive_number(value, field_path)


def _expect_mapping(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise SavedConfigError(f"{path} must be an object.")


def _expect_exact_keys(value: dict, expected: set | frozenset, path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise SavedConfigError(f"{path} is missing: {', '.join(missing)}.")
    if extra:
        raise SavedConfigError(f"{path} contains unsupported fields: {', '.join(extra)}.")


def _expect_bool(value: Any, path: str) -> None:
    if not isinstance(value, bool):
        raise SavedConfigError(f"{path} must be true or false.")


def _expect_text(value: Any, path: str, *, max_length: int = MAX_TEXT_LENGTH) -> None:
    if not isinstance(value, str):
        raise SavedConfigError(f"{path} must be text.")
    if len(value) > max_length:
        raise SavedConfigError(f"{path} is too long.")
    if any(ord(char) < 32 and char not in "\t" for char in value):
        raise SavedConfigError(f"{path} contains unsupported characters.")


def _expect_positive_number(value: Any, path: str) -> None:
    _expect_number(value, path, allow_zero=False)


def _expect_number(value: Any, path: str, *, allow_zero: bool) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SavedConfigError(f"{path} must be a number.")
    if isinstance(value, float) and math.isnan(value):
        raise SavedConfigError(
            f"{path} is blank. Fill blank inputs before saving the configuration."
        )
    if not math.isfinite(value):
        raise SavedConfigError(f"{path} must be a finite number.")
    if abs(value) > MAX_ABS_NUMBER:
        raise SavedConfigError(f"{path} is outside the supported range.")
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "zero or greater" if allow_zero else "greater than zero"
        raise SavedConfigError(f"{path} must be {qualifier}.")


def _validate_timestamp(value: Any, path: str) -> None:
    if not isinstance(value, str) or len(value) > 64:
        raise SavedConfigError(f"{path} must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SavedConfigError(f"{path} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise SavedConfigError(f"{path} must include a timezone.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SavedConfigError(f"Configuration file repeats the field '{key}'.")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise SavedConfigError(f"Configuration file contains invalid number {value}.")

