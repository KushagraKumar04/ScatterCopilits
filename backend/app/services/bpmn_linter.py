from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional
from ..config import MAX_XML_BYTES

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

WEIGHTS = {
    "connectivity": 30,
    "completeness": 25,
    "gateway": 20,
    "naming": 15,
    "ownership": 10,
}

EVENT_TYPES = {"startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"}
TASK_TYPES = {
    "task", "userTask", "serviceTask", "scriptTask", "businessRuleTask",
    "manualTask", "sendTask", "receiveTask", "callActivity", "subProcess",
}
GATEWAY_TYPES = {"exclusiveGateway", "inclusiveGateway", "parallelGateway", "complexGateway", "eventBasedGateway"}

FLOWNODE_TYPES = EVENT_TYPES | TASK_TYPES | GATEWAY_TYPES

VAGUE_TERMS = {
    "handle", "process", "do", "stuff", "thing", "things", "check it", "someone",
    "manage", "it", "task", "activity", "step", "work", "review it", "fix it",
    "handle it", "process it", "check", "review", "update", "make", "sort out",
}


class BpmnParseError(Exception):
    pass


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _strip_code_fences(xml: str) -> str:
    text = (xml or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    start = text.find("<?xml")
    if start == -1:
        start = text.find("<bpmn:definitions")
    if start == -1:
        start = text.find("<definitions")
    if start > 0:
        text = text[start:]
    end = text.rfind("</bpmn:definitions>")
    if end == -1:
        end = text.rfind("</definitions>")
    if end != -1:
        close_at = text.find(">", end)
        if close_at != -1:
            text = text[: close_at + 1]
    return text.strip()


def _parse(xml: str) -> ET.Element:
    cleaned = _strip_code_fences(xml)
    if not cleaned:
        raise BpmnParseError("Empty document: no BPMN XML found.")
    if len(cleaned) > MAX_XML_BYTES:
        raise BpmnParseError(
            f"Document too large ({len(cleaned)} bytes, limit {MAX_XML_BYTES})."
        )
    low = cleaned.lower()
    if "<!doctype" in low or "<!entity" in low:
        raise BpmnParseError(
            "DTD/entity declarations are not allowed for security reasons."
        )
    try:
        return ET.fromstring(cleaned)
    except ET.ParseError as e:
        raise BpmnParseError(f"XML is not well-formed: {e}")



def _find_process(root: ET.Element) -> Optional[ET.Element]:
    for el in root.iter():
        if _local(el.tag) == "process":
            return el
    return None


def _collect(process: ET.Element) -> dict:
    nodes: dict[str, dict] = {}
    flows: list[dict] = []
    lanes = 0
    for el in process.iter():
        name = _local(el.tag)
        if name == "sequenceFlow":
            flows.append({
                "id": el.get("id", ""),
                "name": (el.get("name") or "").strip(),
                "source": el.get("sourceRef", ""),
                "target": el.get("targetRef", ""),
            })
        elif name == "lane":
            lanes += 1
        elif name in EVENT_TYPES or name in TASK_TYPES or name in GATEWAY_TYPES:
            nid = el.get("id", "")
            if nid:
                nodes[nid] = {
                    "id": nid,
                    "type": name,
                    "name": (el.get("name") or "").strip(),
                    "incoming": [],
                    "outgoing": [],
                }
    for f in flows:
        if f["source"] in nodes:
            nodes[f["source"]]["outgoing"].append(f)
        if f["target"] in nodes:
            nodes[f["target"]]["incoming"].append(f)
    return {"nodes": nodes, "flows": flows, "lanes": lanes}


def _category(nodes: dict, flows: list, lanes: int) -> tuple[dict, list]:
    issues: list[dict] = []
    node_ids = set(nodes.keys())

    starts = [n for n in nodes.values() if n["type"] == "startEvent"]
    ends = [n for n in nodes.values() if n["type"] == "endEvent"]
    tasks = [n for n in nodes.values() if n["type"] in TASK_TYPES]
    gateways = [n for n in nodes.values() if n["type"] in GATEWAY_TYPES]

    completeness = WEIGHTS["completeness"]
    if len(starts) == 0:
        completeness -= 13
        issues.append(_issue("critical", "Missing start event", "The process has no start event. Every process must have exactly one reachable start.", fix="add_start"))
    elif len(starts) > 1:
        completeness -= 6
        issues.append(_issue("warning", "Multiple start events", f"Found {len(starts)} start events. A single clear entry point is recommended.", node=starts[1]["id"]))
    if len(ends) == 0:
        completeness -= 12
        issues.append(_issue("critical", "Missing end event", "The process has no end event, so its completion is undefined.", fix="add_end"))
    completeness = max(0, completeness)

    connectivity = WEIGHTS["connectivity"]
    dangling = [f for f in flows if (f["source"] and f["source"] not in node_ids) or (f["target"] and f["target"] not in node_ids)]
    for f in dangling:
        connectivity -= 6
        issues.append(_issue("critical", "Broken sequence flow", f"Flow '{f['id'] or 'unnamed'}' references a node that does not exist.", target=f["id"], fix="reconnect"))
    for n in nodes.values():
        if n["type"] == "startEvent":
            if not n["outgoing"]:
                connectivity -= 5
                issues.append(_issue("critical", "Start event not connected", f"Start event '{_disp(n)}' has no outgoing flow.", node=n["id"], fix="reconnect"))
        elif n["type"] == "endEvent":
            if not n["incoming"]:
                connectivity -= 5
                issues.append(_issue("critical", "End event not connected", f"End event '{_disp(n)}' has no incoming flow.", node=n["id"], fix="reconnect"))
        else:
            if not n["incoming"] and not n["outgoing"]:
                connectivity -= 5
                issues.append(_issue("critical", "Disconnected node", f"'{_disp(n)}' is isolated with no connections.", node=n["id"], fix="reconnect"))
            elif not n["incoming"]:
                connectivity -= 3
                issues.append(_issue("warning", "Unreachable node", f"'{_disp(n)}' has no incoming flow and cannot be reached.", node=n["id"], fix="reconnect"))
            elif not n["outgoing"]:
                connectivity -= 3
                issues.append(_issue("warning", "Dead-end node", f"'{_disp(n)}' has no outgoing flow and leads nowhere.", node=n["id"], fix="reconnect"))
    if starts:
        reachable = _reachable(starts[0]["id"], nodes)
        orphans = [n for nid, n in nodes.items() if nid not in reachable]
        for n in orphans:
            connectivity -= 2
            issues.append(_issue("warning", "Not reachable from start", f"'{_disp(n)}' cannot be reached by following flows from the start event.", node=n["id"]))
    connectivity = max(0, connectivity)

    gateway = WEIGHTS["gateway"]
    if gateways:
        per = WEIGHTS["gateway"] / len(gateways)
        for g in gateways:
            branching = g["type"] == "exclusiveGateway" and len(g["outgoing"]) > 1
            if branching:
                if not g["name"]:
                    gateway -= per * 0.5
                    issues.append(_issue("critical", "Unlabeled decision gateway", "A branching gateway has no name. Name it as a yes/no question, e.g. 'Payment Valid?'.", node=g["id"], fix="label_gateway"))
                elif not g["name"].endswith("?"):
                    gateway -= per * 0.25
                    issues.append(_issue("warning", "Gateway is not a question", f"Gateway '{g['name']}' should be phrased as a question ending with '?'.", node=g["id"], fix="label_gateway"))
                unlabeled = [f for f in g["outgoing"] if not f["name"]]
                if unlabeled:
                    gateway -= per * 0.25
                    issues.append(_issue("warning", "Unlabeled gateway branches", f"Gateway '{_disp(g)}' has {len(unlabeled)} outgoing path(s) without a label (e.g. 'Yes'/'No').", node=g["id"], fix="label_branches"))
    gateway = max(0, gateway)

    naming = WEIGHTS["naming"]
    if tasks:
        per = WEIGHTS["naming"] / len(tasks)
        for t in tasks:
            nm = t["name"].lower().strip()
            if not nm:
                naming -= per
                issues.append(_issue("critical", "Unnamed task", "A task has no name. Use a clear 'Verb + Noun' label.", node=t["id"], fix="rename_task"))
            elif nm in VAGUE_TERMS or len(nm.split()) < 2:
                naming -= per * 0.6
                issues.append(_issue("warning", "Vague task name", f"'{t['name']}' is unclear. Use a specific 'Verb + Noun' name like 'Validate Request'.", node=t["id"], fix="rename_task"))
    naming = max(0, naming)

    ownership = WEIGHTS["ownership"] if lanes > 0 else 0
    if lanes == 0 and tasks:
        issues.append(_issue("warning", "No swimlanes defined", "The process has no lanes/pools, so task ownership is not explicit. Consider adding roles.", fix="add_lanes"))

    breakdown = {
        "connectivity": {"score": round(connectivity), "max": WEIGHTS["connectivity"]},
        "completeness": {"score": round(completeness), "max": WEIGHTS["completeness"]},
        "gateway": {"score": round(gateway), "max": WEIGHTS["gateway"]},
        "naming": {"score": round(naming), "max": WEIGHTS["naming"]},
        "ownership": {"score": round(ownership), "max": WEIGHTS["ownership"]},
    }
    return breakdown, issues


def _reachable(start_id: str, nodes: dict) -> set:
    seen: set[str] = set()
    stack = [start_id]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in nodes:
            continue
        seen.add(cur)
        for f in nodes[cur]["outgoing"]:
            if f["target"] not in seen:
                stack.append(f["target"])
    return seen


def _issue(kind: str, title: str, desc: str, node: str = None, target: str = None, fix: str = None) -> dict:
    _issue.counter = getattr(_issue, "counter", 0) + 1
    return {
        "id": f"iss_{_issue.counter}",
        "type": kind,
        "title": title,
        "desc": desc,
        "nodeId": node,
        "targetId": target,
        "fixAction": fix,
    }


def _disp(node: dict) -> str:
    return node["name"] or node["id"] or node["type"]


def _band(score: int) -> str:
    if score >= 90:
        return "Audit-Ready (90-100)"
    if score >= 70:
        return "Solid (70-89)"
    if score >= 50:
        return "Needs Work (50-69)"
    return "At Risk (< 50)"

def _structural_di_issues(root: ET.Element) -> tuple[list, int]:
    """Item 11 (duplicate IDs + lane reference integrity) and Item 13 (missing DI).
    Returns (issues, connectivity_penalty). Only fires on broken models, so a clean,
    well-formed BPMN yields ([], 0) and does not change the score."""
    issues: list = []
    penalty = 0

    all_ids: list[str] = []
    node_ids: set[str] = set()
    flow_ids: set[str] = set()
    lane_refs: list[str] = []
    di_refs: set[str] = set()

    for el in root.iter():
        name = _local(el.tag)
        eid = el.get("id")
        if eid:
            all_ids.append(eid)
        if name in FLOWNODE_TYPES and eid:
            node_ids.add(eid)
        elif name == "sequenceFlow":
            if eid:
                flow_ids.add(eid)
        elif name == "flowNodeRef":
            lane_refs.append((el.text or "").strip())
        elif name in ("BPMNShape", "BPMNEdge"):
            ref = el.get("bpmnElement")
            if ref:
                di_refs.add(ref)

    seen: set[str] = set()
    dupes: set[str] = set()
    for i in all_ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    for d in sorted(dupes):
        penalty += 6
        issues.append(_issue("critical", "Duplicate element ID",
            f"The ID '{d}' is used by more than one element. IDs must be unique.",
            node=d, fix="reconnect"))

    for ref in lane_refs:
        if ref and ref not in node_ids:
            penalty += 3
            issues.append(_issue("warning", "Lane references a missing node",
                f"A swimlane lists flowNodeRef '{ref}', but no such node exists.", node=ref))

    if di_refs:
        for nid in sorted(node_ids):
            if nid not in di_refs:
                penalty += 2
                issues.append(_issue("warning", "Element missing from diagram",
                    f"Node '{nid}' has no BPMNShape in the diagram, so it will not render.", node=nid))
        for fid in sorted(flow_ids):
            if fid and fid not in di_refs:
                penalty += 1
                issues.append(_issue("warning", "Connector missing from diagram",
                    f"Sequence flow '{fid}' has no BPMNEdge, so the connector will not render.", node=fid))

    return issues, penalty



def lint(xml: str) -> dict:
    _issue.counter = 0
    root = _parse(xml)
    process = _find_process(root)
    if process is None:
        raise BpmnParseError("No <bpmn:process> element found in the document.")
    collected = _collect(process)
    nodes, flows, lanes = collected["nodes"], collected["flows"], collected["lanes"]
    breakdown, issues = _category(nodes, flows, lanes)

    struct_issues, struct_penalty = _structural_di_issues(root)
    if struct_issues:
        issues.extend(struct_issues)
        conn = breakdown["connectivity"]
        conn["score"] = max(0, conn["score"] - struct_penalty)

    total = sum(part["score"] for part in breakdown.values())
    total = max(0, min(100, total))
    critical = sum(1 for i in issues if i["type"] == "critical")
    counts = {
        "startEvents": sum(1 for n in nodes.values() if n["type"] == "startEvent"),
        "endEvents": sum(1 for n in nodes.values() if n["type"] == "endEvent"),
        "tasks": sum(1 for n in nodes.values() if n["type"] in TASK_TYPES),
        "gateways": sum(1 for n in nodes.values() if n["type"] in GATEWAY_TYPES),
        "flows": len(flows),
    }
    return {
        "cleanedXml": _strip_code_fences(xml),
        "totalScore": total,
        "band": _band(total),
        "breakdown": breakdown,
        "issues": issues,
        "criticalCount": critical,
        "counts": counts,
    }


def summarize_for_llm(xml: str) -> dict:
    root = _parse(xml)
    process = _find_process(root)
    if process is None:
        raise BpmnParseError("No <bpmn:process> element found in the document.")
    collected = _collect(process)
    nodes = [
        {"id": n["id"], "type": n["type"], "name": n["name"]}
        for n in collected["nodes"].values()
    ]
    flows = [
        {"id": f["id"], "name": f["name"], "source": f["source"], "target": f["target"]}
        for f in collected["flows"]
    ]
    return {"nodes": nodes, "flows": flows, "lanes": collected["lanes"]}
