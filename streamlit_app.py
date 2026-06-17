"""
Streamlit web app for generating lift shaft plan sketches.
"""

import base64
import os
from pathlib import Path

import streamlit as st
from shaft_sketch import LiftShaftSketch, LiftConfig, FIRE_LIFT_CABIN_SIZES
from section_sketch import LiftSectionSketch, SectionConfig
import config

# Fire lift cabin size options for dropdown
FIRE_CABIN_OPTIONS = {
    f"{w} x {d} mm": (w, d) for w, d in FIRE_LIFT_CABIN_SIZES
}

# Brand assets (sidebar logo + display font), inlined as base64 data URIs.
BRAND_IMAGE_PATH = Path(__file__).with_name("drawing-debbie.png")
DISPLAY_FONT_PATH = (
    Path(__file__).resolve().parent / "assets" / "fonts" / "ClashGrotesk-Variable.woff2"
)

def _gate_password() -> str | None:
    """Single shared gate password. Read from Streamlit secrets
    (.streamlit/secrets.toml, gitignored) or the GATE_PASSWORD env var — never
    hardcoded in source. Returns None if unset (gate then stays locked)."""
    try:
        if "GATE_PASSWORD" in st.secrets:
            return st.secrets["GATE_PASSWORD"]
    except Exception:
        pass
    return os.environ.get("GATE_PASSWORD")


def _file_data_uri(path: Path, mime_type: str) -> str | None:
    """Read a file and return a base64 data URI, or None if it doesn't exist."""
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def inject_brand_theme() -> None:
    """Inject the KARR AI dark/indigo reskin — fonts + global CSS.

    Mirrors the Code Charlie Streamlit app: dark slate base, indigo accents,
    glassmorph sidebar, Inter body + Clash Grotesk display font.
    """
    font_data_uri = _file_data_uri(DISPLAY_FONT_PATH, "font/woff2")
    if font_data_uri:
        st.html(
            f"""
<style>
@font-face {{
    font-family: 'Clash Grotesk';
    src: url('{font_data_uri}') format('woff2');
    font-weight: 200 700;
    font-display: swap;
}}
</style>
"""
        )

    st.html(
        """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
/* =========================================================================
   KARR AI "Drawing Debbie" reskin — dark slate base, indigo accents,
   glassmorph sidebar. Matches the Code Charlie Streamlit theme.
   ========================================================================= */

/* ---- Global base ---- */
html, body, .stApp, .block-container,
section[data-testid="stSidebar"] {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}

/* Always reserve the vertical scrollbar track so the viewport width never
   changes when content height grows/shrinks (expander open, Generate, etc.).
   Without this the scrollbar appears/disappears, shifting the config/preview
   split sideways. */
html {
    overflow-y: scroll;
    scrollbar-gutter: stable;
}
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    scrollbar-gutter: stable;
}
/* Lock the config/preview split so the two columns can't reflow horizontally. */
[data-testid="stMain"] [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
}

.stApp {
    background:
        radial-gradient(ellipse at top, rgba(99, 102, 241, 0.08), transparent 50%),
        radial-gradient(ellipse at bottom right, rgba(168, 85, 247, 0.06), transparent 60%),
        #020617 !important;
    color: #e2e8f0 !important;
}

/* Hide default Streamlit chrome, keep header alive for sidebar reopen. */
#MainMenu,
footer {
    visibility: hidden;
    height: 0;
}
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 2.75rem !important;
}
header[data-testid="stHeader"] [data-testid="stDecoration"],
header[data-testid="stHeader"] [data-testid="stStatusWidget"] {
    display: none !important;
}
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
[class*="_profileContainer_"],
[class*="_viewerBadge_"],
a[href*="streamlit.io/cloud"] {
    display: none !important;
}
header[data-testid="stHeader"] button {
    background: rgba(99, 102, 241, 0.2) !important;
    border: 1px solid rgba(129, 140, 248, 0.35) !important;
    border-radius: 0.7rem !important;
    color: #e2e8f0 !important;
}
header[data-testid="stHeader"] svg {
    color: #e2e8f0 !important;
    fill: currentColor !important;
}

.block-container {
    padding-top: 1.5rem !important;
}

/* ---- Headings + captions ---- */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    color: #f1f5f9 !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
}
.stApp [data-testid="stCaptionContainer"],
.stApp .stCaption,
.stApp small {
    color: #94a3b8 !important;
}
.stApp p, .stApp li, .stApp span, .stApp label, .stApp div {
    color: #e2e8f0;
}

/* Main-area section headers (st.header / st.subheader) — keep below the
   1.875rem brand title so the page title stays the largest element. */
.stApp [data-testid="stMain"] h2 {
    font-size: 1.25rem !important;
}
.stApp [data-testid="stMain"] h3 {
    font-size: 1.05rem !important;
}

.main-brand-title {
    color: #f1f5f9 !important;
    font-family: 'Clash Grotesk', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
    font-size: 1.875rem !important;
    font-weight: 600 !important;
    letter-spacing: 0 !important;
    line-height: 1.2 !important;
    margin: 0 0 1rem !important;
}

/* ---- Sidebar — glassmorph dark ---- */
section[data-testid="stSidebar"] {
    background: rgba(15, 23, 42, 0.55) !important;
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}
section[data-testid="stSidebar"] > div {
    background: transparent !important;
}
.sidebar-brand-image {
    display: block !important;
    width: 220px !important;
    max-width: 100% !important;
    height: auto !important;
    margin: 0 auto 0.5rem !important;
    border-radius: 0.5rem !important;
    image-rendering: -webkit-optimize-contrast;
    image-rendering: auto;
}
section[data-testid="stSidebar"] [data-testid="stHtml"]:has(> .sidebar-brand-image) {
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
}
.sidebar-brand-title {
    color: #f1f5f9 !important;
    font-family: 'Clash Grotesk', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
    font-size: 1.7rem !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;
    margin: 0.4rem 0 0.2rem !important;
    text-align: left !important;
}
.sidebar-brand-subtitle {
    color: #ffffff !important;
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
    margin: 0 0 0.95rem !important;
    text-align: left !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #f1f5f9 !important;
}

/* ---- Sidebar control text — bump to Code Charlie chat size (~1rem) ---- */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
section[data-testid="stSidebar"] [data-testid="stRadio"] label p,
section[data-testid="stSidebar"] [data-testid="stRadio"] label,
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label p,
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
section[data-testid="stSidebar"] [data-baseweb="select"] {
    font-size: 1rem !important;
    line-height: 1.5 !important;
}
section[data-testid="stSidebar"] h3 {
    font-size: 1.15rem !important;
}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    font-size: 0.9rem !important;
}

section[data-testid="stSidebar"] hr,
section[data-testid="stSidebar"] [data-testid="stDivider"] {
    border-color: rgba(255, 255, 255, 0.08) !important;
    background: rgba(255, 255, 255, 0.08) !important;
}

/* ---- Dividers (main area) ---- */
.stApp hr,
.stApp [data-testid="stDivider"] {
    border-color: rgba(255, 255, 255, 0.08) !important;
    background: rgba(255, 255, 255, 0.08) !important;
}

/* ---- Primary button (Generate / Download) ---- */
.stApp .stButton button[kind="primary"],
.stApp .stDownloadButton button {
    background: rgba(99, 102, 241, 0.2) !important;
    border: 1px solid rgba(129, 140, 248, 0.35) !important;
    color: #e0e7ff !important;
    font-weight: 500 !important;
    border-radius: 0.75rem !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}
.stApp .stButton button[kind="primary"]:hover,
.stApp .stDownloadButton button:hover {
    background: rgba(99, 102, 241, 0.3) !important;
    border-color: rgba(129, 140, 248, 0.5) !important;
}

/* ---- Secondary buttons (Copy from Lift 1, etc.) ---- */
.stApp .stButton button[kind="secondary"] {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #cbd5e1 !important;
    border-radius: 0.6rem !important;
    box-shadow: none !important;
}
.stApp .stButton button[kind="secondary"]:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.18) !important;
    border-color: rgba(129, 140, 248, 0.35) !important;
    color: #e0e7ff !important;
}
.stApp .stButton button:disabled {
    opacity: 0.45 !important;
}

/* ---- Inputs: number / text / select ---- */
.stApp [data-testid="stNumberInput"] input,
.stApp [data-testid="stTextInput"] input,
.stApp [data-baseweb="select"] > div {
    background: rgba(2, 6, 23, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #f1f5f9 !important;
    border-radius: 0.5rem !important;
}
.stApp [data-testid="stNumberInput"] input:focus,
.stApp [data-testid="stTextInput"] input:focus {
    border-color: rgba(129, 140, 248, 0.5) !important;
    box-shadow: none !important;
}
.stApp [data-testid="stNumberInput"] input::placeholder,
.stApp [data-testid="stTextInput"] input::placeholder {
    color: #64748b !important;
}
/* Number input +/- stepper buttons */
.stApp [data-testid="stNumberInput"] button {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #c7d2fe !important;
}
.stApp [data-testid="stNumberInput"] button:hover {
    background: rgba(99, 102, 241, 0.25) !important;
}
/* Select dropdown popover */
.stApp [data-baseweb="popover"] [role="listbox"],
.stApp [data-baseweb="menu"] {
    background: rgba(15, 23, 42, 0.98) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}
.stApp [data-baseweb="select"] svg {
    fill: #c7d2fe !important;
}

/* ---- Radio + checkbox ---- */
.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stRadio"] label,
.stApp [data-testid="stCheckbox"] label {
    color: #cbd5e1 !important;
}
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] [data-testid="stCheckboxChecked"],
.stApp [data-baseweb="checkbox"] span[aria-checked="true"] {
    background-color: #818cf8 !important;
    border-color: #818cf8 !important;
}
.stApp [data-testid="stRadio"] [aria-checked="true"] {
    border-color: #818cf8 !important;
}

/* ---- Expanders (per-lift config) ---- */
.stApp [data-testid="stExpander"] {
    background: rgba(99, 102, 241, 0.1) !important;
    border: 1px solid rgba(129, 140, 248, 0.3) !important;
    border-radius: 0.75rem !important;
    margin-top: 0.4rem;
}
/* Per-lift expander header — indigo tint matching the Generate/Download buttons. */
.stApp [data-testid="stExpander"] summary {
    background: rgba(99, 102, 241, 0.2) !important;
    border: 1px solid rgba(129, 140, 248, 0.35) !important;
    border-radius: 0.6rem !important;
    color: #e0e7ff !important;
    font-weight: 600 !important;
    padding: 0.6rem 0.9rem !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}
.stApp [data-testid="stExpander"] summary:hover {
    background: rgba(99, 102, 241, 0.3) !important;
    border-color: rgba(129, 140, 248, 0.5) !important;
    color: #ffffff !important;
}
.stApp [data-testid="stExpander"] summary p,
.stApp [data-testid="stExpander"] summary span {
    color: inherit !important;
}
.stApp [data-testid="stExpander"] [data-testid="stExpanderToggleIcon"],
.stApp [data-testid="stExpander"] summary svg {
    color: #e0e7ff !important;
    fill: currentColor !important;
}

/* ---- Alerts (info / error / success / warning) ---- */
.stApp [data-testid="stAlert"] {
    border-radius: 0.6rem !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    backdrop-filter: blur(8px);
}
/* Dims-summary info box sits inside the indigo lift card — drop its border +
   background so it reads as plain text, not a box-in-a-box. */
.stApp [data-testid="stExpander"] [data-testid="stAlert"] {
    border: none !important;
    background: transparent !important;
    backdrop-filter: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}
.stApp [data-testid="stAlertContentInfo"] {
    background: rgba(99, 102, 241, 0.12) !important;
    color: #e0e7ff !important;
}
.stApp [data-testid="stExpander"] [data-testid="stAlertContentInfo"] {
    background: transparent !important;
}
.stApp [data-testid="stAlertContentError"] {
    background: rgba(239, 68, 68, 0.12) !important;
    color: #fecaca !important;
}
.stApp [data-testid="stAlertContentSuccess"] {
    background: rgba(34, 197, 94, 0.12) !important;
    color: #bbf7d0 !important;
}
.stApp [data-testid="stAlertContentWarning"] {
    background: rgba(234, 179, 8, 0.12) !important;
    color: #fde68a !important;
}

/* ---- Generated sketch image — soft glow + framed ---- */
.stApp [data-testid="stImage"] img {
    border-radius: 0;
    filter: drop-shadow(0 0 40px rgba(56, 189, 248, 0.12));
}

/* ---- Markdown emphasis ---- */
.stApp strong { color: #f8fafc !important; }
.stApp em { color: #e2e8f0 !important; }

/* ---- Spinner ---- */
.stApp .stSpinner > div {
    border-top-color: #818cf8 !important;
}

/* ---- Scrollbars ---- */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.15); }
</style>
""",
    )


