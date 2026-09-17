import { useCallback, useEffect, useRef, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { api, ApiError } from "./lib/api";
import { LanguageProvider } from './lib/LanguageContext';
import type {
  AIConfig,
  AgentId,
  AgentState,
  AutomationCandidate,
  ChatMessage,
  Explanation,
  GenerateResult,
  HistoryItem,
  Lint,
  LogLine,
  Persona,
  Preset,
  StreamEvent,
  OptimizeResult,
} from "./lib/types";
import { useLocalState, useToasts } from "./hooks/useLocalState";
import { TopBar } from "./components/TopBar";
import { AgentPipeline } from "./components/AgentPipeline";
import { SettingsModal } from "./components/SettingsModal";
import { InputPanel } from "./components/InputPanel";
import { InsightsPanel } from "./components/InsightsPanel";
import { BpmnCanvas, type CanvasHandle } from "./components/BpmnCanvas";
import { ChatPanel } from "./components/ChatPanel";
import { Toasts } from "./components/Toasts";


const DEFAULT_CFG: AIConfig = { provider: "mock", apiKey: "", model: "mock" };
const IDLE_AGENTS: Record<AgentId, AgentState> = {
  interpreter: "idle",
  modeler: "idle",
  validator: "idle",
  fixer: "idle",
  editor: "idle",
  optimizer: "idle",
  explainer: "idle",
};
const OPTIMIZE_PHRASE_RE =
  /^(optimize|improve)(\s+(this|the))?(\s+(process|model|diagram))?\.?$/i;

function HHandle() {
  return (
    <PanelResizeHandle className="group relative w-2 shrink-0">
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors group-hover:bg-brand group-data-[panel-resize-handle-state=drag]:bg-brand" />
      <div className="absolute left-1/2 top-1/2 h-8 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-border transition-colors group-hover:bg-brand" />
    </PanelResizeHandle>
  );
}
function VHandle() {
  return (
    <PanelResizeHandle className="group relative h-2 shrink-0">
      <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border transition-colors group-hover:bg-brand group-data-[panel-resize-handle-state=drag]:bg-brand" />
      <div className="absolute left-1/2 top-1/2 h-1 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full bg-border transition-colors group-hover:bg-brand" />
    </PanelResizeHandle>
  );
}

export default function App() {
  const canvasRef = useRef<CanvasHandle>(null);
  const lastEditRef = useRef<string>("");

  const [cfg, setCfg] = useLocalState<AIConfig>("bpmn.ai", DEFAULT_CFG);
  const [dark, setDark] = useLocalState<boolean>("bpmn.dark", true);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [description, setDescription] = useState("");
  const [xml, setXml] = useState<string | null>(null);
  const [xmlHistory, setXmlHistory] = useState<string[]>([]);
  const [lint, setLint] = useState<Lint | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [candidates, setCandidates] = useState<AutomationCandidate[] | null>(
    null,
  );
  const [persona, setPersona] = useState<Persona>("auditor");

  const [presets, setPresets] = useState<Preset[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  const [agents, setAgents] =
    useState<Record<AgentId, AgentState>>(IDLE_AGENTS);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [streaming, setStreaming] = useState(false);
  const logId = useRef(1);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const chatId = useRef(1);

  const [busy, setBusy] = useState({
    generate: false,
    fix: false,
    explain: false,
    automate: false,
  });
  const { toasts, push, dismiss } = useToasts();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.classList.toggle("light", !dark);
  }, [dark]);

  const reloadHistory = useCallback(() => {
    api
      .history()
      .then(setHistory)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    api
      .presets()
      .then(setPresets)
      .catch(() => undefined);
    reloadHistory();
  }, [reloadHistory]);

  const errMsg = (e: unknown) =>
    e instanceof ApiError
      ? e.code === "NO_API_KEY"
        ? "Add an AI API key in Settings first."
        : e.message
      : "Something went wrong.";

  const ensureConfigured = (): boolean => {
    const ok =
      cfg.provider === "mock" || cfg.provider === "ollama" || !!cfg.apiKey;
    if (!ok) {
      setSettingsOpen(true);
      push("error", "Add an AI API key to continue.");
    }
    return ok;
  };

  const pushLog = (level: LogLine["level"], text: string) =>
    setLogs((l) => [...l.slice(-200), { id: logId.current++, level, text }]);

  const applyModel = async (newXml: string, newLint: Lint | null) => {
    setXmlHistory((h) => (xml ? [...h.slice(-19), xml] : h));

    setXml(newXml);
    setLint(newLint);
    setExplanation(null);
    setCandidates(null);

    await canvasRef.current?.importXml(newXml);
  };

  const applyModelNoPush = async (
    previousXml: string,
    previousLint: Lint | null = null,
  ) => {
    const nextLint = previousLint ?? (await api.lint(previousXml));

    setXml(previousXml);
    setLint(nextLint);
    setExplanation(null);
    setCandidates(null);

    await canvasRef.current?.importXml(previousXml);
  };

  const undoEdit = async () => {
    if (xmlHistory.length === 0) return;

    const previousXml = xmlHistory[xmlHistory.length - 1];

    setXmlHistory((h) => h.slice(0, -1));

    await applyModelNoPush(previousXml);
  };

  const generate = async () => {
    if (!description.trim() || !ensureConfigured()) return;
    setBusy((b) => ({ ...b, generate: true }));
    setStreaming(true);
    setAgents(IDLE_AGENTS);
    pushLog(
      "info",
      `[System] Starting multi-agent loop for: "${description.trim().slice(0, 60)}${description.length > 60 ? "…" : ""}"`,
    );
    const holder: { result: GenerateResult | null } = { result: null };
    try {
      await api.generateStream(description, cfg, (e: StreamEvent) => {
        if (e.type === "agent" && e.agent && e.status) {
          setAgents((a) => ({ ...a, [e.agent!]: e.status! }));
        } else if (e.type === "log" && e.line) {
          pushLog(e.level || "info", e.line);
        } else if (e.type === "result" && e.data) {
          holder.result = e.data;
        } else if (e.type === "error") {
          pushLog("error", `[Error] ${e.error}`);
          push(
            "error",
            e.code === "NO_API_KEY"
              ? "Add an AI API key in Settings first."
              : e.error || "Generation failed.",
          );
        }
      });
      const finalResult = holder.result;
      if (finalResult && finalResult.xml) {
        await applyModel(finalResult.xml, finalResult.lint);
        setChatMessages([]);
        reloadHistory();
        const s = finalResult.lint?.totalScore;
        pushLog(
          "success",
          `[System] Done. Final health score ${s}/100 in ${finalResult.loops} loop(s).`,
        );
        push(
          "success",
          `Model generated - health ${s}/100 in ${finalResult.loops} loop(s).`,
        );
      }
    } catch (e) {
      pushLog("error", `[Error] ${errMsg(e)}`);
      push("error", errMsg(e));
    } finally {
      setStreaming(false);
      setBusy((b) => ({ ...b, generate: false }));
    }
  };

  const explainFromFile = async (uploadedXml: string) => {
    try {
      const l = await api.lint(uploadedXml);
      await applyModel(uploadedXml, l);
      setChatMessages([]);
      pushLog(
        "info",
        `[System] Uploaded model parsed. Health ${l.totalScore}/100.`,
      );
      push("success", `Loaded model - health ${l.totalScore}/100.`);
    } catch (e) {
      push("error", errMsg(e));
    }
  };

  const fixAll = async () => {
    if (!xml || !lint || !ensureConfigured()) return;
    setBusy((b) => ({ ...b, fix: true }));
    setAgents({ ...IDLE_AGENTS, fixer: "active" });
    pushLog("warn", `[Fixer] Repairing ${lint.issues.length} issue(s)…`);
    try {
      const res = await api.fix(xml, lint.issues, cfg);
      await applyModel(res.xml, res.lint);
      setAgents((a) => ({ ...a, fixer: "done" }));
      pushLog(
        "success",
        `[Fixer] Done. Health rose to ${res.lint.totalScore}/100.`,
      );
      push("success", `Fixed - health rose to ${res.lint.totalScore}/100.`);
    } catch (e) {
      setAgents((a) => ({ ...a, fixer: "idle" }));
      pushLog("error", `[Fixer] ${errMsg(e)}`);
      push("error", errMsg(e));
    } finally {
      setBusy((b) => ({ ...b, fix: false }));
    }
  };

  const sendEdit = async (instruction: string) => {
    if (!xml || chatBusy) return;
    if (!ensureConfigured()) return;
    const userMsg: ChatMessage = {
      id: chatId.current++,
      role: "user",
      text: instruction,
    };
    const agentMsg: ChatMessage = {
      id: chatId.current++,
      role: "agent",
      text: "Applying your change…",
      pending: true,
      scoreBefore: lint?.totalScore ?? null,
    };
    setChatMessages((m) => [...m, userMsg, agentMsg]);
    setChatBusy(true);
    setStreaming(true);
    if (OPTIMIZE_PHRASE_RE.test(instruction.trim())) {
      setAgents((a) => ({
        ...a,
        optimizer: "idle",
        validator: "idle",
        explainer: "idle",
      }));
      const holder: { result: OptimizeResult | null; failed: boolean } = {
        result: null,
        failed: false,
      };
      try {
        await api.optimizeStream(xml, cfg, (e) => {
          if (e.type === "agent" && e.agent && e.status) {
            setAgents((a) => ({ ...a, [e.agent!]: e.status! }));
          } else if (e.type === "log" && e.line) {
            pushLog(e.level || "info", e.line);
          } else if (e.type === "result" && e.data) {
            holder.result = e.data;
          } else if (e.type === "error") {
            holder.failed = true;
            pushLog("error", `[Error] ${e.error}`);
            push(
              "error",
              e.code === "NO_API_KEY"
                ? "Add an AI API key in Settings first."
                : e.error || "Optimization failed.",
            );
          }
        });
        const res = holder.result;
        if (res && res.xml && res.lint) {
          await applyModel(res.xml, res.lint);
          const before = res.beforeLint?.totalScore ?? lint?.totalScore ?? null;
          const after = res.lint.totalScore;
          const headline = res.rationale?.headline || "Process optimized.";
          setChatMessages((m) =>
            m.map((msg) =>
              msg.id === agentMsg.id
                ? {
                    ...msg,
                    pending: false,
                    text: headline,
                    scoreBefore: before,
                    scoreAfter: after,
                  }
                : msg,
            ),
          );
          push("success", `Optimized - health ${before ?? "?"} → ${after}.`);
        } else {
          setChatMessages((m) =>
            m.map((msg) =>
              msg.id === agentMsg.id
                ? {
                    ...msg,
                    pending: false,
                    failed: true,
                    text: res?.warning || "Could not optimize the process.",
                  }
                : msg,
            ),
          );
        }
      } catch (e) {
        setChatMessages((m) =>
          m.map((msg) =>
            msg.id === agentMsg.id
              ? { ...msg, pending: false, failed: true, text: errMsg(e) }
              : msg,
          ),
        );
        push("error", errMsg(e));
      } finally {
        setChatBusy(false);
        setStreaming(false);
      }
      return;
    }

    setAgents({ ...IDLE_AGENTS });

    const holder: { result: GenerateResult | null; failed: boolean } = {
      result: null,
      failed: false,
    };
    try {
      const contextual = lastEditRef.current
        ? `Previous instruction was: "${lastEditRef.current}". Now: ${instruction}`
        : instruction;

      await api.editStream(xml, contextual, cfg, (e: StreamEvent) => {
        if (e.type === "agent" && e.agent && e.status) {
          setAgents((a) => ({ ...a, [e.agent!]: e.status! }));
        } else if (e.type === "log" && e.line) {
          pushLog(e.level || "info", e.line);
        } else if (e.type === "result" && e.data) {
          holder.result = e.data;
        } else if (e.type === "error") {
          holder.failed = true;
          pushLog("error", `[Error] ${e.error}`);
          push(
            "error",
            e.code === "NO_API_KEY"
              ? "Add an AI API key in Settings first."
              : e.error || "Edit failed.",
          );
        }
      });
      const res = holder.result;
      if (res && res.xml) {
        await applyModel(res.xml, res.lint);
        lastEditRef.current = instruction;
        const after = res.lint?.totalScore ?? null;
        setChatMessages((m) =>
          m.map((msg) =>
            msg.id === agentMsg.id
              ? {
                  ...msg,
                  pending: false,
                  text: "Done - diagram updated.",
                  scoreAfter: after,
                }
              : msg,
          ),
        );
        push("success", `Edit applied - health ${after}/100.`);
      } else {
        setChatMessages((m) =>
          m.map((msg) =>
            msg.id === agentMsg.id
              ? {
                  ...msg,
                  pending: false,
                  failed: true,
                  text: holder.failed
                    ? "That edit could not be applied."
                    : "No change was produced.",
                }
              : msg,
          ),
        );
      }
    } catch (e) {
      setChatMessages((m) =>
        m.map((msg) =>
          msg.id === agentMsg.id
            ? { ...msg, pending: false, failed: true, text: errMsg(e) }
            : msg,
        ),
      );
      push("error", errMsg(e));
    } finally {
      setChatBusy(false);
      setStreaming(false);
    }
  };

  const explain = async () => {
    if (!xml || !ensureConfigured()) return;
    setBusy((b) => ({ ...b, explain: true }));
    setAgents((a) => ({ ...a, explainer: "active" }));
    pushLog("info", `[Explainer] Generating narrative for ${persona}...`);
    try {
      const result = await api.explain(xml, persona, cfg);
      setExplanation(result);
      setAgents((a) => ({ ...a, explainer: "done" }));
      pushLog("success", `[Explainer] Generated narrative for ${persona}.`);
    } catch (e) {
      setAgents((a) => ({ ...a, explainer: "idle" }));
      push("error", errMsg(e));
    } finally {
      setBusy((b) => ({ ...b, explain: false }));
    }
  };

  const automate = async () => {
    if (!xml || !ensureConfigured()) return;
    setBusy((b) => ({ ...b, automate: true }));
    try {
      const c = await api.automate(xml, cfg);
      setCandidates(c);
      pushLog("info", `[Automation] Found ${c.length} candidate task(s).`);
    } catch (e) {
      push("error", errMsg(e));
    } finally {
      setBusy((b) => ({ ...b, automate: false }));
    }
  };

  const onCanvasEdit = useCallback((editedXml: string) => {
    setXml(editedXml);
    api
      .lint(editedXml)
      .then(setLint)
      .catch(() => undefined);
  }, []);

  const onHoverIssue = (nodeId: string | null) =>
    canvasRef.current?.highlight(nodeId ? [nodeId] : []);
  const onAgentEvent = (agent: AgentId, status: AgentState) => {
    if (status === "idle") {
      setAgents({ ...IDLE_AGENTS }); 
    } else {
      setAgents((a) => ({ ...a, [agent]: status }));
    }
  };
  const exportXml = () => canvasRef.current?.exportXml();
  const exportPng = () => canvasRef.current?.exportPng();

  const exportFlow = async () => {
    if (!xml) return;
    try {
      const { blob, filename } = await api.exportPowerAutomate(xml);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      pushLog("success", "[Export] Power Automate package (.zip) generated.");
      push("success", "Power Automate package exported.");
    } catch (e) {
      push("error", errMsg(e));
    }
  };

  return (
    <LanguageProvider>
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar
        cfg={cfg}
        dark={dark}
        hasModel={!!xml}
        streaming={streaming}
        onToggleDark={() => setDark((d) => !d)}
        onOpenSettings={() => setSettingsOpen(true)}
        onExportXml={exportXml}
        onExportPng={exportPng}
      />

      <div className="border-b border-border bg-surface/50 px-4 py-2">
        <AgentPipeline states={agents} />
      </div>

      <PanelGroup
        direction="horizontal"
        autoSaveId="bpmn.layout.h"
        className="min-h-0 flex-1 p-3"
      >
        <Panel defaultSize={27} minSize={16} className="min-h-0">
          <InputPanel
            value={description}
            onChange={setDescription}
            onGenerate={generate}
            loading={busy.generate}
            presets={presets}
            history={history}
            onReloadHistory={reloadHistory}
            logLines={logs}
            streaming={streaming}
            cfg={cfg}
          />
        </Panel>

        <HHandle />

        <Panel defaultSize={45} minSize={28} className="min-h-0">
          <PanelGroup
            direction="vertical"
            autoSaveId="bpmn.layout.v"
            className="min-h-0"
          >
            <Panel defaultSize={64} minSize={25} className="min-h-0">
              <div className="card h-full overflow-hidden">
                <BpmnCanvas
                  ref={canvasRef}
                  onChange={onCanvasEdit}
                  onUpload={explainFromFile}
                  empty={!xml}
                  loading={busy.generate}
                />
              </div>
            </Panel>
            <VHandle />
            <Panel defaultSize={36} minSize={18} className="min-h-0">
              <div className="card h-full overflow-hidden">
                <ChatPanel
                  messages={chatMessages}
                  enabled={!!xml}
                  busy={chatBusy}
                  onSend={sendEdit}
                  onUndoEdit={undoEdit}
                  canUndoEdit={xmlHistory.length > 0}
                />
              </div>
            </Panel>
          </PanelGroup>
        </Panel>

        <HHandle />

        <Panel defaultSize={28} minSize={16} className="min-h-0">
          <InsightsPanel
            lint={lint}
            explanation={explanation}
            candidates={candidates}
            busy={{
              fix: busy.fix,
              explain: busy.explain,
              automate: busy.automate,
            }}
            persona={persona}
            onPersona={setPersona}
            onFixAll={fixAll}
            onExplain={explain}
            onAutomate={automate}
            onHoverIssue={onHoverIssue}
            onExportFlow={exportFlow}
            xml={xml}
            cfg={cfg}
            onApplyOptimized={(newXml, newLint) => applyModel(newXml, newLint)}
            onAgentEvent={onAgentEvent}
            onLog={pushLog}
            onToast={push}
            ensureConfigured={ensureConfigured}
          />
        </Panel>
      </PanelGroup>

      <SettingsModal
        open={settingsOpen}
        value={cfg}
        onClose={() => setSettingsOpen(false)}
        onSave={(c) => {
          setCfg(c);
          setSettingsOpen(false);
          push("success", "AI settings saved.");
        }}
      />
      <Toasts toasts={toasts} onDismiss={dismiss} />
    </div>
    </LanguageProvider>
  );
}
