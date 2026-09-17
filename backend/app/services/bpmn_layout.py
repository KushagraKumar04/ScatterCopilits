"""Deterministic BPMN layout engine.

`bpmn-auto-layout@1.3.0` cannot lay out collaborations (pools + lanes) — its
`getProcess()` explicitly looks only for a <bpmn:Process>, ignoring any
<Collaboration>. So we compute the DI here ourselves, server-side, whenever
the model has a laneSet.

Layout model
------------
- Horizontal pool containing N horizontal lanes (equal height).
- Nodes assigned to a lane sit vertically centered inside that lane's band.
- Nodes are assigned to columns via longest-path from any start event.
- Edges use orthogonal (L-shaped) routing.
"""
from __future__ import annotations

from collections import deque
import xml.etree.ElementTree as ET

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

EVENT_TYPES = {
    "startEvent", "endEvent", "intermediateCatchEvent",
    "intermediateThrowEvent", "boundaryEvent",
}
TASK_TYPES = {
    "task", "userTask", "serviceTask", "scriptTask", "businessRuleTask",
    "manualTask", "sendTask", "receiveTask", "callActivity", "subProcess",
}
GATEWAY_TYPES = {
    "exclusiveGateway", "inclusiveGateway", "parallelGateway",
    "complexGateway", "eventBasedGateway",
}
FLOWNODE_TYPES = EVENT_TYPES | TASK_TYPES | GATEWAY_TYPES

NODE_SIZES: dict[str, tuple[int, int]] = {
    "startEvent": (36, 36),
    "endEvent": (36, 36),
    "intermediateCatchEvent": (36, 36),
    "intermediateThrowEvent": (36, 36),
    "boundaryEvent": (36, 36),
    "exclusiveGateway": (50, 50),
    "inclusiveGateway": (50, 50),
    "parallelGateway": (50, 50),
    "complexGateway": (50, 50),
    "eventBasedGateway": (50, 50),
}
DEFAULT_TASK_SIZE = (110, 80)

POOL_X = 40
POOL_Y = 40
LANE_LABEL_W = 30
LANE_HEIGHT = 150
COLUMN_GAP = 70
RIGHT_PADDING = 40


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _node_size(node_type: str) -> tuple[int, int]:
    return NODE_SIZES.get(node_type, DEFAULT_TASK_SIZE)


def _find(root: ET.Element, tag: str):
    for el in root.iter():
        if _local(el.tag) == tag:
            return el
    return None


def _find_lanes(process: ET.Element) -> list[dict]:
    lanes: list[dict] = []
    for el in process.iter():
        if _local(el.tag) == "lane":
            name = (el.get("name") or el.get("id") or "Lane").strip()
            refs: list[str] = []
            for child in el:
                if _local(child.tag) == "flowNodeRef":
                    ref = (child.text or "").strip()
                    if ref:
                        refs.append(ref)
            lanes.append({"id": el.get("id", ""), "name": name, "refs": refs})
    return lanes


def _collect_nodes(process: ET.Element) -> dict[str, dict]:
    nodes: dict[str, dict] = {}
    for el in process.iter():
        name = _local(el.tag)
        if name in FLOWNODE_TYPES:
            nid = el.get("id")
            if nid:
                nodes[nid] = {"id": nid, "type": name}
    return nodes


def _collect_flows(process: ET.Element) -> dict[str, dict]:
    flows: dict[str, dict] = {}
    for el in process.iter():
        if _local(el.tag) == "sequenceFlow":
            fid = el.get("id")
            if fid:
                flows[fid] = {
                    "id": fid,
                    "source": el.get("sourceRef", ""),
                    "target": el.get("targetRef", ""),
                }
    return flows


def _topological_columns(nodes: dict, flows: dict) -> dict[str, int]:
    """Assign each node a column = longest path length from any start node."""
    incoming = {nid: 0 for nid in nodes}
    edges: dict[str, list[str]] = {nid: [] for nid in nodes}
    for f in flows.values():
        if f["source"] in nodes and f["target"] in nodes:
            edges[f["source"]].append(f["target"])
            incoming[f["target"]] += 1

    col = {nid: 0 for nid in nodes}
    q = deque(n for n in nodes if incoming[n] == 0)
    seen = set(q)
    while q:
        u = q.popleft()
        for v in edges[u]:
            if col[u] + 1 > col[v]:
                col[v] = col[u] + 1
            incoming[v] -= 1
            if incoming[v] == 0 and v not in seen:
                seen.add(v)
                q.append(v)
    return col


def _clear_di(root: ET.Element) -> None:
    for parent in list(root):
        if _local(parent.tag) == "BPMNDiagram":
            root.remove(parent)


def _di_shape(
    shape_id: str,
    element_id: str,
    x: float, y: float, w: float, h: float,
    *,
    is_horizontal: bool | None = None,
    is_marker: bool | None = None,
) -> ET.Element:
    attrib = {"id": shape_id, "bpmnElement": element_id}
    if is_horizontal is not None:
        attrib["isHorizontal"] = "true" if is_horizontal else "false"
    if is_marker is not None:
        attrib["isMarkerVisible"] = "true" if is_marker else "false"
    shape = ET.Element(_q(BPMNDI_NS, "BPMNShape"), attrib)
    ET.SubElement(shape, _q(DC_NS, "Bounds"), {
        "x": str(int(x)), "y": str(int(y)),
        "width": str(int(w)), "height": str(int(h)),
    })
    return shape