# =============================================================================
# Geometry constants — sourced from config.py so the form math matches the
# drawing engine exactly. These mirror apps/web/lib/sketches/sketch-utils.ts in
# the KARR AI web app (this form is a 1:1 port of that React form's behavior).
# =============================================================================

CAR_WALL_THICKNESS = config.DEFAULT_CAR_WALL_THICKNESS            # 25
DOOR_GAP = config.DEFAULT_DOOR_GAP                                # 30
REAR_CLEARANCE = config.DEFAULT_REAR_CLEARANCE                    # 200
DEFAULT_DOOR_EXTENSION = config.DEFAULT_DOOR_EXTENSION            # 100
FIRE_DOOR_WIDTH = config.FIRE_LIFT_DOOR_WIDTH                     # 1200
FIRE_MIN_SHAFT_WIDTH = config.FIRE_LIFT_MIN_SHAFT_WIDTH           # 2700
FIRE_MIN_SHAFT_WIDTH_TELESCOPIC = config.FIRE_LIFT_MIN_SHAFT_WIDTH_TELESCOPIC  # 2550
TELESCOPIC_LEFT_EXT_EXTRA = config.TELESCOPIC_LEFT_EXTENSION_EXTRA   # 100
TELESCOPIC_RIGHT_EXT = config.TELESCOPIC_RIGHT_EXTENSION             # 200
# Bracket form fields hold PURE bracket widths; rails are separate inputs.
# Zone width (what the sketch arrows show) = pure bracket + rail.
RAIL_WIDTH_DEFAULT = config.DEFAULT_RAIL_WIDTH                                        # 100
CW_BOX_WIDTH_DEFAULT = config.CW_BOX_WIDTH                                            # 450
CW_BOX_DEPTH_DEFAULT = config.CW_BOX_HEIGHT                                           # 1000
MRA_CW_BOX_WIDTH_DEFAULT = config.MRA_CW_BOX_WIDTH                                    # 1100
MRL_CW_BRACKET_MIN = config.DEFAULT_COUNTERWEIGHT_BRACKET_WIDTH - RAIL_WIDTH_DEFAULT  # 525
MRL_CAR_BRACKET_MIN = config.DEFAULT_CAR_BRACKET_WIDTH - RAIL_WIDTH_DEFAULT           # 275
MRA_CAR_BRACKET_MIN = config.MRA_CAR_BRACKET_WIDTH - RAIL_WIDTH_DEFAULT               # 225
MRA_CW_BRACKET_DEPTH_MIN = config.MRA_CW_BRACKET_DEPTH               # 400
MRA_CW_GAP_MIN = config.MRA_CW_GAP                                   # 100
MRA_CW_WALL_GAP_MIN = config.MRA_CW_WALL_GAP                         # 100
PANEL_THICKNESS_DEFAULT = config.DEFAULT_LIFT_DOOR_THICKNESS         # 150


# =============================================================================
# Default factories + validation — direct port of sketch-utils.ts
# =============================================================================

def make_default_lift(lift_type: str = "passenger", machine_type: str = "mrl") -> dict:
    """Default per-lift form data. Port of makeDefaultLift()."""
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
    # switching to centre recomputes it — see _cb_door_opening_type)
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
        "door_offset_mm": 0,
        "door_offset_direction": "right",
        "swap_brackets": False,
    }


def make_default_section() -> dict:
    """Default section-view config. Port of makeDefaultSection()."""
    return {
        "shaft_width": 2950,   # horizontal dim in section (= shaft depth)
        "wall_thickness": 200,
        "pit_slab": 200,
        "pit_depth": 1200,
        "travel_height": 30000,
        "overhead_clearance": 4200,
        "door_height": 2100,
        "structural_opening_height": 2200,
        "machine_room_height": 3000,
    }


def lift_rails(lift: dict) -> tuple:
    """Per-lift rail widths with defaults (left, right)."""
    rl = lift.get("rail_width_left")
    rr = lift.get("rail_width_right")
    return (rl if rl is not None else RAIL_WIDTH_DEFAULT,
            rr if rr is not None else RAIL_WIDTH_DEFAULT)


def lift_door_gap(lift: dict) -> float:
    """Per-lift running clearance with default."""
    g = lift.get("door_gap")
    return g if g is not None else DOOR_GAP


def compute_min_shaft_width(lift: dict, machine_type: str) -> int:
    """Port of computeMinShaftWidth(). Zone = pure bracket + rail."""
    uc_w = lift["width"] + 2 * CAR_WALL_THICKNESS
    rail_l, rail_r = lift_rails(lift)
    if machine_type == "mra" and not lift.get("double_entrance") and lift["type"] != "fire":
        min_w = (MRA_CAR_BRACKET_MIN + rail_l) + uc_w + (MRA_CAR_BRACKET_MIN + rail_r)
    else:
        # MRL, or MRA with MRL-style side brackets (double entrance / fire)
        min_w = (MRL_CW_BRACKET_MIN + rail_l) + uc_w + (MRL_CAR_BRACKET_MIN + rail_r)
    if lift["type"] == "fire":
        fire_min = (FIRE_MIN_SHAFT_WIDTH_TELESCOPIC
                    if lift.get("door_opening_type") == "telescopic"
                    else FIRE_MIN_SHAFT_WIDTH)
        min_w = max(min_w, fire_min)
    return int(min_w)


