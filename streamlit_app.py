"""
Streamlit web app for generating lift shaft plan sketches.
"""

import streamlit as st
from shaft_sketch import LiftShaftSketch, LiftConfig, FIRE_LIFT_CABIN_SIZES
from section_sketch import LiftSectionSketch, SectionConfig
import config

# Fire lift cabin size options for dropdown
FIRE_CABIN_OPTIONS = {
    f"{w} x {d} mm": (w, d) for w, d in FIRE_LIFT_CABIN_SIZES
}



def get_default_lift_config(lift_type: str = "passenger") -> dict:
    """Get default configuration for a lift type."""
    if lift_type == "fire":
        return {
            "type": "fire",
            "capacity": 1600,
            "width": 1400,
            "depth": 2400,
            "door_width": config.FIRE_LIFT_DOOR_WIDTH,
            "door_panel_thickness": config.DEFAULT_LIFT_DOOR_THICKNESS,
            "door_extension": config.DEFAULT_DOOR_EXTENSION,
            "door_opening_type": "centre",
        }
    return {
        "type": "passenger",
        "capacity": config.DEFAULT_LIFT_CAPACITY,
        "width": config.DEFAULT_FINISHED_CAR_WIDTH,
        "depth": config.DEFAULT_FINISHED_CAR_DEPTH,
        "door_width": config.DEFAULT_DOOR_WIDTH,
        "door_panel_thickness": config.DEFAULT_LIFT_DOOR_THICKNESS,
        "door_extension": config.DEFAULT_DOOR_EXTENSION,
        "door_opening_type": "centre",
    }


