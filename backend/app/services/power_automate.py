from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from . import bpmn_linter as linter

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_SOLUTION_VERSION = "1.0.0.0"


def _safe_action_name(name: str, used: set) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", (name or "").strip()).strip("_")
    if not base:
        base = "Action"
    if not base[0].isalpha():
        base = "A_" + base
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}_{n}"
        n += 1
    used.add(candidate)
    return candidate


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _tool_to_hint(name_lower: str) -> dict:
    if any(k in name_lower for k in ("email", "notify", "notification", "send mail", "mail")):
        return {"connector": "Office 365 Outlook", "suggestedAction": "Send an email (V2)"}
    if any(k in name_lower for k in ("approve", "approval", "review", "sign off", "sign-off")):
        return {"connector": "Approvals", "suggestedAction": "Start and wait for an approval"}
    if any(k in name_lower for k in ("teams", "message", "post")):
        return {"connector": "Microsoft Teams", "suggestedAction": "Post message in a chat or channel"}
    if any(k in name_lower for k in ("sharepoint", "list", "record", "log", "store", "save", "calendar")):
        return {"connector": "SharePoint", "suggestedAction": "Create item"}
    if any(k in name_lower for k in ("excel", "spreadsheet", "row")):
        return {"connector": "Excel Online", "suggestedAction": "Add a row into a table"}
    if any(k in name_lower for k in ("api", "http", "service", "system", "verify", "validate", "check")):
        return {"connector": "HTTP", "suggestedAction": "HTTP request"}
    if any(k in name_lower for k in ("sql", "database", "db")):
        return {"connector": "SQL Server", "suggestedAction": "Execute a stored procedure"}
    return {"connector": "Compose", "suggestedAction": "Compose / placeholder step"}


def _build_graph(xml: str) -> dict:
    cleaned = linter._strip_code_fences(xml)
    root = ET.fromstring(cleaned)
    process = linter._find_process(root)
    if process is None:
        raise linter.BpmnParseError("No <bpmn:process> element found in the document.")

    nodes: dict[str, dict] = {}
    flows: list[dict] = []
    for el in process.iter():
        name = _local(el.tag)
        if name == "sequenceFlow":
            flows.append({
                "id": el.get("id", ""),
                "name": (el.get("name") or "").strip(),
                "source": el.get("sourceRef", ""),
                "target": el.get("targetRef", ""),
            })
        elif name in linter.EVENT_TYPES or name in linter.TASK_TYPES or name in linter.GATEWAY_TYPES:
            nid = el.get("id", "")
            if nid:
                nodes[nid] = {
                    "id": nid,
                    "type": name,
                    "name": (el.get("name") or "").strip(),
                    "outgoing": [],
                    "incoming": [],
                }
    for f in flows:
        if f["source"] in nodes:
            nodes[f["source"]]["outgoing"].append(f)
        if f["target"] in nodes:
            nodes[f["target"]]["incoming"].append(f)
    return {"nodes": nodes, "flows": flows}


def _topological_order(nodes: dict, starts: list) -> list:
    seen: set = set()
    order: list = []
    queue = [s["id"] for s in starts] or (list(nodes.keys())[:1])
    while queue:
        cur = queue.pop(0)
        if cur in seen or cur not in nodes:
            continue
        seen.add(cur)
        order.append(nodes[cur])
        for f in nodes[cur]["outgoing"]:
            if f["target"] not in seen:
                queue.append(f["target"])
    for nid, node in nodes.items():
        if nid not in seen:
            order.append(node)
    return order


def _prepend_decision_var(actions: dict) -> dict:
    if not any(a.get("type") == "Switch" for a in actions.values()):
        return actions
    init = {
        "Initialize_decision": {
            "type": "InitializeVariable",
            "inputs": {"variables": [{"name": "decision", "type": "string", "value": ""}]},
            "runAfter": {},
        }
    }
    roots = [name for name, a in actions.items() if not a.get("runAfter")]
    rebuilt = dict(init)
    for name, a in actions.items():
        if name in roots and not a.get("runAfter"):
            a = dict(a)
            a["runAfter"] = {"Initialize_decision": ["Succeeded"]}
        rebuilt[name] = a
    return rebuilt