# Min/max bounds for the bounded numeric widgets. Used to clamp values that
# callbacks write programmatically (e.g. auto-adjusted door panel length) so
# Streamlit never sees an out-of-range session_state value (which would raise).
FIELD_BOUNDS = {
    "door_height": (1500, 3500),
    # door_panel_length is intentionally NOT clamped here: the web lets door
    # width auto-grow it past 6000 (only a user edit clamps it). See
    # _cb_panel_len, which clamps user input but leaves auto-grow free.
    "door_panel_thickness": (50, 300),
    "structural_opening_width": (800, 3000),
    "structural_opening_height": (1500, 4000),
    "telescopic_left_ext": (50, 2000),
    "telescopic_right_ext": (50, 1000),
    "capacity": (100, 10000),
}


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


def gather_plan_lifts(machine_type: str) -> list:
    """Collect the plan-view lift form dicts from session_state, as (bank, idx,
    data) tuples. The section view derives its geometry from a real plan lift,
    exactly like the KARR AI /preview/section endpoint."""
    arrangement = st.session_state.get("arrangement", "Inline")
    out = []
    n1 = int(st.session_state.get("num_lifts_bank1", 1))
    for i in range(n1):
        d = st.session_state.get(f"bank1_lift_{i}_data") or make_default_lift("passenger", machine_type)
        out.append(("bank1", i, d))
    if arrangement == "Facing":
        n2 = int(st.session_state.get("num_lifts_bank2", 2))
        for i in range(n2):
            d = st.session_state.get(f"bank2_lift_{i}_data") or make_default_lift("passenger", machine_type)
            out.append(("bank2", i, d))
    return out


def copy_lift_to_section(lift: dict, plan_wall_thickness: int) -> None:
    """Port of copyLiftValuesToSection() — copy a plan lift's shaft depth, door
    height and structural height into the section form (+ plan wall thickness).
    Writes both the section data dict and the widget keys (called before the
    section form is rendered this run)."""
    S = st.session_state.setdefault("section_data", make_default_section())
    updates = {
        "shaft_width": int(lift["shaft_depth"]),  # section 'Shaft Depth' field
        "door_height": max(1500, min(3500, int(lift["door_height"]))),
        "structural_opening_height": max(1500, min(4000, int(lift["structural_opening_height"]))),
        "wall_thickness": max(100, min(500, int(plan_wall_thickness))),
    }
    for f, v in updates.items():
        S[f] = v
        st.session_state[f"section_w_{f}"] = v


# =============================================================================
# Per-lift config form — 1:1 port of the web LiftConfigForm component.
# Brackets are always-editable, zero-sum linked, clamped only with max(0, .).
# Car-width / shaft changes redistribute brackets but keep them editable.
# =============================================================================

