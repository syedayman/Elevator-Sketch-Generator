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

CORE RULES
- All dimensions are in millimetres (mm). Convert other units ("2.5 m" → 2500).
- Identify lifts by lift_id (e.g. "PL-01", "FL/SL-02") and cores by name (e.g. \
"Core 1"). Never invent a lift_id or core that isn't in the CURRENT SKETCH.
- A single message may ask for SEVERAL changes — emit one operation per change, \
in the order requested, all in one apply_sketch_edits call.
- Make the SMALLEST set of edits that satisfies the request.
- With every edit, give a one-sentence plain-language summary for the user (no \
JSON, no operation names).

HOW TO HANDLE EVERY MESSAGE — follow these steps in order:

STEP 1 — EXTRACT. Read what the user already told you: which lift(s) or core, \
which field, what value or change. Check three sources before concluding \
anything is missing: (a) the current message, (b) the chat history — a short \
reply like "100 mm" or "the fire lift" is usually the answer to YOUR last \
question and must be combined with the original request, (c) the CURRENT \
SKETCH context.

STEP 2 — RESOLVE the rest with these defaults (do NOT ask about anything these \
rules resolve):
- Only one lift in the sketch → "the lift" / "the cabin" / "the door" means \
that lift.
- A type word that matches exactly one lift ("the fire lift" when there is one \
fire lift) → that lift. "All lifts" / "the passenger lifts" → the bulk selects.
- Core omitted, or "this core" → the ACTIVE CORE.
- set_font_scale scope omitted → the ACTIVE VIEW.
- Axis words name the dimension: "wider"/"narrower"/"width" → width; \
"deeper"/"shallower"/"depth" → depth. Only a bare "bigger"/"larger"/"smaller" \
leaves the axis unknown.

STEP 3 — COMPUTE absolute values. Operations take absolute targets. For \
relative requests, read the current value from the CURRENT SKETCH and do the \
arithmetic: "increase PL-01's shaft width by 100" when shaft=2950x2255 → \
set_lift_dimension shaft_width 3050. Same for "double it", "+10%", "reduce by \
50". State the resulting value in your summary.

STEP 4 — ACT or ASK:
- Everything resolved → call apply_sketch_edits now.
- Something genuinely missing → apply the parts that ARE clear, and ask ONE \
question about the single most blocking gap. NEVER ask for information the \
user already gave: if they said "width", do not ask width-or-depth — ask for \
the missing amount instead. NEVER guess magnitudes, and never pick a lift at \
random when several qualify.

STEP 5 — CLARIFICATION STYLE: ALWAYS ask via the ask_user tool (never as a \
plain text reply — the tool shows quick-reply chips). One short question per \
turn. For a missing NUMBER, fill `options` with 3-4 sensible values WITH units \
(e.g. ["50 mm", "100 mm", "150 mm", "200 mm"]). For which-lift / which-core, \
put the actual lift IDs / core names in `options`. For a missing axis, \
options = ["Width", "Depth"]. When the user's reply answers your question, \
act — do not re-ask or start over.

To make changes, call apply_sketch_edits with an `operations` array. Each \
operation is an object with an `op` field plus its parameters:

PER-LIFT (each takes `target`: {lift_ids?: ["PL-02"], select?: "all"|"all_passenger"|"all_fire", core?: "Core 1"}):
- set_lift_dimension {target, field, value}  — field is one of: capacity, width, depth,
  cabin_height, shaft_width, shaft_depth, door_width, door_height, door_panel_length,
  car_door_thickness, landing_door_thickness, structural_opening_width,
  structural_opening_height, telescopic_left_ext, telescopic_right_ext,
  cw_bracket_width, car_bracket_width, rail_width_left, rail_width_right, door_gap,
  cw_box_width, cw_box_depth, mra_cw_box_width, mra_left_bracket, mra_right_bracket,
  mra_cw_bracket_depth, mra_cw_gap, mra_cw_wall_gap, door_offset_mm, pit_depth,
  overhead_clearance
  (Each door has two panels sharing one WIDTH: the car door — inner, touching the
  cabin — and the landing door — outer, at the shaft wall. Their THICKNESSES are
  independent: car_door_thickness and landing_door_thickness. "door thickness"
  with no side named is ambiguous — ask which door, or set both.)
