from __future__ import annotations


import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

try:
    from ..config import AI_TIMEOUT_SECONDS as DEFAULT_TIMEOUT, AI_MAX_RETRIES as MAX_RETRIES
except Exception:
    DEFAULT_TIMEOUT = int(os.environ.get("AI_TIMEOUT_SECONDS", "120"))
    MAX_RETRIES = 2

_AI_TLS_VERIFY = os.environ.get("AI_TLS_VERIFY", "true").strip().lower() not in (
    "0", "false", "no", "off",
)
if not _AI_TLS_VERIFY:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


_OPENAI_COMPATIBLE_BASE = {
    "openai": "https://api.openai.com/v1",
    "xai": "https://api.x.ai/v1",
    "grok": "https://api.x.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434/v1",
    "llmaas": "https://llmapi.ai.vwgroup.com/v1",   
}
_ANTHROPIC_BASE = "https://api.anthropic.com/v1"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

_AZURE_TOKEN_PROVIDER = None

def _get_azure_token() -> str:
    global _AZURE_TOKEN_PROVIDER
    if _AZURE_TOKEN_PROVIDER is None:
        try:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        except ImportError:
            raise AIConfigError("azure-identity is not installed. Run: pip install azure-identity")
        scope = os.environ.get("AZURE_OPENAI_SCOPE", "https://cognitiveservices.azure.com/.default")
        _AZURE_TOKEN_PROVIDER = get_bearer_token_provider(DefaultAzureCredential(), scope)
    return _AZURE_TOKEN_PROVIDER()


# ---------------------------------------------------------------------------
# VW LLMaaS — OAuth token cache + fetcher + chat function
# ---------------------------------------------------------------------------
_LLMAAS_TOKEN_CACHE: dict = {"token": None, "expires_at": 0.0}