def _di_edge(edge_id: str, element_id: str, waypoints: list[tuple[float, float]]) -> ET.Element:
    edge = ET.Element(_q(BPMNDI_NS, "BPMNEdge"), {"id": edge_id, "bpmnElement": element_id})
    for wx, wy in waypoints:
        ET.SubElement(edge, _q(DI_NS, "waypoint"), {
            "x": str(int(wx)), "y": str(int(wy)),
        })
    return edge


def apply_layout(root: ET.Element) -> bool:
    """Compute and install DI for a collaboration-with-lanes model.

    Returns True if DI was written, False if the model has no lanes (in which
    case the frontend's bpmn-auto-layout can handle a plain process).
    """
    process = _find(root, "process")
    collab = _find(root, "collaboration")
    if process is None or collab is None:
        return False

    lanes = _find_lanes(process)
    if not lanes:
        return False

    nodes = _collect_nodes(process)
    flows = _collect_flows(process)
    if not nodes:
        return False

    # Participant ID (goes on the pool BPMNShape's bpmnElement).
    participant_id = None
    for child in collab:
        if _local(child.tag) == "participant":
            participant_id = child.get("id")
            break
    participant_id = participant_id or "Participant_1"

    # Assign each node to a lane (default: first lane).
    node_lane: dict[str, int] = {nid: 0 for nid in nodes}
    for i, lane in enumerate(lanes):
        for ref in lane["refs"]:
            if ref in nodes:
                node_lane[ref] = i

    cols = _topological_columns(nodes, flows)

    # Column widths (max node width per column).
    col_widths: dict[int, int] = {}
    for nid, node in nodes.items():
        w, _ = _node_size(node["type"])
        c = cols[nid]
        col_widths[c] = max(col_widths.get(c, 0), w)

    # Column x offsets.
    col_x: dict[int, int] = {}
    x_cursor = POOL_X + LANE_LABEL_W + 30
    for c in sorted(col_widths):
        col_x[c] = x_cursor
        x_cursor += col_widths[c] + COLUMN_GAP

    content_w = x_cursor - (POOL_X + LANE_LABEL_W)
    pool_w = LANE_LABEL_W + content_w + RIGHT_PADDING
    pool_h = LANE_HEIGHT * len(lanes)

    # Node positions: centered in their column, centered in their lane band.
    node_pos: dict[str, tuple[int, int, int, int]] = {}
    for nid, node in nodes.items():
        w, h = _node_size(node["type"])
        c = cols[nid]
        col_w = col_widths[c]
        cx = col_x[c] + (col_w - w) // 2
        li = node_lane[nid]
        lane_top = POOL_Y + li * LANE_HEIGHT
        cy = lane_top + (LANE_HEIGHT - h) // 2
        node_pos[nid] = (cx, cy, w, h)

    # Rebuild DI from scratch.
    _clear_di(root)

    diagram = ET.Element(_q(BPMNDI_NS, "BPMNDiagram"), {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, _q(BPMNDI_NS, "BPMNPlane"), {
        "id": "BPMNPlane_1",
        "bpmnElement": collab.get("id"),
    })

    # 1) Pool shape (must come before lanes so it renders underneath).
    plane.append(_di_shape(
        f"{participant_id}_di", participant_id,
        POOL_X, POOL_Y, pool_w, pool_h,
        is_horizontal=True,
    ))

    # 2) Lane shapes.
    for i, lane in enumerate(lanes):
        lane_y = POOL_Y + i * LANE_HEIGHT
        plane.append(_di_shape(
            f"{lane['id']}_di", lane["id"],
            POOL_X, lane_y, pool_w, LANE_HEIGHT,
            is_horizontal=True,
        ))

    # 3) Node shapes.
    for nid, node in nodes.items():
        cx, cy, w, h = node_pos[nid]
        kwargs = {}
        if node["type"] == "exclusiveGateway":
            kwargs["is_marker"] = True
        plane.append(_di_shape(f"{nid}_di", nid, cx, cy, w, h, **kwargs))

    # 4) Edge waypoints (orthogonal L-shaped routing).
    for fid, f in flows.items():
        if f["source"] not in node_pos or f["target"] not in node_pos:
            continue
        sx, sy, sw, sh = node_pos[f["source"]]
        tx, ty, tw, th = node_pos[f["target"]]
        s_cy = sy + sh // 2
        t_cy = ty + th // 2

        if abs(s_cy - t_cy) < 5:
            wps = [(sx + sw, s_cy), (tx, t_cy)]
        else:
            mid_x = (sx + sw + tx) // 2
            wps = [
                (sx + sw, s_cy),
                (mid_x, s_cy),
                (mid_x, t_cy),
                (tx, t_cy),
            ]
        plane.append(_di_edge(f"{fid}_di", fid, wps))

    root.append(diagram)
    return True