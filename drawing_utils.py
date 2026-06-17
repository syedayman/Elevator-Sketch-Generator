"""
Drawing utility functions for lift shaft sketch generation.
"""

import io
from contextlib import contextmanager

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Polygon, Circle
from matplotlib.lines import Line2D
from PIL import Image, ImageOps
from typing import Tuple, Optional, List

# Support both package (relative) and standalone (absolute) imports
try:
    from . import config
except ImportError:
    import config


@contextmanager
def scaled_dimension_font(scale: float):
    """Temporarily scale dimension-label font + arrowhead size for the duration of a draw.

    All dimension text reads config.DIMENSION_TEXT_SIZE directly and draw_dimension_line
    reads config.DIMENSION_ARROW_MUTATION, so overriding both here scales every dimension
    label and its arrowheads (draw_dimension_line + inline ax.text) with no per-site
    plumbing. Originals are always restored. scale=1.0 is a no-op.

    Note: mutates module globals for the render window — fine for this single-user
    app; concurrent multi-session renders could theoretically interleave.
    """
    original_text = config.DIMENSION_TEXT_SIZE
    original_arrow = config.DIMENSION_ARROW_MUTATION
    try:
        config.DIMENSION_TEXT_SIZE = original_text * scale
        config.DIMENSION_ARROW_MUTATION = original_arrow * scale
        yield
    finally:
        config.DIMENSION_TEXT_SIZE = original_text
        config.DIMENSION_ARROW_MUTATION = original_arrow


