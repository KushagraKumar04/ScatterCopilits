import { useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../lib/types';
import { useI18n } from '../lib/LanguageContext';
import { Chat, Send, Check, Alert } from './icons';

interface Props {
  messages: ChatMessage[];
  enabled: boolean;
  busy: boolean;
  onSend: (instruction: string) => void;
  onUndoEdit: () => void;
  canUndoEdit: boolean;
}

export function ChatPanel({ messages, enabled, busy, onSend, onUndoEdit, canUndoEdit }: Props) {
  const { t } = useI18n();
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const QUICK_EDITS = [
    t('chat.quick.optimize'),
    t('chat.quick.addApproval'),
    t('chat.quick.addSwimlanes'),
    t('chat.quick.renameVague'),
    t('chat.quick.addParallel'),
  ];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length]);

  const submit = () => {
    const value = text.trim();
    if (!value || !enabled || busy) return;
    onSend(value);
    setText('');
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="flex items-center gap-1.5 text-sm font-bold text-ink">
          <span className="grid h-6 w-6 place-items-center rounded-md bg-brand/10 text-brand"><Chat width={14} height={14} /></span>
          {t('chat.title')}
        </span>
        <div className="flex items-center gap-2">
          <button className="text-[11px] font-semibold text-muted hover:text-ink disabled:opacity-40 disabled:hover:text-muted"
            onClick={onUndoEdit} disabled={!canUndoEdit} title={t('chat.undoTooltip')}>
            ↺ {t('button.undo')}
          </button>
          <span className="text-[11px] font-semibold text-muted">{t('chat.agentLabel')}</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <p className="text-sm text-muted">
              {enabled ? t('chat.emptyEnabled') : t('chat.emptyDisabled')}
            </p>
            {enabled && (
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {QUICK_EDITS.map((q) => (
                  <button key={q} className="chip hover:border-brand/50 hover:text-ink" onClick={() => onSend(q)} disabled={busy}>
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className="animate-fade-up">
              {m.role === 'user' ? (
                <div className="chat-bubble-user">{m.text}</div>
              ) : (
                <div className="chat-bubble-agent">
                  <div className="flex items-start gap-2">
                    {m.pending ? (
                      <span className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-border border-t-brand" />
                    ) : m.failed ? (
                      <Alert width={14} height={14} className="mt-0.5 shrink-0 text-bad" />
                    ) : (
                      <Check width={14} height={14} className="mt-0.5 shrink-0 text-good" />
                    )}
                    <div>
                      <span>{m.text}</span>
                      {m.scoreAfter != null && (
                        <span className="mt-1 block text-xs text-muted">
                          Health {m.scoreBefore != null ? `${m.scoreBefore} → ` : ''}
                          <span className="font-bold text-good">{m.scoreAfter}</span>/100
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            className="field max-h-28 min-h-[44px] flex-1 resize-none py-2.5"
            rows={1}
            placeholder={enabled ? t('chat.placeholderEnabled') : t('chat.placeholderDisabled')}
            value={text}
            disabled={!enabled || busy}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button className="btn-primary !min-h-[44px] !px-3.5" onClick={submit} disabled={!enabled || busy || !text.trim()} aria-label={t('chat.send')}>
            {busy ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-fg/40 border-t-brand-fg" /> : <Send width={16} height={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