def render_lift_config_form(
    lift_index: int,
    bank_name: str,
    machine_type: str,
    show_capacity_input: bool = False,
) -> dict:
    """Render one lift's config form and return its form-data dict."""
    prefix = f"{bank_name}_lift_{lift_index}"
    data_key = f"{prefix}_data"
    mt_key = f"{prefix}_prev_mt"

    def _reset_widget_keys(keep: set = frozenset()):
        for k in list(st.session_state.keys()):
            if k.startswith(f"{prefix}_w_") and k not in keep:
                del st.session_state[k]

    # Initialize, or reset on machine-type change (web resets every lift to the
    # default for the new machine type, preserving lift type).
    if data_key not in st.session_state:
        st.session_state[data_key] = make_default_lift("passenger", machine_type)
        st.session_state[mt_key] = machine_type
    elif st.session_state.get(mt_key) != machine_type:
        cur_type = st.session_state[data_key].get("type", "passenger")
        st.session_state[data_key] = make_default_lift(cur_type, machine_type)
        st.session_state[mt_key] = machine_type
        _reset_widget_keys()

    L = st.session_state[data_key]

    def _apply(updates: dict):
        """Write fields to the lift dict + mirror to their widget keys.

        Values written to a bounded widget are clamped to that widget's
        min/max so Streamlit never sees an out-of-range session_state value.
        The lift dict keeps the clamped value too (it is what gets drawn).
        """
        data = st.session_state[data_key]
        for k, v in updates.items():
            if v is not None and k in FIELD_BOUNDS:
                lo, hi = FIELD_BOUNDS[k]
                v = max(lo, min(hi, v))
            data[k] = v
            wk = f"{prefix}_w_{k}"
            if wk in st.session_state:
                st.session_state[wk] = v

    # ── Callbacks (mirror the React onChange handlers exactly) ──

    def _cb_type():
        new_type = st.session_state[f"{prefix}_w_type"]
        st.session_state[data_key] = make_default_lift(new_type, machine_type)
        _reset_widget_keys(keep={f"{prefix}_w_type"})

    def _cb_cabin():
        data = st.session_state[data_key]
        w, d = (int(x) for x in st.session_state[f"{prefix}_w_cabin"].split("x"))
        rail_l, rail_r = lift_rails(data)
        new_avail = data["shaft_width"] - (w + 2 * CAR_WALL_THICKNESS) - rail_l - rail_r
        upd = {"width": w, "depth": d}
        if machine_type == "mrl" or data["double_entrance"] or data["type"] == "fire":
            extra = max(0, new_avail - MRL_CW_BRACKET_MIN - MRL_CAR_BRACKET_MIN)
            cw = MRL_CW_BRACKET_MIN + extra // 2
            upd["cw_bracket_width"] = cw
            upd["car_bracket_width"] = new_avail - cw
        else:
            extra = max(0, new_avail - 2 * MRA_CAR_BRACKET_MIN)
            left = MRA_CAR_BRACKET_MIN + extra // 2
            upd["mra_left_bracket"] = left
            upd["mra_right_bracket"] = new_avail - left
        if data["double_entrance"]:
            door_zone = 2 * (data["door_panel_thickness"] or PANEL_THICKNESS_DEFAULT) + lift_door_gap(data)
            upd["shaft_depth"] = door_zone + d + door_zone
        _apply(upd)

    def _cb_width():
        data = st.session_state[data_key]
        v = st.session_state[f"{prefix}_w_width"]
        rail_l, rail_r = lift_rails(data)
        new_avail = data["shaft_width"] - (v + 2 * CAR_WALL_THICKNESS) - rail_l - rail_r
        upd = {"width": v}
        half = new_avail // 2
        if machine_type == "mrl":
            upd["cw_bracket_width"] = max(0, half)
            upd["car_bracket_width"] = max(0, new_avail - half)
        else:
            upd["mra_left_bracket"] = max(0, half)
            upd["mra_right_bracket"] = max(0, new_avail - half)
        _apply(upd)

    def _cb_shaft_width():
        data = st.session_state[data_key]
        new_sw = st.session_state[f"{prefix}_w_shaft_width"]
        uc_w = data["width"] + 2 * CAR_WALL_THICKNESS
        rail_l, rail_r = lift_rails(data)
        old_avail = data["shaft_width"] - uc_w - rail_l - rail_r
        new_avail = new_sw - uc_w - rail_l - rail_r
        half = (new_avail - old_avail) // 2
        upd = {"shaft_width": new_sw}
        if machine_type == "mrl" or data["double_entrance"] or data["type"] == "fire":
            old_cw = data["cw_bracket_width"] if data["cw_bracket_width"] is not None else MRL_CW_BRACKET_MIN
            new_cw = old_cw + half
            upd["cw_bracket_width"] = max(0, new_cw)
            upd["car_bracket_width"] = max(0, new_avail - new_cw)
        else:
            old_left = data["mra_left_bracket"] if data["mra_left_bracket"] is not None else MRA_CAR_BRACKET_MIN
            new_left = old_left + half
            upd["mra_left_bracket"] = max(0, new_left)
            upd["mra_right_bracket"] = max(0, new_avail - new_left)
        _apply(upd)

    def _cb_shaft_depth():
        data = st.session_state[data_key]
        new_sd = st.session_state[f"{prefix}_w_shaft_depth"]
        upd = {"shaft_depth": new_sd}
        if machine_type == "mra" and not data["double_entrance"] and data["type"] != "fire":
            uc_d = data["depth"] + CAR_WALL_THICKNESS
            fixed_depth = 2 * (data["door_panel_thickness"] or PANEL_THICKNESS_DEFAULT) + lift_door_gap(data) + uc_d
            wall_gap = data["mra_cw_wall_gap"] if data["mra_cw_wall_gap"] is not None else MRA_CW_WALL_GAP_MIN
            old_avail_d = data["shaft_depth"] - fixed_depth - wall_gap
            new_avail_d = new_sd - fixed_depth - wall_gap
            old_cwd = data["mra_cw_bracket_depth"] if data["mra_cw_bracket_depth"] is not None else MRA_CW_BRACKET_DEPTH_MIN
            half = (new_avail_d - old_avail_d) // 2
            new_cwd = old_cwd + half
            upd["mra_cw_bracket_depth"] = max(0, new_cwd)
            upd["mra_cw_gap"] = max(0, new_avail_d - new_cwd)
        _apply(upd)

    def _avail_w():
        data = st.session_state[data_key]
        rail_l, rail_r = lift_rails(data)
        return data["shaft_width"] - (data["width"] + 2 * CAR_WALL_THICKNESS) - rail_l - rail_r

    def _cb_rail_left():
        # Rail edit: same-side bracket absorbs (zone and shaft width stay put)
        data = st.session_state[data_key]
        v = max(0, st.session_state[f"{prefix}_w_rail_width_left"])
        old_l, _ = lift_rails(data)
        delta = v - old_l
        upd = {"rail_width_left": v}
        if machine_type == "mrl" or data["double_entrance"] or data["type"] == "fire":
            cw = data["cw_bracket_width"] if data["cw_bracket_width"] is not None else MRL_CW_BRACKET_MIN
            upd["cw_bracket_width"] = cw - delta
        else:
            left = data["mra_left_bracket"] if data["mra_left_bracket"] is not None else MRA_CAR_BRACKET_MIN
            upd["mra_left_bracket"] = left - delta
        _apply(upd)

    def _cb_rail_right():
        data = st.session_state[data_key]
        v = max(0, st.session_state[f"{prefix}_w_rail_width_right"])
        _, old_r = lift_rails(data)
        delta = v - old_r
        upd = {"rail_width_right": v}
        if machine_type == "mrl" or data["double_entrance"] or data["type"] == "fire":
            car = data["car_bracket_width"] if data["car_bracket_width"] is not None else MRL_CAR_BRACKET_MIN
            upd["car_bracket_width"] = car - delta
        else:
            right = data["mra_right_bracket"] if data["mra_right_bracket"] is not None else MRA_CAR_BRACKET_MIN
            upd["mra_right_bracket"] = right - delta
        _apply(upd)

    def _cb_door_gap():
        data = st.session_state[data_key]
        v = max(0, st.session_state[f"{prefix}_w_door_gap"])
        upd = {"door_gap": v}
        if data["double_entrance"]:
            door_zone = 2 * (data["door_panel_thickness"] or PANEL_THICKNESS_DEFAULT) + v
            upd["shaft_depth"] = door_zone + data["depth"] + door_zone
        _apply(upd)

    def _cb_cw():
        v = max(0, st.session_state[f"{prefix}_w_cw_bracket_width"])
        _apply({"cw_bracket_width": v, "car_bracket_width": _avail_w() - v})

    def _cb_car():
        v = max(0, st.session_state[f"{prefix}_w_car_bracket_width"])
        _apply({"car_bracket_width": v, "cw_bracket_width": _avail_w() - v})

    def _cb_mra_left():
        v = max(0, st.session_state[f"{prefix}_w_mra_left_bracket"])
        _apply({"mra_left_bracket": v, "mra_right_bracket": _avail_w() - v})

    def _cb_mra_right():
        v = max(0, st.session_state[f"{prefix}_w_mra_right_bracket"])
        _apply({"mra_right_bracket": v, "mra_left_bracket": _avail_w() - v})

    def _avail_d():
        data = st.session_state[data_key]
        uc_d = data["depth"] + CAR_WALL_THICKNESS
        fixed = 2 * (data["door_panel_thickness"] or PANEL_THICKNESS_DEFAULT) + lift_door_gap(data) + uc_d
        wall_gap = data["mra_cw_wall_gap"] if data["mra_cw_wall_gap"] is not None else MRA_CW_WALL_GAP_MIN
        return data["shaft_depth"] - fixed - wall_gap

    def _cb_mra_cwd():
        v = max(0, st.session_state[f"{prefix}_w_mra_cw_bracket_depth"])
        _apply({"mra_cw_bracket_depth": v, "mra_cw_gap": _avail_d() - v})

    def _cb_mra_gap():
        v = max(0, st.session_state[f"{prefix}_w_mra_cw_gap"])
        _apply({"mra_cw_gap": v, "mra_cw_bracket_depth": _avail_d() - v})

    def _cb_mra_wall_gap():
        data = st.session_state[data_key]
        v = max(0, st.session_state[f"{prefix}_w_mra_cw_wall_gap"])
        uc_d = data["depth"] + CAR_WALL_THICKNESS
        fixed = 2 * (data["door_panel_thickness"] or PANEL_THICKNESS_DEFAULT) + lift_door_gap(data) + uc_d
        new_avail_d = data["shaft_depth"] - fixed - v
        cwd = data["mra_cw_bracket_depth"] if data["mra_cw_bracket_depth"] is not None else MRA_CW_BRACKET_DEPTH_MIN
        _apply({"mra_cw_wall_gap": v, "mra_cw_gap": max(0, new_avail_d - cwd)})

    def _cb_double():
        # Double entrance is fire-only; fire lifts use MRL-style side brackets in
        # both MRL and MRA, so only the shaft depth changes with the toggle.
        data = st.session_state[data_key]
        on = st.session_state[f"{prefix}_w_double_entrance"]
        upd = {"double_entrance": on}
        if on:
            door_zone = 2 * (data["door_panel_thickness"] or PANEL_THICKNESS_DEFAULT) + lift_door_gap(data)
            upd["shaft_depth"] = door_zone + data["depth"] + door_zone
        else:
            uc_d = data["depth"] + CAR_WALL_THICKNESS
            upd["shaft_depth"] = 2 * PANEL_THICKNESS_DEFAULT + lift_door_gap(data) + uc_d + REAR_CLEARANCE
        _apply(upd)

    def _cb_door_width():
        data = st.session_state[data_key]
        v = st.session_state[f"{prefix}_w_door_width"]
        upd = {"door_width": v}
        if data["door_opening_type"] != "telescopic":
            prev = data["door_width"]
            current_panel = (data["door_panel_length"]
                             if data["door_panel_length"] is not None
                             else min(2 * prev + 2 * DEFAULT_DOOR_EXTENSION, data["shaft_width"]))
            upd["door_panel_length"] = current_panel + 2 * (v - prev)
        if data["door_opening_type"] == "telescopic" and data["telescopic_left_ext"] is not None:
            old_default = int(0.5 * data["door_width"]) + TELESCOPIC_LEFT_EXT_EXTRA
            if data["telescopic_left_ext"] == old_default:
                upd["telescopic_left_ext"] = int(0.5 * v) + TELESCOPIC_LEFT_EXT_EXTRA
        _apply(upd)

    def _cb_door_opening_type():
        data = st.session_state[data_key]
        new_type = st.session_state[f"{prefix}_w_door_opening_type"]
        upd = {"door_opening_type": new_type}
        if new_type == "telescopic":
            upd["telescopic_left_ext"] = int(0.5 * data["door_width"]) + TELESCOPIC_LEFT_EXT_EXTRA
            upd["telescopic_right_ext"] = TELESCOPIC_RIGHT_EXT
            upd["door_panel_length"] = None
        else:
            upd["telescopic_left_ext"] = None
            upd["telescopic_right_ext"] = None
            upd["door_panel_length"] = min(2 * data["door_width"] + 2 * DEFAULT_DOOR_EXTENSION, data["shaft_width"])
        _apply(upd)

    def _cb_thickness():
        data = st.session_state[data_key]
        v = st.session_state[f"{prefix}_w_door_panel_thickness"]
        upd = {"door_panel_thickness": v}
        if data["double_entrance"]:
            door_zone = 2 * v + lift_door_gap(data)
            upd["shaft_depth"] = door_zone + data["depth"] + door_zone
        _apply(upd)

    def _store(field):
        def cb():
            _apply({field: st.session_state[f"{prefix}_w_{field}"]})
        return cb

    def _cb_panel_len():
        # Clamp only user edits to [500, 6000] (web NumInput commit behavior).
        # Programmatic auto-grow from door width is left uncapped (see
        # FIELD_BOUNDS) so it matches the web.
        v = max(500, min(6000, st.session_state[f"{prefix}_w_door_panel_length"]))
        _apply({"door_panel_length": v})

    # ── Number-input helper: seed session_state once, no value= (avoids the
    #    Streamlit "value + session_state" warning), clamp seed into range. ──
    def _num(field, label, *, min_value=None, max_value=None, step=1,
             on_change=None, help=None, disabled=False, seed=None):
        wk = f"{prefix}_w_{field}"
        if wk not in st.session_state:
            s = seed if seed is not None else L.get(field)
            if s is None:
                s = min_value if min_value is not None else 0
            s = int(s)
            if min_value is not None:
                s = max(min_value, s)
            if max_value is not None:
                s = min(max_value, s)
            st.session_state[wk] = s
        kwargs = {"key": wk, "step": step}
        if min_value is not None:
            kwargs["min_value"] = min_value
        if max_value is not None:
            kwargs["max_value"] = max_value
        if on_change is not None:
            kwargs["on_change"] = on_change
        if help is not None:
            kwargs["help"] = help
        if disabled:
            kwargs["disabled"] = True
        return st.number_input(label, **kwargs)

    # ── Render ──
    is_fire = L["type"] == "fire"
    title = f"Lift {lift_index + 1} · {'Fire/Service' if is_fire else 'Passenger'}"

    with st.expander(title, expanded=(lift_index == 0)):

        # Lift Type
        tkey = f"{prefix}_w_type"
        if tkey not in st.session_state:
            st.session_state[tkey] = L["type"]
        st.selectbox(
            "Lift Type",
            options=["passenger", "fire"],
            format_func=lambda x: "Fire/Service" if x == "fire" else "Passenger",
            key=tkey, on_change=_cb_type,
        )

        # Double Car Entrance (fire only)
        if is_fire:
            dkey = f"{prefix}_w_double_entrance"
            if dkey not in st.session_state:
                st.session_state[dkey] = bool(L["double_entrance"])
            st.checkbox("Double Car Entrance", key=dkey, on_change=_cb_double)

        # Shaft Dimensions
        st.markdown("**Shaft Dimensions**")
        mrl_style = machine_type == "mrl" or L["double_entrance"] or L["type"] == "fire"
        if mrl_style:
            width_formula = ("Min = CWT Bracket Spacing + Unfinished Car Width "
                             "(finished + 50) + Car Bracket Spacing")
            if is_fire:
                width_formula += ". Fire lifts: at least 2700 (2925 with telescopic doors)."
        else:
            width_formula = ("Min = Left Car Bracket Spacing + Unfinished Car Width "
                             "(finished + 50) + Right Car Bracket Spacing")
        if L["double_entrance"]:
            depth_formula = ("Auto-computed: Door Zone + Finished Car Depth + Door Zone, "
                             "where Door Zone = 2 x Door Panel + Door Gap")
        elif mrl_style:
            depth_formula = ("Min = Unfinished Car Depth (finished + 25) + "
                             "2 x Door Panel + Door Gap + Rear Clearance (200)")
        else:
            depth_formula = ("Min = 2 x Door Panel + Door Gap + Unfinished Car Depth "
                             "(finished + 25) + CWT Gap + CWT Bracket Spacing + "
                             "CWT Wall Gap")
        c1, c2 = st.columns(2)
        with c1:
            _num("shaft_width", "Shaft Width (mm)", step=10, on_change=_cb_shaft_width,
                 help=width_formula)
        with c2:
            _num("shaft_depth", "Shaft Depth (mm)", step=10, on_change=_cb_shaft_depth,
                 disabled=bool(L["double_entrance"]),
                 help=depth_formula)

        # Swap bracket sides — only for MRL-style side-bracket lifts. MRA passenger
        # has car brackets on both sides, so there is nothing to swap.
        if mrl_style:
            swkey = f"{prefix}_w_swap_brackets"
            if swkey not in st.session_state:
                st.session_state[swkey] = bool(L.get("swap_brackets", False))

            def _cb_swap():
                _apply({"swap_brackets": st.session_state[swkey]})

            st.checkbox(
                "Swap brackets",
                key=swkey, on_change=_cb_swap,
                help="Swap positions of the CWT bracket and car bracket with each other."
            )

        # Capacity (conditional)
        if show_capacity_input:
            _num("capacity", "Capacity (KG)", min_value=100, max_value=10000, step=50,
                 on_change=_store("capacity"),
                 seed=L["capacity"] if L["capacity"] is not None else (1600 if is_fire else 1350))

        # Car Dimensions
        st.markdown("**Car Dimensions**")
        if is_fire:
            ckey = f"{prefix}_w_cabin"
            cabin_opts = [f"{w}x{d}" for w, d in FIRE_LIFT_CABIN_SIZES]
            cur_cabin = f"{L['width']}x{L['depth']}"
            if ckey not in st.session_state:
                st.session_state[ckey] = cur_cabin if cur_cabin in cabin_opts else cabin_opts[0]
            st.selectbox(
                "Cabin Size (W x D)",
                options=cabin_opts,
                format_func=lambda s: s.replace("x", " x ") + " mm",
                key=ckey, on_change=_cb_cabin,
            )
        else:
            cc1, cc2 = st.columns(2)
            with cc1:
                _num("width", "Car Width (mm)", step=10, on_change=_cb_width)
            with cc2:
                _num("depth", "Car Depth (mm)", step=10, on_change=_store("depth"))

        # Shaft Spacing — always editable, zero-sum, max(0, .) only
        st.markdown("**Shaft Spacing**")
        if machine_type == "mrl" or L["double_entrance"] or L["type"] == "fire":
            bc1, bc2 = st.columns(2)
            with bc1:
                _num("cw_bracket_width", "CWT Bracket Spacing (mm)", step=25,
                     on_change=_cb_cw, help="Car bracket auto-adjusts.",
                     seed=L["cw_bracket_width"] if L["cw_bracket_width"] is not None else MRL_CW_BRACKET_MIN)
            with bc2:
                _num("car_bracket_width", "Car Bracket Spacing (mm)", step=25,
                     on_change=_cb_car, help="CWT bracket auto-adjusts.",
                     seed=L["car_bracket_width"] if L["car_bracket_width"] is not None else MRL_CAR_BRACKET_MIN)
        else:
            st.caption("Width")
            wc1, wc2 = st.columns(2)
            with wc1:
                _num("mra_left_bracket", "Left Car Bracket Spacing (mm)", step=25,
                     on_change=_cb_mra_left,
                     seed=L["mra_left_bracket"] if L["mra_left_bracket"] is not None else MRA_CAR_BRACKET_MIN)
            with wc2:
                _num("mra_right_bracket", "Right Car Bracket Spacing (mm)", step=25,
                     on_change=_cb_mra_right,
                     seed=L["mra_right_bracket"] if L["mra_right_bracket"] is not None else MRA_CAR_BRACKET_MIN)
            st.caption("Depth")
            dc1, dc2 = st.columns(2)
            with dc1:
                _num("mra_cw_bracket_depth", "CWT Bracket Spacing (mm)", step=25,
                     on_change=_cb_mra_cwd,
                     seed=L["mra_cw_bracket_depth"] if L["mra_cw_bracket_depth"] is not None else MRA_CW_BRACKET_DEPTH_MIN)
            with dc2:
                _num("mra_cw_gap", "CWT Gap (mm)", step=25,
                     on_change=_cb_mra_gap,
                     seed=L["mra_cw_gap"] if L["mra_cw_gap"] is not None else MRA_CW_GAP_MIN)
            _num("mra_cw_wall_gap", "CWT Wall Gap (mm)", step=25,
                 on_change=_cb_mra_wall_gap,
                 help="Space between rear wall and CWT box. CWT gap auto-adjusts.",
                 seed=L["mra_cw_wall_gap"] if L["mra_cw_wall_gap"] is not None else MRA_CW_WALL_GAP_MIN)

        # Car guide rails (decoupled from brackets; arrow shows bracket + rail)
        rc1, rc2 = st.columns(2)
        with rc1:
            _num("rail_width_left", "Left Rail Spacing (mm)", step=5,
                 on_change=_cb_rail_left,
                 help="Bracket on this side auto-adjusts; arrow shows bracket + rail.",
                 seed=L.get("rail_width_left") if L.get("rail_width_left") is not None else RAIL_WIDTH_DEFAULT)
        with rc2:
            _num("rail_width_right", "Right Rail Spacing (mm)", step=5,
                 on_change=_cb_rail_right,
                 help="Bracket on this side auto-adjusts.",
                 seed=L.get("rail_width_right") if L.get("rail_width_right") is not None else RAIL_WIDTH_DEFAULT)

        # CW box visual dimensions (free inputs; the box floats inside its zone)
        if machine_type == "mrl" or L["double_entrance"] or L["type"] == "fire":
            cwb1, cwb2 = st.columns(2)
            with cwb1:
                _num("cw_box_width", "CWT Box Width (mm)", step=25,
                     on_change=_store("cw_box_width"),
                     seed=L.get("cw_box_width") if L.get("cw_box_width") is not None else CW_BOX_WIDTH_DEFAULT)
            with cwb2:
                _num("cw_box_depth", "CWT Box Depth (mm)", step=25,
                     on_change=_store("cw_box_depth"),
                     seed=L.get("cw_box_depth") if L.get("cw_box_depth") is not None else CW_BOX_DEPTH_DEFAULT)
        else:
            _num("mra_cw_box_width", "CWT Box Spacing (mm)", step=25,
                 on_change=_store("mra_cw_box_width"),
                 help="Width of the rear CWT box (depth = CWT Bracket Spacing).",
                 seed=L.get("mra_cw_box_width") if L.get("mra_cw_box_width") is not None else MRA_CW_BOX_WIDTH_DEFAULT)

        # Door Settings
        st.markdown("**Door Settings**")
        dwc1, dwc2 = st.columns(2)
        with dwc1:
            _num("door_width", "Door Width (mm)",
                 min_value=FIRE_DOOR_WIDTH if is_fire else 700, max_value=2000, step=50,
                 on_change=_cb_door_width)
        with dwc2:
            _num("door_height", "Door Height (mm)", min_value=1500, max_value=3500, step=50,
                 on_change=_store("door_height"))

        _num("door_gap", "Running Clearance (mm)", min_value=0, max_value=500, step=5,
             on_change=_cb_door_gap,
             help="Clearance between the landing and car door.",
             seed=L.get("door_gap") if L.get("door_gap") is not None else DOOR_GAP)

        if is_fire:
            otkey = f"{prefix}_w_door_opening_type"
            if otkey not in st.session_state:
                st.session_state[otkey] = L["door_opening_type"]
            st.selectbox(
                "Door Opening Type",
                options=["centre", "telescopic"],
                format_func=lambda x: "Telescopic Opening" if x == "telescopic" else "Centre Opening",
                key=otkey, on_change=_cb_door_opening_type,
            )

        if L["door_opening_type"] == "telescopic":
            tc1, tc2 = st.columns(2)
            with tc1:
                _num("telescopic_left_ext", "Left Extension (mm)", min_value=50, max_value=2000, step=25,
                     on_change=_store("telescopic_left_ext"),
                     seed=L["telescopic_left_ext"] if L["telescopic_left_ext"] is not None
                     else int(0.5 * L["door_width"]) + TELESCOPIC_LEFT_EXT_EXTRA)
            with tc2:
                _num("telescopic_right_ext", "Right Extension (mm)", min_value=50, max_value=1000, step=25,
                     on_change=_store("telescopic_right_ext"),
                     seed=L["telescopic_right_ext"] if L["telescopic_right_ext"] is not None else TELESCOPIC_RIGHT_EXT)
            _num("door_panel_thickness", "Door Panel Thickness (mm)", min_value=50, max_value=300, step=10,
                 on_change=_cb_thickness)
        else:
            pc1, pc2 = st.columns(2)
            with pc1:
                # No min/max on the widget so an auto-grown value past 6000
                # doesn't raise; _cb_panel_len clamps user input to [500, 6000].
                _num("door_panel_length", "Door Panel Length (mm)", step=50,
                     on_change=_cb_panel_len,
                     seed=L["door_panel_length"] if L["door_panel_length"] is not None
                     else min(2 * L["door_width"] + 2 * DEFAULT_DOOR_EXTENSION, L["shaft_width"]))
            with pc2:
                _num("door_panel_thickness", "Door Panel Thickness (mm)", min_value=50, max_value=300, step=10,
                     on_change=_cb_thickness)

        sc1, sc2 = st.columns(2)
        with sc1:
            _num("structural_opening_width", "Structural Opening W (mm)", min_value=800, max_value=3000, step=50,
                 on_change=_store("structural_opening_width"))
        with sc2:
            _num("structural_opening_height", "Structural Opening H (mm)", min_value=1500, max_value=4000, step=50,
                 on_change=_store("structural_opening_height"))

        # Door horizontal offset from cabin centre (X axis). No upper bound —
        # the user is responsible for visual correctness, even if parts overlap.
        oc1, oc2 = st.columns(2)
        with oc1:
            _num("door_offset_mm", "Door Centre Offset (mm)", min_value=0, step=25,
                 on_change=_store("door_offset_mm"),
                 help="Shift the door (opening, jambs, panels, returns) left/right "
                      "from the cabin centre. Overlap is allowed.")
        with oc2:
            odkey = f"{prefix}_w_door_offset_direction"
            if odkey not in st.session_state:
                st.session_state[odkey] = L.get("door_offset_direction", "right")
            st.selectbox(
                "Offset Direction",
                options=["left", "right"],
                format_func=lambda x: x.capitalize(),
                key=odkey, on_change=_store("door_offset_direction"),
            )

    return st.session_state[data_key]


