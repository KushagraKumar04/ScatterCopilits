from __future__ import annotations

import json

from . import bpmn_linter as linter
from .ai_client import AISettings, chat, chat_json
from .lang_helper import language_instruction
from ..config import (
    MAX_SELF_CORRECT_LOOPS,
    GEN_MAX_TOKENS,
    ENHANCE_MAX_TOKENS,
    EXPLAIN_MAX_TOKENS,
    AUTOMATE_MAX_TOKENS,
    LLM_TEMPERATURE_GENERATE,
    LLM_TEMPERATURE_EDIT,
    LLM_TEMPERATURE_FIX,
    LLM_TEMPERATURE_ENHANCE,
    LLM_TEMPERATURE_EXPLAIN,
    LLM_TEMPERATURE_AUTOMATE,
)

BPMN_XML_RULES = """
You are the Interpreter+Modeler agent inside BPMN Copilot, a multi-agent process
intelligence engine. Convert a plain-language business process description into a
single, complete, valid BPMN 2.0 XML document.

STRICT OUTPUT RULES:
- Output ONLY the raw BPMN 2.0 XML. No markdown fences, no commentary.
- Start with <?xml ...?> and contain exactly one <bpmn:definitions> root with one
  <bpmn:process> inside it, and end with </bpmn:definitions>.
- Use these namespaces exactly:
  xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
- EXACTLY ONE reachable <bpmn:startEvent> and AT LEAST ONE reachable <bpmn:endEvent>.
  Every node connected by <bpmn:sequenceFlow> with valid sourceRef/targetRef.
- Every task uses a clear "Verb + Noun" business name (e.g. "Support Agent Reviews
  Complaint"). Never use vague names ("someone checks it", "handle", "process") or empty names.
- Every <bpmn:exclusiveGateway> has a name phrased as a yes/no question ending in "?"
  and its outgoing flows are labelled (e.g. name="Yes" / name="No").
- Do NOT include a <bpmndi:BPMNDiagram> section at all. The visual layout is generated
  automatically and deterministically after you respond, so coordinates are unnecessary.
  Output ONLY the semantic process (events, tasks, gateways, sequenceFlows).

LAYOUT & STRUCTURE RULES (apply to EVERY process, regardless of domain):
- Tasks that belong to the SAME lane must sit on the SAME horizontal (or vertical)
  baseline. Do not stagger task boxes within a lane - sequence flows must be
  straight, never diagonal or crossing.
- When two or more branches converge on a single end event, insert a joining
  <bpmn:exclusiveGateway> immediately before that end event. NEVER let two
  sequence flows point directly at the same end event without a merger.
- If the branches end with genuinely different outcomes, use SEPARATE end events
  (one per branch), each with its own distinct name. Do NOT merge them.
- End events must belong to the lane of the actor who COMPLETES the workflow.
  Never leave an end event in a lane that has no tasks.
- No lane may contain ONLY an end event.
- No lane may be empty (a lane with zero tasks, gateways, or activities is invalid).
- Every lane must own at least one meaningful task (or a gateway that routes work).

- Keep it compact: short IDs, minimal whitespace, no comments. Do not invent extra steps.
""".strip()

EDIT_RULES = """
You are the Editor agent inside BPMN Copilot. You receive an EXISTING, valid BPMN 2.0
XML document plus a single natural-language edit instruction from the user. Apply ONLY
that instruction and return the complete, updated BPMN 2.0 XML.

STRICT RULES:
- Output ONLY the raw BPMN 2.0 XML. No markdown fences, no commentary, no explanation.
- The document MUST be complete: start with <?xml ...?> and end with </bpmn:definitions>.
- Preserve every existing element ID and every part of the process that the instruction
  does not mention. Do not restructure or rename things you were not asked to change.
- Keep the model valid: exactly one reachable start event, at least one reachable end
  event, all sequenceFlows wired with valid sourceRef/targetRef.
- When ADDING a node, insert it into the flow correctly (rewire the surrounding
  sequenceFlows) and give it a clear "Verb + Noun" name and a new unique ID.
- When REMOVING a node, reconnect the surrounding flows so the process stays connected.
- Do NOT include a <bpmndi:BPMNDiagram> section. Output ONLY the semantic process; the
  layout is regenerated automatically after you respond. (If the input contained lanes/
  pools, keep the laneSet/collaboration but you may still omit the diagram section.)
- Use the same namespaces as the input document.
""".strip()

