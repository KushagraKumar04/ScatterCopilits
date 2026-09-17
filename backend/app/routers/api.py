import io
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .. import db
from ..config import APP_VERSION, PRESETS
from ..deps import get_ai_settings
from ..schemas import (
    AssistantChatRequest,
    EditRequest, EnhanceRequest, ExplainRequest, FixRequest,
    GenerateRequest, ReviewExportRequest, SuggestRequest, XmlRequest,
)
from ..services import agents
from ..services import power_automate
from ..services import bpmn_optimize
from ..services import review_export
from ..services import bpmn_linter as linter

from ..services.ai_client import AIAPIError, AIConfigError, AISettings

router = APIRouter(prefix="/api")


def _fail(e: Exception) -> HTTPException:
    if isinstance(e, AIConfigError):
        return HTTPException(status_code=401, detail={"error": str(e), "code": "NO_API_KEY"})
    if isinstance(e, AIAPIError):
        status = e.status_code if e.status_code and e.status_code < 500 else 502
        return HTTPException(status_code=status, detail={"error": str(e), "code": "AI_API_ERROR"})
    if isinstance(e, linter.BpmnParseError):
        return HTTPException(status_code=422, detail={"error": str(e), "code": "PARSE_ERROR"})
    return HTTPException(status_code=500, detail={"error": f"Unexpected error: {e}", "code": "SERVER_ERROR"})


@router.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION}


@router.get("/health/full")
def health_full(settings: AISettings = Depends(get_ai_settings)):
    """Diagnostic endpoint. Verifies DB, LLMaaS env, and OAuth token."""
    result = {
        "ok": True,
        "version": APP_VERSION,
        "provider": settings.norm_provider,
        "model": settings.model,
        "has_frontend_key": bool(settings.api_key),
        "checks": {},
    }

    try:
        db.list_history(limit=1)
        result["checks"]["db"] = "ok"
    except Exception as e:
        result["checks"]["db"] = f"error: {e}"
        result["ok"] = False

    if settings.norm_provider == "llmaas":
        for var in (
            "LLMAAS_API_KEY",
            "LLMAAS_CLIENT_ID",
            "LLMAAS_CLIENT_SECRET",
            "LLMAAS_IDP_URL",
            "LLMAAS_BASE_URL",
        ):
            result["checks"][var] = "set" if os.environ.get(var) else "MISSING"
        try:
            from ..services.ai_client import _get_llmaas_token
            _get_llmaas_token()
            result["checks"]["llmaas_oauth"] = "ok"
        except Exception as e:
            result["checks"]["llmaas_oauth"] = f"error: {e}"
            result["ok"] = False

    return result


@router.post("/health/llm")
def health_llm(settings: AISettings = Depends(get_ai_settings)):
    """Fire a 5-token call to the configured provider. Use this in Settings
    to verify the key works before a demo."""
    from ..services.ai_client import chat
    try:
        reply = chat(
            "Reply with only the word OK.",
            "ping",
            settings,
            temperature=0.0,
            max_tokens=5,
        )
        return {"ok": True, "reply": (reply or "").strip()[:50]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


@router.get("/presets")
def presets():
    return {"presets": PRESETS}


@router.post("/lint")
def api_lint(body: XmlRequest):
    try:
        result = linter.lint(body.xml)
        return agents._public_lint(result)
    except Exception as e:
        raise _fail(e)


@router.post("/generate")
def api_generate(body: GenerateRequest, settings: AISettings = Depends(get_ai_settings)):
    description = body.description.strip()
    try:
        result = agents.generate_bpmn(description, settings)
        if not result.get("xml"):
            raise HTTPException(502, detail={"error": result.get("warning") or "Generation failed.", "code": "GENERATION_FAILED"})
        lint = result.get("lint") or {}
        hid = db.add_history(description, score=lint.get("totalScore"), loops=result.get("loops"))
        db.save_model(result["xml"], lint.get("totalScore"), lint.get("band"), history_id=hid)
        result["historyId"] = hid
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise _fail(e)

@router.post("/enhance")
def api_enhance(body: EnhanceRequest, settings: AISettings = Depends(get_ai_settings)):
    if not body.description.strip():
        raise HTTPException(400, detail={"error": "description is required.", "code": "BAD_REQUEST"})
    try:
        return {"enhanced": agents.enhance_description(body.description, settings)}
    except Exception as e:
        raise _fail(e)


@router.post("/generate/stream")
def api_generate_stream(body: GenerateRequest, settings: AISettings = Depends(get_ai_settings)):
    description = body.description.strip()

    def event_stream():
        try:
            final = None
            for event in agents.generate_bpmn_events(description, settings):
                if event["type"] == "result":
                    final = event["data"]
                yield f"data: {json.dumps(event)}\n\n"
            if final and final.get("xml"):
                lint = final.get("lint") or {}
                hid = db.add_history(description, score=lint.get("totalScore"), loops=final.get("loops"))
                db.save_model(final["xml"], lint.get("totalScore"), lint.get("band"), history_id=hid)
                yield f"data: {json.dumps({'type': 'saved', 'historyId': hid})}\n\n"
        except AIConfigError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'code': 'NO_API_KEY'})}\n\n"
        except AIAPIError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'code': 'AI_API_ERROR'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': f'Unexpected error: {e}', 'code': 'SERVER_ERROR'})}\n\n"
        yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/edit/stream")
