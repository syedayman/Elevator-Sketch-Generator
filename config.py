"""
Configuration defaults and styling constants for lift shaft sketch generator.
"""

# =============================================================================
# Default Shaft Parameters (in mm)
# =============================================================================

DEFAULT_SHAFT_WIDTH = 2950  # Internal width of shaft
DEFAULT_SHAFT_DEPTH = 2300  # Internal depth of shaft
DEFAULT_WALL_THICKNESS = 200  # RCC wall thickness
DEFAULT_DOOR_WIDTH = 1100  # Lift door opening width
DEFAULT_DOOR_HEIGHT = 2100  # Lift door opening height (for reference)
DEFAULT_STRUCTURAL_OPENING_WIDTH = 1300  # Front wall structural opening
DEFAULT_STRUCTURAL_OPENING_HEIGHT = 2200  # Front wall structural opening (for reference)
DEFAULT_SHARED_WALL_THICKNESS = 200  # Dividing wall between lifts

# =============================================================================
# Fire Lift Parameters (in mm)
# =============================================================================

FIRE_LIFT_MIN_SHAFT_WIDTH = 2700  # Minimum shaft width for fire lifts
FIRE_LIFT_DOOR_WIDTH = 1200  # Fire lift door width

# =============================================================================
# Default Car and Bracket Parameters (in mm)
# =============================================================================

DEFAULT_FINISHED_CAR_WIDTH = 1900  # Interior finished car width
DEFAULT_FINISHED_CAR_DEPTH = 1600  # Interior finished car depth
DEFAULT_CAR_WALL_THICKNESS = 25  # Thickness between finished/unfinished car
DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH = 625  # Left bracket width

# Counterweight box visual dimensions (the gray box inside the bracket area)
CW_BOX_WIDTH = 450    # Visual outer box width (slimmer bracket)
CW_BOX_HEIGHT = 1000  # Visual outer box height

# Counterweight frame styling (double-outline frame)
CW_FRAME_THICKNESS = 50       # Frame border thickness (mm)
CW_FRAME_COLOR = "#4CAF50"    # Green fill for frame
CW_BOX_COLOR = "#FFD700"      # Yellow fill for inner CW box

# Car bracket box visual dimensions (blue box opposite side of counterweight)
CAR_BRACKET_BOX_WIDTH = 275     # Visual box width (mm)
CAR_BRACKET_BOX_HEIGHT = 450    # Visual box height (mm)
CAR_BRACKET_BOX_COLOR = "#3B82F6"  # Blue fill color

DEFAULT_CAR_BRACKET_WIDTH = 375  # Right bracket width
DEFAULT_LIFT_CAPACITY = 1350  # Default capacity in KG

# =============================================================================
# Separator Parameters (in mm)
# =============================================================================

DEFAULT_STEEL_BEAM_WIDTH = 150  # Steel separator beam width
DEFAULT_RCC_SEPARATOR_WIDTH = 200  # RCC wall separator width (fire lift)

# =============================================================================
# Display Defaults
# =============================================================================

DEFAULT_DPI = 150
DEFAULT_FIGURE_WIDTH = 10  # inches
DEFAULT_FIGURE_HEIGHT = 10  # inches
DEFAULT_TITLE = "LIFT SHAFT PLAN"

# =============================================================================
# Drawing Style Constants
# =============================================================================

# Colors
WALL_FILL_COLOR = "#FFFFFF"  # White for wall fill (concrete background)
WALL_EDGE_COLOR = "#000000"  # Black for wall outline
WALL_HATCH_COLOR = "#000000"  # Black for concrete hatch (dots and triangles)
OPENING_FILL_COLOR = "#FFFFFF"  # White for openings
SHAFT_INTERIOR_COLOR = "#F5F5F5"  # Very light gray for shaft interior
DIMENSION_COLOR = "#000000"  # Black for dimensions
CENTERLINE_COLOR = "#FF0000"  # Red for centerlines
TITLE_COLOR = "#000000"  # Black for title text

# Lift car interior colors
UNFINISHED_CAR_COLOR = "#E8E8E8"  # Light gray for unfinished car boundary
FINISHED_CAR_COLOR = "#FFFFFF"  # White for finished car interior
FINISHED_CAR_EDGE_COLOR = "#404040"  # Dark gray for finished car outline
UNFINISHED_CAR_EDGE_COLOR = "#606060"  # Medium gray for unfinished car outline

# Bracket colors
COUNTERWEIGHT_BRACKET_COLOR = "#B0B0B0"  # Gray for counterweight bracket
CAR_BRACKET_COLOR = "#C8C8C8"  # Lighter gray for car bracket
BRACKET_EDGE_COLOR = "#505050"  # Dark gray for bracket outline

# Steel beam colors
STEEL_BEAM_COLOR = "#FFFFFF"  # White for steel beam
STEEL_BEAM_EDGE_COLOR = "#000000"  # Black outline