ENHANCE_RULES = """
You are the Enhancer agent inside BPMN Copilot. You receive a rough, informal business
process description. Rewrite it into a clear, well-structured description that a process
modeler can turn into a clean BPMN diagram.

RULES:
- Preserve the user's original intent. Do NOT invent steps, actors, systems, or decisions
  that are not stated or clearly implied. If something is ambiguous, keep it general rather
  than fabricating specifics.
- Make it structured and explicit: identify the trigger/start, the ordered steps (each as a
  clear "Actor + Verb + Object" action), any decision points phrased as yes/no questions,
  and the end state(s).
- Use clear business language, short sentences, and name the actors/roles when implied.
- Return ONLY the rewritten description as plain prose (a short paragraph or a few
  sentences). No headings, no bullet symbols, no markdown, no commentary, no preamble.
""".strip()

PERSONA_FRAMING = {
    "auditor": "a Process Auditor focused on compliance, controls, segregation of duties, traceability, and audit readiness",
    "manager": "a Manager who wants a high-level view of throughput, bottlenecks, cycle time, and business risk - no BPMN jargon",
    "engineer": "an Automation Developer looking for RPA / Power Automate / REST API integration opportunities and technical implementation notes",
}


def enhance_description(description: str, settings: AISettings) -> str:
    user = f'Rough description:\n"""\n{description.strip()}\n"""\n\nRewrite it now.'
    text = chat(ENHANCE_RULES + language_instruction(settings.language), user, settings, temperature=LLM_TEMPERATURE_ENHANCE, max_tokens=ENHANCE_MAX_TOKENS)

    return (text or "").strip()


def _looks_truncated(raw: str) -> bool:
    if not raw:
        return True
    text = raw.strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return "</bpmn:definitions>" not in text and "</definitions>" not in text


def _retry_feedback(raw: str, error: str) -> str:
    if _looks_truncated(raw):
        return (
            "\n\nYour previous output was CUT OFF before the closing </bpmn:definitions> tag, "
            "so the XML was incomplete. Produce a MORE COMPACT but COMPLETE document: use short "
            "IDs, put each element on one line, remove all whitespace between tags, and keep the "
            "<bpmndi:BPMNDiagram> minimal. The full document MUST end with </bpmn:definitions>."
        )
    return (
        f"\n\nThe previous output failed to parse: {error}. Return a COMPLETE, well-formed BPMN 2.0 "
        "XML document only, with every tag properly closed and ending in </bpmn:definitions>."
    )


def generate_valid_xml(system, base_user, settings, temperature, *,
                       extra_ok=None, extra_feedback=None, max_loops=None):
    """Call the LLM, lint, and self-correct on parse errors up to max_loops.

    - Handles linter.BpmnParseError gracefully (never raises it up).
    - extra_ok(result)->bool: optional post-condition (e.g. lanes present, edit applied).
      When it returns False, one more corrective loop is attempted.
    Returns (result_or_None, warning_or_None, loops_used).
    """
    loops = max_loops or MAX_SELF_CORRECT_LOOPS
    feedback = ""
    last_result = None
    warning = None
    for loop in range(1, loops + 1):
        raw = chat(system, base_user + feedback, settings, temperature=temperature, max_tokens=GEN_MAX_TOKENS)
        try:
            result = linter.lint(raw)
        except linter.BpmnParseError as e:
            warning = f"Invalid XML on attempt {loop}: {e}"
            feedback = _retry_feedback(raw, str(e))
            continue
        last_result = result
        if extra_ok is None or extra_ok(result):
            return result, None, loop
        feedback = "\n\n" + (extra_feedback or "The requested change was not fully applied. Try again and ensure it is.")
    return last_result, (warning or "Could not produce a fully valid result after retries."), loops


