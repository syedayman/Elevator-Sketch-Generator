import pytest

import debbie_operations as dops
import sketch_state as ss
from section_sketch import LiftSectionSketch, SectionConfig, parse_floors, served_floors
from shaft_sketch import LiftConfig


def _config():
    config = ss.make_default_config()
    core = config["cores"][0]
    core["bank1_lifts"] = [
        ss.make_default_lift("passenger", "mrl"),
        ss.make_default_lift("fire", "mrl"),
    ]
    core["separator_types_bank1"] = ["rcc_wall"]
    return ss.renumber_lift_ids(config)


@pytest.mark.parametrize(
    ("text", "floors"),
    [
        ("g,b1,b2,1-5", ["B2", "B1", "G", "1", "2", "3", "4", "5"]),
        ("1, 2, 3", ["1", "2", "3"]),
        ("B2, B1, G, P1-P3, 1-2, Roof",
         ["B2", "B1", "G", "P1", "P2", "P3", "1", "2", "Roof"]),
        ("b1-3, gf, m, 1-2, r", ["B3", "B2", "B1", "G", "M", "1", "2", "Roof"]),
        ("Basement 2, Ground Floor, Level 1, Level R", ["B2", "G", "1", "Roof"]),
        ("LG, UG, 1-2, 2", ["LG", "UG", "1", "2"]),
        ("", []),
    ],
)
def test_parse_floors_orders_codes_and_ranges_bottom_to_top(text, floors):
    assert parse_floors(text) == (floors, [])


def test_parse_floors_reports_what_it_cannot_read():
    assert parse_floors("1, x, 5-a, 1-100000, 3") == (
        ["1", "3"], ["x", "5-a", "1-100000"])


def test_served_floors_defaults_and_order():
    floors = ["B1", "G", "1", "2", "3"]
    assert served_floors(floors, "", "") == floors
    assert served_floors(floors, "G", "2") == ["G", "1", "2"]
    # A choice no longer in the list falls back to lowest / highest.
    assert served_floors(floors, "B3", "9") == floors
    assert served_floors([], "G", "2") == []


def _sketch(**floors):
    return LiftSectionSketch(
        lift_config=LiftConfig(shaft_depth_override=2300),
        section_config=SectionConfig(travel_height=21000, **floors),
    )


def test_landings_and_average_come_from_the_served_floors():
    sketch = _sketch(floors="g,b1,b2,1-7", bottom_floor="G", top_floor="7")
    assert sketch._landing_labels() == (
        "Floor G F.F.L.", "Floor 1 F.F.L.", "Floor 6 F.F.L.", "Floor 7 F.F.L.")
    # G to 7 = 8 floors: travel / 7.
    assert sketch._average_floor_height() == 21000 / 7


def test_roof_label_and_default_bottom_and_top():
    sketch = _sketch(floors="B2, B1, G, 1-25, Roof")
    assert sketch._landing_labels() == (
        "Floor B2 F.F.L.", "Floor B1 F.F.L.", "Floor 25 F.F.L.", "Roof F.F.L.")
    assert sketch._average_floor_height() == 21000 / 28


def test_calculated_floor_height():
    from section_sketch import calculated_floor_height

    assert calculated_floor_height(21000, ["G", "1", "2", "3", "4", "5", "6", "7"]) == 3000
    assert calculated_floor_height(21000, ["G"]) is None
    assert calculated_floor_height(21000, []) is None


def test_no_floors_keeps_the_generic_labels():
    sketch = _sketch()
    assert sketch._landing_labels() == (
        "Bottom-most\nLanding FFL", "Floor 1 F.F.L.", "Floor n-1 F.F.L.",
        "Top Floor F.F.L.")
    assert sketch._average_floor_height() is None
    assert _sketch(average_floor_height=3600)._average_floor_height() == 3600


def test_default_section_has_blank_floor_labels():
    section = ss.make_default_section()
    assert section["floors"] == ""
    for lift_type in ("passenger", "fire"):
        assert section[f"{lift_type}_bottom_floor"] == ""
        assert section[f"{lift_type}_top_floor"] == ""
        assert section[f"{lift_type}_average_floor_height"] is None


def test_section_floor_labels_picks_the_lift_types_choices():
    section = {
        **ss.make_default_section(),
        "floors": "B2, B1, G, 1-26",
        "passenger_bottom_floor": "G",
        "fire_bottom_floor": "B2",
        "fire_top_floor": "26",
        "fire_average_floor_height": 3500,
    }
    assert ss.section_floor_labels(section, "fire") == {
        "floors": "B2, B1, G, 1-26",
        "bottom_floor": "B2",
        "top_floor": "26",
        "average_floor_height": 3500,
    }
    # Missing keys → generic labels, auto average.
    assert ss.section_floor_labels({}, "passenger") == {
        "floors": "", "bottom_floor": "", "top_floor": "", "average_floor_height": None,
    }


def test_format_floors_collapses_numbered_runs():
    assert ss.format_floors(["B2", "B1", "G", "1", "2", "3", "5", "6", "Roof"]) == (
        "B2, B1, G, 1–3, 5, 6, Roof")


def test_set_floor_labels_sets_floors_and_one_types_bottom_and_top():
    config, results = dops.apply_operations(_config(), [
        {"op": "set_floor_labels", "floors": "b2, b1, g, 1-26"},
        {"op": "set_floor_labels", "lift_type": "fire", "bottom_floor": "b2",
         "top_floor": "26", "average_floor_height": 3450},
    ])
    assert [r["status"] for r in results] == ["applied", "applied"]
    section = config["section"]
    assert section["floors"] == "b2, b1, g, 1-26"
    assert (section["fire_bottom_floor"], section["fire_top_floor"]) == ("B2", "26")
    assert section["fire_average_floor_height"] == 3450
    assert (section["passenger_bottom_floor"], section["passenger_top_floor"]) == ("", "")


def test_set_floor_labels_without_lift_type_sets_both_and_resets():
    base = _config()
    base["section"]["floors"] = "G, 1-10"
    config, _ = dops.apply_operations(base, [
        {"op": "set_floor_labels", "bottom_floor": "G", "top_floor": "9"},
    ])
    for lift_type in ("passenger", "fire"):
        assert config["section"][f"{lift_type}_top_floor"] == "9"
    config, results = dops.apply_operations(config, [
        {"op": "set_floor_labels", "top_floor": "", "average_floor_height": None},
    ])
    assert results[0]["status"] == "applied"
    assert config["section"]["passenger_top_floor"] == ""


def test_set_floor_labels_rejects_bad_values_without_changing_config():
    base = _config()
    base["section"]["floors"] = "G, 1-10"
    for op in (
        {"op": "set_floor_labels", "floors": "G, 1-10, nonsense"},
        {"op": "set_floor_labels", "top_floor": "25"},
        {"op": "set_floor_labels", "bottom_floor": "5", "top_floor": "2"},
        {"op": "set_floor_labels", "average_floor_height": 0},
        {"op": "set_floor_labels", "lift_type": "fire"},
        {"op": "set_floor_labels", "lift_type": "service", "top_floor": "5"},
    ):
        config, results = dops.apply_operations(base, [op])
        assert results[0]["status"] == "rejected", op
        assert config is base
