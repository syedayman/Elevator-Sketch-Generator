"""
Streamlit web app for generating lift shaft plan sketches.
"""

import streamlit as st
from shaft_sketch import LiftShaftSketch, LiftConfig, FIRE_LIFT_CABIN_SIZES
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
        }
    return {
        "type": "passenger",
        "capacity": config.DEFAULT_LIFT_CAPACITY,
        "width": config.DEFAULT_FINISHED_CAR_WIDTH,
        "depth": config.DEFAULT_FINISHED_CAR_DEPTH,
        "door_width": config.DEFAULT_DOOR_WIDTH,
        "door_panel_thickness": config.DEFAULT_LIFT_DOOR_THICKNESS,
        "door_extension": config.DEFAULT_DOOR_EXTENSION,
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

        # Copy from Lift 1 button (for lifts 2+)
        if lift_index > 0:
            copy_key = f"{key_prefix}_copy_from_lift1"
            if st.button("Copy from Lift 1", key=copy_key, help="Copy all settings from Lift 1"):
                # Get Lift 1's values from session state
                lift1_prefix = f"{bank_name}_lift_0"
                # Copy will be handled via session_state in next rerun
                st.session_state[f"{key_prefix}_copy_pending"] = True
                st.rerun()

        # Handle pending copy
        if st.session_state.get(f"{key_prefix}_copy_pending"):
            lift1_prefix = f"{bank_name}_lift_0"
            # Copy relevant session state keys
            keys_to_copy = ["_capacity", "_width", "_depth", "_door_width",
                            "_door_panel_length", "_door_panel_thickness",
                            "_cw_bracket", "_car_bracket", "_mra_car_bracket", "_mra_cw_bracket",
                            "_shaft_depth"]
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
            index=0 if initial_values.get("type", "passenger") == "passenger" else 1,
            key=f"{key_prefix}_type",
            help="Fire lift only allowed at position 1 (first lift)",
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
            # Fire lift: dropdown for fixed cabin sizes
            cabin_options = list(FIRE_CABIN_OPTIONS.keys())
            default_size = f"{initial_values.get('width', 1400)} x {initial_values.get('depth', 2400)} mm"
            if default_size not in cabin_options:
                default_size = cabin_options[0]

            cabin_size = st.selectbox(
                "Cabin Size (Width x Depth)",
                options=cabin_options,
                index=cabin_options.index(default_size),
                key=f"{key_prefix}_cabin_size",
                help="Fire lifts have fixed cabin sizes",
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
                    step=50,
                    key=f"{key_prefix}_width",
                )
            with col2:
                car_depth = st.number_input(
                    "Finished Car Depth (mm) *",
                    min_value=800,
                    max_value=3000,
                    value=int(initial_values.get("depth", config.DEFAULT_FINISHED_CAR_DEPTH)),
                    step=50,
                    key=f"{key_prefix}_depth",
                )

        # Bracket Configuration (per-lift)
        st.divider()
        st.markdown("**Bracket Spaces**")

        if machine_type == "mrl":
            col_br1, col_br2 = st.columns(2)
            with col_br1:
                cw_bracket = st.number_input(
                    "CW Bracket Space Width (mm)",
                    min_value=int(config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH), max_value=1000,
                    value=int(initial_values.get("cw_bracket_width", config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH)),
                    step=25, key=f"{key_prefix}_cw_bracket",
                    help=f"Space for counterweight (min {config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH}mm)"
                )
            with col_br2:
                car_bracket = st.number_input(
                    "Car Bracket Space Width (mm)",
                    min_value=int(config.DEFAULT_CAR_BRACKET_WIDTH), max_value=800,
                    value=int(initial_values.get("car_bracket_width", config.DEFAULT_CAR_BRACKET_WIDTH)),
                    step=25, key=f"{key_prefix}_car_bracket",
                    help=f"Space for car guide rails (min {config.DEFAULT_CAR_BRACKET_WIDTH}mm)"
                )
            mra_car_bracket = None
            mra_cw_bracket = None
            # Calculate shaft width for validation
            unfinished_car_width = car_width + 2 * config.DEFAULT_CAR_WALL_THICKNESS
            shaft_width = cw_bracket + unfinished_car_width + car_bracket
        else:  # MRA
            col_br1, col_br2 = st.columns(2)
            with col_br1:
                mra_car_bracket = st.number_input(
                    "Car Bracket Space Width (mm)",
                    min_value=int(config.MRA_CAR_BRACKET_WIDTH), max_value=800,
                    value=int(initial_values.get("mra_car_bracket_width", config.MRA_CAR_BRACKET_WIDTH)),
                    step=25, key=f"{key_prefix}_mra_car_bracket",
                    help=f"Space for car brackets (min {config.MRA_CAR_BRACKET_WIDTH}mm)"
                )
            with col_br2:
                mra_cw_bracket = st.number_input(
                    "CW Bracket Space Depth (mm)",
                    min_value=int(config.MRA_CW_BRACKET_DEPTH), max_value=800,
                    value=int(initial_values.get("mra_cw_bracket_depth", config.MRA_CW_BRACKET_DEPTH)),
                    step=25, key=f"{key_prefix}_mra_cw_bracket",
                    help=f"Space for counterweight (min {config.MRA_CW_BRACKET_DEPTH}mm)"
                )
            cw_bracket = None
            car_bracket = None
            # Calculate shaft width for validation
            unfinished_car_width = car_width + 2 * config.DEFAULT_CAR_WALL_THICKNESS
            shaft_width = unfinished_car_width + 2 * mra_car_bracket

        # Apply fire lift minimum width if applicable
        if lift_type == "fire":
            shaft_width = max(shaft_width, config.FIRE_LIFT_MIN_SHAFT_WIDTH)

        # Door Settings (after brackets so we can validate against shaft width)
        with st.expander("Door Settings", expanded=False):
            if lift_type == "fire":
                st.info(f"Fire lift door width is fixed at {config.FIRE_LIFT_DOOR_WIDTH}mm")
                door_width = config.FIRE_LIFT_DOOR_WIDTH
            else:
                door_width = st.number_input(
                    "Door Width (mm)",
                    min_value=700,
                    max_value=2000,
                    value=int(initial_values.get("door_width", config.DEFAULT_DOOR_WIDTH)),
                    step=50,
                    key=f"{key_prefix}_door_width",
                    help="Width of the door opening (bold inner part)"
                )

            # Calculate panel length constraints with proper validation
            min_panel_length = 2 * door_width  # At minimum, must fit the doors
            default_panel_length = min(2 * door_width + 2 * config.DEFAULT_DOOR_EXTENSION, shaft_width)
            max_panel_length = int(shaft_width)  # Cannot exceed shaft inner width

            door_panel_length = st.number_input(
                "Door Panel Length (mm)",
                min_value=int(min_panel_length),
                max_value=max_panel_length,
                value=int(min(initial_values.get("door_panel_length", default_panel_length), max_panel_length)),
                step=50,
                key=f"{key_prefix}_door_panel_length",
                help=f"Total width of door panel rectangle. Max: {max_panel_length}mm (shaft width)"
            )

            door_panel_thickness = st.number_input(
                "Door Panel Thickness (mm)",
                min_value=50,
                max_value=300,
                value=int(initial_values.get("door_panel_thickness", config.DEFAULT_LIFT_DOOR_THICKNESS)),
                step=10,
                key=f"{key_prefix}_door_panel_thickness",
                help="Depth of each door panel. Affects shaft depth calculation."
            )

            # Calculate extension from panel length
            door_extension = (door_panel_length - 2 * door_width) / 2

        # Shaft depth override (MRL only, after door_panel_thickness is set)
        if machine_type == "mrl":
            # Calculate min shaft depth for MRL
            temp_for_min = LiftConfig(
                lift_type=lift_type,
                finished_car_width=car_width,
                finished_car_depth=car_depth,
                lift_machine_type=machine_type,
                counterweight_bracket_width=cw_bracket,
                car_bracket_width=car_bracket,
                door_panel_thickness=door_panel_thickness,
            )
            min_shaft_depth = int(temp_for_min.min_shaft_depth)

            shaft_depth_override = st.number_input(
                "Shaft Depth (mm)",
                min_value=min_shaft_depth, max_value=5000,
                value=int(initial_values.get("shaft_depth_override", min_shaft_depth)),
                step=25, key=f"{key_prefix}_shaft_depth",
                help=f"Shaft depth (min {min_shaft_depth}mm based on car and door thickness)"
            )
            # Only set override if different from minimum
            if shaft_depth_override == min_shaft_depth:
                shaft_depth_override = None
        else:
            shaft_depth_override = None

        # Show calculated shaft dimensions (read-only info)
        temp_kwargs = {
            "lift_type": lift_type,
            "finished_car_width": car_width,
            "finished_car_depth": car_depth,
            "lift_machine_type": machine_type,
            "door_panel_thickness": door_panel_thickness,
        }
        if machine_type == "mrl":
            temp_kwargs["counterweight_bracket_width"] = cw_bracket
            temp_kwargs["car_bracket_width"] = car_bracket
            temp_kwargs["shaft_depth_override"] = shaft_depth_override
        else:
            temp_kwargs["mra_car_bracket_width"] = mra_car_bracket
            temp_kwargs["mra_cw_bracket_depth"] = mra_cw_bracket

        temp_lift = LiftConfig(**temp_kwargs)
        st.info(f"Shaft: {int(temp_lift.shaft_width)}mm W x {int(temp_lift.effective_shaft_depth)}mm D")

    return {
        "type": lift_type,
        "capacity": capacity,
        "width": car_width,
        "depth": car_depth,
        "door_width": door_width,
        "door_panel_thickness": door_panel_thickness,
        "door_extension": door_extension,
        "cw_bracket_width": cw_bracket,
        "car_bracket_width": car_bracket,
        "mra_car_bracket_width": mra_car_bracket,
        "mra_cw_bracket_depth": mra_cw_bracket,
        "shaft_depth_override": shaft_depth_override,
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
        "door_panel_thickness": lift_data["door_panel_thickness"],
        "door_extension": lift_data["door_extension"],
        "wall_thickness": wall_thickness,
    }

    if machine_type == "mrl":
        if lift_data.get("cw_bracket_width") is not None:
            kwargs["counterweight_bracket_width"] = lift_data["cw_bracket_width"]
        if lift_data.get("car_bracket_width") is not None:
            kwargs["car_bracket_width"] = lift_data["car_bracket_width"]
        if lift_data.get("shaft_depth_override") is not None:
            kwargs["shaft_depth_override"] = lift_data["shaft_depth_override"]
    else:  # MRA
        if lift_data.get("mra_car_bracket_width") is not None:
            kwargs["mra_car_bracket_width"] = lift_data["mra_car_bracket_width"]
        if lift_data.get("mra_cw_bracket_depth") is not None:
            kwargs["mra_cw_bracket_depth"] = lift_data["mra_cw_bracket_depth"]

    return LiftConfig(**kwargs)


def main():
    st.set_page_config(
        page_title="Lift Plan Sketch Generator",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Lift Plan Sketch Generator")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")

        # Machine type
        machine_type = st.radio(
            "Machine Type",
            options=["mrl", "mra"],
            index=0,
            format_func=lambda x: "MRL (Machine Room Less)" if x == "mrl" else "MRA (Machine Room Above)",
            key="machine_type",
        )

        # Arrangement
        arrangement = st.radio(
            "Arrangement",
            options=["Inline", "Facing"],
            index=0,
            key="arrangement",
        )

        st.divider()

        # Number of lifts
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

    # Main area - lift configuration forms
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

        generate_btn = st.button("Generate Sketch", type="primary", use_container_width=True)

        if generate_btn:
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
            st.image(st.session_state["generated_image"], use_container_width=True)

            # Download button
            st.download_button(
                label="Download PNG",
                data=st.session_state["generated_image"],
                file_name="lift_plan.png",
                mime="image/png",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
