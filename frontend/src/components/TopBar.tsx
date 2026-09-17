import type { AIConfig } from "../lib/types";
import { useI18n } from "../lib/LanguageContext";
import {
  Settings,
  Moon,
  Sun,
  Sparkles,
  Download,
  Image,
  Shield,
} from "./icons";

const LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Claude",
  gemini: "Gemini",
  xai: "Grok",
  groq: "Groq",
  mistral: "Mistral",
  openrouter: "OpenRouter",
  deepseek: "DeepSeek",
  together: "Together",
  ollama: "Ollama",
  custom: "Custom",
  azure: "Azure (MI)",
  llmaas: "LLMaaS",
  mock: "Demo mode",
};

interface Props {
  cfg: AIConfig;
  dark: boolean;
  hasModel: boolean;
  streaming: boolean;
  onToggleDark: () => void;
  onOpenSettings: () => void;
  onExportXml: () => void;
  onExportPng: () => void;
}

export function TopBar({
  cfg,
  dark,
  hasModel,
  streaming,
  onToggleDark,
  onOpenSettings,
  onExportXml,
  onExportPng,
}: Props) {
  const { locale, setLocale, t } = useI18n();
  const configured =
    cfg.provider === "mock" ||
    cfg.provider === "ollama" ||
    cfg.provider === "azure" ||
    !!cfg.apiKey;

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface/80 px-4 py-2.5 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <span className="topbar-logo">
            <img
              src={dark ? "/brand/skoda_Auto7.jpeg" : "/brand/skoda_Auto2.png"}
              alt=""
              className="topbar-logo-img"
              draggable={false}
            />
          </span>
          <div>
            <h1 className="text-base font-extrabold leading-none">
              {t("app.title")}
            </h1>
            <span className="chip mt-1 !py-0.5 !text-[10px]">
              {t("app.version")}
            </span>
          </div>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <span className="chip-live">
            <span
              className={`h-1.5 w-1.5 rounded-full bg-good ${streaming ? "animate-pulse-ring" : ""}`}
            />
            {streaming
              ? t("topbar.multiAgentRunning")
              : t("topbar.multiAgentActive")}
          </span>
          <span className="chip-strict">
            <Shield width={12} height={12} /> {t("topbar.linterStrict")}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="btn-subtle"
          onClick={onExportXml}
          disabled={!hasModel}
          title={t("topbar.exportXml")}
        >
          <Download width={16} height={16} />
          <span className="hidden sm:inline">{t("topbar.exportXml")}</span>
        </button>
        <button
          className="btn-subtle"
          onClick={onExportPng}
          disabled={!hasModel}
          title={t("topbar.exportPng")}
        >
          <Image width={16} height={16} />
          <span className="hidden sm:inline">{t("topbar.exportPng")}</span>
        </button>
        <button
          className="btn-subtle"
          onClick={onOpenSettings}
          title={t("topbar.settings")}
        >
          <Settings width={16} height={16} />
          <span className="hidden sm:inline">
            {LABELS[cfg.provider] ?? cfg.provider}
          </span>
          <span
            className={`ml-1 inline-block h-2 w-2 rounded-full ${configured ? "bg-good" : "bg-warn"}`}
            title={configured ? "AI configured" : "Add an API key"}
          />
        </button>
        <button
          className="btn-subtle !min-h-[36px] !px-3"
          onClick={() => setLocale(locale === "en" ? "de" : "en")}
          title={t("topbar.language")}
          aria-label={t("topbar.language")}
        >
          <span
            className={locale === "en" ? "font-bold text-ink" : "text-muted"}
          >
            EN
          </span>
          <span className="mx-1 text-muted">/</span>
          <span
            className={locale === "de" ? "font-bold text-ink" : "text-muted"}
          >
            DE
          </span>
        </button>
        <button
          className="icon-btn"
          onClick={onToggleDark}
          aria-label={t("topbar.toggleTheme")}
        >
          {dark ? <Sun /> : <Moon />}
        </button>
      </div>
    </header>
  );
}
