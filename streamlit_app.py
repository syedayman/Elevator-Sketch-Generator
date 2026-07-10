"""
Streamlit web app for generating lift shaft plan and section sketches.

Feature parity with the KARR AI standalone sketch generator (apps/web
dashboard/sketches): single-config state model, multi-core plans, lift IDs +
brief-spec table, split passenger/fire plan carousel, whole-sketch undo/redo,
and the Debbie AI editing assistant. See sketch_state.py (config + reducers),
debbie_operations.py (operation interpreter) and debbie_agent.py (OpenAI call).
"""

import base64
import hashlib
import hmac
import os
import re
import tempfile
import time
from pathlib import Path

import streamlit as st

import debbie_agent
import debbie_operations as dops
import sketch_state as ss
from section_sketch import LiftSectionSketch, SectionConfig
from shaft_sketch import LiftConfig, LiftShaftSketch, FIRE_LIFT_CABIN_SIZES

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
/* Hide Streamlit's "Press Enter to …" input hints — they overlay the
   placeholder/value in narrow columns instead of sitting beside it. */
.stApp [data-testid="InputInstructions"],
.stApp [class*="InputInstructions"] {
    display: none !important;
}
/* Chat input (Debbie) — match the other dark inputs. Paint ONE surface (the
   outermost element) and force every inner BaseWeb layer transparent, so no
   second box shows through. */
