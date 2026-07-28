import copy

import pytest

import saved_sketches as saved
import sketch_state as ss


FIXED_TIME = "2026-07-27T12:00:00Z"
FIXED_ID = "2f99134d-aebb-4018-8d7c-f1e53f79c074"


def _snapshot(config=None, name="Hotel Core A"):
    return saved.build_snapshot(
        name,
        config or ss.make_default_config(),
        saved.make_view_state(),
    )


def _row(snapshot=None):
    return {
        "id": FIXED_ID,
        **(snapshot or _snapshot()),
        "created_at": FIXED_TIME,
        "updated_at": FIXED_TIME,
    }


def test_default_config_snapshot_is_valid_and_detached():
    config = ss.make_default_config()

    snapshot = saved.validate_snapshot(_snapshot(config))

    assert snapshot["config"] == config
    assert snapshot["config"] is not config
    snapshot["config"]["section"]["pit_depth"] = 9999
    assert config["section"]["pit_depth"] != 9999


def test_mra_facing_multi_lift_summary_and_validation():
    config = ss.make_default_config()
    config["machine_type"] = "mra"
    core = ss.make_default_core("mra", "Tower A")
    core["arrangement"] = "Facing"
    core["bank1_lifts"] = [
        ss.make_default_lift("passenger", "mra"),
        ss.make_default_lift("fire", "mra"),
    ]
    core["bank2_lifts"] = [
        ss.make_default_lift("passenger", "mra"),
        ss.make_default_lift("passenger", "mra"),
    ]
    core["separator_types_bank1"] = ["rcc_wall"]
    core["separator_types_bank2"] = ["steel_beam"]
    config["cores"] = [core]
    config = ss.renumber_lift_ids(config)

    snapshot = _snapshot(config)

    assert snapshot["config"] == config
    assert saved.config_summary(config) == "MRA · 1 core · 4 lifts"


def test_blank_numeric_input_is_rejected_before_supabase():
    config = ss.make_default_config()
    config["section"]["pit_depth"] = float("nan")

    with pytest.raises(saved.SavedSketchError, match="blank"):
        _snapshot(config, "Incomplete")


def test_unsupported_schema_and_config_fields_are_rejected():
    snapshot = _snapshot()
    snapshot["schema_version"] = saved.SCHEMA_VERSION + 1
    with pytest.raises(saved.SavedSketchError, match="newer version"):
        saved.validate_snapshot(snapshot)

    snapshot = _snapshot()
    snapshot["config"]["cores"][0]["bank1_lifts"][0]["unexpected"] = 1
    with pytest.raises(saved.SavedSketchError, match="unsupported fields"):
        saved.validate_snapshot(snapshot)


def test_names_are_normalized_and_bounded():
    assert saved.normalize_name("  Dubai   Hotel – Core A  ") == "Dubai Hotel – Core A"
    with pytest.raises(saved.SavedSketchError, match="Enter a name"):
        saved.normalize_name("   ")
    with pytest.raises(saved.SavedSketchError, match="80"):
        saved.normalize_name("x" * 81)


def test_copy_name_is_unique_case_insensitively_and_bounded():
    assert saved.available_copy_name(
        "Hotel Core",
        ["hotel core", "Hotel Core copy", "HOTEL CORE COPY 2"],
    ) == "Hotel Core copy 3"

    result = saved.available_copy_name("x" * 80, ["x" * 80])
    assert result.endswith(" copy")
    assert len(result) == saved.MAX_NAME_LENGTH


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("active_core", -1),
        ("plan_variant", "side"),
        ("section_source", "lift-one"),
    ],
)
def test_view_state_is_validated(field, value):
    state = saved.make_view_state()
    state[field] = value

    with pytest.raises(saved.SavedSketchError, match=field):
        saved.validate_view_state(state)


def test_supabase_record_is_validated_and_detached():
    original = _row()

    record = saved.record_from_row(original)

    assert record == original
    assert record is not original
    assert record["config"] is not original["config"]
    record["config"]["section"]["pit_depth"] = 9999
    assert original["config"]["section"]["pit_depth"] != 9999


def test_supabase_record_requires_valid_id_and_timestamps():
    bad_id = _row()
    bad_id["id"] = "not-a-uuid"
    with pytest.raises(saved.SavedSketchError, match="invalid ID"):
        saved.record_from_row(bad_id)

    bad_timestamp = copy.deepcopy(_row())
    bad_timestamp["updated_at"] = "yesterday"
    with pytest.raises(saved.SavedSketchError, match="ISO-8601"):
        saved.record_from_row(bad_timestamp)


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-07-27T12:00:00Z", "2026-07-27 16:00"),
        ("2026-07-27T20:30:00+00:00", "2026-07-28 00:30"),
        ("2026-07-27T16:00:00+04:00", "2026-07-27 16:00"),
    ],
)
def test_timestamp_is_formatted_in_uae_local_time(timestamp, expected):
    assert saved.format_uae_timestamp(timestamp) == expected


@pytest.mark.parametrize("timestamp", ["yesterday", "2026-07-27T12:00:00"])
def test_uae_timestamp_format_requires_timezone_aware_iso_value(timestamp):
    with pytest.raises(saved.SavedSketchError):
        saved.format_uae_timestamp(timestamp)
