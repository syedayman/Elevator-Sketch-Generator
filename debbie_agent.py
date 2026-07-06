"""
Debbie planning turn — port of the KARR AI backend's
apps/api/worker/agent/nodes/debbie_planning.py, minus LangGraph (the graph
there is a single node, so here it's a plain function call).

One OpenAI call on the fast tier (DEBBIE_MODEL). The model either:
  • calls apply_sketch_edits(operations, summary) → edits to run through
    debbie_operations.apply_operations()
  • calls ask_user(question, options?) → a clarification (no edits this turn)
  • or replies in plain text (greeting / can't-do).

No RAG, no retrieval, no persistence — the app re-sends the chat history and
current config each turn. The static system prompt (identity + operation
catalog) is a stable prefix so OpenAI prompt-caching shortens follow-up turns;
the dynamic per-turn context (current lifts) goes last.

Config (Streamlit secrets or environment):
  OPENAI_API_KEY     — required for Debbie to work
  DEBBIE_MODEL       — default "gpt-5.4-mini"
  DEBBIE_MAX_TOKENS  — default 800
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_openai_client = None


def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a setting from Streamlit secrets, falling back to the environment."""
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def is_configured() -> bool:
    """True when an OpenAI key is available (Debbie can run)."""
    return bool(_secret("OPENAI_API_KEY"))


def _client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=_secret("OPENAI_API_KEY"))
    return _openai_client


# =============================================================================
# Static system prompt (verbatim from the KARR AI backend — the PROJECT MODE /
# LOCKED sections are inert here because standalone mode never sends locks)
# =============================================================================

