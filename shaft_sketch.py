"""
Main lift shaft sketch generator class.
"""

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for PNG generation
from matplotlib.patches import Rectangle

# Support both package (relative) and standalone (absolute) imports
try:
    from . import config
    from .drawing_utils import (
        draw_wall_section,
        draw_opening,
        draw_dimension_line,
        draw_centerline,
        draw_shaft_interior,
        draw_title_block,
        draw_steel_beam,
        draw_counterweight_bracket,
        draw_car_bracket,
        draw_car_bracket_cw_side,
        draw_lift_car,
        draw_door_panels,
        draw_car_interior_details,
        draw_lift_doors,
        draw_door_jambs,
        draw_counterweight_bracket_top,
        draw_car_brackets_mra,
    )
except ImportError:
    import config
    from drawing_utils import (
        draw_wall_section,
        draw_opening,
        draw_dimension_line,
        draw_centerline,
        draw_shaft_interior,
        draw_title_block,
        draw_steel_beam,
        draw_counterweight_bracket,
        draw_car_bracket,
        draw_car_bracket_cw_side,
        draw_lift_car,
        draw_door_panels,
        draw_car_interior_details,
        draw_lift_doors,
        draw_door_jambs,
        draw_counterweight_bracket_top,
        draw_car_brackets_mra,
    )


# Fire lift fixed cabin sizes (Width x Depth in mm)
FIRE_LIFT_CABIN_SIZES = [
    (1400, 2400),
    (1500, 2300),
    (1550, 2200),
]


@dataclass
class LiftConfig:
    """Configuration for a single lift."""

    lift_type: str = "passenger"  # "passenger" or "fire"
    lift_capacity: Optional[int] = None  # e.g., 1350 KG
    lift_machine_type: str = "mrl"  # "mrl" (Machine Room Less) or "mra" (Machine Room Above)

    # Car dimensions (for detailed drawings)
    finished_car_width: float = field(default_factory=lambda: config.DEFAULT_FINISHED_CAR_WIDTH)
    finished_car_depth: float = field(default_factory=lambda: config.DEFAULT_FINISHED_CAR_DEPTH)

    # MRL Bracket widths (used when lift_machine_type == "mrl")
    counterweight_bracket_width: float = field(default_factory=lambda: config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH)
    car_bracket_width: float = field(default_factory=lambda: config.DEFAULT_CAR_BRACKET_WIDTH)

    # MRA-specific parameters (used when lift_machine_type == "mra")
    mra_car_bracket_width: float = field(default_factory=lambda: config.MRA_CAR_BRACKET_WIDTH)
    mra_car_bracket_width_right: Optional[float] = None  # None = same as left
    mra_cw_bracket_depth: float = field(default_factory=lambda: config.MRA_CW_BRACKET_DEPTH)

    # Shaft dimension overrides (user-specified explicit shaft dimensions)
    shaft_width_override: Optional[float] = None
    shaft_depth_override: Optional[float] = None
    wall_thickness: float = field(default_factory=lambda: config.DEFAULT_WALL_THICKNESS)

    # Door/opening dimensions
    door_width: float = field(default_factory=lambda: config.DEFAULT_DOOR_WIDTH)
    door_height: float = field(default_factory=lambda: config.DEFAULT_DOOR_HEIGHT)
    structural_opening_width: float = field(default_factory=lambda: config.DEFAULT_STRUCTURAL_OPENING_WIDTH)
    structural_opening_height: float = field(default_factory=lambda: config.DEFAULT_STRUCTURAL_OPENING_HEIGHT)

    # Door panel dimensions (affects shaft depth calculation)
    door_panel_thickness: float = field(default_factory=lambda: config.DEFAULT_LIFT_DOOR_THICKNESS)
    door_extension: float = field(default_factory=lambda: config.DEFAULT_DOOR_EXTENSION)

    # Telescopic door parameters (fire lifts only)
    door_opening_type: str = "centre"  # "centre" or "telescopic" (fire lifts only)
    telescopic_left_ext: Optional[float] = None   # Left extension for telescopic (auto-calculated if None)
    telescopic_right_ext: Optional[float] = None   # Right extension for telescopic (auto-calculated if None)

    @property
    def unfinished_car_width(self) -> float:
        """Unfinished car width = finished + 50mm (25mm each side)."""
        return self.finished_car_width + 2 * config.DEFAULT_CAR_WALL_THICKNESS

    @property
    def unfinished_car_depth(self) -> float:
        """Unfinished car depth = finished + 25mm (at top only)."""
        return self.finished_car_depth + config.DEFAULT_CAR_WALL_THICKNESS

    @property
    def mra_right_bracket_width(self) -> float:
        """Right MRA car bracket width (defaults to left if not set)."""
        if self.mra_car_bracket_width_right is not None:
            return self.mra_car_bracket_width_right
        return self.mra_car_bracket_width

    @property
    def min_shaft_width(self) -> float:
        """Calculate minimum shaft width from car + brackets."""
        if self.lift_machine_type == "mra":
            width = self.mra_car_bracket_width + self.unfinished_car_width + self.mra_right_bracket_width
        else:
            width = self.counterweight_bracket_width + self.unfinished_car_width + self.car_bracket_width
        if self.lift_type == "fire":
            fire_min = (config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC
                        if self.door_opening_type == "telescopic"
                        else config.FIRE_LIFT_MIN_SHAFT_WIDTH)
            width = max(width, fire_min)
        return width

    @property
    def min_shaft_depth(self) -> float:
        """Calculate minimum shaft depth from car + doors + clearances."""
        if self.lift_machine_type == "mra":
            return (2 * self.door_panel_thickness + config.DEFAULT_DOOR_GAP
                    + self.unfinished_car_depth + config.MRA_CW_GAP + self.mra_cw_bracket_depth)
        else:
            return (self.unfinished_car_depth + 2 * self.door_panel_thickness
                    + config.DEFAULT_DOOR_GAP + config.DEFAULT_REAR_CLEARANCE)

    @property
    def shaft_width(self) -> float:
        """Return shaft width (override or calculated minimum)."""
        if self.shaft_width_override is not None:
            return self.shaft_width_override
        return self.min_shaft_width

    @property
    def shaft_depth(self) -> float:
        """Backward-compatible alias for effective_shaft_depth."""
        return self.effective_shaft_depth

    @property
    def effective_shaft_depth(self) -> float:
        """Return shaft depth (override or calculated minimum)."""
        if self.shaft_depth_override is not None:
            return self.shaft_depth_override
        return self.min_shaft_depth

    @property
    def remaining_width(self) -> float:
        """Extra width beyond minimum (shaft_width - min_shaft_width)."""
        return self.shaft_width - self.min_shaft_width

    @property
    def remaining_depth(self) -> float:
        """Extra depth beyond minimum (effective_shaft_depth - min_shaft_depth)."""
        return self.effective_shaft_depth - self.min_shaft_depth

    @property
    def actual_rear_clearance(self) -> float:
        """MRL: actual rear clearance including extra depth."""
        return config.DEFAULT_REAR_CLEARANCE + self.remaining_depth

    @property
    def actual_mra_cw_gap(self) -> float:
        """MRA: actual gap between car top and CW bracket including extra depth."""
        return config.MRA_CW_GAP + self.remaining_depth

    def _width_breakdown_str(self) -> str:
        """Return a human-readable breakdown of minimum shaft width components."""
        if self.lift_machine_type == "mra":
            return (f"Left Bracket ({int(self.mra_car_bracket_width)}) + "
                    f"Unfinished Car ({int(self.unfinished_car_width)}) + "
                    f"Right Bracket ({int(self.mra_right_bracket_width)})")
        else:
            return (f"CW Bracket ({int(self.counterweight_bracket_width)}) + "
                    f"Unfinished Car ({int(self.unfinished_car_width)}) + "
                    f"Car Bracket ({int(self.car_bracket_width)})")

    def _depth_breakdown_str(self) -> str:
        """Return a human-readable breakdown of minimum shaft depth components."""
        if self.lift_machine_type == "mra":
            return (f"2 x Door ({int(self.door_panel_thickness)}) + "
                    f"Gap ({int(config.DEFAULT_DOOR_GAP)}) + "
                    f"Unfinished Car ({int(self.unfinished_car_depth)}) + "
                    f"CW Gap ({int(config.MRA_CW_GAP)}) + "
                    f"CW Bracket ({int(self.mra_cw_bracket_depth)})")
        else:
            return (f"Unfinished Car ({int(self.unfinished_car_depth)}) + "
                    f"2 x Door ({int(self.door_panel_thickness)}) + "
                    f"Gap ({int(config.DEFAULT_DOOR_GAP)}) + "
                    f"Rear Clearance ({int(config.DEFAULT_REAR_CLEARANCE)})")

    def __post_init__(self):
        """Validate and configure lift settings. Collects all errors and reports them together."""
        errors = []

        # Fire lift cabin size validation
        if self.lift_type == "fire":
            size = (int(self.finished_car_width), int(self.finished_car_depth))
            if size not in FIRE_LIFT_CABIN_SIZES:
                valid = ", ".join(f"{w}x{d}" for w, d in FIRE_LIFT_CABIN_SIZES)
                errors.append(
                    f"Fire lift must use one of these cabin sizes (WxD): {valid}. "
                    f"Got: {size[0]}x{size[1]}"
                )
            # Set fire lift door width
            self.door_width = config.FIRE_LIFT_DOOR_WIDTH

        # Validate door_opening_type
        if self.door_opening_type not in ("centre", "telescopic"):
            errors.append(
                f"door_opening_type must be 'centre' or 'telescopic', got '{self.door_opening_type}'."
            )
        if self.door_opening_type == "telescopic" and self.lift_type != "fire":
            errors.append("Telescopic door opening is only available for fire lifts.")

        # Auto-calculate telescopic extensions if not provided
        if self.door_opening_type == "telescopic":
            if self.telescopic_left_ext is None:
                self.telescopic_left_ext = 0.5 * self.door_width + config.TELESCOPIC_LEFT_EXTENSION_EXTRA
            if self.telescopic_right_ext is None:
                self.telescopic_right_ext = config.TELESCOPIC_RIGHT_EXTENSION

        # Validate bracket dimensions meet minimums
        if self.lift_machine_type == "mrl":
            if self.counterweight_bracket_width < config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH:
                errors.append(
                    f"CW Bracket Width ({int(self.counterweight_bracket_width)}mm) is below minimum "
                    f"({int(config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH)}mm)."
                )
            if self.car_bracket_width < config.DEFAULT_CAR_BRACKET_WIDTH:
                errors.append(
                    f"Car Bracket Width ({int(self.car_bracket_width)}mm) is below minimum "
                    f"({int(config.DEFAULT_CAR_BRACKET_WIDTH)}mm)."
                )
        else:  # MRA
            if self.mra_car_bracket_width < config.MRA_CAR_BRACKET_WIDTH:
                errors.append(
                    f"Left Car Bracket ({int(self.mra_car_bracket_width)}mm) is below minimum "
                    f"({int(config.MRA_CAR_BRACKET_WIDTH)}mm)."
                )
            if self.mra_right_bracket_width < config.MRA_CAR_BRACKET_WIDTH:
                errors.append(
                    f"Right Car Bracket ({int(self.mra_right_bracket_width)}mm) is below minimum "
                    f"({int(config.MRA_CAR_BRACKET_WIDTH)}mm)."
                )
            if self.mra_cw_bracket_depth < config.MRA_CW_BRACKET_DEPTH:
                errors.append(
                    f"CW Bracket Depth ({int(self.mra_cw_bracket_depth)}mm) is below minimum "
                    f"({int(config.MRA_CW_BRACKET_DEPTH)}mm)."
                )

        # Validate shaft width override
        if self.shaft_width_override is not None:
            if self.shaft_width_override < self.min_shaft_width:
                errors.append(
                    f"Shaft Width ({int(self.shaft_width_override)}mm) is below minimum "
                    f"({int(self.min_shaft_width)}mm). Minimum = {self._width_breakdown_str()}"
                )
            # Fire lift minimum shaft width
            if self.lift_type == "fire":
                fire_min_w = (config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC
                              if self.door_opening_type == "telescopic"
                              else config.FIRE_LIFT_MIN_SHAFT_WIDTH)
                if self.shaft_width_override < fire_min_w:
                    errors.append(
                        f"Fire lift Shaft Width ({int(self.shaft_width_override)}mm) is below "
                        f"fire lift minimum ({int(fire_min_w)}mm)."
                    )
            # Structural opening must fit within shaft width
            if self.shaft_width_override < self.structural_opening_width:
                errors.append(
                    f"Structural Opening Width ({int(self.structural_opening_width)}mm) exceeds "
                    f"Shaft Width ({int(self.shaft_width_override)}mm)."
                )

        # Validate shaft depth override
        if self.shaft_depth_override is not None:
            if self.shaft_depth_override < self.min_shaft_depth:
                errors.append(
                    f"Shaft Depth ({int(self.shaft_depth_override)}mm) is below minimum "
                    f"({int(self.min_shaft_depth)}mm). Minimum = {self._depth_breakdown_str()}"
                )
            # MRL: check minimum rear clearance
            if self.lift_machine_type == "mrl":
                actual_rear = config.DEFAULT_REAR_CLEARANCE + (self.shaft_depth_override - self.min_shaft_depth) if self.shaft_depth_override >= self.min_shaft_depth else config.DEFAULT_REAR_CLEARANCE - (self.min_shaft_depth - self.shaft_depth_override)
                if actual_rear < config.MIN_REAR_CLEARANCE:
                    errors.append(
                        f"MRL Rear Clearance ({int(actual_rear)}mm) is below minimum "
                        f"({int(config.MIN_REAR_CLEARANCE)}mm)."
                    )

        # Validate door width fits structural opening
        if self.door_width > self.structural_opening_width:
            errors.append(
                f"Door Width ({int(self.door_width)}mm) exceeds "
                f"Structural Opening Width ({int(self.structural_opening_width)}mm)."
            )

        if errors:
            error_list = "\n  - ".join(errors)
            raise ValueError(f"LiftConfig validation failed:\n  - {error_list}")


def validate_fire_lift_positions(lifts: List[LiftConfig]) -> None:
    """
    Ensure fire lifts are only at position 0 (first position).

    Args:
        lifts: List of lift configurations

    Raises:
        ValueError: If a fire lift is not at position 0
    """
    for idx, lift in enumerate(lifts):
        if lift.lift_type == "fire" and idx != 0:
            raise ValueError(
                f"Fire lift at position {idx} is invalid. "
                f"Fire lifts must be at position 0 (first position)."
            )


def determine_separator_type(lifts: List[LiftConfig], is_common_shaft: bool) -> str:
    """
    Determine the separator type based on lift configuration.

    Rules:
    - Multiple passenger lifts in common shaft -> Steel separator beam (150mm)
    - Fire lift present -> RCC wall (200mm)
    - Separate shafts -> RCC wall (standard)

    Args:
        lifts: List of lift configurations
        is_common_shaft: Whether lifts share a common shaft

    Returns:
        "steel_beam" or "rcc_wall"
    """
    if not is_common_shaft:
        return "rcc_wall"  # Separate shafts use RCC

    lift_types = [lift.lift_type for lift in lifts]

    if "fire" in lift_types:
        return "rcc_wall"  # Fire lift requires RCC wall (200mm)
    else:
        return "steel_beam"  # All passenger lifts use steel beam (150mm)


