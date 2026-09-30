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

export type FindingSeverity = 'high' | 'medium' | 'low' | 'info';

/** Where a finding was observed, so a reviewer can go and look at it. */
export interface Evidence {
  document: string;
  doc_type?: string;
  page?: number | null;
  field?: string | null;
  value?: string | null;
}

/**
 * The legal provision a finding rests on. Retrieved from the indexed corpus,
 * never composed by the model -- `unverified` means the named provision was
 * not found in the index, and the UI must say so rather than imply the
 * citation was checked.
 */
export interface Authority {
  doc: string;
  section?: string;
  heading?: string;
  page?: number | null;
  citation: string;
  quoted_text?: string;
  unverified?: boolean;
}

/** One side of a cross-document comparison. */
export interface ComparisonRow {
  document: string;
  doc_type?: string;
  value?: string;
  detail?: string;
  page?: number | null;
  item?: string;
  /**
   * What the reference document said for this same line. Line-item rows
   * carry it per row, because the reference value differs per item.
   */
  reference_value?: string;
}

export interface Comparison {
  kind: 'scalar' | 'directional' | 'line_items' | 'coverage';
  reference?: ComparisonRow;
  rows: ComparisonRow[];
}

/** One check result, with everything needed to act on it. */
export interface FindingDetail {
  rule_id: string;
  task: string;
  title: string;
  detail: string;
  severity: FindingSeverity;
  field?: string | null;
  /** e.g. "amendment_to_order" vs "variation_order". */
  action_hint?: string | null;
  evidence: Evidence[];
  authority?: Authority | null;
  comparison?: Comparison | null;
}

export interface Finding {
  category: string;
  items: string[];
  severity: FindingSeverity;
  /** Empty for advisory groups, which carry no structured evidence. */
  details?: FindingDetail[];
}

export type VerdictStatus = 'PASS' | 'FAIL';

export interface VerdictSummary {
  total: number;
  failed: number;
  passed: number;
  skipped: number;
  high: number;
  medium: number;
  low: number;
}

/** Per-requirement (T1..T6) check counts, computed by the report compiler. */
export interface TaskStats {
  total: number;
  failed: number;
  passed: number;
  skipped: number;
  high: number;
}

/** What the router detected about one uploaded file. */
export interface ReviewedDocument {
  file: string;
  doc_type: string;
  label: string;
  confidence: number;
  pages_read?: number;
  total_pages?: number;
  skipped_pages?: number[];
  ingest_source?: string;
  error?: string | null;
}

export interface VerdictData {
  status: VerdictStatus;
  title: string;
  findings: Finding[];
  confidence: number;
  summary?: VerdictSummary;
  documents?: ReviewedDocument[];
  checkers_run?: string[];
  /** Keyed by task id ("T1".."T6"). */
  tasks?: Record<string, TaskStats>;
}

export interface SessionSummary {
  thread_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  status: string;
  confidence: number;
  file_count: number;
  finding_count: number;
  high_count: number;
  checkers: string[];
}

export interface ArchivedSession extends SessionSummary {
  report: VerdictData | null;
  documents: Array<{
    filename: string;
    doc_type: string;
    confidence: number;
    pages_read: number;
    total_pages: number;
    ingest_source: string;
  }>;
  findings: FindingDetail[];
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
  uploadFiles: (files: File[], verdict?: VerdictData) => void;
  startScenario: (verdict: VerdictData, scenarioName: string) => void;
  generateReport: () => void;
  declineReport: () => void;
  closeSplitView: () => void;
  reset: () => void;
}
