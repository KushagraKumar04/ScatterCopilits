import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import BpmnModeler from "bpmn-js/lib/Modeler";
import { layoutProcess } from "bpmn-auto-layout";
import "bpmn-js/dist/assets/diagram-js.css";
import "bpmn-js/dist/assets/bpmn-font/css/bpmn.css";
import { useI18n } from "../lib/LanguageContext";
import { Upload, Sparkles, Grid } from "./icons";

export interface CanvasHandle {
  importXml: (xml: string) => Promise<void>;
  getXml: () => Promise<string>;
  exportXml: () => Promise<void>;
  exportPng: () => Promise<void>;
  highlight: (nodeIds: string[]) => void;
}

interface Props {
  onChange?: (xml: string) => void;
  onUpload?: (xml: string) => void;
  empty?: boolean;
  loading?: boolean;
}

const EMPTY_DIAGRAM = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" id="d" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false" />
  <bpmndi:BPMNDiagram id="Di"><bpmndi:BPMNPlane id="Pl" bpmnElement="Process_1" /></bpmndi:BPMNDiagram>
</bpmn:definitions>`;

function triggerDownload(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
}

const BPMN_NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL';
const BPMNDI_NS = 'http://www.omg.org/spec/BPMN/20100524/DI';

function ensureCollaboration(xml: string): string {
  // Two failure modes we fix here:
  //   1. Lanes exist but no collaboration -> add one.
  //   2. Collaboration exists but BPMNPlane points at the process -> redirect.
  // Without the redirect, bpmn-auto-layout flattens the process and drops
  // pool + lanes. Backend already does this for generated models; this is a
  // safety net for uploaded .bpmn files.
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'application/xml');

    const process = doc.getElementsByTagNameNS(BPMN_NS, 'process')[0];
    if (!process) return xml;

    const hasLanes = process.getElementsByTagNameNS(BPMN_NS, 'laneSet').length > 0;
    if (!hasLanes) return xml;

    let collab = doc.getElementsByTagNameNS(BPMN_NS, 'collaboration')[0] || null;

    if (!collab) {
      const processId = process.getAttribute('id') || 'Process_1';

      collab = doc.createElementNS(BPMN_NS, 'bpmn:collaboration');
      collab.setAttribute('id', 'Collaboration_1');

      const participant = doc.createElementNS(BPMN_NS, 'bpmn:participant');
      participant.setAttribute('id', 'Participant_1');
      participant.setAttribute('name', 'Process Pool');
      participant.setAttribute('processRef', processId);
      collab.appendChild(participant);

      process.parentNode?.insertBefore(collab, process);
    }

    const collabId = collab.getAttribute('id');
    if (!collabId) return xml;

    const planes = doc.getElementsByTagNameNS(BPMNDI_NS, 'BPMNPlane');
    for (const plane of Array.from(planes)) {
      if (plane.getAttribute('bpmnElement') !== collabId) {
        plane.setAttribute('bpmnElement', collabId);
      }
    }

    return new XMLSerializer().serializeToString(doc);
  } catch {
    return xml;
  }
}

function stripDiagram(xml: string): string {
  // bpmn-auto-layout expects semantic XML with NO DI section. If DI is present,
  // it can silently drop pool / lane shapes. Strip the entire <bpmndi:BPMNDiagram>
  // before handing off, and let the library regenerate everything from scratch.
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'application/xml');
    const diagrams = doc.getElementsByTagNameNS(BPMNDI_NS, 'BPMNDiagram');
    for (const d of Array.from(diagrams)) {
      d.parentNode?.removeChild(d);
    }
    return new XMLSerializer().serializeToString(doc);
  } catch {
    return xml;
  }
}

async function ensureLayout(xml: string): Promise<string> {
  // The backend now runs a deterministic layout pass for any model with lanes,
  // so if we already have a pool BPMNShape, we trust the DI as-is.
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'application/xml');
    const hasPoolShape = Array.from(
      doc.getElementsByTagNameNS(BPMNDI_NS, 'BPMNShape'),
    ).some((s) => {
      const ref = s.getAttribute('bpmnElement') || '';
      return ref.startsWith('Participant_') || ref.startsWith('Pool_');
    });
    if (hasPoolShape) return xml;
  } catch {
    // fall through
  }

  // No pool DI means this is a plain process (no lanes). bpmn-auto-layout
  // handles that case correctly.
  try {
    const laid = await layoutProcess(xml);
    return laid || xml;
  } catch (err) {
    console.warn('[BpmnCanvas] Auto-layout failed, using raw XML:', err);
    return xml;
  }
}

const ico = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};
const ZoomIn = () => (
  <svg {...ico}>
    <circle cx="11" cy="11" r="7" />
    <path d="M11 8v6M8 11h6M21 21l-4.3-4.3" />
  </svg>
);
const ZoomOut = () => (
  <svg {...ico}>
    <circle cx="11" cy="11" r="7" />
    <path d="M8 11h6M21 21l-4.3-4.3" />
  </svg>
);
const Fit = () => (
  <svg {...ico}>
    <path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" />
  </svg>
);
const UndoIco = () => (
  <svg {...ico}>
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h11a5 5 0 0 1 0 10h-1" />
  </svg>
);
const RedoIco = () => (
  <svg {...ico}>
    <path d="m15 14 5-5-5-5" />
    <path d="M20 9H9a5 5 0 0 0 0 10h1" />
  </svg>
);

export const BpmnCanvas = forwardRef<CanvasHandle, Props>(function BpmnCanvas(
  { onChange, onUpload, empty, loading },
  ref,
) {
  const { t } = useI18n();
  const hostRef = useRef<HTMLDivElement>(null);
  const modelerRef = useRef<BpmnModeler | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showPalette, setShowPalette] = useState(true);
  const [zoomPct, setZoomPct] = useState(100);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  useEffect(() => {
    if (!hostRef.current) return;
    const host = hostRef.current;
    const modeler = new BpmnModeler({
      container: host,
      keyboard: { bindTo: document },
    });
    modelerRef.current = modeler;
    modeler.importXML(EMPTY_DIAGRAM).catch(() => undefined);

    const emit = async () => {
      try {
        const { xml } = await modeler.saveXML({ format: true });
        if (xml) onChange?.(xml);
      } catch {
        void 0;
      }
    };

    const refreshUndo = () => {
      try {
        const cs = modeler.get<any>("commandStack");
        setCanUndo(!!cs.canUndo?.());
        setCanRedo(!!cs.canRedo?.());
      } catch {
        void 0;
      }
    };
    const refreshZoom = () => {
      try {
        setZoomPct(Math.round((modeler.get<any>("canvas").zoom() || 1) * 100));
      } catch {
        void 0;
      }
    };

    modeler.on("commandStack.changed", emit);
    modeler.on("commandStack.changed", refreshUndo);
    modeler.on("canvas.viewbox.changed", refreshZoom);

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      try {
        const zoomScroll = modeler.get<any>("zoomScroll");
        const rect = host.getBoundingClientRect();
        const position = {
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
        };
        const delta = -event.deltaY / 500;
        zoomScroll.stepZoom(delta, position);
      } catch {
        void 0;
      }
    };
    host.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      host.removeEventListener("wheel", onWheel);
      modeler.destroy();
    };
  }, []);

  const zoomBy = (factor: number) => {
    try {
      const canvas = modelerRef.current!.get<any>("canvas");
      const next = Math.min(4, Math.max(0.2, (canvas.zoom() || 1) * factor));
      canvas.zoom(next);
    } catch {
      void 0;
    }
  };
  const fit = () => {
    try {
      modelerRef.current!.get<any>("canvas").zoom("fit-viewport", "auto");
    } catch {
      void 0;
    }
  };
  const undo = () => {
    try {
      modelerRef.current!.get<any>("commandStack").undo();
    } catch {
      void 0;
    }
  };
  const redo = () => {
    try {
      modelerRef.current!.get<any>("commandStack").redo();
    } catch {
      void 0;
    }
  };

  useImperativeHandle(ref, () => ({
    importXml: async (xml: string) => {
      const modeler = modelerRef.current!;
      const laidOut = await ensureLayout(xml);
      await modeler.importXML(laidOut);

      // Render guard: if the XML declares lanes + collaboration but bpmn-js
      // rendered zero lanes, the DI is wrong. Log loudly so we catch it
      // immediately instead of shipping a lane-less diagram to the judges.
      const declaresLanes = /<[^>]*laneSet/.test(laidOut);
      const declaresCollab = /<[^>]*collaboration/.test(laidOut);
      if (declaresLanes && declaresCollab) {
        try {
          const registry = modeler.get("elementRegistry") as any;
          const laneCount = registry
            .filter((el: any) => el.businessObject?.$type === "bpmn:Lane")
            .length;
          if (laneCount === 0) {
            console.error(
              "[BpmnCanvas] RENDER GUARD FAILED: XML declares lanes but 0 " +
              "lanes rendered. DI is missing pool/lane shapes. Check bpmn_layout.py.",
            );
          } else {
            console.info(`[BpmnCanvas] Render guard OK: ${laneCount} lanes rendered.`);
          }
        } catch {
          void 0;
        }
      }

      try {
        (modeler.get("canvas") as any).zoom("fit-viewport", "auto");
      } catch {
        void 0;
      }
    },
    getXml: async () => {
      const { xml } = await modelerRef.current!.saveXML({ format: true });
      return xml || "";
    },
    exportXml: async () => {
      const { xml } = await modelerRef.current!.saveXML({ format: true });
      const blob = new Blob([xml || ""], { type: "application/xml" });
      const url = URL.createObjectURL(blob);
      triggerDownload(url, "process.bpmn");
      URL.revokeObjectURL(url);
    },
    exportPng: async () => {
      const { svg } = await modelerRef.current!.saveSVG();
      const img = new window.Image();
      const svgBlob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
      const url = URL.createObjectURL(svgBlob);
      await new Promise<void>((resolve) => {
        img.onload = () => {
          const scale = 2;
          const canvas = document.createElement("canvas");
          canvas.width = (img.width || 1200) * scale;
          canvas.height = (img.height || 800) * scale;
          const ctx = canvas.getContext("2d")!;
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.scale(scale, scale);
          ctx.drawImage(img, 0, 0);
          triggerDownload(canvas.toDataURL("image/png"), "process.png");
          URL.revokeObjectURL(url);
          resolve();
        };
        img.src = url;
      });
    },
    highlight: (nodeIds: string[]) => {
      const modeler = modelerRef.current;
      if (!modeler) return;
      const canvas = modeler.get("canvas") as any;
      const registry = modeler.get("elementRegistry") as any;
      registry
        .getAll()
        .forEach((el: any) => canvas.removeMarker(el.id, "issue-node"));
      nodeIds.forEach((id) => {
        if (id && registry.get(id)) canvas.addMarker(id, "issue-node");
      });
    },
  }));

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onUpload?.(String(reader.result || ""));
    reader.readAsText(file);
  };

  return (
    <div
      className="relative h-full w-full"
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div
        ref={hostRef}
        className={`absolute inset-0 ${showPalette ? "" : "hide-palette"}`}
        aria-label="BPMN diagram canvas"
        role="img"
      />

      <div className="absolute right-3 top-3 z-10 flex gap-2">
        <button
          className="icon-btn border border-border bg-elevated"
          onClick={() => setShowPalette((s) => !s)}
          title={showPalette ? t("canvas.hideTools") : t("canvas.showTools")}
          aria-label={
            showPalette ? t("canvas.hideTools") : t("canvas.showTools")
          }
        >
          <Grid width={16} height={16} />
        </button>
        <label
          className="btn-subtle cursor-pointer"
          title={t("canvas.uploadTooltip")}
        >
          <Upload width={16} height={16} /> {t("button.upload")}
          <input
            type="file"
            accept=".bpmn,.xml,text/xml"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </label>
      </div>

      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-1 rounded-xl border border-border bg-surface/90 p-1 backdrop-blur">
        <button
          className="icon-btn"
          onClick={() => zoomBy(1 / 1.15)}
          title={t("canvas.zoomOut")}
          aria-label={t("canvas.zoomOut")}
        >
          <ZoomOut />
        </button>
        <button
          className="min-w-[52px] rounded-lg px-2 py-1 text-xs font-semibold text-muted hover:text-ink"
          onClick={() => {
            try {
              modelerRef.current!.get<any>("canvas").zoom(1);
            } catch {
              void 0;
            }
          }}
          title="Reset to 100%"
        >
          {zoomPct}%
        </button>
        <button
          className="icon-btn"
          onClick={() => zoomBy(1.15)}
          title={t("canvas.zoomIn")}
          aria-label={t("canvas.zoomIn")}
        >
          <ZoomIn />
        </button>
        <span className="mx-0.5 h-5 w-px bg-border" />
        <button
          className="icon-btn"
          onClick={fit}
          title={t("canvas.fitScreen")}
          aria-label={t("canvas.fitScreen")}
        >
          <Fit />
        </button>
        <span className="mx-0.5 h-5 w-px bg-border" />
        <button
          className="icon-btn"
          onClick={undo}
          disabled={!canUndo}
          title={t("canvas.undo")}
          aria-label={t("canvas.undo")}
        >
          <UndoIco />
        </button>
        <button
          className="icon-btn"
          onClick={redo}
          disabled={!canRedo}
          title={t("canvas.redo")}
          aria-label={t("canvas.redo")}
        >
          <RedoIco />
        </button>
      </div>

      {empty && !loading && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center pl-40">
          <div className="max-w-sm text-center animate-fade-up">
            <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand/10 text-brand">
              <Sparkles />
            </div>
            <h3 className="text-lg font-bold text-slate-800">
              {t("canvas.emptyTitle")}
            </h3>
            <p className="mt-1.5 text-sm text-slate-500">
              {t("canvas.emptyBody")}{" "}
              <span className="font-semibold text-slate-800">
                {t("canvas.emptyBodyGenerate")}
              </span>
              , {t("canvas.emptyBodyOr")}{" "}
              <code className="rounded bg-slate-200 px-1 text-slate-700">
                {t("canvas.emptyBodyFile")}
              </code>{" "}
              {t("canvas.emptyBodyEnd")}
            </p>
          </div>
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 z-20 grid place-items-center bg-canvas/70 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3 animate-fade-up">
            <div className="h-9 w-9 animate-spin rounded-full border-[3px] border-border border-t-brand" />
            <p className="text-sm font-semibold text-muted">
              {t("canvas.loading")}
            </p>
          </div>
        </div>
      )}

      {dragOver && (
        <div className="absolute inset-3 z-30 grid place-items-center rounded-2xl border-2 border-dashed border-brand bg-brand/5">
          <p className="text-sm font-semibold text-brand">
            {t("canvas.dropHint")}
          </p>
        </div>
      )}
    </div>
  );
});