class LiftShaftSketch:
    """
    Generator for lift shaft plan diagrams.

    Supports single lifts and multi-lift banks with configurable dimensions.
    Outputs high-quality PNG images suitable for technical documentation.

    Enhanced API supports lift car interiors, brackets, and separator types.
    """

    def __init__(
        self,
        # Simple API parameters (backward compatible)
        shaft_width: float = None,
        shaft_depth: float = None,
        wall_thickness: float = None,
        door_width: float = None,
        door_height: float = None,
        structural_opening_width: float = None,
        structural_opening_height: float = None,
        num_lifts: int = 1,
        shared_wall_thickness: float = None,
        # Enhanced API parameters
        lifts: List[LiftConfig] = None,
        lifts_bank2: List[LiftConfig] = None,  # Second bank for facing arrangement
        lobby_width: float = None,  # Gap between facing banks
        is_common_shaft: bool = False,
        steel_beam_width: float = None,
    ):
        """
        Initialize lift shaft sketch generator.

        Simple API (backward compatible):
            shaft_width: Internal width of shaft (mm)
            shaft_depth: Internal depth of shaft (mm)
            wall_thickness: RCC wall thickness (mm)
            door_width: Lift door opening width (mm)
            door_height: Lift door opening height (mm) - for reference
            structural_opening_width: Front wall structural opening width (mm)
            structural_opening_height: Front wall structural opening height (mm)
            num_lifts: Number of adjacent lifts (1, 2, 3, ...)
            shared_wall_thickness: Dividing wall between lifts (mm)

        Enhanced API:
            lifts: List of LiftConfig objects for Bank 1 (top in facing arrangement)
            lifts_bank2: List of LiftConfig objects for Bank 2 (bottom, facing Bank 1)
            lobby_width: Gap between facing banks (mm)
            is_common_shaft: Whether lifts share a common shaft (affects separator)
            steel_beam_width: Width of steel separator beam (mm)

        Facing Arrangement:
            - If lifts_bank2 is provided with at least one lift, facing arrangement is used
            - Bank 1 (lifts) is drawn at top with doors facing down toward lobby
            - Bank 2 (lifts_bank2) is drawn at bottom with doors facing up toward lobby
            - Max 4 lifts per bank, max 8 lifts total
        """
        # Validate lift counts per bank
        if lifts and len(lifts) > 4:
            raise ValueError("Max 4 lifts per bank (Bank 1 has {})".format(len(lifts)))
        if lifts_bank2 and len(lifts_bank2) > 4:
            raise ValueError("Max 4 lifts per bank (Bank 2 has {})".format(len(lifts_bank2)))

        # Determine if facing arrangement
        self._is_facing = lifts_bank2 is not None and len(lifts_bank2) > 0

        self.lifts = lifts
        self.lifts_bank2 = lifts_bank2 if self._is_facing else None
        self.lobby_width = lobby_width or config.DEFAULT_LOBBY_WIDTH
        self.is_common_shaft = is_common_shaft
        self.steel_beam_width = steel_beam_width or config.DEFAULT_STEEL_BEAM_WIDTH

        # Determine if using enhanced or simple API
        self._use_enhanced_api = lifts is not None and len(lifts) > 0

        if self._use_enhanced_api:
            # Enhanced API mode
            self.num_lifts = len(lifts)
            self._machine_type = lifts[0].lift_machine_type  # Store machine type for drawing

            # Validate fire lift positions (must be at position 0)
            validate_fire_lift_positions(lifts)

            # Calculate per-lift shaft depths (uses effective_shaft_depth for MRL override support)
            self._shaft_depths = [lift.effective_shaft_depth for lift in lifts]

            # Max depth for outer envelope (used for total_depth calculation and common shaft)
            if shaft_depth:
                # User provided explicit shaft depth - use for all
                self.shaft_depth = shaft_depth
                self._shaft_depths = [shaft_depth] * len(lifts)
            else:
                self.shaft_depth = max(self._shaft_depths)

            self._max_shaft_depth = self.shaft_depth
            self.wall_thickness = wall_thickness or config.DEFAULT_WALL_THICKNESS

            # Determine separator type
            self._separator_type = determine_separator_type(lifts, is_common_shaft)
            if self._separator_type == "steel_beam":
                self.shared_wall_thickness = self.steel_beam_width
            else:
                # For RCC separators: use explicit shared_wall_thickness, else wall_thickness, else default
                self.shared_wall_thickness = shared_wall_thickness or self.wall_thickness

            # Store individual shaft widths from lift configs
            self._shaft_widths = [lift.shaft_width for lift in lifts]
            self.shaft_width = self._shaft_widths[0]  # Primary shaft width

            # Initialize Bank 2 if facing arrangement
            if self._is_facing:
                self.num_lifts_bank2 = len(lifts_bank2)

                # Validate fire lift positions in Bank 2
                validate_fire_lift_positions(lifts_bank2)

                # Calculate per-lift shaft depths for Bank 2 (uses effective_shaft_depth for MRL override support)
                self._shaft_depths_bank2 = [lift.effective_shaft_depth for lift in lifts_bank2]

                self._max_shaft_depth_bank2 = max(self._shaft_depths_bank2)
                self._shaft_widths_bank2 = [lift.shaft_width for lift in lifts_bank2]

                # Determine separator type for Bank 2
                self._separator_type_bank2 = determine_separator_type(lifts_bank2, is_common_shaft)
                if self._separator_type_bank2 == "steel_beam":
                    self.shared_wall_thickness_bank2 = self.steel_beam_width
                else:
                    # For RCC separators: use explicit shared_wall_thickness, else wall_thickness, else default
                    self.shared_wall_thickness_bank2 = shared_wall_thickness or self.wall_thickness
            else:
                self.num_lifts_bank2 = 0
                self._shaft_depths_bank2 = []
                self._shaft_widths_bank2 = []
                self._max_shaft_depth_bank2 = 0
                self.shared_wall_thickness_bank2 = 0
        else:
            # Simple API mode (backward compatible)
            self._machine_type = "mrl"  # Default to MRL for simple API
            self.shaft_width = shaft_width or config.DEFAULT_SHAFT_WIDTH
            self.shaft_depth = shaft_depth or config.DEFAULT_SHAFT_DEPTH
            self.wall_thickness = wall_thickness or config.DEFAULT_WALL_THICKNESS
            self.door_width = door_width or config.DEFAULT_DOOR_WIDTH
            self.door_height = door_height or config.DEFAULT_DOOR_HEIGHT
            self.structural_opening_width = structural_opening_width or config.DEFAULT_STRUCTURAL_OPENING_WIDTH
            self.structural_opening_height = structural_opening_height or config.DEFAULT_STRUCTURAL_OPENING_HEIGHT
            self.num_lifts = max(1, num_lifts)
            self.shared_wall_thickness = shared_wall_thickness or config.DEFAULT_SHARED_WALL_THICKNESS
            self._separator_type = "rcc_wall"
            self._shaft_widths = [self.shaft_width] * self.num_lifts
            self._shaft_depths = [self.shaft_depth] * self.num_lifts
            self._max_shaft_depth = self.shaft_depth

        # Calculate total dimensions
        self._calculate_geometry()

    def _calculate_geometry(self) -> None:
        """Calculate all geometry based on parameters."""
        wt = self.wall_thickness

        # Calculate Bank 1 width
        if self.num_lifts == 1:
            bank1_width = self._shaft_widths[0] + 2 * wt
        else:
            bank1_width = (
                2 * wt
                + sum(self._shaft_widths)
                + (self.num_lifts - 1) * self.shared_wall_thickness
            )

        if self._is_facing:
            # Calculate Bank 2 width
            if self.num_lifts_bank2 == 1:
                bank2_width = self._shaft_widths_bank2[0] + 2 * wt
            else:
                bank2_width = (
                    2 * wt
                    + sum(self._shaft_widths_bank2)
                    + (self.num_lifts_bank2 - 1) * self.shared_wall_thickness_bank2
                )

            # Total width = max of both banks (they stack vertically)
            self.total_width = max(bank1_width, bank2_width)

            # Store individual bank widths for drawing
            self._bank1_width = bank1_width
            self._bank2_width = bank2_width

            # Total depth = bank1_depth + lobby + bank2_depth
            bank1_depth = self._max_shaft_depth + 2 * wt
            bank2_depth = self._max_shaft_depth_bank2 + 2 * wt

            self.total_depth = bank1_depth + self.lobby_width + bank2_depth

            # Store bank Y positions (bottom edges)
            # Bank 2 is at bottom (y=0), Bank 1 is at top
            self._bank2_y = 0
            self._bank1_y = bank2_depth + self.lobby_width
        else:
            # Inline arrangement (current behavior)
            self.total_width = bank1_width
            self.total_depth = self.shaft_depth + 2 * wt
            self._bank1_width = bank1_width
            self._bank2_width = 0
            self._bank1_y = 0
            self._bank2_y = 0

    def generate(
        self,
        output_path: str,
        show_hatching: bool = True,
        show_dimensions: bool = True,
        show_centerlines: bool = False,
        show_car_interior: bool = True,
        show_brackets: bool = True,
        show_door_panels: bool = True,
        show_capacity: bool = False,
        show_accessibility: bool = False,
        show_lift_doors: bool = True,
        title: str = None,
        subtitle: Optional[str] = None,
        dpi: int = None,
    ) -> str:
        """
        Generate the sketch and save to file.

        Args:
            output_path: Path to save PNG file
            show_hatching: Draw concrete hatch pattern
            show_dimensions: Show dimension annotations
            show_centerlines: Show car/door centerlines
            show_car_interior: Show lift car inside shaft
            show_brackets: Show counterweight/car brackets
            show_door_panels: Show door panel divisions
            show_capacity: Show capacity label
            show_accessibility: Show accessibility symbol
            show_lift_doors: Show landing and car doors with neck extension
            title: Drawing title text
            subtitle: Subtitle/notes text
            dpi: Output image resolution

        Returns:
            Absolute path to the generated file
        """
        display_options = {
            "show_hatching": show_hatching,
            "show_dimensions": show_dimensions,
            "show_centerlines": show_centerlines,
            "show_car_interior": show_car_interior,
            "show_brackets": show_brackets,
            "show_door_panels": show_door_panels,
            "show_capacity": show_capacity,
            "show_accessibility": show_accessibility,
            "show_lift_doors": show_lift_doors,
        }

        fig, ax = self._create_figure()
        self._draw_sketch(ax, title, subtitle, display_options)

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
        show_centerlines: bool = False,
        show_car_interior: bool = True,
        show_brackets: bool = True,
        show_door_panels: bool = True,
        show_capacity: bool = True,
        show_accessibility: bool = True,
        show_lift_doors: bool = True,
        title: str = None,
        subtitle: Optional[str] = None,
        dpi: int = None,
    ) -> bytes:
        """
        Return PNG as bytes (for API responses).

        Args:
            show_hatching: Draw concrete hatch pattern
            show_dimensions: Show dimension annotations
            show_centerlines: Show car/door centerlines
            show_car_interior: Show lift car inside shaft
            show_brackets: Show counterweight/car brackets
            show_door_panels: Show door panel divisions
            show_capacity: Show capacity label
            show_accessibility: Show accessibility symbol
            show_lift_doors: Show landing and car doors with neck extension
            title: Drawing title text
            subtitle: Subtitle/notes text
            dpi: Output image resolution

        Returns:
            PNG image as bytes
        """
        display_options = {
            "show_hatching": show_hatching,
            "show_dimensions": show_dimensions,
            "show_centerlines": show_centerlines,
            "show_car_interior": show_car_interior,
            "show_brackets": show_brackets,
            "show_door_panels": show_door_panels,
            "show_capacity": show_capacity,
            "show_accessibility": show_accessibility,
            "show_lift_doors": show_lift_doors,
        }

        fig, ax = self._create_figure()
        self._draw_sketch(ax, title, subtitle, display_options)

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
        """Create matplotlib figure and axes."""
        fig, ax = plt.subplots(
            figsize=(config.DEFAULT_FIGURE_WIDTH, config.DEFAULT_FIGURE_HEIGHT)
        )
        ax.set_aspect("equal")
        ax.axis("off")
        return fig, ax

    def _draw_sketch(
        self,
        ax: plt.Axes,
        title: str,
        subtitle: Optional[str],
        display_options: dict,
    ) -> None:
        """Draw the complete shaft sketch."""
        # Draw based on arrangement type
        if self._is_facing:
            self._draw_facing_banks(ax, display_options)
        elif self.num_lifts == 1:
            self._draw_single_lift(ax, display_options)
        else:
            self._draw_multi_lift_bank(ax, display_options)

        # Set axis limits with margin for dimensions
        top_margin = 1000  # Extra space for top dimensions (offset 850 + buffer)
        bottom_margin = 1200  # Extra space for bottom dimensions
        right_margin = 1500  # Extra space for right depth dimensions (when depths differ)
        left_margin = 1500  # Extra space for left depth dimensions (3 levels)
        ax.set_xlim(-left_margin, self.total_width + right_margin)
        ax.set_ylim(-bottom_margin, self.total_depth + top_margin)

    def _draw_single_lift(
        self,
        ax: plt.Axes,
        display_options: dict,
    ) -> None:
        """Draw a single lift shaft plan."""
        wt = self.wall_thickness
        sw = self._shaft_widths[0]
        sd = self.shaft_depth

        # Get structural opening width from lift config or defaults
        if self._use_enhanced_api and self.lifts:
            sow = self.lifts[0].structural_opening_width
            dw = self.lifts[0].door_width
        else:
            sow = self.structural_opening_width
            dw = self.door_width

        # Draw shaft interior first (background)
        draw_shaft_interior(ax, wt, wt, sw, sd)

        # Draw lift interior components (brackets, car)
        if self._use_enhanced_api and self.lifts:
            self._draw_lift_interior(ax, wt, wt, self.lifts[0], display_options)

        # Draw walls
        # Left wall
        draw_wall_section(ax, 0, 0, wt, self.total_depth, display_options["show_hatching"])
        # Right wall
        draw_wall_section(ax, wt + sw, 0, wt, self.total_depth, display_options["show_hatching"])
        # Back wall
        draw_wall_section(ax, wt, wt + sd, sw, wt, display_options["show_hatching"])

        # Front wall with opening
        # Calculate opening position - center on cabin if enhanced API, otherwise shaft-centered
        if self._use_enhanced_api and self.lifts:
            lift = self.lifts[0]
            if lift.lift_machine_type == "mra":
                # MRA: center car in available space between brackets
                left_cb = lift.mra_car_bracket_width
                right_cb = lift.mra_right_bracket_width
                uc_width = lift.unfinished_car_width
                available = sw - left_cb - right_cb
                car_center_x = wt + left_cb + (available - uc_width) / 2 + uc_width / 2
            else:
                # MRL: center car in available space between brackets
                cwb_width = lift.counterweight_bracket_width
                cb_width = lift.car_bracket_width
                uc_width = lift.unfinished_car_width
                available = sw - cwb_width - cb_width
                car_center_x = wt + cwb_width + (available - uc_width) / 2 + uc_width / 2

            # For fire lifts, center door/opening on shaft (not car) to avoid wall overlap
            if lift.lift_type == "fire":
                door_center_x = wt + sw / 2  # Shaft center
            else:
                door_center_x = car_center_x  # Car center

            opening_x = door_center_x - sow / 2
        else:
            # Simple API: center opening on shaft
            opening_x = wt + (sw - sow) / 2
            car_center_x = wt + sw / 2  # Shaft center as fallback
            door_center_x = car_center_x

        # Left part of front wall
        if opening_x > wt:
            draw_wall_section(ax, wt, 0, opening_x - wt, wt, display_options["show_hatching"])
        # Right part of front wall
        right_wall_x = opening_x + sow
        if right_wall_x < wt + sw:
            draw_wall_section(ax, right_wall_x, 0, wt + sw - right_wall_x, wt, display_options["show_hatching"])

        # Draw opening
        draw_opening(ax, opening_x, 0, sow, wt)

        # Draw door jambs at structural opening edges (only when doors are shown)
        if self._use_enhanced_api and display_options.get("show_lift_doors", False):
            draw_door_jambs(ax, opening_x, wt, sow)

        # Draw door panels - center on shaft for fire lifts, cabin for others
        if display_options["show_door_panels"]:
            door_x = door_center_x - dw / 2
            draw_door_panels(ax, door_x, 0, dw, wt, num_panels=config.DEFAULT_DOOR_PANELS)

        # Draw dimensions
        if display_options["show_dimensions"]:
            self._draw_single_lift_dimensions(ax)

        # Draw centerlines
        if display_options["show_centerlines"]:
            # Vertical centerline through shaft center
            center_x = wt + sw / 2
            draw_centerline(ax, (center_x, 0), (center_x, self.total_depth))
            # Horizontal centerline through shaft center
            center_y = wt + sd / 2
            draw_centerline(ax, (0, center_y), (self.total_width, center_y))

    def _draw_lift_interior(
        self,
        ax: plt.Axes,
        shaft_x: float,
        shaft_y: float,
        lift_config: LiftConfig,
        display_options: dict,
        mirror: bool = False,
        shaft_depth: float = None,
    ) -> None:
        """
        Draw the interior components of a lift shaft.

        Dispatches to MRL or MRA-specific drawing based on lift_machine_type.

        Args:
            ax: Matplotlib axes
            shaft_x: Left x coordinate of shaft interior
            shaft_y: Bottom y coordinate of shaft interior
            lift_config: Lift configuration
            display_options: Display options dictionary
            mirror: If True, place counterweight on right side instead of left (MRL only)
            shaft_depth: This lift's shaft depth (for positioning). If None, uses self.shaft_depth.
        """
        # Use provided shaft_depth or fall back to self.shaft_depth
        sd = shaft_depth if shaft_depth is not None else self.shaft_depth

        # Dispatch to MRA-specific drawing if machine type is MRA
        if lift_config.lift_machine_type == "mra":
            self._draw_lift_interior_mra(ax, shaft_x, shaft_y, lift_config, display_options, shaft_depth=sd)
            return

        # MRL drawing (original code)
        cwb_width = lift_config.counterweight_bracket_width
        cb_width = lift_config.car_bracket_width
        uc_width = lift_config.unfinished_car_width
        uc_depth = lift_config.unfinished_car_depth
        fc_width = lift_config.finished_car_width
        fc_depth = lift_config.finished_car_depth
        sw = lift_config.shaft_width  # Respects override

        # Calculate car center position (center car in available space between brackets)
        if not mirror:
            available = sw - cwb_width - cb_width
            car_x_offset = cwb_width + (available - uc_width) / 2
            car_center_x = shaft_x + car_x_offset + uc_width / 2
        else:
            available = sw - cb_width - cwb_width
            car_x_offset = cb_width + (available - uc_width) / 2
            car_center_x = shaft_x + car_x_offset + uc_width / 2

        # For fire lifts, center doors on shaft (not car) to avoid wall overlap
        if lift_config.lift_type == "fire":
            door_center_x = shaft_x + lift_config.shaft_width / 2  # Shaft center
        else:
            door_center_x = car_center_x  # Car center

        # Draw lift doors first (if enabled)
        door_info = None
        if display_options.get("show_lift_doors", False):
            door_info = draw_lift_doors(
                ax,
                center_x=door_center_x,  # Shaft center for fire lifts, car center for others
                wall_inner_y=shaft_y,  # At y = wall_thickness (inner edge of front wall)
                door_width=lift_config.door_width,
                door_extension=lift_config.door_extension,
                door_thickness=lift_config.door_panel_thickness,
                door_opening_type=lift_config.door_opening_type,
                telescopic_left_ext=lift_config.telescopic_left_ext,
                telescopic_right_ext=lift_config.telescopic_right_ext,
            )

        # Draw counterweight bracket only (car bracket not shown)
        if display_options["show_brackets"]:
            bracket_height = sd * 0.7
            bracket_y = shaft_y + (sd - bracket_height) / 2

            if not mirror:
                # Normal: counterweight on left, align box to left edge
                draw_counterweight_bracket(ax, shaft_x, bracket_y, cwb_width, bracket_height, align="left")
            else:
                # Mirrored: counterweight on right, align box to right edge
                cw_bracket_x = shaft_x + cb_width + uc_width
                draw_counterweight_bracket(ax, cw_bracket_x, bracket_y, cwb_width, bracket_height, align="right")

            # Draw car bracket box (blue box on opposite side of counterweight)
            # Positioned against shaft wall
            car_bracket_box_y = shaft_y + (sd - config.CAR_BRACKET_BOX_HEIGHT) / 2
            if not mirror:
                # Normal: car bracket on right side - against right shaft wall
                car_bracket_box_x = shaft_x + sw - config.CAR_BRACKET_BOX_WIDTH
            else:
                # Mirrored: car bracket on left side - against left shaft wall
                car_bracket_box_x = shaft_x

            ax.add_patch(Rectangle(
                (car_bracket_box_x, car_bracket_box_y),
                config.CAR_BRACKET_BOX_WIDTH,
                config.CAR_BRACKET_BOX_HEIGHT,
                facecolor=config.CAR_BRACKET_BOX_COLOR,
                edgecolor="#000000",
                linewidth=0.8,
                zorder=3,
            ))

            # Draw CW-side car bracket (small bracket in gap between CW box and rail guide)
            # This bracket is positioned right after the CW box, before the car's rail guide
            cw_side_bracket_y = shaft_y + (sd - config.MRL_CW_SIDE_CAR_BRACKET_HEIGHT) / 2
            if not mirror:
                # Normal: CW box right edge is at shaft_x + (CW_BOX_WIDTH - CW_FRAME_THICKNESS)
                cw_side_bracket_x = shaft_x + (config.CW_BOX_WIDTH - config.CW_FRAME_THICKNESS)
            else:
                # Mirrored: CW is on right, bracket goes between car right rail and CW box left edge
                # CW box left edge: shaft_x + cb_width + uc_width + cwb_width - (CW_BOX_WIDTH - CW_FRAME_THICKNESS)
                cw_box_left_edge = shaft_x + cb_width + uc_width + cwb_width - (config.CW_BOX_WIDTH - config.CW_FRAME_THICKNESS)
                cw_side_bracket_x = cw_box_left_edge - config.MRL_CW_SIDE_CAR_BRACKET_WIDTH

            draw_car_bracket_cw_side(ax, cw_side_bracket_x, cw_side_bracket_y)

        # Draw lift car - position depends on mirror flag
        if display_options["show_car_interior"]:
            if not mirror:
                available_w = sw - cwb_width - cb_width
                car_x = shaft_x + cwb_width + (available_w - uc_width) / 2
            else:
                available_w = sw - cb_width - cwb_width
                car_x = shaft_x + cb_width + (available_w - uc_width) / 2
            # Front-fixed: extra depth goes to rear clearance
            door_zone = 2 * lift_config.door_panel_thickness + config.DEFAULT_DOOR_GAP
            car_y = shaft_y + door_zone

            draw_lift_car(
                ax,
                car_x,
                car_y,
                uc_width,
                uc_depth,
                fc_width,
                fc_depth,
            )

            # Draw car interior details
            finished_car_x = car_x + (uc_width - fc_width) / 2
            finished_car_y = car_y  # Same bottom as unfinished car

            draw_car_interior_details(
                ax,
                finished_car_x,
                finished_car_y,
                fc_width,
                fc_depth,
                capacity=lift_config.lift_capacity if display_options["show_capacity"] else None,
                show_cop=False,
                show_accessibility=display_options["show_accessibility"],
            )

    def _draw_lift_interior_mra(
        self,
        ax: plt.Axes,
        shaft_x: float,
        shaft_y: float,
        lift_config: LiftConfig,
        display_options: dict,
        shaft_depth: float = None,
    ) -> None:
        """
        Draw the interior components of a MRA (Machine Room Above) lift shaft.

        MRA differs from MRL:
        - CW bracket at TOP (rear of shaft in plan view)
        - Car brackets on BOTH left and right sides
        - Car centered horizontally between the two car brackets

        Args:
            ax: Matplotlib axes
            shaft_x: Left x coordinate of shaft interior
            shaft_y: Bottom y coordinate of shaft interior
            lift_config: Lift configuration
            display_options: Display options dictionary
            shaft_depth: This lift's shaft depth (for positioning). If None, uses self.shaft_depth.
        """
        # Use provided shaft_depth or fall back to self.shaft_depth
        sd = shaft_depth if shaft_depth is not None else self.shaft_depth

        left_cb = lift_config.mra_car_bracket_width
        right_cb = lift_config.mra_right_bracket_width
        cw_bracket_depth = lift_config.mra_cw_bracket_depth
        uc_width = lift_config.unfinished_car_width
        uc_depth = lift_config.unfinished_car_depth
        fc_width = lift_config.finished_car_width
        fc_depth = lift_config.finished_car_depth
        shaft_width = lift_config.shaft_width

        # Calculate car position (center car in available space between brackets)
        available_w = shaft_width - left_cb - right_cb
        car_x = shaft_x + left_cb + (available_w - uc_width) / 2
        car_center_x = car_x + uc_width / 2

        # Draw lift doors first (if enabled) - centered on car cabin
        if display_options.get("show_lift_doors", False):
            draw_lift_doors(
                ax,
                center_x=car_center_x,
                wall_inner_y=shaft_y,
                door_width=lift_config.door_width,
                door_extension=lift_config.door_extension,
                door_thickness=lift_config.door_panel_thickness,
                door_opening_type=lift_config.door_opening_type,
                telescopic_left_ext=lift_config.telescopic_left_ext,
                telescopic_right_ext=lift_config.telescopic_right_ext,
            )
        # Position car so bottom touches top of car door (like MRL)
        # Door area = 2 * door_thickness + door_gap
        car_y = shaft_y + 2 * lift_config.door_panel_thickness + config.DEFAULT_DOOR_GAP

        # Draw brackets (CW at top, car brackets on both sides)
        if display_options["show_brackets"]:
            # Draw CW bracket at top
            draw_counterweight_bracket_top(
                ax,
                shaft_x=shaft_x,
                shaft_y=shaft_y,
                shaft_width=shaft_width,
                shaft_depth=sd,
                cw_bracket_depth=cw_bracket_depth,
            )

            # Draw car brackets on both left and right sides (at car center height)
            draw_car_brackets_mra(
                ax,
                shaft_x=shaft_x,
                shaft_y=shaft_y,
                shaft_width=shaft_width,
                shaft_depth=sd,
                car_bracket_width=left_cb,
                car_y=car_y,
                car_depth=uc_depth,
            )

        # Draw lift car - centered horizontally
        if display_options["show_car_interior"]:

            draw_lift_car(
                ax,
                car_x,
                car_y,
                uc_width,
                uc_depth,
                fc_width,
                fc_depth,
            )

            # Draw car interior details
            finished_car_x = car_x + (uc_width - fc_width) / 2
            finished_car_y = car_y

            draw_car_interior_details(
                ax,
                finished_car_x,
                finished_car_y,
                fc_width,
                fc_depth,
                capacity=lift_config.lift_capacity if display_options["show_capacity"] else None,
                show_cop=False,
                show_accessibility=display_options["show_accessibility"],
            )

    def _draw_single_lift_dimensions(self, ax: plt.Axes) -> None:
        """Draw dimensions for single lift (internal dimensions only, positioned outside)."""
        wt = self.wall_thickness
        sw = self._shaft_widths[0]
        sd = self.shaft_depth

        # Get structural opening width
        if self._use_enhanced_api and self.lifts:
            sow = self.lifts[0].structural_opening_width
        else:
            sow = self.structural_opening_width

        # Reference positions for extension lines
        shaft_top_y = wt + sd  # Inner top edge of shaft
        shaft_right_x = wt + sw  # Inner right edge of shaft

        # Internal width dimension (top, level 1 - closest to drawing)
        # Extension lines start from inner shaft top edge
        draw_dimension_line(
            ax,
            start=(wt, shaft_top_y),
            end=(wt + sw, shaft_top_y),
            text=f"Shaft Width {int(sw)}",
            offset=250 + wt,  # Add wall thickness to keep dimension line at same position
            orientation="horizontal",
        )

        # Internal depth dimension (left side, level 1)
        # Extension lines start from inner shaft left edge, positioned outside left wall
        draw_dimension_line(
            ax,
            start=(wt, wt),
            end=(wt, wt + sd),
            text=f"Shaft Depth {int(sd)}",
            offset=-(wt + 250),  # Position outside left wall
            orientation="vertical",
        )

        # Get door width
        if self._use_enhanced_api and self.lifts:
            dw = self.lifts[0].door_width
        else:
            dw = self.door_width

        # Get door and structural opening heights
        if self._use_enhanced_api and self.lifts:
            dh = self.lifts[0].door_height
            soh = self.lifts[0].structural_opening_height
        else:
            dh = self.door_height
            soh = self.structural_opening_height

        # Calculate door center (same logic as _draw_single_lift)
        if self._use_enhanced_api and self.lifts:
            lift = self.lifts[0]
            if lift.lift_machine_type == "mra":
                # MRA: center car in available space between brackets
                left_cb = lift.mra_car_bracket_width
                right_cb = lift.mra_right_bracket_width
                uc_width = lift.unfinished_car_width
                available = sw - left_cb - right_cb
                car_center_x = wt + left_cb + (available - uc_width) / 2 + uc_width / 2
            else:
                # MRL: center car in available space between brackets
                cwb_width = lift.counterweight_bracket_width
                cb_width = lift.car_bracket_width
                uc_width = lift.unfinished_car_width
                available = sw - cwb_width - cb_width
                car_center_x = wt + cwb_width + (available - uc_width) / 2 + uc_width / 2

            # For fire lifts, door is centered on shaft (not car)
            if lift.lift_type == "fire":
                door_center_x = wt + sw / 2  # Shaft center
            else:
                door_center_x = car_center_x
        else:
            car_center_x = wt + sw / 2  # Shaft center as fallback
            door_center_x = car_center_x

        # Door width (bottom, level 1)
        door_x = door_center_x - dw / 2
        draw_dimension_line(
            ax,
            start=(door_x, 0),
            end=(door_x + dw, 0),
            text=f"Door Width {int(dw)}",
            offset=-150,
            orientation="horizontal",
        )

        # Door height label (below door width)
        door_center_x = door_x + dw / 2
        ax.text(
            door_center_x, -320,
            f"Height {int(dh)}",
            ha="center", va="top",
            fontsize=config.DIMENSION_TEXT_SIZE,
            color=config.DIMENSION_COLOR,
        )

        # Structural opening width (bottom, level 2) - centered on door
        opening_x = door_center_x - sow / 2
        draw_dimension_line(
            ax,
            start=(opening_x, 0),
            end=(opening_x + sow, 0),
            text=f"Structural Opening Width {int(sow)}",
            offset=-500,
            orientation="horizontal",
        )

        # Structural opening height label (below structural opening width)
        opening_center_x = opening_x + sow / 2
        ax.text(
            opening_center_x, -670,
            f"Height {int(soh)}",
            ha="center", va="top",
            fontsize=config.DIMENSION_TEXT_SIZE,
            color=config.DIMENSION_COLOR,
        )

        # Draw bracket and car dimensions if using enhanced API
        if self._use_enhanced_api and self.lifts:
            lift = self.lifts[0]

            # Calculate car positions based on machine type
            if lift.lift_machine_type == "mra":
                # MRA: center car in available space between brackets
                left_cb = lift.mra_car_bracket_width
                right_cb = lift.mra_right_bracket_width
                available_w = lift.shaft_width - left_cb - right_cb
                car_x = wt + left_cb + (available_w - lift.unfinished_car_width) / 2
                # MRA: car bottom touches top of car door
                car_y = wt + 2 * lift.door_panel_thickness + config.DEFAULT_DOOR_GAP
            else:
                # MRL: center car in available space between brackets
                cwb_w = lift.counterweight_bracket_width
                cb_w = lift.car_bracket_width
                available_w = lift.shaft_width - cwb_w - cb_w
                car_x = wt + cwb_w + (available_w - lift.unfinished_car_width) / 2
                # Front-fixed: extra depth goes to rear clearance
                car_y = wt + 2 * lift.door_panel_thickness + config.DEFAULT_DOOR_GAP

            finished_car_x = car_x + (lift.unfinished_car_width - lift.finished_car_width) / 2
            finished_car_y = car_y  # Same bottom as unfinished car

            # Calculate actual object edges for extension lines
            car_top_y = car_y + lift.unfinished_car_depth
            car_right_x = car_x + lift.unfinished_car_width
            finished_car_top_y = finished_car_y + lift.finished_car_depth
            finished_car_right_x = finished_car_x + lift.finished_car_width

            # Target dimension line positions (same as before)
            # Level 2: shaft_top_y + 550 + wt = wt + sd + 550 + wt
            # Level 3: shaft_top_y + 850 + wt = wt + sd + 850 + wt
            level2_target_y = shaft_top_y + 550 + wt
            level3_target_y = shaft_top_y + 850 + wt
            level2_target_x = shaft_right_x + 550 + wt
            level3_target_x = shaft_right_x + 850 + wt

            if lift.lift_machine_type == "mra":
                # MRA: Dynamic left bracket (shaft wall to car left edge)
                shaft_left_wall = wt
                left_cb = lift.mra_car_bracket_width
                right_cb = lift.mra_right_bracket_width
                available_w = lift.shaft_width - left_cb - right_cb
                car_left_edge = wt + left_cb + (available_w - lift.unfinished_car_width) / 2
                left_gap = car_left_edge - shaft_left_wall
                draw_dimension_line(
                    ax,
                    start=(shaft_left_wall, shaft_top_y),
                    end=(car_left_edge, shaft_top_y),
                    text=f"{int(left_gap)}",
                    offset=level2_target_y - shaft_top_y,
                    orientation="horizontal",
                )

                # MRA: Dynamic right bracket (car right edge to shaft wall)
                car_right_edge = car_left_edge + lift.unfinished_car_width
                shaft_right_wall = wt + lift.shaft_width
                right_gap = shaft_right_wall - car_right_edge
                draw_dimension_line(
                    ax,
                    start=(car_right_edge, shaft_top_y),
                    end=(shaft_right_wall, shaft_top_y),
                    text=f"{int(right_gap)}",
                    offset=level2_target_y - shaft_top_y,
                    orientation="horizontal",
                )
            else:
                # MRL: Counterweight bracket width (top, level 2)
                # Extension from shaft top edge
                draw_dimension_line(
                    ax,
                    start=(wt, shaft_top_y),
                    end=(wt + lift.counterweight_bracket_width, shaft_top_y),
                    text=f"{int(lift.counterweight_bracket_width)}",
                    offset=level2_target_y - shaft_top_y,
                    orientation="horizontal",
                )

                # MRL: Car bracket width (top, level 2)
                # Dimension from unfinished car right edge to shaft wall
                car_right_edge = wt + lift.counterweight_bracket_width + lift.unfinished_car_width
                shaft_wall_x = wt + lift.shaft_width
                bracket_gap = shaft_wall_x - car_right_edge
                draw_dimension_line(
                    ax,
                    start=(car_right_edge, shaft_top_y),
                    end=(shaft_wall_x, shaft_top_y),
                    text=f"{int(bracket_gap)}",
                    offset=level2_target_y - shaft_top_y,
                    orientation="horizontal",
                )

            # Finished car width (top, level 2 - closer to drawing)
            # Extension from finished car top edge
            draw_dimension_line(
                ax,
                start=(finished_car_x, finished_car_top_y),
                end=(finished_car_x + lift.finished_car_width, finished_car_top_y),
                text=f"Finished Car Width {int(lift.finished_car_width)}",
                offset=level2_target_y - finished_car_top_y,
                orientation="horizontal",
            )

            # Unfinished car width (top, level 3 - further from drawing)
            # Extension from car top edge
            draw_dimension_line(
                ax,
                start=(car_x, car_top_y),
                end=(car_x + lift.unfinished_car_width, car_top_y),
                text=f"Unfinished Car Width {int(lift.unfinished_car_width)}",
                offset=level3_target_y - car_top_y,
                orientation="horizontal",
            )

            # Finished car depth (left side, level 2)
            # Extension from finished car left edge, positioned outside left wall
            draw_dimension_line(
                ax,
                start=(finished_car_x, car_y),
                end=(finished_car_x, car_y + lift.finished_car_depth),
                text=f"Finished Car Depth {int(lift.finished_car_depth)}",
                offset=-(finished_car_x + 550),  # Position further outside left wall
                orientation="vertical",
            )

            # Unfinished car depth (left side, level 3)
            # Extension from unfinished car left edge, positioned further outside
            draw_dimension_line(
                ax,
                start=(car_x, car_y),
                end=(car_x, car_y + lift.unfinished_car_depth),
                text=f"Unfinished Car Depth {int(lift.unfinished_car_depth)}",
                offset=-(car_x + 850),  # Position even further outside left wall
                orientation="vertical",
            )

    def _draw_multi_lift_bank(
        self,
        ax: plt.Axes,
        display_options: dict,
    ) -> None:
        """Draw a multi-lift bank plan with support for dual boundary system."""
        wt = self.wall_thickness
        swt = self.shared_wall_thickness
        max_sd = self._max_shaft_depth  # Outer envelope depth

        # Check if depths differ (need L-shaped inner boundary)
        depths_differ = len(set(self._shaft_depths)) > 1

        # Track x position as we draw each lift
        x_pos = 0

        for lift_idx in range(self.num_lifts):
            is_first = lift_idx == 0
            is_last = lift_idx == self.num_lifts - 1
            sw = self._shaft_widths[lift_idx]
            sd = self._shaft_depths[lift_idx]  # This lift's actual depth

            # Get lift config if using enhanced API
            lift_config = self.lifts[lift_idx] if self._use_enhanced_api else None
            sow = lift_config.structural_opening_width if lift_config else self.structural_opening_width
            dw = lift_config.door_width if lift_config else self.door_width

            # Left wall (outer wall for first lift, shared wall/separator otherwise)
            if is_first:
                # Left outer wall - use first lift's depth for L-shape
                first_depth = self._shaft_depths[0]
                draw_wall_section(ax, x_pos, 0, wt, first_depth + 2 * wt, display_options["show_hatching"])
                shaft_left = x_pos + wt
            else:
                # Draw separator (steel beam or RCC wall)
                # Use min of adjacent shaft depths for L-shaped walls
                prev_depth = self._shaft_depths[lift_idx - 1]
                curr_depth = sd
                separator_depth = min(prev_depth, curr_depth)  # Separator extends to shallower depth

                if self._separator_type == "steel_beam":
                    draw_steel_beam(
                        ax, x_pos, wt, swt, separator_depth,  # Use min depth for separator
                        label=None  # Label drawn above top dimension instead
                    )
                    # Draw wall sections above and below steel beam
                    draw_wall_section(ax, x_pos, 0, swt, wt, display_options["show_hatching"])
                    draw_wall_section(ax, x_pos, wt + separator_depth, swt, wt, display_options["show_hatching"])

                    # L-shape: If previous shaft is deeper, continue fire shaft's right wall
                    if prev_depth > curr_depth:
                        # Vertical wall piece from separator end to fire's back wall
                        wall_start_y = wt + separator_depth + wt  # Below separator's back wall piece
                        wall_height = prev_depth - separator_depth  # Difference in depths
                        draw_wall_section(ax, x_pos, wall_start_y, wt, wall_height, display_options["show_hatching"])

                    # L-shape: If current shaft is deeper, extend current shaft's left wall
                    if curr_depth > prev_depth:
                        wall_start_y = wt + separator_depth + wt  # Below separator's back wall piece
                        wall_height = curr_depth - separator_depth
                        # Draw on RIGHT side of separator (left wall of current/deeper shaft)
                        draw_wall_section(ax, x_pos + swt - wt, wall_start_y, wt, wall_height, display_options["show_hatching"])
                else:
                    # RCC wall with hatching - extends to shallower depth
                    draw_wall_section(ax, x_pos, 0, swt, separator_depth + 2 * wt, display_options["show_hatching"])

                    # L-shape: If previous shaft is deeper, continue fire shaft's right wall
                    if prev_depth > curr_depth:
                        # Vertical wall piece from separator end to fire's back wall
                        wall_start_y = separator_depth + 2 * wt  # Below separator
                        wall_height = prev_depth - separator_depth  # Difference in depths
                        draw_wall_section(ax, x_pos, wall_start_y, wt, wall_height, display_options["show_hatching"])

                    # L-shape: If current shaft is deeper, extend current shaft's left wall
                    if curr_depth > prev_depth:
                        wall_start_y = separator_depth + 2 * wt  # Below separator
                        wall_height = curr_depth - separator_depth
                        # Draw on RIGHT side of separator (left wall of current/deeper shaft)
                        draw_wall_section(ax, x_pos + swt - wt, wall_start_y, wt, wall_height, display_options["show_hatching"])

                shaft_left = x_pos + swt

            # Draw shaft interior at this lift's actual depth
            draw_shaft_interior(ax, shaft_left, wt, sw, sd)

            # Draw lift interior components
            # Mirror odd-indexed lifts (right side lifts have counterweight on right)
            if self._use_enhanced_api and lift_config:
                mirror = (lift_idx % 2 == 1)
                self._draw_lift_interior(ax, shaft_left, wt, lift_config, display_options, mirror=mirror, shaft_depth=sd)

            # Front wall with opening
            # Calculate opening position - center on cabin if enhanced API, otherwise shaft-centered
            # Fire lifts: always center on shaft to avoid wall overlap
            if self._use_enhanced_api and lift_config:
                if lift_config.lift_machine_type == "mra":
                    # MRA: center car in available space between brackets
                    left_cb = lift_config.mra_car_bracket_width
                    right_cb = lift_config.mra_right_bracket_width
                    uc_width = lift_config.unfinished_car_width
                    available = sw - left_cb - right_cb
                    car_center_x = shaft_left + left_cb + (available - uc_width) / 2 + uc_width / 2
                else:
                    # MRL: center car in available space between brackets
                    cwb_width = lift_config.counterweight_bracket_width
                    cb_width = lift_config.car_bracket_width
                    uc_width = lift_config.unfinished_car_width
                    mirror = (lift_idx % 2 == 1)
                    if not mirror:
                        available = sw - cwb_width - cb_width
                        car_center_x = shaft_left + cwb_width + (available - uc_width) / 2 + uc_width / 2
                    else:
                        available = sw - cb_width - cwb_width
                        car_center_x = shaft_left + cb_width + (available - uc_width) / 2 + uc_width / 2

                # For fire lifts, center door/opening on shaft (not car) to avoid wall overlap
                if lift_config.lift_type == "fire":
                    door_center_x = shaft_left + sw / 2  # Shaft center
                else:
                    door_center_x = car_center_x  # Car center

                opening_x = door_center_x - sow / 2
            else:
                # Simple API: center opening on shaft
                opening_x = shaft_left + (sw - sow) / 2
                car_center_x = shaft_left + sw / 2  # Shaft center as fallback
                door_center_x = car_center_x

            # Left part of front wall
            front_wall_left = shaft_left
            if opening_x > front_wall_left:
                draw_wall_section(ax, front_wall_left, 0, opening_x - front_wall_left, wt, display_options["show_hatching"])

            # Right part of front wall
            right_wall_x = opening_x + sow
            front_wall_right = shaft_left + sw
            if right_wall_x < front_wall_right:
                draw_wall_section(ax, right_wall_x, 0, front_wall_right - right_wall_x, wt, display_options["show_hatching"])

            # Draw opening
            draw_opening(ax, opening_x, 0, sow, wt)

            # Draw door jambs at structural opening edges (only when doors are shown)
            if self._use_enhanced_api and display_options.get("show_lift_doors", False):
                draw_door_jambs(ax, opening_x, wt, sow)

            # Draw door panels - center on shaft for fire lifts, cabin for others
            if display_options["show_door_panels"]:
                door_x = door_center_x - dw / 2
                draw_door_panels(ax, door_x, 0, dw, wt, num_panels=config.DEFAULT_DOOR_PANELS)

            # Back wall for this lift at its own depth
            draw_wall_section(ax, shaft_left, wt + sd, sw, wt, display_options["show_hatching"])

            # L-shaped walls: Do NOT draw envelope back wall at max depth for shallower shafts
            # Each shaft's back wall is at its own depth, creating an L-shape when depths differ

            # Draw centerlines for this lift - extend to each shaft's own depth
            if display_options["show_centerlines"]:
                center_x = shaft_left + sw / 2
                draw_centerline(ax, (center_x, 0), (center_x, sd + 2 * wt))

            # Update x position
            if is_first:
                x_pos = wt + sw
            else:
                x_pos = shaft_left + sw

        # Draw right outer wall - use last lift's depth for L-shape
        last_depth = self._shaft_depths[-1]
        draw_wall_section(ax, x_pos, 0, wt, last_depth + 2 * wt, display_options["show_hatching"])

        # Horizontal centerline
        if display_options["show_centerlines"]:
            center_y = wt + max_sd / 2
            draw_centerline(ax, (0, center_y), (self.total_width, center_y))

        # Draw dimensions
        if display_options["show_dimensions"]:
            self._draw_multi_lift_dimensions(ax)

    def _draw_multi_lift_dimensions(self, ax: plt.Axes) -> None:
        """Draw dimensions for multi-lift bank (internal dimensions only, positioned outside)."""
        wt = self.wall_thickness
        swt = self.shared_wall_thickness
        max_sd = self._max_shaft_depth  # Use max depth for positioning

        # Check if depths differ (for individual depth annotations)
        depths_differ = len(set(self._shaft_depths)) > 1

        # Individual shaft width dimensions (top, outside the drawing)
        x_pos = wt
        for lift_idx in range(self.num_lifts):
            sw = self._shaft_widths[lift_idx]
            sd = self._shaft_depths[lift_idx]  # This lift's actual depth
            shaft_left = x_pos

            # Get lift config and structural opening width
            if self._use_enhanced_api and self.lifts:
                lift = self.lifts[lift_idx]
                sow = lift.structural_opening_width
            else:
                lift = None
                sow = self.structural_opening_width

            # Shaft width (level 1)
            # Extension from inner shaft top edge (use max_sd for consistent dimension line position)
            shaft_top_y = wt + max_sd
            draw_dimension_line(
                ax,
                start=(shaft_left, shaft_top_y),
                end=(shaft_left + sw, shaft_top_y),
                text=f"Shaft Width {int(sw)}",
                offset=250 + wt,  # Add wall thickness to keep dimension line outside
                orientation="horizontal",
            )

            # Get door width and heights for this lift
            if lift:
                dw = lift.door_width
                dh = lift.door_height
                soh = lift.structural_opening_height
            else:
                dw = self.door_width
                dh = self.door_height
                soh = self.structural_opening_height

            # Calculate cabin center based on mirror state (same as _draw_multi_lift)
            if self._use_enhanced_api and lift:
                if lift.lift_machine_type == "mra":
                    # MRA: center car in available space between brackets
                    left_cb = lift.mra_car_bracket_width
                    right_cb = lift.mra_right_bracket_width
                    uc_width = lift.unfinished_car_width
                    available = sw - left_cb - right_cb
                    car_center_x = shaft_left + left_cb + (available - uc_width) / 2 + uc_width / 2
                else:
                    # MRL: center car in available space between brackets
                    cwb_width = lift.counterweight_bracket_width
                    cb_width = lift.car_bracket_width
                    uc_width = lift.unfinished_car_width
                    mirror = (lift_idx % 2 == 1)
                    if not mirror:
                        available = sw - cwb_width - cb_width
                        car_center_x = shaft_left + cwb_width + (available - uc_width) / 2 + uc_width / 2
                    else:
                        available = sw - cb_width - cwb_width
                        car_center_x = shaft_left + cb_width + (available - uc_width) / 2 + uc_width / 2

                # For fire lifts, center door/opening on shaft (not car)
                if lift.lift_type == "fire":
                    door_center_x = shaft_left + sw / 2  # Shaft center
                else:
                    door_center_x = car_center_x  # Car center
            else:
                car_center_x = shaft_left + sw / 2  # Shaft center as fallback
                door_center_x = car_center_x

            # Door width (bottom, level 1)
            door_x = door_center_x - dw / 2
            draw_dimension_line(
                ax,
                start=(door_x, 0),
                end=(door_x + dw, 0),
                text=f"Door Width {int(dw)}",
                offset=-150,
                orientation="horizontal",
            )

            # Door height label (below door width)
            door_label_center_x = door_x + dw / 2
            ax.text(
                door_label_center_x, -320,
                f"Height {int(dh)}",
                ha="center", va="top",
                fontsize=config.DIMENSION_TEXT_SIZE,
                color=config.DIMENSION_COLOR,
            )

            # Structural opening width (bottom, level 2)
            opening_x = door_center_x - sow / 2
            draw_dimension_line(
                ax,
                start=(opening_x, 0),
                end=(opening_x + sow, 0),
                text=f"Structural Opening Width {int(sow)}",
                offset=-500,
                orientation="horizontal",
            )

            # Structural opening height label (below structural opening width)
            opening_label_center_x = opening_x + sow / 2
            ax.text(
                opening_label_center_x, -670,
                f"Height {int(soh)}",
                ha="center", va="top",
                fontsize=config.DIMENSION_TEXT_SIZE,
                color=config.DIMENSION_COLOR,
            )

            # Car WIDTH dimensions for each lift (brackets and car widths)
            if lift:
                mirror = (lift_idx % 2 == 1)

                # Calculate car positions based on machine type and mirror state
                if lift.lift_machine_type == "mra":
                    # MRA: center car in available space between brackets
                    left_cb = lift.mra_car_bracket_width
                    right_cb = lift.mra_right_bracket_width
                    available_w = lift.shaft_width - left_cb - right_cb
                    car_x = shaft_left + left_cb + (available_w - lift.unfinished_car_width) / 2
                    car_y = wt + 2 * lift.door_panel_thickness + config.DEFAULT_DOOR_GAP
                else:
                    # MRL: center car in available space between brackets
                    if not mirror:
                        cwb_w = lift.counterweight_bracket_width
                        cb_w = lift.car_bracket_width
                        available_w = lift.shaft_width - cwb_w - cb_w
                        car_x = shaft_left + cwb_w + (available_w - lift.unfinished_car_width) / 2
                    else:
                        cb_w = lift.car_bracket_width
                        cwb_w = lift.counterweight_bracket_width
                        available_w = lift.shaft_width - cb_w - cwb_w
                        car_x = shaft_left + cb_w + (available_w - lift.unfinished_car_width) / 2
                    # Front-fixed: extra depth goes to rear clearance
                    car_y = wt + 2 * lift.door_panel_thickness + config.DEFAULT_DOOR_GAP

                finished_car_x = car_x + (lift.unfinished_car_width - lift.finished_car_width) / 2
                finished_car_y = car_y

                # Calculate actual object edges for extension lines
                car_top_y = car_y + lift.unfinished_car_depth
                finished_car_top_y = finished_car_y + lift.finished_car_depth

                # Target dimension line positions
                level2_target_y = shaft_top_y + 550 + wt
                level3_target_y = shaft_top_y + 850 + wt

                if lift.lift_machine_type == "mra":
                    # MRA: Dynamic left bracket (shaft wall to car left edge)
                    left_cb = lift.mra_car_bracket_width
                    right_cb = lift.mra_right_bracket_width
                    available_w = lift.shaft_width - left_cb - right_cb
                    car_left_edge = shaft_left + left_cb + (available_w - lift.unfinished_car_width) / 2
                    left_gap = car_left_edge - shaft_left
                    draw_dimension_line(
                        ax,
                        start=(shaft_left, shaft_top_y),
                        end=(car_left_edge, shaft_top_y),
                        text=f"{int(left_gap)}",
                        offset=level2_target_y - shaft_top_y,
                        orientation="horizontal",
                    )

                    # MRA: Dynamic right bracket (car right edge to shaft wall)
                    car_right_edge = car_left_edge + lift.unfinished_car_width
                    shaft_wall_x = shaft_left + sw
                    right_gap = shaft_wall_x - car_right_edge
                    draw_dimension_line(
                        ax,
                        start=(car_right_edge, shaft_top_y),
                        end=(shaft_wall_x, shaft_top_y),
                        text=f"{int(right_gap)}",
                        offset=level2_target_y - shaft_top_y,
                        orientation="horizontal",
                    )
                else:
                    # MRL: bracket positions depend on mirror state
                    if not mirror:
                        # Normal: CW bracket on left, car bracket on right
                        left_bracket_width = lift.counterweight_bracket_width
                    else:
                        # Mirrored: car bracket on left, CW bracket on right
                        left_bracket_width = lift.car_bracket_width

                    # Left bracket width (top, level 2)
                    draw_dimension_line(
                        ax,
                        start=(shaft_left, shaft_top_y),
                        end=(shaft_left + left_bracket_width, shaft_top_y),
                        text=f"{int(left_bracket_width)}",
                        offset=level2_target_y - shaft_top_y,
                        orientation="horizontal",
                    )

                    # Right bracket width (top, level 2)
                    # Dynamic: measure from unfinished car right edge to shaft wall
                    car_right_edge = shaft_left + left_bracket_width + lift.unfinished_car_width
                    shaft_wall_x = shaft_left + sw
                    right_gap = shaft_wall_x - car_right_edge
                    draw_dimension_line(
                        ax,
                        start=(car_right_edge, shaft_top_y),
                        end=(shaft_wall_x, shaft_top_y),
                        text=f"{int(right_gap)}",
                        offset=level2_target_y - shaft_top_y,
                        orientation="horizontal",
                    )

                # Finished car width (top, level 2 - closer to drawing)
                draw_dimension_line(
                    ax,
                    start=(finished_car_x, finished_car_top_y),
                    end=(finished_car_x + lift.finished_car_width, finished_car_top_y),
                    text=f"Finished Car Width {int(lift.finished_car_width)}",
                    offset=level2_target_y - finished_car_top_y,
                    orientation="horizontal",
                )

                # Unfinished car width (top, level 3 - further from drawing)
                draw_dimension_line(
                    ax,
                    start=(car_x, car_top_y),
                    end=(car_x + lift.unfinished_car_width, car_top_y),
                    text=f"Unfinished Car Width {int(lift.unfinished_car_width)}",
                    offset=level3_target_y - car_top_y,
                    orientation="horizontal",
                )

            # Move to next shaft
            if lift_idx < self.num_lifts - 1:
                x_pos = shaft_left + sw + swt
            else:
                x_pos = shaft_left + sw

        # Car DEPTH dimensions (draw after loop: first lift on left, last lift on right if different)
        if self._use_enhanced_api and self.lifts:
            first_lift = self.lifts[0]
            first_sd = self._shaft_depths[0]  # First lift's actual depth
            last_lift = self.lifts[-1]
            last_sd = self._shaft_depths[-1]  # Last lift's actual depth

            # Calculate first lift car position for depth dimensions
            first_shaft_left = wt
            first_sw = self._shaft_widths[0]
            if first_lift.lift_machine_type == "mra":
                left_cb = first_lift.mra_car_bracket_width
                right_cb = first_lift.mra_right_bracket_width
                available_w = first_lift.shaft_width - left_cb - right_cb
                first_car_x = first_shaft_left + left_cb + (available_w - first_lift.unfinished_car_width) / 2
                first_car_y = wt + 2 * first_lift.door_panel_thickness + config.DEFAULT_DOOR_GAP
            else:
                # First lift is never mirrored (lift_idx 0)
                cwb_w = first_lift.counterweight_bracket_width
                cb_w = first_lift.car_bracket_width
                available_w = first_lift.shaft_width - cwb_w - cb_w
                first_car_x = first_shaft_left + cwb_w + (available_w - first_lift.unfinished_car_width) / 2
                first_car_y = wt + 2 * first_lift.door_panel_thickness + config.DEFAULT_DOOR_GAP

            first_finished_car_x = first_car_x + (first_lift.unfinished_car_width - first_lift.finished_car_width) / 2

            # First lift depth dimensions (left side)
            draw_dimension_line(
                ax,
                start=(first_finished_car_x, first_car_y),
                end=(first_finished_car_x, first_car_y + first_lift.finished_car_depth),
                text=f"Finished Car Depth {int(first_lift.finished_car_depth)}",
                offset=-(first_finished_car_x + 550),
                orientation="vertical",
            )

            draw_dimension_line(
                ax,
                start=(first_car_x, first_car_y),
                end=(first_car_x, first_car_y + first_lift.unfinished_car_depth),
                text=f"Unfinished Car Depth {int(first_lift.unfinished_car_depth)}",
                offset=-(first_car_x + 850),
                orientation="vertical",
            )

            # Last lift depth dimensions (right side) - only if different from first lift
            if self.num_lifts > 1:
                car_depths_differ = (
                    last_lift.finished_car_depth != first_lift.finished_car_depth or
                    last_lift.unfinished_car_depth != first_lift.unfinished_car_depth
                )
                if car_depths_differ:
                    # Calculate last lift car position
                    last_lift_idx = self.num_lifts - 1
                    last_shaft_left = wt + sum(self._shaft_widths[:last_lift_idx]) + last_lift_idx * swt
                    last_mirror = (last_lift_idx % 2 == 1)

                    last_sw = self._shaft_widths[-1]
                    if last_lift.lift_machine_type == "mra":
                        left_cb = last_lift.mra_car_bracket_width
                        right_cb = last_lift.mra_right_bracket_width
                        available_w = last_lift.shaft_width - left_cb - right_cb
                        last_car_x = last_shaft_left + left_cb + (available_w - last_lift.unfinished_car_width) / 2
                        last_car_y = wt + 2 * last_lift.door_panel_thickness + config.DEFAULT_DOOR_GAP
                    else:
                        if not last_mirror:
                            cwb_w = last_lift.counterweight_bracket_width
                            cb_w = last_lift.car_bracket_width
                            available_w = last_lift.shaft_width - cwb_w - cb_w
                            last_car_x = last_shaft_left + cwb_w + (available_w - last_lift.unfinished_car_width) / 2
                        else:
                            cb_w = last_lift.car_bracket_width
                            cwb_w = last_lift.counterweight_bracket_width
                            available_w = last_lift.shaft_width - cb_w - cwb_w
                            last_car_x = last_shaft_left + cb_w + (available_w - last_lift.unfinished_car_width) / 2
                        last_car_y = wt + 2 * last_lift.door_panel_thickness + config.DEFAULT_DOOR_GAP

                    last_finished_car_x = last_car_x + (last_lift.unfinished_car_width - last_lift.finished_car_width) / 2
                    last_car_right_x = last_car_x + last_lift.unfinished_car_width
                    last_finished_car_right_x = last_finished_car_x + last_lift.finished_car_width

                    # Right side offset calculation (same approach as left side):
                    # Left side order: shaft depth (level 1), finished car (level 2), unfinished car (level 3)
                    # Right side: same order - shaft depth closest to wall

                    # Shaft depth (right side, level 1) - from inner right wall edge
                    # Show the last lift's actual depth
                    bank_right_inner = self.total_width - wt
                    draw_dimension_line(
                        ax,
                        start=(bank_right_inner, wt),
                        end=(bank_right_inner, wt + last_sd),
                        text=f"Shaft Depth {int(last_sd)}",
                        offset=(self.total_width + 250) - bank_right_inner,
                        orientation="vertical",
                    )

                    # Last lift finished car depth (right side, level 2)
                    draw_dimension_line(
                        ax,
                        start=(last_finished_car_right_x, last_car_y),
                        end=(last_finished_car_right_x, last_car_y + last_lift.finished_car_depth),
                        text=f"Finished Car Depth {int(last_lift.finished_car_depth)}",
                        offset=(self.total_width + 550) - last_finished_car_right_x,
                        orientation="vertical",
                    )

                    # Last lift unfinished car depth (right side, level 3)
                    draw_dimension_line(
                        ax,
                        start=(last_car_right_x, last_car_y),
                        end=(last_car_right_x, last_car_y + last_lift.unfinished_car_depth),
                        text=f"Unfinished Car Depth {int(last_lift.unfinished_car_depth)}",
                        offset=(self.total_width + 850) - last_car_right_x,
                        orientation="vertical",
                    )

        # Internal depth dimension (left side, level 1) - show first lift's actual depth
        first_sd = self._shaft_depths[0] if self._use_enhanced_api else max_sd
        draw_dimension_line(
            ax,
            start=(wt, wt),
            end=(wt, wt + first_sd),
            text=f"Shaft Depth {int(first_sd)}",
            offset=-(wt + 250),  # Position outside left wall
            orientation="vertical",
        )

        # Separator dimension (top, level 3 - same as unfinished car width)
        if self.num_lifts > 1:
            shared_wall_x = wt + self._shaft_widths[0]
            shaft_top_y = wt + max_sd  # Use max_sd for consistent positioning
            if self._separator_type == "steel_beam":
                label = f"{int(swt)}"
            else:
                label = f"{int(swt)}"
            draw_dimension_line(
                ax,
                start=(shared_wall_x, shaft_top_y),
                end=(shared_wall_x + swt, shaft_top_y),
                text=label,
                offset=850 + wt,
                orientation="horizontal",
            )

            # Add "STEEL BEAM" label above the dimension for steel separators
            if self._separator_type == "steel_beam":
                dim_y = shaft_top_y + 850 + wt + 50  # Just above the dimension line
                ax.text(
                    shared_wall_x + swt / 2,
                    dim_y + 120,  # Above the dimension
                    "Steel\nBeam",
                    ha="center",
                    va="bottom",
                    fontsize=config.SEPARATOR_LABEL_SIZE,
                    color=config.DIMENSION_COLOR,
                )

            # Total shaft width (bottom, level 4 - furthest from drawing)
            # This is the internal width of all shafts combined (excluding outer walls)
            total_internal_width = sum(self._shaft_widths) + (self.num_lifts - 1) * swt
            draw_dimension_line(
                ax,
                start=(wt, 0),
                end=(wt + total_internal_width, 0),
                text=f"Total Shaft Width {int(total_internal_width)}",
                offset=-1050,
                orientation="horizontal",
            )

    def _draw_facing_banks(
        self,
        ax: plt.Axes,
        display_options: dict,
    ) -> None:
        """Draw two banks of lifts facing each other across a lobby."""
        wt = self.wall_thickness

        # Draw Bank 1 (top) - doors face down toward lobby
        self._draw_bank(
            ax,
            lifts=self.lifts,
            shaft_widths=self._shaft_widths,
            shaft_depths=self._shaft_depths,
            max_shaft_depth=self._max_shaft_depth,
            base_y=self._bank1_y,
            bank_width=self._bank1_width,
            shared_wall_thickness=self.shared_wall_thickness,
            separator_type=self._separator_type,
            doors_face="down",
            display_options=display_options,
        )

        # Draw Bank 2 (bottom) - doors face up toward lobby (mirrored)
        self._draw_bank(
            ax,
            lifts=self.lifts_bank2,
            shaft_widths=self._shaft_widths_bank2,
            shaft_depths=self._shaft_depths_bank2,
            max_shaft_depth=self._max_shaft_depth_bank2,
            base_y=self._bank2_y,
            bank_width=self._bank2_width,
            shared_wall_thickness=self.shared_wall_thickness_bank2,
            separator_type=self._separator_type_bank2,
            doors_face="up",
            display_options=display_options,
        )

        # Draw centerlines if enabled
        if display_options["show_centerlines"]:
            # Horizontal centerline through lobby center
            lobby_center_y = self._bank2_y + self._max_shaft_depth_bank2 + 2 * wt + self.lobby_width / 2
            draw_centerline(ax, (0, lobby_center_y), (self.total_width, lobby_center_y))

        # Draw dimensions
        if display_options["show_dimensions"]:
            self._draw_facing_banks_dimensions(ax)

    def _draw_bank(
        self,
        ax: plt.Axes,
        lifts: List[LiftConfig],
        shaft_widths: List[float],
        shaft_depths: List[float],
        max_shaft_depth: float,
        base_y: float,
        bank_width: float,
        shared_wall_thickness: float,
        separator_type: str,
        doors_face: str,
        display_options: dict,
    ) -> None:
        """
        Draw a single bank of lifts.

        Args:
            ax: Matplotlib axes
            lifts: List of LiftConfig objects for this bank
            shaft_widths: Per-lift shaft widths
            shaft_depths: Per-lift shaft depths
            max_shaft_depth: Maximum shaft depth in this bank
            base_y: Bottom Y coordinate for this bank
            bank_width: Total width of this bank
            shared_wall_thickness: Width of separator between lifts
            separator_type: "steel_beam" or "rcc_wall"
            doors_face: "down" (normal) or "up" (mirrored for Bank 2)
            display_options: Display options dictionary
        """
        wt = self.wall_thickness
        swt = shared_wall_thickness
        num_lifts = len(lifts)

        # Center bank horizontally if narrower than total_width
        x_offset = (self.total_width - bank_width) / 2

        # Track x position as we draw each lift
        x_pos = x_offset

        for lift_idx in range(num_lifts):
            is_first = lift_idx == 0
            is_last = lift_idx == num_lifts - 1
            sw = shaft_widths[lift_idx]
            sd = shaft_depths[lift_idx]

            lift_config = lifts[lift_idx]
            sow = lift_config.structural_opening_width
            dw = lift_config.door_width

            # Left wall (outer wall for first lift, shared wall/separator otherwise)
            if is_first:
                # Left outer wall - use first lift's depth for L-shape
                first_depth = shaft_depths[0]
                if doors_face == "down":
                    # Normal: wall starts at base_y, extends up by first_depth + 2*wt
                    draw_wall_section(ax, x_pos, base_y, wt, first_depth + 2 * wt, display_options["show_hatching"])
                else:
                    # Mirrored: wall starts at back wall position (further from front)
                    wall_start_y = base_y + (max_shaft_depth - first_depth)
                    draw_wall_section(ax, x_pos, wall_start_y, wt, first_depth + 2 * wt, display_options["show_hatching"])
                shaft_left = x_pos + wt
            else:
                # Draw separator (steel beam or RCC wall)
                # Use min of adjacent shaft depths for L-shaped walls
                prev_depth = shaft_depths[lift_idx - 1]
                curr_depth = sd
                separator_depth = min(prev_depth, curr_depth)  # Separator extends to shallower depth

                if separator_type == "steel_beam":
                    if doors_face == "down":
                        # Normal: beam starts at wt from base_y
                        draw_steel_beam(ax, x_pos, base_y + wt, swt, separator_depth, label=None)
                        # Front wall section
                        draw_wall_section(ax, x_pos, base_y, swt, wt, display_options["show_hatching"])
                        # Back wall section at shallower depth
                        draw_wall_section(ax, x_pos, base_y + wt + separator_depth, swt, wt, display_options["show_hatching"])

                        # L-shape: If previous shaft is deeper, continue fire shaft's right wall
                        if prev_depth > curr_depth:
                            wall_start_y = base_y + wt + separator_depth + wt  # Below separator's back wall
                            wall_height = prev_depth - separator_depth
                            draw_wall_section(ax, x_pos, wall_start_y, wt, wall_height, display_options["show_hatching"])

                        # L-shape: If current shaft is deeper, extend current shaft's left wall
                        if curr_depth > prev_depth:
                            wall_start_y = base_y + wt + separator_depth + wt  # Below separator's back wall
                            wall_height = curr_depth - separator_depth
                            draw_wall_section(ax, x_pos + swt - wt, wall_start_y, wt, wall_height, display_options["show_hatching"])
                    else:
                        # Mirrored: beam positioned from back (further from front)
                        beam_start_y = base_y + wt + (max_shaft_depth - separator_depth)
                        draw_steel_beam(ax, x_pos, beam_start_y, swt, separator_depth, label=None)
                        # Front wall section (at top)
                        draw_wall_section(ax, x_pos, base_y + wt + max_shaft_depth, swt, wt, display_options["show_hatching"])
                        # Back wall section at shallower depth position
                        draw_wall_section(ax, x_pos, base_y + (max_shaft_depth - separator_depth), swt, wt, display_options["show_hatching"])

                        # L-shape: If previous shaft is deeper, continue fire shaft's right wall
                        if prev_depth > curr_depth:
                            wall_start_y = base_y + (max_shaft_depth - prev_depth)  # Previous's back wall position
                            wall_height = prev_depth - curr_depth  # Gap to separator
                            draw_wall_section(ax, x_pos, wall_start_y, wt, wall_height, display_options["show_hatching"])

                        # L-shape: If current shaft is deeper, extend current shaft's left wall
                        if curr_depth > prev_depth:
                            wall_start_y = base_y + (max_shaft_depth - curr_depth)  # Current's back wall position
                            wall_height = curr_depth - prev_depth  # Gap to separator
                            draw_wall_section(ax, x_pos + swt - wt, wall_start_y, wt, wall_height, display_options["show_hatching"])
                else:
                    # RCC wall - extends to shallower depth
                    if doors_face == "down":
                        draw_wall_section(ax, x_pos, base_y, swt, separator_depth + 2 * wt, display_options["show_hatching"])

                        # L-shape: If previous shaft is deeper, continue fire shaft's right wall
                        if prev_depth > curr_depth:
                            wall_start_y = base_y + separator_depth + 2 * wt  # Below separator
                            wall_height = prev_depth - separator_depth
                            draw_wall_section(ax, x_pos, wall_start_y, wt, wall_height, display_options["show_hatching"])

                        # L-shape: If current shaft is deeper, extend current shaft's left wall
                        if curr_depth > prev_depth:
                            wall_start_y = base_y + separator_depth + 2 * wt  # Below separator
                            wall_height = curr_depth - separator_depth
                            draw_wall_section(ax, x_pos + swt - wt, wall_start_y, wt, wall_height, display_options["show_hatching"])
                    else:
                        wall_start_y = base_y + (max_shaft_depth - separator_depth)
                        draw_wall_section(ax, x_pos, wall_start_y, swt, separator_depth + 2 * wt, display_options["show_hatching"])

                        # L-shape: If previous shaft is deeper, continue fire shaft's right wall
                        if prev_depth > curr_depth:
                            cont_start_y = base_y + (max_shaft_depth - prev_depth)  # Previous's back wall position
                            cont_height = prev_depth - curr_depth  # Gap to separator
                            draw_wall_section(ax, x_pos, cont_start_y, wt, cont_height, display_options["show_hatching"])

                        # L-shape: If current shaft is deeper, extend current shaft's left wall
                        if curr_depth > prev_depth:
                            cont_start_y = base_y + (max_shaft_depth - curr_depth)  # Current's back wall position
                            cont_height = curr_depth - prev_depth  # Gap to separator
                            draw_wall_section(ax, x_pos + swt - wt, cont_start_y, wt, cont_height, display_options["show_hatching"])

                shaft_left = x_pos + swt

            # Draw shaft interior at this lift's actual depth
            if doors_face == "down":
                # Normal: shaft interior at bottom, back wall at top
                draw_shaft_interior(ax, shaft_left, base_y + wt, sw, sd)
            else:
                # Mirrored: shaft interior at top (after back wall), front wall at bottom
                draw_shaft_interior(ax, shaft_left, base_y + wt + (max_shaft_depth - sd), sw, sd)

            # Calculate car center position (center car in available space between brackets)
            if lift_config.lift_machine_type == "mra":
                left_cb = lift_config.mra_car_bracket_width
                right_cb = lift_config.mra_right_bracket_width
                uc_width = lift_config.unfinished_car_width
                available = sw - left_cb - right_cb
                car_center_x = shaft_left + left_cb + (available - uc_width) / 2 + uc_width / 2
            else:
                cwb_width = lift_config.counterweight_bracket_width
                cb_width = lift_config.car_bracket_width
                uc_width = lift_config.unfinished_car_width
                mirror = (lift_idx % 2 == 1)
                if not mirror:
                    available = sw - cwb_width - cb_width
                    car_center_x = shaft_left + cwb_width + (available - uc_width) / 2 + uc_width / 2
                else:
                    available = sw - cb_width - cwb_width
                    car_center_x = shaft_left + cb_width + (available - uc_width) / 2 + uc_width / 2

            # For fire lifts, center door/opening on shaft (not car) to avoid wall overlap
            if lift_config.lift_type == "fire":
                door_center_x = shaft_left + sw / 2  # Shaft center
            else:
                door_center_x = car_center_x  # Car center

            opening_x = door_center_x - sow / 2

            # Draw lift interior components
            if doors_face == "down":
                # Normal orientation - pass shaft_y as base_y + wt
                self._draw_lift_interior(
                    ax, shaft_left, base_y + wt, lift_config, display_options,
                    mirror=(lift_idx % 2 == 1), shaft_depth=sd
                )
            else:
                # Mirrored orientation for Bank 2
                self._draw_lift_interior_mirrored(
                    ax, shaft_left, base_y + wt, lift_config, display_options,
                    mirror=(lift_idx % 2 == 1), shaft_depth=sd, max_shaft_depth=max_shaft_depth
                )

            # Front wall with opening
            if doors_face == "down":
                front_wall_y = base_y
            else:
                front_wall_y = base_y + wt + max_shaft_depth

            # Left part of front wall
            front_wall_left = shaft_left
            if opening_x > front_wall_left:
                draw_wall_section(ax, front_wall_left, front_wall_y, opening_x - front_wall_left, wt, display_options["show_hatching"])

            # Right part of front wall
            right_wall_x = opening_x + sow
            front_wall_right = shaft_left + sw
            if right_wall_x < front_wall_right:
                draw_wall_section(ax, right_wall_x, front_wall_y, front_wall_right - right_wall_x, wt, display_options["show_hatching"])

            # Draw opening
            draw_opening(ax, opening_x, front_wall_y, sow, wt)

            # Draw door jambs (only when doors are shown)
            if display_options.get("show_lift_doors", False):
                if doors_face == "down":
                    draw_door_jambs(ax, opening_x, base_y + wt, sow)
                else:
                    # Mirrored: jambs at top of shaft interior, extending upward
                    draw_door_jambs(ax, opening_x, front_wall_y, sow, mirrored=True)

            # Draw door panels - center on shaft for fire lifts, cabin for others
            if display_options["show_door_panels"]:
                door_x = door_center_x - dw / 2
                draw_door_panels(ax, door_x, front_wall_y, dw, wt, num_panels=config.DEFAULT_DOOR_PANELS)

            # Back wall for this lift at its own depth
            # For normal (doors_face="down"): back wall is above shaft interior
            # For mirrored (doors_face="up"): back wall is below shaft interior
            if doors_face == "down":
                back_wall_y = base_y + wt + sd
            else:
                # Mirrored: back wall at bottom, below shaft interior
                back_wall_y = base_y + (max_shaft_depth - sd)
            draw_wall_section(ax, shaft_left, back_wall_y, sw, wt, display_options["show_hatching"])

            # L-shaped walls: Do NOT draw envelope back wall at max depth for shallower shafts
            # Each shaft's back wall is at its own depth, creating an L-shape when depths differ

            # Draw centerlines for this lift - extend to each shaft's own depth
            if display_options["show_centerlines"]:
                center_x = shaft_left + sw / 2
                if doors_face == "down":
                    draw_centerline(ax, (center_x, base_y), (center_x, base_y + sd + 2 * wt))
                else:
                    # Mirrored: centerline from back wall position to front
                    cl_start_y = base_y + (max_shaft_depth - sd)
                    draw_centerline(ax, (center_x, cl_start_y), (center_x, base_y + max_shaft_depth + 2 * wt))

            # Update x position
            if is_first:
                x_pos = x_offset + wt + sw
            else:
                x_pos = shaft_left + sw

        # Draw right outer wall - use last lift's depth for L-shape
        last_depth = shaft_depths[-1]
        if doors_face == "down":
            draw_wall_section(ax, x_pos, base_y, wt, last_depth + 2 * wt, display_options["show_hatching"])
        else:
            # Mirrored: wall starts from back wall position
            wall_start_y = base_y + (max_shaft_depth - last_depth)
            draw_wall_section(ax, x_pos, wall_start_y, wt, last_depth + 2 * wt, display_options["show_hatching"])

    def _draw_lift_interior_mirrored(
        self,
        ax: plt.Axes,
        shaft_x: float,
        shaft_y: float,
        lift_config: LiftConfig,
        display_options: dict,
        mirror: bool = False,
        shaft_depth: float = None,
        max_shaft_depth: float = None,
    ) -> None:
        """
        Draw the interior components of a lift shaft with vertical mirroring.

        This is used for Bank 2 in facing arrangement where doors face up.
        The lift car and brackets are drawn in mirrored Y orientation.

        Args:
            ax: Matplotlib axes
            shaft_x: Left x coordinate of shaft interior
            shaft_y: Bottom y coordinate of outer bank envelope (not shaft interior)
            lift_config: Lift configuration
            display_options: Display options dictionary
            mirror: If True, place counterweight on right side instead of left (MRL only)
            shaft_depth: This lift's shaft depth
            max_shaft_depth: Maximum shaft depth in the bank
        """
        sd = shaft_depth if shaft_depth is not None else self.shaft_depth
        msd = max_shaft_depth if max_shaft_depth is not None else sd

        # In mirrored mode, the shaft interior starts at shaft_y + (max_shaft_depth - sd)
        # The car is placed relative to this mirrored shaft interior
        shaft_interior_y = shaft_y + (msd - sd)

        # Dispatch to MRA-specific drawing if machine type is MRA
        if lift_config.lift_machine_type == "mra":
            self._draw_lift_interior_mra_mirrored(
                ax, shaft_x, shaft_interior_y, lift_config, display_options, shaft_depth=sd
            )
            return

        # MRL drawing (mirrored)
        cwb_width = lift_config.counterweight_bracket_width
        cb_width = lift_config.car_bracket_width
        uc_width = lift_config.unfinished_car_width
        uc_depth = lift_config.unfinished_car_depth
        fc_width = lift_config.finished_car_width
        fc_depth = lift_config.finished_car_depth
        sw = lift_config.shaft_width  # Respects override

        # Calculate car center position (center car in available space between brackets)
        if not mirror:
            available = sw - cwb_width - cb_width
            car_center_x = shaft_x + cwb_width + (available - uc_width) / 2 + uc_width / 2
        else:
            available = sw - cb_width - cwb_width
            car_center_x = shaft_x + cb_width + (available - uc_width) / 2 + uc_width / 2

        # For fire lifts, center doors on shaft (not car) to avoid wall overlap
        if lift_config.lift_type == "fire":
            door_center_x = shaft_x + lift_config.shaft_width / 2  # Shaft center
        else:
            door_center_x = car_center_x  # Car center

        # In mirrored orientation, doors are at top (high Y), back is at bottom (low Y)
        # Car Y position: front-fixed (mirrored: door at top, so car top touches door zone)
        door_zone = 2 * lift_config.door_panel_thickness + config.DEFAULT_DOOR_GAP
        car_y = shaft_interior_y + sd - door_zone - uc_depth

        # Draw lift doors (at top of shaft for mirrored)
        door_info = None
        if display_options.get("show_lift_doors", False):
            # Doors are at top of shaft (shaft_interior_y + sd is where front wall is)
            door_info = draw_lift_doors(
                ax,
                center_x=door_center_x,  # Shaft center for fire lifts, car center for others
                wall_inner_y=shaft_interior_y + sd,  # Top of shaft interior
                door_width=lift_config.door_width,
                door_extension=lift_config.door_extension,
                door_thickness=lift_config.door_panel_thickness,
                mirrored=True,  # Draw doors facing down (into shaft)
                door_opening_type=lift_config.door_opening_type,
                telescopic_left_ext=lift_config.telescopic_left_ext,
                telescopic_right_ext=lift_config.telescopic_right_ext,
            )

        # Draw counterweight bracket
        if display_options["show_brackets"]:
            bracket_height = sd * 0.7
            bracket_y = shaft_interior_y + (sd - bracket_height) / 2

            if not mirror:
                draw_counterweight_bracket(ax, shaft_x, bracket_y, cwb_width, bracket_height, align="left")
            else:
                cw_bracket_x = shaft_x + cb_width + uc_width
                draw_counterweight_bracket(ax, cw_bracket_x, bracket_y, cwb_width, bracket_height, align="right")

            # Draw car bracket box (against shaft wall)
            car_bracket_box_y = shaft_interior_y + (sd - config.CAR_BRACKET_BOX_HEIGHT) / 2
            if not mirror:
                car_bracket_box_x = shaft_x + sw - config.CAR_BRACKET_BOX_WIDTH
            else:
                car_bracket_box_x = shaft_x

            ax.add_patch(Rectangle(
                (car_bracket_box_x, car_bracket_box_y),
                config.CAR_BRACKET_BOX_WIDTH,
                config.CAR_BRACKET_BOX_HEIGHT,
                facecolor=config.CAR_BRACKET_BOX_COLOR,
                edgecolor="#000000",
                linewidth=0.8,
                zorder=3,
            ))

            # Draw CW-side car bracket
            cw_side_bracket_y = shaft_interior_y + (sd - config.MRL_CW_SIDE_CAR_BRACKET_HEIGHT) / 2
            if not mirror:
                cw_side_bracket_x = shaft_x + (config.CW_BOX_WIDTH - config.CW_FRAME_THICKNESS)
            else:
                cw_box_left_edge = shaft_x + cb_width + uc_width + cwb_width - (config.CW_BOX_WIDTH - config.CW_FRAME_THICKNESS)
                cw_side_bracket_x = cw_box_left_edge - config.MRL_CW_SIDE_CAR_BRACKET_WIDTH

            draw_car_bracket_cw_side(ax, cw_side_bracket_x, cw_side_bracket_y)

        # Draw lift car (center in available space between brackets)
        if display_options["show_car_interior"]:
            if not mirror:
                available_w = sw - cwb_width - cb_width
                car_x = shaft_x + cwb_width + (available_w - uc_width) / 2
            else:
                available_w = sw - cb_width - cwb_width
                car_x = shaft_x + cb_width + (available_w - uc_width) / 2

            draw_lift_car(
                ax,
                car_x,
                car_y,
                uc_width,
                uc_depth,
                fc_width,
                fc_depth,
                mirrored=True,  # Doors at top for Bank 2
            )

            # Draw car interior details
            finished_car_x = car_x + (uc_width - fc_width) / 2
            finished_car_y = car_y

            draw_car_interior_details(
                ax,
                finished_car_x,
                finished_car_y,
                fc_width,
                fc_depth,
                capacity=lift_config.lift_capacity if display_options["show_capacity"] else None,
                show_cop=False,
                show_accessibility=display_options["show_accessibility"],
            )

    def _draw_lift_interior_mra_mirrored(
        self,
        ax: plt.Axes,
        shaft_x: float,
        shaft_y: float,
        lift_config: LiftConfig,
        display_options: dict,
        shaft_depth: float = None,
    ) -> None:
        """
        Draw the interior components of a MRA lift shaft with vertical mirroring.

        Args:
            ax: Matplotlib axes
            shaft_x: Left x coordinate of shaft interior
            shaft_y: Bottom y coordinate of shaft interior (already adjusted for mirroring)
            lift_config: Lift configuration
            display_options: Display options dictionary
            shaft_depth: This lift's shaft depth
        """
        sd = shaft_depth if shaft_depth is not None else self.shaft_depth

        left_cb = lift_config.mra_car_bracket_width
        right_cb = lift_config.mra_right_bracket_width
        cw_bracket_depth = lift_config.mra_cw_bracket_depth
        uc_width = lift_config.unfinished_car_width
        uc_depth = lift_config.unfinished_car_depth
        fc_width = lift_config.finished_car_width
        fc_depth = lift_config.finished_car_depth
        shaft_width = lift_config.shaft_width

        # In mirrored mode, doors are at top (shaft_y + sd), CW bracket at bottom
        # Center car in available space between brackets
        available_w = shaft_width - left_cb - right_cb
        car_x = shaft_x + left_cb + (available_w - uc_width) / 2
        car_center_x = car_x + uc_width / 2
        car_y = shaft_y + sd - 2 * lift_config.door_panel_thickness - config.DEFAULT_DOOR_GAP - uc_depth

        # Draw lift doors (at top of shaft)
        if display_options.get("show_lift_doors", False):
            draw_lift_doors(
                ax,
                center_x=car_center_x,
                wall_inner_y=shaft_y + sd,
                door_width=lift_config.door_width,
                door_extension=lift_config.door_extension,
                door_thickness=lift_config.door_panel_thickness,
                mirrored=True,
                door_opening_type=lift_config.door_opening_type,
                telescopic_left_ext=lift_config.telescopic_left_ext,
                telescopic_right_ext=lift_config.telescopic_right_ext,
            )

        # Draw brackets
        if display_options["show_brackets"]:
            # CW bracket at bottom (instead of top)
            draw_counterweight_bracket_top(
                ax,
                shaft_x=shaft_x,
                shaft_y=shaft_y,
                shaft_width=shaft_width,
                shaft_depth=sd,
                cw_bracket_depth=cw_bracket_depth,
                mirrored=True,  # Draw at bottom instead of top
            )

            # Car brackets on both sides
            draw_car_brackets_mra(
                ax,
                shaft_x=shaft_x,
                shaft_y=shaft_y,
                shaft_width=shaft_width,
                shaft_depth=sd,
                car_bracket_width=left_cb,
                car_y=car_y,
                car_depth=uc_depth,
            )

        # Draw lift car
        if display_options["show_car_interior"]:
            draw_lift_car(
                ax,
                car_x,
                car_y,
                uc_width,
                uc_depth,
                fc_width,
                fc_depth,
                mirrored=True,  # Doors at top for Bank 2
            )

            finished_car_x = car_x + (uc_width - fc_width) / 2
            finished_car_y = car_y

            draw_car_interior_details(
                ax,
                finished_car_x,
                finished_car_y,
                fc_width,
                fc_depth,
                capacity=lift_config.lift_capacity if display_options["show_capacity"] else None,
                show_cop=False,
                show_accessibility=display_options["show_accessibility"],
            )

    def _draw_facing_banks_dimensions(self, ax: plt.Axes) -> None:
        """Draw dimensions for facing banks arrangement."""
        wt = self.wall_thickness

        # Bank 1 dimensions (top bank) - reuse inline style
        self._draw_bank_dimensions_inline_style(
            ax,
            lifts=self.lifts,
            shaft_widths=self._shaft_widths,
            shaft_depths=self._shaft_depths,
            max_shaft_depth=self._max_shaft_depth,
            base_y=self._bank1_y,
            bank_width=self._bank1_width,
            shared_wall_thickness=self.shared_wall_thickness,
            separator_type=self._separator_type,
            doors_face="down",
        )

        # Bank 2 dimensions (bottom bank) - reuse inline style
        self._draw_bank_dimensions_inline_style(
            ax,
            lifts=self.lifts_bank2,
            shaft_widths=self._shaft_widths_bank2,
            shaft_depths=self._shaft_depths_bank2,
            max_shaft_depth=self._max_shaft_depth_bank2,
            base_y=self._bank2_y,
            bank_width=self._bank2_width,
            shared_wall_thickness=self.shared_wall_thickness_bank2,
            separator_type=self._separator_type_bank2,
            doors_face="up",
        )

        # Lobby width dimension (left side, between banks)
        # Extension lines should reach from the front walls of both banks
        bank2_front_wall_top = self._bank2_y + self._max_shaft_depth_bank2 + 2 * wt
        bank1_front_wall_bottom = self._bank1_y
        draw_dimension_line(
            ax,
            start=(0, bank2_front_wall_top),
            end=(0, bank1_front_wall_bottom),
            text=f"Lobby Depth {int(self.lobby_width)}",
            offset=-(wt + 550),
            orientation="vertical",
        )

    def _draw_bank_dimensions_inline_style(
        self,
        ax: plt.Axes,
        lifts: List[LiftConfig],
        shaft_widths: List[float],
        shaft_depths: List[float],
        max_shaft_depth: float,
        base_y: float,
        bank_width: float,
        shared_wall_thickness: float,
        separator_type: str,
        doors_face: str,  # "down" (normal) or "up" (mirrored)
    ) -> None:
        """
        Draw dimensions for a bank using the same approach as _draw_multi_lift_dimensions.

        Uses actual object edges for extension lines and includes all car width/depth dimensions.
        """
        wt = self.wall_thickness
        swt = shared_wall_thickness
        num_lifts = len(lifts)

        # Center bank horizontally if narrower than total_width
        x_offset = (self.total_width - bank_width) / 2

        # Determine dimension positions based on door orientation
        if doors_face == "down":
            # Normal: dimensions above (top) and below (front wall at base_y)
            shaft_top_y = base_y + wt + max_shaft_depth
            front_wall_y = base_y
            dim_above = True
        else:
            # Mirrored: dimensions below (bottom) and above (front wall at top)
            shaft_top_y = base_y + wt + max_shaft_depth
            front_wall_y = base_y + wt + max_shaft_depth
            dim_above = False

        # Target dimension line positions (consistent offsets from shaft edge)
        level1_offset = 250 + wt  # Shaft width
        level2_offset = 550 + wt  # Brackets, finished car width
        level3_offset = 850 + wt  # Unfinished car width

        # Individual shaft dimensions
        x_pos = x_offset + wt
        for lift_idx in range(num_lifts):
            sw = shaft_widths[lift_idx]
            sd = shaft_depths[lift_idx]
            shaft_left = x_pos
            lift = lifts[lift_idx]

            # Calculate car positions based on machine type and mirror state
            mirror = (lift_idx % 2 == 1)

            if lift.lift_machine_type == "mra":
                left_cb = lift.mra_car_bracket_width
                right_cb = lift.mra_right_bracket_width
                available_w = lift.shaft_width - left_cb - right_cb
                car_x = shaft_left + left_cb + (available_w - lift.unfinished_car_width) / 2
                door_zone = 2 * lift.door_panel_thickness + config.DEFAULT_DOOR_GAP
                if doors_face == "down":
                    car_y = base_y + wt + door_zone
                else:
                    shaft_interior_y = base_y + wt + (max_shaft_depth - sd)
                    car_y = shaft_interior_y + sd - door_zone - lift.unfinished_car_depth
                car_center_x = car_x + lift.unfinished_car_width / 2
            else:
                # MRL: center car in available space between brackets
                cwb_width = lift.counterweight_bracket_width
                cb_width = lift.car_bracket_width
                door_zone = 2 * lift.door_panel_thickness + config.DEFAULT_DOOR_GAP
                if not mirror:
                    available_w = lift.shaft_width - cwb_width - cb_width
                    car_x = shaft_left + cwb_width + (available_w - lift.unfinished_car_width) / 2
                    car_center_x = car_x + lift.unfinished_car_width / 2
                else:
                    available_w = lift.shaft_width - cb_width - cwb_width
                    car_x = shaft_left + cb_width + (available_w - lift.unfinished_car_width) / 2
                    car_center_x = car_x + lift.unfinished_car_width / 2

                if doors_face == "down":
                    car_y = base_y + wt + door_zone
                else:
                    shaft_interior_y = base_y + wt + (max_shaft_depth - sd)
                    car_y = shaft_interior_y + sd - door_zone - lift.unfinished_car_depth

            finished_car_x = car_x + (lift.unfinished_car_width - lift.finished_car_width) / 2
            finished_car_y = car_y
            car_top_y = car_y + lift.unfinished_car_depth
            finished_car_top_y = finished_car_y + lift.finished_car_depth

            # For fire lifts, center door/opening on shaft (not car) to avoid wall overlap
            if lift.lift_type == "fire":
                door_center_x = shaft_left + sw / 2  # Shaft center
            else:
                door_center_x = car_center_x  # Car center

            # --- Horizontal dimensions (above or below based on door orientation) ---

            if dim_above:
                # Dimensions above the bank (doors facing down)
                # Shaft width (level 1)
                draw_dimension_line(
                    ax,
                    start=(shaft_left, shaft_top_y),
                    end=(shaft_left + sw, shaft_top_y),
                    text=f"Shaft Width {int(sw)}",
                    offset=level1_offset,
                    orientation="horizontal",
                )

                # Bracket widths (level 2)
                if lift.lift_machine_type == "mra":
                    # MRA: Dynamic left bracket (shaft wall to car left edge)
                    left_cb = lift.mra_car_bracket_width
                    right_cb = lift.mra_right_bracket_width
                    available_w = lift.shaft_width - left_cb - right_cb
                    car_left_edge = shaft_left + left_cb + (available_w - lift.unfinished_car_width) / 2
                    left_gap = car_left_edge - shaft_left
                    draw_dimension_line(
                        ax,
                        start=(shaft_left, shaft_top_y),
                        end=(car_left_edge, shaft_top_y),
                        text=f"{int(left_gap)}",
                        offset=level2_offset,
                        orientation="horizontal",
                    )
                    # MRA: Dynamic right bracket (car right edge to shaft wall)
                    car_right_edge = car_left_edge + lift.unfinished_car_width
                    shaft_wall_x = shaft_left + sw
                    right_gap = shaft_wall_x - car_right_edge
                    draw_dimension_line(
                        ax,
                        start=(car_right_edge, shaft_top_y),
                        end=(shaft_wall_x, shaft_top_y),
                        text=f"{int(right_gap)}",
                        offset=level2_offset,
                        orientation="horizontal",
                    )
                else:
                    # MRL bracket widths
                    if not mirror:
                        left_bracket_width = lift.counterweight_bracket_width
                    else:
                        left_bracket_width = lift.car_bracket_width

                    draw_dimension_line(
                        ax,
                        start=(shaft_left, shaft_top_y),
                        end=(shaft_left + left_bracket_width, shaft_top_y),
                        text=f"{int(left_bracket_width)}",
                        offset=level2_offset,
                        orientation="horizontal",
                    )
                    # Dynamic: measure from unfinished car right edge to shaft wall
                    car_right_edge = shaft_left + left_bracket_width + lift.unfinished_car_width
                    shaft_wall_x = shaft_left + sw
                    right_gap = shaft_wall_x - car_right_edge
                    draw_dimension_line(
                        ax,
                        start=(car_right_edge, shaft_top_y),
                        end=(shaft_wall_x, shaft_top_y),
                        text=f"{int(right_gap)}",
                        offset=level2_offset,
                        orientation="horizontal",
                    )

                # Finished car width (level 2, from actual car edge)
                draw_dimension_line(
                    ax,
                    start=(finished_car_x, finished_car_top_y),
                    end=(finished_car_x + lift.finished_car_width, finished_car_top_y),
                    text=f"Finished Car Width {int(lift.finished_car_width)}",
                    offset=shaft_top_y + level2_offset - finished_car_top_y,
                    orientation="horizontal",
                )

                # Unfinished car width (level 3, from actual car edge)
                draw_dimension_line(
                    ax,
                    start=(car_x, car_top_y),
                    end=(car_x + lift.unfinished_car_width, car_top_y),
                    text=f"Unfinished Car Width {int(lift.unfinished_car_width)}",
                    offset=shaft_top_y + level3_offset - car_top_y,
                    orientation="horizontal",
                )

            else:
                # Dimensions below the bank (doors facing up / mirrored)
                car_bottom_y = car_y
                finished_car_bottom_y = finished_car_y

                # Shaft width (level 1, below front wall)
                draw_dimension_line(
                    ax,
                    start=(shaft_left, base_y),
                    end=(shaft_left + sw, base_y),
                    text=f"Shaft Width {int(sw)}",
                    offset=-level1_offset,
                    orientation="horizontal",
                )

                # Bracket widths (level 2)
                if lift.lift_machine_type == "mra":
                    # MRA: Dynamic left bracket (shaft wall to car left edge)
                    left_cb = lift.mra_car_bracket_width
                    right_cb = lift.mra_right_bracket_width
                    available_w = lift.shaft_width - left_cb - right_cb
                    car_left_edge = shaft_left + left_cb + (available_w - lift.unfinished_car_width) / 2
                    left_gap = car_left_edge - shaft_left
                    draw_dimension_line(
                        ax,
                        start=(shaft_left, base_y),
                        end=(car_left_edge, base_y),
                        text=f"{int(left_gap)}",
                        offset=-level2_offset,
                        orientation="horizontal",
                    )
                    # MRA: Dynamic right bracket (car right edge to shaft wall)
                    car_right_edge = car_left_edge + lift.unfinished_car_width
                    shaft_wall_x = shaft_left + sw
                    right_gap = shaft_wall_x - car_right_edge
                    draw_dimension_line(
                        ax,
                        start=(car_right_edge, base_y),
                        end=(shaft_wall_x, base_y),
                        text=f"{int(right_gap)}",
                        offset=-level2_offset,
                        orientation="horizontal",
                    )
                else:
                    if not mirror:
                        left_bracket_width = lift.counterweight_bracket_width
                    else:
                        left_bracket_width = lift.car_bracket_width

                    draw_dimension_line(
                        ax,
                        start=(shaft_left, base_y),
                        end=(shaft_left + left_bracket_width, base_y),
                        text=f"{int(left_bracket_width)}",
                        offset=-level2_offset,
                        orientation="horizontal",
                    )
                    # Dynamic: measure from unfinished car right edge to shaft wall
                    car_right_edge = shaft_left + left_bracket_width + lift.unfinished_car_width
                    shaft_wall_x = shaft_left + sw
                    right_gap = shaft_wall_x - car_right_edge
                    draw_dimension_line(
                        ax,
                        start=(car_right_edge, base_y),
                        end=(shaft_wall_x, base_y),
                        text=f"{int(right_gap)}",
                        offset=-level2_offset,
                        orientation="horizontal",
                    )

                # Finished car width (level 2, from actual car edge)
                # Target position: base_y - level2_offset (below bank)
                draw_dimension_line(
                    ax,
                    start=(finished_car_x, finished_car_bottom_y),
                    end=(finished_car_x + lift.finished_car_width, finished_car_bottom_y),
                    text=f"Finished Car Width {int(lift.finished_car_width)}",
                    offset=(base_y - level2_offset) - finished_car_bottom_y,
                    orientation="horizontal",
                )

                # Unfinished car width (level 3, from actual car edge)
                # Target position: base_y - level3_offset (below bank)
                draw_dimension_line(
                    ax,
                    start=(car_x, car_bottom_y),
                    end=(car_x + lift.unfinished_car_width, car_bottom_y),
                    text=f"Unfinished Car Width {int(lift.unfinished_car_width)}",
                    offset=(base_y - level3_offset) - car_bottom_y,
                    orientation="horizontal",
                )

            # --- Door and structural opening dimensions (near front wall) ---
            dw = lift.door_width
            sow = lift.structural_opening_width
            dh = lift.door_height
            soh = lift.structural_opening_height
            door_x = door_center_x - dw / 2
            opening_x = door_center_x - sow / 2

            if dim_above:
                # Front wall at base_y (bottom of bank)
                # Door width (level 1 below)
                draw_dimension_line(
                    ax,
                    start=(door_x, front_wall_y),
                    end=(door_x + dw, front_wall_y),
                    text=f"Door Width {int(dw)}",
                    offset=-150,
                    orientation="horizontal",
                )

                # Door height label
                ax.text(
                    door_x + dw / 2, front_wall_y - 320,
                    f"Height {int(dh)}",
                    ha="center", va="top",
                    fontsize=config.DIMENSION_TEXT_SIZE,
                    color=config.DIMENSION_COLOR,
                )

                # Structural opening width (level 2 below)
                draw_dimension_line(
                    ax,
                    start=(opening_x, front_wall_y),
                    end=(opening_x + sow, front_wall_y),
                    text=f"Structural Opening Width {int(sow)}",
                    offset=-500,
                    orientation="horizontal",
                )

                # Structural opening height label
                ax.text(
                    opening_x + sow / 2, front_wall_y - 670,
                    f"Height {int(soh)}",
                    ha="center", va="top",
                    fontsize=config.DIMENSION_TEXT_SIZE,
                    color=config.DIMENSION_COLOR,
                )
            else:
                # Front wall at top (doors facing up)
                # Door width (level 1 above front wall)
                draw_dimension_line(
                    ax,
                    start=(door_x, front_wall_y + wt),
                    end=(door_x + dw, front_wall_y + wt),
                    text=f"Door Width {int(dw)}",
                    offset=150,
                    orientation="horizontal",
                )

                # Door height label
                ax.text(
                    door_x + dw / 2, front_wall_y + wt + 320,
                    f"Height {int(dh)}",
                    ha="center", va="bottom",
                    fontsize=config.DIMENSION_TEXT_SIZE,
                    color=config.DIMENSION_COLOR,
                )

                # Structural opening width (level 2 above)
                draw_dimension_line(
                    ax,
                    start=(opening_x, front_wall_y + wt),
                    end=(opening_x + sow, front_wall_y + wt),
                    text=f"Structural Opening Width {int(sow)}",
                    offset=500,
                    orientation="horizontal",
                )

                # Structural opening height label
                ax.text(
                    opening_x + sow / 2, front_wall_y + wt + 670,
                    f"Height {int(dh)}",
                    ha="center", va="bottom",
                    fontsize=config.DIMENSION_TEXT_SIZE,
                    color=config.DIMENSION_COLOR,
                )

            # Move to next shaft
            if lift_idx < num_lifts - 1:
                x_pos = shaft_left + sw + swt
            else:
                x_pos = shaft_left + sw

        # --- Car DEPTH dimensions (first lift on left side) ---
        first_lift = lifts[0]
        first_sd = shaft_depths[0]
        first_shaft_left = x_offset + wt

        first_sw = shaft_widths[0]
        first_door_zone = 2 * first_lift.door_panel_thickness + config.DEFAULT_DOOR_GAP

        # Car X: center car in available space between brackets (same as per-lift loop)
        if first_lift.lift_machine_type == "mra":
            left_cb = first_lift.mra_car_bracket_width
            right_cb = first_lift.mra_right_bracket_width
            available_w = first_lift.shaft_width - left_cb - right_cb
            first_car_x = first_shaft_left + left_cb + (available_w - first_lift.unfinished_car_width) / 2
        else:
            cwb_w = first_lift.counterweight_bracket_width
            cb_w = first_lift.car_bracket_width
            available_w = first_lift.shaft_width - cwb_w - cb_w
            first_car_x = first_shaft_left + cwb_w + (available_w - first_lift.unfinished_car_width) / 2

        # Car Y: front-fixed positioning (same as per-lift loop)
        if doors_face == "down":
            first_car_y = base_y + wt + first_door_zone
        else:
            shaft_interior_y = base_y + wt + (max_shaft_depth - first_sd)
            first_car_y = shaft_interior_y + first_sd - first_door_zone - first_lift.unfinished_car_depth

        first_finished_car_x = first_car_x + (first_lift.unfinished_car_width - first_lift.finished_car_width) / 2

        # Calculate shaft interior Y position (differs for mirrored banks)
        if doors_face == "down":
            shaft_interior_start_y = base_y + wt
        else:
            shaft_interior_start_y = base_y + wt + (max_shaft_depth - first_sd)

        # Shaft depth (left side, level 1) - from actual shaft interior edges
        draw_dimension_line(
            ax,
            start=(first_shaft_left, shaft_interior_start_y),
            end=(first_shaft_left, shaft_interior_start_y + first_sd),
            text=f"Shaft Depth {int(first_sd)}",
            offset=-(first_shaft_left - x_offset + 250),
            orientation="vertical",
        )

        # Car depth dimensions - extension lines should coincide at the door side
        # Normal (doors down): both start from bottom (shared edge)
        # Mirrored (doors up): both start from top (shared edge)
        if doors_face == "down":
            # Normal: dimensions from bottom (shared edge) upward
            # Finished car depth (left side, level 2)
            draw_dimension_line(
                ax,
                start=(first_finished_car_x, first_car_y),
                end=(first_finished_car_x, first_car_y + first_lift.finished_car_depth),
                text=f"Finished Car Depth {int(first_lift.finished_car_depth)}",
                offset=-(first_finished_car_x - x_offset + 550),
                orientation="vertical",
            )

            # Unfinished car depth (left side, level 3)
            draw_dimension_line(
                ax,
                start=(first_car_x, first_car_y),
                end=(first_car_x, first_car_y + first_lift.unfinished_car_depth),
                text=f"Unfinished Car Depth {int(first_lift.unfinished_car_depth)}",
                offset=-(first_car_x - x_offset + 850),
                orientation="vertical",
            )
        else:
            # Mirrored: dimensions from top (shared edge near doors) downward
            # Both cars share the same TOP edge
            car_top_y = first_car_y + first_lift.unfinished_car_depth
            # Finished car in mirrored mode: top at car_top_y, bottom at car_top_y - finished_depth
            finished_car_bottom_y = car_top_y - first_lift.finished_car_depth

            # Finished car depth (left side, level 2) - from shared top edge
            draw_dimension_line(
                ax,
                start=(first_finished_car_x, finished_car_bottom_y),
                end=(first_finished_car_x, car_top_y),
                text=f"Finished Car Depth {int(first_lift.finished_car_depth)}",
                offset=-(first_finished_car_x - x_offset + 550),
                orientation="vertical",
            )

            # Unfinished car depth (left side, level 3) - from shared top edge
            draw_dimension_line(
                ax,
                start=(first_car_x, first_car_y),
                end=(first_car_x, car_top_y),
                text=f"Unfinished Car Depth {int(first_lift.unfinished_car_depth)}",
                offset=-(first_car_x - x_offset + 850),
                orientation="vertical",
            )

        # --- Separator dimension (if multiple lifts, level 3 - same as unfinished car width) ---
        if num_lifts > 1:
            separator_x = x_offset + wt + shaft_widths[0]
            if dim_above:
                draw_dimension_line(
                    ax,
                    start=(separator_x, shaft_top_y),
                    end=(separator_x + swt, shaft_top_y),
                    text=f"{int(swt)}",
                    offset=level3_offset,
                    orientation="horizontal",
                )
                # Steel beam label
                if separator_type == "steel_beam":
                    dim_y = shaft_top_y + level3_offset + 50
                    ax.text(
                        separator_x + swt / 2,
                        dim_y + 120,
                        "Steel\nBeam",
                        ha="center",
                        va="bottom",
                        fontsize=config.SEPARATOR_LABEL_SIZE,
                        color=config.DIMENSION_COLOR,
                    )
            else:
                draw_dimension_line(
                    ax,
                    start=(separator_x, base_y),
                    end=(separator_x + swt, base_y),
                    text=f"{int(swt)}",
                    offset=-level3_offset,
                    orientation="horizontal",
                )
                if separator_type == "steel_beam":
                    dim_y = base_y - level3_offset - 50
                    ax.text(
                        separator_x + swt / 2,
                        dim_y - 120,
                        "Steel\nBeam",
                        ha="center",
                        va="top",
                        fontsize=config.SEPARATOR_LABEL_SIZE,
                        color=config.DIMENSION_COLOR,
                    )

            # Total shaft width (level 3 - same as separator) - on the lobby/door side (front wall)
            total_internal_width = sum(shaft_widths) + (num_lifts - 1) * swt
            if dim_above:
                # Bank 1 (doors_face="down"): total shaft width at bottom (front wall)
                draw_dimension_line(
                    ax,
                    start=(x_offset + wt, front_wall_y),
                    end=(x_offset + wt + total_internal_width, front_wall_y),
                    text=f"Total Shaft Width {int(total_internal_width)}",
                    offset=-level3_offset,
                    orientation="horizontal",
                )
            else:
                # Bank 2 (doors_face="up"): total shaft width at top (front wall)
                draw_dimension_line(
                    ax,
                    start=(x_offset + wt, front_wall_y + wt),
                    end=(x_offset + wt + total_internal_width, front_wall_y + wt),
                    text=f"Total Shaft Width {int(total_internal_width)}",
                    offset=level3_offset,
                    orientation="horizontal",
                )