def generate_bpmn_events(description: str, settings: AISettings):
    user_prompt = f'Process description:\n"""\n{description.strip()}\n"""\n\nGenerate the BPMN 2.0 XML now.'
    last_xml = None
    last_lint = None
    warning = None
    feedback = ""
    yield _ev("agent", agent="interpreter", status="active")
    yield _ev("log", line="[Interpreter] Parsing natural-language description and extracting actors, tasks, decisions and events.")
    yield _ev("agent", agent="interpreter", status="done")
    for loop in range(1, MAX_SELF_CORRECT_LOOPS + 1):
        yield _ev("agent", agent="modeler", status="active")
        yield _ev("log", line=f"[Modeler] Generating BPMN 2.0 XML (attempt {loop} of {MAX_SELF_CORRECT_LOOPS}).")
        raw = chat(BPMN_XML_RULES + language_instruction(settings.language), user_prompt + feedback, settings, temperature=LLM_TEMPERATURE_GENERATE, max_tokens=GEN_MAX_TOKENS)
        yield _ev("agent", agent="modeler", status="done")
        yield _ev("agent", agent="validator", status="active")
        try:
            result = linter.lint(raw)
        except linter.BpmnParseError as e:
            warning = f"Model produced invalid XML on attempt {loop}: {e}"
            truncated = _looks_truncated(raw)
            yield _ev("log", line=f"[Validator] {'Output was cut off (truncated).' if truncated else 'XML failed to parse.'} {e}", level="error")
            yield _ev("agent", agent="validator", status="done")
            feedback = _retry_feedback(raw, str(e))
            continue
        last_xml = result["cleanedXml"]
        last_lint = result
        crit = result["criticalCount"]
        yield _ev("log", line=f"[Validator] Health score {result['totalScore']}/100 ({result['band']}). Critical issues: {crit}.")
        yield _ev("agent", agent="validator", status="done")
        if crit == 0:
            yield _ev("log", line="[Validator] Model passed deterministic checks. Loop complete.", level="success")
            # Mark the Explainer step as complete so the stepper shows the pipeline finished.
            # Emit 'active' first so the UI transitions correctly rather than jumping to 'done'.
            yield _ev("agent", agent="explainer", status="active")
            yield _ev("log", line="[Explainer] Model ready - click 'Explain for' to generate a narrative.")
            yield _ev("agent", agent="explainer", status="done")
            yield _ev("result", data={"xml": last_xml, "lint": _public_lint(result), "loops": loop})
            return
        criticals = [i for i in result["issues"] if i["type"] == "critical"]
        yield _ev("agent", agent="fixer", status="active")
        for i in criticals:
            yield _ev("log", line=f"[Fixer] Feeding back: {i['title']} - {i['desc']}", level="warn")
        yield _ev("agent", agent="fixer", status="done")
        feedback = (
            "\n\nThe previous BPMN had these CRITICAL issues; regenerate a fully valid version fixing them:\n"
            + "\n".join(f"- {i['title']}: {i['desc']}" for i in criticals)
        )
    yield _ev("log", line=warning or "Model still had issues after the maximum correction loops.", level="warn")
    yield _ev("result", data={
        "xml": last_xml,
        "lint": _public_lint(last_lint) if last_lint else None,
        "loops": MAX_SELF_CORRECT_LOOPS,
        "warning": warning or "Model still had issues after the max correction loops.",
    })


def generate_bpmn(description: str, settings: AISettings) -> dict:
    final = None
    for event in generate_bpmn_events(description, settings):
        if event["type"] == "result":
            final = event["data"]
    return final or {"xml": None, "lint": None, "loops": 0, "warning": "Generation produced no result."}


