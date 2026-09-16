import type { AgentId, AgentState } from '../lib/types';
import { useI18n } from '../lib/LanguageContext';
import { Interpreter, Modeler, Validator, Fixer, Editor, Optimizer, Explainer, ChevronRight } from './icons';

const STEP_ORDER: { id: AgentId; num: number; Icon: typeof Interpreter }[] = [
  { id: 'interpreter', num: 1, Icon: Interpreter },
  { id: 'modeler', num: 2, Icon: Modeler },
  { id: 'validator', num: 3, Icon: Validator },
  { id: 'fixer', num: 4, Icon: Fixer },
  { id: 'editor', num: 5, Icon: Editor },
  { id: 'optimizer', num: 6, Icon: Optimizer },
  { id: 'explainer', num: 7, Icon: Explainer },
];

export function AgentPipeline({ states }: { states: Record<AgentId, AgentState> }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-1.5 overflow-x-auto py-1" aria-label="Agent pipeline status">
      {STEP_ORDER.map((step, i) => {
        const state = states[step.id];
        const label = `${step.num}. ${t(`agent.${step.id}`)}`;
        return (
          <div key={step.id} className="flex items-center gap-1.5">
            <div className="pipe-step" data-state={state}>
              <step.Icon width={14} height={14} className={state === 'active' ? 'animate-pulse-ring' : ''} />
              <span className="whitespace-nowrap">{label}</span>
              {state === 'active' && <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse-ring" />}
              {state === 'done' && <span className="h-1.5 w-1.5 rounded-full bg-good" />}
            </div>
            {i < STEP_ORDER.length - 1 && <ChevronRight width={14} height={14} className="shrink-0 text-muted" />}
          </div>
        );
      })}
    </div>
  );
}
