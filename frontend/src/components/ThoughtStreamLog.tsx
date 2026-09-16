import { useEffect, useRef, useState, type MouseEvent } from "react";
import type { LogLine } from "../lib/types";
import { useI18n } from "../lib/LanguageContext";
import { Terminal } from "./icons";

const LEVEL_COLOR: Record<string, string> = {
  info: "text-muted",
  success: "text-good",
  warn: "text-warn",
  error: "text-bad",
};

const MIN_H = 96;
const MAX_H = 420;
const DEFAULT_H = 160;

export function ThoughtStreamLog({
  lines,
  streaming,
}: {
  lines: LogLine[];
  streaming: boolean;
}) {
  const { t } = useI18n();
  const endRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>(() => {
    const saved = Number(localStorage.getItem("bpmn.log.h"));
    return saved >= MIN_H && saved <= MAX_H ? saved : DEFAULT_H;
  });
  const dragRef = useRef<{ startY: number; startH: number } | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines.length]);

  useEffect(() => {
    const onMove = (e: globalThis.MouseEvent) => {
      if (!dragRef.current) return;
      const delta = dragRef.current.startY - e.clientY;
      const next = Math.min(
        MAX_H,
        Math.max(MIN_H, dragRef.current.startH + delta),
      );
      setHeight(next);
    };
    const onUp = () => {
      if (dragRef.current) {
        localStorage.setItem("bpmn.log.h", String(height));
        dragRef.current = null;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [height]);

  const startDrag = (e: MouseEvent) => {
    dragRef.current = { startY: e.clientY, startH: height };
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
  };

  return (
    <div className="flex flex-col">
      <div
        onMouseDown={startDrag}
        role="separator"
        aria-orientation="horizontal"
        title="Drag to resize the log"
        className="group mb-0.5 flex h-3 cursor-row-resize items-center justify-center"
      >
        <span className="h-1 w-10 rounded-full bg-border transition-colors group-hover:bg-brand" />
      </div>

      <div className="mb-1.5 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-bold text-ink">
          <Terminal width={14} height={14} /> {t("log.title")}
        </span>
        <span
          className={`flex items-center gap-1 text-[11px] font-semibold ${streaming ? "text-good" : "text-muted"}`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${streaming ? "bg-good animate-pulse-ring" : "bg-muted"}`}
          />
          {streaming ? t("log.live") : t("log.idle")}
        </span>
      </div>

      <div className="console" style={{ height }}>
        {lines.length === 0 ? (
          <div className="console-line text-muted">{t("log.systemReady")}</div>
        ) : (
          lines.map((l) => (
            <div
              key={l.id}
              className={`console-line ${LEVEL_COLOR[l.level] || "text-muted"}`}
            >
              {l.text}
            </div>
          ))
        )}
        {streaming && (
          <span className="inline-block h-3 w-2 bg-brand align-middle animate-blink" />
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
