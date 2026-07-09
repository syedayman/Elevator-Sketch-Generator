"""
Debbie operation interpreter — 1:1 port of the KARR AI web app's
apps/web/lib/sketches/apply-operations.ts (standalone mode: no space-planning
locks, so every lock branch of the web interpreter simply never triggers).

The model never rewrites the sketch config directly; it emits a list of
operations and apply_operations() executes each one through the SAME pure
reducers the manual form uses (sketch_state.py). That keeps AI edits and hand
edits byte-identical.

Pure: the input config is never mutated. Rejected ops leave config unchanged.
Each op returns an OperationResult dict: {"op", "status": "applied"|"rejected",
"detail"} for Debbie to relay.
"""

import re

from sketch_state import (
    MAX_CORES,
    MAX_LIFTS_PER_BANK,
    LOBBY_WIDTH_BOUNDS,
    SECTION_DIM_FONT_MAX,
    apply_car_bracket,
    apply_car_width,
    apply_cw_bracket,
    apply_door_gap,
    apply_door_panel_thickness,
    apply_door_type,
    apply_door_width,
    apply_double_entrance,
    apply_fire_cabin,
    apply_mra_cw_depth,
    apply_mra_cw_gap,
    apply_mra_cw_wall_gap,
    apply_mra_left_bracket,
    apply_mra_right_bracket,
    apply_rail_left,
    apply_rail_right,
    apply_shaft_depth,
    apply_shaft_width,
    carry_lift_id,
    clamp_dimension_font_scale,
    compute_default_separator_types,
    fill_blank_lift_ids,
    lift_error,
    make_default_core,
    make_default_lift,
    plan_dimension_font_max,
    section_error,
)

# ── Operation vocabulary (mirror of debbie-operations.ts) ──

LIFT_DIMENSION_FIELDS = frozenset([
    "capacity", "width", "depth", "cabin_height", "shaft_width", "shaft_depth",
    "door_width", "door_height", "door_panel_length", "door_panel_thickness",
    "structural_opening_width", "structural_opening_height",
    "telescopic_left_ext", "telescopic_right_ext",
    "cw_bracket_width", "car_bracket_width",
    "rail_width_left", "rail_width_right", "door_gap",
    "cw_box_width", "cw_box_depth", "mra_cw_box_width",
    "mra_left_bracket", "mra_right_bracket", "mra_cw_bracket_depth",
    "mra_cw_gap", "mra_cw_wall_gap", "door_offset_mm",
    "pit_depth", "overhead_clearance",
])

DISPLAY_OPTIONS = frozenset([
    "show_dimensions", "show_hatching", "show_centerlines", "show_capacity",
    "show_accessibility", "show_brackets", "show_lift_doors", "show_lift_id",
    "show_brief_spec", "split_lift_types",
    "section_show_dimensions", "section_show_hatching",
    "section_show_break_lines", "section_show_machine",
])

SECTION_FIELDS = frozenset([
    "shaft_depth", "wall_thickness", "pit_slab", "pit_depth", "travel_height",
    "overhead_clearance", "door_height", "structural_opening_height",
    "machine_room_height",
])

KNOWN_OPS = frozenset([
    "set_lift_dimension", "set_lift_type", "set_door_type", "set_fire_cabin",
    "set_door_direction", "toggle_lift_flag", "set_lift_id",
    "add_lift", "remove_lift", "set_arrangement", "set_common_shaft",
    "add_core", "remove_core", "set_lobby_width", "set_separator_type",
    "set_display_option", "set_font_scale", "set_machine_type",
    "set_section_field",
])


# ── Targeting ──

