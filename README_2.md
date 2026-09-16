# VW LLMaaS Setup

## 1. Start the Backend

Open a terminal in the `backend` folder:

```powershell
uvicorn app.main:app --reload
```

## 2. Start the Frontend

Open another terminal in the `frontend` folder:

```powershell
npm run dev
```

Open the application:

```text
http://localhost:5173
```

## 3. Configure VW LLMaaS

In the application:

1. Click **⚙️ Settings**.
2. Select **Provider → VW LLMaaS (internal)**.
3. Enter the `sk-no...` API key provided by VW.
4. Select **Model → gpt-4o**.
5. Click **Test Connection**.
6. Confirm that you see:

```text
✓ Connected. Reply: OK
```

7. Click **Save**.

## 4. Configure Backend `.env`

The following OAuth credentials must be available in the backend `.env` file:

```env
LLMAAS_CLIENT_ID=your-client-id
LLMAAS_CLIENT_SECRET=your-client-secret
LLMAAS_IDP_URL=https://idp.cloud.vwgroup.com/auth/realms/kums-mfa/protocol/openid-connect/token
LLMAAS_BASE_URL=https://llmapi.ai.vwgroup.com
```

### Optional: Store the API Key in `.env`

You can also add the API key as a server-side fallback:

```env
LLMAAS_API_KEY=sk-no-your-key
```

The API key priority is:

1. **Frontend Settings (`X-AI-Key`)** — highest priority
2. **Backend `.env` (`LLMAAS_API_KEY`)** — fallback

## 5. Verify the Connection

Open:

```text
http://localhost:8000/api/health/full
```

A successful configuration should show:

```json
{
  "ok": true,
  "provider": "llmaas",
  "checks": {
    "db": "ok",
    "LLMAAS_API_KEY": "set",
    "LLMAAS_CLIENT_ID": "set",
    "LLMAAS_CLIENT_SECRET": "set",
    "LLMAAS_IDP_URL": "set",
    "LLMAAS_BASE_URL": "set",
    "llmaas_oauth": "ok"
  }
}
```

## Important Notes

* Do **not** change `AI_PROVIDER=mock`. The UI selects the provider per request.
* Do **not** put the VW LLMaaS key in `AI_API_KEY`.
* Keep `LLMAAS_CLIENT_ID`, `LLMAAS_CLIENT_SECRET`, `LLMAAS_IDP_URL`, and `LLMAAS_BASE_URL` in the backend `.env`.
* **Never commit `.env` or API keys to Git.**
* If `llmaas_oauth` shows an error, verify the **Client ID** and **Client Secret**.

## Quick Start

```powershell
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Then open:

```text
http://localhost:5173
```

Configure **VW LLMaaS** from **Settings** and test the connection.


The LLMaaS Portal (most likely)
The DEVELOPER_GUIDE.pdf you forwarded says:

"LLMAAS_API_KEY=sk-your-virtual-key # Virtual API key from the LLMaas portal"

So there's a LLMaaS portal where apps are registered. Log into it, go to your application's settings page, and you'll see:

Client ID — a string like abc-123-xyz

Client Secret — a longer token (click "reveal" or "regenerate")

Virtual API key — the sk-no… 

wo copy krlena
aur .env me paste krdena
