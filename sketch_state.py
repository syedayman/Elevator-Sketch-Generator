"""
Sketch config model + pure reducers — 1:1 port of the KARR AI web app's
apps/web/lib/sketches/sketch-utils.ts (and the config shape of
apps/web/lib/schemas/sketch-config-schema.ts).

The whole sketch lives in ONE nested dict (the "config"):

    {
      "machine_type": "mrl" | "mra",
      "cores": [ { name, arrangement, bank1_lifts[], bank2_lifts[],
                   wall_thickness_mm, common_shaft, lobby_width_mm,
                   separator_types_bank1[], separator_types_bank2[] } ],
      ...global display options..., "section": {...}, ...section options...
    }

Every mutation goes through a pure reducer here (or the operation interpreter
in debbie_operations.py, which routes through these same reducers), so manual
form edits and Debbie's AI edits apply byte-identical linking math.

Blank cells (after "Clear All") use float('nan') as the sentinel — mirroring
the web app's NaN convention — so a cleared cell is distinguishable from a
legitimately-null optional field.
"""

import copy
import math
import re

import config

# =============================================================================
# Geometry constants — sourced from config.py so the form math matches the
# drawing engine exactly. Mirror of the constants in sketch-utils.ts.
# =============================================================================

CAR_WALL_THICKNESS = config.DEFAULT_CAR_WALL_THICKNESS            # 25
DOOR_GAP = config.DEFAULT_DOOR_GAP                                # 30
REAR_CLEARANCE = config.DEFAULT_REAR_CLEARANCE                    # 200
DEFAULT_DOOR_EXTENSION = config.DEFAULT_DOOR_EXTENSION            # 100
FIRE_DOOR_WIDTH = config.FIRE_LIFT_DOOR_WIDTH                     # 1200
FIRE_MIN_SHAFT_WIDTH = config.FIRE_LIFT_MIN_SHAFT_WIDTH           # 2700
FIRE_MIN_SHAFT_WIDTH_TELESCOPIC = config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC
TELESCOPIC_LEFT_EXT_EXTRA = config.TELESCOPIC_LEFT_EXTENSION_EXTRA   # 100
TELESCOPIC_RIGHT_EXT = config.TELESCOPIC_RIGHT_EXTENSION             # 200
# Bracket fields hold PURE bracket widths; rails are separate inputs.
# Zone width (what the sketch arrows show) = pure bracket + rail.
RAIL_WIDTH_DEFAULT = config.DEFAULT_RAIL_WIDTH                                        # 100
CW_BOX_WIDTH_DEFAULT = config.CW_BOX_WIDTH                                            # 450
CW_BOX_DEPTH_DEFAULT = config.CW_BOX_HEIGHT                                           # 1000
MRA_CW_BOX_WIDTH_DEFAULT = config.MRA_CW_BOX_WIDTH                                    # 1100
MRL_CW_BRACKET_MIN = config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH - RAIL_WIDTH_DEFAULT  # 525
MRL_CAR_BRACKET_MIN = config.DEFAULT_CAR_BRACKET_WIDTH - RAIL_WIDTH_DEFAULT           # 275
MRA_CAR_BRACKET_MIN = config.MRA_CAR_BRACKET_WIDTH - RAIL_WIDTH_DEFAULT               # 225
MRA_CW_BRACKET_DEPTH_MIN = config.MRA_CW_BRACKET_DEPTH
MRA_CW_GAP_MIN = config.MRA_CW_GAP
MRA_CW_WALL_GAP_MIN = config.MRA_CW_WALL_GAP
PANEL_THICKNESS_DEFAULT = config.DEFAULT_LIFT_DOOR_THICKNESS         # 150

DIMENSION_FONT_SCALE_MIN = 0.5
DIMENSION_FONT_SCALE_DEFAULT = 1.0
# Max dimension-font scale before labels collide, by lift count (per bank).
PLAN_DIM_FONT_MAX_INLINE = {1: 2.0, 2: 1.5, 3: 1.1, 4: 1.0}
PLAN_DIM_FONT_MAX_FACING = {1: 1.1, 2: 1.1, 3: 1.1, 4: 1.0}
SECTION_DIM_FONT_MAX = 1.6

MAX_CORES = 5
MAX_LIFTS_PER_BANK = 4


def plan_dimension_font_max(arrangement: str, bank1_count: int, bank2_count: int) -> float:
    """Port of planDimensionFontMax()."""
    count = max(bank1_count, bank2_count) if arrangement == "Facing" else bank1_count
    safe = min(4, max(1, int(count)))
    table = PLAN_DIM_FONT_MAX_FACING if arrangement == "Facing" else PLAN_DIM_FONT_MAX_INLINE
    return table.get(safe, DIMENSION_FONT_SCALE_DEFAULT)


