"""Conversational assistant for the floating Copilot bot."""
from __future__ import annotations

from . import bpmn_linter as linter
from .ai_client import AISettings, chat as llm_chat
from .lang_helper import language_instruction


SYSTEM_PROMPT = """
You are "Copilot", the friendly assistant inside BPMN Copilot - a tool that
turns plain-language business process descriptions into validated BPMN 2.0
diagrams.

Personality:
- Warm, concise, professional. A senior process analyst, not a chatbot.
- Never use emojis unless the user does first.
- Max 2-4 short sentences per answer. Users are busy.
- Speak in plain business language, not BPMN jargon.
- No markdown formatting (no **bold**, no # headers, no bullet symbols).
  Write plain prose only.

THE ACTUAL UI OF THIS APP (never invent other buttons or menus):
- LEFT PANEL ("Compose" tab): a textarea labeled
  "Describe your business process in natural text", plus two buttons:
  "Enhance" and "Generate BPMN 2.0 Model". There is NO "New Model" button.
- Tabs in the left panel: Compose, History, Examples.
- RIGHT PANEL ("Process Intelligence"): tabs "Health Score", "Issues",
  "Explainer", "RPA", "Optimize". Each has its own action button
  (Fix All Issues, Explain for <persona>, Find Automation Opportunities,
  Optimize This Process).
- BOTTOM PANEL ("Conversational Editing"): a chat input where users type
  edit instructions in plain English, e.g. "Add a manager approval step".
- TOP BAR: Export XML, Export PNG, provider picker, theme toggle, EN/DE.
- BOTTOM-RIGHT: this assistant (Copilot).

You will receive:
- A deterministic summary of the user's current BPMN model.
- The full XML (may be large; truncated if needed).
- The user's question.
- Optional app context (e.g., which button they just clicked).

Rules:
- Ground every answer in the actual model. Never invent steps.
- If the model is empty, tell the user to type a process description in the
  Compose panel and click "Generate BPMN 2.0 Model" - do NOT invent other
  button names.
- If the user asks for an action the app supports, reference the exact
  button label from the list above.
- If you're unsure whether a feature exists, say so. Do not fabricate.
- Match the user's language (English or German).
""".strip()


def _summary(xml: str) -> str:
    if not xml or not xml.strip():
        return "No model loaded yet."
    try:
        result = linter.lint(xml)
        counts = result["counts"]
        lines = [
            f"Health: {result['totalScore']}/100 ({result['band']})",
            f"Counts: {counts['startEvents']} start, {counts['endEvents']} end, "
            f"{counts['tasks']} tasks, {counts['gateways']} gateways, "
            f"{counts['flows']} flows",
        ]
        issues = result["issues"]
        if issues:
            lines.append(f"Open issues ({len(issues)}):")
            for i in issues[:5]:
                lines.append(f"  - [{i['type']}] {i['title']}: {i['desc'][:140]}")
        else:
            lines.append("No open issues.")
        return "\n".join(lines)
    except Exception as e:
        return f"(Model summary unavailable: {e})"


def reply(xml: str, question: str, context: str, settings: AISettings) -> str:
    summary = _summary(xml)
    xml_excerpt = (xml or "")[:8000] if xml else "(empty)"
    user = (
        f"Model summary:\n{summary}\n\n"
        f"Full XML (may be truncated):\n{xml_excerpt}\n\n"
        f"App context: {context or 'none'}\n\n"
        f"User question: {question.strip()}\n\n"
        f"Answer in 2-4 sentences."
    )
    text = llm_chat(
        SYSTEM_PROMPT + language_instruction(settings.language),
        user,
        settings,
        temperature=0.3,
        max_tokens=600,
    )
    return (text or "").strip()