# COP and accessibility colors
COP_COLOR = "#808080"  # Gray for COP markers
ACCESSIBILITY_COLOR = "#0066CC"  # Blue for accessibility symbol
CAPACITY_TEXT_COLOR = "#333333"  # Dark gray for capacity label

# Line widths
WALL_EDGE_WIDTH = 1.5
DIMENSION_LINE_WIDTH = 0.5
CENTERLINE_WIDTH = 0.5
OPENING_EDGE_WIDTH = 1.0

# Dimension styling
DIMENSION_ARROW_SIZE = 50  # Arrow head size in mm
DIMENSION_OFFSET = 150  # Offset from object in mm
DIMENSION_TEXT_SIZE = 6  # Font size for dimension text (smaller to avoid overlap)
DIMENSION_EXTENSION = 50  # Extension line beyond dimension

# Title styling
TITLE_FONT_SIZE = 14
SUBTITLE_FONT_SIZE = 10

# Hatching
HATCH_DENSITY = 0.0005  # Dots per square mm (sparse for cleaner look)
HATCH_DOT_SIZE = 0.25  # Size of hatch dots

# Centerline
CENTERLINE_DASH_PATTERN = (5, 3)  # Dash pattern (on, off)

# Lift car styling
CAR_EDGE_WIDTH = 1.0  # Line width for car boundaries
BRACKET_EDGE_WIDTH = 0.8  # Line width for bracket outlines
STEEL_BEAM_EDGE_WIDTH = 1.0  # Line width for steel beam outline
DOOR_PANEL_LINE_WIDTH = 0.5  # Line width for door panel divisions

# Text sizes
CAPACITY_TEXT_SIZE = 10  # Font size for capacity label
COP_TEXT_SIZE = 7  # Font size for C.O.P markers
ACCESSIBILITY_SYMBOL_SIZE = 8  # Font size for accessibility symbol
SEPARATOR_LABEL_SIZE = 5  # Font size for separator labels

# COP marker dimensions
COP_MARKER_WIDTH = 80  # Width of C.O.P marker (mm)
COP_MARKER_HEIGHT = 120  # Height of C.O.P marker (mm)

# Door panel settings
DEFAULT_DOOR_PANELS = 2  # Number of door panels (2 or 4)

# =============================================================================
# Lift Door Parameters (landing + car doors)
# =============================================================================

DEFAULT_LIFT_DOOR_THICKNESS = 150   # Thickness of each door (mm)
DEFAULT_DOOR_GAP = 30               # Running clearance between landing and car door (mm)
DEFAULT_DOOR_EXTENSION = 100        # Extension beyond door width on each side (mm)

# Rear clearance (distance from back of car to rear wall)
DEFAULT_REAR_CLEARANCE = 345        # Default rear clearance (mm)
MIN_REAR_CLEARANCE = 200            # Minimum allowed rear clearance (mm)
# Total door width = 2 × door_width + 2 × DEFAULT_DOOR_EXTENSION

# Door styling
LIFT_DOOR_FILL_COLOR = "#FFFFFF"    # Light gray fill
LIFT_DOOR_EDGE_COLOR = "#000000"    # Dark gray edge
LIFT_DOOR_EDGE_WIDTH = 0.8
DOOR_EXTENSION_COLOR = "#000000"    # Color for extension lines
DOOR_EXTENSION_LINE_WIDTH = 0.8

# Inner door panel styling
LIFT_DOOR_FRAME_MARGIN = 37.5       # Distance from top/bottom edges to frame lines (mm)
LIFT_DOOR_PANEL_HEIGHT = 75         # Height of inner door panels (mm)
LIFT_DOOR_PANEL_EDGE_WIDTH = 1.5    # Thicker border for inner panels
LIFT_DOOR_FRAME_LINE_WIDTH = 0.8    # Width for horizontal frame lines

# Door jamb styling
DOOR_JAMB_WIDTH = 75                # Horizontal dimension (mm)
DOOR_JAMB_HEIGHT = 50               # Vertical dimension (mm)

# =============================================================================
# Guide Rail Symbol Parameters (in mm)
# =============================================================================

# Guide rail box dimensions (vertical rectangle)
GUIDE_RAIL_BOX_WIDTH = 30       # Width of white rectangle (horizontal dimension)
GUIDE_RAIL_BOX_HEIGHT = 300     # Height of white rectangle (vertical dimension)

# Guide rail T-shape dimensions
GUIDE_RAIL_STEM_LENGTH = 38     # Length of horizontal stem extending from box
GUIDE_RAIL_STEM_THICKNESS = 25  # Thickness of horizontal stem
GUIDE_RAIL_BAR_HEIGHT = 75      # Height of vertical bar at end of stem
GUIDE_RAIL_BAR_THICKNESS = 25   # Thickness of vertical bar

# Guide rail colors
GUIDE_RAIL_BOX_COLOR = "#FFFFFF"       # White fill for rectangle
GUIDE_RAIL_BOX_EDGE_COLOR = "#000000"  # Black edge for rectangle
GUIDE_RAIL_T_COLOR = "#000000"         # Black fill for T-shape (stem + bar)
GUIDE_RAIL_LINE_WIDTH = 0.8            # Edge line width