def _resolve_core_index(cfg: dict, ref):
    """Resolve a core reference (name like "Core 2", or an index) to a 0-based
    index, or -1 when it can't be found. Port of resolveCoreIndex()."""
    cores = cfg["cores"]

    def by_name(n):
        for i, c in enumerate(cores):
            if (c.get("name") or "").strip().lower() == f"core {n}":
                return i
        return -1

    if isinstance(ref, (int, float)) and not isinstance(ref, bool):
        ref = int(ref)
        named = by_name(ref)
        if named >= 0:
            return named
        if 0 <= ref < len(cores):
            return ref
        if 0 <= ref - 1 < len(cores):
            return ref - 1
        return -1
    if not isinstance(ref, str):
        return -1
    s = ref.strip().lower()
    for i, c in enumerate(cores):
        if (c.get("name") or "").strip().lower() == s:
            return i
    m = re.search(r"(\d+)", s)
    if m:
        n = int(m.group(1))
        named = by_name(n)
        if named >= 0:
            return named
        if 0 <= n - 1 < len(cores):
            return n - 1
    return -1


def _resolve_lift_targets(cfg: dict, target: dict) -> list:
    """Expand a lift target into the concrete lifts it addresses, in render
    order. Returns [(ci, bank, idx, lift), ...]. Port of resolveLiftTargets()."""
    out = []
    if not isinstance(target, dict):
        return out
    core_filter = None
    if target.get("core") is not None:
        core_filter = _resolve_core_index(cfg, target["core"])
    lift_ids = [str(x).strip() for x in (target.get("lift_ids") or [])]
    select = target.get("select")

    for ci, core in enumerate(cfg["cores"]):
        if core_filter is not None and core_filter != ci:
            continue
        for bank in ("bank1", "bank2"):
            lifts = core["bank1_lifts"] if bank == "bank1" else core["bank2_lifts"]
            for idx, lift in enumerate(lifts):
                match = (
                    (lift.get("lift_id") or "").strip() in lift_ids
                    or select == "all"
                    or (select == "all_passenger" and lift["type"] == "passenger")
                    or (select == "all_fire" and lift["type"] == "fire")
                )
                if match:
                    out.append((ci, bank, idx, lift))
    return out


# ── Immutable config helpers ──

def _update_core(cfg: dict, ci: int, next_core: dict) -> dict:
    cores = list(cfg["cores"])
    cores[ci] = next_core
    return {**cfg, "cores": cores}


def _replace_lift(cfg: dict, ci: int, bank: str, idx: int, new_lift: dict) -> dict:
    core = cfg["cores"][ci]
    key = "bank1_lifts" if bank == "bank1" else "bank2_lifts"
    lifts = list(core[key])
    lifts[idx] = new_lift
    sep_key = "separator_types_bank1" if bank == "bank1" else "separator_types_bank2"
    return _update_core(cfg, ci, {
        **core,
        key: lifts,
        sep_key: compute_default_separator_types(lifts, core["common_shaft"]),
    })


def _get_lift(cfg: dict, ci: int, bank: str, idx: int) -> dict:
    key = "bank1_lifts" if bank == "bank1" else "bank2_lifts"
    return cfg["cores"][ci][key][idx]


# ── Per-lift field dispatch (routes through the shared reducers) ──

def _apply_lift_field_change(lift: dict, field: str, value, machine_type: str) -> dict:
    if field == "shaft_width":
        return apply_shaft_width(lift, value, machine_type)
    if field == "shaft_depth":
        return apply_shaft_depth(lift, value, machine_type)
    if field == "width":
        return (apply_fire_cabin(lift, value, lift["depth"], machine_type)
                if lift["type"] == "fire" else apply_car_width(lift, value, machine_type))
    if field == "depth":
        return (apply_fire_cabin(lift, lift["width"], value, machine_type)
                if lift["type"] == "fire" else {**lift, "depth": value})
    if field == "door_width":
        return apply_door_width(lift, value)
    if field == "door_gap":
        return apply_door_gap(lift, value)
    if field == "door_panel_thickness":
        return apply_door_panel_thickness(lift, value)
    if field == "cw_bracket_width":
        return apply_cw_bracket(lift, value)
    if field == "car_bracket_width":
        return apply_car_bracket(lift, value)
    if field == "rail_width_left":
        return apply_rail_left(lift, value, machine_type)
    if field == "rail_width_right":
        return apply_rail_right(lift, value, machine_type)
    if field == "mra_left_bracket":
        return apply_mra_left_bracket(lift, value)
    if field == "mra_right_bracket":
        return apply_mra_right_bracket(lift, value)
    if field == "mra_cw_bracket_depth":
        return apply_mra_cw_depth(lift, value)
    if field == "mra_cw_gap":
        return apply_mra_cw_gap(lift, value)
    if field == "mra_cw_wall_gap":
        return apply_mra_cw_wall_gap(lift, value)
    # Plain fields without linking (capacity, door_height, offsets, boxes,
    # telescopic exts, pit/overhead, etc.).
    return {**lift, field: value}


