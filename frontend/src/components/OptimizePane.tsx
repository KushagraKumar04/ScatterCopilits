import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type {
  AgentId,
  AgentState,
  AIConfig,
  Lint,
  OptimizeResult,
  OptimizeStreamEvent,
  ReviewReport,
  ReviewExportFormat,
} from "../lib/types";
import { useI18n } from "../lib/LanguageContext";
import {
  Wand,
  Bulb,
  Check,
  Close,
  Alert,
  ChevronRight,
  Download,
} from "./icons";

interface Props {
  xml: string | null;
  lint: Lint | null;
  cfg: AIConfig;
  onApply: (xml: string, lint: Lint) => void;
  onAgentEvent?: (agent: AgentId, status: AgentState) => void;
  onLog?: (level: "info" | "success" | "warn" | "error", text: string) => void;
  onToast?: (kind: "info" | "success" | "error", message: string) => void;
  ensureConfigured: () => boolean;
}

export function OptimizePane({
  xml,
  lint,
  cfg,
  onApply,
  onAgentEvent,
  onLog,
  onToast,
  ensureConfigured,
}: Props) {
  const { t } = useI18n();
  const [reviewBusy, setReviewBusy] = useState(false);
  const [review, setReview] = useState<ReviewReport | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const [optBusy, setOptBusy] = useState(false);
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null);
  const [optError, setOptError] = useState<string | null>(null);

  const [exportFormat, setExportFormat] = useState<ReviewExportFormat>("pdf");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setReview(null);
    setReviewError(null);
    setOptResult(null);
    setOptError(null);
  }, [xml]);

  const log = (level: "info" | "success" | "warn" | "error", text: string) =>
    onLog?.(level, text);
  const toast = (kind: "info" | "success" | "error", message: string) =>
    onToast?.(kind, message);

  const errMsg = (e: unknown) =>
    e instanceof ApiError
      ? e.code === "NO_API_KEY"
        ? t("toast.addApiKey")
        : e.message
      : t("toast.somethingWrong");

  const runReview = async () => {
    if (!xml || reviewBusy || !ensureConfigured()) return;
    setReviewBusy(true);
    setReviewError(null);
    log("info", "[Review] Generating a process review report.");
    try {
      const r = await api.review(xml, cfg);
      setReview(r);
      log(
        "success",
        `[Review] Report ready. Health ${r.healthScore}/100 (${r.band}).`,
      );
    } catch (e) {
      setReviewError(errMsg(e));
      toast("error", errMsg(e));
    } finally {
      setReviewBusy(false);
    }
  };

  const runOptimize = async () => {
    if (!xml || optBusy || !ensureConfigured()) return;
    setOptBusy(true);
    setOptError(null);
    setOptResult(null);
    onAgentEvent?.("optimizer", "idle");
    try {
      const holder: { result: OptimizeResult | null } = { result: null };
      await api.optimizeStream(xml, cfg, (e: OptimizeStreamEvent) => {
        if (e.type === "agent" && e.agent && e.status) {
          onAgentEvent?.(e.agent, e.status);
        } else if (e.type === "log" && e.line) {
          log(e.level || "info", e.line);
        } else if (e.type === "result" && e.data) {
          holder.result = e.data;
        } else if (e.type === "error") {
          log("error", `[Optimizer] ${e.error}`);
          toast(
            "error",
            e.code === "NO_API_KEY"
              ? t("toast.addApiKey")
              : e.error || "Optimization failed.",
          );
        }
      });
      if (holder.result) {
        setOptResult(holder.result);
        if (!holder.result.xml) {
          setOptError(
            holder.result.warning || "Could not produce an optimized version.",
          );
        } else {
          toast(
            "success",
            "Optimized version ready - review the comparison below.",
          );
        }
      }
    } catch (e) {
      setOptError(errMsg(e));
      toast("error", errMsg(e));
    } finally {
      setOptBusy(false);
    }
  };

  const applyOptimized = () => {
    if (optResult?.xml && optResult.lint) {
      onApply(optResult.xml, optResult.lint);
      toast("success", t("toast.optimizedApplied"));
      setOptResult(null);
    }
  };

  const discardOptimized = () => setOptResult(null);

  const doExport = async () => {
    if (!review || exporting) return;
    setExporting(true);
    try {
      const { blob, filename } = await api.exportReview(review, exportFormat);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast(
        "success",
        `${t("toast.reportExported")} ${exportFormat.toUpperCase()}.`,
      );
    } catch (e) {
      toast("error", errMsg(e));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* ---------------- Process Review Report ---------------- */}
      <div>
        <button
          className="btn-subtle mb-3 w-full"
          onClick={runReview}
          disabled={reviewBusy || !xml}
        >
          {reviewBusy ? (
            t("button.reviewing")
          ) : (
            <>
              <Bulb width={16} height={16} /> {t("button.reviewReport")}
            </>
          )}
        </button>
        {reviewBusy && <SkeletonLines />}
        {!reviewBusy && reviewError && <ErrorBox text={reviewError} />}
        {!reviewBusy && review && (
          <div className="animate-fade-up space-y-3 rounded-xl border border-border p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-ink">
                {t("review.title")}
              </span>
              <span
                className={`chip font-bold ${review.healthScore >= 90 ? "text-good" : review.healthScore >= 70 ? "text-warn" : "text-bad"}`}
              >
                {review.healthScore}/100 · {review.band}
              </span>
            </div>
            <p className="text-sm leading-relaxed text-muted">
              {review.summary}
            </p>
            <ReviewList
              title={t("review.bottlenecks")}
              items={review.bottlenecks}
              tone="warn"
            />
            <ReviewList
              title={t("review.risks")}
              items={review.risks}
              tone="bad"
            />
            <ReviewList
              title={t("review.missingSteps")}
              items={review.missingSteps}
              tone="warn"
            />
            <ReviewList
              title={t("review.recommendations")}
              items={review.recommendations}
              tone="brand"
            />
            <ReviewList
              title={t("review.automationOpportunities")}
              items={review.automationOpportunities}
              tone="good"
            />

            <div className="flex items-center gap-2 border-t border-border pt-3">
              <select
                className="field !min-h-[36px] w-28 !py-1.5 !text-xs"
                value={exportFormat}
                onChange={(e) =>
                  setExportFormat(e.target.value as ReviewExportFormat)
                }
                aria-label={t("optimize.exportFormat")}
              >
                <option value="pdf">PDF</option>
                <option value="docx">Word (.docx)</option>
                <option value="md">Markdown (.md)</option>
              </select>
              <button
                className="btn-subtle flex-1 !min-h-[36px] !text-xs"
                onClick={doExport}
                disabled={exporting}
              >
                {exporting ? (
                  t("button.exporting")
                ) : (
                  <>
                    <Download width={14} height={14} />{" "}
                    {t("button.exportReport")}
                  </>
                )}
              </button>
            </div>
          </div>
        )}
        {!reviewBusy && !review && !reviewError && (
          <Placeholder text={t("review.placeholder")} />
        )}
      </div>

      <div className="h-px bg-border" />

      {/* ---------------- Optimization Assistant ---------------- */}
      <div>
        <button
          className="btn-primary mb-3 w-full"
          onClick={runOptimize}
          disabled={optBusy || !xml}
        >
          {optBusy ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-fg/40 border-t-brand-fg" />{" "}
              {t("button.optimizing")}
            </>
          ) : (
            <>
              <Wand width={16} height={16} /> {t("button.optimize")}
            </>
          )}
        </button>
        {optBusy && <SkeletonLines />}
        {!optBusy && optError && !optResult?.xml && (
          <ErrorBox text={optError} />
        )}

        {!optBusy && optResult?.xml && optResult.lint && (
          <div className="animate-fade-up space-y-3 rounded-xl border border-brand/30 bg-brand/[0.04] p-3">
            {optResult.rationale && (
              <div>
                <p className="text-sm font-bold text-ink">
                  {optResult.rationale.headline}
                </p>
                <ul className="mt-1.5 space-y-1">
                  {optResult.rationale.changes.map((c, i) => (
                    <li key={i} className="flex gap-2 text-xs text-muted">
                      <Check
                        width={13}
                        height={13}
                        className="mt-0.5 shrink-0 text-good"
                      />
                      {c}
                    </li>
                  ))}
                </ul>
                {optResult.rationale.impact && (
                  <p className="mt-1.5 text-xs italic text-muted">
                    {optResult.rationale.impact}
                  </p>
                )}
              </div>
            )}

            {optResult.beforeLint && (
              <div className="flex items-center justify-center gap-3 rounded-lg bg-elevated/60 py-2.5">
                <ScoreBadge
                  label={t("optimize.before")}
                  score={optResult.beforeLint.totalScore}
                />
                <ChevronRight width={18} height={18} className="text-muted" />
                <ScoreBadge
                  label={t("optimize.after")}
                  score={optResult.lint.totalScore}
                  highlight
                />
              </div>
            )}

            {optResult.diff && (
              <div className="rounded-lg bg-elevated/40 p-2.5">
                <p className="mb-1 text-xs font-semibold text-ink">
                  {t("optimize.whatChanged")}
                </p>
                <p className="text-xs text-muted">{optResult.diff.summary}</p>
                {optResult.diff.removed_nodes.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {optResult.diff.removed_nodes.map((n) => (
                      <li key={n.id} className="text-xs text-bad">
                        − {n.name || n.id}
                      </li>
                    ))}
                  </ul>
                )}
                {optResult.diff.added_nodes.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {optResult.diff.added_nodes.map((n) => (
                      <li key={n.id} className="text-xs text-good">
                        + {n.name || n.id}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <button
                className="btn-primary !min-h-[38px] flex-1"
                onClick={applyOptimized}
              >
                <Check width={16} height={16} /> {t("button.useOptimized")}
              </button>
              <button
                className="btn-subtle !min-h-[38px]"
                onClick={discardOptimized}
              >
                <Close width={16} height={16} /> {t("button.keepOriginal")}
              </button>
            </div>
          </div>
        )}

        {!optBusy && !optResult && !optError && (
          <Placeholder text={t("optimize.placeholder")} />
        )}
      </div>
    </div>
  );
}

function ScoreBadge({
  label,
  score,
  highlight,
}: {
  label: string;
  score: number;
  highlight?: boolean;
}) {
  const tone = score >= 90 ? "good" : score >= 70 ? "warn" : "bad";
  return (
    <div className="text-center">
      <div
        className={`text-2xl font-extrabold ${highlight ? `text-${tone}` : "text-muted"}`}
      >
        {score}
      </div>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-muted">
        {label}
      </div>
    </div>
  );
}

function ReviewList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: string;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className={`mb-1 text-xs font-bold text-${tone}`}>{title}</p>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2 text-xs text-ink">
            <span
              className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-${tone}`}
            />
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Placeholder({ text }: { text: string }) {
  return <p className="px-2 py-6 text-center text-sm text-muted">{text}</p>;
}
function ErrorBox({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-bad/30 bg-bad/10 p-3 text-sm text-bad">
      <Alert width={16} height={16} className="mt-0.5 shrink-0" />
      {text}
    </div>
  );
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
