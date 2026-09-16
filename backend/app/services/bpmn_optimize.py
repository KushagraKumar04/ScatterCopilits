from __future__ import annotations

import json
from .lang_helper import language_instruction

from . import bpmn_diff
from . import bpmn_linter as linter

MAX_OPTIMIZE_LOOPS = 3
OPTIMIZE_MAX_TOKENS = 16000
REVIEW_MAX_TOKENS = 1600

OPTIMIZE_RULES = """
You are the Optimization agent inside BPMN Copilot. You receive an EXISTING, valid
BPMN 2.0 process. Propose an OPTIMIZED version of the SAME process that is faster,
simpler, and more automation-ready - without changing its business purpose.

Look for opportunities to:
- Merge or remove redundant/duplicate approval or review steps that add delay without
  adding control (e.g. two consecutive manual reviews of the same thing).
- Remove dead-end tasks, unreachable steps, or steps that do not affect the outcome.
- Simplify overly branchy decision logic where it does not reflect a real business rule.
- Rename vague tasks to clear "Verb + Noun" business names.
- Flag tasks that are good automation candidates by naming them clearly and keeping
  them as single, well-scoped steps (do not change the automation agent's job, just make
  the model automation-friendly).

STRICT RULES:
- Preserve the process's business intent and outcome. Do NOT remove a step that changes
  what the business actually decides or produces. When unsure, keep the step.
- Preserve existing element IDs for anything you do not change.
- The result MUST remain a complete, valid BPMN 2.0 document: exactly one reachable
  start event, at least one reachable end event, all sequenceFlows wired correctly.
- Output ONLY the raw BPMN 2.0 XML - no markdown fences, no commentary, no explanation.
  Do NOT include a <bpmndi:BPMNDiagram> section; layout is generated separately.
- The document MUST end with </bpmn:definitions>.
""".strip()

REVIEW_RULES = """
You are the Process Review agent inside BPMN Copilot. You write a business-friendly
review report for a process model, for an audience of process owners and managers.

You will receive a structured JSON summary of the process (nodes and flows) and its
deterministic Process Health Score and issue list. Base your report ONLY on what is
in that data - do not invent steps, systems, or risks that are not implied by it.

Return a JSON object with EXACTLY these keys:
{
  "summary": "<2-3 sentence plain-language overview of what this process does>",
  "bottlenecks": ["<short phrase naming a likely bottleneck step and why>", ...],
  "risks": ["<short phrase naming a compliance/control/quality risk>", ...],
  "missingSteps": ["<short phrase naming something a process like this typically needs but this model lacks>", ...],
  "recommendations": ["<short, concrete, actionable improvement>", ...],
  "automationOpportunities": ["<short phrase naming a task well-suited to automation and why>", ...]
}
Keep each list to at most 4 items. If a category has nothing meaningful to say, return
an empty list for it rather than inventing content.
""".strip()


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
            "\n\nYour previous output was CUT OFF before the closing </bpmn:definitions> "
            "tag. Produce a MORE COMPACT but COMPLETE document ending in </bpmn:definitions>."
        )
    return f"\n\nThe previous output failed to parse: {error}. Return a COMPLETE, well-formed BPMN 2.0 XML document only."


def _public_lint(result: dict) -> dict:
    if not result:
        return result
    return {k: v for k, v in result.items() if k != "cleanedXml"}


def _ev(kind: str, **payload) -> dict:
    return {"type": kind, **payload}