SYSTEM_PROMPT = """You are Debbie, an assistant that edits lift (elevator) shaft \
sketches by issuing structured operations. You never draw or compute geometry \
yourself — you translate the user's request into operations, and the app \
re-renders the sketch.

GENERAL RULES
- All dimensions are in millimetres (mm).
- Identify lifts by their lift_id (e.g. "PL-01", "FL/SL-02") and cores by name (e.g. "Core 1").
- A single message may ask for SEVERAL changes — emit one operation per change \
in the operations array, in the order requested, and apply them all in one go. \
If only some parts are clear, apply those and ask_user about the unclear ones.
- Make the SMALLEST set of edits that satisfies the request.
- If the request is ambiguous (which lift? which core?) or missing a required \
value (e.g. "move the door" with no distance), call ask_user — do NOT guess \
magnitudes or pick a lift at random.
- When you ask_user for a missing NUMERIC value (a distance, size, etc.), always \
fill the ask_user `options` with 3-4 sensible suggested values WITH units so the \
user can pick a chip quickly — e.g. for a door move: ["50 mm", "100 mm", "150 mm", \
"200 mm"]. For a which-lift/which-core question, put the actual lift IDs / core names \
in options.
- Never invent a lift_id or core that isn't in the current sketch.
- Door POSITION is two fields: door_offset_mm (distance from centre, in mm) and \
door_offset_direction (left/right). "Centre/center the doors" = set door_offset_mm 0. \
To MOVE/shift a door left or right you MUST have a DISTANCE: set door_offset_mm to \
that many mm AND set_door_direction. CRITICAL: setting the direction alone does \
NOTHING while door_offset_mm is 0 — the door stays centred. If the user gives a \
direction but no distance (e.g. "move the doors left"), ASK how many mm; do NOT just \
set the direction and claim it moved. NEVER use set_door_type for position — \
set_door_type only changes the opening STYLE (centre vs telescopic) and is often \
LOCKED in project mode.
- Set a fire lift's cabin with set_fire_cabin (width, depth), not set_lift_dimension.
- The sketch context lists the ACTIVE VIEW (plan or section) and the ACTIVE CORE. \
For set_font_scale, default scope to the active view unless the user says otherwise. \
When the user says "this core" / "the current core" or omits the core, use the active core.
- If a field is marked LOCKED for a lift, you cannot change it; tell the user it's \
locked by space planning.
- When you make edits, also give a one-sentence summary for the user.

To make changes, call apply_sketch_edits with an `operations` array. Each \
operation is an object with an `op` field plus its parameters:

PER-LIFT (each takes `target`: {lift_ids?: ["PL-02"], select?: "all"|"all_passenger"|"all_fire", core?: "Core 1"}):
- set_lift_dimension {target, field, value}  — field is one of: capacity, width, depth,
  cabin_height, shaft_width, shaft_depth, door_width, door_height, door_panel_length,
  door_panel_thickness, structural_opening_width, structural_opening_height,
  telescopic_left_ext, telescopic_right_ext, cw_bracket_width, car_bracket_width,
  rail_width_left, rail_width_right, door_gap, cw_box_width, cw_box_depth,
  mra_cw_box_width, mra_left_bracket, mra_right_bracket, mra_cw_bracket_depth,
  mra_cw_gap, mra_cw_wall_gap, door_offset_mm, pit_depth, overhead_clearance
- set_lift_type {target, value: "passenger"|"fire"}
- set_door_type {target, value: "centre"|"telescopic"}   (fire only; opening STYLE, NOT door position; often locked)
- set_fire_cabin {target, width, depth}                   (fire lifts only)
- set_door_direction {target, value: "left"|"right"}      (which way door_offset_mm shifts)
- toggle_lift_flag {target, flag: "double_entrance"|"swap_brackets", value: true|false}
- set_lift_id {target, value: "PL-03"}                    (rename ONE lift's ID; target must match exactly one)

STRUCTURAL:
- add_lift {core?, bank?: "bank1"|"bank2", lift_type?: "passenger"|"fire"}
- remove_lift {target}                                    (target must match exactly one lift)
- set_arrangement {core?, value: "Inline"|"Facing"}
- set_common_shaft {core?, value: true|false}
- add_core {}
- remove_core {core}
- set_lobby_width {core?, value}                          (gap between facing banks; locked in project mode)
- set_separator_type {core?, bank?: "bank1"|"bank2", index, value: "steel_beam"|"rcc_wall"}  (separator between adjacent lifts; index is 0-based)

GLOBAL / SECTION:
- set_display_option {option, value: true|false}  — option is one of: show_dimensions,
  show_hatching, show_centerlines, show_capacity, show_accessibility, show_brackets,
  show_lift_doors, show_lift_id, show_brief_spec, split_lift_types,
  section_show_dimensions, section_show_hatching, section_show_break_lines, section_show_machine
- set_font_scale {scope: "plan"|"section", value}
- set_machine_type {value: "mrl"|"mra"}
- set_section_field {field, value}  — field is one of: shaft_depth, wall_thickness,
  pit_slab, pit_depth, travel_height, overhead_clearance, door_height,
  structural_opening_height, machine_room_height

DISAMBIGUATION — these words map to MORE THAN ONE field. If the user hasn't made
it specific, call ask_user instead of guessing:
- "clearance": running clearance = door_gap; headroom = overhead_clearance; \
CWT clearances = mra_cw_gap / mra_cw_wall_gap.
- "height": door_height, structural_opening_height, cabin_height, travel_height, \
machine_room_height, or headroom (overhead_clearance).
- "bigger / wider / deeper" on a car/cabin or shaft: clarify WIDTH vs DEPTH \
(width and depth are separate fields for both car and shaft).
- "the opening": door opening (door_width / door_height) vs structural opening \
(structural_opening_width / structural_opening_height).
- "the bracket(s)" / "counterweight" / "CW" / "CWT": several fields, and they \
DIFFER BY MACHINE TYPE — MRL uses cw_bracket_width & car_bracket_width; MRA uses \
mra_left_bracket, mra_right_bracket, mra_cw_bracket_depth, mra_cw_gap, plus \
cw_box_width/mra_cw_box_width. Use the current machine_type's fields and ask which one.
- "rails": rail_width_left vs rail_width_right (or both).
- Font / text size: set_font_scale needs scope "plan" or "section" — ask which if unclear.

TERMINOLOGY: "service lift" / "FL/SL" = a fire lift (type "fire"). "counterweight" = CW/CWT.

PROJECT MODE (some fields are LOCKED — see the LOCKED list in the sketch context):
- If the user asks to change a LOCKED field, do NOT emit the operation. Tell them \
it's fixed by space planning. (Locked fields typically include cabin/shaft sizes, \
door width/height, door opening type, capacity, pit depth, headroom.)
- Machine type, arrangement, and adding/removing cores may be locked too — don't attempt them when locked.

STANDALONE MODE:
- set_machine_type REBUILDS every lift at default dimensions (custom sizes are lost). \
Say this in your summary so the user isn't surprised.
"""

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "apply_sketch_edits",
            "description": (
                "Apply one or more edits to the lift sketch. Use only when you "
                "have enough information; otherwise call ask_user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "description": "Operations to apply, in order.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {"type": "string"},
                                "target": {"type": "object"},
                                "field": {"type": "string"},
                                "value": {},
                                "width": {"type": "number"},
                                "depth": {"type": "number"},
                                "option": {"type": "string"},
                                "scope": {"type": "string"},
                                "flag": {"type": "string"},
                                "core": {},
                                "bank": {"type": "string"},
                                "lift_type": {"type": "string"},
                            },
                            "required": ["op"],
                        },
                    },
                    "summary": {
                        "type": "string",
                        "description": "One short sentence describing the change, for the user.",
                    },
                },
                "required": ["operations", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Ask the user a clarifying question when the request is ambiguous "
                "or missing a required value. No edits are made this turn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional short quick-reply choices.",
                    },
                },
                "required": ["question"],
            },
        },
    },
]


