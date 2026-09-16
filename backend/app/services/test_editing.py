import xml.etree.ElementTree as ET

from . import bpmn_edit as E
from . import bpmn_diff as D

NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def _wrap(inner: str) -> str:
    return f'<?xml version="1.0"?><bpmn:definitions {NS}><bpmn:process id="P">{inner}</bpmn:process></bpmn:definitions>'


LINEAR = _wrap(
    '<bpmn:startEvent id="S" name="Start"><bpmn:outgoing>F1</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:task id="T1" name="Check Request"><bpmn:incoming>F1</bpmn:incoming><bpmn:outgoing>F2</bpmn:outgoing></bpmn:task>'
    '<bpmn:task id="T2" name="Notify Customer"><bpmn:incoming>F2</bpmn:incoming><bpmn:outgoing>F3</bpmn:outgoing></bpmn:task>'
    '<bpmn:endEvent id="E" name="Done"><bpmn:incoming>F3</bpmn:incoming></bpmn:endEvent>'
    '<bpmn:sequenceFlow id="F1" sourceRef="S" targetRef="T1"/>'
    '<bpmn:sequenceFlow id="F2" sourceRef="T1" targetRef="T2"/>'
    '<bpmn:sequenceFlow id="F3" sourceRef="T2" targetRef="E"/>'
)


def _well_formed(xml: str) -> bool:
    try:
        ET.fromstring(xml)
        return True
    except ET.ParseError:
        return False


def test_rename_preserves_id_and_changes_name():
    out = E.try_deterministic_edit(
        LINEAR,
        "rename 'Check Request' to 'Validate Request'",
    )
    assert out and out["op"] == "rename"
    assert 'name="Validate Request"' in out["xml"]
    assert 'id="T1"' in out["xml"]
    assert "Check Request" not in out["xml"]
    assert _well_formed(out["xml"])


def test_rename_without_quotes():
    out = E.try_deterministic_edit(
        LINEAR,
        "rename Notify Customer to Email Customer",
    )
    assert out and 'name="Email Customer"' in out["xml"]


def test_delete_middle_node_rewires():
    out = E.try_deterministic_edit(
        LINEAR,
        "delete 'Notify Customer'",
    )
    assert out and out["op"] == "delete"
    assert 'id="T2"' not in out["xml"]
    assert 'targetRef="E"' in out["xml"]
    assert _well_formed(out["xml"])


def test_delete_start_event_defers_to_llm():
    assert E.try_deterministic_edit(
        LINEAR,
        "delete 'Start'",
    ) is None


def test_branching_delete_defers_to_llm():
    br = _wrap(
        '<bpmn:exclusiveGateway id="G" name="ok?"/>'
        '<bpmn:task id="A" name="Path A"/><bpmn:task id="B" name="Path B"/>'
        '<bpmn:sequenceFlow id="F1" sourceRef="G" targetRef="A"/>'
        '<bpmn:sequenceFlow id="F2" sourceRef="G" targetRef="B"/>'
    )
    assert E.try_deterministic_edit(
        br,
        "delete 'ok?'",
    ) is None


def test_ambiguous_target_is_reported():
    amb = _wrap(
        '<bpmn:task id="A" name="Validate Request"/>'
        '<bpmn:task id="B" name="Reject Request"/>'
    )
    out = E.try_deterministic_edit(
        amb,
        "rename request to something",
    )
    assert out and "ambiguous" in out
    assert len(out["ambiguous"]) == 2


def test_complex_edit_falls_back():
    assert E.try_deterministic_edit(
        LINEAR,
        "add a manager approval after payment",
    ) is None


def test_unknown_target_falls_back():
    assert E.try_deterministic_edit(
        LINEAR,
        "rename 'Nope' to 'X'",
    ) is None


def test_multi_step_rename_then_delete():
    step1 = E.try_deterministic_edit(
        LINEAR,
        "rename 'Check Request' to 'Validate Request'",
    )
    assert step1

    step2 = E.try_deterministic_edit(
        step1["xml"],
        "delete 'Notify Customer'",
    )
    assert step2

    xml = step2["xml"]

    assert 'name="Validate Request"' in xml
    assert 'id="T2"' not in xml
    assert 'targetRef="E"' in xml
    assert _well_formed(xml)


def test_diff_detects_rename_only():
    after = E.try_deterministic_edit(
        LINEAR,
        "rename 'Check Request' to 'Validate Request'",
    )["xml"]

    d = D.diff_bpmn(LINEAR, after)

    assert d["counts"]["renamed_nodes"] == 1
    assert d["counts"]["added_nodes"] == 0
    assert d["counts"]["removed_nodes"] == 0


def test_unintended_change_flagged():
    after = E.try_deterministic_edit(
        LINEAR,
        "rename 'Check Request' to 'Validate Request'",
    )["xml"]

    warns = D.unintended_change_report(
        LINEAR,
        after,
        allowed_ids=["T2"],
    )

    assert any("T1" in w for w in warns)
    assert D.unintended_change_report(
        LINEAR,
        after,
        allowed_ids=["T1"],
    ) == []