# =============================================================================
# Form data -> LiftConfig — 1:1 port of sketch_generator_task.build_lift_config
# =============================================================================

def build_lift_config(lift_data: dict, machine_type: str, wall_thickness: float) -> LiftConfig:
    """Build a LiftConfig from per-lift form data (matches the worker task)."""
    door_width = lift_data.get("door_width", 1100)
    door_opening_type = lift_data.get("door_opening_type", "centre")
    door_panel_length = lift_data.get("door_panel_length")

    if door_opening_type == "telescopic":
        door_extension = 0
    elif door_panel_length:
        door_extension = (door_panel_length - 2 * door_width) / 2
    else:
        door_extension = 100

    kwargs = {
        "lift_type": lift_data.get("type", "passenger"),
        "lift_machine_type": machine_type,
        "finished_car_width": lift_data.get("width", 1900),
        "finished_car_depth": lift_data.get("depth", 1600),
        "door_width": door_width,
        "door_height": lift_data.get("door_height", 2100),
        "door_panel_thickness": lift_data.get("door_panel_thickness", 150),
        "door_extension": door_extension,
        "structural_opening_width": lift_data.get("structural_opening_width", 1300),
        "structural_opening_height": lift_data.get("structural_opening_height", 2200),
        "wall_thickness": wall_thickness,
        "door_opening_type": door_opening_type,
    }

    if lift_data.get("capacity"):
        kwargs["lift_capacity"] = lift_data["capacity"]

    # Rails + running clearance (LiftConfig bracket fields are ZONE widths,
    # so form's pure bracket values get the rail added back below)
    rail_l, rail_r = lift_rails(lift_data)
    kwargs["rail_width_left"] = rail_l
    kwargs["rail_width_right"] = rail_r
    kwargs["door_gap"] = lift_door_gap(lift_data)
    if lift_data.get("cw_box_width") is not None:
        kwargs["cw_box_width"] = lift_data["cw_box_width"]
    if lift_data.get("cw_box_depth") is not None:
        kwargs["cw_box_depth"] = lift_data["cw_box_depth"]
    if lift_data.get("mra_cw_box_width") is not None:
        kwargs["mra_cw_box_width"] = lift_data["mra_cw_box_width"]

    is_double_entrance = lift_data.get("double_entrance", False)
    is_fire = lift_data.get("type") == "fire"
    if machine_type == "mrl" or (machine_type == "mra" and (is_double_entrance or is_fire)):
        if lift_data.get("cw_bracket_width") is not None:
            kwargs["counterweight_bracket_width"] = lift_data["cw_bracket_width"] + rail_l
        if lift_data.get("car_bracket_width") is not None:
            kwargs["car_bracket_width"] = lift_data["car_bracket_width"] + rail_r
    if machine_type == "mra":
        if lift_data.get("mra_left_bracket") is not None:
            kwargs["mra_car_bracket_width"] = lift_data["mra_left_bracket"] + rail_l
        if lift_data.get("mra_right_bracket") is not None:
            kwargs["mra_car_bracket_width_right"] = lift_data["mra_right_bracket"] + rail_r
        if lift_data.get("mra_cw_bracket_depth") is not None:
            kwargs["mra_cw_bracket_depth"] = lift_data["mra_cw_bracket_depth"]
        if lift_data.get("mra_cw_wall_gap") is not None:
            kwargs["mra_cw_wall_gap"] = lift_data["mra_cw_wall_gap"]

    if lift_data.get("double_entrance"):
        kwargs["double_entrance"] = True

    if lift_data.get("swap_brackets"):
        kwargs["swap_brackets"] = True

    if lift_data.get("telescopic_left_ext") is not None:
        kwargs["telescopic_left_ext"] = lift_data["telescopic_left_ext"]
    if lift_data.get("telescopic_right_ext") is not None:
        kwargs["telescopic_right_ext"] = lift_data["telescopic_right_ext"]

    if lift_data.get("door_offset_mm"):
        kwargs["door_offset_mm"] = lift_data["door_offset_mm"]
        kwargs["door_offset_direction"] = lift_data.get("door_offset_direction", "right")

    # Construct once (surfaces any genuine config error, e.g. fire cabin size).
    LiftConfig(**kwargs)

    shaft_width = lift_data.get("shaft_width")
    shaft_depth = lift_data.get("shaft_depth")
    if shaft_width is not None:
        kwargs["shaft_width_override"] = shaft_width
    if shaft_depth is not None:
        kwargs["shaft_depth_override"] = shaft_depth

    return LiftConfig(**kwargs)


