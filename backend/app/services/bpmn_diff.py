from __future__ import annotations

import xml.etree.ElementTree as ET

FLOWNODE_TYPES = {
    "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent",
    "task", "userTask", "serviceTask", "scriptTask", "businessRuleTask", "manualTask",
    "sendTask", "receiveTask", "callActivity", "subProcess",
    "exclusiveGateway", "inclusiveGateway", "parallelGateway", "complexGateway", "eventBasedGateway",
}


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _model(xml: str) -> dict:
    root = ET.fromstring(xml)
    nodes = {}
    flows = {}

    for el in root.iter():
        name = _local(el.tag)

        if name in FLOWNODE_TYPES:
            nid = el.get("id")
            if nid:
                nodes[nid] = {
                    "type": name,
                    "name": (el.get("name") or "").strip(),
                }

        elif name == "sequenceFlow":
            fid = el.get("id")
            if fid:
                flows[fid] = {
                    "source": el.get("sourceRef", ""),
                    "target": el.get("targetRef", ""),
                    "name": (el.get("name") or "").strip(),
                }

    return {"nodes": nodes, "flows": flows}


def diff_bpmn(before_xml: str, after_xml: str) -> dict:
    b = _model(before_xml)
    a = _model(after_xml)

    bn, an = b["nodes"], a["nodes"]
    bf, af = b["flows"], a["flows"]

    added_nodes = [
        {"id": i, **an[i]}
        for i in an
        if i not in bn
    ]

    removed_nodes = [
        {"id": i, **bn[i]}
        for i in bn
        if i not in an
    ]

    renamed_nodes = [
        {
            "id": i,
            "from": bn[i]["name"],
            "to": an[i]["name"],
        }
        for i in an
        if i in bn and an[i]["name"] != bn[i]["name"]
    ]

    retyped_nodes = [
        {
            "id": i,
            "from": bn[i]["type"],
            "to": an[i]["type"],
        }
        for i in an
        if i in bn and an[i]["type"] != bn[i]["type"]
    ]

    added_flows = [
        {"id": i, **af[i]}
        for i in af
        if i not in bf
    ]

    removed_flows = [
        {"id": i, **bf[i]}
        for i in bf
        if i not in af
    ]

    rewired_flows = [
        {
            "id": i,
            "from": (bf[i]["source"], bf[i]["target"]),
            "to": (af[i]["source"], af[i]["target"]),
        }
        for i in af
        if i in bf
        and (af[i]["source"], af[i]["target"])
        != (bf[i]["source"], bf[i]["target"])
    ]

    parts = []

    if added_nodes:
        parts.append(f"+{len(added_nodes)} node(s)")

    if removed_nodes:
        parts.append(f"-{len(removed_nodes)} node(s)")

    if renamed_nodes:
        parts.append(f"{len(renamed_nodes)} renamed")

    if retyped_nodes:
        parts.append(f"{len(retyped_nodes)} retyped")

    if added_flows:
        parts.append(f"+{len(added_flows)} flow(s)")

    if removed_flows:
        parts.append(f"-{len(removed_flows)} flow(s)")

    if rewired_flows:
        parts.append(f"{len(rewired_flows)} rewired")

    summary = ", ".join(parts) if parts else "no semantic changes"

    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "renamed_nodes": renamed_nodes,
        "retyped_nodes": retyped_nodes,
        "added_flows": added_flows,
        "removed_flows": removed_flows,
        "rewired_flows": rewired_flows,
        "summary": summary,
        "counts": {
            "added_nodes": len(added_nodes),
            "removed_nodes": len(removed_nodes),
            "renamed_nodes": len(renamed_nodes),
            "retyped_nodes": len(retyped_nodes),
            "added_flows": len(added_flows),
            "removed_flows": len(removed_flows),
            "rewired_flows": len(rewired_flows),
        },
    }


def unintended_change_report(
    before_xml: str,
    after_xml: str,
    allowed_ids,
) -> list[str]:
    allowed = set(allowed_ids or [])
    d = diff_bpmn(before_xml, after_xml)
    warnings = []

    for n in d["removed_nodes"]:
        if n["id"] not in allowed:
            warnings.append(
                f"Unrelated node removed: '{n['name'] or n['id']}' ({n['id']})."
            )

    for r in d["renamed_nodes"]:
        if r["id"] not in allowed:
            warnings.append(
                f"Unrelated node renamed: '{r['from']}' -> '{r['to']}' ({r['id']})."
            )

    for r in d["retyped_nodes"]:
        if r["id"] not in allowed:
            warnings.append(
                f"Unrelated node changed type: {r['from']} -> {r['to']} ({r['id']})."
            )

    for f in d["rewired_flows"]:
        if f["id"] not in allowed:
            warnings.append(
                f"Unrelated flow rewired: {f['id']} {f['from']} -> {f['to']}."
            )

    return warnings