def add_image_border(png_bytes: bytes) -> bytes:
    """Add a white pad + solid frame around a rendered PNG, returning new bytes.

    Applied to final output (file + bytes, plan + section) so every image ships
    with a border. Sizes/colors come from config.IMAGE_BORDER_*.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    # Scale border/pad with image width so displayed thickness stays constant after
    # the browser downscales the image; fall back to the absolute px floors.
    pad = max(config.IMAGE_BORDER_PAD, round(img.width * config.IMAGE_BORDER_PAD_FRAC))
    bw = max(config.IMAGE_BORDER_WIDTH, round(img.width * config.IMAGE_BORDER_WIDTH_FRAC))
    # Black frame first (inner), white pad outside it. This keeps the black frame
    # flanked by white so it stays visible on a dark page background too; on a white
    # download the outer white pad simply blends in.
    if bw > 0:
        img = ImageOps.expand(img, border=bw, fill=config.IMAGE_BORDER_COLOR)
    if pad > 0:
        img = ImageOps.expand(img, border=pad, fill=config.IMAGE_BORDER_PAD_COLOR)
    out = io.BytesIO()
    img.save(out, format="png")
    out.seek(0)
    return out.read()


def draw_wall_section(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    show_hatching: bool = True,
) -> None:
    """
    Draw a wall section with concrete hatching.

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate (mm)
        y: Bottom-left y coordinate (mm)
        width: Wall section width (mm)
        height: Wall section height (mm)
        show_hatching: Whether to show concrete hatching pattern
    """
    # Draw filled rectangle for wall
    wall = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.WALL_FILL_COLOR,
        edgecolor=config.WALL_EDGE_COLOR,
        linewidth=config.WALL_EDGE_WIDTH,
        zorder=2,
    )
    ax.add_patch(wall)

    # Add concrete hatching pattern (random dots for aggregate look)
    if show_hatching:
        add_concrete_hatch(ax, x, y, width, height)


def add_concrete_hatch(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Add random dot and triangle pattern to simulate concrete aggregate texture.

    Pattern includes:
    - Random filled dots of varying sizes (aggregate)
    - Small triangle outlines (stone chips)

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate
        y: Bottom-left y coordinate
        width: Section width
        height: Section height
    """
    # Calculate number of elements based on area and density
    area = width * height
    num_dots = int(area * config.HATCH_DENSITY)
    num_triangles = max(1, num_dots // 8)  # Fewer triangles than dots

    if num_dots > 0:
        # Generate random positions for dots
        np.random.seed(int(x + y) % 1000)  # Consistent seed for same position
        dot_x = np.random.uniform(x + 5, x + width - 5, num_dots)
        dot_y = np.random.uniform(y + 5, y + height - 5, num_dots)

        # Varying dot sizes
        dot_sizes = np.random.uniform(0.5, 2.0, num_dots) * config.HATCH_DOT_SIZE

        ax.scatter(
            dot_x,
            dot_y,
            s=dot_sizes,
            c=config.WALL_HATCH_COLOR,
            alpha=0.6,
            zorder=3,
        )

        # Add small triangle outlines (stone chips)
        tri_x = np.random.uniform(x + 10, x + width - 10, num_triangles)
        tri_y = np.random.uniform(y + 10, y + height - 10, num_triangles)
        tri_sizes = np.random.uniform(8, 18, num_triangles)  # Triangle size in mm
        tri_rotations = np.random.uniform(0, 360, num_triangles)  # Random rotation

        for i in range(num_triangles):
            size = tri_sizes[i]
            cx, cy = tri_x[i], tri_y[i]
            angle = np.radians(tri_rotations[i])

            # Create triangle vertices (equilateral-ish, slightly irregular)
            irregularity = np.random.uniform(0.7, 1.3, 3)
            angles = [0, 120, 240]
            vertices = []
            for j, a in enumerate(angles):
                rad = np.radians(a) + angle
                r = size * 0.5 * irregularity[j]
                vx = cx + r * np.cos(rad)
                vy = cy + r * np.sin(rad)
                vertices.append([vx, vy])

            triangle = Polygon(
                vertices,
                facecolor="none",
                edgecolor=config.WALL_HATCH_COLOR,
                linewidth=0.5,
                alpha=0.7,
                zorder=3,
            )
            ax.add_patch(triangle)


def draw_opening(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Draw a structural opening (door opening) in a wall.

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate
        y: Bottom-left y coordinate
        width: Opening width
        height: Opening height (wall thickness)
    """
    opening = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.OPENING_FILL_COLOR,
        edgecolor=config.WALL_EDGE_COLOR,
        linewidth=config.OPENING_EDGE_WIDTH,
        zorder=4,
    )
    ax.add_patch(opening)


def _dimension_label_with_units(text: str) -> str:
    """Return dimension label text with millimetre units."""
    label = str(text).strip()
    if not label:
        return label
    if label.lower().endswith("mm"):
        return label
    return f"{label} mm"


def draw_dimension_line(
    ax: plt.Axes,
    start: Tuple[float, float],
    end: Tuple[float, float],
    text: str,
    offset: float = None,
    orientation: str = "horizontal",
    ext_clip: float = None,
) -> None:
    """
    Draw a dimension line with arrows and text centered on the line.
    Uses straight line instead of arrows when dimension is too small.

    Args:
        ax: Matplotlib axes
        start: Start point (x, y)
        end: End point (x, y)
        text: Dimension text (e.g., "2950")
        offset: Offset from the object being measured
        orientation: "horizontal" or "vertical"
        ext_clip: If given, extension lines start at this coordinate (y for
            horizontal, x for vertical) instead of the measured object edge.
            Used to keep extension lines outside the shaft walls.
    """
    if offset is None:
        offset = config.DIMENSION_OFFSET

    label_text = _dimension_label_with_units(text)

    x1, y1 = start
    x2, y2 = end

    # Calculate dimension length to decide if arrows fit
    if orientation == "horizontal":
        dim_length = abs(x2 - x1)
    else:
        dim_length = abs(y2 - y1)

    # Use straight line if dimension is too small for arrows (less than 300mm)
    min_arrow_length = 300
    use_arrows = dim_length >= min_arrow_length

    if orientation == "horizontal":
        # Dimension line is horizontal, offset in y direction
        dim_y = y1 + offset

        # Extension lines (from object edge past dimension line, or from
        # ext_clip so they stay outside the shaft walls)
        ext_y1 = y1 if ext_clip is None else ext_clip
        ext_y2 = y2 if ext_clip is None else ext_clip
        ax.plot(
            [x1, x1], [ext_y1, dim_y + np.sign(offset) * config.DIMENSION_EXTENSION],
            color=config.DIMENSION_COLOR,
            linewidth=config.DIMENSION_LINE_WIDTH,
            zorder=5,
        )
        ax.plot(
            [x2, x2], [ext_y2, dim_y + np.sign(offset) * config.DIMENSION_EXTENSION],
            color=config.DIMENSION_COLOR,
            linewidth=config.DIMENSION_LINE_WIDTH,
            zorder=5,
        )

        if use_arrows:
            # Dimension line with arrows (shrinkA/B=0 ensures tips touch extension lines)
            ax.annotate(
                "",
                xy=(x2, dim_y),
                xytext=(x1, dim_y),
                arrowprops=dict(
                    arrowstyle="<->",
                    color=config.DIMENSION_COLOR,
                    lw=config.DIMENSION_LINE_WIDTH,
                    shrinkA=0,
                    shrinkB=0,
                    mutation_scale=config.DIMENSION_ARROW_MUTATION,
                ),
                zorder=5,
            )
        else:
            # Straight line for small dimensions
            ax.plot(
                [x1, x2], [dim_y, dim_y],
                color=config.DIMENSION_COLOR,
                linewidth=config.DIMENSION_LINE_WIDTH,
                zorder=5,
            )

        # Dimension text above the line (for negative offset, text goes below line toward drawing)
        mid_x = (x1 + x2) / 2
        # Position text above the dimension line
        text_offset = 30 if offset > 0 else -30
        ax.text(
            mid_x,
            dim_y + text_offset,
            label_text,
            ha="center",
            va="bottom" if offset > 0 else "top",
            fontsize=config.DIMENSION_TEXT_SIZE,
            color=config.DIMENSION_COLOR,
            zorder=6,
        )

    else:  # vertical
        # Dimension line is vertical, offset in x direction
        dim_x = x1 + offset

        # Extension lines (from object edge, or from ext_clip so they stay
        # outside the shaft walls)
        ext_x1 = x1 if ext_clip is None else ext_clip
        ext_x2 = x2 if ext_clip is None else ext_clip
        ax.plot(
            [ext_x1, dim_x + np.sign(offset) * config.DIMENSION_EXTENSION], [y1, y1],
            color=config.DIMENSION_COLOR,
            linewidth=config.DIMENSION_LINE_WIDTH,
            zorder=5,
        )
        ax.plot(
            [ext_x2, dim_x + np.sign(offset) * config.DIMENSION_EXTENSION], [y2, y2],
            color=config.DIMENSION_COLOR,
            linewidth=config.DIMENSION_LINE_WIDTH,
            zorder=5,
        )

        if use_arrows:
            # Dimension line with arrows (shrinkA/B=0 ensures tips touch extension lines)
            ax.annotate(
                "",
                xy=(dim_x, y2),
                xytext=(dim_x, y1),
                arrowprops=dict(
                    arrowstyle="<->",
                    color=config.DIMENSION_COLOR,
                    lw=config.DIMENSION_LINE_WIDTH,
                    shrinkA=0,
                    shrinkB=0,
                    mutation_scale=config.DIMENSION_ARROW_MUTATION,
                ),
                zorder=5,
            )
        else:
            # Straight line for small dimensions
            ax.plot(
                [dim_x, dim_x], [y1, y2],
                color=config.DIMENSION_COLOR,
                linewidth=config.DIMENSION_LINE_WIDTH,
                zorder=5,
            )

        # Dimension text beside the line (rotated for vertical)
        mid_y = (y1 + y2) / 2
        # Position text to the right of the dimension line
        text_offset = 30 if offset > 0 else -30
        ax.text(
            dim_x + text_offset,
            mid_y,
            label_text,
            ha="left" if offset > 0 else "right",
            va="center",
            fontsize=config.DIMENSION_TEXT_SIZE,
            color=config.DIMENSION_COLOR,
            rotation=90,
            zorder=6,
        )


def draw_centerline(
    ax: plt.Axes,
    start: Tuple[float, float],
    end: Tuple[float, float],
    extend: float = 100,
) -> None:
    """
    Draw a dashed centerline.

    Args:
        ax: Matplotlib axes
        start: Start point (x, y)
        end: End point (x, y)
        extend: How much to extend beyond start/end points
    """
    x1, y1 = start
    x2, y2 = end

    # Calculate direction and extend the line
    dx = x2 - x1
    dy = y2 - y1
    length = np.sqrt(dx**2 + dy**2)

    if length > 0:
        ux, uy = dx / length, dy / length
        x1_ext = x1 - ux * extend
        y1_ext = y1 - uy * extend
        x2_ext = x2 + ux * extend
        y2_ext = y2 + uy * extend
    else:
        x1_ext, y1_ext = x1, y1
        x2_ext, y2_ext = x2, y2

    line = Line2D(
        [x1_ext, x2_ext],
        [y1_ext, y2_ext],
        color=config.CENTERLINE_COLOR,
        linewidth=config.CENTERLINE_WIDTH,
        linestyle="--",
        dashes=config.CENTERLINE_DASH_PATTERN,
        zorder=5,
    )
    ax.add_line(line)


def draw_shaft_interior(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Draw the interior space of the shaft.

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate
        y: Bottom-left y coordinate
        width: Interior width
        height: Interior height
    """
    interior = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.SHAFT_INTERIOR_COLOR,
        edgecolor="none",
        zorder=1,
    )
    ax.add_patch(interior)


def draw_title_block(
    ax: plt.Axes,
    title: str,
    subtitle: Optional[str] = None,
    y_position: float = -200,
) -> None:
    """
    Draw title and subtitle below the drawing.

    Args:
        ax: Matplotlib axes
        title: Main title text
        subtitle: Optional subtitle/notes
        y_position: Y position for title (in drawing coordinates)
    """
    # Get the center of the current axes in data coordinates
    xlim = ax.get_xlim()
    center_x = (xlim[0] + xlim[1]) / 2

    ax.text(
        center_x,
        y_position,
        title,
        ha="center",
        va="top",
        fontsize=config.TITLE_FONT_SIZE,
        fontweight="bold",
        color=config.TITLE_COLOR,
        zorder=10,
    )

    if subtitle:
        ax.text(
            center_x,
            y_position - 250,
            subtitle,
            ha="center",
            va="top",
            fontsize=config.SUBTITLE_FONT_SIZE,
            color=config.TITLE_COLOR,
            zorder=10,
        )


def draw_steel_beam(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    label: Optional[str] = None,
) -> None:
    """
    Draw a steel separator beam between lift shafts.

    Steel beams are used between multiple passenger lifts in a common shaft.
    Uses ANSI 32 steel hatch pattern (diagonal lines at 45 degrees).

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate (mm)
        y: Bottom-left y coordinate (mm)
        width: Beam width (mm)
        height: Beam height (mm)
        label: Optional label text (e.g., "SEPARATOR STEEL BEAM")
    """
    # Draw beam with light fill
    beam = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.STEEL_BEAM_COLOR,
        edgecolor=config.STEEL_BEAM_EDGE_COLOR,
        linewidth=config.STEEL_BEAM_EDGE_WIDTH,
        zorder=3,
    )
    ax.add_patch(beam)

    # Add ANSI 32 steel hatch pattern (diagonal lines at 45 degrees)
    # Lines go from bottom-left to top-right
    hatch_spacing = 40  # mm between diagonal lines
    hatch_color = "#000000"
    hatch_linewidth = 0.5

    # Calculate the diagonal span needed to cover the rectangle
    diagonal_length = width + height

    # Create clipping path for the beam area
    from matplotlib.patches import Rectangle as ClipRect
    clip_rect = ClipRect((x, y), width, height, transform=ax.transData)

    # Draw diagonal lines from bottom-left to top-right
    # Start from bottom-left corner and move along the perimeter
    num_lines = int(diagonal_length / hatch_spacing) + 1

    for i in range(num_lines):
        offset = i * hatch_spacing

        # Line starts from left edge or bottom edge
        if offset <= height:
            x1 = x
            y1 = y + offset
        else:
            x1 = x + (offset - height)
            y1 = y + height

        # Line ends at right edge or top edge
        if offset <= width:
            x2 = x + offset
            y2 = y
        else:
            x2 = x + width
            y2 = y + (offset - width)

        # Only draw if line is within bounds
        if x1 <= x + width and y2 <= y + height:
            line = Line2D(
                [x1, x2], [y1, y2],
                color=hatch_color,
                linewidth=hatch_linewidth,
                zorder=3.5,
            )
            line.set_clip_path(clip_rect)
            ax.add_line(line)

    # Add label if provided
    if label:
        center_x = x + width / 2
        center_y = y + height / 2
        ax.text(
            center_x,
            center_y,
            label,
            ha="center",
            va="center",
            fontsize=config.SEPARATOR_LABEL_SIZE,
            color=config.DIMENSION_COLOR,
            rotation=90 if width < height else 0,
            backgroundcolor="white",
            zorder=4,
        )


