import os

# Load .env into os.environ before reading any variable.
# This makes backend/.env the source of truth for LLMAAS_* etc.
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(_env_path, override=False)
except Exception:
    # python-dotenv not installed yet — values will fall back to real env vars.
    pass

APP_NAME = "BPMN Copilot"
APP_VERSION = "2.2.0"

DB_PATH = os.environ.get("BPMN_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "bpmn_copilot.db"))

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

# ---------------------------------------------------------------------------
# VW LLMaaS (internal OpenAI-compatible gateway)
# The gateway expects an OAuth bearer token in Authorization AND a virtual
# key (sk-no...) in the X-LLM-API-CLIENT-ID header on every request.
# ---------------------------------------------------------------------------
LLMAAS_API_KEY = os.environ.get("LLMAAS_API_KEY", "")
LLMAAS_CLIENT_ID = os.environ.get("LLMAAS_CLIENT_ID", "")
LLMAAS_CLIENT_SECRET = os.environ.get("LLMAAS_CLIENT_SECRET", "")
LLMAAS_IDP_URL = os.environ.get(
    "LLMAAS_IDP_URL",
    "https://idp.cloud.vwgroup.com/auth/realms/kums-mfa/protocol/openid-connect/token",
)
LLMAAS_BASE_URL = os.environ.get(
    "LLMAAS_BASE_URL", "https://llmapi.ai.vwgroup.com"
)

MAX_SELF_CORRECT_LOOPS = int(os.environ.get("MAX_SELF_CORRECT_LOOPS", "3"))


GEN_MAX_TOKENS = int(os.environ.get("GEN_MAX_TOKENS", "16000"))
ENHANCE_MAX_TOKENS = int(os.environ.get("ENHANCE_MAX_TOKENS", "800"))
EXPLAIN_MAX_TOKENS = int(os.environ.get("EXPLAIN_MAX_TOKENS", "1200"))
AUTOMATE_MAX_TOKENS = int(os.environ.get("AUTOMATE_MAX_TOKENS", "1500"))

LLM_TEMPERATURE_GENERATE = float(os.environ.get("LLM_TEMPERATURE_GENERATE", "0.25"))
LLM_TEMPERATURE_EDIT = float(os.environ.get("LLM_TEMPERATURE_EDIT", "0.15"))
LLM_TEMPERATURE_FIX = float(os.environ.get("LLM_TEMPERATURE_FIX", "0.15"))
LLM_TEMPERATURE_ENHANCE = float(os.environ.get("LLM_TEMPERATURE_ENHANCE", "0.3"))
LLM_TEMPERATURE_EXPLAIN = float(os.environ.get("LLM_TEMPERATURE_EXPLAIN", "0.3"))
LLM_TEMPERATURE_AUTOMATE = float(os.environ.get("LLM_TEMPERATURE_AUTOMATE", "0.3"))

AI_TIMEOUT_SECONDS = int(os.environ.get("AI_TIMEOUT_SECONDS", "120"))
AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "2"))

MAX_DESCRIPTION_CHARS = int(os.environ.get("MAX_DESCRIPTION_CHARS", "8000"))
MAX_INSTRUCTION_CHARS = int(os.environ.get("MAX_INSTRUCTION_CHARS", "2000"))
MAX_XML_CHARS = int(os.environ.get("MAX_XML_CHARS", "200000"))
MAX_QUERY_CHARS = int(os.environ.get("MAX_QUERY_CHARS", "2000"))

MAX_XML_BYTES = int(os.environ.get("MAX_XML_BYTES", "1000000"))

PRESETS = [
    {
        "key": "messy",
        "title": "UC-1 Benchmark: Messy Complaint",
        "tag": "Flawed v1",
        "desc": "Vague task names, missing end event, unlabeled gateway. Demonstrates the self-healing loop.",
        "prompt": "When a customer complaint comes in, someone checks it. If valid, Support Agent fixes it, otherwise Manager rejects it and we close the ticket.",
    },
    {
        "key": "onboarding",
        "title": "Employee Onboarding",
        "tag": "HR Workflow",
        "desc": "Multi-step process covering IT setup, HR documents, and manager intro.",
        "prompt": "When a new employee is hired, HR collects onboarding documents, then IT provisions a laptop and accounts, then the manager conducts a Day 1 orientation, and the onboarding is marked complete.",
    },
    {
        "key": "fulfillment",
        "title": "Order Fulfillment & Logistics",
        "tag": "E-Commerce",
        "desc": "Payment verification, dispatch decision, and delivery/refund paths.",
        "prompt": "When a customer places an order, the system verifies the payment signature. If the payment is valid, the warehouse packs and dispatches the items and the order is fulfilled. If the payment is invalid, the customer is notified of a refund and the order is cancelled.",
    },
    {
        "key": "loan",
        "title": "Loan Application & Risk Assessment",
        "tag": "Fintech",
        "desc": "Credit check, manual underwriting, approval decision, and disbursement.",
        "prompt": "When a customer submits a loan application, the system runs an automated credit check. An underwriter then manually reviews the application and credit results. If the underwriter approves the loan, finance disburses the funds to the customer. If the underwriter rejects it, the customer is notified of the decision and the application is closed.",
    },
    {
        "key": "expense",
        "title": "Expense Reimbursement",
        "tag": "Finance",
        "desc": "Receipt submission, manager sign-off, audit verification, and payout.",
        "prompt": "When an employee submits an expense claim with receipts, their manager reviews and either approves or rejects the claim. If approved, finance audits the claim for policy compliance and pays out the reimbursement. If rejected, the employee is notified with the reason and the claim is closed.",
    },
]