def render_lift_config_form(
    lift_index: int,
    bank_name: str,
    machine_type: str,
    initial_values: dict = None,
    show_capacity_input: bool = False,
) -> dict:
    """
    Render configuration form for a single lift.

    Returns dict with lift configuration values.
    """
    if initial_values is None:
        initial_values = get_default_lift_config()

    key_prefix = f"{bank_name}_lift_{lift_index}"

    with st.expander(f"Lift {lift_index + 1}", expanded=(lift_index == 0)):
        st.caption("* Required fields")

        # Copy from Lift 1 button (for lifts 2+, disabled when lift 1 is fire)
        if lift_index > 0:
            lift1_is_fire = st.session_state.get(f"{bank_name}_lift_0_type") == "fire"
            copy_key = f"{key_prefix}_copy_from_lift1"
            if st.button(
                "Copy from Lift 1", key=copy_key,
                disabled=lift1_is_fire,
                help="Disabled: Fire/Service lift settings cannot be copied" if lift1_is_fire
                     else "Copy all settings from Lift 1",
            ):
                lift1_prefix = f"{bank_name}_lift_0"
                st.session_state[f"{key_prefix}_copy_pending"] = True
                st.rerun()

        # Handle pending copy
        if st.session_state.get(f"{key_prefix}_copy_pending"):
            lift1_prefix = f"{bank_name}_lift_0"
            # Copy relevant session state keys
            keys_to_copy = ["_capacity", "_width", "_depth", "_door_width",
                            "_door_height", "_door_panel_length", "_door_panel_thickness",
                            "_structural_opening_width", "_structural_opening_height",
                            "_cw_bracket", "_car_bracket",
                            "_mra_left_bracket", "_mra_right_bracket",
                            "_mra_cw_bracket", "_mra_cw_gap",
                            "_shaft_width", "_shaft_depth",
                            "_door_opening_type", "_telescopic_left_ext", "_telescopic_right_ext"]
            for k in keys_to_copy:
                src_key = f"{lift1_prefix}{k}"
                dst_key = f"{key_prefix}{k}"
                if src_key in st.session_state:
                    st.session_state[dst_key] = st.session_state[src_key]
            st.session_state[f"{key_prefix}_copy_pending"] = False

        # Lift type selection
        lift_type_options = ["passenger", "fire"] if lift_index == 0 else ["passenger"]
        lift_type = st.selectbox(
            "Lift Type",
            options=lift_type_options,
            format_func=lambda x: "fire/service" if x == "fire" else x,
            index=0 if initial_values.get("type", "passenger") == "passenger" else 1,
            key=f"{key_prefix}_type",
            help="Fire/Service lift only allowed at position 1 (first lift)",
        )

        # --- Shaft Dimensions (first, before car/brackets) ---
        st.divider()
        st.markdown("**Shaft Dimensions**")

        # Compute lift-type and machine-type aware defaults
        if lift_type == "fire":
            _fire_defaults = get_default_lift_config("fire")
            _def_car_w = _fire_defaults["width"]
            _def_car_d = _fire_defaults["depth"]
        else:
            _def_car_w = initial_values.get("width", config.DEFAULT_FINISHED_CAR_WIDTH)
            _def_car_d = initial_values.get("depth", config.DEFAULT_FINISHED_CAR_DEPTH)
        _def_uc_w = _def_car_w + 2 * config.DEFAULT_CAR_WALL_THICKNESS
        _def_uc_d = _def_car_d + config.DEFAULT_CAR_WALL_THICKNESS
        if machine_type == "mra":
            _default_sw = int(_def_uc_w + 2 * config.MRA_CAR_BRACKET_WIDTH)
            _default_sd = int(2 * config.DEFAULT_LIFT_DOOR_THICKNESS + config.DEFAULT_DOOR_GAP
                              + _def_uc_d + config.MRA_CW_GAP + config.MRA_CW_BRACKET_DEPTH)
        elif lift_type == "fire":
            # MRL fire lift: compute from fire cabin dims (default MRL dims are for passenger)
            _default_sw = int(config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH + _def_uc_w
                              + config.DEFAULT_CAR_BRACKET_WIDTH)
            _default_sd = int(2 * config.DEFAULT_LIFT_DOOR_THICKNESS + config.DEFAULT_DOOR_GAP
                              + _def_uc_d + config.DEFAULT_REAR_CLEARANCE)
        else:
            _default_sw = int(config.DEFAULT_SHAFT_WIDTH)
            _default_sd = int(config.DEFAULT_SHAFT_DEPTH)
        # Enforce fire lift minimum shaft width
        if lift_type == "fire":
            _fire_min_sw = (config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC
                            if st.session_state.get(f"{key_prefix}_door_opening_type") == "Telescopic Opening"
                            else config.FIRE_LIFT_MIN_SHAFT_WIDTH)
            _default_sw = max(_default_sw, int(_fire_min_sw))

        # Reset shaft dims when machine type or lift type changes
        _stale_bracket_keys = ["_cw_bracket", "_car_bracket", "_avail_w",
                               "_mra_cw_bracket", "_mra_cw_gap", "_avail_d",
                               "_mra_left_bracket", "_mra_right_bracket", "_avail_mra_w",
                               "_door_width", "_door_panel_length",
                               "_door_opening_type", "_telescopic_left_ext",
                               "_telescopic_right_ext", "_prev_door_width"]

        mt_key = f"{key_prefix}_prev_machine_type"
        if mt_key in st.session_state and st.session_state[mt_key] != machine_type:
            st.session_state[f"{key_prefix}_shaft_width"] = _default_sw
            st.session_state[f"{key_prefix}_shaft_depth"] = _default_sd
            for k in _stale_bracket_keys:
                st.session_state.pop(f"{key_prefix}{k}", None)
        st.session_state[mt_key] = machine_type

        lt_key = f"{key_prefix}_prev_lift_type"
        if lt_key in st.session_state and st.session_state[lt_key] != lift_type:
            st.session_state[f"{key_prefix}_shaft_width"] = _default_sw
            st.session_state[f"{key_prefix}_shaft_depth"] = _default_sd
            for k in _stale_bracket_keys:
                st.session_state.pop(f"{key_prefix}{k}", None)
        st.session_state[lt_key] = lift_type

        col_sw, col_sd = st.columns(2)
        with col_sw:
            # Clamp shaft width value to valid range
            sw_value = int(initial_values.get("shaft_width_override", 0) or _default_sw)
            sw_value = max(500, min(sw_value, 6000))

            # Fix session state if invalid
            sw_key = f"{key_prefix}_shaft_width"
            if sw_key in st.session_state:
                if st.session_state[sw_key] < 500 or st.session_state[sw_key] > 6000:
                    st.session_state[sw_key] = sw_value

            shaft_width_input = st.number_input(
                "Shaft Width (mm)",
                min_value=500, max_value=6000,
                value=sw_value,
                step=10, key=sw_key,
                help="Internal shaft width. Leave at default or increase for extra space."
            )
        with col_sd:
            # Clamp shaft depth value to valid range
            sd_value = int(initial_values.get("shaft_depth_override", 0) or _default_sd)
            sd_value = max(500, min(sd_value, 6000))

            # Fix session state if invalid
            sd_key = f"{key_prefix}_shaft_depth"
            if sd_key in st.session_state:
                if st.session_state[sd_key] < 500 or st.session_state[sd_key] > 6000:
                    st.session_state[sd_key] = sd_value

            shaft_depth_input = st.number_input(
                "Shaft Depth (mm)",
                min_value=500, max_value=6000,
                value=sd_value,
                step=10, key=sd_key,
                help="Internal shaft depth. Leave at default or increase for extra space."
            )

        # Capacity input (only shown when Show Capacity Label is on)
        if show_capacity_input:
            capacity = st.number_input(
                "Capacity (KG)",
                min_value=100,
                max_value=10000,
                value=initial_values.get("capacity", config.DEFAULT_LIFT_CAPACITY),
                step=50,
                key=f"{key_prefix}_capacity",
            )
        else:
            capacity = None

        # Car dimensions
        if lift_type == "fire":
            # Fire/Service lift: dropdown for fixed cabin sizes
            cabin_options = list(FIRE_CABIN_OPTIONS.keys())
            default_size = f"{initial_values.get('width', 1400)} x {initial_values.get('depth', 2400)} mm"
            if default_size not in cabin_options:
                default_size = cabin_options[0]

            cabin_size = st.selectbox(
                "Cabin Size (Width x Depth)",
                options=cabin_options,
                index=cabin_options.index(default_size),
                key=f"{key_prefix}_cabin_size",
                help="Fire/Service lifts have fixed cabin sizes",
            )
            car_width, car_depth = FIRE_CABIN_OPTIONS[cabin_size]
            door_width = config.FIRE_LIFT_DOOR_WIDTH
        else:
            # Passenger lift: manual input
            col1, col2 = st.columns(2)
            with col1:
                car_width = st.number_input(
                    "Finished Car Width (mm) *",
                    min_value=800,
                    max_value=3000,
                    value=int(initial_values.get("width", config.DEFAULT_FINISHED_CAR_WIDTH)),
                    step=10,
                    key=f"{key_prefix}_width",
                )
            with col2:
                car_depth = st.number_input(
                    "Finished Car Depth (mm) *",
                    min_value=800,
                    max_value=3000,
                    value=int(initial_values.get("depth", config.DEFAULT_FINISHED_CAR_DEPTH)),
                    step=10,
                    key=f"{key_prefix}_depth",
                )

        # Bracket Configuration (derived from shaft dimensions)
        st.divider()
        st.markdown("**Bracket Spaces**")

        unfinished_car_width = car_width + 2 * config.DEFAULT_CAR_WALL_THICKNESS

        if machine_type == "mrl":
            # MRL Width: shaft_width = CW_bracket + unfinished_car_width + car_bracket
            # Both brackets are adjustable inputs linked by zero-sum constraint.
            min_cw = int(config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH)  # 625
            min_car = int(config.DEFAULT_CAR_BRACKET_WIDTH)  # 375
            available_width = int(shaft_width_input - unfinished_car_width)
            min_shaft_width = min_cw + unfinished_car_width + min_car

            if available_width < min_cw + min_car:
                cw_bracket = min_cw
                car_bracket = min_car
            else:
                extra = available_width - min_cw - min_car
                default_cw = min_cw + extra // 2
                default_car = available_width - default_cw

                cw_key = f"{key_prefix}_cw_bracket"
                car_key = f"{key_prefix}_car_bracket"
                avail_key = f"{key_prefix}_avail_w"

                # Initialize session state on first run
                if cw_key not in st.session_state:
                    st.session_state[cw_key] = int(initial_values.get("cw_bracket_width", default_cw))
                if car_key not in st.session_state:
                    st.session_state[car_key] = int(initial_values.get("car_bracket_width", default_car))

                # When available_width changes (shaft/car width changed), split
                # the change equally between both brackets
                prev_avail = st.session_state.get(avail_key)
                if prev_avail is not None and prev_avail != available_width:
                    delta = available_width - prev_avail
                    half = delta // 2
                    new_cw = st.session_state[cw_key] + half
                    new_car = available_width - new_cw
                    # Clamp both within their minimums
                    if new_cw >= min_cw and new_car >= min_car:
                        st.session_state[cw_key] = new_cw
                        st.session_state[car_key] = new_car
                    else:
                        # Reset both to new defaults (equal split)
                        new_extra = available_width - min_cw - min_car
                        st.session_state[cw_key] = min_cw + new_extra // 2
                        st.session_state[car_key] = available_width - st.session_state[cw_key]
                st.session_state[avail_key] = available_width

                # Callbacks: changing one bracket auto-adjusts the other
                def _on_cw_change():
                    a = st.session_state[avail_key]
                    st.session_state[car_key] = max(min_car, a - st.session_state[cw_key])

                def _on_car_change():
                    a = st.session_state[avail_key]
                    st.session_state[cw_key] = max(min_cw, a - st.session_state[car_key])

                col_br1, col_br2 = st.columns(2)
                with col_br1:
                    cw_bracket = st.number_input(
                        "CW Bracket Width (mm)",
                        min_value=min_cw,
                        max_value=available_width - min_car,
                        step=25, key=cw_key,
                        on_change=_on_cw_change,
                        help=f"Min {min_cw}mm. Car bracket auto-adjusts."
                    )
                with col_br2:
                    car_bracket = st.number_input(
                        "Car Bracket Width (mm)",
                        min_value=min_car,
                        max_value=available_width - min_cw,
                        step=25, key=car_key,
                        on_change=_on_car_change,
                        help=f"Min {min_car}mm. CW bracket auto-adjusts."
                    )

            mra_car_bracket = None
            mra_cw_bracket = None

        else:  # MRA
            # MRA Width: shaft_width = left_bracket + uc_width + right_bracket
            # Both brackets are adjustable linked inputs (same as MRL pattern).
            available_width = int(shaft_width_input - unfinished_car_width)
            min_mra_car = int(config.MRA_CAR_BRACKET_WIDTH)  # 325
            min_shaft_width = unfinished_car_width + 2 * min_mra_car

            if available_width < 2 * min_mra_car:
                mra_car_bracket_left = min_mra_car
                mra_car_bracket_right = min_mra_car
            else:
                extra = available_width - 2 * min_mra_car
                default_left = min_mra_car + extra // 2
                default_right = available_width - default_left

                left_key = f"{key_prefix}_mra_left_bracket"
                right_key = f"{key_prefix}_mra_right_bracket"
                avail_mra_w_key = f"{key_prefix}_avail_mra_w"

                # Initialize session state on first run
                if left_key not in st.session_state:
                    st.session_state[left_key] = int(initial_values.get("mra_car_bracket_width", default_left))
                if right_key not in st.session_state:
                    st.session_state[right_key] = int(initial_values.get("mra_car_bracket_width_right", default_right))

                # When available_width changes, split equally
                prev_avail_mra = st.session_state.get(avail_mra_w_key)
                if prev_avail_mra is not None and prev_avail_mra != available_width:
                    delta = available_width - prev_avail_mra
                    half = delta // 2
                    new_left = st.session_state[left_key] + half
                    new_right = available_width - new_left
                    if new_left >= min_mra_car and new_right >= min_mra_car:
                        st.session_state[left_key] = new_left
                        st.session_state[right_key] = new_right
                    else:
                        new_extra = available_width - 2 * min_mra_car
                        st.session_state[left_key] = min_mra_car + new_extra // 2
                        st.session_state[right_key] = available_width - st.session_state[left_key]
                st.session_state[avail_mra_w_key] = available_width

                def _on_left_change():
                    a = st.session_state[avail_mra_w_key]
                    st.session_state[right_key] = max(min_mra_car, a - st.session_state[left_key])

                def _on_right_change():
                    a = st.session_state[avail_mra_w_key]
                    st.session_state[left_key] = max(min_mra_car, a - st.session_state[right_key])

                col_br1, col_br2 = st.columns(2)
                with col_br1:
                    mra_car_bracket_left = st.number_input(
                        "Left Car Bracket (mm)",
                        min_value=min_mra_car,
                        max_value=available_width - min_mra_car,
                        step=25, key=left_key,
                        on_change=_on_left_change,
                        help=f"Min {min_mra_car}mm. Right bracket auto-adjusts."
                    )
                with col_br2:
                    mra_car_bracket_right = st.number_input(
                        "Right Car Bracket (mm)",
                        min_value=min_mra_car,
                        max_value=available_width - min_mra_car,
                        step=25, key=right_key,
                        on_change=_on_right_change,
                        help=f"Min {min_mra_car}mm. Left bracket auto-adjusts."
                    )

            cw_bracket = None
            car_bracket = None

        # Apply fire lift minimum width if applicable
        if lift_type == "fire":
            _fire_min_sw = (config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC
                            if st.session_state.get(f"{key_prefix}_door_opening_type") == "Telescopic Opening"
                            else config.FIRE_LIFT_MIN_SHAFT_WIDTH)
            min_shaft_width = max(min_shaft_width, _fire_min_sw)

        # Use shaft_width_input for door panel length constraint (may be larger than min)
        shaft_width = max(shaft_width_input, min_shaft_width)

        # Door Settings (after brackets so we can validate against shaft width)
        st.divider()
        st.markdown("**Door Settings**")

        # Telescopic door variables (set defaults for non-fire lifts)
        door_opening_type = "centre"
        telescopic_left_ext = None
        telescopic_right_ext = None

        col_dw, col_dh = st.columns(2)
        with col_dw:
            if lift_type == "fire":
                # Ensure fire lift door width is at least the minimum
                fire_door_default = max(
                    int(initial_values.get("door_width", config.FIRE_LIFT_DOOR_WIDTH)),
                    int(config.FIRE_LIFT_DOOR_WIDTH)
                )
                door_width = st.number_input(
                    "Door Width (mm)",
                    min_value=int(config.FIRE_LIFT_DOOR_WIDTH),
                    max_value=2000,
                    value=fire_door_default,
                    step=50, key=f"{key_prefix}_door_width",
                    help=f"Minimum {config.FIRE_LIFT_DOOR_WIDTH}mm for fire/service lifts"
                )
            else:
                door_width = st.number_input(
                    "Door Width (mm)",
                    min_value=700, max_value=2000,
                    value=int(initial_values.get("door_width", config.DEFAULT_DOOR_WIDTH)),
                    step=50, key=f"{key_prefix}_door_width",
                    help="Width of the door opening"
                )
        with col_dh:
            door_height = st.number_input(
                "Door Opening Height (mm)",
                min_value=1500, max_value=3500,
                value=int(initial_values.get("door_height", config.DEFAULT_DOOR_HEIGHT)),
                step=50, key=f"{key_prefix}_door_height",
                help="Height of the door opening"
            )

        if lift_type == "fire":
            # Door Opening Type selector (fire lifts only)
            opening_type_options = ["Centre Opening", "Telescopic Opening"]
            opening_type_idx = 0
            stored_type = st.session_state.get(f"{key_prefix}_door_opening_type")
            if stored_type == "Telescopic Opening" or initial_values.get("door_opening_type") == "telescopic":
                opening_type_idx = 1
            door_opening_type_label = st.selectbox(
                "Door Opening Type",
                options=opening_type_options,
                index=opening_type_idx,
                key=f"{key_prefix}_door_opening_type",
                help="Centre Opening: symmetric panels. Telescopic: asymmetric shorter panel."
            )
            door_opening_type = "telescopic" if door_opening_type_label == "Telescopic Opening" else "centre"

        if door_opening_type == "telescopic":
            # Telescopic extension inputs
            default_left = int(0.5 * door_width + config.TELESCOPIC_LEFT_EXTENSION_EXTRA)
            default_right = config.TELESCOPIC_RIGHT_EXTENSION
            col_tl, col_tr = st.columns(2)
            with col_tl:
                # Clamp value to valid range
                left_ext_value = max(50, min(int(initial_values.get("telescopic_left_ext", default_left)), 2000))

                # Auto-update left extension if it was at the previous default
                left_key = f"{key_prefix}_telescopic_left_ext"
                prev_dw_key = f"{key_prefix}_prev_door_width"
                if left_key in st.session_state:
                    prev_dw = st.session_state.get(prev_dw_key, door_width)
                    old_default = int(0.5 * prev_dw + config.TELESCOPIC_LEFT_EXTENSION_EXTRA)
                    if st.session_state[left_key] == old_default and old_default != default_left:
                        st.session_state[left_key] = default_left
                    elif st.session_state[left_key] < 50 or st.session_state[left_key] > 2000:
                        st.session_state[left_key] = left_ext_value
                st.session_state[prev_dw_key] = door_width

                telescopic_left_ext = st.number_input(
                    "Left Extension (mm)",
                    min_value=50, max_value=2000,
                    value=left_ext_value,
                    step=25, key=left_key,
                    help="Extension beyond door width on left side"
                )
            with col_tr:
                # Clamp value to valid range
                right_ext_value = max(50, min(int(initial_values.get("telescopic_right_ext", default_right)), 1000))

                # Fix session state if invalid
                right_key = f"{key_prefix}_telescopic_right_ext"
                if right_key in st.session_state:
                    if st.session_state[right_key] < 50 or st.session_state[right_key] > 1000:
                        st.session_state[right_key] = right_ext_value

                telescopic_right_ext = st.number_input(
                    "Right Extension (mm)",
                    min_value=50, max_value=1000,
                    value=right_ext_value,
                    step=25, key=right_key,
                    help="Extension beyond door width on right side"
                )
            total_panel = telescopic_left_ext + door_width + telescopic_right_ext
            st.caption(f"Total panel length: {int(total_panel)}mm")
            # For telescopic, door_extension is not used for drawing
            door_extension = 0
            door_panel_length = int(total_panel)

            # Door panel thickness (for telescopic)
            # Clamp value to valid range
            thickness_value = max(50, min(int(initial_values.get("door_panel_thickness", config.DEFAULT_LIFT_DOOR_THICKNESS)), 300))

            # Fix session state if invalid
            thickness_key = f"{key_prefix}_door_panel_thickness"
            if thickness_key in st.session_state:
                if st.session_state[thickness_key] < 50 or st.session_state[thickness_key] > 300:
                    st.session_state[thickness_key] = thickness_value

            door_panel_thickness = st.number_input(
                "Door Panel Thickness (mm)",
                min_value=50,
                max_value=300,
                value=thickness_value,
                step=10,
                key=thickness_key,
                help="Depth of each door panel. Affects shaft depth calculation."
            )
        else:
            # Default panel length = 2×door_width + 2×extension, capped at shaft width
            default_panel_length = min(2 * door_width + 2 * config.DEFAULT_DOOR_EXTENSION, shaft_width)

            # Auto-adjust panel length when door_width changes (panel contains 2× door)
            panel_key = f"{key_prefix}_door_panel_length"
            prev_dw_key = f"{key_prefix}_prev_door_width"
            if panel_key in st.session_state:
                prev_dw = st.session_state.get(prev_dw_key, door_width)
                if prev_dw != door_width:
                    delta = int(2 * (door_width - prev_dw))
                    st.session_state[panel_key] = st.session_state[panel_key] + delta
            st.session_state[prev_dw_key] = door_width

            col_dpl, col_dpt = st.columns(2)
            with col_dpl:
                door_panel_length = st.number_input(
                    "Door Panel Length (mm)",
                    min_value=500,
                    max_value=6000,
                    value=int(initial_values.get("door_panel_length", default_panel_length)),
                    step=50,
                    key=f"{key_prefix}_door_panel_length",
                    help="Total door panel length. Auto-calculated from door width + extensions."
                )
            with col_dpt:
                # Clamp value to valid range
                thickness_value = max(50, min(int(initial_values.get("door_panel_thickness", config.DEFAULT_LIFT_DOOR_THICKNESS)), 300))

                # Fix session state if invalid
                thickness_key = f"{key_prefix}_door_panel_thickness"
                if thickness_key in st.session_state:
                    if st.session_state[thickness_key] < 50 or st.session_state[thickness_key] > 300:
                        st.session_state[thickness_key] = thickness_value

                door_panel_thickness = st.number_input(
                    "Door Panel Thickness (mm)",
                    min_value=50,
                    max_value=300,
                    value=thickness_value,
                    step=10,
                    key=thickness_key,
                    help="Depth of each door panel. Affects shaft depth calculation."
                )

        col_sow, col_soh = st.columns(2)
        with col_sow:
            structural_opening_width = st.number_input(
                "Structural Opening Width (mm)",
                min_value=800,
                max_value=3000,
                value=int(initial_values.get("structural_opening_width", config.DEFAULT_STRUCTURAL_OPENING_WIDTH)),
                step=50,
                key=f"{key_prefix}_structural_opening_width",
                help="Width of structural opening in front wall"
            )
        with col_soh:
            structural_opening_height = st.number_input(
                "Structural Opening Height (mm)",
                min_value=1500,
                max_value=4000,
                value=int(initial_values.get("structural_opening_height", config.DEFAULT_STRUCTURAL_OPENING_HEIGHT)),
                step=50,
                key=f"{key_prefix}_structural_opening_height",
                help="Height of structural opening in front wall"
            )

        # Calculate extension from panel length (centre opening only)
        if door_opening_type != "telescopic":
            door_extension = (door_panel_length - 2 * door_width) / 2

        # --- MRA Depth bracket inputs (after door settings, needs door_panel_thickness) ---
        unfinished_car_depth = car_depth + config.DEFAULT_CAR_WALL_THICKNESS
        has_errors = False

        if machine_type == "mrl":
            mra_cw_bracket = None
            mra_cw_gap = None
        else:  # MRA depth brackets (shown under same Bracket Spaces section)
            fixed_depth = 2 * door_panel_thickness + config.DEFAULT_DOOR_GAP + unfinished_car_depth
            available_depth = int(shaft_depth_input - fixed_depth)
            min_cw_depth = int(config.MRA_CW_BRACKET_DEPTH)  # 400
            min_cw_gap = int(config.MRA_CW_GAP)  # 100

            if available_depth < min_cw_depth + min_cw_gap:
                mra_cw_bracket = min_cw_depth
                mra_cw_gap = min_cw_gap
            else:
                extra_depth = available_depth - min_cw_depth - min_cw_gap
                default_cw_depth = min_cw_depth + extra_depth // 2
                default_cw_gap = available_depth - default_cw_depth

                cwb_key = f"{key_prefix}_mra_cw_bracket"
                cwg_key = f"{key_prefix}_mra_cw_gap"
                avail_d_key = f"{key_prefix}_avail_d"

                if cwb_key not in st.session_state:
                    st.session_state[cwb_key] = int(initial_values.get("mra_cw_bracket_depth", default_cw_depth))
                if cwg_key not in st.session_state:
                    st.session_state[cwg_key] = int(initial_values.get("mra_cw_gap", default_cw_gap))

                prev_avail_d = st.session_state.get(avail_d_key)
                if prev_avail_d is not None and prev_avail_d != available_depth:
                    delta = available_depth - prev_avail_d
                    half = delta // 2
                    new_cwb = st.session_state[cwb_key] + half
                    new_cwg = available_depth - new_cwb
                    if new_cwb >= min_cw_depth and new_cwg >= min_cw_gap:
                        st.session_state[cwb_key] = new_cwb
                        st.session_state[cwg_key] = new_cwg
                    else:
                        new_extra = available_depth - min_cw_depth - min_cw_gap
                        st.session_state[cwb_key] = min_cw_depth + new_extra // 2
                        st.session_state[cwg_key] = available_depth - st.session_state[cwb_key]
                st.session_state[avail_d_key] = available_depth

                def _on_cwb_change():
                    a = st.session_state[avail_d_key]
                    st.session_state[cwg_key] = max(min_cw_gap, a - st.session_state[cwb_key])

                def _on_cwg_change():
                    a = st.session_state[avail_d_key]
                    st.session_state[cwb_key] = max(min_cw_depth, a - st.session_state[cwg_key])

                st.caption("Depth")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    mra_cw_bracket = st.number_input(
                        "CW Bracket Depth (mm)",
                        min_value=min_cw_depth,
                        max_value=available_depth - min_cw_gap,
                        step=25, key=cwb_key,
                        on_change=_on_cwb_change,
                        help=f"Min {min_cw_depth}mm. CW gap auto-adjusts."
                    )
                with col_d2:
                    mra_cw_gap = st.number_input(
                        "CW Gap (mm)",
                        min_value=min_cw_gap,
                        max_value=available_depth - min_cw_depth,
                        step=25, key=cwg_key,
                        on_change=_on_cwg_change,
                        help=f"Min {min_cw_gap}mm. CW bracket depth auto-adjusts."
                    )

        # --- Validation ---
        temp_kwargs = {
            "lift_type": lift_type,
            "finished_car_width": car_width,
            "finished_car_depth": car_depth,
            "lift_machine_type": machine_type,
            "door_width": door_width,
            "door_panel_thickness": door_panel_thickness,
            "door_opening_type": door_opening_type,
            "structural_opening_width": structural_opening_width,
        }
        if machine_type == "mrl":
            temp_kwargs["counterweight_bracket_width"] = cw_bracket
            temp_kwargs["car_bracket_width"] = car_bracket
        else:
            temp_kwargs["mra_car_bracket_width"] = mra_car_bracket_left
            temp_kwargs["mra_car_bracket_width_right"] = mra_car_bracket_right
            temp_kwargs["mra_cw_bracket_depth"] = mra_cw_bracket

        try:
            temp_lift = LiftConfig(**temp_kwargs)
            min_sw = int(temp_lift.min_shaft_width)
            min_sd = int(temp_lift.min_shaft_depth)

            shaft_width_override = shaft_width_input if shaft_width_input > min_sw else None
            shaft_depth_override = shaft_depth_input if shaft_depth_input > min_sd else None

            errors = []
            if shaft_width_input < min_sw:
                errors.append(f"Shaft Width ({shaft_width_input}mm) below minimum ({min_sw}mm)")
            if shaft_depth_input < min_sd:
                errors.append(f"Shaft Depth ({shaft_depth_input}mm) below minimum ({min_sd}mm)")
            if lift_type == "fire":
                _fire_min_sw_check = (config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC
                                      if door_opening_type == "telescopic"
                                      else config.FIRE_LIFT_MIN_SHAFT_WIDTH)
                if shaft_width_input < _fire_min_sw_check:
                    errors.append(f"Fire/Service lift shaft width ({shaft_width_input}mm) below minimum ({int(_fire_min_sw_check)}mm)")
            actual_sw = max(shaft_width_input, min_sw)
            if door_width > structural_opening_width:
                errors.append(f"Door Width ({door_width}mm) exceeds Structural Opening Width ({structural_opening_width}mm)")
            if door_opening_type == "centre":
                if door_panel_length > actual_sw:
                    errors.append(f"Door Panel Length ({door_panel_length}mm) exceeds shaft width ({int(actual_sw)}mm)")

            if errors:
                st.error(" | ".join(errors))
                has_errors = True
            else:
                # Component breakdown info box
                actual_sd = max(shaft_depth_input, min_sd)
                if machine_type == "mrl":
                    rear_cl = actual_sd - (2 * door_panel_thickness + config.DEFAULT_DOOR_GAP + unfinished_car_depth)
                    info_str = (
                        f"**{actual_sw}mm W x {actual_sd}mm D** | "
                        f"CW Bracket: {int(cw_bracket)}mm | "
                        f"Car Bracket: {int(car_bracket)}mm | "
                        f"Rear Clearance: {int(rear_cl)}mm"
                    )
                else:
                    cw_gap_display = mra_cw_gap if mra_cw_gap is not None else int(actual_sd - (2 * door_panel_thickness + config.DEFAULT_DOOR_GAP + unfinished_car_depth + mra_cw_bracket))
                    info_str = (
                        f"**{actual_sw}mm W x {actual_sd}mm D** | "
                        f"L Bracket: {int(mra_car_bracket_left)}mm | "
                        f"R Bracket: {int(mra_car_bracket_right)}mm | "
                        f"CW Depth: {int(mra_cw_bracket)}mm | "
                        f"CW Gap: {int(cw_gap_display)}mm"
                    )
                st.info(info_str)

        except ValueError as e:
            shaft_width_override = None
            shaft_depth_override = None
            has_errors = True
            st.error(str(e))

    return {
        "type": lift_type,
        "capacity": capacity,
        "width": car_width,
        "depth": car_depth,
        "door_width": door_width,
        "door_height": door_height,
        "door_panel_thickness": door_panel_thickness,
        "door_extension": door_extension,
        "structural_opening_width": structural_opening_width,
        "structural_opening_height": structural_opening_height,
        "cw_bracket_width": cw_bracket,
        "car_bracket_width": car_bracket,
        "mra_car_bracket_width": mra_car_bracket_left if machine_type == "mra" else None,
        "mra_car_bracket_width_right": mra_car_bracket_right if machine_type == "mra" else None,
        "mra_cw_bracket_depth": mra_cw_bracket,
        "shaft_width_override": shaft_width_override,
        "shaft_depth_override": shaft_depth_override,
        "door_opening_type": door_opening_type,
        "telescopic_left_ext": telescopic_left_ext,
        "telescopic_right_ext": telescopic_right_ext,
        "has_errors": has_errors,
    }


