import { useEffect, useState } from 'react';
import { useI18n } from '../lib/LanguageContext';

const NARRATION_KEYS = [
  'skeleton.parsing',
  'skeleton.extracting',
  'skeleton.modelling',
  'skeleton.wiring',
  'skeleton.validating',
  'skeleton.scoring',
];

const ROTATE_MS = 1600;

export function SkeletonBpmn() {
  const { t } = useI18n();
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStep((s) => (s + 1) % NARRATION_KEYS.length);
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="skeleton-bpmn absolute inset-0 z-20 grid place-items-center bg-canvas/85 backdrop-blur-sm">
      <div className="flex w-full max-w-3xl flex-col items-center gap-8 px-8">
        <svg
          viewBox="0 0 800 320"
          className="w-full"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Connectors */}
          <g className="skeleton-lines">
            <line
              className="skeleton-line"
              x1="82" y1="160" x2="140" y2="160"
              style={{ animationDelay: '0.7s' }}
            />
            <line
              className="skeleton-line"
              x1="260" y1="160" x2="305" y2="160"
              style={{ animationDelay: '1.5s' }}
            />
            <path
              className="skeleton-line"
              d="M355 160 L355 130 L440 130"
              style={{ animationDelay: '2.3s' }}
            />
            <path
              className="skeleton-line"
              d="M355 160 L355 210 L440 210"
              style={{ animationDelay: '2.3s' }}
            />
            <line
              className="skeleton-line"
              x1="560" y1="130" x2="620" y2="130"
              style={{ animationDelay: '3.1s' }}
            />
            <line
              className="skeleton-line"
              x1="560" y1="210" x2="620" y2="210"
              style={{ animationDelay: '3.1s' }}
            />
          </g>

          {/* Start event */}
          <g className="skeleton-shape" style={{ animationDelay: '0.1s' }}>
            <g className="skeleton-shape-pulse">
              <circle className="skeleton-event" cx="62" cy="160" r="18" />
            </g>
          </g>

          {/* Task 1 */}
          <g className="skeleton-shape" style={{ animationDelay: '0.9s' }}>
            <g className="skeleton-shape-pulse">
              <rect
                className="skeleton-task"
                x="140" y="120" width="120" height="80" rx="10"
              />
            </g>
          </g>

          {/* Gateway */}
          <g className="skeleton-shape" style={{ animationDelay: '1.7s' }}>
            <g className="skeleton-shape-pulse">
              <rect
                className="skeleton-gateway"
                x="305" y="135" width="50" height="50"
                transform="rotate(45 330 160)"
              />
            </g>
          </g>

          {/* Top branch */}
          <g className="skeleton-shape" style={{ animationDelay: '2.5s' }}>
            <g className="skeleton-shape-pulse">
              <rect
                className="skeleton-task"
                x="440" y="90" width="120" height="80" rx="10"
              />
            </g>
          </g>

          {/* Bottom branch */}
          <g className="skeleton-shape" style={{ animationDelay: '2.5s' }}>
            <g className="skeleton-shape-pulse">
              <rect
                className="skeleton-task"
                x="440" y="170" width="120" height="80" rx="10"
              />
            </g>
          </g>

          {/* End events */}
          <g className="skeleton-shape" style={{ animationDelay: '3.3s' }}>
            <g className="skeleton-shape-pulse">
              <circle
                className="skeleton-event skeleton-event-end"
                cx="638" cy="130" r="18"
              />
            </g>
          </g>
          <g className="skeleton-shape" style={{ animationDelay: '3.3s' }}>
            <g className="skeleton-shape-pulse">
              <circle
                className="skeleton-event skeleton-event-end"
                cx="638" cy="210" r="18"
              />
            </g>
          </g>
        </svg>

        <div className="flex w-full max-w-md flex-col items-center gap-3">
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-border/60">
            <div className="skeleton-progress absolute inset-y-0 left-0 rounded-full bg-brand" />
          </div>
          <p
            key={step}
            role="status"
            aria-live="polite"
            className="animate-fade-up text-sm font-semibold text-brand"
          >
            {t(NARRATION_KEYS[step])}
          </p>
        </div>
      </div>
    </div>
  );
}