# =============================================================================
# MRA (Machine Room Above) Specific Parameters (in mm)
# =============================================================================

# MRA Shaft Layout (space allocation for shaft depth calculation)
MRA_CAR_BRACKET_WIDTH = 325       # Car bracket width (left and right sides)
MRA_CW_BRACKET_DEPTH = 400        # CW bracket depth (at top of shaft)
MRA_CW_GAP = 100                  # Gap between car top and CW bracket bottom

# MRA Green U-Frame (counterweight bracket visual)
MRA_CW_FRAME_WIDTH = 1100         # Green frame width
MRA_CW_FRAME_DEPTH = 400          # Green frame depth (matches MRA_CW_BRACKET_DEPTH)
MRA_CW_FRAME_THICKNESS = 40       # Green frame bar thickness

# MRA Yellow Box (counterweight inside green frame)
MRA_CW_BOX_WIDTH = 900            # Yellow box width
MRA_CW_BOX_DEPTH = 250            # Yellow box depth

# MRA Blue Box (car brackets on left/right sides)
MRA_CAR_BRACKET_BOX_WIDTH = 200   # Blue box width
MRA_CAR_BRACKET_BOX_HEIGHT = 400  # Blue box height

# =============================================================================
# Dual Bank (Facing) Configuration
# =============================================================================

DEFAULT_LOBBY_WIDTH = 4000  # mm - space between facing banks

# =============================================================================
# MRL CW-side Car Bracket (smaller bracket in gap between CW bracket and rail guide)
# =============================================================================

# This bracket fits in the narrow gap between the CW box and the left rail guide.
# Gap calculation: rail_left_edge - cw_box_right_edge = 532mm - 400mm = 132mm
MRL_CW_SIDE_CAR_BRACKET_WIDTH = 130   # Slightly less than 132mm gap
MRL_CW_SIDE_CAR_BRACKET_HEIGHT = 450  # Same height as existing car bracket

# =============================================================================
# Section View Parameters (in mm)
# =============================================================================

# Vertical dimensions
DEFAULT_PIT_DEPTH = 200              # Pit depth below lowest landing
DEFAULT_OVERHEAD_CLEARANCE = 4200    # Overhead clearance above highest landing
DEFAULT_TRAVEL_HEIGHT = 30000        # Travel height (total vertical travel)
DEFAULT_FLOOR_HEIGHT = 3200          # Typical floor-to-floor height
DEFAULT_CAR_INTERIOR_HEIGHT = 2400   # Interior car height

# Guide rails in section view (vertical blue rectangles)
SECTION_GUIDE_RAIL_WIDTH = 100       # Width of guide rail in section
SECTION_GUIDE_RAIL_COLOR = "#3B82F6"  # Blue
SECTION_GUIDE_RAIL_EDGE_COLOR = "#1E40AF"  # Darker blue edge

# Machine unit in section view (MRL - at top of shaft)
SECTION_MACHINE_WIDTH = 800          # Machine unit width
SECTION_MACHINE_HEIGHT = 400         # Machine unit height
SECTION_MACHINE_COLOR = "#FFD700"    # Yellow fill
SECTION_MACHINE_FRAME_COLOR = "#4CAF50"  # Green frame
SECTION_MACHINE_FRAME_THICKNESS = 30  # Frame border thickness

# Break lines (zigzag pattern to hide repetitive floors)
BREAK_LINE_HEIGHT = 200              # Height of break line area
BREAK_LINE_COLOR = "#000000"         # Black
BREAK_LINE_WIDTH = 1.0               # Line width
BREAK_LINE_AMPLITUDE = 50            # Zigzag amplitude (horizontal extent)
BREAK_LINE_SEGMENTS = 6              # Number of zigzag segments

# Section view car (side view of lift car)
SECTION_CAR_FILL_COLOR = "#FFFFFF"   # White fill
SECTION_CAR_EDGE_COLOR = "#000000"   # Black edge
SECTION_CAR_EDGE_WIDTH = 1.0

# Door opening in section view
SECTION_DOOR_FILL_COLOR = "#FFFFFF"  # Light gray for door opening
SECTION_DOOR_FRAME_COLOR = "#000000"  # Black frame
SECTION_DOOR_FRAME_WIDTH = 100        # Frame thickness around door

# Landing/floor slab in section view
SECTION_LANDING_HEIGHT = 150         # Landing slab thickness
SECTION_LANDING_COLOR = "#C0C0C0"    # Gray

# Pit area styling
SECTION_PIT_FILL_COLOR = "#FFFFFF"   # White (uniform with shaft interior)
SECTION_PIT_EDGE_COLOR = "#000000"   # Black edge

# Section figure sizing
SECTION_FIGURE_WIDTH = 8             # Figure width in inches
SECTION_FIGURE_HEIGHT = 14           # Figure height in inches (taller for section)

# MRA (Machine Room Above) section specific
DEFAULT_MACHINE_ROOM_HEIGHT = 3000   # MRA machine room height (mm)