def api_edit_stream(body: EditRequest, settings: AISettings = Depends(get_ai_settings)):
    xml = body.xml
    instruction = body.instruction.strip()

    def event_stream():
        try:
            for event in agents.edit_bpmn_events(xml, instruction, settings):
                yield f"data: {json.dumps(event)}\n\n"
        except AIConfigError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'code': 'NO_API_KEY'})}\n\n"
        except AIAPIError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'code': 'AI_API_ERROR'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': f'Unexpected error: {e}', 'code': 'SERVER_ERROR'})}\n\n"
        yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/edit")
def api_edit(body: EditRequest, settings: AISettings = Depends(get_ai_settings)):
    if not body.xml.strip():
        raise HTTPException(400, detail={"error": "xml is required.", "code": "BAD_REQUEST"})
    try:
        result = agents.edit_bpmn(body.xml, body.instruction, settings)
        if not result.get("xml"):
            raise HTTPException(502, detail={"error": result.get("warning") or "Edit failed.", "code": "EDIT_FAILED"})
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise _fail(e)


@router.post("/fix")
def api_fix(body: FixRequest, settings: AISettings = Depends(get_ai_settings)):
    if not body.xml.strip():
        raise HTTPException(400, detail={"error": "xml is required.", "code": "BAD_REQUEST"})
    try:
        return agents.fix_bpmn(body.xml, body.issues, settings)
    except Exception as e:
        raise _fail(e)


@router.post("/explain")
def api_explain(body: ExplainRequest, settings: AISettings = Depends(get_ai_settings)):
    if not body.xml.strip():
        raise HTTPException(400, detail={"error": "xml is required.", "code": "BAD_REQUEST"})
    try:
        return agents.explain_bpmn(body.xml, body.persona, settings)
    except Exception as e:
        raise _fail(e)


@router.post("/assistant/chat")
def api_assistant_chat(body: AssistantChatRequest, settings: AISettings = Depends(get_ai_settings)):
    """Floating assistant — conversational replies grounded in the current model."""
    try:
        from ..services import assistant
        return {"reply": assistant.reply(body.xml, body.question, body.context, settings)}
    except Exception as e:
        raise _fail(e)


@router.post("/automate")
def api_automate(body: XmlRequest, settings: AISettings = Depends(get_ai_settings)):
    if not body.xml.strip():
        raise HTTPException(400, detail={"error": "xml is required.", "code": "BAD_REQUEST"})
    try:
        return {"candidates": agents.automation_candidates(body.xml, settings)}
    except Exception as e:
        raise _fail(e)

@router.post("/optimize/stream")
def api_optimize_stream(body: XmlRequest, settings: AISettings = Depends(get_ai_settings)):
    xml = body.xml

    def event_stream():
        try:
            from ..services.ai_client import chat, chat_json
            for event in bpmn_optimize.optimize_process_events(xml, settings, chat, chat_json):
                yield f"data: {json.dumps(event)}\n\n"
        except AIConfigError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'code': 'NO_API_KEY'})}\n\n"
        except AIAPIError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'code': 'AI_API_ERROR'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': f'Unexpected error: {e}', 'code': 'SERVER_ERROR'})}\n\n"
        yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/review")
def api_review(body: XmlRequest, settings: AISettings = Depends(get_ai_settings)):
    if not body.xml.strip():
        raise HTTPException(400, detail={"error": "xml is required.", "code": "BAD_REQUEST"})
    try:
        from ..services.ai_client import chat_json
        return bpmn_optimize.review_process(body.xml, settings, chat_json)
    except Exception as e:
        raise _fail(e)

@router.post("/review/export")
def api_review_export(body: ReviewExportRequest):
    try:
        data, filename, media_type = review_export.render_review(
            body.report, body.format, body.processName,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": str(e), "code": "BAD_REQUEST"})
    except Exception as e:
        raise _fail(e)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/power-automate")
def api_export_power_automate(body: XmlRequest):
    if not body.xml.strip():
        raise HTTPException(400, detail={"error": "xml is required.", "code": "BAD_REQUEST"})
    try:
        data, filename = power_automate.build_solution_zip(body.xml)
    except Exception as e:
        raise _fail(e)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )




@router.get("/history")
def get_history(limit: int = 100):
    return {"history": db.list_history(limit)}


@router.post("/history/suggest")
def post_suggest(body: SuggestRequest):
    return {"suggestions": db.suggest(body.query)}


@router.delete("/history/{hid}")
def del_history(hid: int):
    db.delete_history(hid)
    return {"ok": True}


@router.post("/history/{hid}/pin")
def pin_history(hid: int):
    db.toggle_pin(hid)
    return {"ok": True}


@router.delete("/history")
def clear_hist():
    db.clear_history()
    return {"ok": True}
