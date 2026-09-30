"""
Lift shaft section sketch generator class.

Generates cross-sectional views of lift shafts (viewing from door/landing side).
Complements the plan sketch (top-down view) in shaft_sketch.py.
"""

import io
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for PNG generation
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

# Support both package (relative) and standalone (absolute) imports
try:
    from . import config
    from .shaft_sketch import LiftConfig
    from .drawing_utils import (
        draw_wall_section,
        draw_dimension_line,
        draw_section_pit,
        draw_break_lines,
        draw_section_landing,
        draw_floor_slab_protrusion,
        draw_machine_image,
        add_image_border,
        scaled_dimension_font,
        composite_brief_spec_table,
        brief_spec_row,
    )
except ImportError:
    import config
    from shaft_sketch import LiftConfig
    from drawing_utils import (
        draw_wall_section,
        draw_dimension_line,
        draw_section_pit,
        draw_break_lines,
        draw_section_landing,
        draw_floor_slab_protrusion,
        draw_machine_image,
        add_image_border,
        scaled_dimension_font,
        composite_brief_spec_table,
        brief_spec_row,
    )


@dataclass
class SectionConfig:
    """Configuration for section view parameters."""

    pit_slab: float = field(default_factory=lambda: config.DEFAULT_PIT_SLAB)
    pit_depth: float = field(default_factory=lambda: config.DEFAULT_PIT_DEPTH)
    overhead_clearance: float = field(default_factory=lambda: config.DEFAULT_OVERHEAD_CLEARANCE)
    travel_height: float = field(default_factory=lambda: config.DEFAULT_TRAVEL_HEIGHT)
    floor_height: float = field(default_factory=lambda: config.DEFAULT_FLOOR_HEIGHT)
    car_interior_height: float = field(default_factory=lambda: config.DEFAULT_CAR_INTERIOR_HEIGHT)

    # Door dimensions in section view
    door_height: float = field(default_factory=lambda: config.DEFAULT_DOOR_HEIGHT)
    structural_opening_height: float = field(default_factory=lambda: config.DEFAULT_STRUCTURAL_OPENING_HEIGHT)

    # MRA (Machine Room Above) parameters
    machine_room_height: float = field(default_factory=lambda: config.DEFAULT_MACHINE_ROOM_HEIGHT)

    # Landing labels. Blank keeps the generic wording. top_floor_number N names
    # the top two landings Floor N / Floor N-1; lowest_floor_name names the
    # bottom landing, and the landing above it follows (see floor_above).
    top_floor_number: Optional[int] = None
    lowest_floor_name: str = ""
    # Shown under the Travel dimension. Blank → travel / (floors - 1) from the
    # named top and lowest floors (see floor_level).
    average_floor_height: Optional[float] = None

    @property
    def total_shaft_height(self) -> float:
        """Total height from pit bottom to overhead top."""
        return self.pit_slab + self.pit_depth + self.travel_height + self.overhead_clearance

    @property
    def num_floors(self) -> int:
        """Approximate number of floors based on travel height."""
        return max(2, int(self.travel_height / self.floor_height) + 1)


_INTEGER_FLOOR = re.compile(r"-?\d+")
_BASEMENT_FLOOR = re.compile(r"(b(?:asement)?)([ -]?)(\d*)", re.IGNORECASE)
_NUMBERED_FLOOR = re.compile(r"(.*?)(\d+)")
_GROUND_FLOOR = re.compile(r"g|gf|ug|ground(?: floor)?", re.IGNORECASE)


def floor_level(name: str) -> Optional[int]:
    """Level of a named floor counted from ground (G = 0, B2 = -2, 7 = 7), or
    None when the name can't be placed relative to ground (e.g. P1, M)."""
    name = name.strip()
    if _INTEGER_FLOOR.fullmatch(name):
        return int(name)
    basement = _BASEMENT_FLOOR.fullmatch(name)
    if basement:
        digits = basement.group(3)
        return -(int(digits) if digits else 1)
    if name.upper() in ("LG", "LOWER GROUND"):
        return -1
    if _GROUND_FLOOR.fullmatch(name):
        return 0
    return None


def floor_above(name: str) -> str:
    """Name of the landing directly above the landing called `name`.

    Basements count up towards ground (B2 -> B1, B / B1 -> G), lower ground
    sits below ground (LG -> G), other numbered floors count up (5 -> 6,
    P1 -> P2), and any other name is followed by Floor 1 (G -> 1).
    """
    name = name.strip()
    if _INTEGER_FLOOR.fullmatch(name):
        return str(int(name) + 1)
    basement = _BASEMENT_FLOOR.fullmatch(name)
    if basement:
        prefix, separator, digits = basement.groups()
        level = int(digits) if digits else 1
        if level <= 1:
            return "G"
        return f"{prefix}{separator}{str(level - 1).zfill(len(digits))}"
    if name.upper() in ("LG", "LOWER GROUND"):
        return "G"
    numbered = _NUMBERED_FLOOR.fullmatch(name)
    if numbered:
        prefix, digits = numbered.groups()
        return f"{prefix}{str(int(digits) + 1).zfill(len(digits))}"
    return "1"


