export type SimulationState =
  | 'idle'
  | 'uploading'
  | 'thinking'
  | 'verdict'
  | 'generating'
  | 'complete';

export type ThinkingLogStatus = 'pending' | 'active' | 'complete';

export interface ThinkingLog {
  id: string;
  agent: string;
  message: string;
  timestamp: number;
  status: ThinkingLogStatus;
  delay?: number;
}

export type FindingSeverity = 'high' | 'medium' | 'low';

export interface Finding {
  category: string;
  items: string[];
  severity: FindingSeverity;
}

export type VerdictStatus = 'PASS' | 'FAIL';

export interface VerdictData {
  status: VerdictStatus;
  title: string;
  findings: Finding[];
  confidence: number;
}

export interface Message {
  id: string;
  type: 'user' | 'ai' | 'thinking' | 'verdict';
  content?: string;
  fileName?: string;
  timestamp: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface UseProcurementSimulationReturn {
  state: SimulationState;
  thinkingLogs: ThinkingLog[];
  verdictData: VerdictData | null;
  messages: Message[];
  showSplitView: boolean;
  uploadFile: (file: File, verdict?: VerdictData) => void;
  startScenario: (verdict: VerdictData, scenarioName: string) => void;
  generateReport: () => void;
  declineReport: () => void;
  closeSplitView: () => void;
  reset: () => void;
}
