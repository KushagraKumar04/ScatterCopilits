import { useEffect, useMemo, useState, type ReactNode } from 'react';
import type { AIConfig, HistoryItem, LogLine, Preset } from '../lib/types';
import { api, ApiError } from '../lib/api';
import { useDebounce } from '../hooks/useLocalState';
import { useI18n } from '../lib/LanguageContext';
import { ThoughtStreamLog } from './ThoughtStreamLog';
import { Grid, History as HistoryIcon, Sparkles, Wand, Search, Pin, Trash, Bulb, Check, Close } from './icons';

type Tab = 'compose' | 'history' | 'examples';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onGenerate: () => void;
  loading: boolean;
  presets: Preset[];
  history: HistoryItem[];
  onReloadHistory: () => void;
  logLines: LogLine[];
  streaming: boolean;
  cfg: AIConfig;
}

export function InputPanel(props: Props) {
  const { value, onChange, onGenerate, loading, presets, history, onReloadHistory, logLines, streaming, cfg } = props;
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>('compose');
  const [suggestions, setSuggestions] = useState<HistoryItem[]>([]);
  const [dismissedFor, setDismissedFor] = useState('');
  const debounced = useDebounce(value, 450);

  const [enhancing, setEnhancing] = useState(false);
  const [enhanced, setEnhanced] = useState<string | null>(null);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const q = debounced.trim();
    if (q.length < 8) { setSuggestions([]); return; }
    api.suggest(q).then((s) => { if (alive) setSuggestions(s); }).catch(() => undefined);
    return () => { alive = false; };
  }, [debounced]);

  const showSuggestions = tab === 'compose' && suggestions.length > 0 && dismissedFor !== debounced.trim();

  const runEnhance = async () => {
    if (value.trim().length < 3 || enhancing) return;
    setEnhancing(true);
    setEnhanceError(null);
    setEnhanced(null);
    try {
      const result = await api.enhance(value, cfg);
      setEnhanced(result);
    } catch (e) {
      const msg = e instanceof ApiError
        ? (e.code === 'NO_API_KEY' ? t('toast.addApiKey') : e.message)
        : 'Could not enhance the description.';
      setEnhanceError(msg);
    } finally {
      setEnhancing(false);
    }
  };

  const acceptEnhanced = () => {
    if (enhanced) onChange(enhanced);
    setEnhanced(null);
    setEnhanceError(null);
  };
  const discardEnhanced = () => {
    setEnhanced(null);
    setEnhanceError(null);
  };

  return (
    <section className="card flex h-full flex-col overflow-hidden">
      <div role="tablist" aria-label="Input source" className="flex items-center gap-1 border-b border-border px-3">
        <TabBtn active={tab === 'compose'} onClick={() => setTab('compose')} icon={<Wand width={16} height={16} />} label={t('tabs.compose')} />
        <TabBtn active={tab === 'history'} onClick={() => setTab('history')} icon={<HistoryIcon width={16} height={16} />} label={t('tabs.history')} badge={history.length || undefined} />
        <TabBtn active={tab === 'examples'} onClick={() => setTab('examples')} icon={<Grid width={16} height={16} />} label={t('tabs.examples')} />
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        {tab === 'compose' && (
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
            <label className="label" htmlFor="desc">{t('compose.label')}</label>
            <textarea id="desc" className="field min-h-[90px] flex-1 resize-none leading-relaxed"
              placeholder={t('compose.placeholder')}
              value={value} onChange={(e) => onChange(e.target.value)} />
            <p className="hint">{t('compose.hint')}</p>

            {enhanceError && (
              <div className="mt-3 animate-fade-up rounded-xl border border-bad/30 bg-bad/10 p-3 text-sm text-bad">
                {enhanceError}
              </div>
            )}

            {enhanced && (
              <div className="mt-3 animate-fade-up rounded-xl border border-brand/30 bg-brand/[0.06] p-3">
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-brand">
                  <Sparkles width={14} height={14} /> {t('enhance.title')}
                </div>
                <p className="max-h-40 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink">
                  {enhanced}
                </p>
                <div className="mt-2.5 flex items-center gap-2">
                  <button className="btn-primary !min-h-[38px] flex-1" onClick={acceptEnhanced}>
                    <Check width={16} height={16} /> {t('button.useThis')}
                  </button>
                  <button className="btn-subtle !min-h-[38px]" onClick={discardEnhanced}>
                    <Close width={16} height={16} /> {t('button.keepOriginal')}
                  </button>
                </div>
              </div>
            )}

            {showSuggestions && (
              <div className="mt-3 animate-fade-up rounded-xl border border-brand/30 bg-brand/[0.06] p-3">
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-brand">
                  <Bulb width={14} height={14} /> {t('compose.suggestionsTitle')}
                </div>
                <ul className="space-y-1">
                  {suggestions.slice(0, 3).map((s) => (
                    <li key={s.id}>
                      <button className="w-full rounded-lg px-2 py-1.5 text-left text-sm text-ink hover:bg-brand/10"
                        onClick={() => { onChange(s.description); setDismissedFor(''); }}>
                        <span className="line-clamp-2">{s.description}</span>
                        <span className="mt-0.5 block text-xs text-muted">
                          {Math.round((s.similarity ?? 0) * 100)}{t('compose.matchScore')}{s.score != null ? ` · ${t('compose.scored')} ${s.score}` : ''} - {t('compose.reuse')}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                <button className="mt-1 text-xs font-medium text-muted hover:text-ink"
                  onClick={() => setDismissedFor(debounced.trim())}>{t('compose.dismiss')}</button>
              </div>
            )}

            <div className="mt-3 flex shrink-0 items-center gap-2">
              <button className="btn-subtle" onClick={runEnhance}
                disabled={enhancing || loading || value.trim().length < 3}
                title="Rewrite rough notes into a clear, structured description">
                {enhancing ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-brand" /> {t('button.enhancing')}</>
                           : <><Wand width={16} height={16} /> {t('button.enhance')}</>}
              </button>
              <button className="btn-primary flex-1" onClick={onGenerate} disabled={loading || value.trim().length < 3}>
                {loading ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-fg/40 border-t-brand-fg" /> {t('button.generating')}</>
                         : <><Sparkles width={16} height={16} /> {t('button.generate')}</>}
              </button>
            </div>
          </div>
        )}

        {tab === 'history' && (
          <HistoryTab items={history} onPick={(d) => { onChange(d); setTab('compose'); }} onReload={onReloadHistory} />
        )}
        {tab === 'examples' && (
          <ExamplesTab presets={presets} onPick={(p) => { onChange(p); setTab('compose'); }} />
        )}
      </div>

      <div className="shrink-0 border-t border-border p-4">
        <ThoughtStreamLog lines={logLines} streaming={streaming} />
      </div>
    </section>
  );
}

function TabBtn({ active, onClick, icon, label, badge }: {
  active: boolean; onClick: () => void; icon: ReactNode; label: string; badge?: number;
}) {
  return (
    <button role="tab" aria-selected={active} data-active={active} className="tab" onClick={onClick}>
      {icon}{label}
      {badge != null && <span className="ml-0.5 rounded-full bg-brand/15 px-1.5 text-[11px] font-bold text-brand">{badge}</span>}
    </button>
  );
}

function HistoryTab({ items, onPick, onReload }: {
  items: HistoryItem[]; onPick: (d: string) => void; onReload: () => void;
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? items.filter((i) => i.description.toLowerCase().includes(q)) : items;
  }, [items, query]);

  const remove = async (id: number) => { await api.deleteHistory(id); onReload(); };
  const pin = async (id: number) => { await api.pinHistory(id); onReload(); };
  const clearAll = async () => { await api.clearHistory(); onReload(); };

  return (
    <div className="flex min-h-0 flex-1 flex-col p-4">
      <div className="mb-3 flex items-center gap-2">
        <div className="relative flex-1">
          <Search width={16} height={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input className="field pl-9" placeholder={t('history.searchPlaceholder')} value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Search history" />
        </div>
        {items.length > 0 && (
          <button className="btn-subtle" onClick={clearAll} title={t('history.clear')}>
            <Trash width={16} height={16} /> {t('history.clear')}
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={<HistoryIcon />}
          title={items.length === 0 ? t('history.empty.title') : t('history.noMatches.title')}
          body={items.length === 0 ? t('history.empty.body') : t('history.noMatches.body')} />
      ) : (
        <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          {filtered.map((it) => (
            <li key={it.id} className="group rounded-xl border border-border bg-elevated/50 p-3 transition-colors hover:border-brand/40">
              <button className="block w-full text-left" onClick={() => onPick(it.description)}>
                <p className="line-clamp-2 text-sm font-medium text-ink">{it.description}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {it.score != null && <ScoreChip score={it.score} />}
                  {it.loops != null && <span className="chip">{it.loops} {it.loops === 1 ? t('history.loops') : t('history.loopsPlural')}</span>}
                  <span className="chip">{timeAgo(it.createdAt, t)}</span>
                  {it.pinned && <span className="chip text-brand"><Pin width={12} height={12} /> {t('history.pinned')}</span>}
                </div>
              </button>
              <div className="mt-2 flex justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button className="icon-btn" title={it.pinned ? t('history.unpin') : t('history.pin')} onClick={() => pin(it.id)}>
                  <Pin width={16} height={16} className={it.pinned ? 'text-brand' : ''} />
                </button>
                <button className="icon-btn" title={t('history.delete')} onClick={() => remove(it.id)}>
                  <Trash width={16} height={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ExamplesTab({ presets, onPick }: { presets: Preset[]; onPick: (prompt: string) => void }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4">
      <ul className="space-y-2.5">
        {presets.map((p) => (
          <li key={p.key}>
            <button className="w-full rounded-xl border border-border bg-elevated/50 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-brand/50 hover:shadow-card"
              onClick={() => onPick(p.prompt)}>
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-bold text-ink">{p.title}</h4>
                <span className="chip">{p.tag}</span>
              </div>
              <p className="mt-1 text-xs text-muted">{p.desc}</p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EmptyState({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="grid flex-1 place-items-center px-6 text-center">
      <div className="animate-fade-up">
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-brand/10 text-brand">{icon}</div>
        <h3 className="font-bold text-ink">{title}</h3>
        <p className="mt-1 text-sm text-muted">{body}</p>
      </div>
    </div>
  );
}

function ScoreChip({ score }: { score: number }) {
  const tone = score >= 90 ? 'text-good' : score >= 70 ? 'text-warn' : 'text-bad';
  return <span className={`chip font-bold ${tone}`}>{score}/100</span>;
}

function timeAgo(ts: number, t: (k: string) => string): string {
  const s = Math.floor(Date.now() / 1000 - ts);
  if (s < 60) return t('history.justNow');
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