def _get_llmaas_token() -> str:
    """Fetch (and cache) an OAuth access token from the VW Cloud IDP.

    The LLMaaS gateway expects BOTH:
      Authorization: Bearer <oauth_access_token>   (short-lived)
      X-LLM-API-CLIENT-ID: Bearer <virtual_key>    (the sk-no... key)
    The virtual key alone is NOT sufficient.
    """
    now = time.time()
    cached = _LLMAAS_TOKEN_CACHE.get("token")
    expires_at = _LLMAAS_TOKEN_CACHE.get("expires_at", 0.0)
    if cached and now < expires_at - 30:
        return cached

    client_id = os.environ.get("LLMAAS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("LLMAAS_CLIENT_SECRET", "").strip()
    idp_url = (
        os.environ.get("LLMAAS_IDP_URL", "").strip()
        or "https://idp.cloud.vwgroup.com/auth/realms/kums-mfa/protocol/openid-connect/token"
    )
    if not client_id or not client_secret:
        raise AIConfigError(
            "LLMaaS OAuth credentials missing. Set LLMAAS_CLIENT_ID and "
            "LLMAAS_CLIENT_SECRET in the server .env file."
        )

    try:
        resp = requests.post(
            idp_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        raise AIAPIError(f"Could not reach the LLMaaS IDP at {idp_url}: {e}")

    if resp.status_code != 200:
        raise AIAPIError(
            f"LLMaaS IDP rejected the token request ({resp.status_code}): "
            f"{resp.text[:200]}"
        )

    try:
        data = resp.json()
    except ValueError:
        raise AIAPIError(f"LLMaaS IDP returned non-JSON: {resp.text[:200]}")

    token = data.get("access_token")
    if not token:
        raise AIAPIError(
            f"LLMaaS IDP response had no access_token: {str(data)[:200]}"
        )

    expires_in = int(data.get("expires_in") or 300)
    _LLMAAS_TOKEN_CACHE["token"] = token
    _LLMAAS_TOKEN_CACHE["expires_at"] = now + expires_in
    return token


def _chat_llmaas(system_prompt, user_prompt, s, json_mode, temperature, max_tokens) -> str:
    """Chat via the VW LLMaaS gateway.

    - Adds X-LLM-API-CLIENT-ID (virtual key) + Authorization (OAuth token)
    - Routes gpt-5* through the Responses API (/v1/responses)
    - Routes everything else through Chat Completions (/v1/chat/completions)
    - Refreshes the OAuth token once on a 401/403
    """
    virtual_key = (s.api_key or os.environ.get("LLMAAS_API_KEY", "")).strip()
    if not virtual_key:
        raise AIConfigError(
            "No LLMaaS virtual key provided. Paste the sk-no… key in Settings, "
            "or set LLMAAS_API_KEY in the server .env."
        )

    base = s.resolved_base().rstrip("/")
    model = s.model or "gpt-4o"
    is_gpt5 = model.lower().startswith("gpt-5")

    def _do_call() -> dict:
        token = _get_llmaas_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-LLM-API-CLIENT-ID": f"Bearer {virtual_key}",
        }
        if is_gpt5:
            url = f"{base}/responses"
            payload = {
                "model": model,
                "instructions": system_prompt,
                "input": user_prompt,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
        else:
            url = f"{base}/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
        return _post_with_retries(url, headers, payload)

    try:
        data = _do_call()
    except AIAPIError as e:
        if e.status_code in (401, 403):
            _LLMAAS_TOKEN_CACHE["token"] = None
            _LLMAAS_TOKEN_CACHE["expires_at"] = 0.0
            data = _do_call()
        else:
            raise

    if is_gpt5:
        try:
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for part in item.get("content", []):
                        if part.get("type") == "output_text":
                            text = part.get("text", "")
                            if text:
                                return text
            raise AIAPIError(f"Empty LLMaaS Responses output: {str(data)[:300]}")
        except AIAPIError:
            raise
        except (KeyError, IndexError, TypeError):
            raise AIAPIError(f"Unexpected LLMaaS Responses shape: {str(data)[:300]}")

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIAPIError(f"Unexpected LLMaaS response shape: {str(data)[:300]}")


class AIConfigError(Exception):
    pass


class AIAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class AISettings:
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    language: str = "en"


    @property
    def norm_provider(self) -> str:
        return (self.provider or "openai").strip().lower()

    def resolved_base(self) -> str:
        p = self.norm_provider
        if self.base_url:
            return self.base_url.rstrip("/")
        if p in _OPENAI_COMPATIBLE_BASE:
            return _OPENAI_COMPATIBLE_BASE[p]
        if p == "anthropic":
            return _ANTHROPIC_BASE
        if p in ("gemini", "google"):
            return _GEMINI_BASE
        return _OPENAI_COMPATIBLE_BASE["openai"]


def settings_from_env() -> AISettings:
    return AISettings(
        provider=os.environ.get("AI_PROVIDER", "mock"),
        api_key=os.environ.get("AI_API_KEY", "").strip(),
        model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
        base_url=os.environ.get("AI_BASE_URL") or None,
        language=os.environ.get("AI_LANGUAGE", "en"),
    )



def chat(system_prompt, user_prompt, settings, *, json_mode=False, temperature=0.25, max_tokens=8192) -> str:
    p = settings.norm_provider
    if p == "mock":
        return _mock_response(system_prompt, user_prompt, json_mode)
    if p == "anthropic":
        return _chat_anthropic(system_prompt, user_prompt, settings, json_mode, temperature, max_tokens)
    if p in ("gemini", "google"):
        return _chat_gemini(system_prompt, user_prompt, settings, json_mode, temperature, max_tokens)
    if p in ("azure", "azure-mi", "azure_openai"):
        return _chat_azure(system_prompt, user_prompt, settings, json_mode, temperature, max_tokens)
    if p == "llmaas":
        return _chat_llmaas(system_prompt, user_prompt, settings, json_mode, temperature, max_tokens)

    return _chat_openai(system_prompt, user_prompt, settings, json_mode, temperature, max_tokens)


def chat_json(system_prompt, user_prompt, settings, **kwargs) -> dict:
    raw = chat(system_prompt, user_prompt, settings, json_mode=True, **kwargs)
    if not raw or not raw.strip():
        raise AIAPIError("The model returned an empty response. Please try again.")
    try:
        data = _loads_lenient(raw)
    except (json.JSONDecodeError, ValueError):
        hint = " The response looked truncated." if not raw.rstrip().endswith("}") else ""
        raise AIAPIError(
            "The model's response was not valid JSON (common on free/smaller models or "
            "when truncated)." + hint + " Please try again."
        )
    if not isinstance(data, dict):
        raise AIAPIError("The model's JSON response was not an object. Please try again.")
    return data


def _chat_openai(system_prompt, user_prompt, s, json_mode, temperature, max_tokens) -> str:
    key = s.api_key or os.environ.get("AI_API_KEY", "").strip()
    if not key and s.norm_provider != "ollama":
        raise AIConfigError("No API key provided. Add one in the Settings panel or the server .env.")
    url = f"{s.resolved_base()}/chat/completions"
    payload = {
        "model": s.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if s.norm_provider == "openrouter":
        headers["HTTP-Referer"] = "https://bpmn-copilot.local"
        headers["X-Title"] = "BPMN Copilot"
    data = _post_with_retries(url, headers, payload)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIAPIError(f"Unexpected response shape from {s.provider}: {str(data)[:300]}")

def _chat_azure(system_prompt, user_prompt, s, json_mode, temperature, max_tokens) -> str:
    endpoint = (s.base_url or os.environ.get("AZURE_OPENAI_ENDPOINT", "")).rstrip("/")
    if not endpoint:
        raise AIConfigError("AZURE_OPENAI_ENDPOINT is not set (or provide it as the Base URL).")
    deployment = s.model or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    if not deployment:
        raise AIConfigError("No Azure deployment name set (enter it as the model).")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01")
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    token = _get_azure_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    data = _post_with_retries(url, headers, payload)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIAPIError(f"Unexpected Azure OpenAI response: {str(data)[:300]}")


def _chat_anthropic(system_prompt, user_prompt, s, json_mode, temperature, max_tokens) -> str:
    key = s.api_key or os.environ.get("AI_API_KEY", "").strip()
    if not key:
        raise AIConfigError("No Anthropic API key provided.")
    url = f"{s.resolved_base()}/messages"
    if json_mode:
        user_prompt += "\n\nRespond with ONLY a single valid JSON object, no prose, no code fences."
    payload = {
        "model": s.model,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    data = _post_with_retries(url, headers, payload)
    try:
        return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
    except Exception:
        raise AIAPIError(f"Unexpected Anthropic response: {str(data)[:300]}")


def _chat_gemini(system_prompt, user_prompt, s, json_mode, temperature, max_tokens) -> str:
    key = s.api_key or os.environ.get("AI_API_KEY", "").strip()
    if not key:
        raise AIConfigError("No Google API key provided.")
    url = f"{s.resolved_base()}/models/{s.model}:generateContent?key={key}"
    gen_cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"
    if "2.5" in (s.model or ""):
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": gen_cfg,
    }
    data = _post_with_retries(url, {"Content-Type": "application/json"}, payload)
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            raise AIAPIError(f"Gemini returned no candidates (possibly blocked). {str(data.get('promptFeedback', ''))[:200]}")
        cand = candidates[0]
        text = "".join(part.get("text", "") for part in cand.get("content", {}).get("parts", []))
        if not text.strip():
            raise AIAPIError(f"Gemini returned an empty response (finishReason={cand.get('finishReason', 'unknown')}). Please try again.")
        return text
    except AIAPIError:
        raise
    except (KeyError, IndexError, TypeError):
        raise AIAPIError(f"Unexpected Gemini response: {str(data)[:300]}")


def _post_with_retries(url, headers, payload) -> dict:
    last_error: Optional[Exception] = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=DEFAULT_TIMEOUT,
                verify=_AI_TLS_VERIFY,
            )
        except requests.exceptions.SSLError as e:
            raise AIAPIError(
                f"TLS certificate verification failed contacting the AI provider ({e}). "
                "Fix options: (1) set AI_TLS_VERIFY=false in the server .env for a quick "
                "workaround, (2) run 'pip install pip-system-certs' in the venv, or "
                "(3) set REQUESTS_CA_BUNDLE to your corporate root CA .pem."
            )
        except requests.exceptions.Timeout:
            last_error = AIAPIError("AI provider request timed out.")
            time.sleep(1 + attempt)
            continue
        except requests.exceptions.RequestException as e:
            last_error = AIAPIError(f"Could not reach the AI provider: {e}")
            time.sleep(1 + attempt)
            continue
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                raise AIAPIError(f"Provider returned non-JSON: {resp.text[:300]}")
        if resp.status_code in (401, 403):
            raise AIAPIError("The provider rejected the request (invalid or unauthorized API key).", status_code=resp.status_code)
        if resp.status_code == 429:
            last_error = AIAPIError("Rate limit exceeded. Please retry shortly.", status_code=429)
            time.sleep(2 + attempt * 2)
            continue
        if 500 <= resp.status_code < 600:
            last_error = AIAPIError(f"Provider server error ({resp.status_code}).", status_code=resp.status_code)
            time.sleep(1 + attempt)
            continue
        raise AIAPIError(f"Provider error {resp.status_code}: {resp.text[:400]}", status_code=resp.status_code)
    raise last_error or AIAPIError("AI provider call failed after retries.")


def _loads_lenient(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]
        return json.loads(cleaned.strip())


def _mock_response(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    sys_l = system_prompt.lower()
    if json_mode and "explainer" in sys_l:
        return json.dumps({
            "headline": "A clean, mostly linear approval workflow",
            "summary": "This process starts with an incoming request, routes it through a single decision point, and terminates on both branches. It is small, readable, and largely audit-ready.",
            "bullets": [
                "One clear start and explicit end events on every branch.",
                "A single labelled decision gateway keeps control flow unambiguous.",
                "Task names follow verb-noun form, aiding traceability.",
                "Consider adding swimlanes to make role ownership explicit.",
            ],
        })
    if json_mode and "automation" in sys_l:
        return json.dumps({"candidates": [
            {"id": "Task_1", "name": "Validate Request", "roi": "High", "tool": "API Integration", "rationale": "Rule-based validation is easily codified."},
            {"id": "Task_2", "name": "Notify Customer", "roi": "Medium", "tool": "Power Automate Bot", "rationale": "Templated notifications suit low-code automation."},
        ]})
    if json_mode:
        return "{}"
    if "enhancer agent" in sys_l:
        return ("When a customer submits a request, a Support Agent reviews the request "
                "details. The Support Agent decides: is the request valid? If yes, the "
                "Support Agent resolves the request and the case is closed. If no, a Manager "
                "rejects the request, the customer is notified with the reason, and the case "
                "is closed.")

    if "editor agent" in sys_l:
        return _MOCK_EDITED_XML
    return _MOCK_BPMN_XML


_MOCK_BPMN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
    xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Defs_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1" name="Request Received">
      <bpmn:outgoing>F1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Validate Request">
      <bpmn:incoming>F1</bpmn:incoming>
      <bpmn:outgoing>F2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:exclusiveGateway id="GW_1" name="Is Request Valid?">
      <bpmn:incoming>F2</bpmn:incoming>
      <bpmn:outgoing>F3</bpmn:outgoing>
      <bpmn:outgoing>F4</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:task id="Task_2" name="Notify Customer">
      <bpmn:incoming>F3</bpmn:incoming>
      <bpmn:outgoing>F5</bpmn:outgoing>
    </bpmn:task>
    <bpmn:task id="Task_3" name="Reject Request">
      <bpmn:incoming>F4</bpmn:incoming>
      <bpmn:outgoing>F6</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1" name="Request Fulfilled">
      <bpmn:incoming>F5</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:endEvent id="End_2" name="Request Closed">
      <bpmn:incoming>F6</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="F2" sourceRef="Task_1" targetRef="GW_1" />
    <bpmn:sequenceFlow id="F3" name="Yes" sourceRef="GW_1" targetRef="Task_2" />
    <bpmn:sequenceFlow id="F4" name="No" sourceRef="GW_1" targetRef="Task_3" />
    <bpmn:sequenceFlow id="F5" sourceRef="Task_2" targetRef="End_1" />
    <bpmn:sequenceFlow id="F6" sourceRef="Task_3" targetRef="End_2" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="Diagram_1">
    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1"><dc:Bounds x="150" y="200" width="36" height="36" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_1_di" bpmnElement="Task_1"><dc:Bounds x="240" y="178" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="GW_1_di" bpmnElement="GW_1"><dc:Bounds x="400" y="193" width="50" height="50" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_2_di" bpmnElement="Task_2"><dc:Bounds x="510" y="118" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_3_di" bpmnElement="Task_3"><dc:Bounds x="510" y="258" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="End_1_di" bpmnElement="End_1"><dc:Bounds x="672" y="140" width="36" height="36" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="End_2_di" bpmnElement="End_2"><dc:Bounds x="672" y="280" width="36" height="36" /></bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="F1_di" bpmnElement="F1"><di:waypoint x="186" y="218" /><di:waypoint x="240" y="218" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F2_di" bpmnElement="F2"><di:waypoint x="340" y="218" /><di:waypoint x="400" y="218" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F3_di" bpmnElement="F3"><di:waypoint x="425" y="193" /><di:waypoint x="425" y="158" /><di:waypoint x="510" y="158" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F4_di" bpmnElement="F4"><di:waypoint x="425" y="243" /><di:waypoint x="425" y="298" /><di:waypoint x="510" y="298" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F5_di" bpmnElement="F5"><di:waypoint x="610" y="158" /><di:waypoint x="672" y="158" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F6_di" bpmnElement="F6"><di:waypoint x="610" y="298" /><di:waypoint x="672" y="298" /></bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""


_MOCK_EDITED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
    xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Defs_1" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="Start_1" name="Request Received">
      <bpmn:outgoing>F1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Validate Request">
      <bpmn:incoming>F1</bpmn:incoming>
      <bpmn:outgoing>F2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:exclusiveGateway id="GW_1" name="Is Request Valid?">
      <bpmn:incoming>F2</bpmn:incoming>
      <bpmn:outgoing>F3</bpmn:outgoing>
      <bpmn:outgoing>F4</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:task id="Task_2" name="Notify Customer">
      <bpmn:incoming>F3</bpmn:incoming>
      <bpmn:outgoing>F5</bpmn:outgoing>
    </bpmn:task>
    <bpmn:task id="Task_3" name="Reject Request">
      <bpmn:incoming>F4</bpmn:incoming>
      <bpmn:outgoing>F6</bpmn:outgoing>
    </bpmn:task>
    <bpmn:task id="Task_4" name="Manager Approves Request">
      <bpmn:incoming>F5</bpmn:incoming>
      <bpmn:outgoing>F7</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="End_1" name="Request Fulfilled">
      <bpmn:incoming>F7</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:endEvent id="End_2" name="Request Closed">
      <bpmn:incoming>F6</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="F1" sourceRef="Start_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="F2" sourceRef="Task_1" targetRef="GW_1" />
    <bpmn:sequenceFlow id="F3" name="Yes" sourceRef="GW_1" targetRef="Task_2" />
    <bpmn:sequenceFlow id="F4" name="No" sourceRef="GW_1" targetRef="Task_3" />
    <bpmn:sequenceFlow id="F5" sourceRef="Task_2" targetRef="Task_4" />
    <bpmn:sequenceFlow id="F7" sourceRef="Task_4" targetRef="End_1" />
    <bpmn:sequenceFlow id="F6" sourceRef="Task_3" targetRef="End_2" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="Diagram_1">
    <bpmndi:BPMNPlane id="Plane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="Start_1_di" bpmnElement="Start_1"><dc:Bounds x="150" y="200" width="36" height="36" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_1_di" bpmnElement="Task_1"><dc:Bounds x="240" y="178" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="GW_1_di" bpmnElement="GW_1"><dc:Bounds x="400" y="193" width="50" height="50" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_2_di" bpmnElement="Task_2"><dc:Bounds x="510" y="118" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_3_di" bpmnElement="Task_3"><dc:Bounds x="510" y="258" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_4_di" bpmnElement="Task_4"><dc:Bounds x="660" y="118" width="100" height="80" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="End_1_di" bpmnElement="End_1"><dc:Bounds x="822" y="140" width="36" height="36" /></bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="End_2_di" bpmnElement="End_2"><dc:Bounds x="672" y="280" width="36" height="36" /></bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="F1_di" bpmnElement="F1"><di:waypoint x="186" y="218" /><di:waypoint x="240" y="218" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F2_di" bpmnElement="F2"><di:waypoint x="340" y="218" /><di:waypoint x="400" y="218" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F3_di" bpmnElement="F3"><di:waypoint x="425" y="193" /><di:waypoint x="425" y="158" /><di:waypoint x="510" y="158" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F4_di" bpmnElement="F4"><di:waypoint x="425" y="243" /><di:waypoint x="425" y="298" /><di:waypoint x="510" y="298" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F5_di" bpmnElement="F5"><di:waypoint x="610" y="158" /><di:waypoint x="660" y="158" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F7_di" bpmnElement="F7"><di:waypoint x="760" y="158" /><di:waypoint x="822" y="158" /></bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="F6_di" bpmnElement="F6"><di:waypoint x="610" y="298" /><di:waypoint x="672" y="298" /></bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>"""