def _floor_label(name: str) -> str:
    """Landing label for a named floor, e.g. "Floor B2 F.F.L.".

    Lines wrap at the width of the generic "Floor n-1 F.F.L." so long names
    stay clear of the vertical dimensions on their left.
    """
    return textwrap.fill(f"Floor {name} F.F.L.", width=16)


class LiftSectionSketch:
    """
    Generator for lift shaft section diagrams.

    Produces cross-sectional views showing:
    - Full shaft height with break lines hiding repetitive middle floors
    - Ground floor and top floor details
    - Machine unit at top (MRL configuration)
    - Pit area at bottom
    - Guide rails, car outline, door openings
    - Dimension annotations
    """

    def __init__(
        self,
        # Simple API (backward compatible with plan sketch dimensions)
        shaft_depth: float = None,
        wall_thickness: float = None,
        door_width: float = None,
        # Enhanced API
        lift_config: LiftConfig = None,
        section_config: SectionConfig = None,
    ):
        """
        Initialize lift section sketch generator.

        Args:
            shaft_depth: Shaft depth (horizontal dimension in section view, mm)
            wall_thickness: RCC wall thickness (mm)
            door_width: Door opening width (mm)
            lift_config: LiftConfig from plan sketch (for dimensional consistency)
            section_config: Section-specific configuration (heights, pit depth, etc.)
        """
        self.lift_config = lift_config
        self.section_config = section_config or SectionConfig()

        # Determine dimensions from lift_config or defaults
        if lift_config is not None:
            self.shaft_depth = lift_config.effective_shaft_depth
            self.wall_thickness = lift_config.wall_thickness
            self.door_width = lift_config.door_width
            self.door_height = lift_config.door_height
            self.structural_opening_width = lift_config.structural_opening_width
            self.structural_opening_height = lift_config.structural_opening_height
            self.finished_car_width = lift_config.finished_car_width
            self.finished_car_depth = lift_config.finished_car_depth
            self.unfinished_car_width = lift_config.unfinished_car_width
            self.unfinished_car_depth = lift_config.unfinished_car_depth
            self.machine_type = lift_config.lift_machine_type
        else:
            self.shaft_depth = shaft_depth or config.DEFAULT_SHAFT_DEPTH
            self.wall_thickness = wall_thickness or config.DEFAULT_WALL_THICKNESS
            self.door_width = door_width or config.DEFAULT_DOOR_WIDTH
            self.door_height = config.DEFAULT_DOOR_HEIGHT
            self.structural_opening_width = config.DEFAULT_STRUCTURAL_OPENING_WIDTH
            self.structural_opening_height = config.DEFAULT_STRUCTURAL_OPENING_HEIGHT
            self.finished_car_width = config.DEFAULT_FINISHED_CAR_WIDTH
            self.finished_car_depth = config.DEFAULT_FINISHED_CAR_DEPTH
            self.unfinished_car_width = config.DEFAULT_FINISHED_CAR_WIDTH + 2 * config.DEFAULT_CAR_WALL_THICKNESS
            self.unfinished_car_depth = config.DEFAULT_FINISHED_CAR_DEPTH + config.DEFAULT_CAR_WALL_THICKNESS
            self.machine_type = "mrl"

        # Override door/structural heights from section config
        self.door_height = self.section_config.door_height
        self.structural_opening_height = self.section_config.structural_opening_height

        # Section-specific parameters
        self.pit_slab = self.section_config.pit_slab
        self.pit_depth = self.section_config.pit_depth
        self.overhead_clearance = self.section_config.overhead_clearance
        self.travel_height = self.section_config.travel_height
        self.floor_height = self.section_config.floor_height
        self.car_interior_height = self.section_config.car_interior_height
        top_floor = self.section_config.top_floor_number
        self.top_floor_number = None if top_floor is None else int(top_floor)
        self.lowest_floor_name = (self.section_config.lowest_floor_name or "").strip()
        self.average_floor_height = self.section_config.average_floor_height

        # Calculate geometry
        self._calculate_geometry()

    def _calculate_geometry(self) -> None:
        """Calculate section geometry based on parameters."""
        # Total width including walls
        self.total_width = self.shaft_depth + 2 * self.wall_thickness

        # Add a small display-only gap so the wall between adjacent visible
        # landing openings does not look cramped in the compressed section.
        self.display_floor_height = self.floor_height + 500

        # Vertical geometry
        # Ground floor level is at y=0 in the drawing (top of pit slab)
        self.ground_floor_y = 0
        self.pit_bottom_y = -self.pit_slab
        self.top_floor_y = self.travel_height
        self.overhead_top_y = self.top_floor_y + self.overhead_clearance

        # For the simplified section view with break lines, the lower zone shows
        # both the bottom-most landing and a complete Floor 1 landing. Leave a
        # clear gap above the Floor 1 opening before the break symbol.
        floor_1_opening_top = (
            self.pit_depth
            + self.display_floor_height
            + self.structural_opening_height
        )
        self.ground_zone_height = max(4000, floor_1_opening_top + 500)
        # The upper zone shows Floor n-1 above the break and the Top Floor one
        # configured floor height above it.
        self.top_landing_gap_above_break = 800
        self.top_zone_height = (
            self.top_landing_gap_above_break
            + self.display_floor_height
            + self.overhead_clearance
        )
        self.break_zone_height = 1500  # Height for break line area

        # Total drawing height (simplified)
        self.drawing_height = (
            self.pit_slab +
            self.ground_zone_height +
            self.break_zone_height +
            self.top_zone_height
        )

        # For MRA, add machine room height to total
        if self.machine_type == "mra":
            self.machine_room_height = self.section_config.machine_room_height
            self.drawing_height += self.machine_room_height
        else:
            self.machine_room_height = 0

    def generate(
        self,
        output_path: str,
        show_hatching: bool = True,
        show_dimensions: bool = True,
        show_pit: bool = True,
        show_break_lines: bool = True,
        show_mrl_machine: bool = True,
        title: str = None,
        subtitle: Optional[str] = None,
        dpi: int = None,
        font_scale: float = 1.0,
    ) -> str:
        """
        Generate the section sketch and save to file.

        Args:
            output_path: Path to save PNG file
            show_hatching: Draw concrete hatch pattern on walls
            show_dimensions: Show dimension annotations
            show_pit: Show pit area at bottom
            show_break_lines: Show break lines for hidden floors
            show_mrl_machine: Show MRL machine image in overhead area
            title: Drawing title text
            subtitle: Subtitle/notes text
            dpi: Output image resolution

        Returns:
            Absolute path to the generated file
        """
        display_options = {
            "show_hatching": show_hatching,
            "show_dimensions": show_dimensions,
            "show_pit": show_pit,
            "show_break_lines": show_break_lines,
            "show_mrl_machine": show_mrl_machine,
        }

        fig, ax = self._create_figure()
        with scaled_dimension_font(font_scale):
            self._draw_section(ax, title, subtitle, display_options)

        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi or config.DEFAULT_DPI,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)

        output_path.write_bytes(add_image_border(buf.getvalue()))

        return str(output_path.absolute())

    def to_bytes(
        self,
        show_hatching: bool = True,
        show_dimensions: bool = True,
        show_pit: bool = True,
        show_break_lines: bool = True,
        show_mrl_machine: bool = True,
        show_brief_spec: bool = False,
        brief_spec_title: Optional[str] = None,
        brief_spec_rows: Optional[list] = None,
        title: str = None,
        subtitle: Optional[str] = None,
        dpi: int = None,
        font_scale: float = 1.0,
    ) -> bytes:
        """
        Return PNG as bytes (for API responses).

        `brief_spec_rows` overrides the default single-lift brief-spec body (used
        when one section represents several lifts sharing the same config).

        Args:
            show_hatching: Draw concrete hatch pattern on walls
            show_dimensions: Show dimension annotations
            show_pit: Show pit area at bottom
            show_break_lines: Show break lines for hidden floors
            show_mrl_machine: Show MRL machine image in overhead area
            title: Drawing title text
            subtitle: Subtitle/notes text
            dpi: Output image resolution

        Returns:
            PNG image as bytes
        """
        display_options = {
            "show_hatching": show_hatching,
            "show_dimensions": show_dimensions,
            "show_pit": show_pit,
            "show_break_lines": show_break_lines,
            "show_mrl_machine": show_mrl_machine,
            "show_brief_spec": show_brief_spec,
            "brief_spec_title": brief_spec_title,
        }

        fig, ax = self._create_figure()
        with scaled_dimension_font(font_scale):
            self._draw_section(ax, title, subtitle, display_options)

        # Save to bytes buffer
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi or config.DEFAULT_DPI,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)

        png = buf.getvalue()
        if show_brief_spec:
            rows = brief_spec_rows if brief_spec_rows is not None else self._brief_spec_rows()
            png = composite_brief_spec_table(png, rows, brief_spec_title)
        return add_image_border(png)

    def _create_figure(self) -> tuple:
        """Create matplotlib figure and axes for section view."""
        # Keep the default section's vertical drawing scale, but let sections
        # with more visible content grow taller instead of compressing every
        # floor and annotation into the same fixed-height canvas.
        reference_drawing_height = 18_000
        figure_height = config.SECTION_FIGURE_HEIGHT * max(
            1.0,
            self.drawing_height / reference_drawing_height,
        )
        fig, ax = plt.subplots(
            figsize=(config.SECTION_FIGURE_WIDTH, figure_height)
        )
        ax.set_aspect("equal")
        ax.axis("off")
        return fig, ax

    def _draw_section(
        self,
        ax: plt.Axes,
        title: str,
        subtitle: Optional[str],
        display_options: dict,
    ) -> None:
        """Draw the complete section sketch."""
        wt = self.wall_thickness
        sw = self.shaft_depth
        margin_x = 1500  # Horizontal margin for dimensions
        margin_bottom = 500  # Bottom margin for dimensions
        margin_top = 500  # Top margin

        # Calculate y positions for the simplified view
        ground_level = 0
        break_line_bottom = self.ground_zone_height
        break_line_top = break_line_bottom + self.break_zone_height
        floor_n_minus_1_level = (
            break_line_top + self.top_landing_gap_above_break
        )
        top_level = floor_n_minus_1_level + self.display_floor_height
        overhead_top = top_level + self.overhead_clearance

        # For MRA, calculate machine room top.
        if self.machine_type == "mra":
            machine_room_top = overhead_top + self.machine_room_height
        else:
            machine_room_top = overhead_top

        # Machine images intentionally retain the section renderer's original
        # full-width, automatic aspect. Compensate only horizontal structural
        # elements so a 200mm slab renders as thick as a 200mm vertical wall.
        render_scale_y = 1.0
        if display_options.get("show_mrl_machine", True):
            ax.set_aspect("auto")
            figure_width, figure_height = ax.figure.get_size_inches()
            axes_box = ax.get_position()
            x_span = self.total_width + 2 * margin_x
            axes_display_ratio = (
                axes_box.width * figure_width
                / (axes_box.height * figure_height)
            )
            fixed_y_span = machine_room_top + margin_top + margin_bottom
            render_scale_y = (
                axes_display_ratio * fixed_y_span
                / (x_span - axes_display_ratio * self.pit_slab)
            )

        slab_thickness = wt * render_scale_y
        pit_slab_thickness = self.pit_slab * render_scale_y
        pit_bottom = -pit_slab_thickness

        # Floor slab positions (needed for structural openings)
        ground_floor_slab_y = ground_level + self.pit_depth
        floor_1_level = ground_floor_slab_y + self.display_floor_height

        # Skip shaft interior background - keep it white

        # Draw pit area (pit slab is drawn as the bottom wall below)

        # Draw side walls (left and right)
        # Left wall - segmented around the four visible landing openings
        opening_height = self.structural_opening_height
        ground_opening_top = ground_floor_slab_y + opening_height
        floor_1_opening_top = floor_1_level + opening_height
        floor_n_minus_1_opening_top = floor_n_minus_1_level + opening_height
        top_opening_top = top_level + opening_height

        # Segment 1: From pit bottom to ground floor slab (below ground opening)
        draw_wall_section(
            ax, 0, pit_bottom, wt, ground_floor_slab_y - pit_bottom,
            display_options["show_hatching"]
        )

        # Segment 2: Between the bottom-most and Floor 1 openings
        draw_wall_section(
            ax, 0, ground_opening_top, wt, floor_1_level - ground_opening_top,
            display_options["show_hatching"]
        )

        # Segment 3: From above Floor 1 to Floor n-1 (spans break zone)
        draw_wall_section(
            ax, 0, floor_1_opening_top, wt,
            floor_n_minus_1_level - floor_1_opening_top,
            display_options["show_hatching"]
        )

        # Segment 4: Between the Floor n-1 and Top Floor openings
        draw_wall_section(
            ax, 0, floor_n_minus_1_opening_top, wt,
            top_level - floor_n_minus_1_opening_top,
            display_options["show_hatching"]
        )

        # Segment 5: From above the Top Floor opening to overhead top
        draw_wall_section(
            ax, 0, top_opening_top, wt, overhead_top - top_opening_top,
            display_options["show_hatching"]
        )

        # Landing doors - thin rectangles at each floor opening
        door_rect_width = 50  # Thin rectangle width
        door_rect_extend = 100  # How much it extends beyond the opening
        door_rect_height = opening_height + door_rect_extend * 2  # Slightly taller than opening

        # Ground floor landing door
        ax.add_patch(Rectangle(
            (wt, ground_floor_slab_y - door_rect_extend),
            door_rect_width, door_rect_height,
            facecolor='white',
            edgecolor=config.WALL_EDGE_COLOR,
            linewidth=config.WALL_EDGE_WIDTH,
            zorder=3,
        ))

        # Floor 1 landing door
        ax.add_patch(Rectangle(
            (wt, floor_1_level - door_rect_extend),
            door_rect_width, door_rect_height,
            facecolor='white',
            edgecolor=config.WALL_EDGE_COLOR,
            linewidth=config.WALL_EDGE_WIDTH,
            zorder=3,
        ))

        # Floor n-1 landing door
        ax.add_patch(Rectangle(
            (wt, floor_n_minus_1_level - door_rect_extend),
            door_rect_width, door_rect_height,
            facecolor='white',
            edgecolor=config.WALL_EDGE_COLOR,
            linewidth=config.WALL_EDGE_WIDTH,
            zorder=3,
        ))

        # Top Floor landing door
        ax.add_patch(Rectangle(
            (wt, top_level - door_rect_extend),
            door_rect_width, door_rect_height,
            facecolor='white',
            edgecolor=config.WALL_EDGE_COLOR,
            linewidth=config.WALL_EDGE_WIDTH,
            zorder=3,
        ))

        # Right wall (continuous - no openings on this side)
        # Extends to machine room top for MRA
        draw_wall_section(
            ax, wt + sw, pit_bottom, wt, machine_room_top - pit_bottom,
            display_options["show_hatching"]
        )
        # Top wall (closing the shaft at overhead level for MRL, or machine room top for MRA)
        draw_wall_section(
            ax, wt, machine_room_top - slab_thickness, sw, slab_thickness,
            display_options["show_hatching"]
        )
        # Bottom wall / pit slab (single wall with pit_slab thickness)
        draw_wall_section(
            ax, wt, pit_bottom, sw, pit_slab_thickness,
            display_options["show_hatching"]
        )

        # For MRA, draw machine room walls (left wall extension from overhead_top to machine_room_top)
        if self.machine_type == "mra":
            # Left wall extension for machine room
            draw_wall_section(
                ax, 0, overhead_top, wt, self.machine_room_height,
                display_options["show_hatching"]
            )

        # Draw floor slab protrusions at the visible landing and overhead levels
        protrusion_depth = 400  # mm

        # 1. Top edge (overhead level)
        if self.machine_type == "mra":
            # For MRA: draw full-width slab as machine room floor (no protrusions)
            draw_wall_section(
                ax, wt, overhead_top - slab_thickness, sw, slab_thickness,
                display_options["show_hatching"]
            )
        else:
            # For MRL: draw protrusions extending outward
            draw_floor_slab_protrusion(
                ax, wt, wt + sw, overhead_top,
                protrusion_depth=protrusion_depth,
                slab_thickness=slab_thickness,
                wall_thickness=wt,
                show_hatching=display_options["show_hatching"],
            )

        # 2. Ground floor level (slightly above pit edge)
        draw_floor_slab_protrusion(
            ax, wt, wt + sw, ground_floor_slab_y,
            protrusion_depth=protrusion_depth,
            slab_thickness=slab_thickness,
            wall_thickness=wt,
            show_hatching=display_options["show_hatching"],
        )

        # 3. Floor 1 level (below break lines)
        draw_floor_slab_protrusion(
            ax, wt, wt + sw, floor_1_level,
            protrusion_depth=protrusion_depth,
            slab_thickness=slab_thickness,
            wall_thickness=wt,
            show_hatching=display_options["show_hatching"],
        )

        # 4. Floor n-1 level (above break lines)
        draw_floor_slab_protrusion(
            ax, wt, wt + sw, floor_n_minus_1_level,
            protrusion_depth=protrusion_depth,
            slab_thickness=slab_thickness,
            wall_thickness=wt,
            show_hatching=display_options["show_hatching"],
        )

        # 5. Top Floor level
        draw_floor_slab_protrusion(
            ax, wt, wt + sw, top_level,
            protrusion_depth=protrusion_depth,
            slab_thickness=slab_thickness,
            wall_thickness=wt,
            show_hatching=display_options["show_hatching"],
        )

        # Draw machine, loading beam, and AC duct
        # For MRL: in overhead area
        # For MRA: in machine room (above overhead area)
        if display_options.get("show_mrl_machine", True):
            if self.machine_type == "mra":
                # MRA: Draw machine in machine room (above overhead)
                mrh = self.machine_room_height

                # Hoisting beam (visual thickness remains proportional)
                beam_height = mrh * 0.025
                bar_y = machine_room_top - slab_thickness - beam_height - 100  # Fixed 100mm gap from ceiling

                ax.add_patch(Rectangle(
                    (wt, bar_y),
                    sw, beam_height,
                    facecolor='white',
                    edgecolor='black',
                    linewidth=1.0,
                    zorder=4,
                ))
                self._draw_hoisting_beam_callout(
                    ax,
                    beam_right_x=wt + sw,
                    wall_thickness=wt,
                    beam_center_y=bar_y + beam_height / 2,
                )

                # Machine - draw at 70% of the available size while keeping its
                # bottom edge anchored to the machine-room floor.
                machine_scale = 0.7
                machine_width = sw * 0.9 * machine_scale
                machine_x_center = wt + sw / 2  # Centered in shaft
                machine_y_bottom = overhead_top  # Bottom edge touches top of machine room floor slab
                machine_height = (
                    bar_y - machine_y_bottom - 100
                ) * machine_scale

                # If an unusually short machine room leaves no safe space,
                # omit the image instead of allowing it to cross the beam.
                if machine_height > 0:
                    draw_machine_image(
                        ax,
                        x_center=machine_x_center,
                        y_bottom=machine_y_bottom,
                        width=machine_width,
                        height=machine_height,
                        machine_type="mra",
                        display_scale_y=render_scale_y,
                    )

            elif self.machine_type == "mrl":
                # MRL: Draw machine in overhead area (existing behavior)
                # Heights are proportional to overhead clearance for proper scaling
                ohc = self.overhead_clearance

                # Hoisting beam (visual thickness remains proportional)
                beam_height = ohc * 0.015
                bar_y = overhead_top - slab_thickness - beam_height - 100  # Fixed 100mm gap from ceiling

                ax.add_patch(Rectangle(
                    (wt, bar_y),
                    sw, beam_height,
                    facecolor='white',
                    edgecolor='black',
                    linewidth=1.0,
                    zorder=4,
                ))
                self._draw_hoisting_beam_callout(
                    ax,
                    beam_right_x=wt + sw,
                    wall_thickness=wt,
                    beam_center_y=bar_y + beam_height / 2,
                )

                # Machine (height proportional)
                machine_width = sw * 0.85  # 85% of shaft width
                machine_height = ohc * 0.24  # 24% of overhead clearance
                machine_x_center = wt + sw / 2  # Centered in shaft
                machine_y_bottom = bar_y - machine_height - 100  # Fixed 100mm gap below beam

                draw_machine_image(
                    ax,
                    x_center=machine_x_center,
                    y_bottom=machine_y_bottom,
                    width=machine_width,
                    height=machine_height,
                    machine_type="mrl",
                )

                # AC duct (height proportional)
                duct_width = wt  # Same width as wall thickness
                duct_height = ohc * 0.12  # 12% of overhead clearance (half of machine)
                duct_x = wt + sw  # Inside the right wall
                duct_y = machine_y_bottom + (machine_height - duct_height) / 2  # Centered vertically with machine

                # Draw the rectangle
                ax.add_patch(Rectangle(
                    (duct_x, duct_y),
                    duct_width, duct_height,
                    facecolor='white',
                    edgecolor='black',
                    linewidth=1.0,
                    zorder=4,
                ))

                # Draw X cross inside the box
                ax.plot(
                    [duct_x, duct_x + duct_width],
                    [duct_y, duct_y + duct_height],
                    color='black', linewidth=0.8, zorder=5
                )
                ax.plot(
                    [duct_x, duct_x + duct_width],
                    [duct_y + duct_height, duct_y],
                    color='black', linewidth=0.8, zorder=5
                )

                # AC Duct label with arrow
                duct_center_x = duct_x + duct_width / 2
                duct_center_y = duct_y + duct_height / 2
                label_x = duct_x + duct_width + 600

                # Draw arrow line with arrowhead
                arrow = FancyArrowPatch(
                    (label_x - 50, duct_center_y),  # Start (near label)
                    (duct_x + duct_width + 20, duct_center_y),  # End (at duct)
                    arrowstyle='->',
                    mutation_scale=15,
                    color='black',
                    linewidth=1.0,
                    zorder=10,
                )
                ax.add_patch(arrow)

                # Label text
                ax.text(
                    label_x, duct_center_y,
                    'AC Duct',
                    fontsize=config.DIMENSION_TEXT_SIZE,
                    ha='left',
                    va='center',
                )

        # Draw break lines
        if display_options["show_break_lines"]:
            break_y_center = break_line_bottom + self.break_zone_height / 2
            draw_break_lines(
                ax,
                x_left=wt,
                x_right=wt + sw,
                y_center=break_y_center,
                wall_thickness=wt,
            )

        # Draw dimensions
        if display_options["show_dimensions"]:
            self._draw_section_dimensions(
                ax,
                pit_bottom,
                ground_level,
                top_level,
                overhead_top,
                ground_floor_slab_y,
                floor_1_level,
                machine_room_top,
                floor_n_minus_1_level=floor_n_minus_1_level,
                rendered_slab_thickness=slab_thickness,
            )

        # Set axis limits with margins
        ax.set_xlim(-margin_x, self.total_width + margin_x)
        ax.set_ylim(pit_bottom - margin_bottom, machine_room_top + margin_top)
        # NOTE: the brief-spec table is composited as a PIL strip above the saved
        # image (see to_bytes); it is no longer drawn inside the axes.

    @staticmethod
    def _draw_hoisting_beam_callout(
        ax: plt.Axes,
        beam_right_x: float,
        wall_thickness: float,
        beam_center_y: float,
    ) -> None:
        """Draw the fixed-height, single-arrow label for the hoisting beam."""
        wall_outer_x = beam_right_x + wall_thickness
        label_x = wall_outer_x + 600
        arrow = FancyArrowPatch(
            (label_x - 50, beam_center_y),
            (wall_outer_x + 20, beam_center_y),
            arrowstyle='->',
            mutation_scale=15,
            color='black',
            linewidth=1.0,
            zorder=10,
        )
        ax.add_patch(arrow)
        ax.text(
            label_x,
            beam_center_y,
            f"Hoisting Beam Height {int(config.HOISTING_BEAM_HEIGHT_LABEL)} mm",
            fontsize=config.DIMENSION_TEXT_SIZE,
            ha='left',
            va='center',
        )

    def _brief_spec_rows(self) -> list:
        """Single-row brief-spec body for the depicted lift (columns per
        `brief_spec_row`)."""
        if self.lift_config is None:
            return []
        return [brief_spec_row(self.lift_config)]

    def _landing_labels(self) -> tuple[str, str, str, str]:
        """Labels of the four drawn landings, bottom to top."""
        if self.lowest_floor_name:
            bottom = _floor_label(self.lowest_floor_name)
            second = _floor_label(floor_above(self.lowest_floor_name))
        else:
            bottom, second = "Bottom-most\nLanding FFL", "Floor 1 F.F.L."
        if self.top_floor_number is not None:
            below_top = _floor_label(str(self.top_floor_number - 1))
            top = _floor_label(str(self.top_floor_number))
        else:
            below_top, top = "Floor n-1 F.F.L.", "Top Floor F.F.L."
        return bottom, second, below_top, top

    def _average_floor_height(self) -> Optional[float]:
        """The entered average floor height, else travel / (floors - 1) from
        the named top and lowest floors; None when neither is known."""
        if self.average_floor_height is not None:
            return self.average_floor_height
        if self.top_floor_number is None or not self.lowest_floor_name:
            return None
        lowest = floor_level(self.lowest_floor_name)
        if lowest is None or self.top_floor_number <= lowest:
            return None
        return self.travel_height / (self.top_floor_number - lowest)

    def _draw_section_dimensions(
        self,
        ax: plt.Axes,
        pit_bottom: float,
        ground_level: float,
        top_level: float,
        overhead_top: float,
        ground_floor_slab_y: float = None,
        floor_1_level: float = None,
        machine_room_top: float = None,
        floor_n_minus_1_level: float = None,
        rendered_slab_thickness: float = None,
    ) -> None:
        """Draw dimension annotations for section view."""
        wt = self.wall_thickness
        sw = self.shaft_depth
        slab_thickness = (
            rendered_slab_thickness
            if rendered_slab_thickness is not None
            else wt
        )

        # Use ground_level if ground_floor_slab_y not provided
        if ground_floor_slab_y is None:
            ground_floor_slab_y = ground_level + 1200

        if floor_1_level is None:
            floor_1_level = ground_floor_slab_y + self.display_floor_height

        if floor_n_minus_1_level is None:
            floor_n_minus_1_level = top_level - self.display_floor_height

        # Default machine_room_top to overhead_top for MRL
        if machine_room_top is None:
            machine_room_top = overhead_top

        # Horizontal dimensions at bottom
        # Shaft depth (cross-section view)
        draw_dimension_line(
            ax,
            start=(wt, pit_bottom),
            end=(wt + sw, pit_bottom),
            text=f"Shaft Depth {int(sw)}",
            offset=-300,
            orientation="horizontal",
        )

        # Pit slab callout, aligned with the AC duct and hoisting beam labels.
        wall_outer_x = wt + sw + wt
        label_x = wall_outer_x + 600
        pit_slab_center_y = (pit_bottom + ground_level) / 2
        ax.add_patch(FancyArrowPatch(
            (label_x - 50, pit_slab_center_y),
            (wall_outer_x + 20, pit_slab_center_y),
            arrowstyle="->",
            mutation_scale=15,
            color="black",
            linewidth=1.0,
            zorder=10,
        ))
        ax.text(
            label_x,
            pit_slab_center_y,
            f"Pit Slab {int(self.pit_slab)} mm",
            fontsize=config.DIMENSION_TEXT_SIZE,
            ha="left",
            va="center",
        )

        # Keep the overall vertical dimensions clear of the landing labels.
        overall_dimension_offset = -1200

        # Vertical dimensions on left side
        # Pit Depth (from ground level to ground floor slab top)
        draw_dimension_line(
            ax,
            start=(0, ground_level),
            end=(0, ground_floor_slab_y),
            text=f"Pit Depth {int(ground_floor_slab_y - ground_level)}",
            offset=overall_dimension_offset,
            orientation="vertical",
        )

        # Travel (from ground floor slab top to top floor slab top)
        # Use actual travel_height from config (visual positions are compressed by break lines)
        travel_text = f"Travel {int(self.travel_height)} mm"
        average = self._average_floor_height()
        if average is not None:
            travel_text += f"\nAverage Floor Height {average:.0f} mm"
        draw_dimension_line(
            ax,
            start=(0, ground_floor_slab_y),
            end=(0, top_level),
            text=travel_text,
            offset=overall_dimension_offset,
            orientation="vertical",
        )

        # Headroom (from top floor slab top to inner edge of top wall)
        draw_dimension_line(
            ax,
            start=(0, top_level),
            end=(0, overhead_top - slab_thickness),
            text=f"Headroom {int(self.overhead_clearance)}",
            offset=overall_dimension_offset,
            orientation="vertical",
        )

        # Wall thickness
        draw_dimension_line(
            ax,
            start=(0, pit_bottom),
            end=(wt, pit_bottom),
            text=f"{int(wt)}",
            offset=-300,
            orientation="horizontal",
        )

        # Place landing labels just beyond the outer end of the left slab.
        # parse_math=False: floor names are user text, never mathtext.
        floor_label_x = -450
        landing_levels = (
            ground_floor_slab_y,
            floor_1_level,
            floor_n_minus_1_level,
            top_level,
        )
        for level, label in zip(landing_levels, self._landing_labels()):
            ax.text(
                floor_label_x, level - slab_thickness - 100,
                label,
                ha="right", va="top",
                fontsize=config.DIMENSION_TEXT_SIZE,
                color=config.DIMENSION_COLOR,
                parse_math=False,
            )

        # Structural opening dimensions (on left side, near the openings)
        opening_height = self.structural_opening_height
        door_height = self.door_height

        # Ground floor - Structural Opening (further left)
        draw_dimension_line(
            ax,
            start=(0, ground_floor_slab_y),
            end=(0, ground_floor_slab_y + opening_height),
            text=f"Struct. Opening {int(opening_height)}",
            offset=-300,
            orientation="vertical",
        )

        # Ground floor - Door Opening (closer to wall)
        draw_dimension_line(
            ax,
            start=(0, ground_floor_slab_y),
            end=(0, ground_floor_slab_y + door_height),
            text=f"Door Opening {int(door_height)}",
            offset=-50,
            orientation="vertical",
        )

        # Floor 1 - Structural Opening (further left)
        draw_dimension_line(
            ax,
            start=(0, floor_1_level),
            end=(0, floor_1_level + opening_height),
            text=f"Struct. Opening {int(opening_height)}",
            offset=-300,
            orientation="vertical",
        )

        # Floor 1 - Door Opening (closer to wall)
        draw_dimension_line(
            ax,
            start=(0, floor_1_level),
            end=(0, floor_1_level + door_height),
            text=f"Door Opening {int(door_height)}",
            offset=-50,
            orientation="vertical",
        )

        # Floor n-1 - Structural Opening (further left)
        draw_dimension_line(
            ax,
            start=(0, floor_n_minus_1_level),
            end=(0, floor_n_minus_1_level + opening_height),
            text=f"Struct. Opening {int(opening_height)}",
            offset=-300,
            orientation="vertical",
        )

        # Floor n-1 - Door Opening (closer to wall)
        draw_dimension_line(
            ax,
            start=(0, floor_n_minus_1_level),
            end=(0, floor_n_minus_1_level + door_height),
            text=f"Door Opening {int(door_height)}",
            offset=-50,
            orientation="vertical",
        )

        # Top Floor - Structural Opening (further left)
        draw_dimension_line(
            ax,
            start=(0, top_level),
            end=(0, top_level + opening_height),
            text=f"Struct. Opening {int(opening_height)}",
            offset=-300,
            orientation="vertical",
        )

        # Top Floor - Door Opening (closer to wall)
        draw_dimension_line(
            ax,
            start=(0, top_level),
            end=(0, top_level + door_height),
            text=f"Door Opening {int(door_height)}",
            offset=-50,
            orientation="vertical",
        )

        # MRA Machine Room dimension (only for MRA)
        if self.machine_type == "mra" and machine_room_top > overhead_top:
            draw_dimension_line(
                ax,
                start=(0, overhead_top),
                end=(0, machine_room_top - slab_thickness),
                text=f"Machine Room {int(self.machine_room_height)}",
                offset=overall_dimension_offset,
                orientation="vertical",
            )
