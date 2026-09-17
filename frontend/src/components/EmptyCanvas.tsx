import { useI18n } from '../lib/LanguageContext';

export function EmptyCanvas() {
  const { t } = useI18n();

  return (
    <div className="pointer-events-none absolute inset-0 grid place-items-center">
      <div className="pointer-events-auto max-w-md px-6 text-center animate-fade-up">
        <div className="relative overflow-hidden rounded-2xl border border-border bg-surface/70 px-8 py-7 shadow-card backdrop-blur-sm">
          <img
            src="/brand/skoda_Auto1.jpeg"
            alt=""
            aria-hidden="true"
            className="empty-hero-bg"
            draggable={false}
          />
          <div className="relative">
          <svg
            viewBox="0 0 360 180"
            className="empty-demo-svg mx-auto mb-6 w-full max-w-xs"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <g className="empty-demo">
              {/* Connectors — no stroke/fill attrs, styled via CSS */}
              <g fill="none" strokeLinecap="round">
                <line className="empty-demo-connector" x1="42" y1="100" x2="60" y2="100" />
                <line className="empty-demo-connector" x1="130" y1="100" x2="148" y2="100" />
                <path className="empty-demo-connector" d="M 182 100 L 186 82 L 210 82" />
                <path className="empty-demo-connector" d="M 182 100 L 186 118 L 210 118" />
                <line className="empty-demo-connector" x1="280" y1="82" x2="309" y2="82" />
                <line className="empty-demo-connector" x1="280" y1="118" x2="309" y2="118" />
              </g>

              {/* Start event */}
              <circle
                className="empty-shape empty-shape-event"
                style={{ animationDelay: '0s' }}
                cx="30" cy="100" r="12"
              />

              {/* Task 1 */}
              <rect
                className="empty-shape empty-shape-task"
                style={{ animationDelay: '0.35s' }}
                x="60" y="80" width="70" height="40" rx="6"
              />

              {/* Gateway */}
              <g transform="rotate(45 178 100)">
                <rect
                  className="empty-shape empty-shape-task"
                  style={{ animationDelay: '0.7s' }}
                  x="160" y="82" width="36" height="36" rx="4"
                />
              </g>

              {/* Top branch task */}
              <rect
                className="empty-shape empty-shape-task"
                style={{ animationDelay: '1.05s' }}
                x="210" y="62" width="70" height="40" rx="6"
              />

              {/* Bottom branch task */}
              <rect
                className="empty-shape empty-shape-task"
                style={{ animationDelay: '1.05s' }}
                x="210" y="98" width="70" height="40" rx="6"
              />

              {/* End events */}
              <circle
                className="empty-shape empty-shape-event empty-shape-event-end"
                style={{ animationDelay: '1.4s' }}
                cx="320" cy="82" r="11"
              />
              <circle
                className="empty-shape empty-shape-event empty-shape-event-end"
                style={{ animationDelay: '1.4s' }}
                cx="320" cy="118" r="11"
              />
            </g>
          </svg>

          <h3
            className="text-xl font-bold leading-tight"
            style={{ color: 'rgb(var(--ink))' }}
          >
            {t('canvas.emptyTitle')}
          </h3>
          <p
            className="mt-2 text-sm leading-relaxed"
            style={{ color: 'rgb(var(--muted))' }}
          >
            {t('canvas.emptyHint')}
          </p>
          </div>
        </div>
      </div>
    </div>
  );
}