def _build_definition(xml: str) -> dict:
    graph = _build_graph(xml)
    nodes = graph["nodes"]

    starts = [n for n in nodes.values() if n["type"] == "startEvent"]
    tasks = [n for n in nodes.values() if n["type"] in linter.TASK_TYPES]
    gateways = [n for n in nodes.values() if n["type"] in linter.GATEWAY_TYPES]

    used_names: set = set()
    actions: dict = {}
    ordered = _topological_order(nodes, starts)
    prev_action = None

    for node in ordered:
        if node["type"] in linter.TASK_TYPES:
            action_name = _safe_action_name(node["name"] or node["id"], used_names)
            hint = _tool_to_hint((node["name"] or "").lower())
            run_after = {prev_action: ["Succeeded"]} if prev_action else {}
            actions[action_name] = {
                "type": "Compose",
                "inputs": {
                    "bpmnTaskId": node["id"],
                    "businessStep": node["name"] or node["id"],
                    "suggestedConnector": hint["connector"],
                    "suggestedAction": hint["suggestedAction"],
                    "note": "Replace this Compose step with the suggested connector action and bind its inputs.",
                },
                "runAfter": run_after,
            }
            prev_action = action_name
        elif node["type"] == "exclusiveGateway" and len(node["outgoing"]) > 1:
            gate_name = _safe_action_name("Decision_" + (node["name"] or node["id"]), used_names)
            branches = [f.get("name") or "path" for f in node["outgoing"]]
            run_after = {prev_action: ["Succeeded"]} if prev_action else {}
            actions[gate_name] = {
                "type": "Switch",
                "expression": "@variables('decision')",
                "cases": {
                    _safe_action_name("Case_" + b, used_names): {"case": b, "actions": {}}
                    for b in branches
                },
                "default": {"actions": {}},
                "runAfter": run_after,
                "metadata": {
                    "bpmnGatewayId": node["id"],
                    "question": node["name"] or "Decision",
                    "note": "Set the 'decision' variable before this Switch, or convert to a Condition. Move downstream actions into the matching case.",
                },
            }
            prev_action = gate_name

    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {},
        "triggers": {
            "manual": {
                "type": "Request",
                "kind": "Button",
                "inputs": {"schema": {"type": "object", "properties": {}, "required": []}},
            }
        },
        "actions": _prepend_decision_var(actions),
        "outputs": {},
    }
    process_name = starts[0]["name"] if starts and starts[0]["name"] else "Process"
    return {"definition": definition, "processName": process_name, "taskCount": len(tasks), "gatewayCount": len(gateways)}


def bpmn_to_power_automate(xml: str) -> dict:
    built = _build_definition(xml)
    meta = {
        "generatedBy": "BPMN Copilot - Power Automate Export",
        "sourceProcessName": built["processName"],
        "counts": {"tasks": built["taskCount"], "gateways": built["gatewayCount"]},
        "disclaimer": "Scaffold in Logic Apps / Power Automate Workflow Definition Language. Complete connector bindings inside Power Automate.",
    }
    return {"filename": "process.flow.json", "flow": {"definition": built["definition"], "meta": meta}}


def _flow_display_name(process_name: str) -> str:
    name = (process_name or "BPMN Copilot Flow").strip()
    return name if name.lower().endswith("flow") else f"{name} Flow"


def _deterministic_guid(seed: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, seed)


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="text/xml" />'
        '<Default Extension="json" ContentType="application/json" />'
        '</Types>'
    )


def _solution_xml(display_name: str, unique_name: str, publisher_unique: str, prefix: str, workflow_guid: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        '<ImportExportXml version="9.2.24025.00000" SolutionPackageVersion="9.2" languagecode="1033" '
        'generatedBy="BPMNCopilot" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<SolutionManifest>'
        f'<UniqueName>{escape(unique_name)}</UniqueName>'
        '<LocalizedNames>'
        f'<LocalizedName description="{escape(display_name)}" languagecode="1033" />'
        '</LocalizedNames>'
        '<Descriptions>'
        '<Description description="Generated from a BPMN 2.0 model by BPMN Copilot." languagecode="1033" />'
        '</Descriptions>'
        f'<Version>{_SOLUTION_VERSION}</Version>'
        '<Managed>0</Managed>'
        '<Publisher>'
        f'<UniqueName>{escape(publisher_unique)}</UniqueName>'
        '<LocalizedNames>'
        '<LocalizedName description="BPMN Copilot" languagecode="1033" />'
        '</LocalizedNames>'
        '<Descriptions>'
        '<Description description="BPMN Copilot publisher" languagecode="1033" />'
        '</Descriptions>'
        '<EMailAddress xsi:nil="true" />'
        '<SupportingWebsiteUrl xsi:nil="true" />'
        f'<CustomizationPrefix>{escape(prefix)}</CustomizationPrefix>'
        '<CustomizationOptionValuePrefix>10000</CustomizationOptionValuePrefix>'
        '<Addresses />'
        '</Publisher>'
        '<RootComponents>'
        f'<RootComponent type="29" id="{{{workflow_guid}}}" behavior="0" />'
        '</RootComponents>'
        '<MissingDependencies />'
        '</SolutionManifest>'
        '</ImportExportXml>'
    )


