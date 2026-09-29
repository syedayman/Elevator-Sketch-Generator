import debbie_operations as dops
import sketch_state as ss


def _config():
    config = ss.make_default_config()
    core = config["cores"][0]
    core["bank1_lifts"] = [
        ss.make_default_lift("passenger", "mrl"),
        ss.make_default_lift("fire", "mrl"),
    ]
    core["separator_types_bank1"] = ["rcc_wall"]
    return ss.renumber_lift_ids(config)


def test_default_section_has_blank_floor_labels():
    section = ss.make_default_section()
    assert section["passenger_top_floor_number"] is None
    assert section["passenger_lowest_floor_name"] == ""
    assert section["fire_top_floor_number"] is None
    assert section["fire_lowest_floor_name"] == ""


def test_section_floor_labels_picks_the_lift_types_pair():
    section = {
        **ss.make_default_section(),
        "passenger_top_floor_number": 25,
        "passenger_lowest_floor_name": "G",
        "fire_top_floor_number": 26,
        "fire_lowest_floor_name": "B2",
    }
    assert ss.section_floor_labels(section, "fire") == {
        "top_floor_number": 26,
        "lowest_floor_name": "B2",
    }
    # Older configs without the keys → generic labels.
    assert ss.section_floor_labels({}, "passenger") == {
        "top_floor_number": None,
        "lowest_floor_name": "",
    }


def test_set_floor_labels_without_lift_type_sets_both_types():
    config, results = dops.apply_operations(_config(), [
        {"op": "set_floor_labels", "top_floor_number": 25, "lowest_floor_name": " B2 "},
    ])
    assert results[0]["status"] == "applied"
    for lift_type in ("passenger", "fire"):
        assert config["section"][f"{lift_type}_top_floor_number"] == 25
        assert config["section"][f"{lift_type}_lowest_floor_name"] == "B2"


def test_set_floor_labels_for_one_type_leaves_the_rest_alone():
    base = _config()
    base["section"]["passenger_top_floor_number"] = 20
    config, _ = dops.apply_operations(base, [
        {"op": "set_floor_labels", "lift_type": "fire", "top_floor_number": 22.0},
    ])
    assert config["section"]["fire_top_floor_number"] == 22
    assert config["section"]["fire_lowest_floor_name"] == ""
    assert config["section"]["passenger_top_floor_number"] == 20


def test_set_floor_labels_clears_with_null_and_empty_text():
    base = _config()
    base["section"]["passenger_top_floor_number"] = 20
    base["section"]["passenger_lowest_floor_name"] = "B1"
    config, results = dops.apply_operations(base, [
        {"op": "set_floor_labels", "lift_type": "passenger",
         "top_floor_number": None, "lowest_floor_name": ""},
    ])
    assert results[0]["status"] == "applied"
    assert config["section"]["passenger_top_floor_number"] is None
    assert config["section"]["passenger_lowest_floor_name"] == ""


def test_set_floor_labels_rejects_bad_values_without_changing_config():
    base = _config()
    for op in (
        {"op": "set_floor_labels", "top_floor_number": 1},
        {"op": "set_floor_labels", "top_floor_number": 12.5},
        {"op": "set_floor_labels", "lowest_floor_name": "Lower Basement 3"},
        {"op": "set_floor_labels", "lift_type": "fire"},
        {"op": "set_floor_labels", "lift_type": "service", "top_floor_number": 5},
    ):
        config, results = dops.apply_operations(base, [op])
        assert results[0]["status"] == "rejected", op
        assert config is base
