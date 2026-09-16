export type Provider =
  | 'openai' | 'anthropic' | 'gemini' | 'xai' | 'groq' | 'mistral'
  | 'openrouter' | 'together' | 'deepseek' | 'ollama' | 'custom' | 'mock'
  | 'azure';

export interface AIConfig {
  provider: Provider;
  apiKey: string;
  model: string;
  baseUrl?: string;
}

export interface Issue {
  id: string;
  type: 'critical' | 'warning';
  title: string;
  desc: string;
  nodeId?: string | null;
  fixAction?: string | null;
  targetId?: string | null;
}

export interface LintBreakdownItem { score: number; max: number; }

export interface Lint {
  totalScore: number;
  band: string;
  breakdown: Record<string, LintBreakdownItem>;
  issues: Issue[];
  criticalCount: number;
  counts: { startEvents: number; endEvents: number; tasks: number; gateways: number; flows: number };
}

export interface GenerateResult {
  xml: string;
  lint: Lint;
  loops: number;
  warning?: string;
  historyId?: number;
}

export interface Explanation { headline: string; summary: string; bullets: string[]; }

export interface AutomationCandidate {
  id: string; name: string; roi: 'High' | 'Medium' | 'Low';
  tool: string; rationale: string;
}

export interface HistoryItem {
  id: number; description: string; score: number | null;
  loops: number | null; pinned: boolean; createdAt: number; similarity?: number;
}

export interface Preset { key: string; title: string; tag: string; desc: string; prompt: string; }

export type Persona = 'auditor' | 'manager' | 'engineer';

export type AgentId = 'interpreter' | 'modeler' | 'validator' | 'fixer' | 'editor' | 'explainer' | 'optimizer';

export type AgentState = 'idle' | 'active' | 'done';

export type LogLevel = 'info' | 'success' | 'warn' | 'error';
export type ReviewExportFormat = 'md' | 'docx' | 'pdf';
export interface LogLine { id: number; level: LogLevel; text: string; }

export interface StreamEvent {
  type: 'agent' | 'log' | 'result' | 'saved' | 'error' | 'end';
  agent?: AgentId;
  status?: AgentState;
  line?: string;
  level?: LogLevel;
  data?: GenerateResult;
  historyId?: number;
  error?: string;
  code?: string;
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'agent';
  text: string;
  scoreBefore?: number | null;
  scoreAfter?: number | null;
  pending?: boolean;
  failed?: boolean;
}


export interface DiffNode { id: string; type: string; name: string; }
export interface DiffFlow { id: string; source: string; target: string; name: string; }
export interface DiffRenamed { id: string; from: string; to: string; }

export interface BpmnDiff {
  added_nodes: DiffNode[];
  removed_nodes: DiffNode[];
  renamed_nodes: DiffRenamed[];
  added_flows: DiffFlow[];
  removed_flows: DiffFlow[];
  summary: string;
  counts: Record<string, number>;
}

export interface OptimizeRationale {
  headline: string;
  changes: string[];
  impact: string;
}

export interface OptimizeResult {
  xml: string | null;
  lint: Lint | null;
  beforeLint?: Lint | null;
  diff?: BpmnDiff | null;
  rationale?: OptimizeRationale | null;
  loops: number;
  warning?: string;
}

export interface OptimizeStreamEvent {
  type: 'agent' | 'log' | 'result' | 'error' | 'end';
  agent?: AgentId;
  status?: AgentState;
  line?: string;
  level?: LogLevel;
  data?: OptimizeResult;
  error?: string;
  code?: string;
}

export interface ReviewReport {
  summary: string;
  bottlenecks: string[];
  risks: string[];
  missingSteps: string[];
  recommendations: string[];
  automationOpportunities: string[];
  healthScore: number;
  band: string;
}