def draw_counterweight_bracket(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    show_pulley: bool = True,
    align: str = "left",
    box_width: float = None,
    box_depth: float = None,
) -> None:
    """
    Draw the counterweight bracket area with double-outline frame.

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate (mm)
        y: Bottom-left y coordinate (mm)
        width: Bracket space width (for positioning, mm)
        height: Bracket space height (for positioning, mm)
        show_pulley: Whether to show pulley/weight representation
        align: "left"/"right" — which shaft wall the open frame side faces
        box_width: CW box full width (mm); None = config default (450)
        box_depth: CW box depth/height in plan (mm); None = config default (1000)
    """
    # Visual CW box dimensions (frame open on the wall side, so the drawn
    # rectangle is box_width minus the missing wall-side bar)
    full_box_width = box_width if box_width is not None else config.CW_BOX_WIDTH
    box_height = box_depth if box_depth is not None else config.CW_BOX_HEIGHT
    frame_thickness = config.CW_FRAME_THICKNESS  # 50mm
    box_width = full_box_width - frame_thickness  # Shorter since no wall-side bar

    # Flush against the shaft wall (open frame side faces the wall)
    if align == "left":
        box_x = x
    else:  # right
        box_x = x + width - box_width
    box_y = y + (height - box_height) / 2

    frame_color = config.CW_FRAME_COLOR
    edge_color = config.BRACKET_EDGE_COLOR
    edge_width = config.BRACKET_EDGE_WIDTH
    frame_fill_style = dict(facecolor=frame_color, edgecolor="none", zorder=2)
    outline_style = dict(
        facecolor="none",
        edgecolor=edge_color,
        linewidth=edge_width,
        zorder=3,
        joinstyle="miter",
        capstyle="butt",
    )

    if align == "left":
        # Simple frame: fill bars + two rectangle outlines (outer + offset inner)
        ax.add_patch(Rectangle(
            (box_x, box_y + box_height - frame_thickness),
            box_width,
            frame_thickness,
            **frame_fill_style,
        ))
        ax.add_patch(Rectangle(
            (box_x, box_y),
            box_width,
            frame_thickness,
            **frame_fill_style,
        ))
        ax.add_patch(Rectangle(
            (box_x + box_width - frame_thickness, box_y),
            frame_thickness,
            box_height,
            **frame_fill_style,
        ))

        # Outer rectangle
        ax.add_patch(Rectangle(
            (box_x, box_y),
            box_width,
            box_height,
            **outline_style,
        ))
        # Inner rectangle: shifted up by thickness; width/height reduced
        ax.add_patch(Rectangle(
            (box_x, box_y + frame_thickness),
            box_width - frame_thickness,
            box_height - 2 * frame_thickness,
            **outline_style,
        ))
    else:  # align == "right"
        # Simple frame: fill bars + two rectangle outlines (outer + offset inner)
        ax.add_patch(Rectangle(
            (box_x, box_y + box_height - frame_thickness),
            box_width,
            frame_thickness,
            **frame_fill_style,
        ))
        ax.add_patch(Rectangle(
            (box_x, box_y),
            box_width,
            frame_thickness,
            **frame_fill_style,
        ))
        ax.add_patch(Rectangle(
            (box_x, box_y),
            frame_thickness,
            box_height,
            **frame_fill_style,
        ))

        # Outer rectangle
        ax.add_patch(Rectangle(
            (box_x, box_y),
            box_width,
            box_height,
            **outline_style,
        ))
        # Inner rectangle: shifted up+right by thickness; width/height reduced
        ax.add_patch(Rectangle(
            (box_x + frame_thickness, box_y + frame_thickness),
            box_width - frame_thickness,
            box_height - 2 * frame_thickness,
            **outline_style,
        ))

    # Draw inner CW box (elongated: 35% width x 80% height of original box)
    if show_pulley:
        cw_width = full_box_width * 0.35   # 35% of original = ~157mm
        cw_height = box_height * 0.8  # 80% = 800mm
        # Center within the visible bracket area
        cw_x = box_x + (box_width - cw_width) / 2
        cw_y = box_y + (box_height - cw_height) / 2

        counterweight = Rectangle(
            (cw_x, cw_y),
            cw_width,
            cw_height,
            facecolor=config.CW_BOX_COLOR,
            edgecolor=config.BRACKET_EDGE_COLOR,
            linewidth=config.BRACKET_EDGE_WIDTH,
            zorder=3,
        )
        ax.add_patch(counterweight)