# =============================================================================
# Section-view config form — port of the web SectionConfigForm.
# =============================================================================

def render_section_config_form(machine_type: str) -> dict:
    """Render the section-view config form; return its data dict."""
    sec_key = "section_data"
    if sec_key not in st.session_state:
        st.session_state[sec_key] = make_default_section()
    S = st.session_state[sec_key]

    def _num(field, label, *, min_value=None, max_value=None, step=1):
        wk = f"section_w_{field}"
        if wk not in st.session_state:
            s = int(S[field])
            if min_value is not None:
                s = max(min_value, s)
            if max_value is not None:
                s = min(max_value, s)
            st.session_state[wk] = s

        def cb():
            S[field] = st.session_state[wk]

        kwargs = {"key": wk, "step": step, "on_change": cb}
        if min_value is not None:
            kwargs["min_value"] = min_value
        if max_value is not None:
            kwargs["max_value"] = max_value
        return st.number_input(label, **kwargs)

    c1, c2 = st.columns(2)
    with c1:
        _num("shaft_width", "Shaft Depth (mm)", step=10)
    with c2:
        _num("wall_thickness", "Wall Thickness (mm)", min_value=100, max_value=500, step=25)

    c3, c4 = st.columns(2)
    with c3:
        _num("pit_slab", "Pit Slab (mm)", min_value=100, max_value=500, step=25)
    with c4:
        _num("pit_depth", "Pit Depth (mm)", min_value=500, max_value=3000, step=50)

    c5, c6 = st.columns(2)
    with c5:
        _num("travel_height", "Travel Height (mm)", min_value=5000, max_value=200000, step=1000)
    with c6:
        _num("overhead_clearance", "Headroom (mm)", min_value=2000, max_value=10000, step=100)

    c7, c8 = st.columns(2)
    with c7:
        _num("door_height", "Door Opening Height (mm)", min_value=1500, max_value=3500, step=50)
    with c8:
        _num("structural_opening_height", "Structural Opening Height (mm)", min_value=1500, max_value=4000, step=50)

    machine_room_height = None
    if machine_type == "mra":
        c9, _ = st.columns(2)
        with c9:
            _num("machine_room_height", "Machine Room Height (mm)", min_value=2000, max_value=6000, step=100)
        machine_room_height = S["machine_room_height"]

    return {
        "shaft_width": S["shaft_width"],
        "wall_thickness": S["wall_thickness"],
        "pit_slab": S["pit_slab"],
        "pit_depth": S["pit_depth"],
        "travel_height": S["travel_height"],
        "overhead_clearance": S["overhead_clearance"],
        "door_height": S["door_height"],
        "structural_opening_height": S["structural_opening_height"],
        "machine_room_height": machine_room_height,
    }