.stApp [data-testid="stChatInput"] {
    background: rgba(2, 6, 23, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 0.6rem !important;
}
.stApp [data-testid="stChatInput"]:focus-within {
    border-color: rgba(129, 140, 248, 0.5) !important;
}
.stApp [data-testid="stChatInput"] div,
.stApp [data-testid="stChatInput"] [data-baseweb="textarea"],
.stApp [data-testid="stChatInput"] [data-baseweb="base-input"] {
    background: transparent !important;
    border: none !important;
}
.stApp [data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: #f1f5f9 !important;
}
.stApp [data-testid="stChatInput"] textarea::placeholder {
    color: #64748b !important;
}
.stApp [data-testid="stChatInput"] button {
    background: transparent !important;
    border: none !important;
    color: #c7d2fe !important;
}
.stApp [data-testid="stChatInput"] button:hover {
    background: rgba(99, 102, 241, 0.25) !important;
}
.stApp [data-testid="stChatInput"] button svg {
    fill: currentColor !important;
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
# Single-config state model
# =============================================================================
# The whole sketch lives in ONE nested dict (st.session_state["config"]) —
# mirror of the KARR AI web app's SketchConfig. Every mutation goes through
# set_config(), which pushes an undo snapshot and bumps the widget revision so
# every input re-seeds from the new config on the next run. Manual form edits
# and Debbie's AI edits share the same reducers (sketch_state.py) and the same
# undo/redo timeline — exactly like the web page's useUndoable + setConfig.

UNDO_LIMIT = 50  # matches use-undoable.ts DEFAULT_LIMIT

PLAN_VARIANTS = ("all", "passenger", "fire")
PLAN_VARIANT_LABELS = {"all": "All Lifts", "passenger": "Passenger Lifts", "fire": "Fire Lifts"}


def init_state() -> None:
    stt = st.session_state
    if "config" not in stt:
        stt["config"] = ss.make_default_config()
    stt.setdefault("hist_past", [])
    stt.setdefault("hist_future", [])
    stt.setdefault("rev", 0)
    stt.setdefault("ui_active_view", "plan")
    stt.setdefault("ui_active_core", 0)
    stt.setdefault("ui_plan_variant", "all")
    stt.setdefault("ui_section_source", "c0-b1-0")
    stt.setdefault("plan_image", None)
    stt.setdefault("plan_error", None)
    stt.setdefault("section_image", None)
    stt.setdefault("section_error", None)
    stt.setdefault("debbie_msgs", [])
    stt.setdefault("debbie_pending", None)
    stt.setdefault("debbie_hits", [])
    stt.setdefault("_autogen_rev", None)


def bump_rev() -> None:
    """Invalidate every widget key so inputs re-seed from the config."""
    st.session_state["rev"] += 1


def _wk(name: str) -> str:
    """Revision-stamped widget key."""
    return f"w{st.session_state['rev']}_{name}"


def cleanup_old_widget_keys() -> None:
    """Drop widget state from previous revisions (stale after a rev bump)."""
    rev_prefix = f"w{st.session_state['rev']}_"
    for k in list(st.session_state.keys()):
        if k.startswith("w") and "_" in k and not k.startswith(rev_prefix):
            head_part = k.split("_", 1)[0]
            if head_part[1:].isdigit():
                del st.session_state[k]


def set_config(next_cfg: dict) -> None:
    """Undoable config write (drop-in for the web's setConfig): push the prior
    value onto the undo stack, clear the redo stack, re-seed all widgets."""
    stt = st.session_state
    if next_cfg is stt["config"]:
        return
    stt["hist_past"].append(ss.deep_copy_config(stt["config"]))
    if len(stt["hist_past"]) > UNDO_LIMIT:
        stt["hist_past"].pop(0)
    stt["hist_future"] = []
    stt["config"] = next_cfg
    bump_rev()


def can_undo() -> bool:
    return len(st.session_state["hist_past"]) > 0


def can_redo() -> bool:
    return len(st.session_state["hist_future"]) > 0


def undo_config() -> None:
    stt = st.session_state
    if not stt["hist_past"]:
        return
    stt["hist_future"].insert(0, ss.deep_copy_config(stt["config"]))
    stt["config"] = stt["hist_past"].pop()
    bump_rev()


def redo_config() -> None:
    stt = st.session_state
    if not stt["hist_future"]:
        return
    stt["hist_past"].append(ss.deep_copy_config(stt["config"]))
    stt["config"] = stt["hist_future"].pop(0)
    bump_rev()


def _active_core_index() -> int:
    cfg = st.session_state["config"]
    return max(0, min(st.session_state["ui_active_core"], len(cfg["cores"]) - 1))


def _replace_lift(cfg: dict, ci: int, bank: str, idx: int, new_lift: dict) -> dict:
    """Swap one lift (recomputing that bank's separator defaults) — same helper
    the operation interpreter uses, so form edits stay identical to Debbie's."""
    return dops._replace_lift(cfg, ci, bank, idx, new_lift)


def _get_lift(cfg: dict, ci: int, bank: str, idx: int) -> dict:
    key = "bank1_lifts" if bank == "bank1" else "bank2_lifts"
    return cfg["cores"][ci][key][idx]


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
        "lift_id": lift_data.get("lift_id", ""),
        "lift_machine_type": machine_type,
        "finished_car_width": lift_data.get("width", 1900),
        "finished_car_depth": lift_data.get("depth", 1600),
        "door_width": door_width,
        "door_height": lift_data.get("door_height", 2100),
        # Split door-panel thicknesses (car = inner/cabin side, landing =
        # outer/wall side); fall back to the legacy single thickness when unset.
        "door_panel_thickness": lift_data.get("door_panel_thickness", 150),
        "car_door_thickness": lift_data.get(
            "car_door_thickness", lift_data.get("door_panel_thickness", 150)),
        "landing_door_thickness": lift_data.get(
            "landing_door_thickness", lift_data.get("door_panel_thickness", 150)),
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
    rail_l, rail_r = ss.lift_rails(lift_data)
    kwargs["rail_width_left"] = rail_l
    kwargs["rail_width_right"] = rail_r
    kwargs["door_gap"] = ss.lift_door_gap(lift_data)
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

    # Construct once (surfaces any genuine config error early).
    LiftConfig(**kwargs)

    shaft_width = lift_data.get("shaft_width")
    shaft_depth = lift_data.get("shaft_depth")
    if shaft_width is not None:
        kwargs["shaft_width_override"] = shaft_width
    if shaft_depth is not None:
        kwargs["shaft_depth_override"] = shaft_depth

    return LiftConfig(**kwargs)


# =============================================================================
# Widget helpers (revision-keyed; seeds come from the config)
# =============================================================================

def _num(key: str, label: str, *, seed, min_value=None, max_value=None, step=1,
         on_change=None, help=None, disabled=False):
    """Number input seeded once per revision from the config. A NaN (blank)
    seed renders an empty cell. Seeds are clamped into the widget's range so
    Streamlit never sees an out-of-range session_state value; the config keeps
    the true value (it is what gets drawn)."""
    wkey = _wk(key)
    if wkey not in st.session_state:
        if seed is None or ss.is_blank(seed):
            st.session_state[wkey] = None
        else:
            s = int(seed)
            if min_value is not None:
                s = max(min_value, s)
            if max_value is not None:
                s = min(max_value, s)
            st.session_state[wkey] = s
    kwargs = {"key": wkey, "step": step}
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


def _lift_write(ci: int, bank: str, idx: int, new_lift: dict) -> None:
    set_config(_replace_lift(st.session_state["config"], ci, bank, idx, new_lift))


def _lift_num_cb(ci: int, bank: str, idx: int, field: str, key: str,
                 reducer=None, clamp=None):
    """on_change for a per-lift number input. Routes the edit through the given
    pure reducer (sketch_state) so manual edits match Debbie's exactly. A blank
    (None) widget stores NaN — the web's blank-cell sentinel. If blank sibling
    cells make the linking math fail, just store the edited value raw. A key
    that no longer exists means a stale event from a previous widget revision
    — drop it."""
    wkey = _wk(key)

    def cb():
        if wkey not in st.session_state:
            return  # stale event from a previous widget revision
        raw = st.session_state[wkey]
        cfg = st.session_state["config"]
        lift = _get_lift(cfg, ci, bank, idx)
        if raw is None:
            _lift_write(ci, bank, idx, {**lift, field: float("nan")})
            return
        v = clamp(raw) if clamp else raw
        try:
            new_lift = reducer(lift, v) if reducer else {**lift, field: v}
        except TypeError:
            new_lift = {**lift, field: v}
        _lift_write(ci, bank, idx, new_lift)
    return cb


def _config_write(partial: dict) -> None:
    """Undoable write of global (non-core) config fields."""
    set_config({**st.session_state["config"], **partial})


def _core_write(ci: int, partial: dict) -> None:
    """Undoable write of the given core's fields, recomputing separator
    defaults when common_shaft flips (mirror of updateActiveCore)."""
    cfg = st.session_state["config"]
    cores = list(cfg["cores"])
    nxt = {**cores[ci], **partial}
    if "common_shaft" in partial and "separator_types_bank1" not in partial:
        nxt["separator_types_bank1"] = ss.compute_default_separator_types(
            nxt["bank1_lifts"], nxt["common_shaft"])
    if "common_shaft" in partial and "separator_types_bank2" not in partial:
        nxt["separator_types_bank2"] = ss.compute_default_separator_types(
            nxt["bank2_lifts"], nxt["common_shaft"])
    cores[ci] = nxt
    set_config({**cfg, "cores": cores})


def _set_bank_count(ci: int, bank: str, n: int) -> None:
    """Resize a bank to n lifts (mirror of setNumBank1/2)."""
    cfg = st.session_state["config"]
    cores = list(cfg["cores"])
    core = cores[ci]
    key = "bank1_lifts" if bank == "bank1" else "bank2_lifts"
    sep_key = "separator_types_bank1" if bank == "bank1" else "separator_types_bank2"
    lifts = list(core[key])
    while len(lifts) < n:
        lifts.append(ss.make_default_lift("passenger", cfg["machine_type"]))
    lifts = lifts[:n]
    cores[ci] = {
        **core,
        key: lifts,
        sep_key: ss.compute_default_separator_types(lifts, core["common_shaft"]),
    }
    set_config(ss.fill_blank_lift_ids({**cfg, "cores": cores}))


def _parse_cabin_size(text: str):
    """Fuzzy-parse a fire cabin "W x D" string (any separator/format) into
    (width, depth). Port of parseCabinSize()."""
    nums = re.findall(r"\d+(?:\.\d+)?", text or "")
    if len(nums) < 2:
        return None
    w, d = float(nums[0]), float(nums[1])
    if w <= 0 or d <= 0:
        return None
    return int(w), int(d)


# =============================================================================
# Per-lift config form — config-driven port of the web LiftConfigForm
# =============================================================================

def _door_thickness_inputs(num, L: dict) -> None:
    """Render the two door-panel thickness inputs (shared by the centre and
    telescopic branches). Car door = inner (cabin side); landing door = outer
    (shaft-wall side). Width is shared; only thickness is split. Seeds resolve
    the legacy single thickness so older lifts show the right value."""
    tt1, tt2 = st.columns(2)
    with tt1:
        num("car_door_thickness", "Car Door Thickness (mm)", min_value=50,
            max_value=300, step=10, reducer=ss.apply_car_door_thickness,
            seed=ss.lift_car_door_thickness(L),
            help="Thickness of the car door (inner panel touching the cabin).")
    with tt2:
        num("landing_door_thickness", "Landing Door Thickness (mm)", min_value=50,
            max_value=300, step=10, reducer=ss.apply_landing_door_thickness,
            seed=ss.lift_landing_door_thickness(L),
            help="Thickness of the landing door (outer panel at the shaft wall).")


def render_lift_form(ci: int, bank: str, idx: int, machine_type: str,
                     show_capacity: bool) -> None:
    cfg = st.session_state["config"]
    L = _get_lift(cfg, ci, bank, idx)
    prefix = f"c{ci}_{bank}_{idx}"
    is_fire = L["type"] == "fire"
    mrl_style = ss.lift_is_side_cw(L, machine_type)

    def num(field, label, *, reducer=None, clamp=None, seed=None, **kw):
        key = f"{prefix}_{field}"
        return _num(key, label,
                    seed=seed if seed is not None else L.get(field),
                    on_change=_lift_num_cb(ci, bank, idx, field, key,
                                           reducer=reducer, clamp=clamp),
                    **kw)

    lid = (L.get("lift_id") or "").strip()
    title = f"Lift {idx + 1} · {'Fire/Service' if is_fire else 'Passenger'}"
    if lid:
        title += f" · {lid}"

    with st.expander(title, expanded=(idx == 0 and bank == "bank1")):

        # Copy this lift's dims into the section view (and switch to it).
        def _cb_copy_to_section(ci=ci, bank=bank, idx=idx):
            c = st.session_state["config"]
            lift = _get_lift(c, ci, bank, idx)
            wall = c["cores"][ci]["wall_thickness_mm"]
            set_config({**c, "section": ss.copy_lift_values_to_section(
                c["section"], lift, wall)})
            st.session_state["ui_section_source"] = f"c{ci}-b{'1' if bank == 'bank1' else '2'}-{idx}"
            st.session_state["ui_active_view"] = "section"
            st.session_state["section_image"] = None

        st.button("Copy to Section", key=_wk(f"{prefix}_copy_sec"),
                  on_click=_cb_copy_to_section)

        # Lift ID (designation shown in the brief-spec table)
        idkey = _wk(f"{prefix}_lift_id")
        if idkey not in st.session_state:
            st.session_state[idkey] = L.get("lift_id", "")

        def _cb_lift_id():
            if idkey not in st.session_state:
                return  # stale event from a previous widget revision
            c = st.session_state["config"]
            lift = _get_lift(c, ci, bank, idx)
            _lift_write(ci, bank, idx, {**lift, "lift_id": st.session_state[idkey]})

        st.text_input("Lift ID", key=idkey, placeholder="e.g. PL-01",
                      on_change=_cb_lift_id)

        # Lift Type — rebuilds the lift at the new type's defaults, carrying the
        # ID across (PL ⇄ FL/SL prefix swap when it was the canonical default).
        tkey = _wk(f"{prefix}_type")
        if tkey not in st.session_state:
            st.session_state[tkey] = L["type"]

        def _cb_type():
            if tkey not in st.session_state:
                return  # stale event from a previous widget revision
            new_type = st.session_state[tkey]
            c = st.session_state["config"]
            lift = _get_lift(c, ci, bank, idx)
            if lift["type"] == new_type:
                return
            rebuilt = ss.make_default_lift(new_type, c["machine_type"])
            rebuilt["lift_id"] = ss.carry_lift_id(lift, new_type)
            _lift_write(ci, bank, idx, rebuilt)

        st.selectbox(
            "Lift Type", options=["passenger", "fire"],
            format_func=lambda x: "Fire/Service" if x == "fire" else "Passenger",
            key=tkey, on_change=_cb_type,
        )

        # Double Car Entrance — doors on both front and rear faces (any lift
        # type). Turning it on moves an MRA lift's counterweight to the side (a
        # through-car has no rear wall for it).
        dkey = _wk(f"{prefix}_double")
        if dkey not in st.session_state:
            st.session_state[dkey] = bool(L.get("double_entrance"))

        def _cb_double():
            if dkey not in st.session_state:
                return  # stale event from a previous widget revision
            c = st.session_state["config"]
            lift = _get_lift(c, ci, bank, idx)
            try:
                _lift_write(ci, bank, idx,
                            ss.apply_double_entrance(lift, st.session_state[dkey], machine_type))
            except TypeError:
                _lift_write(ci, bank, idx,
                            {**lift, "double_entrance": st.session_state[dkey]})

        st.checkbox("Double Car Entrance", key=dkey, on_change=_cb_double)

        # Shaft Dimensions
        st.markdown("**Shaft Dimensions**")
        if mrl_style:
            width_formula = ("Min = CWT Bracket Spacing + Unfinished Car Width "
                             "(finished + 50) + Car Bracket Spacing")
            if is_fire:
                width_formula += ". Fire lifts: at least 2700, or 2450 with telescopic doors."
        else:
            width_formula = ("Min = Left Car Bracket Spacing + Unfinished Car Width "
                             "(finished + 50) + Right Car Bracket Spacing")
        if L.get("double_entrance"):
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
            num("shaft_width", "Shaft Width (mm)", step=10, help=width_formula,
                reducer=lambda lf, v: ss.apply_shaft_width(lf, v, machine_type))
        with c2:
            num("shaft_depth", "Shaft Depth (mm)", step=10, help=depth_formula,
                disabled=bool(L.get("double_entrance")),
                reducer=lambda lf, v: ss.apply_shaft_depth(lf, v, machine_type))

        # Swap bracket sides — MRL-style side-bracket lifts only.
        if mrl_style:
            swkey = _wk(f"{prefix}_swap")
            if swkey not in st.session_state:
                st.session_state[swkey] = bool(L.get("swap_brackets", False))

            def _cb_swap():
                if swkey not in st.session_state:
                    return  # stale event from a previous widget revision
                c = st.session_state["config"]
                lift = _get_lift(c, ci, bank, idx)
                _lift_write(ci, bank, idx,
                            {**lift, "swap_brackets": st.session_state[swkey]})

            st.checkbox("Swap brackets", key=swkey, on_change=_cb_swap,
                        help="Swap positions of the CWT bracket and car bracket with each other.")

        # Capacity (conditional)
        if show_capacity:
            cap_seed = L.get("capacity")
            if cap_seed is None:
                cap_seed = 1600 if is_fire else 1350
            num("capacity", "Capacity (KG)", min_value=100, max_value=10000,
                step=50, seed=cap_seed)

        # Car Dimensions
        st.markdown("**Car Dimensions**")
        if is_fire:
            # Free-entry cabin combobox: pick a preset or type any "W x D" size
            # (fuzzy-parsed). No size is enforced — any value is drawable.
            ckey = _wk(f"{prefix}_cabin")
            if ckey not in st.session_state:
                w0, d0 = L.get("width"), L.get("depth")
                st.session_state[ckey] = (
                    f"{int(w0)} x {int(d0)}"
                    if w0 is not None and d0 is not None
                    and not ss.is_blank(w0) and not ss.is_blank(d0) else ""
                )

            def _cb_cabin():
                if ckey not in st.session_state:
                    return  # stale event from a previous widget revision
                parsed = _parse_cabin_size(st.session_state[ckey])
                if not parsed:
                    bump_rev()  # reset the text to the current cabin size
                    return
                c = st.session_state["config"]
                lift = _get_lift(c, ci, bank, idx)
                try:
                    _lift_write(ci, bank, idx,
                                ss.apply_fire_cabin(lift, parsed[0], parsed[1], machine_type))
                except TypeError:
                    _lift_write(ci, bank, idx,
                                {**lift, "width": parsed[0], "depth": parsed[1]})

            presets = ", ".join(f"{w} x {d}" for w, d in FIRE_LIFT_CABIN_SIZES)
            st.text_input(
                "Cabin Size (W x D)", key=ckey, placeholder="e.g. 1400 x 2400",
                on_change=_cb_cabin,
                help=f"Standard sizes: {presets}. Any custom \"W x D\" is accepted.",
            )
        else:
            cc1, cc2 = st.columns(2)
            with cc1:
                num("width", "Car Width (mm)", step=10,
                    reducer=lambda lf, v: ss.apply_car_width(lf, v, machine_type))
            with cc2:
                num("depth", "Car Depth (mm)", step=10)

        # Shaft Spacing — always editable, zero-sum, max(0, .) only
        st.markdown("**Shaft Spacing**")
        if mrl_style:
            bc1, bc2 = st.columns(2)
            with bc1:
                num("cw_bracket_width", "CWT Bracket Spacing (mm)", step=25,
                    help="Car bracket auto-adjusts.",
                    reducer=ss.apply_cw_bracket,
                    seed=L.get("cw_bracket_width") if L.get("cw_bracket_width") is not None
                    else ss.MRL_CW_BRACKET_MIN)
            with bc2:
                num("car_bracket_width", "Car Bracket Spacing (mm)", step=25,
                    help="CWT bracket auto-adjusts.",
                    reducer=ss.apply_car_bracket,
                    seed=L.get("car_bracket_width") if L.get("car_bracket_width") is not None
                    else ss.MRL_CAR_BRACKET_MIN)
        else:
            st.caption("Width")
            wc1, wc2 = st.columns(2)
            with wc1:
                num("mra_left_bracket", "Left Car Bracket Spacing (mm)", step=25,
                    reducer=ss.apply_mra_left_bracket,
                    seed=L.get("mra_left_bracket") if L.get("mra_left_bracket") is not None
                    else ss.MRA_CAR_BRACKET_MIN)
            with wc2:
                num("mra_right_bracket", "Right Car Bracket Spacing (mm)", step=25,
                    reducer=ss.apply_mra_right_bracket,
                    seed=L.get("mra_right_bracket") if L.get("mra_right_bracket") is not None
                    else ss.MRA_CAR_BRACKET_MIN)
            st.caption("Depth")
            dc1, dc2 = st.columns(2)
            with dc1:
                num("mra_cw_bracket_depth", "CWT Bracket Spacing (mm)", step=25,
                    reducer=ss.apply_mra_cw_depth,
                    seed=L.get("mra_cw_bracket_depth") if L.get("mra_cw_bracket_depth") is not None
                    else ss.MRA_CW_BRACKET_DEPTH_MIN)
            with dc2:
                num("mra_cw_gap", "CWT Gap (mm)", step=25,
                    reducer=ss.apply_mra_cw_gap,
                    seed=L.get("mra_cw_gap") if L.get("mra_cw_gap") is not None
                    else ss.MRA_CW_GAP_MIN)
            num("mra_cw_wall_gap", "CWT Wall Gap (mm)", step=25,
                help="Space between rear wall and CWT box. CWT gap auto-adjusts.",
                reducer=ss.apply_mra_cw_wall_gap,
                seed=L.get("mra_cw_wall_gap") if L.get("mra_cw_wall_gap") is not None
                else ss.MRA_CW_WALL_GAP_MIN)

        # Car guide rails (decoupled from brackets; arrow shows bracket + rail)
        rc1, rc2 = st.columns(2)
        with rc1:
            num("rail_width_left", "Left Rail Spacing (mm)", step=5,
                help="Bracket on this side auto-adjusts; arrow shows bracket + rail.",
                reducer=lambda lf, v: ss.apply_rail_left(lf, v, machine_type),
                seed=L.get("rail_width_left") if L.get("rail_width_left") is not None
                else ss.RAIL_WIDTH_DEFAULT)
        with rc2:
            num("rail_width_right", "Right Rail Spacing (mm)", step=5,
                help="Bracket on this side auto-adjusts.",
                reducer=lambda lf, v: ss.apply_rail_right(lf, v, machine_type),
                seed=L.get("rail_width_right") if L.get("rail_width_right") is not None
                else ss.RAIL_WIDTH_DEFAULT)

        # CW box visual dimensions (free inputs; the box floats inside its zone)
        if mrl_style:
            cwb1, cwb2 = st.columns(2)
            with cwb1:
                num("cw_box_width", "CWT Box Width (mm)", step=25,
                    clamp=lambda v: max(0, v),
                    seed=L.get("cw_box_width") if L.get("cw_box_width") is not None
                    else ss.CW_BOX_WIDTH_DEFAULT)
            with cwb2:
                num("cw_box_depth", "CWT Box Depth (mm)", step=25,
                    clamp=lambda v: max(0, v),
                    seed=L.get("cw_box_depth") if L.get("cw_box_depth") is not None
                    else ss.CW_BOX_DEPTH_DEFAULT)
        else:
            num("mra_cw_box_width", "CWT Box Spacing (mm)", step=25,
                clamp=lambda v: max(0, v),
                help="Width of the rear CWT box (depth = CWT Bracket Spacing).",
                seed=L.get("mra_cw_box_width") if L.get("mra_cw_box_width") is not None
                else ss.MRA_CW_BOX_WIDTH_DEFAULT)

        # Door Settings
        st.markdown("**Door Settings**")
        dwc1, dwc2 = st.columns(2)
        with dwc1:
            num("door_width", "Door Width (mm)", min_value=700, max_value=2000,
                step=50, reducer=ss.apply_door_width)
        with dwc2:
            num("door_height", "Door Height (mm)", min_value=1500, max_value=3500, step=50)

        num("door_gap", "Running Clearance (mm)", min_value=0, max_value=500, step=5,
            help="Clearance between the landing and car door.",
            reducer=ss.apply_door_gap,
            seed=L.get("door_gap") if L.get("door_gap") is not None else ss.DOOR_GAP)

        # Fire lift: door opening type
        if is_fire:
            otkey = _wk(f"{prefix}_door_opening_type")
            if otkey not in st.session_state:
                st.session_state[otkey] = L["door_opening_type"]

            def _cb_door_type():
                if otkey not in st.session_state:
                    return  # stale event from a previous widget revision
                c = st.session_state["config"]
                lift = _get_lift(c, ci, bank, idx)
                new_type = st.session_state[otkey]
                try:
                    _lift_write(ci, bank, idx, ss.apply_door_type(lift, new_type))
                except TypeError:
                    _lift_write(ci, bank, idx, {**lift, "door_opening_type": new_type})

            st.selectbox(
                "Door Opening Type", options=["centre", "telescopic"],
                format_func=lambda x: "Telescopic Opening" if x == "telescopic" else "Centre Opening",
                key=otkey, on_change=_cb_door_type,
            )

        if L["door_opening_type"] == "telescopic":
            tele_left_seed = L.get("telescopic_left_ext")
            if tele_left_seed is None and L.get("door_width") is not None \
                    and not ss.is_blank(L.get("door_width")):
                tele_left_seed = int(0.5 * L["door_width"]) + ss.TELESCOPIC_LEFT_EXT_EXTRA
            tc1, tc2 = st.columns(2)
            with tc1:
                num("telescopic_left_ext", "Left Extension (mm)", min_value=50,
                    max_value=2000, step=25, seed=tele_left_seed)
            with tc2:
                num("telescopic_right_ext", "Right Extension (mm)", min_value=50,
                    max_value=1000, step=25,
                    seed=L.get("telescopic_right_ext") if L.get("telescopic_right_ext") is not None
                    else ss.TELESCOPIC_RIGHT_EXT)
            _door_thickness_inputs(num, L)
        else:
            panel_seed = L.get("door_panel_length")
            if panel_seed is None and L.get("door_width") is not None \
                    and L.get("shaft_width") is not None \
                    and not ss.is_blank(L.get("door_width")) \
                    and not ss.is_blank(L.get("shaft_width")):
                panel_seed = min(2 * L["door_width"] + 2 * ss.DEFAULT_DOOR_EXTENSION,
                                 L["shaft_width"])
            # No min/max on the widget so an auto-grown value past 6000
            # doesn't raise; user edits are clamped to [500, 6000].
            num("door_panel_length", "Door Panel Length (mm)", step=50,
                clamp=lambda v: max(500, min(6000, v)), seed=panel_seed)
            _door_thickness_inputs(num, L)

        sc1, sc2 = st.columns(2)
        with sc1:
            num("structural_opening_width", "Structural Opening W (mm)",
                min_value=800, max_value=3000, step=50)
        with sc2:
            num("structural_opening_height", "Structural Opening H (mm)",
                min_value=1500, max_value=4000, step=50)

        # Door horizontal offset from cabin centre (X axis). No upper bound —
        # the user owns visual correctness, even if parts overlap.
        oc1, oc2 = st.columns(2)
        with oc1:
            num("door_offset_mm", "Door Centre Offset (mm)", min_value=0, step=25,
                help="Shift the door (opening, jambs, panels, returns) left/right "
                     "from the cabin centre. Overlap is allowed.")
        with oc2:
            odkey = _wk(f"{prefix}_door_offset_direction")
            if odkey not in st.session_state:
                st.session_state[odkey] = L.get("door_offset_direction", "right")

            def _cb_offset_dir():
                if odkey not in st.session_state:
                    return  # stale event from a previous widget revision
                c = st.session_state["config"]
                lift = _get_lift(c, ci, bank, idx)
                _lift_write(ci, bank, idx,
                            {**lift, "door_offset_direction": st.session_state[odkey]})

            st.selectbox(
                "Offset Direction", options=["left", "right"],
                format_func=lambda x: x.capitalize(),
                key=odkey, on_change=_cb_offset_dir,
            )


# =============================================================================
# Section config form — config-driven port of the web SectionConfigForm
# =============================================================================

def render_section_form(machine_type: str) -> None:
    cfg = st.session_state["config"]
    S = cfg["section"]

    def num(field, label, *, seed=None, **kw):
        key = f"section_{field}"

        wkey = _wk(key)

        def cb():
            if wkey not in st.session_state:
                return  # stale event from a previous widget revision
            raw = st.session_state[wkey]
            c = st.session_state["config"]
            value = float("nan") if raw is None else raw
            set_config({**c, "section": {**c["section"], field: value}})

        return _num(key, label,
                    seed=seed if seed is not None else S.get(field),
                    on_change=cb, **kw)

    c1, c2 = st.columns(2)
    with c1:
        num("shaft_depth", "Shaft Depth (mm)", step=10)
    with c2:
        num("wall_thickness", "Wall Thickness (mm)", min_value=100, max_value=500, step=25)

    c3, c4 = st.columns(2)
    with c3:
        num("pit_slab", "Pit Slab (mm)", min_value=100, max_value=500, step=25)
    with c4:
        num("pit_depth", "Pit Depth (mm)", min_value=500, max_value=10000, step=50)

    c5, c6 = st.columns(2)
    with c5:
        num("travel_height", "Travel Height (mm)", min_value=5000, max_value=200000, step=1000)
    with c6:
        num("overhead_clearance", "Headroom (mm)", min_value=2000, max_value=10000, step=100)

    c7, c8 = st.columns(2)
    with c7:
        num("door_height", "Door Opening Height (mm)", min_value=1500, max_value=3500, step=50)
    with c8:
        num("structural_opening_height", "Structural Opening Height (mm)",
            min_value=1500, max_value=4000, step=50)

    if machine_type == "mra":
        c9, _ = st.columns(2)
        with c9:
            num("machine_room_height", "Machine Room Height (mm)",
                min_value=2000, max_value=6000, step=100,
                seed=S.get("machine_room_height") if S.get("machine_room_height") is not None
                else 3000)


# =============================================================================
# Section source lift — port of resolveSectionLift / selectSectionLift
# =============================================================================

SECTION_KEY_RE = re.compile(r"^c(\d+)-b([12])-(\d+)$")


def resolve_section_lift(cfg: dict):
    """Resolve the section's selected lift (and its core) from the source key;
    fall back to the first passenger across cores, else the very first lift.
    Returns (lift, core)."""
    m = SECTION_KEY_RE.match(st.session_state.get("ui_section_source") or "")
    if m:
        ci, b, i = int(m.group(1)), m.group(2), int(m.group(3))
        if ci < len(cfg["cores"]):
            core = cfg["cores"][ci]
            lifts = core["bank1_lifts"] if b == "1" else core["bank2_lifts"]
            if i < len(lifts):
                return lifts[i], core
    for core in cfg["cores"]:
        for lift in core["bank1_lifts"]:
            if lift["type"] == "passenger":
                return lift, core
    return cfg["cores"][0]["bank1_lifts"][0], cfg["cores"][0]


# =============================================================================
# PNG generation — port of the KARR AI /api/sketches preview endpoints
# =============================================================================

def _core_has_both_types(core: dict) -> bool:
    core_lifts = [*core["bank1_lifts"], *core["bank2_lifts"]]
    return (any(lf["type"] == "passenger" for lf in core_lifts)
            and any(lf["type"] == "fire" for lf in core_lifts))


def _plan_blank_reason(core: dict):
    """Blank-cell (NaN sentinel) check for one core's plan. Returns the error
    message to show, or None when every needed cell is filled."""
    lifts_to_check = ([*core["bank1_lifts"], *core["bank2_lifts"]]
                      if core["arrangement"] == "Facing" else core["bank1_lifts"])
    blank = any(ss.has_blank_number(lf) for lf in lifts_to_check)
    if ss.is_blank(core["wall_thickness_mm"]):
        blank = True
    if core["arrangement"] == "Facing" and ss.is_blank(core["lobby_width_mm"]):
        blank = True
    return ("Some input cells are empty. Fill in all fields before generating."
            if blank else None)


def _render_plan_png(cfg: dict, ci: int, lift_filter: str = "all") -> bytes:
    """Render one core's plan PNG (pure — no session state). Port of the
    /preview/plan endpoint. Raises ValueError on config/filter errors."""
    core = cfg["cores"][ci]
    multi_core = len(cfg["cores"]) > 1
    mt = cfg["machine_type"]
    wall = core["wall_thickness_mm"]
    bank1_configs = [build_lift_config(lf, mt, wall) for lf in core["bank1_lifts"]]
    bank2_configs = ([build_lift_config(lf, mt, wall) for lf in core["bank2_lifts"]]
                     if core["arrangement"] == "Facing" else [])

    sep1 = core["separator_types_bank1"] or None
    sep2 = core["separator_types_bank2"] or None

    # Optional single-type filter (split-plan carousel). The
    # subset re-derives its own separators (None); collapse to inline when it
    # lives entirely in bank 2.
    if lift_filter in ("passenger", "fire"):
        bank1_configs = [c for c in bank1_configs if c.lift_type == lift_filter]
        bank2_configs = [c for c in bank2_configs if c.lift_type == lift_filter]
        sep1 = sep2 = None
        if not bank1_configs:
            bank1_configs, bank2_configs = bank2_configs, []
        if not bank1_configs:
            raise ValueError(f"No {lift_filter} lift to preview")

    if core["arrangement"] == "Facing" and bank2_configs:
        sketch = LiftShaftSketch(
            lifts=bank1_configs,
            lifts_bank2=bank2_configs,
            lobby_width=core["lobby_width_mm"],
            is_common_shaft=core["common_shaft"],
            wall_thickness=wall,
            separator_types_bank1=sep1,
            separator_types_bank2=sep2,
        )
    else:
        sketch = LiftShaftSketch(
            lifts=bank1_configs,
            is_common_shaft=core["common_shaft"],
            wall_thickness=wall,
            separator_types_bank1=sep1,
        )

    brief_title = "BRIEF SPECIFICATION"
    if multi_core:
        brief_title += f" — {core['name']}"

    font_max = ss.plan_dimension_font_max(
        core["arrangement"], len(core["bank1_lifts"]), len(core["bank2_lifts"]))

    return sketch.to_bytes(
        show_hatching=cfg["show_hatching"],
        show_dimensions=cfg["show_dimensions"],
        show_centerlines=cfg["show_centerlines"],
        show_brackets=cfg["show_brackets"],
        show_capacity=cfg["show_capacity"],
        show_accessibility=cfg["show_accessibility"],
        show_lift_doors=cfg["show_lift_doors"],
        show_lift_id=cfg["show_lift_id"],
        show_brief_spec=cfg["show_brief_spec"],
        brief_spec_title=brief_title,
        font_scale=ss.clamp_dimension_font_scale(cfg["dimension_font_scale"], font_max),
    )


def generate_plan(plan_filter: str = None) -> None:
    """Generate the active core's plan PNG into session state. Port of the
    web handleGenerate (plan branch)."""
    cfg = st.session_state["config"]
    ci = _active_core_index()
    core = cfg["cores"][ci]
    variant = plan_filter or st.session_state["ui_plan_variant"]

    blank = _plan_blank_reason(core)
    if blank:
        st.session_state["plan_error"] = blank
        st.session_state["plan_image"] = None
        return

    # Only filter when the split option + a mixed core make it meaningful.
    lift_filter = (variant if (cfg["split_lift_types"] and _core_has_both_types(core))
                   else "all")
    try:
        st.session_state["plan_image"] = _render_plan_png(cfg, ci, lift_filter)
        st.session_state["plan_error"] = None
    except ValueError as e:
        st.session_state["plan_error"] = str(e)
        st.session_state["plan_image"] = None
    except Exception as e:  # noqa: BLE001 — surface unexpected errors in the UI
        st.session_state["plan_error"] = f"Unexpected error: {e}"
        st.session_state["plan_image"] = None
    st.session_state["_autogen_rev"] = st.session_state["rev"]


def _render_section_png(cfg: dict) -> bytes:
    """Render the section PNG for the selected source lift (pure — no session
    writes). Port of the /preview/section endpoint. Raises ValueError."""
    section = cfg["section"]
    pick_lift, pick_core = resolve_section_lift(cfg)
    multi_core = len(cfg["cores"]) > 1

    mt = cfg["machine_type"]
    lift_config = build_lift_config(pick_lift, mt, section["wall_thickness"])

    # The section form's Shaft Depth always overrides the lift's depth.
    lift_config.shaft_depth_override = section["shaft_depth"]

    section_kwargs = {
        "pit_slab": section["pit_slab"],
        "pit_depth": section["pit_depth"],
        "overhead_clearance": section["overhead_clearance"],
        "travel_height": section["travel_height"],
        "door_height": section["door_height"],
        "structural_opening_height": section["structural_opening_height"],
    }
    if mt == "mra" and section.get("machine_room_height") is not None:
        section_kwargs["machine_room_height"] = section["machine_room_height"]

    section_sketch = LiftSectionSketch(
        lift_config=lift_config,
        section_config=SectionConfig(**section_kwargs),
    )

    brief_title = "BRIEF SPECIFICATION"
    if multi_core:
        brief_title += f" — {pick_core['name']}"

    return section_sketch.to_bytes(
        show_hatching=cfg["section_show_hatching"],
        show_dimensions=cfg["section_show_dimensions"],
        show_break_lines=cfg["section_show_break_lines"],
        show_mrl_machine=cfg["section_show_machine"],
        show_brief_spec=cfg["show_brief_spec"],
        brief_spec_title=brief_title,
        font_scale=ss.clamp_dimension_font_scale(
            cfg["section_dimension_font_scale"], ss.SECTION_DIM_FONT_MAX),
    )


def generate_section() -> None:
    """Generate the section PNG into session state. Port of the web
    handleGenerate (section branch)."""
    cfg = st.session_state["config"]
    pick_lift, _ = resolve_section_lift(cfg)

    if ss.has_blank_number(pick_lift) or ss.has_blank_number(cfg["section"]):
        st.session_state["section_error"] = (
            "Some input cells are empty. Fill in all fields before generating.")
        st.session_state["section_image"] = None
        return

    try:
        st.session_state["section_image"] = _render_section_png(cfg)
        st.session_state["section_error"] = None
    except ValueError as e:
        st.session_state["section_error"] = str(e)
        st.session_state["section_image"] = None
    except Exception as e:  # noqa: BLE001
        st.session_state["section_error"] = f"Unexpected error: {e}"
        st.session_state["section_image"] = None
    st.session_state["_autogen_rev"] = st.session_state["rev"]


def regenerate_active_view() -> None:
    """Re-render the current view's preview (after Debbie edits / undo / redo),
    mirroring the web's debbieTick effect."""
    if st.session_state["ui_active_view"] == "plan":
        generate_plan()
    else:
        generate_section()


# =============================================================================
# Debbie — AI sketch-editing assistant (port of DebbiePanel + use-debbie)
# =============================================================================

DEBBIE_INTRO = (
    "Hi, I'm Debbie. How would you like to edit the sketch? — e.g. \"centre the doors "
    "for PL-02\" or \"set the pit depth to 1500\". "
)

DEBBIE_RATE_LIMIT_PER_MIN = 30


def _debbie_rate_limited() -> bool:
    now = time.monotonic()
    hits = [t for t in st.session_state["debbie_hits"] if now - t <= 60.0]
    st.session_state["debbie_hits"] = hits
    if len(hits) >= DEBBIE_RATE_LIMIT_PER_MIN:
        return True
    hits.append(now)
    return False


def debbie_send(text: str) -> None:
    """One Debbie turn: call the model, validate + apply returned operations
    through the shared interpreter, re-render the preview. Port of
    use-debbie.ts send()."""
    trimmed = (text or "").strip()
    if not trimmed:
        return

    msgs = st.session_state["debbie_msgs"]
    msgs.append({"role": "user", "content": trimmed})
    st.session_state["debbie_pending"] = None

    if _debbie_rate_limited():
        msgs.append({"role": "assistant",
                     "content": "Too many requests — give Debbie a moment."})
        return

    cfg = st.session_state["config"]
    ci = _active_core_index()
    result = debbie_agent.run_debbie_turn(
        messages=msgs,
        config=cfg,
        active_view=st.session_state["ui_active_view"],
        active_core=cfg["cores"][ci]["name"],
    )

    reply = (result.get("assistant_text") or "").strip()
    operations = result.get("operations") or []

    if operations:
        new_cfg, op_results = dops.apply_operations(cfg, operations, active_core=ci)
        applied = [r for r in op_results if r["status"] == "applied"]
        rejected = [r for r in op_results if r["status"] == "rejected"]
        warnings = "\n".join(f"⚠️ {r['detail']}" for r in rejected)

        if applied:
            # Something changed — apply it (undoable, shared history with the
            # manual form), re-render, keep the model's summary, and append any
            # partial rejections as warnings.
            set_config(new_cfg)
            regenerate_active_view()
            if warnings:
                reply += ("\n\n" if reply else "") + warnings
        elif rejected:
            # Nothing applied — the model's optimistic summary would contradict
            # reality, so replace it with the actual reasons.
            reply = "I couldn't make that change:\n" + warnings

    if result.get("pending_clarification"):
        st.session_state["debbie_pending"] = result["pending_clarification"]

    msgs.append({"role": "assistant", "content": reply or "Done."})


def render_debbie_panel() -> None:
    """Debbie chat UI (chat clears on reload — ephemeral by design)."""
    with st.expander("✨ Debbie — AI sketch assistant", expanded=False):
        if not debbie_agent.is_configured():
            st.info("Debbie needs an OpenAI key. Set OPENAI_API_KEY in "
                    ".streamlit/secrets.toml (or the environment) to enable her.")
            return

        with st.container():
            st.markdown(f"*{DEBBIE_INTRO}*")
            for m in st.session_state["debbie_msgs"]:
                with st.chat_message("user" if m["role"] == "user" else "assistant"):
                    st.markdown(m["content"])

        # Clarification quick-replies
        pending = st.session_state.get("debbie_pending")
        if pending and pending.get("options"):
            opt_cols = st.columns(min(4, len(pending["options"])))
            for i, opt in enumerate(pending["options"][:8]):
                with opt_cols[i % len(opt_cols)]:
                    if st.button(opt, key=_wk(f"debbie_opt_{i}")):
                        with st.spinner("Debbie is thinking…"):
                            debbie_send(opt)
                        st.rerun()

        # Native chat bar (self-clearing, submits on Enter) — one clean control
        # instead of a nested form + text input + Send button.
        prompt = st.chat_input("Tell Debbie what to change…", key=_wk("debbie_chat"))
        st.caption("Chat clears on reload.")

        if prompt and prompt.strip():
            with st.spinner("Debbie is thinking…"):
                debbie_send(prompt)
            st.rerun()

GATE_COOKIE_NAME = "debbie_gate"
GATE_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def _gate_token() -> str | None:
    """Stable auth token: HMAC of the gate password (never the password
    itself). Rotating GATE_PASSWORD invalidates every issued cookie."""
    pw = _gate_password()
    if not pw:
        return None
    return hmac.new(pw.encode(), b"drawing-debbie-gate-v1", hashlib.sha256).hexdigest()


def _cookie_authenticated() -> bool:
    """True when the browser presented a valid gate cookie (set on a previous
    successful login), so reloads skip the password form."""
    token = _gate_token()
    if not token:
        return False
    try:
        presented = st.context.cookies.get(GATE_COOKIE_NAME) or ""
        return hmac.compare_digest(presented, token)
    except Exception:
        return False


def _issue_gate_cookie() -> None:
    """Persist the auth across reloads. document.cookie must run from a real
    page (st.html does not execute scripts), so serve a tiny script file via
    st.iframe — it is hosted on the app's own origin, so the cookie lands on
    the app itself. Best-effort: a failure just means the form shows again."""
    token = _gate_token()
    if not token:
        return
    html = (f"<script>document.cookie = '{GATE_COOKIE_NAME}={token}; "
            f"max-age={GATE_COOKIE_MAX_AGE}; path=/; SameSite=Lax';</script>")
    try:
        path = Path(tempfile.gettempdir()) / f"debbie_gate_{token[:12]}.html"
        path.write_text(html, encoding="utf-8")
        st.iframe(path, height=1)
    except Exception:
        pass


def require_password() -> bool:
    """Render the gate UI if needed. Returns True when authenticated.

    Mirrors the Code Charlie gate: full-screen dark/indigo splash with the
    Debbie logo (responsive — sized off viewport height/width) and a password
    form. When False, the caller should st.stop() so nothing else renders.

    A valid gate cookie (issued after a successful login) skips the form on
    later visits/reloads for 30 days.
    """
    if st.session_state.get("authenticated"):
        # Re-issue the cookie once per session so logins stay sticky across
        # reloads (st.rerun() after submit skips any script emitted there).
        if not st.session_state.get("_gate_cookie_sent"):
            if not _cookie_authenticated():
                _issue_gate_cookie()
            st.session_state["_gate_cookie_sent"] = True
        return True

    if _cookie_authenticated():
        st.session_state["authenticated"] = True
        st.session_state["_gate_cookie_sent"] = True
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


# =============================================================================
# Sidebar widgets bound to the config
# =============================================================================

def _bool_option(field: str, label: str) -> None:
    """Checkbox bound to a top-level boolean config field (undoable)."""
    k = _wk(f"opt_{field}")
    if k not in st.session_state:
        st.session_state[k] = bool(st.session_state["config"][field])

    def cb():
        if k not in st.session_state:
            return  # stale event from a previous widget revision
        _config_write({field: st.session_state[k]})

    st.checkbox(label, key=k, on_change=cb)


def _dim_font_slider(max_pct: int, config_field: str) -> None:
    """Percent slider bound to a font-scale config field (stored as a float).
    The upper limit adapts to the layout so over-scaling that overlaps labels
    is simply not selectable."""
    cfg = st.session_state["config"]
    k = _wk(f"font_{config_field}")
    if k not in st.session_state:
        scale = ss.clamp_dimension_font_scale(cfg[config_field], max_pct / 100)
        pct = int(round(scale * 100 / 10) * 10)
        st.session_state[k] = min(max_pct, max(50, pct))
    else:
        st.session_state[k] = min(st.session_state[k], max_pct)

    def cb():
        if k not in st.session_state:
            return  # stale event from a previous widget revision
        _config_write({config_field: st.session_state[k] / 100})

    st.slider("Font Size", min_value=50, max_value=max_pct, step=10, key=k,
              on_change=cb,
              help="Scale the dimension label text. Upper limit adapts to the layout")


def _clear_all() -> None:
    """Empty every input cell (NaN sentinel) — port of handleClearAll.
    cabin_height has no input so it is left intact; structure, display options
    and lift IDs survive. Undoable."""
    cfg = st.session_state["config"]
    cores = [{
        **core,
        "bank1_lifts": [ss.blank_numeric_fields(lf, skip=("cabin_height",))
                        for lf in core["bank1_lifts"]],
        "bank2_lifts": [ss.blank_numeric_fields(lf, skip=("cabin_height",))
                        for lf in core["bank2_lifts"]],
        "wall_thickness_mm": float("nan"),
        "lobby_width_mm": float("nan"),
    } for core in cfg["cores"]]
    set_config({**cfg, "cores": cores, "section": ss.blank_numeric_fields(cfg["section"])})
    st.session_state["plan_error"] = None
    st.session_state["section_error"] = None


def _restore_defaults() -> None:
    """Reset the whole config to defaults (undoable) — port of handleRestoreDefaults."""
    set_config(ss.make_default_config())
    st.session_state["ui_active_core"] = 0
    st.session_state["plan_error"] = None
    st.session_state["section_error"] = None


def _undo_clicked() -> None:
    undo_config()
    st.session_state["plan_error"] = None
    st.session_state["section_error"] = None
    regenerate_active_view()


def _redo_clicked() -> None:
    redo_config()
    st.session_state["plan_error"] = None
    st.session_state["section_error"] = None
    regenerate_active_view()


def _undo_redo_row() -> None:
    """Undo / Redo under the preview image — whole-sketch history (manual +
    Debbie edits), mirroring the web page's placement."""
    uc1, uc2 = st.columns(2)
    with uc1:
        st.button("↩ Undo", key=_wk("undo"), width="stretch",
                  disabled=not can_undo(), on_click=_undo_clicked)
    with uc2:
        st.button("↪ Redo", key=_wk("redo"), width="stretch",
                  disabled=not can_redo(), on_click=_redo_clicked)


# =============================================================================
# Main app
# =============================================================================

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
    init_state()
    cleanup_old_widget_keys()

    st.html('<h1 class="main-brand-title">Drawing Debbie</h1>')

    cfg = st.session_state["config"]
    st.session_state["ui_active_core"] = _active_core_index()  # clamp after core removals

    # ── Sidebar ──
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
        vkey = _wk("active_view")
        if vkey not in st.session_state:
            st.session_state[vkey] = ("Plan View" if st.session_state["ui_active_view"] == "plan"
                                      else "Section View")

        def _cb_view():
            if vkey not in st.session_state:
                return  # stale event from a previous widget revision
            st.session_state["ui_active_view"] = (
                "plan" if st.session_state[vkey] == "Plan View" else "section")

        st.radio("View", options=["Plan View", "Section View"], key=vkey,
                 on_change=_cb_view)
        active_view = st.session_state["ui_active_view"]

        st.divider()

        # Machine type (shared by both views). Switching REBUILDS every lift at
        # the new machine's defaults, preserving lift IDs (mirror of the web).
        mkey = _wk("machine_type")
        if mkey not in st.session_state:
            st.session_state[mkey] = cfg["machine_type"]

        def _cb_machine():
            if mkey not in st.session_state:
                return  # stale event from a previous widget revision
            mt = st.session_state[mkey]
            c = st.session_state["config"]
            if mt == c["machine_type"]:
                return

            def rb(lf):
                r = ss.make_default_lift(lf["type"], mt)
                r["lift_id"] = lf.get("lift_id", "")
                return r

            cores = [{**core,
                      "bank1_lifts": [rb(lf) for lf in core["bank1_lifts"]],
                      "bank2_lifts": [rb(lf) for lf in core["bank2_lifts"]]}
                     for core in c["cores"]]
            set_config({**c, "machine_type": mt, "cores": cores})

        st.radio(
            "Machine Type", options=["mrl", "mra"],
            format_func=lambda x: "MRL (Machine Room Less)" if x == "mrl" else "MRA (Machine Room Above)",
            key=mkey, on_change=_cb_machine,
        )
        machine_type = st.session_state["config"]["machine_type"]

        ci = _active_core_index()
        core = cfg["cores"][ci]
        multi_core = len(cfg["cores"]) > 1

        if active_view == "plan":
            st.divider()

            # Cores — one plan per core
            st.subheader("Cores")
            ckey = _wk("active_core")
            if ckey not in st.session_state:
                st.session_state[ckey] = ci

            def _cb_core():
                if ckey not in st.session_state:
                    return  # stale event from a previous widget revision
                st.session_state["ui_active_core"] = st.session_state[ckey]
                bump_rev()

            st.radio(
                "Active Core", options=list(range(len(cfg["cores"]))),
                format_func=lambda i: cfg["cores"][i]["name"] or f"Core {i + 1}",
                key=ckey, on_change=_cb_core, horizontal=True,
            )

            def _cb_add_core():
                c = st.session_state["config"]
                if len(c["cores"]) >= ss.MAX_CORES:
                    return
                cores = [*c["cores"],
                         ss.make_default_core(c["machine_type"], f"Core {len(c['cores']) + 1}")]
                set_config(ss.fill_blank_lift_ids({**c, "cores": cores}))
                st.session_state["ui_active_core"] = len(cores) - 1

            def _cb_remove_core():
                c = st.session_state["config"]
                if len(c["cores"]) <= 1:
                    return
                rm = _active_core_index()
                remaining = [x for j, x in enumerate(c["cores"]) if j != rm]
                cores = [{**x, "name": f"Core {j + 1}"} for j, x in enumerate(remaining)]
                set_config(ss.fill_blank_lift_ids({**c, "cores": cores}))
                st.session_state["ui_active_core"] = max(0, min(rm, len(cores) - 1))

            ac1, ac2 = st.columns(2)
            with ac1:
                st.button("+ Add Core", key=_wk("add_core"), width="stretch",
                          disabled=len(cfg["cores"]) >= ss.MAX_CORES,
                          on_click=_cb_add_core)
            with ac2:
                st.button("− Remove Core", key=_wk("remove_core"), width="stretch",
                          disabled=len(cfg["cores"]) <= 1,
                          on_click=_cb_remove_core)

            st.divider()

            # Arrangement (per core). Switching to Facing seeds two bank-2 lifts
            # when the bank is empty (mirror of the web toolbar).
            akey = _wk("arrangement")
            if akey not in st.session_state:
                st.session_state[akey] = core["arrangement"]

            def _cb_arrangement():
                if akey not in st.session_state:
                    return  # stale event from a previous widget revision
                val = st.session_state[akey]
                c = st.session_state["config"]
                aci = _active_core_index()
                acore = c["cores"][aci]
                if acore["arrangement"] == val:
                    return
                nxt = {**acore, "arrangement": val}
                if val == "Facing" and not acore["bank2_lifts"]:
                    b2 = [ss.make_default_lift("passenger", c["machine_type"]),
                          ss.make_default_lift("passenger", c["machine_type"])]
                    nxt["bank2_lifts"] = b2
                    nxt["separator_types_bank2"] = ss.compute_default_separator_types(
                        b2, acore["common_shaft"])
                cores = list(c["cores"])
                cores[aci] = nxt
                set_config(ss.fill_blank_lift_ids({**c, "cores": cores}))

            st.radio("Arrangement", options=["Inline", "Facing"], key=akey,
                     on_change=_cb_arrangement)

            # Number of lifts per bank
            n1key = _wk("num_bank1")
            if n1key not in st.session_state:
                st.session_state[n1key] = len(core["bank1_lifts"])

            def _cb_n1():
                if n1key not in st.session_state:
                    return  # stale event from a previous widget revision
                _set_bank_count(_active_core_index(), "bank1", int(st.session_state[n1key]))

            st.number_input("Number of Lifts (Bank 1)", min_value=1,
                            max_value=ss.MAX_LIFTS_PER_BANK, key=n1key, on_change=_cb_n1)

            if core["arrangement"] == "Facing":
                n2key = _wk("num_bank2")
                if n2key not in st.session_state:
                    st.session_state[n2key] = max(1, len(core["bank2_lifts"]))

                def _cb_n2():
                    if n2key not in st.session_state:
                        return  # stale event from a previous widget revision
                    _set_bank_count(_active_core_index(), "bank2", int(st.session_state[n2key]))

                st.number_input("Number of Lifts (Bank 2)", min_value=1,
                                max_value=ss.MAX_LIFTS_PER_BANK, key=n2key, on_change=_cb_n2)

            st.divider()
            st.subheader("Display Options")
            _bool_option("show_dimensions", "Show Dimensions")
            _bool_option("show_hatching", "Show Hatching")
            _bool_option("show_centerlines", "Show Centerlines")
            _bool_option("show_capacity", "Show Capacity Label")
            _bool_option("show_lift_id", "Show Lift ID Label")
            _bool_option("show_accessibility", "Show Accessibility Symbol")
            _bool_option("show_brackets", "Show Brackets")
            _bool_option("show_lift_doors", "Show Lift Doors")
            _bool_option("show_brief_spec", "Show Brief Spec Table")
            _bool_option("split_lift_types", "Split Passenger / Fire Plans")

            # Renumber all lift IDs (PL-01.., FL/SL-01..) continuously across cores
            def _cb_renumber():
                set_config(ss.renumber_lift_ids(st.session_state["config"]))

            st.button("Renumber Lift IDs", key=_wk("renumber"), width="stretch",
                      on_click=_cb_renumber)

            plan_font_max_pct = int(round(ss.plan_dimension_font_max(
                core["arrangement"], len(core["bank1_lifts"]),
                len(core["bank2_lifts"])) * 100))
            _dim_font_slider(plan_font_max_pct, "dimension_font_scale")

        else:
            st.divider()
            st.subheader("Display Options")
            _bool_option("section_show_dimensions", "Show Dimensions")
            _bool_option("section_show_hatching", "Show Hatching")
            _bool_option("section_show_break_lines", "Show Break Lines")
            _bool_option("section_show_machine", "Show Machine Image")
            _bool_option("show_brief_spec", "Show Brief Spec Table")
            _dim_font_slider(int(ss.SECTION_DIM_FONT_MAX * 100),
                             "section_dimension_font_scale")

        st.divider()

        # Auto-generate: re-render the active view's preview after every edit
        # (manual, Debbie, undo/redo). UI preference — not part of the config.
        st.checkbox(
            "Auto-generate preview", key="auto_generate",
            help="Re-render the preview automatically after every change "
                 "(adds ~1s per edit on large sketches).",
        )

        st.button("Clear All", type="secondary", width="stretch",
                  key=_wk("clear_all"), on_click=_clear_all,
                  help="Empty every input cell (structure, IDs and options survive).")
        st.button("Restore Defaults", type="secondary", width="stretch",
                  key=_wk("restore_defaults"), on_click=_restore_defaults,
                  help="Reset every input back to its default value.")

    # Re-read state (callbacks above may have changed it)
    cfg = st.session_state["config"]
    ci = _active_core_index()
    core = cfg["cores"][ci]
    multi_core = len(cfg["cores"]) > 1
    machine_type = cfg["machine_type"]
    active_view = st.session_state["ui_active_view"]

    # Auto-generate: re-render once per config revision. The generate functions
    # stamp _autogen_rev, so paths that already rendered (Debbie, undo/redo,
    # the Generate button, the carousel) are not rendered twice.
    if (st.session_state.get("auto_generate")
            and st.session_state["_autogen_rev"] != st.session_state["rev"]):
        regenerate_active_view()

    # ── Plan View ──
    if active_view == "plan":
        col_config, col_preview = st.columns([1, 1])

        with col_config:
            st.header("Lift Configuration")

            st.subheader(f"{core['name']} — Bank 1" if multi_core else "Bank 1")
            for i in range(len(core["bank1_lifts"])):
                render_lift_form(ci, "bank1", i, machine_type, cfg["show_capacity"])

            if core["arrangement"] == "Facing" and core["bank2_lifts"]:
                st.subheader(f"{core['name']} — Bank 2" if multi_core else "Bank 2")
                for i in range(len(core["bank2_lifts"])):
                    render_lift_form(ci, "bank2", i, machine_type, cfg["show_capacity"])

            st.divider()
            st.subheader("Shaft Configuration")

            col_shaft1, col_shaft2 = st.columns(2)
            with col_shaft1:
                wkey = f"c{ci}_wall_thickness"

                wall_key = _wk(wkey)

                def _cb_wall():
                    if wall_key not in st.session_state:
                        return  # stale event from a previous widget revision
                    raw = st.session_state[wall_key]
                    _core_write(_active_core_index(),
                                {"wall_thickness_mm": float("nan") if raw is None else raw})

                _num(wkey, "Wall Thickness (mm)", seed=core["wall_thickness_mm"],
                     min_value=100, max_value=500, step=25, on_change=_cb_wall)
            with col_shaft2:
                cskey = _wk(f"c{ci}_common_shaft")
                if cskey not in st.session_state:
                    st.session_state[cskey] = bool(core["common_shaft"])

                def _cb_common():
                    if cskey not in st.session_state:
                        return  # stale event from a previous widget revision
                    _core_write(_active_core_index(),
                                {"common_shaft": st.session_state[cskey]})

                st.checkbox("Common Shaft", key=cskey, on_change=_cb_common,
                            help="If checked, lifts share a common shaft "
                                 "(steel-beam separator between passenger lifts).")

            if core["arrangement"] == "Facing":
                lkey = f"c{ci}_lobby"

                lobby_key = _wk(lkey)

                def _cb_lobby():
                    if lobby_key not in st.session_state:
                        return  # stale event from a previous widget revision
                    raw = st.session_state[lobby_key]
                    _core_write(_active_core_index(),
                                {"lobby_width_mm": float("nan") if raw is None else raw})

                _num(lkey, "Lobby Depth (mm)", seed=core["lobby_width_mm"],
                     min_value=2000, max_value=10000, step=100, on_change=_cb_lobby)

            # Per-gap separator types (only when common shaft + >= 2 lifts)
            def sep_fmt(x):
                return "Steel Beam" if x == "steel_beam" else "RCC Wall"
            for bank, label in (("bank1", "Bank 1"), ("bank2", "Bank 2")):
                lifts = core["bank1_lifts"] if bank == "bank1" else core["bank2_lifts"]
                if not (core["common_shaft"] and len(lifts) >= 2):
                    continue
                if bank == "bank2" and core["arrangement"] != "Facing":
                    continue
                sep_key = f"separator_types_{bank}"
                seps = list(core[sep_key])
                while len(seps) < len(lifts) - 1:
                    seps.append("rcc_wall")
                st.caption(f"{label} Separator Types")
                for gi in range(len(lifts) - 1):
                    skey = _wk(f"c{ci}_{bank}_sep_{gi}")
                    if skey not in st.session_state:
                        st.session_state[skey] = seps[gi]

                    def _cb_sep(bank=bank, gi=gi, skey=skey, sep_key=sep_key):
                        if skey not in st.session_state:
                            return  # stale event from a previous widget revision
                        c = st.session_state["config"]
                        aci = _active_core_index()
                        acore = c["cores"][aci]
                        alifts = acore["bank1_lifts"] if bank == "bank1" else acore["bank2_lifts"]
                        cur = list(acore[sep_key])
                        while len(cur) < len(alifts) - 1:
                            cur.append("rcc_wall")
                        cur[gi] = st.session_state[skey]
                        _core_write(aci, {sep_key: cur[:max(0, len(alifts) - 1)]})

                    st.selectbox(f"Lift {gi + 1}–{gi + 2}",
                                 options=["rcc_wall", "steel_beam"],
                                 format_func=sep_fmt, key=skey, on_change=_cb_sep)

        with col_preview:
            st.header("Preview")

            if st.button("Generate Sketch", type="primary", width="stretch",
                         key=_wk("plan_generate")):
                generate_plan()

            # Split-plan carousel: cycle All / Passenger / Fire (regenerates).
            core_lifts = [*core["bank1_lifts"], *core["bank2_lifts"]]
            has_both = (any(lf["type"] == "passenger" for lf in core_lifts)
                        and any(lf["type"] == "fire" for lf in core_lifts))
            show_variant_nav = cfg["split_lift_types"] and has_both
            if not show_variant_nav and st.session_state["ui_plan_variant"] != "all":
                st.session_state["ui_plan_variant"] = "all"

            if show_variant_nav:
                nav1, nav2, nav3 = st.columns([0.15, 0.7, 0.15])
                cur_i = PLAN_VARIANTS.index(st.session_state["ui_plan_variant"])
                with nav1:
                    if st.button("◀", key=_wk("variant_prev"), width="stretch"):
                        nxt = PLAN_VARIANTS[(cur_i - 1) % len(PLAN_VARIANTS)]
                        st.session_state["ui_plan_variant"] = nxt
                        generate_plan(nxt)
                        st.rerun()
                with nav2:
                    st.markdown(
                        f"<p style='text-align:center;margin:0.4rem 0'>"
                        f"{PLAN_VARIANT_LABELS[st.session_state['ui_plan_variant']]}</p>",
                        unsafe_allow_html=True)
                with nav3:
                    if st.button("▶", key=_wk("variant_next"), width="stretch"):
                        nxt = PLAN_VARIANTS[(cur_i + 1) % len(PLAN_VARIANTS)]
                        st.session_state["ui_plan_variant"] = nxt
                        generate_plan(nxt)
                        st.rerun()

            if st.session_state.get("plan_error"):
                st.error(st.session_state["plan_error"])

            if st.session_state.get("plan_image"):
                st.image(st.session_state["plan_image"], width="stretch")
                _undo_redo_row()
                st.download_button(
                    label="Download PNG",
                    data=st.session_state["plan_image"],
                    file_name="lift_plan.png",
                    mime="image/png",
                    width="stretch",
                )

            render_debbie_panel()

    # ── Section View ──
    else:
        col_section_config, col_section_preview = st.columns([1, 1])

        with col_section_config:
            st.header("Section Configuration")

            # Section lift selector — switching auto-applies that lift's
            # shaft/pit/overhead dimensions into the section view.
            st.caption("Section dimensions follow the selected plan-view lift")
            options = []
            labels = {}
            for cci, c in enumerate(cfg["cores"]):
                prefix = f"{c['name'] or f'Core {cci + 1}'} · " if multi_core else ""
                for b, bank_lifts in (("1", c["bank1_lifts"]), ("2", c["bank2_lifts"])):
                    for i, lf in enumerate(bank_lifts):
                        key = f"c{cci}-b{b}-{i}"
                        options.append(key)
                        labels[key] = prefix + ((lf.get("lift_id") or "").strip()
                                                or f"Bank {b} Lift {i + 1}")

            if st.session_state["ui_section_source"] not in options:
                st.session_state["ui_section_source"] = options[0]

            srckey = _wk("section_source")
            if srckey not in st.session_state:
                st.session_state[srckey] = st.session_state["ui_section_source"]

            def _cb_section_source():
                if srckey not in st.session_state:
                    return  # stale event from a previous widget revision
                key = st.session_state[srckey]
                st.session_state["ui_section_source"] = key
                m = SECTION_KEY_RE.match(key)
                if not m:
                    return
                c = st.session_state["config"]
                cci, b, i = int(m.group(1)), m.group(2), int(m.group(3))
                if cci >= len(c["cores"]):
                    return
                acore = c["cores"][cci]
                lifts = acore["bank1_lifts"] if b == "1" else acore["bank2_lifts"]
                if i >= len(lifts):
                    return
                set_config({**c, "section": ss.copy_lift_values_to_section(
                    c["section"], lifts[i], acore["wall_thickness_mm"])})
                st.session_state["section_image"] = None

            st.selectbox("Section Lift", options=options,
                         format_func=lambda k: labels.get(k, k),
                         key=srckey, on_change=_cb_section_source,
                         label_visibility="collapsed")

            render_section_form(machine_type)

        with col_section_preview:
            st.header("Preview")

            if st.button("Generate Section", type="primary", width="stretch",
                         key=_wk("section_generate")):
                generate_section()

            if st.session_state.get("section_error"):
                st.error(st.session_state["section_error"])

            if st.session_state.get("section_image"):
                st.image(st.session_state["section_image"], width="stretch")
                _undo_redo_row()
                st.download_button(
                    label="Download PNG",
                    data=st.session_state["section_image"],
                    file_name="lift_section.png",
                    mime="image/png",
                    width="stretch",
                )

            render_debbie_panel()


if __name__ == "__main__":
    main()
