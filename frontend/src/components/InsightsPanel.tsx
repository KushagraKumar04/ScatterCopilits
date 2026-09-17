import { useEffect, useRef, useState } from "react";
import type {
  AgentId,
  AgentState,
  AIConfig,
  AutomationCandidate,
  Explanation,
  Issue,
  Lint,
  Persona,
} from "../lib/types";
import { useI18n } from "../lib/LanguageContext";
import { useCountUp } from "../hooks/useCountUp";
import { Confetti } from "./Confetti";
import { OptimizePane } from "./OptimizePane";
import {
  Alert,
  Check,
  Wand,
  Robot,
  Bulb,
  Download,
  ChevronLeft,
  ChevronRight,
} from "./icons";

interface Props {
  lint: Lint | null;
  explanation: Explanation | null;
  candidates: AutomationCandidate[] | null;
  busy: { fix: boolean; explain: boolean; automate: boolean };
  persona: Persona;
  onPersona: (p: Persona) => void;
  onFixAll: () => void;
  onExplain: () => void;
  onAutomate: () => void;
  onHoverIssue: (nodeId: string | null) => void;
  onExportFlow: () => void;
  xml: string | null;
  cfg: AIConfig;
  onApplyOptimized: (xml: string, lint: Lint) => void;
  onAgentEvent: (agent: AgentId, status: AgentState) => void;
  onLog: (level: "info" | "success" | "warn" | "error", text: string) => void;
  onToast: (kind: "info" | "success" | "error", message: string) => void;
  ensureConfigured: () => boolean;
}

type Tab = "health" | "issues" | "explain" | "automate" | "optimize";

export function InsightsPanel(props: Props) {
  const { lint } = props;
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("health");
  const tabRowRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateTabScrollState = () => {
    const el = tabRowRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  };

  useEffect(() => {
    const el = tabRowRef.current;
    if (!el) return;
    updateTabScrollState();
    el.addEventListener("scroll", updateTabScrollState);
    const ro = new ResizeObserver(updateTabScrollState);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateTabScrollState);
      ro.disconnect();
    };
  }, []);

  useEffect(() => {
    updateTabScrollState();
  }, [tab]);

  const scrollTabsBy = (delta: number) =>
    tabRowRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  const CATEGORY_LABELS: Record<string, string> = {
    connectivity: t("health.connectivity"),
    completeness: t("health.completeness"),
    gateway: t("health.gateway"),
    naming: t("health.naming"),
    ownership: t("health.ownership"),
  };

  return (
    <section className="card flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand/10 text-brand">
          <Alert width={16} height={16} />
        </span>
        <h2 className="text-sm font-bold">{t("panel.title")}</h2>
      </div>

      <div className="relative flex items-center border-b border-border">
        {canScrollLeft && (
          <button
            className="absolute left-0 z-10 grid h-full w-7 shrink-0 place-items-center bg-gradient-to-r from-surface via-surface to-transparent text-muted hover:text-ink"
            onClick={() => scrollTabsBy(-100)}
            aria-label="Scroll tabs left"
          >
            <ChevronLeft width={14} height={14} />
          </button>
        )}
        <div
          ref={tabRowRef}
          role="tablist"
          className="scrollbar-none flex flex-1 items-center gap-1 overflow-x-auto px-3"
        >
          <TabBtn
            active={tab === "health"}
            onClick={() => setTab("health")}
            label={t("tabs.healthScore")}
          />
          <TabBtn
            active={tab === "issues"}
            onClick={() => setTab("issues")}
            label={t("tabs.issues")}
            badge={lint?.issues.length}
          />
          <TabBtn
            active={tab === "explain"}
            onClick={() => setTab("explain")}
            label={t("tabs.explainer")}
          />
          <TabBtn
            active={tab === "automate"}
            onClick={() => setTab("automate")}
            label={t("tabs.rpa")}
          />
          <TabBtn
            active={tab === "optimize"}
            onClick={() => setTab("optimize")}
            label={t("tabs.optimize")}
          />
        </div>
        {canScrollRight && (
          <button
            className="absolute right-0 z-10 grid h-full w-7 shrink-0 place-items-center bg-gradient-to-l from-surface via-surface to-transparent text-muted hover:text-ink"
            onClick={() => scrollTabsBy(100)}
            aria-label="Scroll tabs right"
          >
            <ChevronRight width={14} height={14} />
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === "health" && (
          <HealthPane lint={lint} categoryLabels={CATEGORY_LABELS} />
        )}
        {tab === "issues" && <IssuesPane {...props} />}
        {tab === "explain" && <ExplainPane {...props} />}
        {tab === "automate" && <AutomatePane {...props} />}
        {tab === "optimize" && (
          <OptimizePane
            xml={props.xml}
            lint={props.lint}
            cfg={props.cfg}
            onApply={props.onApplyOptimized}
            onAgentEvent={props.onAgentEvent}
            onLog={props.onLog}
            onToast={props.onToast}
            ensureConfigured={props.ensureConfigured}
          />
        )}
      </div>
    </section>
  );
}