def draw_car_bracket(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Draw the car bracket area on the right side of the shaft.

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate (mm)
        y: Bottom-left y coordinate (mm)
        width: Bracket width (mm)
        height: Bracket height (mm)
    """
    bracket = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.CAR_BRACKET_COLOR,
        edgecolor=config.BRACKET_EDGE_COLOR,
        linewidth=config.BRACKET_EDGE_WIDTH,
        zorder=2,
    )
    ax.add_patch(bracket)


def draw_lift_car(
    ax: plt.Axes,
    x: float,
    y: float,
    unfinished_width: float,
    unfinished_depth: float,
    finished_width: float,
    finished_depth: float,
    car_wall_thickness: float = None,
    mirrored: bool = False,
    door_width: float = None,
    lift_type: str = "passenger",
    door_opening_type: str = "centre",
    double_entrance: bool = False,
    door_offset: float = 0,
    rail_width_left: float = None,
    rail_width_right: float = None,
) -> None:
    """
    Draw the lift car with both unfinished and finished boundaries.

    The unfinished car (dotted) is drawn as 3 lines, open on the door side:
    - Normal: top, left, right (open at bottom where doors are)
    - Mirrored: bottom, left, right (open at top where doors are)

    The finished car (solid) is a complete rectangle.

    Args:
        ax: Matplotlib axes
        x: Bottom-left x coordinate of unfinished car (mm)
        y: Bottom-left y coordinate of unfinished car (mm)
        unfinished_width: Unfinished car width (mm)
        unfinished_depth: Unfinished car depth (mm)
        finished_width: Finished car width (mm)
        finished_depth: Finished car depth (mm)
        car_wall_thickness: Thickness between unfinished and finished (mm)
        mirrored: If True, doors are at top (Bank 2), open unfinished outline at top
        door_width: Door opening width for front return calculation (mm)
        lift_type: Lift type ('passenger' or 'fire')
        door_opening_type: Door opening type ('centre' or 'telescopic')
        door_offset: Signed door X offset from cabin centre (+ = right/screen); shifts the front returns
    """
    if car_wall_thickness is None:
        car_wall_thickness = config.DEFAULT_CAR_WALL_THICKNESS

    # Calculate finished car position (centered horizontally)
    finished_x = x + (unfinished_width - finished_width) / 2

    if mirrored:
        # Mirrored: finished car TOP aligns with unfinished car TOP (door side)
        # Unfinished extends downward beyond finished
        finished_y = y + (unfinished_depth - finished_depth)
    else:
        # Normal: finished car BOTTOM aligns with unfinished car BOTTOM (door side)
        # Unfinished extends upward beyond finished
        finished_y = y

    # Draw finished car as complete solid rectangle (all 4 sides)
    finished_car = Rectangle(
        (finished_x, finished_y),
        finished_width,
        finished_depth,
        facecolor=config.FINISHED_CAR_COLOR,
        edgecolor=config.FINISHED_CAR_EDGE_COLOR,
        linewidth=config.CAR_EDGE_WIDTH,
        zorder=5,
    )
    ax.add_patch(finished_car)

    # Draw unfinished car boundary as 3 dashed lines
    # Open on the door side (bottom for normal, top for mirrored)
    unfinished_line_style = dict(
        color=config.UNFINISHED_CAR_EDGE_COLOR,
        linewidth=config.CAR_EDGE_WIDTH,
        linestyle="--",
        zorder=6,
    )

    # Left side (from bottom to top) - always drawn
    ax.plot([x, x], [y, y + unfinished_depth], **unfinished_line_style)
    # Right side (from bottom to top) - always drawn
    ax.plot([x + unfinished_width, x + unfinished_width], [y, y + unfinished_depth], **unfinished_line_style)

    if mirrored:
        # Mirrored: doors at top, so draw bottom line (open at top)
        ax.plot([x, x + unfinished_width], [y, y], **unfinished_line_style)
    else:
        # Normal: doors at bottom, so draw top line (open at bottom)
        ax.plot([x, x + unfinished_width], [y + unfinished_depth, y + unfinished_depth], **unfinished_line_style)

    # Draw front returns (two rectangles at the door-side edge of the finished car)
    if door_width is not None and door_width < finished_width:
        front_return_depth = 100  # mm

        # Front returns are symmetric when the door is centred; a door offset
        # (world +x = right) widens the left return and narrows the right one.
        left_return_width = (finished_width - door_width) / 2 + door_offset
        right_return_width = (finished_width - door_width) / 2 - door_offset

        if mirrored:
            # Doors at top: front returns at top edge of finished car
            return_y = finished_y + finished_depth - front_return_depth
        else:
            # Doors at bottom: front returns at bottom edge of finished car
            return_y = finished_y

        # Left front return
        if left_return_width > 0:
            ax.add_patch(Rectangle(
                (finished_x, return_y),
                left_return_width, front_return_depth,
                facecolor="none",
                edgecolor=config.FINISHED_CAR_EDGE_COLOR,
                linewidth=config.CAR_EDGE_WIDTH,
                zorder=6,
            ))

        # Right front return
        if right_return_width > 0:
            ax.add_patch(Rectangle(
                (finished_x + finished_width - right_return_width, return_y),
                right_return_width, front_return_depth,
                facecolor="none",
                edgecolor=config.FINISHED_CAR_EDGE_COLOR,
                linewidth=config.CAR_EDGE_WIDTH,
                zorder=6,
            ))

    # Draw rear front returns for double entrance (at the rear door-side edge of finished car)
    if double_entrance and door_width is not None and door_width < finished_width:
        rear_return_depth = 100  # mm
        left_return_width = (finished_width - door_width) / 2 + door_offset
        right_return_width = (finished_width - door_width) / 2 - door_offset

        if mirrored:
            # Mirrored: rear is at bottom edge of finished car
            rear_return_y = finished_y
        else:
            # Normal: rear is at top edge of finished car
            rear_return_y = finished_y + finished_depth - rear_return_depth

        if left_return_width > 0:
            ax.add_patch(Rectangle(
                (finished_x, rear_return_y),
                left_return_width, rear_return_depth,
                facecolor="none",
                edgecolor=config.FINISHED_CAR_EDGE_COLOR,
                linewidth=config.CAR_EDGE_WIDTH,
                zorder=6,
            ))
        if right_return_width > 0:
            ax.add_patch(Rectangle(
                (finished_x + finished_width - right_return_width, rear_return_y),
                right_return_width, rear_return_depth,
                facecolor="none",
                edgecolor=config.FINISHED_CAR_EDGE_COLOR,
                linewidth=config.CAR_EDGE_WIDTH,
                zorder=6,
            ))

    # Draw guide rail symbols on left and right edges of unfinished car
    car_vertical_center = y + unfinished_depth / 2
    # Left side: rectangle extends leftward from dashed line
    draw_guide_rail_symbol(ax, x, car_vertical_center, side="left", rail_width=rail_width_left)
    # Right side: rectangle extends rightward from dashed line
    draw_guide_rail_symbol(ax, x + unfinished_width, car_vertical_center, side="right", rail_width=rail_width_right)


def draw_door_panels(
    ax: plt.Axes,
    x: float,
    y: float,
    door_width: float,
    wall_thickness: float,
    num_panels: int = 2,
) -> None:
    """
    Draw door panel divisions within the door opening.

    Args:
        ax: Matplotlib axes
        x: Left x coordinate of door opening (mm)
        y: Bottom y coordinate of door opening (mm)
        door_width: Total door width (mm)
        wall_thickness: Wall thickness (door depth) (mm)
        num_panels: Number of door panels (2 or 4)
    """
    panel_width = door_width / num_panels

    for i in range(1, num_panels):
        panel_x = x + i * panel_width
        ax.plot(
            [panel_x, panel_x],
            [y, y + wall_thickness],
            color=config.DIMENSION_COLOR,
            linewidth=config.DOOR_PANEL_LINE_WIDTH,
            linestyle="-",
            zorder=5,
        )


def draw_capacity_label(
    ax: plt.Axes,
    x: float,
    y: float,
    capacity: int,
) -> None:
    """
    Draw capacity label centered in the lift car.

    Args:
        ax: Matplotlib axes
        x: Center x coordinate (mm)
        y: Center y coordinate (mm)
        capacity: Lift capacity in KG
    """
    ax.text(
        x,
        y,
        f"{capacity} KG",
        ha="center",
        va="center",
        fontsize=config.CAPACITY_TEXT_SIZE,
        fontweight="bold",
        color=config.CAPACITY_TEXT_COLOR,
        zorder=10,
    )


def draw_cop_marker(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float = None,
    height: float = None,
    position: str = "left",
) -> None:
    """
    Draw a Car Operating Panel (C.O.P) marker.

    Args:
        ax: Matplotlib axes
        x: X coordinate for marker
        y: Y coordinate for marker
        width: Marker width (mm)
        height: Marker height (mm)
        position: "left" or "right" side of car
    """
    if width is None:
        width = config.COP_MARKER_WIDTH
    if height is None:
        height = config.COP_MARKER_HEIGHT

    # Draw COP rectangle
    cop = Rectangle(
        (x - width / 2, y - height / 2),
        width,
        height,
        facecolor=config.COP_COLOR,
        edgecolor="#404040",
        linewidth=0.5,
        zorder=8,
    )
    ax.add_patch(cop)

    # Add "C.O.P" label
    ax.text(
        x,
        y,
        "C.O.P",
        ha="center",
        va="center",
        fontsize=config.COP_TEXT_SIZE,
        color="white",
        fontweight="bold",
        rotation=90,
        zorder=9,
    )


def draw_accessibility_symbol(
    ax: plt.Axes,
    x: float,
    y: float,
    size: float = 150,
) -> None:
    """
    Draw wheelchair accessibility symbol.

    Args:
        ax: Matplotlib axes
        x: Center x coordinate (mm)
        y: Center y coordinate (mm)
        size: Symbol size (mm)
    """
    # Draw a simple wheelchair symbol using Unicode
    ax.text(
        x,
        y,
        "♿",
        ha="center",
        va="center",
        fontsize=config.ACCESSIBILITY_SYMBOL_SIZE,
        color=config.ACCESSIBILITY_COLOR,
        zorder=10,
    )


def draw_car_interior_details(
    ax: plt.Axes,
    car_x: float,
    car_y: float,
    car_width: float,
    car_depth: float,
    capacity: Optional[int] = None,
    show_cop: bool = True,
    show_accessibility: bool = True,
    cop_position: str = "left",
) -> None:
    """
    Draw interior details of the lift car (capacity, C.O.P, accessibility).

    Args:
        ax: Matplotlib axes
        car_x: Left x coordinate of finished car interior (mm)
        car_y: Bottom y coordinate of finished car interior (mm)
        car_width: Finished car width (mm)
        car_depth: Finished car depth (mm)
        capacity: Lift capacity in KG
        show_cop: Whether to show C.O.P marker
        show_accessibility: Whether to show accessibility symbol
        cop_position: "left" or "right" for C.O.P placement
    """
    center_x = car_x + car_width / 2
    center_y = car_y + car_depth / 2

    # Draw capacity label in center
    if capacity:
        draw_capacity_label(ax, center_x, center_y + car_depth * 0.2, capacity)

    # Draw accessibility symbol below capacity
    if show_accessibility:
        draw_accessibility_symbol(ax, center_x, center_y - car_depth * 0.15)

    # Draw C.O.P marker on specified side
    if show_cop:
        cop_offset = 60  # Distance from car wall
        if cop_position == "left":
            cop_x = car_x + cop_offset + config.COP_MARKER_WIDTH / 2
        else:
            cop_x = car_x + car_width - cop_offset - config.COP_MARKER_WIDTH / 2
        cop_y = center_y
        draw_cop_marker(ax, cop_x, cop_y, position=cop_position)


def _draw_door_inner_details(
    ax: plt.Axes,
    door_rect_left: float,
    door_rect_width: float,
    door_y: float,
    door_thickness: float,
    door_width: float,
    door_opening_center_x: float = None,
    telescopic_side: str = None,
) -> None:
    """
    Draw inner frame lines and door panels inside a door rectangle.

    Args:
        ax: Matplotlib axes
        door_rect_left: Left x coordinate of the door rectangle (mm)
        door_rect_width: Full width of the door rectangle (mm)
        door_y: Bottom y coordinate of the door rectangle (mm)
        door_thickness: Height/thickness of the door rectangle (mm)
        door_width: Actual door opening width for panel sizing (mm)
        door_opening_center_x: Center x of actual door opening (for telescopic doors
            where rect center differs from opening center). If None, uses rect center.
    """
    door_center_x = door_opening_center_x if door_opening_center_x is not None else door_rect_left + door_rect_width / 2

    panel_props = dict(
        facecolor="none",
        edgecolor=config.LIFT_DOOR_EDGE_COLOR,
        linewidth=config.LIFT_DOOR_PANEL_EDGE_WIDTH,
        zorder=8,
    )

    if telescopic_side in ("left", "right"):
        # Telescopic: two bold panels staggered within the band — one row above
        # the band centerline, one below — overlapping at the centre by p on each
        # side so their union spans exactly door_width. telescopic_side picks
        # which panel rides the upper row, so the landing and car bands mirror
        # each other. No thin frame lines for telescopic bands.
        half = door_width / 2
        p = config.TELESCOPIC_INNER_OVERLAP_RATIO * door_width
        row_height = config.TELESCOPIC_PANEL_ROW_HEIGHT
        row_gap = config.TELESCOPIC_PANEL_ROW_GAP
        upper_y = door_y + door_thickness / 2 + row_gap / 2
        lower_y = door_y + door_thickness / 2 - row_gap / 2 - row_height
        left_span = (door_center_x - half, door_center_x + p)
        right_span = (door_center_x - p, door_center_x + half)
        if telescopic_side == "left":
            upper_span, lower_span = right_span, left_span
        else:
            upper_span, lower_span = left_span, right_span
        ax.add_patch(Rectangle(
            (upper_span[0], upper_y), upper_span[1] - upper_span[0], row_height, **panel_props))
        ax.add_patch(Rectangle(
            (lower_span[0], lower_y), lower_span[1] - lower_span[0], row_height, **panel_props))
        return

    # Calculate frame line y positions (37.5mm from top/bottom)
    frame_margin = config.LIFT_DOOR_FRAME_MARGIN
    bottom_frame_y = door_y + frame_margin
    top_frame_y = door_y + door_thickness - frame_margin

    # Draw horizontal frame lines (full width of door rectangle)
    frame_line_props = dict(
        color=config.LIFT_DOOR_EDGE_COLOR,
        linewidth=config.LIFT_DOOR_FRAME_LINE_WIDTH,
        zorder=8,
    )
    ax.plot(
        [door_rect_left, door_rect_left + door_rect_width],
        [bottom_frame_y, bottom_frame_y],
        **frame_line_props,
    )
    ax.plot(
        [door_rect_left, door_rect_left + door_rect_width],
        [top_frame_y, top_frame_y],
        **frame_line_props,
    )

    # Panel y position (centered vertically between frame lines)
    panel_height = config.LIFT_DOOR_PANEL_HEIGHT
    panel_y = door_y + (door_thickness - panel_height) / 2

    # Centre opening: two panels side by side, each half the door width
    panel_width = door_width / 2
    ax.add_patch(Rectangle((door_center_x - door_width / 2, panel_y), panel_width, panel_height, **panel_props))
    ax.add_patch(Rectangle((door_center_x, panel_y), panel_width, panel_height, **panel_props))


def draw_lift_doors(
    ax: plt.Axes,
    center_x: float,
    wall_inner_y: float,
    door_width: float,
    structural_opening_width: float = None,
    door_extension: float = None,
    door_thickness: float = None,
    door_gap: float = None,
    mirrored: bool = False,
    door_opening_type: str = "centre",
    telescopic_left_ext: float = None,
    telescopic_right_ext: float = None,
    match_front_telescopic: bool = False,
) -> dict:
    """
    Draw landing door and car door at the bottom of the shaft.

    The doors are positioned inside the shaft, touching the inner edge of the front wall.
    Landing door is closer to the wall opening, car door is further inside the shaft.

    Args:
        ax: Matplotlib axes
        center_x: Horizontal center (door opening center) (mm)
        wall_inner_y: Inner edge of front wall (y = wall_thickness) (mm)
        door_width: Door opening width (mm)
        structural_opening_width: Structural opening width in front wall (mm)
        door_extension: Extension beyond door width on each side (mm)
        door_thickness: Thickness of each door (mm)
        door_gap: Gap between landing and car door (mm)
        mirrored: If True, doors are drawn below wall_inner_y (for facing banks Bank 2)

    Returns:
        dict with geometry info for car connection:
        {
            'car_door_top_y': float,    # Top of car door (for neck connection)
            'door_rect_left': float,    # Left x of door rectangles
            'door_rect_width': float,   # Width of door rectangles
        }
    """
    if structural_opening_width is None:
        structural_opening_width = config.DEFAULT_STRUCTURAL_OPENING_WIDTH
    if door_extension is None:
        door_extension = config.DEFAULT_DOOR_EXTENSION
    if door_thickness is None:
        door_thickness = config.DEFAULT_LIFT_DOOR_THICKNESS
    if door_gap is None:
        door_gap = config.DEFAULT_DOOR_GAP

    # Calculate door rectangle dimensions
    if door_opening_type == "telescopic" and telescopic_left_ext is not None and telescopic_right_ext is not None:
        # Telescopic: asymmetric rectangle around door opening
        # Left edge = (center_x - door_width/2) - left_ext
        # Right edge = (center_x + door_width/2) + right_ext
        door_rect_left = (center_x - door_width / 2) - telescopic_left_ext
        door_rect_right = (center_x + door_width / 2) + telescopic_right_ext
        door_rect_width = door_rect_right - door_rect_left
    else:
        # Centre opening: symmetric rectangle
        # Total door width = 2 × door_width + 200mm (e.g., 2 × 1100 + 200 = 2400mm)
        door_rect_width = 2 * door_width + 2 * door_extension
        door_rect_left = center_x - door_rect_width / 2

    if mirrored:
        # Mirrored: doors extend downward from wall_inner_y
        # Car door is closer to the wall, landing door is further into shaft
        car_door_y = wall_inner_y - door_thickness
        landing_door_y = car_door_y - door_gap - door_thickness
    else:
        # Normal: doors extend upward from wall_inner_y
        # Landing door position (touching inner edge of front wall)
        landing_door_y = wall_inner_y
        # Car door position (above landing door + gap)
        car_door_y = wall_inner_y + door_thickness + door_gap

    # Telescopic: stagger the bold inner rectangle — near-wall door -> left, deeper -> right.
    # (Mirrored Bank-2: the car door is the near-wall one, so the sides swap.)
    # A double-entrance rear door is positioned with `mirrored` flipped vs its own
    # front door; match_front_telescopic flips the stagger back so the rear panels
    # read identically to the front instead of mirroring them.
    _is_telescopic = door_opening_type == "telescopic"
    _tel_mirrored = (not mirrored) if match_front_telescopic else mirrored
    landing_side = ("left" if not _tel_mirrored else "right") if _is_telescopic else None
    car_side = ("right" if not _tel_mirrored else "left") if _is_telescopic else None

    # Draw landing door rectangle
    landing_door = Rectangle(
        (door_rect_left, landing_door_y),
        door_rect_width,
        door_thickness,
        facecolor=config.LIFT_DOOR_FILL_COLOR,
        edgecolor=config.LIFT_DOOR_EDGE_COLOR,
        linewidth=config.LIFT_DOOR_EDGE_WIDTH,
        zorder=7,
    )
    ax.add_patch(landing_door)

    # Draw inner details for landing door
    _draw_door_inner_details(
        ax, door_rect_left, door_rect_width, landing_door_y, door_thickness, door_width,
        door_opening_center_x=center_x,
        telescopic_side=landing_side,
    )

    # Draw car door rectangle
    car_door = Rectangle(
        (door_rect_left, car_door_y),
        door_rect_width,
        door_thickness,
        facecolor=config.LIFT_DOOR_FILL_COLOR,
        edgecolor=config.LIFT_DOOR_EDGE_COLOR,
        linewidth=config.LIFT_DOOR_EDGE_WIDTH,
        zorder=7,
    )
    ax.add_patch(car_door)

    # Draw inner details for car door
    _draw_door_inner_details(
        ax, door_rect_left, door_rect_width, car_door_y, door_thickness, door_width,
        door_opening_center_x=center_x,
        telescopic_side=car_side,
    )

    # Return geometry info for car connection
    if mirrored:
        return {
            'car_door_top_y': landing_door_y,  # Bottom of doors in mirrored mode
            'door_rect_left': door_rect_left,
            'door_rect_width': door_rect_width,
        }
    else:
        return {
            'car_door_top_y': car_door_y + door_thickness,
            'door_rect_left': door_rect_left,
            'door_rect_width': door_rect_width,
        }


def draw_door_jambs(
    ax: plt.Axes,
    opening_x: float,
    wall_inner_y: float,
    structural_opening_width: float,
    mirrored: bool = False,
) -> None:
    """
    Draw door jambs at the edges of the structural wall opening.

    Jambs are fixed to the wall opening position, not the door center.
    - Normal: top edge flush with wall inner face, extending down into wall
    - Mirrored: bottom edge flush with wall inner face, extending up into wall

    Args:
        ax: Matplotlib axes
        opening_x: Left x coordinate of the structural opening in the wall (mm)
        wall_inner_y: Inner edge of front wall (mm)
        structural_opening_width: Width of the structural opening (mm)
        mirrored: If True, jambs extend upward instead of downward
    """
    jamb_width = config.DOOR_JAMB_WIDTH
    jamb_height = config.DOOR_JAMB_HEIGHT

    if mirrored:
        # Mirrored: bottom edge flush with wall inner face, extends up
        jamb_y = wall_inner_y
    else:
        # Normal: top edge flush with wall inner face, extends down
        jamb_y = wall_inner_y - jamb_height

    # Left door jamb (at left edge of structural opening)
    left_jamb_x = opening_x
    left_jamb = Rectangle(
        (left_jamb_x, jamb_y),
        jamb_width,
        jamb_height,
        facecolor=config.LIFT_DOOR_FILL_COLOR,
        edgecolor=config.LIFT_DOOR_EDGE_COLOR,
        linewidth=config.LIFT_DOOR_EDGE_WIDTH,
        zorder=7,
    )
    ax.add_patch(left_jamb)

    # Right door jamb (at right edge of structural opening)
    right_jamb_x = opening_x + structural_opening_width - jamb_width
    right_jamb = Rectangle(
        (right_jamb_x, jamb_y),
        jamb_width,
        jamb_height,
        facecolor=config.LIFT_DOOR_FILL_COLOR,
        edgecolor=config.LIFT_DOOR_EDGE_COLOR,
        linewidth=config.LIFT_DOOR_EDGE_WIDTH,
        zorder=7,
    )
    ax.add_patch(right_jamb)


def draw_door_extension(
    ax: plt.Axes,
    car_bottom_y: float,
    car_door_top_y: float,
    extension_left_x: float,
    extension_right_x: float,
) -> None:
    """
    Draw the neck/extension connecting car bottom to car door.

    Two vertical lines from car bottom down to car door top.

    Args:
        ax: Matplotlib axes
        car_bottom_y: Bottom of lift car (mm)
        car_door_top_y: Top of car door (mm)
        extension_left_x: Left edge of extension (mm)
        extension_right_x: Right edge of extension (mm)
    """
    # Draw left vertical line
    ax.plot(
        [extension_left_x, extension_left_x],
        [car_door_top_y, car_bottom_y],
        color=config.DOOR_EXTENSION_COLOR,
        linewidth=config.DOOR_EXTENSION_LINE_WIDTH,
        zorder=6,
    )

    # Draw right vertical line
    ax.plot(
        [extension_right_x, extension_right_x],
        [car_door_top_y, car_bottom_y],
        color=config.DOOR_EXTENSION_COLOR,
        linewidth=config.DOOR_EXTENSION_LINE_WIDTH,
        zorder=6,
    )


def draw_guide_rail_symbol(
    ax: plt.Axes,
    x: float,
    y: float,
    side: str = "left",
    rail_width: float = None,
) -> None:
    """
    Draw a guide rail symbol (vertical box with T-shape extending outward).

    The symbol consists of:
    - A vertical white rectangle box with one edge ON the dashed line
    - A black T-shape (horizontal stem + vertical bar) extending outward from box center

    For RIGHT side: box left edge ON dashed line, T extends rightward
    For LEFT side: box right edge ON dashed line, T extends leftward

    Args:
        ax: Matplotlib axes
        x: X coordinate of the dashed line edge
        y: Y coordinate (vertical center of symbol)
        side: "left" or "right" - determines which direction T extends
        rail_width: Total rail width (box + stem + bar). Box and bar are fixed;
            the stem absorbs the difference. None = config default.
    """
    box_width = config.GUIDE_RAIL_BOX_WIDTH
    box_height = config.GUIDE_RAIL_BOX_HEIGHT
    stem_thickness = config.GUIDE_RAIL_STEM_THICKNESS
    bar_height = config.GUIDE_RAIL_BAR_HEIGHT
    bar_thickness = config.GUIDE_RAIL_BAR_THICKNESS
    if rail_width is not None:
        stem_length = max(0.0, rail_width - box_width - bar_thickness)
    else:
        stem_length = config.GUIDE_RAIL_STEM_LENGTH

    if side == "right":
        # RIGHT side: box left edge ON dashed line, extends rightward
        box_x = x  # Left edge ON dashed line
        box_y = y - box_height / 2  # Vertically centered

        # Horizontal stem: from right edge of box, extending rightward
        stem_x1 = x + box_width
        stem_x2 = stem_x1 + stem_length
        stem_y_bottom = y - stem_thickness / 2
        stem_y_top = y + stem_thickness / 2

        # Vertical bar: at end of stem
        bar_x_left = stem_x2
        bar_x_right = stem_x2 + bar_thickness
        bar_y_bottom = y - bar_height / 2
        bar_y_top = y + bar_height / 2

    else:  # left
        # LEFT side: box right edge ON dashed line, extends leftward
        box_x = x - box_width  # Right edge ON dashed line
        box_y = y - box_height / 2  # Vertically centered

        # Horizontal stem: from left edge of box, extending leftward
        stem_x1 = x - box_width
        stem_x2 = stem_x1 - stem_length
        stem_y_bottom = y - stem_thickness / 2
        stem_y_top = y + stem_thickness / 2

        # Vertical bar: at end of stem
        bar_x_left = stem_x2 - bar_thickness
        bar_x_right = stem_x2
        bar_y_bottom = y - bar_height / 2
        bar_y_top = y + bar_height / 2

    # Draw white rectangle box with black edge
    box = Rectangle(
        (box_x, box_y),
        box_width,
        box_height,
        facecolor=config.GUIDE_RAIL_BOX_COLOR,
        edgecolor=config.GUIDE_RAIL_BOX_EDGE_COLOR,
        linewidth=config.GUIDE_RAIL_LINE_WIDTH,
        zorder=7,
    )
    ax.add_patch(box)

    # Draw horizontal stem as a filled rectangle
    stem = Rectangle(
        (min(stem_x1, stem_x2), stem_y_bottom),
        abs(stem_x2 - stem_x1),
        stem_thickness,
        facecolor=config.GUIDE_RAIL_T_COLOR,
        edgecolor="none",
        zorder=8,
    )
    ax.add_patch(stem)

    # Draw vertical bar as a filled rectangle
    bar = Rectangle(
        (bar_x_left, bar_y_bottom),
        bar_thickness,
        bar_height,
        facecolor=config.GUIDE_RAIL_T_COLOR,
        edgecolor="none",
        zorder=8,
    )
    ax.add_patch(bar)


def draw_counterweight_bracket_top(
    ax: plt.Axes,
    shaft_x: float,
    shaft_y: float,
    shaft_width: float,
    shaft_depth: float,
    cw_bracket_depth: float,
    wall_gap: float = None,
    box_width: float = None,
    mirrored: bool = False,
) -> None:
    """
    Draw the counterweight bracket at the TOP of shaft (for MRA configuration).

    Layout (plan view, rear wall at top):
    - White CW box centered horizontally; its top edge sits wall_gap below the
      rear wall and its depth equals cw_bracket_depth.
    - Two black inverted-L wall brackets hang from the rear wall on either side
      of the box: arms run along the wall pointing outward, columns descend
      beside the box, ending flush with the box bottom.
    - The space below the box (down to the car top) is the CW gap.

    Args:
        ax: Matplotlib axes
        shaft_x: Left x coordinate of shaft interior
        shaft_y: Bottom y coordinate of shaft interior
        shaft_width: Width of shaft interior
        shaft_depth: Depth of shaft interior
        cw_bracket_depth: Depth (height in plan view) of the CW box
        wall_gap: Gap between rear wall and CW box top (excluded from bracket depth)
        mirrored: If True, draw at bottom of shaft instead of top (facing banks Bank 2)
    """
    if wall_gap is None:
        wall_gap = config.MRA_CW_WALL_GAP
    if box_width is None:
        box_width = config.MRA_CW_BOX_WIDTH
    column_width = config.MRA_CW_BRACKET_COLUMN_WIDTH
    arm_length = config.MRA_CW_BRACKET_ARM_LENGTH
    arm_thickness = config.MRA_CW_BRACKET_ARM_THICKNESS
    clearance = config.MRA_CW_BRACKET_CLEARANCE

    # Brackets span from the wall to the box bottom (flush)
    bracket_extent = wall_gap + cw_bracket_depth

    if mirrored:
        # Mirrored: rear wall at bottom of shaft, interior extends upward
        wall_inner_y = shaft_y
        direction = 1.0
    else:
        # Normal: rear wall at top of shaft, interior extends downward
        wall_inner_y = shaft_y + shaft_depth
        direction = -1.0

    center_x = shaft_x + shaft_width / 2

    # White CW box
    box_x = center_x - box_width / 2
    box_near_y = wall_inner_y + direction * wall_gap
    box_far_y = wall_inner_y + direction * bracket_extent
    ax.add_patch(Rectangle(
        (box_x, min(box_near_y, box_far_y)),
        box_width,
        cw_bracket_depth,
        facecolor=config.CW_BOX_COLOR,
        edgecolor=config.BRACKET_EDGE_COLOR,
        linewidth=config.BRACKET_EDGE_WIDTH,
        zorder=3,
    ))

    # Outline-only inverted-L wall brackets (side = -1 left, +1 right)
    arm_under_y = wall_inner_y + direction * arm_thickness
    column_end_y = wall_inner_y + direction * bracket_extent
    for side in (-1.0, 1.0):
        column_inner_x = center_x + side * (box_width / 2 + clearance)
        column_outer_x = column_inner_x + side * column_width
        arm_outer_x = column_inner_x + side * arm_length
        ax.add_patch(Polygon(
            [
                (column_inner_x, wall_inner_y),
                (arm_outer_x, wall_inner_y),
                (arm_outer_x, arm_under_y),
                (column_outer_x, arm_under_y),
                (column_outer_x, column_end_y),
                (column_inner_x, column_end_y),
            ],
            closed=True,
            facecolor="none",
            edgecolor=config.BRACKET_EDGE_COLOR,
            linewidth=config.BRACKET_EDGE_WIDTH,
            zorder=3,
        ))

    # CW guide rails on the bracket inner faces: black bar flat against the
    # bracket, stem pointing at the CW box (no base plate, parts inverted
    # relative to the car rail symbol)
    bar_thickness = config.GUIDE_RAIL_BAR_THICKNESS
    bar_height = config.GUIDE_RAIL_BAR_HEIGHT
    stem_length = config.GUIDE_RAIL_STEM_LENGTH
    stem_thickness = config.GUIDE_RAIL_STEM_THICKNESS
    rail_y = (box_near_y + box_far_y) / 2
    for side in (-1.0, 1.0):
        column_inner_x = center_x + side * (box_width / 2 + clearance)
        inner_dir = -side  # Toward the CW box
        bar_tip_x = column_inner_x + inner_dir * bar_thickness
        ax.add_patch(Rectangle(
            (min(column_inner_x, bar_tip_x), rail_y - bar_height / 2),
            bar_thickness,
            bar_height,
            facecolor=config.GUIDE_RAIL_T_COLOR,
            edgecolor="none",
            zorder=8,
        ))
        stem_tip_x = bar_tip_x + inner_dir * stem_length
        ax.add_patch(Rectangle(
            (min(bar_tip_x, stem_tip_x), rail_y - stem_thickness / 2),
            stem_length,
            stem_thickness,
            facecolor=config.GUIDE_RAIL_T_COLOR,
            edgecolor="none",
            zorder=8,
        ))


def draw_car_bracket_cw_side(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float = None,
    height: float = None,
) -> None:
    """
    Draw a small car bracket on the CW side (for MRL configuration).

    This bracket is positioned in the gap between the CW bracket and the
    left rail guide of the cabin car. It's narrower than the standard car bracket.

    Args:
        ax: Matplotlib axes
        x: Left x coordinate of the bracket (mm)
        y: Bottom y coordinate of the bracket (mm)
        width: Bracket width (mm), defaults to MRL_CW_SIDE_CAR_BRACKET_WIDTH
        height: Bracket height (mm), defaults to MRL_CW_SIDE_CAR_BRACKET_HEIGHT
    """
    if width is None:
        width = config.MRL_CW_SIDE_CAR_BRACKET_WIDTH
    if height is None:
        height = config.MRL_CW_SIDE_CAR_BRACKET_HEIGHT

    bracket = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.CAR_BRACKET_BOX_COLOR,
        edgecolor=config.BRACKET_EDGE_COLOR,
        linewidth=config.BRACKET_EDGE_WIDTH,
        zorder=3,
    )
    ax.add_patch(bracket)


def draw_car_brackets_mra(
    ax: plt.Axes,
    shaft_x: float,
    shaft_y: float,
    shaft_width: float,
    shaft_depth: float,
    car_bracket_width: float,
    car_y: float = None,
    car_depth: float = None,
    left_box_width: float = None,
    right_box_width: float = None,
) -> None:
    """
    Draw car brackets on BOTH left and right sides (for MRA configuration).

    MRA has symmetrical car brackets on both sides (no counterweight on sides).
    Brackets are positioned at the vertical center of the car (where guard rails are).

    Args:
        ax: Matplotlib axes
        shaft_x: Left x coordinate of shaft interior
        shaft_y: Bottom y coordinate of shaft interior
        shaft_width: Width of shaft interior
        shaft_depth: Depth of shaft interior
        car_bracket_width: Width of each car bracket
        car_y: Bottom y coordinate of car (if None, centers in shaft)
        car_depth: Depth of car (if None, centers in shaft)
        left_box_width: Dynamic width for left bracket box (None = use config default)
        right_box_width: Dynamic width for right bracket box (None = use config default)
    """
    # Use MRA car bracket box dimensions
    left_w = left_box_width if left_box_width is not None else config.MRA_CAR_BRACKET_BOX_WIDTH
    right_w = right_box_width if right_box_width is not None else config.MRA_CAR_BRACKET_BOX_WIDTH
    box_height = config.MRA_CAR_BRACKET_BOX_HEIGHT  # 400mm

    # Position brackets at vertical center of car (where guard rails are)
    if car_y is not None and car_depth is not None:
        car_center_y = car_y + car_depth / 2
        box_y = car_center_y - box_height / 2
    else:
        # Fallback: center in shaft
        box_y = shaft_y + (shaft_depth - box_height) / 2

    # Left car bracket box - left edge touches shaft left edge
    left_box_x = shaft_x
    ax.add_patch(Rectangle(
        (left_box_x, box_y),
        left_w,
        box_height,
        facecolor=config.CAR_BRACKET_BOX_COLOR,
        edgecolor=config.BRACKET_EDGE_COLOR,
        linewidth=config.BRACKET_EDGE_WIDTH,
        zorder=3,
    ))

    # Right car bracket box - right edge touches shaft right edge
    right_box_x = shaft_x + shaft_width - right_w
    ax.add_patch(Rectangle(
        (right_box_x, box_y),
        right_w,
        box_height,
        facecolor=config.CAR_BRACKET_BOX_COLOR,
        edgecolor=config.BRACKET_EDGE_COLOR,
        linewidth=config.BRACKET_EDGE_WIDTH,
        zorder=3,
    ))


# =============================================================================
# SECTION VIEW DRAWING FUNCTIONS
# =============================================================================


def draw_section_car(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    finished_width: float = None,
    finished_height: float = None,
    show_finished_boundary: bool = True,
) -> None:
    """
    Draw a lift car in section view (side view).

    The car is drawn as a rectangle with optional finished/unfinished boundaries.
    Unfinished boundary shown as dashed lines on top, left, and right (open at bottom).

    Args:
        ax: Matplotlib axes
        x: Left x coordinate of unfinished car (mm)
        y: Bottom y coordinate of unfinished car (mm)
        width: Unfinished car width (mm)
        height: Unfinished car height (mm)
        finished_width: Finished car width (mm), centered within unfinished
        finished_height: Finished car height (mm)
        show_finished_boundary: Whether to show the finished car boundary
    """
    # Draw unfinished car boundary as 3 dashed lines (top, left, right - open at bottom)
    unfinished_line_style = dict(
        color=config.UNFINISHED_CAR_EDGE_COLOR,
        linewidth=config.SECTION_CAR_EDGE_WIDTH,
        linestyle="--",
        zorder=6,
    )

    # Left side (from bottom to top)
    ax.plot([x, x], [y, y + height], **unfinished_line_style)
    # Top side (from left to right)
    ax.plot([x, x + width], [y + height, y + height], **unfinished_line_style)
    # Right side (from top to bottom)
    ax.plot([x + width, x + width], [y + height, y], **unfinished_line_style)

    # Draw finished car as solid rectangle if dimensions provided
    if show_finished_boundary and finished_width and finished_height:
        finished_x = x + (width - finished_width) / 2
        finished_y = y  # Same bottom as unfinished

        finished_car = Rectangle(
            (finished_x, finished_y),
            finished_width,
            finished_height,
            facecolor=config.SECTION_CAR_FILL_COLOR,
            edgecolor=config.FINISHED_CAR_EDGE_COLOR,
            linewidth=config.SECTION_CAR_EDGE_WIDTH,
            zorder=5,
        )
        ax.add_patch(finished_car)


def draw_section_guide_rails(
    ax: plt.Axes,
    shaft_x: float,
    shaft_bottom_y: float,
    shaft_height: float,
    shaft_width: float,
    rail_width: float = None,
) -> None:
    """
    Draw guide rails in section view (vertical blue rectangles on both sides).

    Args:
        ax: Matplotlib axes
        shaft_x: Left x coordinate of shaft interior (mm)
        shaft_bottom_y: Bottom y coordinate of shaft (mm)
        shaft_height: Total shaft height (mm)
        shaft_width: Shaft interior width (mm)
        rail_width: Width of each guide rail (mm)
    """
    if rail_width is None:
        rail_width = config.SECTION_GUIDE_RAIL_WIDTH

    # Left guide rail
    left_rail = Rectangle(
        (shaft_x, shaft_bottom_y),
        rail_width,
        shaft_height,
        facecolor=config.SECTION_GUIDE_RAIL_COLOR,
        edgecolor=config.SECTION_GUIDE_RAIL_EDGE_COLOR,
        linewidth=0.8,
        zorder=3,
    )
    ax.add_patch(left_rail)

    # Right guide rail
    right_rail = Rectangle(
        (shaft_x + shaft_width - rail_width, shaft_bottom_y),
        rail_width,
        shaft_height,
        facecolor=config.SECTION_GUIDE_RAIL_COLOR,
        edgecolor=config.SECTION_GUIDE_RAIL_EDGE_COLOR,
        linewidth=0.8,
        zorder=3,
    )
    ax.add_patch(right_rail)


def draw_section_machine_unit(
    ax: plt.Axes,
    center_x: float,
    y: float,
    machine_width: float = None,
    machine_height: float = None,
) -> None:
    """
    Draw machine unit in section view (MRL - at top of shaft).

    Machine is drawn as a yellow box with green frame.

    Args:
        ax: Matplotlib axes
        center_x: Horizontal center of machine (mm)
        y: Bottom y coordinate of machine (mm)
        machine_width: Machine width (mm)
        machine_height: Machine height (mm)
    """
    if machine_width is None:
        machine_width = config.SECTION_MACHINE_WIDTH
    if machine_height is None:
        machine_height = config.SECTION_MACHINE_HEIGHT

    frame_thickness = config.SECTION_MACHINE_FRAME_THICKNESS
    x = center_x - machine_width / 2

    # Draw outer green frame
    outer_frame = Rectangle(
        (x, y),
        machine_width,
        machine_height,
        facecolor=config.SECTION_MACHINE_FRAME_COLOR,
        edgecolor="#2E7D32",
        linewidth=1.0,
        zorder=4,
    )
    ax.add_patch(outer_frame)

    # Draw inner yellow machine box
    inner_x = x + frame_thickness
    inner_y = y + frame_thickness
    inner_width = machine_width - 2 * frame_thickness
    inner_height = machine_height - 2 * frame_thickness

    inner_box = Rectangle(
        (inner_x, inner_y),
        inner_width,
        inner_height,
        facecolor=config.SECTION_MACHINE_COLOR,
        edgecolor="#B8860B",
        linewidth=0.8,
        zorder=5,
    )
    ax.add_patch(inner_box)


def draw_section_pit(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    depth: float,
    show_hatching: bool = True,
) -> None:
    """
    Draw pit area in section view (at bottom of shaft).

    Args:
        ax: Matplotlib axes
        x: Left x coordinate of pit (mm)
        y: Top y coordinate of pit (bottom of shaft) (mm)
        width: Pit width (mm)
        depth: Pit depth (mm)
        show_hatching: Whether to show concrete hatching
    """
    pit_y = y - depth

    # Draw pit background
    pit = Rectangle(
        (x, pit_y),
        width,
        depth,
        facecolor=config.SECTION_PIT_FILL_COLOR,
        edgecolor=config.SECTION_PIT_EDGE_COLOR,
        linewidth=1.0,
        zorder=2,
    )
    ax.add_patch(pit)

    # Add hatching if enabled
    if show_hatching:
        add_concrete_hatch(ax, x, pit_y, width, depth)


def draw_break_lines(
    ax: plt.Axes,
    x_left: float,
    x_right: float,
    y_center: float,
    height: float = None,
    wall_thickness: float = 200,
) -> None:
    """
    Draw break lines across FULL WIDTH including walls to indicate hidden floors.

    White rectangle covers the break area, with two parallel horizontal zigzag
    lines extending well beyond the walls.

    Args:
        ax: Matplotlib axes
        x_left: Left x coordinate of shaft interior (mm)
        x_right: Right x coordinate of shaft interior (mm)
        y_center: Vertical center of break line (mm)
        height: Total height of break area (mm)
        wall_thickness: Thickness of walls to extend past (mm)
    """
    if height is None:
        height = config.BREAK_LINE_HEIGHT

    amplitude = config.BREAK_LINE_AMPLITUDE

    y_top = y_center + height / 2
    y_bottom = y_center - height / 2

    # Extend well past walls (3x wall thickness on each side)
    extension = wall_thickness * 3
    x_start = x_left - extension
    x_end = x_right + extension

    # Draw white rectangle to cover the break area (overlaps walls)
    from matplotlib.patches import Rectangle
    white_rect = Rectangle(
        (x_start, y_bottom),
        x_end - x_start,
        height,
        facecolor="white",
        edgecolor="none",
        zorder=9,
    )
    ax.add_patch(white_rect)

    # Break line with zigzag in the middle (one up peak + one down peak each, horizontally aligned)
    x_center = (x_start + x_end) / 2
    zw = 80  # Tight zigzag segment width

    line_width = config.BREAK_LINE_WIDTH * 2

    # Both lines have same pattern: straight -> up peak -> down peak -> straight
    # Peaks line up horizontally (same x positions)
    x_points = [x_start, x_center - zw*1.5, x_center - zw*0.5, x_center + zw*0.5, x_center + zw*1.5, x_end]

    # TOP break line
    ax.plot(
        x_points,
        [y_top, y_top, y_top + amplitude, y_top - amplitude, y_top, y_top],
        color=config.BREAK_LINE_COLOR,
        linewidth=line_width,
        zorder=10,
    )

    # BOTTOM break line (same pattern, peaks aligned)
    ax.plot(
        x_points,
        [y_bottom, y_bottom, y_bottom + amplitude, y_bottom - amplitude, y_bottom, y_bottom],
        color=config.BREAK_LINE_COLOR,
        linewidth=line_width,
        zorder=10,
    )


def draw_section_door_opening(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    frame_width: float = None,
) -> None:
    """
    Draw door opening in section view with structural frame.

    Args:
        ax: Matplotlib axes
        x: Left x coordinate of door opening (mm)
        y: Bottom y coordinate of door opening (mm)
        width: Door opening width (mm)
        height: Door opening height (mm)
        frame_width: Frame thickness around opening (mm)
    """
    if frame_width is None:
        frame_width = config.SECTION_DOOR_FRAME_WIDTH

    # Draw door opening (light fill)
    opening = Rectangle(
        (x, y),
        width,
        height,
        facecolor=config.SECTION_DOOR_FILL_COLOR,
        edgecolor=config.SECTION_DOOR_FRAME_COLOR,
        linewidth=1.0,
        zorder=4,
    )
    ax.add_patch(opening)


def draw_section_landing(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float = None,
    show_hatching: bool = True,
) -> None:
    """
    Draw floor slab/landing at a specific floor level.

    Args:
        ax: Matplotlib axes
        x: Left x coordinate of landing (mm)
        y: Top y coordinate of landing (floor level) (mm)
        width: Landing width (mm)
        height: Landing slab thickness (mm)
        show_hatching: Whether to show concrete hatching
    """
    if height is None:
        height = config.SECTION_LANDING_HEIGHT

    landing_y = y - height  # Slab extends downward from floor level

    landing = Rectangle(
        (x, landing_y),
        width,
        height,
        facecolor=config.SECTION_LANDING_COLOR,
        edgecolor=config.WALL_EDGE_COLOR,
        linewidth=config.WALL_EDGE_WIDTH,
        zorder=2,
    )
    ax.add_patch(landing)

    if show_hatching:
        add_concrete_hatch(ax, x, landing_y, width, height)


def draw_floor_slab_protrusion(
    ax: plt.Axes,
    shaft_left_x: float,
    shaft_right_x: float,
    y: float,
    protrusion_depth: float = 400,
    slab_thickness: float = None,
    wall_thickness: float = 200,
    show_hatching: bool = True,
) -> None:
    """
    Draw floor slab protrusions on BOTH sides of shaft.

    These represent the landing slabs where people stand while waiting for the lift.
    Protrusions extend outward from the RCC shaft walls.

    Args:
        ax: Matplotlib axes
        shaft_left_x: Left inner edge of shaft (x = wall_thickness)
        shaft_right_x: Right inner edge of shaft
        y: Floor level (top of slab)
        protrusion_depth: How far slab extends outward (mm)
        slab_thickness: Slab thickness (mm)
        wall_thickness: Wall thickness for positioning (mm)
        show_hatching: Whether to show concrete hatching
    """
    if slab_thickness is None:
        slab_thickness = config.SECTION_LANDING_HEIGHT  # 150mm

    slab_y = y - slab_thickness  # Slab extends downward from floor level

    # Left side protrusion (extends left from left wall)
    left_slab_x = shaft_left_x - wall_thickness - protrusion_depth
    draw_wall_section(
        ax, left_slab_x, slab_y, protrusion_depth, slab_thickness, show_hatching
    )

    # Right side protrusion (extends right from right wall)
    right_slab_x = shaft_right_x + wall_thickness
    draw_wall_section(
        ax, right_slab_x, slab_y, protrusion_depth, slab_thickness, show_hatching
    )


def draw_machine_image(
    ax: plt.Axes,
    x_center: float,
    y_bottom: float,
    width: float,
    height: float,
    machine_type: str = "mrl",
    assets_path: str = None,
) -> bool:
    """
    Draw machine image at the specified position, preserving aspect ratio.

    Supports both MRL (Machine Room Less) and MRA (Machine Room Above) machine images.
    The image is scaled to fit within the provided width/height bounds while
    maintaining its original aspect ratio.

    Args:
        ax: Matplotlib axes
        x_center: Center x position for the machine (mm)
        y_bottom: Bottom y position for the machine (mm)
        width: Maximum width for the image (mm)
        height: Maximum height for the image (mm)
        machine_type: "mrl" or "mra" - determines which image file to load
        assets_path: Path to assets directory (defaults to module's assets folder)

    Returns:
        True if image was drawn, False if image file not found
    """
    from pathlib import Path
    import matplotlib.image as mpimg

    # Default assets path
    if assets_path is None:
        assets_path = Path(__file__).parent / "assets"
    else:
        assets_path = Path(assets_path)

    # Look for machine image (try multiple formats)
    # File naming: mrl_machine.png or mra_machine.png
    image_file = None
    for ext in [".png", ".jpg", ".jpeg"]:
        candidate = assets_path / f"{machine_type}_machine{ext}"
        if candidate.exists():
            image_file = candidate
            break

    if image_file is None:
        return False

    # Load the image
    img = mpimg.imread(str(image_file))

    # Get original image dimensions (height, width for numpy array)
    img_height, img_width = img.shape[:2]
    img_aspect_ratio = img_width / img_height  # width / height

    # Calculate scaled dimensions to fit within bounds while preserving aspect ratio
    target_aspect_ratio = width / height

    if img_aspect_ratio > target_aspect_ratio:
        # Image is wider than target - constrain by width
        scaled_width = width
        scaled_height = width / img_aspect_ratio
    else:
        # Image is taller than target - constrain by height
        scaled_height = height
        scaled_width = height * img_aspect_ratio

    # Calculate extent (position in data coordinates), centered
    x_left = x_center - scaled_width / 2
    x_right = x_center + scaled_width / 2
    y_top = y_bottom + scaled_height

    # Draw the image with preserved aspect ratio
    ax.imshow(
        img,
        extent=[x_left, x_right, y_bottom, y_top],
        aspect='auto',
        zorder=5,  # Above background, below dimensions
    )

    return True


# Alias for backward compatibility
def draw_mrl_machine_image(
    ax: plt.Axes,
    x_center: float,
    y_bottom: float,
    width: float,
    height: float,
    assets_path: str = None,
) -> bool:
    """Backward compatible wrapper for draw_machine_image with MRL type."""
    return draw_machine_image(
        ax, x_center, y_bottom, width, height,
        machine_type="mrl", assets_path=assets_path
    )