def require_password() -> bool:
    """Render the gate UI if needed. Returns True when authenticated.

    Mirrors the Code Charlie gate: full-screen dark/indigo splash with the
    Debbie logo (responsive — sized off viewport height/width) and a password
    form. When False, the caller should st.stop() so nothing else renders.
    """
    if st.session_state.get("authenticated"):
        return True

    font_data_uri = _file_data_uri(DISPLAY_FONT_PATH, "font/woff2")
    if font_data_uri:
        st.html(
            f"""
<style>
@font-face {{
    font-family: 'Clash Grotesk';
    src: url('{font_data_uri}') format('woff2');
    font-weight: 200 700;
    font-display: swap;
}}
</style>
"""
        )

    st.html(
        """
<style>
.stApp {
    background:
        radial-gradient(ellipse at top, rgba(99, 102, 241, 0.09), transparent 48%),
        radial-gradient(ellipse at bottom right, rgba(168, 85, 247, 0.08), transparent 58%),
        #020617 !important;
    color: #e2e8f0 !important;
}
#MainMenu, footer, header[data-testid="stHeader"] {
    visibility: hidden;
    height: 0;
}
html, body, .stApp, .stApp [data-testid="stAppViewContainer"] {
    height: 100vh;
    overflow: hidden;
}
.stApp [data-testid="stAppViewContainer"] > .main,
.stApp section.main {
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
.block-container {
    max-width: 48rem !important;
    height: 100vh !important;
    max-height: 100vh !important;
    padding-top: 0.75rem !important;
    padding-bottom: 0.75rem !important;
    display: flex !important;
    flex-direction: column;
    justify-content: center;
    gap: 0.4rem;
    overflow: hidden;
}
.stApp h1 {
    color: #f8fafc !important;
    text-align: center;
    font-weight: 700 !important;
    letter-spacing: 0;
    margin-bottom: 0.25rem !important;
}
.stApp [data-testid="stCaptionContainer"],
.stApp .stCaption,
.stApp p,
.stApp label {
    color: #94a3b8 !important;
}
.stApp [data-testid="stImage"] {
    display: flex;
    justify-content: center;
}
.stApp [data-testid="stImage"] img {
    filter: drop-shadow(0 0 42px rgba(56, 189, 248, 0.22));
}
.stApp [data-testid="stElementContainer"]:has(.gate-logo-wrap) {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    display: flex !important;
    align-items: center;
    justify-content: center;
    width: 100%;
}
.gate-logo-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    height: 100%;
    margin: 0;
}
.gate-logo-wrap img {
    display: block;
    width: auto;
    height: 100%;
    max-height: min(calc(100vh - 24rem), 90vw);
    max-width: 90vw;
    object-fit: contain;
    filter: drop-shadow(0 0 60px rgba(56, 189, 248, 0.28));
}
.gate-title-wrap {
    display: flex;
    justify-content: center;
    width: 100%;
    text-align: center;
    margin: 0;
}
.gate-title-wrap .gate-title {
    color: #f8fafc !important;
    text-align: center !important;
    font-family: 'Clash Grotesk', Inter, system-ui, sans-serif !important;
    font-size: 2.25rem;
    line-height: 1.05;
    font-weight: 700;
    letter-spacing: 0;
    margin: 0 !important;
}
.gate-subtitle {
    margin: 0 !important;
    font-size: 0.9rem;
}
.gate-description {
    margin: 0 0 0.25rem !important;
    font-size: 0.85rem;
}
.gate-subtitle,
.gate-description {
    text-align: center;
}
.stApp [data-testid="stForm"] {
    background: rgba(15, 23, 42, 0.62) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 1rem !important;
    backdrop-filter: blur(14px);
    padding: 0.9rem !important;
}
.stApp [data-testid="stTextInput"] input {
    background: rgba(2, 6, 23, 0.62) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    color: #f8fafc !important;
    border-radius: 0.6rem !important;
    padding-right: 3.5rem !important;
}
.stApp [data-testid="stTextInput"] input::placeholder {
    color: #94a3b8 !important;
    opacity: 0.85 !important;
}
.stApp [data-testid="stTextInput"] [data-testid="InputInstructions"],
.stApp [data-testid="stTextInput"] [class*="InputInstructions"],
.stApp [data-testid="stTextInput"] [aria-live="polite"] {
    display: none !important;
}
.stApp [data-testid="stTextInput"] button {
    margin-right: 0.35rem !important;
}
.stApp [data-testid="stTextInput"] input:focus {
    border-color: rgba(129, 140, 248, 0.48) !important;
    box-shadow: none !important;
}
.stApp [data-testid="stForm"] .stButton button {
    background: rgba(99, 102, 241, 0.82) !important;
    border: 1px solid rgba(129, 140, 248, 0.5) !important;
    color: #ffffff !important;
    border-radius: 0.65rem !important;
    width: 100%;
}
</style>
""",
    )

    image_data_uri = _file_data_uri(BRAND_IMAGE_PATH, "image/png")
    if image_data_uri:
        st.html(f'<div class="gate-logo-wrap"><img src="{image_data_uri}" alt=""></div>')

    st.html('<div class="gate-title-wrap"><h1 class="gate-title">DRAWING DEBBIE</h1></div>')
    st.markdown(
        '<p class="gate-subtitle">Powered by Medha 1.0 - KARR AI</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p class='gate-description'>Lift Plan &amp; Section Sketch Generator</p>",
        unsafe_allow_html=True,
    )

    with st.form("gate_form", clear_on_submit=False):
        password = st.text_input(
            "Password",
            type="password",
            autocomplete="current-password",
            placeholder="Enter password",
        )
        submitted = st.form_submit_button("Unlock")

    if submitted:
        gate_password = _gate_password()
        if password and gate_password and password == gate_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


# Max dimension-font scale (%) that fits before labels collide, by lift count.
# Measured empirically (text-bbox overlap vs the 100% baseline), floored to the
# 10% slider step and taken as the min across MRL/MRA. The slider's max_value is
# set from this so over-scaling that overlaps labels is simply not selectable —
# no caption needed; the control's range is the limit.
_DIM_FONT_MAX_INLINE = {1: 200, 2: 150, 3: 110, 4: 100}
_DIM_FONT_MAX_FACING = {1: 110, 2: 110, 3: 110, 4: 100}
_DIM_FONT_MAX_SECTION = 160


def _dim_font_max_pct(arrangement: str, n_bank1: int, n_bank2: int) -> int:
    """Largest dimension-font % that keeps labels collision-free for this layout."""
    if arrangement == "Facing":
        n = max(n_bank1, n_bank2)
        return _DIM_FONT_MAX_FACING.get(min(n, 4), 110)
    return _DIM_FONT_MAX_INLINE.get(min(n_bank1, 4), 110)