function TabBtn({
  active,
  onClick,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  badge?: number;
}) {
  return (
    <button role="tab" data-active={active} className="tab" onClick={onClick}>
      {label}
      {badge != null && badge > 0 && (
        <span className="ml-0.5 rounded-full bg-bad/15 px-1.5 text-[11px] font-bold text-bad">
          {badge}
        </span>
      )}
    </button>
  );
}

function HealthPane({
  lint,
  categoryLabels,
}: {
  lint: Lint | null;
  categoryLabels: Record<string, string>;
}) {
  const { t } = useI18n();
  const score = lint?.totalScore ?? 0;
  const displayScore = useCountUp(lint ? score : 0, 950);

  // Fire confetti when the score transitions INTO 100 from any other value.
  const [confettiKey, setConfettiKey] = useState(0);
  const prevScoreRef = useRef<number | null>(null);
  useEffect(() => {
    if (!lint) return;
    if (score === 100 && prevScoreRef.current !== 100) {
      setConfettiKey((k) => k + 1);
    }
    prevScoreRef.current = score;
  }, [score, lint]);

  const tone = score >= 90 ? "good" : score >= 70 ? "warn" : "bad";
  const toneRGB = {
    good: "var(--good)",
    warn: "var(--warn)",
    bad: "var(--bad)",
  }[tone];
  const R = 52,
    C = 2 * Math.PI * R;
  const dash = lint ? (displayScore / 100) * C : 0;

  return (
    <div className="relative">
      <Confetti trigger={confettiKey} />
      <div className="flex flex-col items-center py-2">
        <div
          className="relative grid place-items-center"
          aria-label={`Process health score ${score} of 100`}
        >
          <svg
            width="150"
            height="150"
            viewBox="0 0 130 130"
            className="-rotate-90"
          >
            <circle
              cx="65"
              cy="65"
              r={R}
              fill="none"
              stroke="rgb(var(--border))"
              strokeWidth="10"
            />
            <circle
              cx="65"
              cy="65"
              r={R}
              fill="none"
              stroke={`rgb(${toneRGB})`}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${dash} ${C}`}
              style={{
                transition: "stroke-dasharray .6s cubic-bezier(.22,1,.36,1)",
              }}
            />
          </svg>
          <div className="absolute text-center">
            <div className="text-4xl font-extrabold leading-none text-ink">
              {lint ? displayScore : "-"}
            </div>
            <div className="mt-1 text-[10px] font-bold uppercase tracking-widest text-muted">
              {t("health.score")}
            </div>
          </div>
        </div>
        <span
          className={`mt-3 rounded-full px-3 py-1 text-sm font-bold text-${tone} bg-${tone}/10 border border-${tone}/30`}
        >
          {lint?.band ?? t("health.awaiting")}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {lint ? (
          Object.entries(lint.breakdown).map(([key, v], i) => {
            const pct = v.max ? Math.round((v.score / v.max) * 100) : 0;
            const bt = pct >= 85 ? "good" : pct >= 50 ? "warn" : "bad";
            return (
              <div key={key}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-semibold text-ink">
                    {i + 1}. {categoryLabels[key] ?? key} ({v.max}%)
                  </span>
                  <span className="font-mono font-bold text-muted">
                    {v.score} / {v.max}
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className={`h-full rounded-full bg-${bt} transition-all duration-500`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })
        ) : (
          <p className="px-2 py-6 text-center text-sm text-muted">
            {t("health.placeholder")}
          </p>
        )}
      </div>

      {lint && (
        <div className="mt-4 grid grid-cols-5 gap-1.5 text-center">
          {[
            [t("health.start"), lint.counts.startEvents],
            [t("health.end"), lint.counts.endEvents],
            [t("health.tasks"), lint.counts.tasks],
            [t("health.gates"), lint.counts.gateways],
            [t("health.flows"), lint.counts.flows],
          ].map(([label, n]) => (
            <div
              key={label as string}
              className="rounded-lg border border-border bg-elevated/50 py-1.5"
            >
              <div className="text-sm font-bold text-ink">{n as number}</div>
              <div className="text-[10px] text-muted">{label as string}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function IssuesPane({ lint, busy, onFixAll, onHoverIssue }: Props) {
  const { t } = useI18n();
  if (!lint) return <Placeholder text={t("issues.placeholder")} />;
  if (lint.issues.length === 0)
    return (
      <div className="grid place-items-center py-10 text-center animate-fade-up">
        <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-good/10 text-good">
          <Check />
        </div>
        <h3 className="font-bold text-ink">{t("issues.noneTitle")}</h3>
        <p className="mt-1 text-sm text-muted">{t("issues.noneBody")}</p>
      </div>
    );

  return (
    <div>
      <button
        className="btn-primary mb-3 w-full"
        onClick={onFixAll}
        disabled={busy.fix}
      >
        {busy.fix ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-fg/40 border-t-brand-fg" />{" "}
            {t("button.fixing")}
          </>
        ) : (
          <>
            <Wand width={16} height={16} /> {t("button.fixAll")}
          </>
        )}
      </button>
      <ul className="space-y-2">
        {lint.issues.map((it: Issue) => (
          <li
            key={it.id}
            onMouseEnter={() => onHoverIssue(it.nodeId || it.targetId || null)}
            onMouseLeave={() => onHoverIssue(null)}
            className="rounded-xl border border-border p-3 transition-colors hover:border-brand/40"
          >
            <div className="flex items-start gap-2">
              <span
                className={`mt-0.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full ${it.type === "critical" ? "bg-bad" : "bg-warn"}`}
              />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{it.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted">
                  {it.desc}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExplainPane({
  explanation,
  busy,
  persona,
  onPersona,
  onExplain,
  lint,
}: Props) {
  const { t } = useI18n();
  const personas: Persona[] = ["auditor", "manager", "engineer"];
  const personaLabel = (p: Persona) => t(`explain.${p}`);
  return (
    <div>
      <div className="mb-3 flex items-center gap-1 rounded-xl bg-elevated p-1">
        {personas.map((p) => (
          <button
            key={p}
            onClick={() => onPersona(p)}
            className={`flex-1 rounded-lg px-2 py-2 text-xs font-semibold capitalize transition-colors ${persona === p ? "bg-surface text-brand shadow-card" : "text-muted hover:text-ink"}`}
          >
            {personaLabel(p)}
          </button>
        ))}
      </div>
      <button
        className="btn-subtle mb-3 w-full"
        onClick={onExplain}
        disabled={busy.explain || !lint}
      >
        {busy.explain ? (
          t("button.explaining")
        ) : (
          <>
            <Bulb width={16} height={16} /> {t("button.explainFor")}{" "}
            {personaLabel(persona)}
          </>
        )}
      </button>

      {busy.explain && <SkeletonLines />}
      {!busy.explain && explanation && (
        <div className="animate-fade-up">
          <h3 className="text-base font-bold text-ink">
            {explanation.headline}
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed text-muted">
            {explanation.summary}
          </p>
          <ul className="mt-3 space-y-1.5">
            {explanation.bullets.map((b, i) => (
              <li key={i} className="flex gap-2 text-sm text-ink">
                <Check
                  width={16}
                  height={16}
                  className="mt-0.5 shrink-0 text-good"
                />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {!busy.explain && !explanation && (
        <Placeholder text={t("explain.placeholder")} />
      )}
    </div>
  );
}

function AutomatePane({
  candidates,
  busy,
  onAutomate,
  onExportFlow,
  lint,
}: Props) {
  const { t } = useI18n();
  const roiTone = (r: string) =>
    r === "High" ? "text-good" : r === "Medium" ? "text-warn" : "text-muted";
  return (
    <div>
      <button
        className="btn-subtle mb-3 w-full"
        onClick={onAutomate}
        disabled={busy.automate || !lint}
      >
        {busy.automate ? (
          t("button.scanning")
        ) : (
          <>
            <Robot width={16} height={16} /> {t("button.findAutomation")}
          </>
        )}
      </button>
      <button
        className="btn-primary mb-3 w-full"
        onClick={onExportFlow}
        disabled={!lint}
        title="Download an importable Power Automate package (.zip)"
      >
        <Download width={16} height={16} /> {t("button.exportPowerAutomate")}
      </button>
      {busy.automate && <SkeletonLines />}
      {!busy.automate && candidates && candidates.length > 0 && (
        <ul className="space-y-2 animate-fade-up">
          {candidates.map((c) => (
            <li key={c.id} className="rounded-xl border border-border p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">{c.name}</p>
                <span className={`text-xs font-bold ${roiTone(c.roi)}`}>
                  {c.roi} ROI
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted">{c.rationale}</p>
              <span className="chip mt-2">{c.tool}</span>
            </li>
          ))}
        </ul>
      )}
      {!busy.automate && candidates && candidates.length === 0 && (
        <Placeholder text={t("automate.none")} />
      )}
      {!busy.automate && !candidates && (
        <Placeholder text={t("automate.placeholder")} />
      )}
    </div>
  );
}

function Placeholder({ text }: { text: string }) {
  return <p className="px-2 py-8 text-center text-sm text-muted">{text}</p>;
}
function SkeletonLines() {
  return (
    <div className="space-y-2">
      <div className="skeleton h-4 w-3/4" />
      <div className="skeleton h-4 w-full" />
      <div className="skeleton h-4 w-5/6" />
      <div className="skeleton h-4 w-2/3" />
    </div>
  );
}