def edit_bpmn_events(xml: str, instruction: str, settings: AISettings):
    instruction = (instruction or "").strip()
    yield _ev("agent", agent="editor", status="active")
    yield _ev("log", line=f'[Editor] Applying change: "{instruction[:80]}{"…" if len(instruction) > 80 else ""}"')

    from . import bpmn_edit
    det = bpmn_edit.try_deterministic_edit(xml, instruction)
    if det is not None:
        if "ambiguous" in det:
            yield _ev("log", line=f"[Editor] Ambiguous target - matches: {', '.join(det['ambiguous'])}. Please be more specific.", level="warn")
            yield _ev("agent", agent="editor", status="done")
            yield _ev("result", data={"xml": xml, "lint": None, "loops": 0,
                                      "warning": "That instruction matched multiple elements: "
                                      + ", ".join(det["ambiguous"]) + ". Please name the exact one."})
            return
        yield _ev("log", line=f"[Editor] {det['detail']} (applied deterministically - no LLM).", level="success")
        yield _ev("agent", agent="editor", status="done")
        yield _ev("agent", agent="validator", status="active")
        try:
            result = linter.lint(det["xml"])
            yield _ev("log", line=f"[Validator] Health score {result['totalScore']}/100 ({result['band']}).", level="success")
            yield _ev("agent", agent="validator", status="done")
            yield _ev("result", data={"xml": result["cleanedXml"], "lint": _public_lint(result), "loops": 0})
            return
        except linter.BpmnParseError:
            pass  # extremely unlikely; fall through to the LLM path

    user = (
        f"Current BPMN XML:\n{xml}\n\n"
        f'Edit instruction:\n"""\n{instruction}\n"""\n\nReturn the complete updated BPMN 2.0 XML.'
    )
    feedback = ""
    last_xml = None
    last_lint = None
    warning = None
    for loop in range(1, MAX_SELF_CORRECT_LOOPS + 1):
        raw = chat(EDIT_RULES + language_instruction(settings.language), user + feedback, settings, temperature=LLM_TEMPERATURE_EDIT, max_tokens=GEN_MAX_TOKENS)
        yield _ev("agent", agent="editor", status="done")
        yield _ev("agent", agent="validator", status="active")
        try:
            result = linter.lint(raw)
        except linter.BpmnParseError as e:
            warning = f"Edited XML failed to parse on attempt {loop}: {e}"
            truncated = _looks_truncated(raw)
            yield _ev("log", line=f"[Validator] {'Edited output was cut off (truncated).' if truncated else 'Edited XML failed to parse.'} {e}", level="error")
            yield _ev("agent", agent="validator", status="done")
            feedback = _retry_feedback(raw, str(e))
            if loop < MAX_SELF_CORRECT_LOOPS:
                yield _ev("agent", agent="editor", status="active")
            continue
        last_xml = result["cleanedXml"]
        last_lint = result
        yield _ev("log", line=f"[Validator] Edit applied. Health score {result['totalScore']}/100 ({result['band']}).", level="success")
        yield _ev("agent", agent="validator", status="done")
        yield _ev("result", data={"xml": last_xml, "lint": _public_lint(result), "loops": loop})
        return
    yield _ev("log", line=warning or "The edit could not be applied cleanly.", level="warn")
    yield _ev("result", data={
        "xml": last_xml,
        "lint": _public_lint(last_lint) if last_lint else None,
        "loops": MAX_SELF_CORRECT_LOOPS,
        "warning": warning or "The edit could not be applied cleanly. Try a shorter instruction or a stronger model.",
    })


def edit_bpmn(xml: str, instruction: str, settings: AISettings) -> dict:
    final = None
    for event in edit_bpmn_events(xml, instruction, settings):
        if event["type"] == "result":
            final = event["data"]
    return final or {"xml": None, "lint": None, "loops": 0, "warning": "Edit produced no result."}