def optimize_process_events(xml: str, settings, chat_fn, chat_json_fn):
    try:
        before_lint = linter.lint(xml)
    except linter.BpmnParseError as e:
        yield _ev("result", data={"xml": None, "lint": None, "loops": 0,
                                  "warning": f"The current model is not valid BPMN, so it can't be optimized: {e}"})
        return

    user = f"Current BPMN XML:\n{xml}\n\nPropose an optimized version now."
    feedback = ""
    last_xml = None
    last_lint = None
    warning = None

    yield _ev("agent", agent="optimizer", status="active")
    yield _ev("log", line="[Optimizer] Analyzing the process for redundant steps, dead-ends, and automation-readiness.")

    for loop in range(1, MAX_OPTIMIZE_LOOPS + 1):
        raw = chat_fn(OPTIMIZE_RULES + language_instruction(settings.language), user + feedback, settings, temperature=0.3, max_tokens=OPTIMIZE_MAX_TOKENS)

        try:
            result = linter.lint(raw)
        except linter.BpmnParseError as e:
            warning = f"Optimization attempt {loop} produced invalid XML: {e}"
            yield _ev("log", line=f"[Validator] {warning}", level="error")
            feedback = _retry_feedback(raw, str(e))
            continue
        last_xml = result["cleanedXml"]
        last_lint = result
        yield _ev("log", line=f"[Validator] Optimized model health {result['totalScore']}/100 ({result['band']}).", level="success")
        break

    yield _ev("agent", agent="optimizer", status="done")

    if last_xml is None:
        yield _ev("result", data={"xml": None, "lint": None, "loops": MAX_OPTIMIZE_LOOPS,
                                  "warning": warning or "Could not produce a valid optimized version. Your original model was kept."})
        return

    diff = bpmn_diff.diff_bpmn(xml, last_xml)
    yield _ev("agent", agent="explainer", status="active")
    yield _ev("log", line="[Explainer] Summarizing what changed and why.")
    rationale = _optimization_rationale(diff, before_lint, last_lint, chat_json_fn, settings)
    yield _ev("agent", agent="explainer", status="done")

    yield _ev("result", data={
        "xml": last_xml,
        "lint": _public_lint(last_lint),
        "beforeLint": _public_lint(before_lint),
        "diff": diff,
        "rationale": rationale,
        "loops": loop,
    })


def optimize_process(xml: str, settings, chat_fn, chat_json_fn) -> dict:
    final = None
    for event in optimize_process_events(xml, settings, chat_fn, chat_json_fn):
        if event["type"] == "result":
            final = event["data"]
    return final or {"xml": None, "lint": None, "loops": 0, "warning": "Optimization produced no result."}


def _optimization_rationale(diff: dict, before_lint: dict, after_lint: dict, chat_json_fn, settings) -> dict:
    system = """
You are the Explainer agent inside BPMN Copilot. You will receive a computed diff
between a process BEFORE and AFTER optimization (added/removed/renamed nodes and
flows) plus both Health Scores. Explain the change in plain business language, based
ONLY on the diff data given - do not claim any change that is not listed in the diff.

Return a JSON object with exactly these keys:
{
  "headline": "<one short headline summarizing the improvement>",
  "changes": ["<one short sentence per meaningful change, grounded in the diff>"],
  "impact": "<1-2 sentence business-friendly statement of the benefit>"
}
""".strip()
    user = json.dumps({
        "diff": diff,
        "healthBefore": before_lint["totalScore"],
        "healthAfter": after_lint["totalScore"],
        "bandBefore": before_lint["band"],
        "bandAfter": after_lint["band"],
    })
    try:
        return chat_json_fn(system + language_instruction(settings.language), user, settings, temperature=0.2, max_tokens=700)

    except Exception:
        return {
            "headline": f"Health {before_lint['totalScore']} -> {after_lint['totalScore']}",
            "changes": [diff["summary"]],
            "impact": "See the before/after comparison for details.",
        }


def review_process(xml: str, settings, chat_json_fn) -> dict:
    summary = linter.summarize_for_llm(xml)
    lint_result = linter.lint(xml)
    user = json.dumps({
        "processSummary": summary,
        "healthScore": lint_result["totalScore"],
        "band": lint_result["band"],
        "issues": [{"title": i["title"], "type": i["type"]} for i in lint_result["issues"]],
        "counts": lint_result["counts"],
    })
    report = chat_json_fn(REVIEW_RULES + language_instruction(settings.language), user, settings, temperature=0.3, max_tokens=REVIEW_MAX_TOKENS)
    for key in ("summary", "bottlenecks", "risks", "missingSteps", "recommendations", "automationOpportunities"):
        report.setdefault(key, [] if key != "summary" else "")
    report["healthScore"] = lint_result["totalScore"]
    report["band"] = lint_result["band"]
    return report