def _dim_font_slider(label_max: int, state_key: str):
    """Render the dimension-font slider with an adaptive max; clamp stored value
    into range first so Streamlit never errors when the ceiling drops."""
    help_txt = ("Scale the dimension label text. Upper limit adapts to the layout")
    if state_key in st.session_state:
        # Clamp existing value into the (possibly lowered) range. Omit `value` so
        # Streamlit doesn't warn about setting a default alongside session_state.
        st.session_state[state_key] = min(st.session_state[state_key], label_max)
        return st.slider(
            "Font Size",
            min_value=50, max_value=label_max, step=10, key=state_key, help=help_txt,
        )
    return st.slider(
        "Font Size",
        min_value=50, max_value=label_max, value=100, step=10, key=state_key, help=help_txt,
    )


def main():
    st.set_page_config(
        page_title="Drawing Debbie",
        page_icon=str(BRAND_IMAGE_PATH) if BRAND_IMAGE_PATH.exists() else "🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Password gate — nothing else renders until authenticated.
    if not require_password():
        st.stop()

    inject_brand_theme()

    st.html('<h1 class="main-brand-title">Drawing Debbie</h1>')

    # Sidebar configuration
    with st.sidebar:
        # Brand block — logo + title + subtitle. The logo is inlined as a
        # base64 <img> (not st.image) to preserve source quality on hi-DPI.
        brand_data_uri = _file_data_uri(BRAND_IMAGE_PATH, "image/png")
        if brand_data_uri:
            st.html(
                f'<img class="sidebar-brand-image" src="{brand_data_uri}" alt="Drawing Debbie" />'
            )
        st.html(
            '<div class="sidebar-brand-title">Drawing Debbie</div>'
            '<div class="sidebar-brand-subtitle">Powered by Medha 1.0 — KARR AI</div>'
        )

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
            dim_font_pct = _dim_font_slider(
                _dim_font_max_pct(arrangement, num_lifts_bank1, num_lifts_bank2),
                "dim_font_pct",
            )

        else:
            st.divider()
            st.subheader("Display Options")
            section_show_dimensions = st.checkbox("Show Dimensions", value=True, key="section_show_dimensions")
            section_show_hatching = st.checkbox("Show Hatching", value=True, key="section_show_hatching")
            section_show_break_lines = st.checkbox("Show Break Lines", value=True, key="section_show_break_lines")
            section_show_machine = st.checkbox("Show Machine Image", value=True, key="section_show_machine")
            section_dim_font_pct = _dim_font_slider(_DIM_FONT_MAX_SECTION, "section_dim_font_pct")

    # Machine-type change resets every lift to the new machine's defaults
    # (matches the web, which resets all lifts globally on machine change —
    # not lazily — so the Section view sees fresh data even when the plan
    # forms aren't currently rendered).
    if st.session_state.get("_app_prev_mt") != machine_type:
        for k in list(st.session_state.keys()):
            if k.startswith("bank1_lift_") or k.startswith("bank2_lift_"):
                del st.session_state[k]
        st.session_state["_app_prev_mt"] = machine_type

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
                    value=200,
                    step=25,
                    key="wall_thickness",
                )

            with col_shaft2:
                common_shaft = st.checkbox(
                    "Common Shaft",
                    value=False,
                    key="common_shaft",
                    help="If checked, lifts share a common shaft (steel-beam separator between passenger lifts).",
                )

            if arrangement == "Facing":
                lobby_width = st.number_input(
                    "Lobby Depth (mm)",
                    min_value=2000,
                    max_value=10000,
                    value=4000,
                    step=100,
                    key="lobby_width",
                )
            else:
                lobby_width = 4000

            # Per-gap separator types (only when common shaft + >= 2 lifts)
            sep_types_bank1 = compute_default_separator_types(bank1_lifts, common_shaft)
            sep_types_bank2 = compute_default_separator_types(bank2_lifts, common_shaft)

            sep_opts = ["rcc_wall", "steel_beam"]
            sep_fmt = lambda x: "Steel Beam" if x == "steel_beam" else "RCC Wall"

            if common_shaft and len(bank1_lifts) >= 2:
                st.caption("Bank 1 Separator Types")
                for i in range(len(bank1_lifts) - 1):
                    skey = f"sep_b1_{i}"
                    if skey not in st.session_state:
                        st.session_state[skey] = sep_types_bank1[i]
                    sep_types_bank1[i] = st.selectbox(
                        f"Lift {i + 1}–{i + 2}", options=sep_opts, format_func=sep_fmt, key=skey,
                    )

            if common_shaft and arrangement == "Facing" and len(bank2_lifts) >= 2:
                st.caption("Bank 2 Separator Types")
                for i in range(len(bank2_lifts) - 1):
                    skey = f"sep_b2_{i}"
                    if skey not in st.session_state:
                        st.session_state[skey] = sep_types_bank2[i]
                    sep_types_bank2[i] = st.selectbox(
                        f"Lift {i + 1}–{i + 2}", options=sep_opts, format_func=sep_fmt, key=skey,
                    )

        # Preview column
        with col_preview:
            st.header("Preview")

            generate_btn = st.button("Generate Sketch", type="primary", width="stretch", key="plan_generate")

            if generate_btn:
                try:
                    # Build LiftConfig objects for Bank 1
                    lift_configs = [build_lift_config(ld, machine_type, wall_thickness) for ld in bank1_lifts]

                    # Build LiftConfig objects for Bank 2 (if facing)
                    lift_configs_bank2 = None
                    if arrangement == "Facing" and bank2_lifts:
                        lift_configs_bank2 = [build_lift_config(ld, machine_type, wall_thickness) for ld in bank2_lifts]

                    # Create sketch
                    sketch = LiftShaftSketch(
                        lifts=lift_configs,
                        lifts_bank2=lift_configs_bank2,
                        lobby_width=lobby_width if arrangement == "Facing" else None,
                        is_common_shaft=common_shaft,
                        wall_thickness=wall_thickness,
                        separator_types_bank1=sep_types_bank1 or None,
                        separator_types_bank2=sep_types_bank2 or None,
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
                        font_scale=dim_font_pct / 100,
                    )

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

                st.download_button(
                    label="Download PNG",
                    data=st.session_state["generated_image"],
                    file_name="lift_plan.png",
                    mime="image/png",
                    width="stretch",
                )

    # ── Section View ──
    else:
        # Gather the plan-view lifts; the section is drawn from a real one
        # (matches KARR AI /preview/section).
        plan_lifts = gather_plan_lifts(machine_type)
        plan_wall = int(st.session_state.get("wall_thickness", 200))

        col_section_config, col_section_preview = st.columns([1, 1])

        with col_section_config:
            st.header("Section Configuration")

            # Copy shaft dimensions from a plan-view lift.
            st.caption("Copy shaft dimensions from a plan-view lift")
            copy_keys = [(b, i) for (b, i, _d) in plan_lifts]

            def _copy_label(bi):
                b, i = bi
                return f"{'Bank 1' if b == 'bank1' else 'Bank 2'} Lift {i + 1}"

            cp_sel, cp_btn = st.columns([0.72, 0.28])
            with cp_sel:
                copy_src = st.selectbox(
                    "Copy source", options=copy_keys, format_func=_copy_label,
                    key="section_copy_src", label_visibility="collapsed",
                )
            with cp_btn:
                if st.button("Copy", key="section_copy_btn", width="stretch"):
                    src_dict = next((d for (b, i, d) in plan_lifts if (b, i) == copy_src), None)
                    if src_dict is not None:
                        copy_lift_to_section(src_dict, plan_wall)
                    st.rerun()

            section_form = render_section_config_form(machine_type)

        with col_section_preview:
            st.header("Preview")

            section_generate_btn = st.button(
                "Generate Section", type="primary", width="stretch", key="section_generate"
            )

            if section_generate_btn:
                try:
                    wall = section_form["wall_thickness"]

                    # Target lift: fire if any fire lift is configured, else passenger.
                    target = "fire" if any(d["type"] == "fire" for (_b, _i, d) in plan_lifts) else "passenger"
                    configs = [build_lift_config(d, machine_type, wall) for (_b, _i, d) in plan_lifts]
                    section_lift_config = next((c for c in configs if c.lift_type == target), None)

                    # Fallback: synthetic config when no matching lift exists.
                    if section_lift_config is None:
                        section_lift_config = LiftConfig(
                            lift_machine_type=machine_type,
                            wall_thickness=wall,
                            door_height=section_form["door_height"],
                            structural_opening_height=section_form["structural_opening_height"],
                            shaft_depth_override=section_form["shaft_width"],
                        )

                    # Section form's Shaft Depth always overrides the lift's depth.
                    section_lift_config.shaft_depth_override = section_form["shaft_width"]

                    # Build SectionConfig
                    section_kwargs = {
                        "pit_slab": section_form["pit_slab"],
                        "pit_depth": section_form["pit_depth"],
                        "overhead_clearance": section_form["overhead_clearance"],
                        "travel_height": section_form["travel_height"],
                        "door_height": section_form["door_height"],
                        "structural_opening_height": section_form["structural_opening_height"],
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
                        font_scale=section_dim_font_pct / 100,
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
