"""
Lift shaft section sketch generator class.

Generates cross-sectional views of lift shafts (viewing from door/landing side).
Complements the plan sketch (top-down view) in shaft_sketch.py.
"""

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for PNG generation
from matplotlib.patches import Rectangle

from . import config
from .shaft_sketch import LiftConfig
from .drawing_utils import (
    draw_wall_section,
    draw_dimension_line,
    draw_title_block,
    draw_section_pit,
    draw_break_lines,
    draw_section_landing,
    draw_floor_slab_protrusion,
    draw_machine_image,
)


@dataclass
class SectionConfig:
    """Configuration for section view parameters."""

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

    @property
    def total_shaft_height(self) -> float:
        """Total height from pit bottom to overhead top."""
        return self.pit_depth + self.travel_height + self.overhead_clearance

    @property
    def num_floors(self) -> int:
        """Approximate number of floors based on travel height."""
        return max(2, int(self.travel_height / self.floor_height) + 1)


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
        shaft_width: float = None,
        shaft_depth: float = None,  # Used as internal width in section view
        wall_thickness: float = None,
        door_width: float = None,
        # Enhanced API
        lift_config: LiftConfig = None,
        section_config: SectionConfig = None,
    ):
        """
        Initialize lift section sketch generator.

        Args:
            shaft_width: Shaft width for section view (horizontal, mm)
            shaft_depth: Shaft depth from plan view (used for wall positioning, mm)
            wall_thickness: RCC wall thickness (mm)
            door_width: Door opening width (mm)
            lift_config: LiftConfig from plan sketch (for dimensional consistency)
            section_config: Section-specific configuration (heights, pit depth, etc.)
        """
        self.lift_config = lift_config
        self.section_config = section_config or SectionConfig()

        # Determine dimensions from lift_config or defaults
        if lift_config is not None:
            self.shaft_width = lift_config.shaft_width
            self.shaft_depth = lift_config.shaft_depth
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
            self.shaft_width = shaft_width or config.DEFAULT_SHAFT_WIDTH
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

        # Section-specific parameters
        self.pit_depth = self.section_config.pit_depth
        self.overhead_clearance = self.section_config.overhead_clearance
        self.travel_height = self.section_config.travel_height
        self.floor_height = self.section_config.floor_height
        self.car_interior_height = self.section_config.car_interior_height

        # Calculate geometry
        self._calculate_geometry()

    def _calculate_geometry(self) -> None:
        """Calculate section geometry based on parameters."""
        # Total width including walls
        self.total_width = self.shaft_width + 2 * self.wall_thickness

        # Vertical geometry
        # Ground floor level is at y=0 in the drawing
        self.ground_floor_y = 0
        self.pit_bottom_y = -self.pit_depth
        self.top_floor_y = self.travel_height
        self.overhead_top_y = self.top_floor_y + self.overhead_clearance

        # For simplified section view with break lines:
        # We show ground floor zone, break lines, and top floor zone
        self.ground_zone_height = 4000  # 4m zone around ground floor
        self.top_zone_height = 5000  # 5m zone around top floor (includes machine)
        self.break_zone_height = 1500  # Height for break line area

        # Total drawing height (simplified)
        self.drawing_height = (
            self.pit_depth +
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
        self._draw_section(ax, title, subtitle, display_options)

        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(
            output_path,
            dpi=dpi or config.DEFAULT_DPI,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)

        return str(output_path.absolute())

    def to_bytes(
        self,
        show_hatching: bool = True,
        show_dimensions: bool = True,
        show_pit: bool = True,
        show_break_lines: bool = True,
        show_mrl_machine: bool = True,
        title: str = None,
        subtitle: Optional[str] = None,
        dpi: int = None,
    ) -> bytes:
        """
        Return PNG as bytes (for API responses).

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
        }

        fig, ax = self._create_figure()
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

        buf.seek(0)
        return buf.read()

    def _create_figure(self) -> tuple:
        """Create matplotlib figure and axes for section view."""
        fig, ax = plt.subplots(
            figsize=(config.SECTION_FIGURE_WIDTH, config.SECTION_FIGURE_HEIGHT)
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
        sw = self.shaft_width

        # Calculate y positions for the simplified view
        pit_bottom = -self.pit_depth
        ground_level = 0
        break_line_bottom = self.ground_zone_height
        break_line_top = break_line_bottom + self.break_zone_height
        top_zone_bottom = break_line_top
        top_level = break_line_top + (self.top_zone_height - self.overhead_clearance)
        overhead_top = break_line_top + self.top_zone_height

        # Floor slab positions (needed for structural openings)
        slab_thickness = wt  # Same thickness as walls (200mm)
        ground_floor_slab_y = ground_level + 1200  # Above pit edge with space for dimension labels

        # Skip shaft interior background - keep it white

        # Draw pit area
        if display_options["show_pit"]:
            draw_section_pit(
                ax,
                x=wt,
                y=ground_level,
                width=sw,
                depth=self.pit_depth,
                show_hatching=display_options["show_hatching"],
            )

        # Draw side walls (left and right)
        # Left wall - segmented with structural openings at ground and top floors
        opening_height = self.structural_opening_height
        ground_opening_top = ground_floor_slab_y + opening_height
        top_opening_top = top_level + opening_height

        # Segment 1: From pit bottom to ground floor slab (below ground opening)
        draw_wall_section(
            ax, 0, pit_bottom, wt, ground_floor_slab_y - pit_bottom,
            display_options["show_hatching"]
        )

        # Segment 2: From above ground opening to top floor slab (spans break zone)
        draw_wall_section(
            ax, 0, ground_opening_top, wt, top_level - ground_opening_top,
            display_options["show_hatching"]
        )

        # Segment 3: From above top opening to overhead top
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

        # Top floor landing door
        ax.add_patch(Rectangle(
            (wt, top_level - door_rect_extend),
            door_rect_width, door_rect_height,
            facecolor='white',
            edgecolor=config.WALL_EDGE_COLOR,
            linewidth=config.WALL_EDGE_WIDTH,
            zorder=3,
        ))

        # For MRA, calculate machine room top
        if self.machine_type == "mra":
            machine_room_top = overhead_top + self.machine_room_height
        else:
            machine_room_top = overhead_top

        # Right wall (continuous - no openings on this side)
        # Extends to machine room top for MRA
        draw_wall_section(
            ax, wt + sw, pit_bottom, wt, machine_room_top - pit_bottom,
            display_options["show_hatching"]
        )
        # Top wall (closing the shaft at overhead level for MRL, or machine room top for MRA)
        draw_wall_section(
            ax, wt, machine_room_top - wt, sw, wt,
            display_options["show_hatching"]
        )
        # Bottom wall (closing the shaft at pit bottom)
        draw_wall_section(
            ax, wt, pit_bottom, sw, wt,
            display_options["show_hatching"]
        )

        # For MRA, draw machine room walls (left wall extension from overhead_top to machine_room_top)
        if self.machine_type == "mra":
            # Left wall extension for machine room
            draw_wall_section(
                ax, 0, overhead_top, wt, self.machine_room_height,
                display_options["show_hatching"]
            )

        # Draw floor slab protrusions at three levels
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

        # 3. Top floor level (above break lines)
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

                # Loading beam (height proportional to machine room)
                beam_height = mrh * 0.02  # ~2% of machine room height
                bar_y = machine_room_top - slab_thickness - beam_height - 100  # Fixed 100mm gap from ceiling

                ax.add_patch(Rectangle(
                    (wt, bar_y),
                    sw, beam_height,
                    facecolor='white',
                    edgecolor='black',
                    linewidth=1.0,
                    zorder=4,
                ))

                # Machine - fill machine room space (aspect ratio preserved by draw_machine_image)
                machine_width = sw * 0.9  #  (will be constrained by aspect ratio)
                machine_height = mrh * 0.9  #  (will be constrained by aspect ratio)
                machine_x_center = wt + sw / 2  # Centered in shaft
                machine_y_bottom = overhead_top  # Bottom edge touches top of machine room floor slab

                draw_machine_image(
                    ax,
                    x_center=machine_x_center,
                    y_bottom=machine_y_bottom,
                    width=machine_width,
                    height=machine_height,
                    machine_type="mra",
                )

            elif self.machine_type == "mrl":
                # MRL: Draw machine in overhead area (existing behavior)
                # Heights are proportional to overhead clearance for proper scaling
                ohc = self.overhead_clearance

                # Loading beam (height proportional)
                beam_height = ohc * 0.007  # ~0.7% of overhead clearance
                bar_y = overhead_top - slab_thickness - beam_height - 100  # Fixed 100mm gap from ceiling

                ax.add_patch(Rectangle(
                    (wt, bar_y),
                    sw, beam_height,
                    facecolor='white',
                    edgecolor='black',
                    linewidth=1.0,
                    zorder=4,
                ))

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
                from matplotlib.patches import FancyArrowPatch
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
            self._draw_section_dimensions(ax, pit_bottom, ground_level, top_level, overhead_top, ground_floor_slab_y, machine_room_top)

        # Set axis limits with margins
        margin_x = 1500  # Horizontal margin for dimensions
        margin_bottom = 1000  # Bottom margin for title and dimensions
        margin_top = 500  # Top margin
        ax.set_xlim(-margin_x, self.total_width + margin_x)
        ax.set_ylim(pit_bottom - margin_bottom, machine_room_top + margin_top)

        # Draw title
        if title is None:
            title = "LIFT SHAFT SECTION"
        draw_title_block(ax, title, subtitle, y_position=pit_bottom - 700)

    def _draw_section_dimensions(
        self,
        ax: plt.Axes,
        pit_bottom: float,
        ground_level: float,
        top_level: float,
        overhead_top: float,
        ground_floor_slab_y: float = None,
        machine_room_top: float = None,
    ) -> None:
        """Draw dimension annotations for section view."""
        wt = self.wall_thickness
        sw = self.shaft_width
        slab_thickness = wt  # 200mm, same as walls

        # Use ground_level if ground_floor_slab_y not provided
        if ground_floor_slab_y is None:
            ground_floor_slab_y = ground_level + 1200

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

        # Vertical dimensions on left side (four stacked dimensions)
        # 1. Pit Slab (bottom wall thickness - from pit bottom to ground level)
        draw_dimension_line(
            ax,
            start=(0, pit_bottom),
            end=(0, ground_level),
            text="Pit Slab",
            offset=-1300,
            orientation="vertical",
        )

        # 2. Pit Depth (from ground level to ground floor slab top)
        draw_dimension_line(
            ax,
            start=(0, ground_level),
            end=(0, ground_floor_slab_y),
            text=f"Pit Depth {int(ground_floor_slab_y - ground_level)}",
            offset=-1000,
            orientation="vertical",
        )

        # 3. Travel (from ground floor slab top to top floor slab top)
        draw_dimension_line(
            ax,
            start=(0, ground_floor_slab_y),
            end=(0, top_level),
            text=f"Travel {int(top_level - ground_floor_slab_y)}",
            offset=-1000,
            orientation="vertical",
        )

        # 4. Headroom (from top floor slab top to bottom of overhead slab)
        draw_dimension_line(
            ax,
            start=(0, top_level),
            end=(0, overhead_top - slab_thickness),
            text=f"Headroom {int(overhead_top - slab_thickness - top_level)}",
            offset=-1000,
            orientation="vertical",
        )

        # Wall thickness
        draw_dimension_line(
            ax,
            start=(0, ground_level),
            end=(wt, ground_level),
            text=f"{int(wt)}",
            offset=-600,
            orientation="horizontal",
        )

        # Add floor labels (positioned below slab levels to avoid overlap with structural opening dimensions)
        ax.text(
            -200, ground_floor_slab_y - slab_thickness - 100,
            "Bottom most\nserving level",
            ha="right", va="top",
            fontsize=config.DIMENSION_TEXT_SIZE,
            color=config.DIMENSION_COLOR,
        )

        ax.text(
            -200, top_level - slab_thickness - 100,
            "Top Landing\nF.F.L.",
            ha="right", va="top",
            fontsize=config.DIMENSION_TEXT_SIZE,
            color=config.DIMENSION_COLOR,
        )

        # Structural opening dimensions (on left side, near the openings)
        opening_height = self.structural_opening_height
        door_height = self.door_height

        # Ground floor - Structural Opening (further left)
        draw_dimension_line(
            ax,
            start=(0, ground_floor_slab_y),
            end=(0, ground_floor_slab_y + opening_height),
            text=f"Structural Opening {int(opening_height)}",
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

        # Top floor - Structural Opening (further left)
        draw_dimension_line(
            ax,
            start=(0, top_level),
            end=(0, top_level + opening_height),
            text=f"Structural Opening {int(opening_height)}",
            offset=-300,
            orientation="vertical",
        )

        # Top floor - Door Opening (closer to wall)
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
                end=(0, machine_room_top),
                text=f"Machine Room {int(self.machine_room_height)}",
                offset=-1000,
                orientation="vertical",
            )
