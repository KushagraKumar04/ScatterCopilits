from __future__ import annotations

import re
import xml.etree.ElementTree as ET

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

EVENT_TYPES = {
    "startEvent",
    "endEvent",
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "boundaryEvent",
}

TASK_TYPES = {
    "task",
    "userTask",
    "serviceTask",
    "scriptTask",
    "businessRuleTask",
    "manualTask",
    "sendTask",
    "receiveTask",
    "callActivity",
    "subProcess",
}

GATEWAY_TYPES = {
    "exclusiveGateway",
    "inclusiveGateway",
    "parallelGateway",
    "complexGateway",
    "eventBasedGateway",
}

FLOWNODE_TYPES = EVENT_TYPES | TASK_TYPES | GATEWAY_TYPES


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _q(pattern_body: str) -> str:
    return pattern_body


_RENAME_RES = [
    re.compile(
        r"^\s*rename\s+(?:the\s+)?['\"]?(?P<from>.+?)['\"]?\s+to\s+['\"]?(?P<to>.+?)['\"]?\s*$",
        re.I,
    ),
    re.compile(
        r"^\s*(?:re)?label\s+(?:the\s+)?(?:gateway\s+)?['\"]?(?P<from>.+?)['\"]?\s+(?:as|to)\s+['\"]?(?P<to>.+?)['\"]?\s*$",
        re.I,
    ),
]

_DELETE_RES = [
    re.compile(
        r"^\s*(?:delete|remove)\s+(?:the\s+)?['\"]?(?P<name>.+?)['\"]?(?:\s+(?:task|step|node|activity|event|gateway))?\s*$",
        re.I,
    ),
]

_STOPWORDS = {
    "the",
    "a",
    "an",
    "task",
    "step",
    "node",
    "activity",
    "event",
    "gateway",
    "this",
    "that",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _find_nodes_by_name(nodes: list[dict], phrase: str) -> list[dict]:
    p = _norm(phrase)
    if not p:
        return []

    exact = [n for n in nodes if _norm(n["name"]) == p]
    if exact:
        return exact

    core = " ".join(w for w in p.split() if w not in _STOPWORDS).strip()
    if not core:
        return []

    return [n for n in nodes if core in _norm(n["name"])]


def _collect_nodes(root: ET.Element) -> list[dict]:
    out = []

    for el in root.iter():
        if _local(el.tag) in FLOWNODE_TYPES:
            out.append(
                {
                    "id": el.get("id", ""),
                    "type": _local(el.tag),
                    "name": (el.get("name") or "").strip(),
                    "el": el,
                }
            )

    return out


def _register_ns():
    ET.register_namespace("bpmn", BPMN_NS)
    ET.register_namespace(
        "bpmndi",
        "http://www.omg.org/spec/BPMN/20100524/DI",
    )
    ET.register_namespace(
        "dc",
        "http://www.omg.org/spec/DD/20100524/DC",
    )
    ET.register_namespace(
        "di",
        "http://www.omg.org/spec/DD/20100524/DI",
    )


def _serialize(root: ET.Element) -> str:
    _register_ns()
    body = ET.tostring(root, encoding="unicode")

    if not body.lstrip().startswith("<?xml"):
        body = '<?xml version="1.0" encoding="UTF-8"?>\n' + body

    return body


def try_deterministic_edit(xml: str, instruction: str):
    instruction = (instruction or "").strip()

    if not instruction:
        return None

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    nodes = _collect_nodes(root)

    for rx in _RENAME_RES:
        m = rx.match(instruction)

        if m:
            frm, to = m.group("from"), m.group("to")
            matches = _find_nodes_by_name(nodes, frm)

            if len(matches) == 0:
                return None

            if len(matches) > 1:
                return {
                    "ambiguous": [n["name"] or n["id"] for n in matches],
                    "op": "rename",
                }

            node = matches[0]
            old_name = node["name"]
            node["el"].set("name", to.strip())

            if node["el"].get("name") != to.strip():
                return None

            return {
                "xml": _serialize(root),
                "op": "rename",
                "detail": f"Renamed '{old_name or node['id']}' to '{to.strip()}'.",
                "targetId": node["id"],
            }

    for rx in _DELETE_RES:
        m = rx.match(instruction)

        if m:
            name = m.group("name")
            matches = _find_nodes_by_name(nodes, name)

            if len(matches) == 0:
                return None

            if len(matches) > 1:
                return {
                    "ambiguous": [n["name"] or n["id"] for n in matches],
                    "op": "delete",
                }

            node = matches[0]

            if node["type"] in ("startEvent", "endEvent"):
                return None

            result = _delete_node_and_rewire(root, node["id"])

            if not result:
                return None

            return {
                "xml": _serialize(root),
                "op": "delete",
                "detail": f"Removed '{node['name'] or node['id']}' and reconnected the flow.",
                "targetId": node["id"],
            }

    return None


def _delete_node_and_rewire(root: ET.Element, node_id: str) -> bool:
    process = None

    for el in root.iter():
        if _local(el.tag) == "process":
            process = el
            break

    if process is None:
        return False

    flows = [
        el
        for el in root.iter()
        if _local(el.tag) == "sequenceFlow"
    ]

    incoming = [
        f for f in flows
        if f.get("targetRef") == node_id
    ]

    outgoing = [
        f for f in flows
        if f.get("sourceRef") == node_id
    ]

    if len(incoming) != 1 or len(outgoing) != 1:
        return False

    src = incoming[0].get("sourceRef")
    dst = outgoing[0].get("targetRef")

    incoming[0].set("targetRef", dst)

    out_id = outgoing[0].get("id")

    _remove_by_predicate(
        root,
        lambda e: (
            (
                _local(e.tag) in FLOWNODE_TYPES
                and e.get("id") == node_id
            )
            or (
                _local(e.tag) == "sequenceFlow"
                and e.get("id") == out_id
            )
            or (
                _local(e.tag) in ("BPMNShape",)
                and e.get("bpmnElement") == node_id
            )
            or (
                _local(e.tag) in ("BPMNEdge",)
                and e.get("bpmnElement") == out_id
            )
        ),
    )

    return True


def _remove_by_predicate(root: ET.Element, pred):
    parent_map = {
        c: p
        for p in root.iter()
        for c in p
    }

    to_remove = [
        el
        for el in root.iter()
        if pred(el)
    ]

    for el in to_remove:
        parent = parent_map.get(el)

        if parent is not None:
            parent.remove(el)