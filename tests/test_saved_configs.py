import json

import pytest

import saved_configs as saved
import sketch_state as ss


FIXED_TIME = "2026-07-27T12:00:00Z"


def _payload(config=None, name="Hotel Core A"):
    return saved.build_payload(
        name,
        config or ss.make_default_config(),
        saved.make_view_state(),
        saved_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


def test_default_config_round_trips_without_sharing_mutable_state():
    config = ss.make_default_config()
    payload = _payload(config)

    loaded = saved.parse_payload(saved.payload_to_bytes(payload))

    assert loaded == payload
    assert loaded is not payload
    assert loaded["config"] is not payload["config"]
    loaded["config"]["section"]["pit_depth"] = 9999
    assert payload["config"]["section"]["pit_depth"] != 9999
    assert config["section"]["pit_depth"] != 9999


def test_mra_facing_multi_lift_config_round_trips():
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

    loaded = saved.parse_payload(saved.payload_to_bytes(_payload(config)))

    assert loaded["config"] == config
    assert saved.config_summary(config) == "MRA · 1 core · 4 lifts"


def test_blank_numeric_input_is_rejected_with_a_clear_error():
    config = ss.make_default_config()
    config["section"]["pit_depth"] = float("nan")

    with pytest.raises(saved.SavedConfigError, match="blank"):
        _payload(config, "Incomplete")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_standard_json_numbers_are_rejected(constant):
    raw = saved.payload_to_bytes(_payload()).decode("utf-8")
    raw = raw.replace('"schema_version": 1', f'"schema_version": {constant}')

    with pytest.raises(saved.SavedConfigError, match="invalid number"):
        saved.parse_payload(raw.encode("utf-8"))


def test_duplicate_json_keys_are_rejected():
    raw = saved.payload_to_bytes(_payload()).decode("utf-8")
    raw = raw.replace(
        '"format": "drawing-debbie-config"',
        '"format": "drawing-debbie-config", "format": "drawing-debbie-config"',
    )

    with pytest.raises(saved.SavedConfigError, match="repeats"):
        saved.parse_payload(raw.encode("utf-8"))


def test_unsupported_future_version_does_not_load():
    payload = _payload()
    payload["schema_version"] = saved.SCHEMA_VERSION + 1

    with pytest.raises(saved.SavedConfigError, match="newer version"):
        saved.parse_payload(json.dumps(payload).encode("utf-8"))


def test_invalid_structure_and_enums_are_rejected():
    payload = _payload()
    payload["config"]["machine_type"] = "hydraulic"
    with pytest.raises(saved.SavedConfigError, match="machine_type"):
        saved.validate_payload(payload)

    payload = _payload()
    payload["config"]["cores"][0]["bank1_lifts"][0]["unexpected"] = 1
    with pytest.raises(saved.SavedConfigError, match="unsupported fields"):
        saved.validate_payload(payload)


def test_names_are_unique_friendly_and_filename_safe():
    assert saved.normalize_name("  Dubai   Hotel – Core A  ") == "Dubai Hotel – Core A"
    assert (
        saved.filename_for_name("Dubai Hotel / Core A")
        == "dubai-hotel-core-a.debbie.json"
    )
    assert saved.filename_for_name("مشروع برج") == "sketch-configuration.debbie.json"
    assert saved.filename_for_name("CON") == "sketch-configuration.debbie.json"
    with pytest.raises(saved.SavedConfigError, match="Enter a name"):
        saved.normalize_name("   ")


def test_rename_changes_only_name_and_update_time(monkeypatch):
    payload = _payload(name="Original")
    monkeypatch.setattr(saved, "utc_now", lambda: "2026-07-28T08:30:00Z")

    renamed = saved.rename_payload(payload, "Renamed")

    assert renamed["metadata"] == {
        "name": "Renamed",
        "saved_at": FIXED_TIME,
        "updated_at": "2026-07-28T08:30:00Z",
    }
    assert renamed["config"] == payload["config"]
    assert renamed["view_state"] == payload["view_state"]
    assert payload["metadata"]["name"] == "Original"


def test_file_size_limit_is_enforced_before_parsing():
    with pytest.raises(saved.SavedConfigError, match="1 MB"):
        saved.parse_payload(b" " * (saved.MAX_FILE_BYTES + 1))