def clamp_dimension_font_scale(value, max_scale: float) -> float:
    """Port of clampDimensionFontScale()."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return DIMENSION_FONT_SCALE_DEFAULT
    if not math.isfinite(n):
        return DIMENSION_FONT_SCALE_DEFAULT
    return min(max(n, DIMENSION_FONT_SCALE_MIN), max_scale)


# =============================================================================
# Blank-cell (NaN) helpers — mirror of the web's NaN sentinel convention
# =============================================================================

def is_blank(v) -> bool:
    """A cell blanked by Clear All (NaN). None means 'unset optional field'."""
    return isinstance(v, float) and math.isnan(v)


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def blank_numeric_fields(obj: dict, skip: tuple = ()) -> dict:
    """Port of blankNumericFields() — NaN every numeric value except `skip`."""
    out = dict(obj)
    for k, v in obj.items():
        if _is_number(v) and k not in skip:
            out[k] = float("nan")
    return out


def has_blank_number(obj: dict) -> bool:
    """Port of hasBlankNumber() — any numeric cell left blank (NaN)."""
    return any(is_blank(v) for v in obj.values())


# =============================================================================
# Default factories — port of makeDefaultLift / Section / Core / Config
# =============================================================================

def make_default_lift(lift_type: str = "passenger", machine_type: str = "mrl") -> dict:
    """Default per-lift form data. Port of makeDefaultLift() (no seed —
    space-planning seeding is project-mode-only and doesn't exist here)."""
    is_fire = lift_type == "fire"
    car_w = 1400 if is_fire else 1900
    car_d = 2400 if is_fire else 1600
    door_w = FIRE_DOOR_WIDTH if is_fire else 1100

    uc_w = car_w + 2 * CAR_WALL_THICKNESS
    uc_d = car_d + CAR_WALL_THICKNESS

    cw_bracket = car_bracket = None
    mra_left = mra_right = mra_cw_depth = mra_cw_gap = mra_cw_wall_gap = None

    # MRA fire lifts use MRL-style side brackets (CW left, car right)
    mra_rear_cw = machine_type == "mra" and not is_fire

    if mra_rear_cw:
        shaft_w = uc_w + 2 * (MRA_CAR_BRACKET_MIN + RAIL_WIDTH_DEFAULT)
        shaft_d = (2 * PANEL_THICKNESS_DEFAULT + DOOR_GAP + uc_d + MRA_CW_GAP_MIN
                   + MRA_CW_BRACKET_DEPTH_MIN + MRA_CW_WALL_GAP_MIN)
        mra_cw_depth = MRA_CW_BRACKET_DEPTH_MIN
        mra_cw_gap = MRA_CW_GAP_MIN
        mra_cw_wall_gap = MRA_CW_WALL_GAP_MIN
    else:
        shaft_w = (MRL_CW_BRACKET_MIN + RAIL_WIDTH_DEFAULT) + uc_w \
                  + (MRL_CAR_BRACKET_MIN + RAIL_WIDTH_DEFAULT)
        shaft_d = 2 * PANEL_THICKNESS_DEFAULT + DOOR_GAP + uc_d + REAR_CLEARANCE
        cw_bracket = MRL_CW_BRACKET_MIN
        car_bracket = MRL_CAR_BRACKET_MIN

    # Seed fire shafts at the DBC minimum width (default only — users can edit
    # freely below it; nothing validates or blocks)
    if is_fire:
        shaft_w = max(shaft_w, FIRE_MIN_SHAFT_WIDTH)

    # Redistribute extra width into the PURE brackets (rails stay at default)
    if mra_rear_cw:
        avail_w = shaft_w - uc_w - 2 * RAIL_WIDTH_DEFAULT
        extra = max(0, avail_w - 2 * MRA_CAR_BRACKET_MIN)
        mra_left = MRA_CAR_BRACKET_MIN + extra // 2
        mra_right = avail_w - mra_left
    else:
        avail_w = shaft_w - uc_w - 2 * RAIL_WIDTH_DEFAULT
        extra = max(0, avail_w - MRL_CW_BRACKET_MIN - MRL_CAR_BRACKET_MIN)
        cw_bracket = MRL_CW_BRACKET_MIN + extra // 2
        car_bracket = avail_w - cw_bracket

    # Fire lifts default to telescopic door opening (panel length unused there;
    # switching to centre recomputes it — see apply_door_type)
    if is_fire:
        door_type = "telescopic"
        tele_left = int(0.5 * door_w) + TELESCOPIC_LEFT_EXT_EXTRA
        tele_right = TELESCOPIC_RIGHT_EXT
        panel_len = None
    else:
        door_type = "centre"
        tele_left = tele_right = None
        panel_len = min(2 * door_w + 2 * DEFAULT_DOOR_EXTENSION, shaft_w)

    return {
        "type": lift_type,
        "lift_id": "",
        "capacity": 1600 if is_fire else 1350,
        "width": car_w,
        "depth": car_d,
        "cabin_height": 2400,
        "shaft_width": shaft_w,
        "shaft_depth": shaft_d,
        "door_width": door_w,
        "door_height": 2100,
        "door_panel_length": panel_len,
        "door_panel_thickness": PANEL_THICKNESS_DEFAULT,
        "structural_opening_width": 1300,
        "structural_opening_height": 2200,
        "door_opening_type": door_type,
        "telescopic_left_ext": tele_left,
        "telescopic_right_ext": tele_right,
        "cw_bracket_width": cw_bracket,
        "car_bracket_width": car_bracket,
        "rail_width_left": RAIL_WIDTH_DEFAULT,
        "rail_width_right": RAIL_WIDTH_DEFAULT,
        "door_gap": DOOR_GAP,
        "cw_box_width": CW_BOX_WIDTH_DEFAULT,
        "cw_box_depth": CW_BOX_DEPTH_DEFAULT,
        "mra_cw_box_width": MRA_CW_BOX_WIDTH_DEFAULT,
        "mra_left_bracket": mra_left,
        "mra_right_bracket": mra_right,
        "mra_cw_bracket_depth": mra_cw_depth,
        "mra_cw_gap": mra_cw_gap,
        "mra_cw_wall_gap": mra_cw_wall_gap,
        "double_entrance": False,
        "swap_brackets": False,
        "door_offset_mm": 0,
        "door_offset_direction": "right",
        # Per-lift section properties: None unless set (e.g. by Debbie); the
        # section form falls back to its own values on copy.
        "pit_depth": None,
        "overhead_clearance": None,
    }


def make_default_section() -> dict:
    """Port of makeDefaultSection(). Keys match the web sectionFormDataSchema
    (`shaft_depth` is the horizontal dimension shown in the section view)."""
    return {
        "shaft_depth": 2950,
        "wall_thickness": 200,
        "pit_slab": 200,
        "pit_depth": 1200,
        "travel_height": 30000,
        "overhead_clearance": 4200,
        "door_height": 2100,
        "structural_opening_height": 2200,
        "machine_room_height": 3000,
    }


def make_default_core(machine_type: str = "mrl", name: str = "Core 1") -> dict:
    """One default core (single passenger lift). Port of makeDefaultCore()."""
    return {
        "name": name,
        "arrangement": "Inline",
        "bank1_lifts": [make_default_lift("passenger", machine_type)],
        "bank2_lifts": [],
        "wall_thickness_mm": 200,
        "common_shaft": False,
        "lobby_width_mm": 4000,
        "separator_types_bank1": [],
        "separator_types_bank2": [],
    }


def make_default_config() -> dict:
    """Port of makeDefaultConfig() — the default lift opens as PL-01."""
    return fill_blank_lift_ids({
        "machine_type": "mrl",
        "cores": [make_default_core("mrl", "Core 1")],
        "show_dimensions": True,
        "show_hatching": True,
        "show_centerlines": False,
        "show_capacity": False,
        "show_accessibility": False,
        "show_brackets": True,
        "show_lift_doors": True,
        "show_lift_id": False,
        "show_brief_spec": True,
        "split_lift_types": False,
        "dimension_font_scale": 1.0,
        "section": make_default_section(),
        "section_show_dimensions": True,
        "section_show_hatching": True,
        "section_show_break_lines": True,
        "section_show_machine": True,
        "section_dimension_font_scale": 1.0,
    })


def deep_copy_config(cfg: dict) -> dict:
    """Snapshot for the undo/redo history."""
    return copy.deepcopy(cfg)


# =============================================================================
# Lift ID (designation) helpers — port of the sketch-utils ID section
# =============================================================================

def default_lift_id_prefix(lift_type: str) -> str:
    """Passenger → "PL"; fire/service → "FL/SL"."""
    return "FL/SL" if lift_type == "fire" else "PL"


def _format_lift_id(prefix: str, n: int) -> str:
    return f"{prefix}-{n:02d}"


_ID_RE = re.compile(r"^(.*)-(\d+)$")


def _map_lifts_in_order(cfg: dict, fn) -> dict:
    """Apply fn to every lift in render order (cores → bank1 → bank2). Returns
    a new config; never mutates the input."""
    out = dict(cfg)
    out["cores"] = [
        {
            **core,
            "bank1_lifts": [fn(lift) for lift in core["bank1_lifts"]],
            "bank2_lifts": [fn(lift) for lift in core["bank2_lifts"]],
        }
        for core in cfg["cores"]
    ]
    return out


def fill_blank_lift_ids(cfg: dict) -> dict:
    """Assign IDs only to lifts whose lift_id is blank, numbering continuously
    across cores per prefix, continuing past the highest existing number."""
    counters: dict = {}
    for core in cfg["cores"]:
        for lift in [*core["bank1_lifts"], *core["bank2_lifts"]]:
            m = _ID_RE.match((lift.get("lift_id") or "").strip())
            if not m:
                continue
            prefix, num = m.group(1), int(m.group(2))
            counters[prefix] = max(counters.get(prefix, 0), num)

    def fn(lift: dict) -> dict:
        if (lift.get("lift_id") or "").strip() != "":
            return lift
        prefix = default_lift_id_prefix(lift["type"])
        nxt = counters.get(prefix, 0) + 1
        counters[prefix] = nxt
        return {**lift, "lift_id": _format_lift_id(prefix, nxt)}

    return _map_lifts_in_order(cfg, fn)


def renumber_lift_ids(cfg: dict) -> dict:
    """Reassign EVERY lift ID from scratch (continuous per prefix across cores)."""
    counters: dict = {}

    def fn(lift: dict) -> dict:
        prefix = default_lift_id_prefix(lift["type"])
        nxt = counters.get(prefix, 0) + 1
        counters[prefix] = nxt
        return {**lift, "lift_id": _format_lift_id(prefix, nxt)}

    return _map_lifts_in_order(cfg, fn)


def carry_lift_id(lift: dict, new_type: str) -> str:
    """Carry an ID across a type change, swapping the PL ⇄ FL/SL prefix when it
    was the canonical default for the old type; otherwise keep the user's ID."""
    old_prefix = default_lift_id_prefix(lift["type"])
    new_prefix = default_lift_id_prefix(new_type)
    m = re.match(rf"^{re.escape(old_prefix)}-(\d+)$", (lift.get("lift_id") or "").strip())
    return f"{new_prefix}-{m.group(1)}" if m else lift.get("lift_id", "")


# =============================================================================
# Validation helpers
# =============================================================================

def compute_default_separator_types(lifts: list, common_shaft: bool) -> list:
    """Port of computeDefaultSeparatorTypes()."""
    types = []
    for i in range(len(lifts) - 1):
        if not common_shaft:
            types.append("rcc_wall")
        elif lifts[i]["type"] == "fire" or lifts[i + 1]["type"] == "fire":
            types.append("rcc_wall")
        else:
            types.append("steel_beam")
    return types


def copy_lift_values_to_section(section: dict, lift: dict, wall_thickness_mm) -> dict:
    """Port of copyLiftValuesToSection() — pure; returns a new section dict."""
    out = dict(section)
    out["shaft_depth"] = lift["shaft_depth"]
    out["door_height"] = lift["door_height"]
    out["structural_opening_height"] = lift["structural_opening_height"]
    out["wall_thickness"] = wall_thickness_mm
    # Per-lift pit/overhead when the lift carries them; else keep the section's.
    if lift.get("pit_depth") is not None:
        out["pit_depth"] = lift["pit_depth"]
    if lift.get("overhead_clearance") is not None:
        out["overhead_clearance"] = lift["overhead_clearance"]
    return out


def lift_rails(lift: dict) -> tuple:
    rl = lift.get("rail_width_left")
    rr = lift.get("rail_width_right")
    return (rl if rl is not None else RAIL_WIDTH_DEFAULT,
            rr if rr is not None else RAIL_WIDTH_DEFAULT)


def lift_door_gap(lift: dict):
    g = lift.get("door_gap")
    return g if g is not None else DOOR_GAP


def compute_min_shaft_width(lift: dict, machine_type: str) -> int:
    """Port of computeMinShaftWidth(). Zone = pure bracket + rail."""
    uc_w = lift["width"] + 2 * CAR_WALL_THICKNESS
    rail_l, rail_r = lift_rails(lift)
    if machine_type == "mra" and not lift.get("double_entrance") and lift["type"] != "fire":
        min_w = (MRA_CAR_BRACKET_MIN + rail_l) + uc_w + (MRA_CAR_BRACKET_MIN + rail_r)
    else:
        min_w = (MRL_CW_BRACKET_MIN + rail_l) + uc_w + (MRL_CAR_BRACKET_MIN + rail_r)
    if lift["type"] == "fire":
        fire_min = (FIRE_MIN_SHAFT_WIDTH_TELESCOPIC
                    if lift.get("door_opening_type") == "telescopic"
                    else FIRE_MIN_SHAFT_WIDTH)
        min_w = max(min_w, fire_min)
    return int(min_w)


def compute_min_shaft_depth(lift: dict, machine_type: str) -> int:
    """Port of computeMinShaftDepth()."""
    uc_d = lift["depth"] + CAR_WALL_THICKNESS
    thickness = lift.get("door_panel_thickness")
    thickness = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
    door_zone = 2 * thickness + lift_door_gap(lift)
    if lift.get("double_entrance"):
        return int(door_zone + lift["depth"] + door_zone)
    if machine_type == "mra" and lift["type"] != "fire":
        return int(door_zone + uc_d + MRA_CW_GAP_MIN + MRA_CW_BRACKET_DEPTH_MIN
                   + MRA_CW_WALL_GAP_MIN)
    return int(uc_d + door_zone + REAR_CLEARANCE)


# ── Field bounds (mirror of liftFormDataSchema / sectionFormDataSchema) ──
# (min, max, nullable). Positive-only fields use (0-exclusive) via min=1e-9.

LIFT_FIELD_BOUNDS = {
    "capacity": (100, 10000, True),
    "width": (1e-9, None, False),
    "depth": (1e-9, None, False),
    "cabin_height": (1e-9, None, False),
    "shaft_width": (1e-9, None, False),
    "shaft_depth": (1e-9, None, False),
    "door_width": (700, 2000, False),
    "door_height": (1500, 3500, False),
    "door_panel_length": (500, 6000, True),
    "door_panel_thickness": (50, 300, False),
    "structural_opening_width": (800, 3000, False),
    "structural_opening_height": (1500, 4000, False),
    "door_offset_mm": (0, None, False),
}

SECTION_FIELD_BOUNDS = {
    "shaft_depth": (1e-9, None, False),
    "wall_thickness": (100, 500, False),
    "pit_slab": (100, 500, False),
    "pit_depth": (500, 10000, False),
    "travel_height": (5000, 200000, False),
    "overhead_clearance": (2000, 10000, False),
    "door_height": (1500, 3500, False),
    "structural_opening_height": (1500, 4000, False),
    "machine_room_height": (2000, 6000, True),
}

LOBBY_WIDTH_BOUNDS = (2000, 10000)


def _check_bounds(value, lo, hi, nullable: bool):
    """None → error message string, or OK (None-as-no-error)."""
    if value is None:
        return None if nullable else "value is required"
    if not _is_number(value) or (isinstance(value, float) and not math.isfinite(value)):
        return "value must be a number"
    if lo is not None and value < lo:
        return f"must be at least {lo:g}" if lo > 1e-9 else "must be positive"
    if hi is not None and value > hi:
        return f"must be at most {hi:g}"
    return None


def lift_error(lift: dict):
    """Validate a lift against the schema bounds. Returns an error message or
    None (port of liftError / liftFormDataSchema.safeParse)."""
    for field, (lo, hi, nullable) in LIFT_FIELD_BOUNDS.items():
        err = _check_bounds(lift.get(field), lo, hi, nullable)
        if err:
            return f"{field}: {err}"
    return None


def section_error(section: dict):
    """Validate the section dict; error message or None."""
    for field, (lo, hi, nullable) in SECTION_FIELD_BOUNDS.items():
        err = _check_bounds(section.get(field), lo, hi, nullable)
        if err:
            return f"{field}: {err}"
    return None


# =============================================================================
# Constraint-linking reducers — 1:1 port of the sketch-utils.ts reducers.
# Each is a pure (lift, value, …) → new lift dict. Inputs are never mutated.
# =============================================================================

def _floor_half(x):
    return math.floor(x / 2)


def lift_is_side_cw(lift: dict, machine_type: str) -> bool:
    """MRL-style side brackets (CW left, car right): MRL, or fire /
    double-entrance lifts (which use side brackets even under MRA)."""
    return machine_type == "mrl" or bool(lift.get("double_entrance")) or lift["type"] == "fire"


def _available_width(lift: dict):
    """Spare width for the two brackets = shaft − unfinished car − rails."""
    uc_w = lift["width"] + 2 * CAR_WALL_THICKNESS
    rail_l, rail_r = lift_rails(lift)
    return lift["shaft_width"] - uc_w - rail_l - rail_r


def _available_depth(lift: dict):
    """Spare depth for the rear CWT (MRA passenger only)."""
    uc_d = lift["depth"] + CAR_WALL_THICKNESS
    thickness = lift.get("door_panel_thickness")
    thickness = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
    fixed = 2 * thickness + lift_door_gap(lift) + uc_d
    wall_gap = lift.get("mra_cw_wall_gap")
    wall_gap = wall_gap if wall_gap is not None else MRA_CW_WALL_GAP_MIN
    return lift["shaft_depth"] - fixed - wall_gap


def apply_rail_left(lift: dict, mm, machine_type: str) -> dict:
    """Guide rail: the same-side bracket absorbs the change."""
    clamped = max(0, mm)
    rail_l, _ = lift_rails(lift)
    delta = clamped - rail_l
    if lift_is_side_cw(lift, machine_type):
        cw = lift.get("cw_bracket_width")
        cw = cw if cw is not None else MRL_CW_BRACKET_MIN
        return {**lift, "rail_width_left": clamped, "cw_bracket_width": cw - delta}
    left = lift.get("mra_left_bracket")
    left = left if left is not None else MRA_CAR_BRACKET_MIN
    return {**lift, "rail_width_left": clamped, "mra_left_bracket": left - delta}


def apply_rail_right(lift: dict, mm, machine_type: str) -> dict:
    clamped = max(0, mm)
    _, rail_r = lift_rails(lift)
    delta = clamped - rail_r
    if lift_is_side_cw(lift, machine_type):
        car = lift.get("car_bracket_width")
        car = car if car is not None else MRL_CAR_BRACKET_MIN
        return {**lift, "rail_width_right": clamped, "car_bracket_width": car - delta}
    right = lift.get("mra_right_bracket")
    right = right if right is not None else MRA_CAR_BRACKET_MIN
    return {**lift, "rail_width_right": clamped, "mra_right_bracket": right - delta}


def apply_door_gap(lift: dict, mm) -> dict:
    """Running clearance; double-entrance lifts re-derive shaft depth from it."""
    clamped = max(0, mm)
    if lift.get("double_entrance"):
        thickness = lift.get("door_panel_thickness")
        thickness = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
        door_zone = 2 * thickness + clamped
        return {**lift, "door_gap": clamped, "shaft_depth": door_zone + lift["depth"] + door_zone}
    return {**lift, "door_gap": clamped}


def apply_cw_bracket(lift: dict, mm) -> dict:
    """MRL side brackets: editing one auto-adjusts the other (shaft stays put)."""
    clamped = max(0, mm)
    avail = _available_width(lift)
    return {**lift, "cw_bracket_width": clamped, "car_bracket_width": avail - clamped}


def apply_car_bracket(lift: dict, mm) -> dict:
    clamped = max(0, mm)
    avail = _available_width(lift)
    return {**lift, "car_bracket_width": clamped, "cw_bracket_width": avail - clamped}


def apply_mra_left_bracket(lift: dict, mm) -> dict:
    clamped = max(0, mm)
    avail = _available_width(lift)
    return {**lift, "mra_left_bracket": clamped, "mra_right_bracket": avail - clamped}


def apply_mra_right_bracket(lift: dict, mm) -> dict:
    clamped = max(0, mm)
    avail = _available_width(lift)
    return {**lift, "mra_right_bracket": clamped, "mra_left_bracket": avail - clamped}


def apply_mra_cw_depth(lift: dict, mm) -> dict:
    """MRA depth: CWT bracket depth and gap trade off within the spare depth."""
    clamped = max(0, mm)
    avail_d = _available_depth(lift)
    return {**lift, "mra_cw_bracket_depth": clamped, "mra_cw_gap": avail_d - clamped}


def apply_mra_cw_gap(lift: dict, mm) -> dict:
    clamped = max(0, mm)
    avail_d = _available_depth(lift)
    return {**lift, "mra_cw_gap": clamped, "mra_cw_bracket_depth": avail_d - clamped}


def apply_mra_cw_wall_gap(lift: dict, mm) -> dict:
    clamped = max(0, mm)
    uc_d = lift["depth"] + CAR_WALL_THICKNESS
    thickness = lift.get("door_panel_thickness")
    thickness = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
    fixed = 2 * thickness + lift_door_gap(lift) + uc_d
    new_avail_d = lift["shaft_depth"] - fixed - clamped
    cw_d = lift.get("mra_cw_bracket_depth")
    cw_d = cw_d if cw_d is not None else MRA_CW_BRACKET_DEPTH_MIN
    return {**lift, "mra_cw_wall_gap": clamped, "mra_cw_gap": max(0, new_avail_d - cw_d)}


def apply_shaft_width(lift: dict, new_sw, machine_type: str) -> dict:
    """Shaft width change: redistribute the delta evenly across both brackets."""
    uc_w = lift["width"] + 2 * CAR_WALL_THICKNESS
    rail_l, rail_r = lift_rails(lift)
    old_avail = _available_width(lift)
    new_avail = new_sw - uc_w - rail_l - rail_r
    half = _floor_half(new_avail - old_avail)
    if lift_is_side_cw(lift, machine_type):
        old_cw = lift.get("cw_bracket_width")
        old_cw = old_cw if old_cw is not None else MRL_CW_BRACKET_MIN
        new_cw = old_cw + half
        return {
            **lift,
            "shaft_width": new_sw,
            "cw_bracket_width": max(0, new_cw),
            "car_bracket_width": max(0, new_avail - new_cw),
        }
    old_left = lift.get("mra_left_bracket")
    old_left = old_left if old_left is not None else MRA_CAR_BRACKET_MIN
    new_left = old_left + half
    return {
        **lift,
        "shaft_width": new_sw,
        "mra_left_bracket": max(0, new_left),
        "mra_right_bracket": max(0, new_avail - new_left),
    }


def apply_shaft_depth(lift: dict, new_sd, machine_type: str) -> dict:
    """Shaft depth change: redistribute into the rear CWT (MRA passenger only)."""
    if machine_type == "mra" and not lift.get("double_entrance") and lift["type"] != "fire":
        uc_d = lift["depth"] + CAR_WALL_THICKNESS
        thickness = lift.get("door_panel_thickness")
        thickness = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
        fixed = 2 * thickness + lift_door_gap(lift) + uc_d
        wall_gap = lift.get("mra_cw_wall_gap")
        wall_gap = wall_gap if wall_gap is not None else MRA_CW_WALL_GAP_MIN
        old_avail_d = lift["shaft_depth"] - fixed - wall_gap
        new_avail_d = new_sd - fixed - wall_gap
        old_cw_d = lift.get("mra_cw_bracket_depth")
        old_cw_d = old_cw_d if old_cw_d is not None else MRA_CW_BRACKET_DEPTH_MIN
        new_cw_d = old_cw_d + _floor_half(new_avail_d - old_avail_d)
        return {
            **lift,
            "shaft_depth": new_sd,
            "mra_cw_bracket_depth": max(0, new_cw_d),
            "mra_cw_gap": max(0, new_avail_d - new_cw_d),
        }
    return {**lift, "shaft_depth": new_sd}


def apply_car_width(lift: dict, mm, machine_type: str) -> dict:
    """Passenger car width: split the freed/consumed width evenly across
    brackets. NOTE: intentionally does NOT subtract rails (matches the form's
    historical behavior for the passenger car-width input)."""
    new_uc_w = mm + 2 * CAR_WALL_THICKNESS
    new_avail = lift["shaft_width"] - new_uc_w
    half = _floor_half(new_avail)
    if machine_type == "mrl":
        return {
            **lift,
            "width": mm,
            "cw_bracket_width": max(0, half),
            "car_bracket_width": max(0, new_avail - half),
        }
    return {
        **lift,
        "width": mm,
        "mra_left_bracket": max(0, half),
        "mra_right_bracket": max(0, new_avail - half),
    }


def apply_fire_cabin(lift: dict, w, d, machine_type: str) -> dict:
    """Fire cabin "W x D": reseed brackets at their minimums + split the spare;
    double-entrance fire lifts re-derive shaft depth."""
    uc_w_new = w + 2 * CAR_WALL_THICKNESS
    rail_l, rail_r = lift_rails(lift)
    new_avail = lift["shaft_width"] - uc_w_new - rail_l - rail_r
    updates = {"width": w, "depth": d}
    if lift_is_side_cw(lift, machine_type):
        extra = max(0, new_avail - MRL_CW_BRACKET_MIN - MRL_CAR_BRACKET_MIN)
        cw = MRL_CW_BRACKET_MIN + _floor_half(extra)
        updates["cw_bracket_width"] = cw
        updates["car_bracket_width"] = new_avail - cw
    else:
        extra = max(0, new_avail - 2 * MRA_CAR_BRACKET_MIN)
        left = MRA_CAR_BRACKET_MIN + _floor_half(extra)
        updates["mra_left_bracket"] = left
        updates["mra_right_bracket"] = new_avail - left
    if lift.get("double_entrance"):
        thickness = lift.get("door_panel_thickness")
        thickness = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
        door_zone = 2 * thickness + lift_door_gap(lift)
        updates["shaft_depth"] = door_zone + d + door_zone
    return {**lift, **updates}


def apply_door_width(lift: dict, mm) -> dict:
    """Door width: centre-opening panels track the width; a still-default
    telescopic left extension re-derives from the new width."""
    updates = {"door_width": mm}
    if lift.get("door_opening_type") != "telescopic":
        prev = lift["door_width"]
        current_panel = lift.get("door_panel_length")
        if current_panel is None:
            current_panel = min(2 * prev + 2 * DEFAULT_DOOR_EXTENSION, lift["shaft_width"])
        updates["door_panel_length"] = current_panel + 2 * (mm - prev)
    if lift.get("door_opening_type") == "telescopic" and lift.get("telescopic_left_ext") is not None:
        old_default = math.floor(0.5 * lift["door_width"]) + TELESCOPIC_LEFT_EXT_EXTRA
        if lift["telescopic_left_ext"] == old_default:
            updates["telescopic_left_ext"] = math.floor(0.5 * mm) + TELESCOPIC_LEFT_EXT_EXTRA
    return {**lift, **updates}


def apply_door_type(lift: dict, door_type: str) -> dict:
    """Door opening type: seed/clear telescopic extensions and the centre panel."""
    if door_type == "telescopic":
        return {
            **lift,
            "door_opening_type": "telescopic",
            "telescopic_left_ext": math.floor(0.5 * lift["door_width"]) + TELESCOPIC_LEFT_EXT_EXTRA,
            "telescopic_right_ext": TELESCOPIC_RIGHT_EXT,
            "door_panel_length": None,
        }
    return {
        **lift,
        "door_opening_type": "centre",
        "telescopic_left_ext": None,
        "telescopic_right_ext": None,
        "door_panel_length": min(2 * lift["door_width"] + 2 * DEFAULT_DOOR_EXTENSION,
                                 lift["shaft_width"]),
    }


def apply_double_entrance(lift: dict, on: bool, machine_type: str) -> dict:
    """Double car entrance (any lift type): doors on both the front and rear
    faces. A through-car has no rear wall, so the counterweight must sit on the
    SIDE (MRL-style) — which means an MRA passenger lift's rear counterweight
    moves to the side when this turns on, making it geometrically identical to
    an MRL double-entrance lift. Only that MRA-passenger case changes the
    bracket model; for MRL (any type) and MRA fire the layout is already
    side-CW, so only the shaft depth re-derives."""
    door_gap = lift_door_gap(lift)
    thickness = lift.get("door_panel_thickness")
    panel = thickness if thickness is not None else PANEL_THICKNESS_DEFAULT
    side_cw_now = lift_is_side_cw(lift, machine_type)
    side_cw_next = machine_type == "mrl" or lift["type"] == "fire" or on

    if side_cw_now == side_cw_next:
        # Bracket model unchanged — only depth re-derives (original behavior).
        if on:
            door_zone = 2 * panel + door_gap
            return {**lift, "double_entrance": True,
                    "shaft_depth": door_zone + lift["depth"] + door_zone}
        uc_d = lift["depth"] + CAR_WALL_THICKNESS
        return {**lift, "double_entrance": False,
                "shaft_depth": 2 * PANEL_THICKNESS_DEFAULT + door_gap + uc_d + REAR_CLEARANCE}

    # Bracket model changes — reached only by an MRA passenger lift.
    rail_l, rail_r = lift_rails(lift)
    uc_w = lift["width"] + 2 * CAR_WALL_THICKNESS

    if on:
        # Rear CW → side CW: rebuild the width layout the MRL way (identical to
        # an MRL double-entrance lift with the same car + rails), drop the
        # rear-CW fields, and re-derive the through-car depth.
        shaft_w = MRL_CW_BRACKET_MIN + rail_l + uc_w + MRL_CAR_BRACKET_MIN + rail_r
        avail = shaft_w - uc_w - rail_l - rail_r
        door_zone = 2 * panel + door_gap
        return {
            **lift,
            "double_entrance": True,
            "shaft_width": shaft_w,
            "cw_bracket_width": MRL_CW_BRACKET_MIN,
            "car_bracket_width": avail - MRL_CW_BRACKET_MIN,
            "mra_left_bracket": None,
            "mra_right_bracket": None,
            "mra_cw_bracket_depth": None,
            "mra_cw_gap": None,
            "mra_cw_wall_gap": None,
            "shaft_depth": door_zone + lift["depth"] + door_zone,
        }

    # Side CW → rear CW: restore the MRA rear-counterweight layout (fresh, like
    # make_default_lift), drop the side-CW bracket fields.
    uc_d = lift["depth"] + CAR_WALL_THICKNESS
    shaft_w = uc_w + (MRA_CAR_BRACKET_MIN + rail_l) + (MRA_CAR_BRACKET_MIN + rail_r)
    avail = shaft_w - uc_w - rail_l - rail_r
    return {
        **lift,
        "double_entrance": False,
        "shaft_width": shaft_w,
        "cw_bracket_width": None,
        "car_bracket_width": None,
        "mra_left_bracket": MRA_CAR_BRACKET_MIN,
        "mra_right_bracket": avail - MRA_CAR_BRACKET_MIN,
        "mra_cw_bracket_depth": MRA_CW_BRACKET_DEPTH_MIN,
        "mra_cw_gap": MRA_CW_GAP_MIN,
        "mra_cw_wall_gap": MRA_CW_WALL_GAP_MIN,
        "shaft_depth": (2 * panel + door_gap + uc_d + MRA_CW_GAP_MIN
                        + MRA_CW_BRACKET_DEPTH_MIN + MRA_CW_WALL_GAP_MIN),
    }


def apply_door_panel_thickness(lift: dict, mm) -> dict:
    """Door panel thickness: double-entrance lifts re-derive shaft depth using
    the lift's actual running clearance."""
    if lift.get("double_entrance"):
        door_zone = 2 * mm + lift_door_gap(lift)
        return {**lift, "door_panel_thickness": mm,
                "shaft_depth": door_zone + lift["depth"] + door_zone}
    return {**lift, "door_panel_thickness": mm}