def _customizations_xml(display_name: str, workflow_guid: str, json_file_name: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        '<ImportExportXml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<Entities />'
        '<Roles />'
        '<Workflows>'
        f'<Workflow WorkflowId="{{{workflow_guid}}}" Name="{escape(display_name)}">'
        f'<JsonFileName>{escape(json_file_name)}</JsonFileName>'
        '<Type>1</Type>'
        '<Subprocess>0</Subprocess>'
        '<Category>5</Category>'
        '<Mode>0</Mode>'
        '<Scope>4</Scope>'
        '<OnDemand>0</OnDemand>'
        '<TriggerOnCreate>0</TriggerOnCreate>'
        '<TriggerOnDelete>0</TriggerOnDelete>'
        '<AsyncAutodelete>0</AsyncAutodelete>'
        '<SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>'
        '<StateCode>0</StateCode>'
        '<StatusCode>1</StatusCode>'
        '<RunAs>1</RunAs>'
        '<IsTransacted>1</IsTransacted>'
        f'<IntroducedVersion>{_SOLUTION_VERSION}</IntroducedVersion>'
        '<IsCustomizable>1</IsCustomizable>'
        '<BusinessProcessType>0</BusinessProcessType>'
        '<IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>'
        '<PrimaryEntity>none</PrimaryEntity>'
        '<LocalizedNames>'
        f'<LocalizedName description="{escape(display_name)}" languagecode="1033" />'
        '</LocalizedNames>'
        '</Workflow>'
        '</Workflows>'
        '<FieldSecurityProfiles />'
        '<Templates />'
        '<EntityMaps />'
        '<EntityRelationships />'
        '<OrganizationSettings />'
        '<optionsets />'
        '<CustomControls />'
        '<EntityDataProviders />'
        '<connectionreferences />'
        '<Languages><Language>1033</Language></Languages>'
        '</ImportExportXml>'
    )


def _flow_clientdata(definition: dict) -> str:
    return json.dumps({
        "properties": {
            "connectionReferences": {},
            "definition": definition,
            "templateName": "",
        },
        "schemaVersion": "1.0.0.0",
    }, indent=2)


def build_solution_zip(xml: str) -> tuple[bytes, str]:
    built = _build_definition(xml)
    definition = built["definition"]
    display_name = _flow_display_name(built["processName"])

    slug = re.sub(r"[^A-Za-z0-9]+", "", display_name) or "BPMNCopilotFlow"
    unique_name = f"BPMNCopilot_{slug}"[:60]
    publisher_unique = "bpmncopilot"
    prefix = "bpmnc"

    workflow_uuid = _deterministic_guid("BPMNCopilot::" + display_name)
    guid_lower = str(workflow_uuid)
    guid_upper = guid_lower.upper()

    file_slug = re.sub(r"[^A-Za-z0-9]+", "_", display_name).strip("_") or "Flow"
    json_entry = f"Workflows/{file_slug}-{guid_upper}.json"
    json_file_name = f"/{json_entry}"

    content_types = _content_types_xml()
    solution_xml = _solution_xml(display_name, unique_name, publisher_unique, prefix, guid_lower)
    customizations_xml = _customizations_xml(display_name, guid_lower, json_file_name)
    clientdata = _flow_clientdata(definition)

    readme = (
        "BPMN Copilot - Power Automate Solution\r\n"
        "======================================\r\n\r\n"
        f"Flow: {display_name}\r\n"
        f"Tasks: {built['taskCount']}   Gateways: {built['gatewayCount']}\r\n\r\n"
        "IMPORT STEPS\r\n"
        "1. Go to make.powerautomate.com > Solutions > Import solution.\r\n"
        "2. Upload this .zip and complete the import wizard.\r\n"
        "3. Open the solution, then open the flow. It imports as Draft (Off).\r\n"
        "4. Each business task is a Compose placeholder tagged with a suggested\r\n"
        "   connector/action - replace it with the real action and bind inputs.\r\n"
        "5. Each decision is a Switch driven by a 'decision' variable; set that\r\n"
        "   variable (or convert to a Condition) and move downstream actions into\r\n"
        "   the matching case. Then turn the flow On.\r\n\r\n"
        "This solution stores no credentials. Connector bindings are completed in\r\n"
        "Power Automate.\r\n"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("solution.xml", solution_xml)
        zf.writestr("customizations.xml", customizations_xml)
        zf.writestr(json_entry, clientdata)
        zf.writestr("BPMNCopilot-README.txt", readme)

    zip_filename = f"{file_slug}_solution.zip"
    return buffer.getvalue(), zip_filename