def _fix_system_prompt(issues: list[dict]) -> str:
    reconnect_rules = """
RECONNECT MISSING FLOWS (apply when a node is a "Dead-end" and/or "Unreachable" node):
A sequence flow was likely deleted. Restore the process connectivity:
- If a node has NO outgoing flow (dead-end) and another node has NO incoming flow
  (unreachable), and the process logically continues from the first to the second,
  add a <bpmn:sequenceFlow> connecting them (sourceRef = dead-end node, targetRef =
  unreachable node) with a new unique id.
- Preserve the left-to-right order implied by the diagram coordinates when deciding
  which node connects to which.
- For every sequenceFlow you add, ALSO add a matching <bpmndi:BPMNEdge> with waypoints
  linking the two nodes' shapes so the connector is visible.
- Never leave a task/gateway without at least one incoming AND one outgoing flow
  (start events need only outgoing; end events need only incoming).
""".strip()

    lane_rules = """
SWIMLANES / OWNERSHIP (apply ONLY if a "swimlane"/lanes issue is listed):
You MUST add visible, correctly-rendered swimlanes by producing a POOL with LANES.
Follow this exact structure or the lanes will not render:

1. Add a <bpmn:collaboration> (a sibling of <bpmn:process>, placed BEFORE it) with ONE
   <bpmn:participant> that has processRef pointing to the existing process id, e.g.:
     <bpmn:collaboration id="Collab_1">
       <bpmn:participant id="Pool_1" name="<Process Name>" processRef="Process_1" />
     </bpmn:collaboration>

2. Inside <bpmn:process>, add a <bpmn:laneSet> as its FIRST child, with one <bpmn:lane>
   per role/actor. EVERY flow node (every startEvent, task, gateway, endEvent) MUST be
   listed in EXACTLY ONE lane via <bpmn:flowNodeRef>. Infer roles from the task names
   (e.g. Customer, Support Agent, Manager, System, Finance). Example:
     <bpmn:laneSet id="LaneSet_1">
       <bpmn:lane id="Lane_Customer" name="Customer">
         <bpmn:flowNodeRef>Start_1</bpmn:flowNodeRef>
       </bpmn:lane>
       <bpmn:lane id="Lane_Agent" name="Support Agent">
         <bpmn:flowNodeRef>Task_1</bpmn:flowNodeRef>
         <bpmn:flowNodeRef>End_1</bpmn:flowNodeRef>
       </bpmn:lane>
     </bpmn:laneSet>

3. In the diagram, the <bpmndi:BPMNPlane> bpmnElement MUST reference the COLLABORATION id
   (Collab_1), NOT the process id. This is critical - if it points at the process, the
   pool and lanes will be invisible.

4. Add DI shapes with non-overlapping bounds:
   - One <bpmndi:BPMNShape isHorizontal="true"> for the pool (Pool_1) enclosing everything.
   - One <bpmndi:BPMNShape isHorizontal="true"> for EACH lane, stacked vertically inside
     the pool (each lane ~120px tall, same width as the pool minus the ~30px label gutter).
   - Position every node's existing BPMNShape so it sits INSIDE its lane's vertical band.
     Keep the left-to-right flow; only shift y-coordinates so each node falls in its lane.
   - Keep/update all BPMNEdge waypoints so connectors still line up.

5. Preserve every existing element id, name, sequenceFlow and the overall flow. Do not
   drop the <bpmndi:BPMNDiagram>; extend it with the pool + lane shapes.
""".strip()

    structural_rules = """
STRUCTURAL FIX RULES (apply when the linter flags these titles):
- "End event merges multiple flows without a joining gateway":
  Insert an <bpmn:exclusiveGateway> immediately before the end event. Rewire every
  incoming branch to target the gateway, then add ONE outgoing sequenceFlow from
  the gateway to the end event. Keep existing element IDs where possible.
- "Swimlane contains only an end event":
  Move the end event into the lane of the task immediately preceding it
  (the lane of the actor who finishes the work). Update both the laneSet
  flowNodeRef lists and the BPMNShape bounds so the event visibly sits inside
  the correct lane.
- "Swimlane has no tasks":
  Prefer merging the lane's events into an adjacent lane and deleting the empty
  lane. Only keep the lane if it represents a genuine system actor, and if so
  add an explicit "Verb + Noun" task describing what that actor does.
- "Empty swimlane":
  Delete the lane, or assign it at least one meaningful task.
- "Unreachable node" / "Dead-end node":
  Rewire the surrounding sequenceFlows so every non-start node has both incoming
  and outgoing flows, and every non-end node has both as well.
""".strip()

    return f"""
You are the Fixer agent inside BPMN Copilot. You receive an existing BPMN 2.0 XML
document plus a list of issues found by the deterministic linter. Apply the MINIMAL
set of changes needed to resolve every listed issue, without altering the overall
process intent or removing unrelated nodes.

Rules:
- Rename vague task names to a clear "Verb + Noun" business name.
- Add a missing bpmn:startEvent / bpmn:endEvent (with correct sequenceFlow wiring) if flagged.
- Label unlabeled bpmn:exclusiveGateway elements with a yes/no question ending in "?".
- Label unlabeled outgoing branches of a gateway (e.g. "Yes"/"No").
- Fix dangling/unreachable sequenceFlow references; preserve existing element IDs where possible.
- Keep a full <bpmndi:BPMNDiagram> with valid, non-overlapping coordinates for every element.

{reconnect_rules}

{lane_rules}

{structural_rules}

Output ONLY the complete corrected BPMN 2.0 XML - no fences, no commentary - and it MUST
end with </bpmn:definitions>.
""".strip()