def build_lift_config(
    lift_data: dict,
    machine_type: str,
    wall_thickness: float,
) -> LiftConfig:
    """Build a LiftConfig object from form data."""
    kwargs = {
        "lift_type": lift_data["type"],
        "lift_capacity": lift_data["capacity"],
        "lift_machine_type": machine_type,
        "finished_car_width": lift_data["width"],
        "finished_car_depth": lift_data["depth"],
        "door_width": lift_data["door_width"],
        "door_height": lift_data["door_height"],
        "door_panel_thickness": lift_data["door_panel_thickness"],
        "door_extension": lift_data["door_extension"],
        "structural_opening_width": lift_data["structural_opening_width"],
        "structural_opening_height": lift_data["structural_opening_height"],
        "wall_thickness": wall_thickness,
    }

    if machine_type == "mrl":
        if lift_data.get("cw_bracket_width") is not None:
            kwargs["counterweight_bracket_width"] = lift_data["cw_bracket_width"]
        if lift_data.get("car_bracket_width") is not None:
            kwargs["car_bracket_width"] = lift_data["car_bracket_width"]
    else:  # MRA
        if lift_data.get("mra_car_bracket_width") is not None:
            kwargs["mra_car_bracket_width"] = lift_data["mra_car_bracket_width"]
        if lift_data.get("mra_car_bracket_width_right") is not None:
            kwargs["mra_car_bracket_width_right"] = lift_data["mra_car_bracket_width_right"]
        if lift_data.get("mra_cw_bracket_depth") is not None:
            kwargs["mra_cw_bracket_depth"] = lift_data["mra_cw_bracket_depth"]

    # Pass shaft dimension overrides (for both MRL and MRA)
    if lift_data.get("shaft_width_override") is not None:
        kwargs["shaft_width_override"] = lift_data["shaft_width_override"]
    if lift_data.get("shaft_depth_override") is not None:
        kwargs["shaft_depth_override"] = lift_data["shaft_depth_override"]

    # Pass telescopic door parameters
    if lift_data.get("door_opening_type"):
        kwargs["door_opening_type"] = lift_data["door_opening_type"]
    if lift_data.get("telescopic_left_ext") is not None:
        kwargs["telescopic_left_ext"] = lift_data["telescopic_left_ext"]
    if lift_data.get("telescopic_right_ext") is not None:
        kwargs["telescopic_right_ext"] = lift_data["telescopic_right_ext"]

    return LiftConfig(**kwargs)


