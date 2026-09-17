import { useEffect, useState } from "react";
import type { AIConfig, Provider } from "../lib/types";
import { api } from "../lib/api";
import { useI18n } from "../lib/LanguageContext";
import { Check, Close, Robot } from "./icons";

interface ProviderMeta {
  id: Provider;
  label: string;
  needsKey: boolean;
  needsBase?: boolean;
  models: string[];
  keyHint: string;
}

const PROVIDERS: ProviderMeta[] = [
  {
    id: "openai",
    label: "OpenAI",
    needsKey: true,
    models: ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini"],
    keyHint: "sk-…",
  },
  {
    id: "anthropic",
    label: "Anthropic (Claude)",
    needsKey: true,
    models: ["claude-sonnet-4", "claude-3-7-sonnet", "claude-3-5-haiku"],
    keyHint: "sk-ant-…",
  },
  {
    id: "gemini",
    label: "Google Gemini",
    needsKey: true,
    models: ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
    keyHint: "AIza…",
  },
  {
    id: "xai",
    label: "xAI (Grok)",
    needsKey: true,
    models: ["grok-4", "grok-3", "grok-3-mini"],
    keyHint: "xai-…",
  },
  {
    id: "groq",
    label: "Groq",
    needsKey: true,
    models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    keyHint: "gsk_…",
  },
  {
    id: "mistral",
    label: "Mistral",
    needsKey: true,
    models: ["mistral-large-latest", "mistral-small-latest"],
    keyHint: "…",
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    needsKey: true,
    models: ["openai/gpt-4o", "anthropic/claude-sonnet-4"],
    keyHint: "sk-or-…",
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    needsKey: true,
    models: ["deepseek-chat", "deepseek-reasoner"],
    keyHint: "sk-…",
  },
  {
    id: "together",
    label: "Together AI",
    needsKey: true,
    models: ["meta-llama/Llama-3.3-70B-Instruct-Turbo"],
    keyHint: "…",
  },
  {
    id: "ollama",
    label: "Ollama (local)",
    needsKey: false,
    needsBase: true,
    models: ["llama3.1", "qwen2.5"],
    keyHint: "not required",
  },
  {
    id: "llmaas",
    label: "VW LLMaaS (internal)",
    needsKey: true,
    models: ["gpt-4o", "gpt-5-mini", "gpt-4.1-mini"],
    keyHint: "sk-no…",
  },
  {
    id: "azure",
    label: "Azure OpenAI (Managed Identity)",
    needsKey: false,
    needsBase: true,
    models: ["your-deployment-name"],
    keyHint: "no key - uses Managed Identity",
  },
  {
    id: "custom",
    label: "Custom (OpenAI-compatible)",
    needsKey: true,
    needsBase: true,
    models: ["your-model"],
    keyHint: "paste key",
  },
  {
    id: "mock",
    label: "Demo mode (no key)",
    needsKey: false,
    models: ["mock"],
    keyHint: "no key needed",
  },
];

interface Props {
  open: boolean;
  value: AIConfig;
  onClose: () => void;
  onSave: (cfg: AIConfig) => void;
}

export function SettingsModal({ open, value, onClose, onSave }: Props) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<AIConfig>(value);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  useEffect(() => {
    if (open) setDraft(value);
  }, [open, value]);
  if (!open) return null;

  const meta = PROVIDERS.find((p) => p.id === draft.provider) ?? PROVIDERS[0];
  const pick = (id: Provider) => {
    const m = PROVIDERS.find((p) => p.id === id)!;
    setDraft((d) => ({ ...d, provider: id, model: m.models[0] }));
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <div className="card w-full max-w-lg animate-fade-up p-6 shadow-pop">
        <div className="mb-5 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-white overflow-hidden">
              <img
                src="/brand/skoda_Auto3.png"
                alt=""
                className="h-full w-full object-contain p-1"
                draggable={false}
              />
            </span>
            <div>
              <h2 id="settings-title" className="text-lg font-bold">
                {t("settings.title")}
              </h2>
              <p className="text-sm text-muted">{t("settings.subtitle")}</p>
            </div>
          </div>
          <button
            className="icon-btn"
            onClick={onClose}
            aria-label="Close settings"
          >
            <Close />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="label" htmlFor="prov">
              {t("settings.provider")}
            </label>
            <select
              id="prov"
              className="field"
              value={draft.provider}
              onChange={(e) => pick(e.target.value as Provider)}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          {meta.needsKey && (
            <div>
              <label className="label" htmlFor="key">
                {t("settings.apiKey")}
              </label>
              <div className="flex gap-2">
                <input
                  id="key"
                  className="field font-mono"
                  type={showKey ? "text" : "password"}
                  placeholder={meta.keyHint}
                  value={draft.apiKey}
                  autoComplete="off"
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, apiKey: e.target.value }))
                  }
                />
                <button
                  type="button"
                  className="btn-subtle"
                  onClick={() => setShowKey((s) => !s)}
                >
                  {showKey ? t("settings.hide") : t("settings.show")}
                </button>
              </div>
              <p className="hint">{t("settings.keyHint")}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="model">
                {t("settings.model")}
              </label>
              <input
                id="model"
                className="field"
                list="model-list"
                value={draft.model}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, model: e.target.value }))
                }
              />
              <datalist id="model-list">
                {meta.models.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
            {meta.needsBase && (
              <div>
                <label className="label" htmlFor="base">
                  {t("settings.baseUrl")}
                </label>
                <input
                  id="base"
                  className="field font-mono"
                  placeholder="https://…/v1"
                  value={draft.baseUrl ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, baseUrl: e.target.value }))
                  }
                />
              </div>
            )}
          </div>

          {draft.provider === "mock" && (
            <p className="rounded-xl bg-good/10 px-3 py-2 text-sm text-good">
              {t("settings.demoNote")}
            </p>
          )}
          {draft.provider === "azure" && (
            <p className="rounded-xl bg-brand/10 px-3 py-2 text-sm text-brand">
              {t("settings.azureNote")}
            </p>
          )}
        </div>

        <div className="mt-6 flex items-center justify-between gap-2">
          <button
            type="button"
            className="btn-subtle !min-h-[38px]"
            disabled={testing}
            onClick={async () => {
              setTesting(true);
              setTestResult(null);
              try {
                const r = await api.testLLM(draft);
                setTestResult({
                  ok: r.ok,
                  msg: r.ok ? `Connected. Reply: ${r.reply || "(empty)"}` : (r.error || "Failed."),
                });
              } catch (e) {
                setTestResult({ ok: false, msg: e instanceof Error ? e.message : "Failed." });
              } finally {
                setTesting(false);
              }
            }}
          >
            {testing ? "Testing…" : "Test connection"}
          </button>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={onClose}>
              {t("settings.cancel")}
            </button>
            <button className="btn-primary" onClick={() => onSave(draft)}>
              <Check width={16} height={16} /> {t("settings.save")}
            </button>
          </div>
        </div>

        {testResult && (
          <p className={`mt-3 rounded-lg px-3 py-2 text-sm ${testResult.ok ? "bg-good/10 text-good" : "bg-bad/10 text-bad"}`}>
            {testResult.ok ? "✓ " : "✗ "}{testResult.msg}
          </p>
        )}
      </div>
    </div>
  );
}