def fix_bpmn(xml: str, issues: list[dict], settings: AISettings) -> dict:
    """Hardened Fixer (items 8, 9, 10): handles BpmnParseError, retries via the
    centralized generate_valid_xml loop, and never crashes - on total failure it
    returns the ORIGINAL xml plus a warning so the caller/UI degrades gracefully."""
    issue_text = "\n".join(
        f"- [{i.get('fixAction', 'general')}] targetId={i.get('nodeId') or i.get('targetId')}: {i.get('title')} - {i.get('desc')}"
        for i in issues
    ) or "General cleanup pass - fix any structural, naming, or gateway-labeling defects."

    needs_lanes = any(
        (i.get("fixAction") == "add_lanes") or ("swimlane" in (i.get("title", "").lower()))
        for i in issues
    )

    system = _fix_system_prompt(issues) + language_instruction(settings.language)
    user = f"Current BPMN XML:\n{xml}\n\nIssues to fix:\n{issue_text}\n\nReturn the corrected XML."


    extra_ok = None
    extra_feedback = None
    if needs_lanes:
        extra_ok = lambda result: _lane_count(result["cleanedXml"]) > 0
        extra_feedback = (
            "The previous attempt did NOT add rendered swimlanes. You MUST add a "
            "<bpmn:collaboration> with a <bpmn:participant processRef=...>, a <bpmn:laneSet> "
            "assigning every flow node to a lane, and point the <bpmndi:BPMNPlane> bpmnElement "
            "at the COLLABORATION id with pool/lane BPMNShape bounds. Return the full XML."
        )

    result, warning, loops = generate_valid_xml(
        system, user, settings, LLM_TEMPERATURE_FIX,
        extra_ok=extra_ok, extra_feedback=extra_feedback,
    )

    if result is None:
        return {
            "xml": xml,
            "lint": None,
            "loops": loops,
            "warning": warning or "The fix could not be applied cleanly. Your original model was kept unchanged.",
        }
    out = {"xml": result["cleanedXml"], "lint": _public_lint(result), "loops": loops}
    if warning:
        out["warning"] = warning
    return out


def _lane_count(xml: str) -> int:
    import xml.etree.ElementTree as _ET
    try:
        root = _ET.fromstring(linter._strip_code_fences(xml))
    except Exception:
        return 0
    return sum(1 for el in root.iter() if (el.tag.split("}", 1)[-1] == "lane"))


def explain_bpmn(xml: str, persona: str, settings: AISettings) -> dict:
    persona = persona if persona in PERSONA_FRAMING else "auditor"
    summary = linter.summarize_for_llm(xml)
    lint_result = linter.lint(xml)
    system = f"""
You are the Explainer agent inside BPMN Copilot. You explain a business process model
to {PERSONA_FRAMING[persona]}.

You will receive a structured JSON summary of the process (nodes and flows) plus its
deterministic Process Health Score. Write a narrative grounded ONLY in the nodes/flows
given - do not invent steps that are not present.

Return a JSON object with exactly these keys:
{{
  "headline": "<one short bold-worthy headline for this persona>",
  "summary": "<2-3 sentence plain-language paragraph>",
  "bullets": ["<3-4 short, specific bullet points relevant to this persona>"]
}}
""".strip()
    user = json.dumps({
        "audience": persona,
        "processSummary": summary,
        "healthScore": lint_result["totalScore"],
        "band": lint_result["band"],
        "openIssueCount": lint_result["criticalCount"],
    })
    return chat_json(system + language_instruction(settings.language), user, settings, temperature=LLM_TEMPERATURE_EXPLAIN, max_tokens=EXPLAIN_MAX_TOKENS)



def automation_candidates(xml: str, settings: AISettings) -> list[dict]:
    summary = linter.summarize_for_llm(xml)
    tasks = [n for n in summary["nodes"] if n["type"] in (
        "task", "userTask", "serviceTask", "scriptTask", "businessRuleTask",
        "manualTask", "sendTask", "receiveTask",
    )]
    if not tasks:
        return []
    system = """
You are the Automation Opportunity agent inside BPMN Copilot. Given a list of process
tasks, assess each for RPA / Power Automate / API-integration suitability.

Return a JSON object: {"candidates": [
  {"id": "", "name": "", "roi": "High"|"Medium"|"Low",
   "tool": "API Integration"|"Power Automate Bot"|"RPA Bot"|"Not Recommended",
   "rationale": "<one concise sentence, specific to this task>"}
]}
Base ROI on how rule-based, repetitive, and system-facing the task is versus how much
human judgment it requires.
""".strip()
    data = chat_json(system + language_instruction(settings.language), json.dumps({"tasks": tasks}), settings, temperature=LLM_TEMPERATURE_AUTOMATE, max_tokens=AUTOMATE_MAX_TOKENS)

    return data.get("candidates", [])


def _ev(kind: str, **payload) -> dict:
    return {"type": kind, **payload}


def _public_lint(result: dict) -> dict:
    if not result:
        return result
    return {k: v for k, v in result.items() if k != "cleanedXml"}
