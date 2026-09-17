import { useEffect, useRef, useState } from 'react';
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
  const prevStatesRef = useRef(states);
  const [justCompleted, setJustCompleted] = useState<Set<AgentId>>(new Set());

  // Detect active → done transitions and trigger a one-shot sweep on those steps.
  useEffect(() => {
    const prev = prevStatesRef.current;
    const completed: AgentId[] = [];
    for (const step of STEP_ORDER) {
      if (prev[step.id] === 'active' && states[step.id] === 'done') {
        completed.push(step.id);
      }
    }
    prevStatesRef.current = states;

    if (completed.length) {
      setJustCompleted(new Set(completed));
      const id = setTimeout(() => setJustCompleted(new Set()), 900);
      return () => clearTimeout(id);
    }
  }, [states]);

  return (
    <div
      className="flex items-center gap-1.5 overflow-x-auto py-1"
      aria-label="Agent pipeline status"
    >
      {STEP_ORDER.map((step, i) => {
        const state = states[step.id];
        const label = `${step.num}. ${t(`agent.${step.id}`)}`;
        const sweep = justCompleted.has(step.id);
        return (
          <div key={step.id} className="flex items-center gap-1.5">
            <div
              className="pipe-step"
              data-state={state}
              data-sweep={sweep || undefined}
            >
              <span className="pipe-step-sweep" aria-hidden="true" />
              <step.Icon
                width={14}
                height={14}
                className={state === 'active' ? 'pipe-icon-active' : ''}
              />
              <span className="whitespace-nowrap">{label}</span>
              {state === 'active' && <span className="pipe-dot pipe-dot-active" />}
              {state === 'done' && <span className="pipe-dot pipe-dot-done" />}
            </div>
            {i < STEP_ORDER.length - 1 && (
              <ChevronRight
                width={14}
                height={14}
                className={`shrink-0 transition-colors duration-300 ${
                  state === 'done' ? 'text-good/70' : 'text-muted'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}