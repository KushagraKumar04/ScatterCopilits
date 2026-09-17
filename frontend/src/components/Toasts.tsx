import type { Toast } from '../hooks/useLocalState';
import { useI18n } from '../lib/LanguageContext';
import { Check, Alert, Close } from './icons';

export function Toasts({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  const { t } = useI18n();
  return (
    <div className="pointer-events-none fixed top-16 left-1/2 z-[60] flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4">
      {toasts.map((t2) => {
        const tone = t2.kind === 'success' ? 'good' : t2.kind === 'error' ? 'bad' : 'brand';
        return (
          <div key={t2.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border border-${tone}/30 bg-elevated p-3 shadow-pop animate-fade-up`}
            role="status">
            <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-${tone}/15 text-${tone}`}>
              {t2.kind === 'error' ? <Alert width={14} height={14} /> : <Check width={14} height={14} />}
            </span>
            <p className="flex-1 text-sm text-ink">{t2.message}</p>
            <button className="icon-btn h-6 w-6 min-h-0 min-w-0" onClick={() => onDismiss(t2.id)} aria-label={t('toast.dismiss')}>
              <Close width={14} height={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