def _rejected(op: dict, detail: str) -> dict:
    return {"op": op, "status": "rejected", "detail": detail}


def _applied(op: dict, detail: str) -> dict:
    return {"op": op, "status": "applied", "detail": detail}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ── Main entry point ──

def apply_operations(cfg: dict, ops: list, active_core: int = 0):
    """Apply a list of operations to a sketch config. Returns
    (new_config, results). Port of applyOperations() — standalone mode only
    (no lock manifest)."""
    working = cfg
    results = []

    for op_raw in ops:
        op = op_raw if isinstance(op_raw, dict) else {}
        name = op.get("op")
        try:
            if name == "set_lift_dimension":
                field, value = op.get("field"), op.get("value")
                if field not in LIFT_DIMENSION_FIELDS or not _is_num(value):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                ok_count = 0
                blocked = []
                for ci, bank, idx, _ in targets:
                    lift = _get_lift(working, ci, bank, idx)
                    nxt = _apply_lift_field_change(lift, field, value, working["machine_type"])
                    err = lift_error(nxt)
                    if err:
                        blocked.append(f"{lift.get('lift_id')} ({err})")
                        continue
                    working = _replace_lift(working, ci, bank, idx, nxt)
                    ok_count += 1
                if ok_count > 0:
                    detail = f"Set {field} = {value} on {ok_count} lift(s)"
                    detail += f"; skipped {', '.join(blocked)}" if blocked else "."
                    results.append(_applied(op, detail))
                else:
                    results.append(_rejected(op, f"Could not set {field}: {', '.join(blocked)}"))

            elif name == "set_lift_type":
                value = op.get("value")
                if value not in ("passenger", "fire"):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                ok_count = 0
                for ci, bank, idx, _ in targets:
                    lift = _get_lift(working, ci, bank, idx)
                    if lift["type"] == value:
                        continue
                    rebuilt = make_default_lift(value, working["machine_type"])
                    rebuilt["lift_id"] = carry_lift_id(lift, value)
                    working = _replace_lift(working, ci, bank, idx, rebuilt)
                    ok_count += 1
                results.append(
                    _applied(op, f"Changed {ok_count} lift(s) to {value}.")
                    if ok_count > 0 else _rejected(op, f"Lift(s) already {value}.")
                )

            elif name == "set_door_type":
                value = op.get("value")
                if value not in ("centre", "telescopic"):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                ok_count = 0
                blocked = []
                for ci, bank, idx, _ in targets:
                    lift = _get_lift(working, ci, bank, idx)
                    if lift["type"] != "fire":
                        blocked.append(f"{lift.get('lift_id')} (door type only applies to fire lifts)")
                        continue
                    working = _replace_lift(working, ci, bank, idx, apply_door_type(lift, value))
                    ok_count += 1
                if ok_count > 0:
                    detail = f"Set door opening to {value} on {ok_count} lift(s)"
                    detail += f"; skipped {', '.join(blocked)}" if blocked else "."
                    results.append(_applied(op, detail))
                else:
                    results.append(_rejected(op, ", ".join(blocked) or "No change."))

            elif name == "set_fire_cabin":
                w, d = op.get("width"), op.get("depth")
                if not (_is_num(w) and _is_num(d) and w > 0 and d > 0):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                targets = _resolve_lift_targets(working, op.get("target") or {})
                fire_targets = [t for t in targets if t[3]["type"] == "fire"]
                if not fire_targets:
                    results.append(_rejected(op, "No fire lift matched that target."))
                    continue
                ok_count = 0
                blocked = []
                for ci, bank, idx, _ in fire_targets:
                    lift = _get_lift(working, ci, bank, idx)
                    nxt = apply_fire_cabin(lift, w, d, working["machine_type"])
                    err = lift_error(nxt)
                    if err:
                        blocked.append(f"{lift.get('lift_id')} ({err})")
                        continue
                    working = _replace_lift(working, ci, bank, idx, nxt)
                    ok_count += 1
                if ok_count > 0:
                    detail = f"Set cabin {w}×{d} on {ok_count} lift(s)"
                    detail += f"; skipped {', '.join(blocked)}" if blocked else "."
                    results.append(_applied(op, detail))
                else:
                    results.append(_rejected(op, ", ".join(blocked) or "No change."))

            elif name == "set_door_direction":
                value = op.get("value")
                if value not in ("left", "right"):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                for ci, bank, idx, _ in targets:
                    lift = _get_lift(working, ci, bank, idx)
                    working = _replace_lift(working, ci, bank, idx,
                                            {**lift, "door_offset_direction": value})
                results.append(_applied(
                    op, f"Set door offset direction {value} on {len(targets)} lift(s)."))

            elif name == "toggle_lift_flag":
                flag, value = op.get("flag"), op.get("value")
                if flag not in ("double_entrance", "swap_brackets") or not isinstance(value, bool):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                ok_count = 0
                for ci, bank, idx, _ in targets:
                    lift = _get_lift(working, ci, bank, idx)
                    nxt = (apply_double_entrance(lift, value, working["machine_type"])
                           if flag == "double_entrance"
                           else {**lift, "swap_brackets": value})
                    working = _replace_lift(working, ci, bank, idx, nxt)
                    ok_count += 1
                results.append(_applied(
                    op, f"{'Enabled' if value else 'Disabled'} {flag} on {ok_count} lift(s)."))

            elif name == "add_lift":
                if not working["cores"]:
                    results.append(_rejected(op, "No core to add a lift to."))
                    continue
                ci = (_resolve_core_index(working, op["core"])
                      if op.get("core") is not None else active_core)
                if ci < 0 or ci >= len(working["cores"]):
                    results.append(_rejected(op, "Core not found."))
                    continue
                core = working["cores"][ci]
                bank = op.get("bank") or "bank1"
                key = "bank1_lifts" if bank == "bank1" else "bank2_lifts"
                if len(core[key]) >= MAX_LIFTS_PER_BANK:
                    results.append(_rejected(op, f"{bank} already has the maximum of 4 lifts."))
                    continue
                lift_type = op.get("lift_type") or "passenger"
                lifts = [*core[key], make_default_lift(lift_type, working["machine_type"])]
                sep_key = "separator_types_bank1" if bank == "bank1" else "separator_types_bank2"
                working = fill_blank_lift_ids(_update_core(working, ci, {
                    **core,
                    key: lifts,
                    sep_key: compute_default_separator_types(lifts, core["common_shaft"]),
                }))
                results.append(_applied(op, f"Added a {lift_type} lift to {core['name']} {bank}."))

            elif name == "remove_lift":
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                if len(targets) > 1:
                    results.append(_rejected(
                        op, f"That matched {len(targets)} lifts — specify a single lift_id."))
                    continue
                ci, bank, idx, ref_lift = targets[0]
                core = working["cores"][ci]
                key = "bank1_lifts" if bank == "bank1" else "bank2_lifts"
                if key == "bank1_lifts" and len(core["bank1_lifts"]) <= 1:
                    results.append(_rejected(op, "A core must keep at least one lift in bank 1."))
                    continue
                lifts = [lf for i, lf in enumerate(core[key]) if i != idx]
                sep_key = "separator_types_bank1" if bank == "bank1" else "separator_types_bank2"
                working = _update_core(working, ci, {
                    **core,
                    key: lifts,
                    sep_key: compute_default_separator_types(lifts, core["common_shaft"]),
                })
                results.append(_applied(op, f"Removed {ref_lift.get('lift_id')} from {core['name']}."))

            elif name == "set_arrangement":
                value = op.get("value")
                if value not in ("Inline", "Facing"):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                ci = (_resolve_core_index(working, op["core"])
                      if op.get("core") is not None else active_core)
                if ci < 0 or ci >= len(working["cores"]):
                    results.append(_rejected(op, "Core not found."))
                    continue
                core = working["cores"][ci]
                nxt = {**core, "arrangement": value}
                if value == "Facing" and not core["bank2_lifts"]:
                    bank2 = [make_default_lift("passenger", working["machine_type"]),
                             make_default_lift("passenger", working["machine_type"])]
                    nxt["bank2_lifts"] = bank2
                    nxt["separator_types_bank2"] = compute_default_separator_types(
                        bank2, core["common_shaft"])
                working = fill_blank_lift_ids(_update_core(working, ci, nxt))
                results.append(_applied(op, f"Set {core['name']} arrangement to {value}."))

            elif name == "set_common_shaft":
                value = op.get("value")
                if not isinstance(value, bool):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                ci = (_resolve_core_index(working, op["core"])
                      if op.get("core") is not None else active_core)
                if ci < 0 or ci >= len(working["cores"]):
                    results.append(_rejected(op, "Core not found."))
                    continue
                core = working["cores"][ci]
                working = _update_core(working, ci, {
                    **core,
                    "common_shaft": value,
                    "separator_types_bank1": compute_default_separator_types(
                        core["bank1_lifts"], value),
                    "separator_types_bank2": compute_default_separator_types(
                        core["bank2_lifts"], value),
                })
                results.append(_applied(
                    op, f"{'Enabled' if value else 'Disabled'} common shaft on {core['name']}."))

            elif name == "add_core":
                if len(working["cores"]) >= MAX_CORES:
                    results.append(_rejected(op, f"Maximum of {MAX_CORES} cores reached."))
                    continue
                cores = [*working["cores"],
                         make_default_core(working["machine_type"],
                                           f"Core {len(working['cores']) + 1}")]
                working = fill_blank_lift_ids({**working, "cores": cores})
                results.append(_applied(op, f"Added Core {len(cores)}."))

            elif name == "remove_core":
                if len(working["cores"]) <= 1:
                    results.append(_rejected(op, "At least one core is required."))
                    continue
                ci = _resolve_core_index(working, op.get("core"))
                if ci < 0:
                    results.append(_rejected(op, "Core not found."))
                    continue
                removed = working["cores"][ci]["name"]
                remaining = [c for j, c in enumerate(working["cores"]) if j != ci]
                cores = [{**c, "name": f"Core {i + 1}"} for i, c in enumerate(remaining)]
                working = fill_blank_lift_ids({**working, "cores": cores})
                results.append(_applied(op, f"Removed {removed}."))

            elif name == "set_display_option":
                option, value = op.get("option"), op.get("value")
                if option not in DISPLAY_OPTIONS or not isinstance(value, bool):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                working = {**working, option: value}
                results.append(_applied(op, f"Set {option} = {value}."))

            elif name == "set_font_scale":
                scope, value = op.get("scope"), op.get("value")
                if scope not in ("plan", "section") or not _is_num(value):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                if scope == "plan":
                    cores = working["cores"]
                    core = cores[active_core] if 0 <= active_core < len(cores) else cores[0]
                    max_scale = plan_dimension_font_max(
                        core["arrangement"], len(core["bank1_lifts"]), len(core["bank2_lifts"]))
                    working = {**working,
                               "dimension_font_scale": clamp_dimension_font_scale(value, max_scale)}
                else:
                    working = {**working,
                               "section_dimension_font_scale": clamp_dimension_font_scale(
                                   value, SECTION_DIM_FONT_MAX)}
                results.append(_applied(op, f"Set {scope} font scale to {value}."))

            elif name == "set_machine_type":
                value = op.get("value")
                if value not in ("mrl", "mra"):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                if working["machine_type"] == value:
                    results.append(_rejected(op, f"Already {value.upper()}."))
                    continue
                # Rebuild every lift for the new machine type, preserving the ID.
                def _rebuild(lf):
                    r = make_default_lift(lf["type"], value)
                    r["lift_id"] = lf.get("lift_id", "")
                    return r
                cores = [{**core,
                          "bank1_lifts": [_rebuild(lf) for lf in core["bank1_lifts"]],
                          "bank2_lifts": [_rebuild(lf) for lf in core["bank2_lifts"]]}
                         for core in working["cores"]]
                working = {**working, "machine_type": value, "cores": cores}
                results.append(_applied(
                    op, f"Switched to {value.upper()} (lift dimensions reset to defaults)."))

            elif name == "set_section_field":
                field, value = op.get("field"), op.get("value")
                if field not in SECTION_FIELDS or not _is_num(value):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                next_section = {**working["section"], field: value}
                err = section_error(next_section)
                if err:
                    results.append(_rejected(op, err))
                    continue
                working = {**working, "section": next_section}
                results.append(_applied(op, f"Set section {field} = {value}."))

            elif name == "set_lift_id":
                targets = _resolve_lift_targets(working, op.get("target") or {})
                if not targets:
                    results.append(_rejected(op, "No lift matched that target."))
                    continue
                if len(targets) > 1:
                    results.append(_rejected(
                        op, f"That matched {len(targets)} lifts — rename one at a time."))
                    continue
                new_id = str(op.get("value") or "").strip()
                if not new_id:
                    results.append(_rejected(op, "The new lift ID is empty."))
                    continue
                ci, bank, idx, ref_lift = targets[0]
                lift = _get_lift(working, ci, bank, idx)
                working = _replace_lift(working, ci, bank, idx, {**lift, "lift_id": new_id})
                results.append(_applied(op, f"Renamed {ref_lift.get('lift_id')} to {new_id}."))

            elif name == "set_lobby_width":
                value = op.get("value")
                lo, hi = LOBBY_WIDTH_BOUNDS
                if not _is_num(value):
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                if not (lo <= value <= hi):
                    results.append(_rejected(op, f"lobby width: must be between {lo} and {hi}"))
                    continue
                ci = (_resolve_core_index(working, op["core"])
                      if op.get("core") is not None else active_core)
                if ci < 0 or ci >= len(working["cores"]):
                    results.append(_rejected(op, "Core not found."))
                    continue
                core = working["cores"][ci]
                working = _update_core(working, ci, {**core, "lobby_width_mm": value})
                results.append(_applied(op, f"Set {core['name']} lobby depth to {value:g}."))

            elif name == "set_separator_type":
                value = op.get("value")
                index = op.get("index")
                if value not in ("steel_beam", "rcc_wall") or not isinstance(index, int) or index < 0:
                    results.append(_rejected(op, "Malformed operation."))
                    continue
                ci = (_resolve_core_index(working, op["core"])
                      if op.get("core") is not None else active_core)
                if ci < 0 or ci >= len(working["cores"]):
                    results.append(_rejected(op, "Core not found."))
                    continue
                core = working["cores"][ci]
                bank = op.get("bank") or "bank1"
                lifts = core["bank2_lifts"] if bank == "bank2" else core["bank1_lifts"]
                gaps = max(0, len(lifts) - 1)
                if gaps == 0:
                    results.append(_rejected(
                        op, f"{core['name']} {bank} has no separators (needs 2+ lifts)."))
                    continue
                if index >= gaps:
                    results.append(_rejected(
                        op, f"Separator index out of range (valid 0..{gaps - 1})."))
                    continue
                sep_key = "separator_types_bank2" if bank == "bank2" else "separator_types_bank1"
                seps = list(core[sep_key])
                while len(seps) < gaps:
                    seps.append("rcc_wall")
                seps[index] = value
                working = _update_core(working, ci, {**core, sep_key: seps[:gaps]})
                results.append(_applied(
                    op, f"Set {core['name']} {bank} separator {index + 1} to {value}."))

            else:
                results.append(_rejected(op, "Unknown operation."))

        except (TypeError, KeyError, IndexError) as e:
            # A blank (NaN/None) cell or malformed payload made the linking math
            # fail — reject this op and keep going (config unchanged for it).
            results.append(_rejected(op, f"Could not apply ({e.__class__.__name__})."))

    return working, results