def render_section_config_form(machine_type: str) -> dict:
    """
    Render configuration form for section view.

    Returns dict with section-specific configuration values.
    """
    key_prefix = "section"

    # Shaft / wall dimensions
    col_sw, col_wt = st.columns(2)
    with col_sw:
        shaft_width = st.number_input(
            "Shaft Width (mm)",
            min_value=500, max_value=6000,
            value=int(config.DEFAULT_SHAFT_WIDTH),
            step=10, key=f"{key_prefix}_shaft_width",
            help="Internal shaft width (shown as 'Shaft Depth' in section view)"
        )
    with col_wt:
        wall_thickness = st.number_input(
            "Wall Thickness (mm)",
            min_value=100, max_value=500,
            value=int(config.DEFAULT_WALL_THICKNESS),
            step=25, key=f"{key_prefix}_wall_thickness",
            help="RCC wall / pit slab thickness"
        )

    # Pit slab and pit depth
    col_ps, col_pit = st.columns(2)
    with col_ps:
        pit_slab = st.number_input(
            "Pit Slab (mm)",
            min_value=100, max_value=500,
            value=int(config.DEFAULT_PIT_SLAB),
            step=25, key=f"{key_prefix}_pit_slab",
            help="Thickness of the concrete slab at pit bottom"
        )
    with col_pit:
        pit_depth = st.number_input(
            "Pit Depth (mm)",
            min_value=500, max_value=3000,
            value=int(config.DEFAULT_PIT_DEPTH),
            step=50, key=f"{key_prefix}_pit_depth",
            help="Depth from lowest landing to pit floor"
        )

    # Travel height and headroom
    col_travel, col_oh = st.columns(2)
    with col_travel:
        travel_height = st.number_input(
            "Travel Height (mm)",
            min_value=5000, max_value=200000,
            value=int(config.DEFAULT_TRAVEL_HEIGHT),
            step=1000, key=f"{key_prefix}_travel_height",
        )
    with col_oh:
        overhead_clearance = st.number_input(
            "Headroom (mm)",
            min_value=2000, max_value=10000,
            value=int(config.DEFAULT_OVERHEAD_CLEARANCE),
            step=100, key=f"{key_prefix}_overhead_clearance",
        )

    # Door opening height and structural opening height
    col_dh, col_soh = st.columns(2)
    with col_dh:
        door_height = st.number_input(
            "Door Opening Height (mm)",
            min_value=1500, max_value=3500,
            value=int(config.DEFAULT_DOOR_HEIGHT),
            step=50, key=f"{key_prefix}_door_height",
        )
    with col_soh:
        structural_opening_height = st.number_input(
            "Structural Opening Height (mm)",
            min_value=1500, max_value=4000,
            value=int(config.DEFAULT_STRUCTURAL_OPENING_HEIGHT),
            step=50, key=f"{key_prefix}_structural_opening_height",
        )

    # Machine Room Height (MRA only)
    machine_room_height = None
    if machine_type == "mra":
        col_mrh, _ = st.columns(2)
        with col_mrh:
            machine_room_height = st.number_input(
                "Machine Room Height (mm)",
                min_value=2000, max_value=6000,
                value=int(config.DEFAULT_MACHINE_ROOM_HEIGHT),
                step=100, key=f"{key_prefix}_machine_room_height",
            )

    return {
        "shaft_width": shaft_width,
        "wall_thickness": wall_thickness,
        "pit_slab": pit_slab,
        "pit_depth": pit_depth,
        "travel_height": travel_height,
        "overhead_clearance": overhead_clearance,
        "door_height": door_height,
        "structural_opening_height": structural_opening_height,
        "machine_room_height": machine_room_height,
    }


