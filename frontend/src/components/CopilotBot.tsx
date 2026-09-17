import React, { useEffect, useRef, useState } from 'react';
import type { AIConfig, Lint } from '../lib/types';
import { api } from '../lib/api';
import { useI18n } from '../lib/LanguageContext';
import { Close, Send, Sparkles } from './icons';

interface Message {
  id: number;
  role: 'assistant' | 'user';
  text: string;
  error?: boolean;
}

interface Suggestion {
  label: string;
  kind: 'action' | 'chat';
  action?: 'fix' | 'explain' | 'automate' | 'optimize';
  prompt?: string;
}

interface Props {
  xml: string | null;
  lint: Lint | null;
  cfg: AIConfig;
  onFixAll: () => void;
  onExplain: () => void;
  onAutomate: () => void;
  onOptimize: () => void;
  ensureConfigured: () => boolean;
}

const INTRO_KEY = 'bpmn.bot.intro.seen';

export function CopilotBot({
  xml, lint, cfg, onFixAll, onExplain, onAutomate, onOptimize, ensureConfigured,
}: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [showWave, setShowWave] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(1);

  // Show the intro wave on first ever visit.
  useEffect(() => {
    const seen = localStorage.getItem(INTRO_KEY);
    if (!seen) {
      setShowWave(true);
      const id = setTimeout(() => {
        setShowWave(false);
        localStorage.setItem(INTRO_KEY, '1');
      }, 6500);
      return () => clearTimeout(id);
    }
  }, []);

  // Reset conversation when the model changes (fresh context).
  useEffect(() => {
    setMessages([]);
  }, [xml]);

  // Auto-scroll on new messages.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages.length, busy]);

  const hasModel = !!xml;
  const issueCount = lint?.issues.length ?? 0;
  const score = lint?.totalScore ?? 0;

  const buildSuggestions = (): Suggestion[] => {
    if (!hasModel) {
      return [
        { label: t('bot.sg.howStart'), kind: 'chat', prompt: t('bot.sg.howStart') },
        { label: t('bot.sg.whatCanDo'), kind: 'chat', prompt: t('bot.sg.whatCanDo') },
      ];
    }
    if (issueCount > 0) {
      return [
        { label: t('bot.sg.fix'), kind: 'action', action: 'fix' },
        { label: t('bot.sg.explain'), kind: 'action', action: 'explain' },
        { label: t('bot.sg.why'), kind: 'chat', prompt: t('bot.sg.why') },
      ];
    }
    return [
      { label: t('bot.sg.explain'), kind: 'action', action: 'explain' },
      { label: t('bot.sg.automate'), kind: 'action', action: 'automate' },
      { label: t('bot.sg.optimize'), kind: 'action', action: 'optimize' },
    ];
  };

  const triggerAction = (kind: 'fix' | 'explain' | 'automate' | 'optimize') => {
    if (!ensureConfigured()) return;
    const labelMap = {
      fix: t('bot.sg.fix'),
      explain: t('bot.sg.explain'),
      automate: t('bot.sg.automate'),
      optimize: t('bot.sg.optimize'),
    };
    setMessages((m) => [...m, { id: idRef.current++, role: 'user', text: labelMap[kind] }]);
    setMessages((m) => [
      ...m,
      { id: idRef.current++, role: 'assistant', text: t(`bot.action.${kind}`) },
    ]);
    if (kind === 'fix') onFixAll();
    else if (kind === 'explain') onExplain();
    else if (kind === 'automate') onAutomate();
    else if (kind === 'optimize') onOptimize();
  };

  const sendMessage = async (text: string) => {
    const clean = text.trim();
    if (!clean || busy) return;
    if (!ensureConfigured()) return;
    setMessages((m) => [...m, { id: idRef.current++, role: 'user', text: clean }]);
    setInput('');
    setBusy(true);
    try {
      const reply = await api.assistantChat(xml || '', clean, '', cfg);
      setMessages((m) => [...m, { id: idRef.current++, role: 'assistant', text: reply }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not reach the assistant.';
      setMessages((m) => [...m, { id: idRef.current++, role: 'assistant', text: msg, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const greeting = !hasModel
    ? t('bot.greet.empty')
    : issueCount > 0
    ? t('bot.greet.issues').replace('{n}', String(issueCount))
    : t('bot.greet.clean').replace('{s}', String(score));

  return (
    <>
      {/* Floating action button */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={`bot-fab ${showWave ? 'bot-fab-wave' : ''}`}
          aria-label={t('bot.open')}
        >
          <span className="bot-fab-pulse" />
          <img
            src="/brand/skoda_Auto7.jpeg"
            alt=""
            className="h-full w-full rounded-full object-cover"
            draggable={false}
          />
          {!hasModel && <span className="bot-fab-dot" />}
        </button>
      )}

      {/* Speech-bubble wave on first load */}
      {showWave && !open && (
        <div className="bot-wave" onClick={() => { setShowWave(false); setOpen(true); }}>
          <strong>{t('bot.name')}</strong>
          <span>{t('bot.wave')}</span>
        </div>
      )}

      {/* Panel */}
      {open && (
        <div className="bot-panel" role="dialog" aria-label={t('bot.name')}>
          <header className="bot-panel-header">
            <div className="flex items-center gap-2.5">
              <div className="bot-avatar overflow-hidden">
                <img
                  src="/brand/skoda_Auto7.jpeg"
                  alt=""
                  className="h-full w-full rounded-full object-cover"
                  draggable={false}
                />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-bold text-ink">{t('bot.name')}</div>
                <div className="text-[10px] text-muted">{t('bot.subtitle')}</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                className="icon-btn !min-w-[28px] !min-h-[28px]"
                onClick={() => { setMessages([]); }}
                title={t('bot.new')}
                aria-label={t('bot.new')}
              >
                <Sparkles width={13} height={13} />
              </button>
              <button
                className="icon-btn !min-w-[28px] !min-h-[28px]"
                onClick={() => setOpen(false)}
                title={t('bot.close')}
                aria-label={t('bot.close')}
              >
                <Close width={13} height={13} />
              </button>
            </div>
          </header>

          <div className="bot-status">
            <span className={`bot-status-dot ${busy ? 'bot-status-busy' : ''}`} />
            {busy ? t('bot.status.thinking') : t('bot.status.ready')}
          </div>

          <div ref={scrollRef} className="bot-messages">
            {messages.length === 0 ? (
              <>
                <div className="bot-bubble bot-bubble-assistant">
                  {greeting}
                </div>
                <div className="bot-suggestions">
                  {buildSuggestions().map((s) => (
                    <button
                      key={s.label}
                      type="button"
                      className="bot-suggestion"
                      onClick={() => {
                        if (s.kind === 'action' && s.action) triggerAction(s.action);
                        else sendMessage(s.prompt || s.label);
                      }}
                      disabled={busy}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`bot-bubble ${
                    m.role === 'user' ? 'bot-bubble-user' : 'bot-bubble-assistant'
                  } ${m.error ? 'bot-bubble-error' : ''}`}
                >
                  {renderInlineMarkdown(m.text)}
                </div>
              ))
            )}
            {busy && (
              <div className="bot-typing">
                <span /><span /><span />
              </div>
            )}
          </div>

          <form
            className="bot-input"
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
          >
            <input
              type="text"
              placeholder={t('bot.placeholder')}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button
              type="submit"
              className="bot-send"
              disabled={busy || !input.trim()}
              aria-label={t('bot.send')}
            >
              <Send width={14} height={14} />
            </button>
          </form>

          <div className="bot-footer">
            <div className="bot-footer-text">{t('bot.footer')}</div>
            <div className="bot-footer-brand">
              <span className="bot-footer-powered">{t('bot.poweredBy')}</span>
              <img
                src="/brand/skoda_Auto4.png"
                alt=""
                className="bot-footer-logo"
                draggable={false}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );

/**
 * Renders just enough markdown for chat: **bold** and *italic*.
 * Everything else is treated as plain text.
 */
function renderInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith('**')) {
      parts.push(<strong key={key++}>{token.slice(2, -2)}</strong>);
    } else {
      parts.push(<em key={key++}>{token.slice(1, -1)}</em>);
    }
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length ? parts : text;
}
}