# =============================================================================
# Dynamic context: summarize the current sketch
# =============================================================================

def _lift_line(lift: Dict[str, Any]) -> str:
    lid = lift.get("lift_id") or "(unassigned)"
    typ = lift.get("type", "passenger")
    parts = [
        f"{lid} {typ}",
        f"shaft={lift.get('shaft_width')}x{lift.get('shaft_depth')}",
        f"car={lift.get('width')}x{lift.get('depth')}",
        f"door={lift.get('door_width')} {lift.get('door_opening_type', 'centre')}",
        f"offset={lift.get('door_offset_mm', 0)} {lift.get('door_offset_direction', 'right')}",
    ]
    if typ == "fire" and lift.get("double_entrance"):
        parts.append("double_entrance")
    return "    " + " ".join(str(p) for p in parts)


def _summarize_config(config: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"machine_type: {config.get('machine_type', 'mrl')}")

    cores = config.get("cores") or []
    for core in cores:
        name = core.get("name", "Core")
        arr = core.get("arrangement", "Inline")
        cs = core.get("common_shaft", False)
        lines.append(f"{name} ({arr}, common_shaft={cs}):")
        b1 = core.get("bank1_lifts") or []
        if b1:
            lines.append("  bank1:")
            lines.extend(_lift_line(lift) for lift in b1)
        b2 = core.get("bank2_lifts") or []
        if b2:
            lines.append("  bank2:")
            lines.extend(_lift_line(lift) for lift in b2)

    section = config.get("section") or {}
    if section:
        sec = " ".join(f"{k}={v}" for k, v in section.items())
        lines.append(f"section: {sec}")

    return "\n".join(lines)


def _build_context_message(config: Dict[str, Any], active_view: Optional[str],
                           active_core: Optional[str]) -> str:
    chunks = ["CURRENT SKETCH:", _summarize_config(config or {})]
    ui_bits = []
    if active_view:
        ui_bits.append(f"ACTIVE VIEW: {active_view}")
    if active_core:
        ui_bits.append(f"ACTIVE CORE: {active_core}")
    if ui_bits:
        chunks.append("\n" + "\n".join(ui_bits))
    return "\n".join(chunks)


def _to_openai_messages(messages: List[Dict[str, str]], config: Dict[str, Any],
                        active_view: Optional[str], active_core: Optional[str]) -> List[Dict[str, str]]:
    """System prompt first (cached prefix), then chat history, then the dynamic
    sketch context as the final user message."""
    msgs: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages or []:
        role = m.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        content = m.get("content") or ""
        if content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user",
                 "content": _build_context_message(config, active_view, active_core)})
    return msgs


# =============================================================================
# The planning turn
# =============================================================================

def run_debbie_turn(
    messages: List[Dict[str, str]],
    config: Dict[str, Any],
    active_view: Optional[str] = None,
    active_core: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one planning turn. Returns a dict with assistant_text plus either
    operations or pending_clarification (mirror of debbie_planning_node)."""
    try:
        response = _client().chat.completions.create(
            model=_secret("DEBBIE_MODEL", "gpt-5.4-mini"),
            messages=_to_openai_messages(messages, config, active_view, active_core),
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
            max_completion_tokens=int(_secret("DEBBIE_MAX_TOKENS", "800")),
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                logger.warning(
                    "Debbie tool args not valid JSON: %s", call.function.arguments
                )
                continue

            if name == "apply_sketch_edits":
                ops = args.get("operations") or []
                summary = (args.get("summary") or "").strip() or "Done."
                if ops:
                    return {"operations": ops, "assistant_text": summary}
                # No ops in the call — fall through to ask/plain text.
            elif name == "ask_user":
                question = (args.get("question") or "").strip()
                if question:
                    return {
                        "assistant_text": question,
                        "pending_clarification": {
                            "question": question,
                            "options": args.get("options") or [],
                        },
                    }

        # No actionable tool call — return the plain text reply.
        text = (message.content or "").strip()
        fallback = "I'm not sure how to change that — can you rephrase?"
        return {"assistant_text": text or fallback}

    except Exception as e:  # noqa: BLE001 — surface a friendly message, log the cause
        logger.error("Debbie planning failed: %s", e, exc_info=True)
        return {
            "error": str(e),
            "assistant_text": (
                "Sorry — I hit an error working that out. Please try again."
            ),
        }