def main():
    st.set_page_config(
        page_title="Lift Sketch Generator",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Lift Sketch Generator")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")

        # View selector
        active_view = st.radio(
            "View",
            options=["Plan View", "Section View"],
            index=0,
            key="active_view",
        )

        st.divider()

        # Machine type (shared by both views)
        machine_type = st.radio(
            "Machine Type",
            options=["mrl", "mra"],
            index=0,
            format_func=lambda x: "MRL (Machine Room Less)" if x == "mrl" else "MRA (Machine Room Above)",
            key="machine_type",
        )

        if active_view == "Plan View":
            st.divider()

            # Plan view settings
            arrangement = st.radio(
                "Arrangement",
                options=["Inline", "Facing"],
                index=0,
                key="arrangement",
            )

            num_lifts_bank1 = st.number_input(
                "Number of Lifts (Bank 1)",
                min_value=1,
                max_value=4,
                value=1,
                key="num_lifts_bank1",
            )

            num_lifts_bank2 = 0
            if arrangement == "Facing":
                num_lifts_bank2 = st.number_input(
                    "Number of Lifts (Bank 2)",
                    min_value=1,
                    max_value=4,
                    value=2,
                    key="num_lifts_bank2",
                )

            st.divider()
            st.subheader("Display Options")
            show_dimensions = st.checkbox("Show Dimensions", value=True, key="show_dimensions")
            show_hatching = st.checkbox("Show Hatching", value=True, key="show_hatching")
            show_centerlines = st.checkbox("Show Centerlines", value=False, key="show_centerlines")
            show_capacity = st.checkbox("Show Capacity Label", value=False, key="show_capacity")
            show_accessibility = st.checkbox("Show Accessibility Symbol", value=False, key="show_accessibility")
            show_brackets = st.checkbox("Show Brackets", value=True, key="show_brackets")
            show_lift_doors = st.checkbox("Show Lift Doors", value=True, key="show_lift_doors")

        else:
            st.divider()
            st.subheader("Display Options")
            section_show_dimensions = st.checkbox("Show Dimensions", value=True, key="section_show_dimensions")
            section_show_hatching = st.checkbox("Show Hatching", value=True, key="section_show_hatching")
            section_show_break_lines = st.checkbox("Show Break Lines", value=True, key="section_show_break_lines")
            section_show_machine = st.checkbox("Show Machine Image", value=True, key="section_show_machine")

    # ── Plan View ──
    if active_view == "Plan View":
        col_config, col_preview = st.columns([1, 1])

        with col_config:
            st.header("Lift Configuration")

            # Bank 1 lift configurations
            st.subheader("Bank 1")
            bank1_lifts = []
            for i in range(num_lifts_bank1):
                lift_data = render_lift_config_form(i, "bank1", machine_type, show_capacity_input=show_capacity)
                bank1_lifts.append(lift_data)

            # Bank 2 configurations (if facing)
            bank2_lifts = []
            if arrangement == "Facing":
                st.subheader("Bank 2")
                for i in range(num_lifts_bank2):
                    lift_data = render_lift_config_form(i, "bank2", machine_type, show_capacity_input=show_capacity)
                    bank2_lifts.append(lift_data)

            st.divider()

            # Shaft configuration
            st.subheader("Shaft Configuration")

            col_shaft1, col_shaft2 = st.columns(2)
            with col_shaft1:
                wall_thickness = st.number_input(
                    "Wall Thickness (mm)",
                    min_value=100,
                    max_value=500,
                    value=int(config.DEFAULT_WALL_THICKNESS),
                    step=25,
                    key="wall_thickness",
                )

            with col_shaft2:
                common_shaft = st.checkbox(
                    "Common Shaft",
                    value=False,
                    key="common_shaft",
                    help="If checked, uses steel beam separator (150mm). Otherwise uses RCC wall (200mm).",
                )

            if arrangement == "Facing":
                lobby_width = st.number_input(
                    "Lobby Width (mm)",
                    min_value=2000,
                    max_value=10000,
                    value=int(config.DEFAULT_LOBBY_WIDTH),
                    step=100,
                    key="lobby_width",
                )
            else:
                lobby_width = config.DEFAULT_LOBBY_WIDTH

        # Preview column
        with col_preview:
            st.header("Preview")

            generate_btn = st.button("Generate Sketch", type="primary", width="stretch", key="plan_generate")

            # Check if any lift has dimension errors
            all_lifts = bank1_lifts + bank2_lifts
            any_errors = any(ld.get("has_errors") for ld in all_lifts)

            if generate_btn and any_errors:
                st.error("Fix dimension errors before generating.")
            elif generate_btn:
                try:
                    # Build LiftConfig objects for Bank 1
                    lift_configs = []
                    for lift_data in bank1_lifts:
                        lc = build_lift_config(lift_data, machine_type, wall_thickness)
                        lift_configs.append(lc)

                    # Build LiftConfig objects for Bank 2 (if facing)
                    lift_configs_bank2 = None
                    if arrangement == "Facing" and bank2_lifts:
                        lift_configs_bank2 = []
                        for lift_data in bank2_lifts:
                            lc = build_lift_config(lift_data, machine_type, wall_thickness)
                            lift_configs_bank2.append(lc)

                    # Create sketch
                    sketch = LiftShaftSketch(
                        lifts=lift_configs,
                        lifts_bank2=lift_configs_bank2,
                        lobby_width=lobby_width if arrangement == "Facing" else None,
                        is_common_shaft=common_shaft,
                        wall_thickness=wall_thickness,
                    )

                    # Generate PNG bytes
                    img_bytes = sketch.to_bytes(
                        show_hatching=show_hatching,
                        show_dimensions=show_dimensions,
                        show_centerlines=show_centerlines,
                        show_car_interior=True,
                        show_brackets=show_brackets,
                        show_door_panels=True,
                        show_capacity=show_capacity,
                        show_accessibility=show_accessibility,
                        show_lift_doors=show_lift_doors,
                    )

                    # Store in session state
                    st.session_state["generated_image"] = img_bytes
                    st.session_state["generation_error"] = None

                except ValueError as e:
                    st.session_state["generation_error"] = str(e)
                    st.session_state["generated_image"] = None
                except Exception as e:
                    st.session_state["generation_error"] = f"Unexpected error: {str(e)}"
                    st.session_state["generated_image"] = None

            # Display image or error
            if st.session_state.get("generation_error"):
                st.error(st.session_state["generation_error"])

            if st.session_state.get("generated_image"):
                st.image(st.session_state["generated_image"], width="stretch")

                # Download button
                st.download_button(
                    label="Download PNG",
                    data=st.session_state["generated_image"],
                    file_name="lift_plan.png",
                    mime="image/png",
                    width="stretch",
                )

    # ── Section View ──
    else:
        col_section_config, col_section_preview = st.columns([1, 1])

        with col_section_config:
            st.header("Section Configuration")
            section_form = render_section_config_form(machine_type)

        with col_section_preview:
            st.header("Preview")

            section_generate_btn = st.button(
                "Generate Section", type="primary", width="stretch", key="section_generate"
            )

            if section_generate_btn:
                try:
                    # Build LiftConfig for section view
                    section_lift_config = LiftConfig(
                        lift_machine_type=machine_type,
                        wall_thickness=section_form["wall_thickness"],
                        door_height=section_form["door_height"],
                        structural_opening_height=section_form["structural_opening_height"],
                        shaft_width_override=section_form["shaft_width"],
                    )

                    # Build SectionConfig
                    section_kwargs = {
                        "pit_slab": section_form["pit_slab"],
                        "pit_depth": section_form["pit_depth"],
                        "overhead_clearance": section_form["overhead_clearance"],
                        "travel_height": section_form["travel_height"],
                    }
                    if machine_type == "mra" and section_form["machine_room_height"] is not None:
                        section_kwargs["machine_room_height"] = section_form["machine_room_height"]

                    section_cfg = SectionConfig(**section_kwargs)

                    # Create section sketch
                    section_sketch = LiftSectionSketch(
                        lift_config=section_lift_config,
                        section_config=section_cfg,
                    )

                    # Generate PNG bytes
                    section_img_bytes = section_sketch.to_bytes(
                        show_hatching=section_show_hatching,
                        show_dimensions=section_show_dimensions,
                        show_break_lines=section_show_break_lines,
                        show_mrl_machine=section_show_machine,
                    )

                    st.session_state["section_generated_image"] = section_img_bytes
                    st.session_state["section_generation_error"] = None

                except ValueError as e:
                    st.session_state["section_generation_error"] = str(e)
                    st.session_state["section_generated_image"] = None
                except Exception as e:
                    st.session_state["section_generation_error"] = f"Unexpected error: {str(e)}"
                    st.session_state["section_generated_image"] = None

            # Display section image or error
            if st.session_state.get("section_generation_error"):
                st.error(st.session_state["section_generation_error"])

            if st.session_state.get("section_generated_image"):
                st.image(st.session_state["section_generated_image"], width="stretch")

                st.download_button(
                    label="Download PNG",
                    data=st.session_state["section_generated_image"],
                    file_name="lift_section.png",
                    mime="image/png",
                    width="stretch",
                )


if __name__ == "__main__":
    main()