from . import bpmn_linter as L

_NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'

def _wrap_lanes(inner: str, lanes_xml: str) -> str:
    return (
        f'<?xml version="1.0"?>'
        f'<bpmn:definitions {_NS}>'
        f'<bpmn:process id="P">'
        f'<bpmn:laneSet id="LS">{lanes_xml}</bpmn:laneSet>'
        f'{inner}'
        f'</bpmn:process></bpmn:definitions>'
    )


def test_linter_flags_end_event_with_multiple_incoming():
    xml = _wrap_lanes(
        '<bpmn:startEvent id="S"><bpmn:outgoing>F1</bpmn:outgoing><bpmn:outgoing>F3</bpmn:outgoing></bpmn:startEvent>'
        '<bpmn:task id="A" name="Do A"><bpmn:incoming>F1</bpmn:incoming><bpmn:outgoing>F2</bpmn:outgoing></bpmn:task>'
        '<bpmn:task id="B" name="Do B"><bpmn:incoming>F3</bpmn:incoming><bpmn:outgoing>F4</bpmn:outgoing></bpmn:task>'
        '<bpmn:endEvent id="E" name="Done">'
        '<bpmn:incoming>F2</bpmn:incoming>'
        '<bpmn:incoming>F4</bpmn:incoming>'
        '</bpmn:endEvent>'
        '<bpmn:sequenceFlow id="F1" sourceRef="S" targetRef="A"/>'
        '<bpmn:sequenceFlow id="F3" sourceRef="S" targetRef="B"/>'
        '<bpmn:sequenceFlow id="F2" sourceRef="A" targetRef="E"/>'
        '<bpmn:sequenceFlow id="F4" sourceRef="B" targetRef="E"/>',
        '<bpmn:lane id="L1" name="Actor">'
        '<bpmn:flowNodeRef>A</bpmn:flowNodeRef>'
        '<bpmn:flowNodeRef>B</bpmn:flowNodeRef>'
        '</bpmn:lane>',
    )
    result = L.lint(xml)
    titles = [i["title"] for i in result["issues"]]
    assert "End event merges multiple flows without a joining gateway" in titles


def test_linter_flags_lane_with_only_end_event():
    xml = _wrap_lanes(
        '<bpmn:startEvent id="S" name="Start"><bpmn:outgoing>F1</bpmn:outgoing></bpmn:startEvent>'
        '<bpmn:task id="T1" name="Work"><bpmn:incoming>F1</bpmn:incoming><bpmn:outgoing>F2</bpmn:outgoing></bpmn:task>'
        '<bpmn:endEvent id="E1" name="Done"><bpmn:incoming>F2</bpmn:incoming></bpmn:endEvent>'
        '<bpmn:sequenceFlow id="F1" sourceRef="S" targetRef="T1"/>'
        '<bpmn:sequenceFlow id="F2" sourceRef="T1" targetRef="E1"/>',
        '<bpmn:lane id="L1" name="Worker">'
        '<bpmn:flowNodeRef>T1</bpmn:flowNodeRef>'
        '</bpmn:lane>'
        '<bpmn:lane id="L2" name="Done-only">'
        '<bpmn:flowNodeRef>E1</bpmn:flowNodeRef>'
        '</bpmn:lane>',
    )
    result = L.lint(xml)
    titles = [i["title"] for i in result["issues"]]
    assert "Swimlane contains only an end event" in titles


def test_linter_flags_lane_with_no_tasks():
    xml = _wrap_lanes(
        '<bpmn:startEvent id="S" name="Start"><bpmn:outgoing>F1</bpmn:outgoing></bpmn:startEvent>'
        '<bpmn:exclusiveGateway id="G" name="Ok?">'
        '<bpmn:incoming>F1</bpmn:incoming>'
        '<bpmn:outgoing>F2</bpmn:outgoing>'
        '</bpmn:exclusiveGateway>'
        '<bpmn:endEvent id="E1" name="Done"><bpmn:incoming>F2</bpmn:incoming></bpmn:endEvent>'
        '<bpmn:sequenceFlow id="F1" sourceRef="S" targetRef="G"/>'
        '<bpmn:sequenceFlow id="F2" name="Yes" sourceRef="G" targetRef="E1"/>',
        '<bpmn:lane id="L1" name="Events-only">'
        '<bpmn:flowNodeRef>S</bpmn:flowNodeRef>'
        '<bpmn:flowNodeRef>G</bpmn:flowNodeRef>'
        '<bpmn:flowNodeRef>E1</bpmn:flowNodeRef>'
        '</bpmn:lane>',
    )
    result = L.lint(xml)
    titles = [i["title"] for i in result["issues"]]
    assert "Swimlane has no tasks" in titles