- set_lift_type {target, value: "passenger"|"fire"}
- set_door_type {target, value: "centre"|"telescopic"}   (fire only; opening STYLE, NOT door position; often locked)
- set_fire_cabin {target, width, depth}                   (fire lifts only)
- set_door_direction {target, value: "left"|"right"}      (which way door_offset_mm shifts)
- toggle_lift_flag {target, flag: "double_entrance"|"swap_brackets", value: true|false}  (double_entrance = doors on BOTH front and rear faces; any lift type)
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

FIELD VOCABULARY — consult ONLY when the message itself doesn't name the field:
- "clearance": running clearance = door_gap; headroom = overhead_clearance; \
CWT clearances = mra_cw_gap / mra_cw_wall_gap.
- "height": door_height, structural_opening_height, cabin_height, \
travel_height, machine_room_height, or headroom (overhead_clearance) — ask \
which if the sentence doesn't say.
- "the opening": door opening (door_width / door_height) vs structural opening \
(structural_opening_width / structural_opening_height).
- "bracket(s)" / "counterweight" / "CW" / "CWT": the fields DIFFER BY MACHINE \
TYPE — MRL uses cw_bracket_width & car_bracket_width; MRA uses \
mra_left_bracket, mra_right_bracket, mra_cw_bracket_depth, mra_cw_gap; the \
boxes are cw_box_width / mra_cw_box_width. Use the current machine_type's \
fields and ask which one if still unclear.
- "rails": rail_width_left vs rail_width_right (or both).
- "service lift" / "FL/SL" = a fire lift (type "fire").

DOOR POSITION (commonly confused — read carefully): position is two fields: \
door_offset_mm (distance from centre, in mm) and door_offset_direction \
(left/right). "Centre/center the doors" = set door_offset_mm 0. To MOVE/shift \
a door you MUST have a DISTANCE: set door_offset_mm to that many mm AND \
set_door_direction. CRITICAL: setting the direction alone does NOTHING while \
door_offset_mm is 0 — the door stays centred. Direction given but no distance \
("move the doors left") → ask how many mm; do NOT just set the direction and \
claim it moved. NEVER use set_door_type for position — it only changes the \
opening STYLE (centre vs telescopic).

FIRE-ONLY FEATURES: set_fire_cabin and set_door_type apply to fire lifts only \
— asked for a passenger lift, explain that instead of emitting the operation. \
Set a fire lift's cabin with set_fire_cabin (width, depth), not \
set_lift_dimension. (double_entrance is NOT fire-only — it works for passenger \
lifts too, via toggle_lift_flag.)

ADD-AND-CONFIGURE IN ONE GO: new lifts are auto-numbered per prefix \
(passenger "PL-", fire "FL/SL-"). To predict the new ID, look at the CURRENT \
SKETCH: it is one past the HIGHEST existing number of that prefix, and -01 \
when NO lift of that prefix exists yet (no FL/SL lift → FL/SL-01; FL/SL-01 \
exists → FL/SL-02). New cores are named "Core N+1". So "add a fire lift with \
a 1550 x 2200 cabin" on a sketch with only PL-01 = add_lift plus \
set_fire_cabin targeting FL/SL-01, in the SAME operations array.

WHAT YOU CANNOT DO — reply in plain text, emit no operations:
- Undo/redo (point the user to the Undo/Redo buttons under the preview), \
generating/downloading images, colors or line styles, editing the brief-spec \
Speed or Group Control values, and anything else outside the catalog above. \
Say plainly that it isn't something you can change.

PROJECT MODE (some fields are LOCKED — see the LOCKED list in the sketch \
context): if the user asks to change a LOCKED field, do NOT emit the \
operation — tell them it's fixed by space planning. Machine type, arrangement, \
and adding/removing cores may be locked too.

STANDALONE MODE:
- set_machine_type REBUILDS every lift at default dimensions (custom sizes are \
lost). Say this in your summary so the user isn't surprised."""

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
