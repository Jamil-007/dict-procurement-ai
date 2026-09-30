/**
 * Mirrors backend/domain.py and backend/review/schema.py.
 *
 * ReviewFinding is the contract every AI Review dimension returns. The UI
 * renders whatever fits this shape, so a dimension owner never writes UI.
 */

export type ProcurementStatus = "ongoing" | "finalized";
export type ReviewStatus = "none" | "processing" | "done";

export interface ProcurementDocument {
  id: string;
  name: string;
  doc_type: string;
  pages: number;
  uploaded: string;
  gcs_path: string;
  status: string;
}

export interface Procurement {
  ref: string;
  title: string;
  abc: number;
  mode: string;
  fund: string;
  category: string;
  end_user: string;
  status: ProcurementStatus;
  created: string;
  updated: string;
  documents: ProcurementDocument[];
  review_status: ReviewStatus;
  /**
   * The Compliance Checks tab runs independently of the AI Review, so it
   * tracks its own progress rather than sharing review_status.
   */
  check_status: ReviewStatus;
  report_notes: string;
  finalized_at: string | null;
  finalized_by: string | null;
  /**
   * Derived server-side on every read — the list page shows it per record.
   * Counted per engine, because each tab badges its own total and a combined
   * number would be wrong on both.
   */
  finding_counts: Record<Severity, number>;
  check_counts: Record<Severity, number>;
  /** Findings the BAC has recorded an action against. Also derived server-side. */
  decided_count: number;
}

export interface ProcurementCreate {
  title: string;
  abc?: number;
  mode?: string;
  fund?: string;
  category?: string;
  end_user?: string;
}

export type Severity = "critical" | "medium" | "low" | "info" | "compliant";
/**
 * The BAC accepts or rejects. "modified" and "further" are no longer offered
 * but stay in the union so a finding decided before they were dropped still
 * loads. Mirrors Decision in review/schema.py.
 */
export type Decision = "accepted" | "modified" | "further" | "rejected";

/** Mirrors RejectionReason in review/schema.py. */
export type RejectionReason =
  | "not_applicable"
  | "insufficient_evidence"
  | "misinterpreted"
  | "duplicate"
  | "acceptable"
  | "other";

export type FindingFeedback = "correct" | "incorrect" | "irrelevant" | "incomplete";

export interface Source {
  doc: string;
  page?: number | null;
  section: string;
}

export interface ComparedText {
  doc: string;
  page?: number | null;
  label: string;
  quote: string;
}

export type Confidence = "high" | "medium" | "low";

/**
 * A web page a dimension consulted, as opposed to an uploaded document. `tier`
 * ranks how authoritative it is: 1 Philippine government, 2 manufacturer or
 * official distributor, 3 Philippine supplier, 4 marketplace listing,
 * 5 informational. Mirrors SOURCE_TIER_MEANING in review/schema.py.
 */
export interface ExternalSource {
  url: string;
  title: string;
  publisher: string;
  tier: number;
  retrieved_at: string;
}

export interface PolicyCitation {
  title: string;
  section: string;
  page: number;
  quote: string;
}

export interface Comment {
  text: string;
  author: string;
  at: string;
}

export interface Finding {
  id: string;
  dimension: string;
  severity: Severity;
  title: string;
  analysis: string;
  recommendation: string;
  source: Source;
  policy_basis: string;
  quote: string;
  comparison: ComparedText[];
  delta: string | null;
  /** Absent when the finding rests wholly on figures stated in the documents. */
  confidence: Confidence | null;
  external_sources: ExternalSource[];
  policy_sources: PolicyCitation[];
  procurement_ref: string;
  decision: Decision | null;
  decided_by: string | null;
  decided_at: string | null;
  /** Set only when decision is "rejected". */
  rejection_reason: RejectionReason | null;
  rejection_note: string;
  edited: boolean;
  ai_analysis: string;
  ai_recommendation: string;
  comments: Comment[];
  feedback: FindingFeedback | null;
}

/** Served by GET /review/dimensions — never hardcode the list. */
export interface Dimension {
  key: string;
  label: string;
  blurb: string;
  owner: string;
}

/**
 * What a dimension says about its own run, as distinct from its findings.
 *
 * A count of zero findings is ambiguous on its own — it reads the same whether
 * the dimension checked and found nothing or had nothing to check. The
 * assessment is where it says which ground it actually walked.
 */
export interface DimensionSummary {
  assessment: string;
  documents_reviewed: string[];
  confidence: Confidence | null;
}

export interface DimensionOutcome {
  key: string;
  label: string;
  status: "ok" | "failed" | "timeout";
  findings: number;
  summary: DimensionSummary | null;
  /** What the dimension could not resolve, and why. */
  research_gaps: string[];
  error: string | null;
  duration_ms: number;
}

export interface RunReviewResponse {
  ref: string;
  dimensions: DimensionOutcome[];
  findings: Finding[];
  counts: Record<Severity, number>;
}

// --- compliance checks ---
//
// The six assigned checkers (T1–T6). They produce the same Finding shape the
// AI Review does — deliberately, so the BAC accepts, rejects and comments on
// both with the same card — but they are deterministic rule and consistency
// engines rather than LLM dimensions, and they are stored and listed apart.

/** Served by GET /checks/checkers — read from the YAML, never hardcoded. */
export interface CheckerInfo {
  key: string;
  /** "T1".."T6", the label the assignment sheet uses. */
  task: string;
  label: string;
  blurb: string;
  owner: string;
  engine: "rule" | "consistency";
  /** What this checker needs uploaded before it has anything to look at. */
  doc_types: string[];
}

/**
 * What one checker did on a run.
 *
 * `status` is the load-bearing field. A checker reporting zero findings is
 * ambiguous — it reads the same whether it checked and found nothing wrong or
 * never ran at all — so "skipped" carries a `reason` saying which.
 */
export interface CheckerOutcome {
  key: string;
  task: string;
  label: string;
  owner: string;
  engine: "rule" | "consistency";
  status: "ran" | "skipped";
  findings: number;
  failed: number;
  passed: number;
  not_verified: number;
  reason: string;
}

export interface RunChecksResponse {
  ref: string;
  checkers: CheckerOutcome[];
  findings: Finding[];
  counts: Record<Severity, number>;
  detected_types: string[];
  log: Record<string, unknown>[];
}

export interface KnowledgeEntry {
  id: string;
  title: string;
  subtitle: string;
  category: string;
  doc_type: string;
  date: string;
  pages: number;
  excerpt: string;
  gcs_path: string;
}

export interface KnowledgeResponse {
  categories: string[];
  total: number;
  entries: KnowledgeEntry[];
}

/** Must stay in step with backend/domain.py DOC_TYPES. */
export const DOC_TYPES = [
  // Planning
  "Annual Procurement Plan (APP)",
  "Project Procurement Management Plan (PPMP)",
  "Market Study",
  "Market Scoping Checklist",
  // Price canvassing evidence gathered for the market study and the ABC, so
  // this is a planning input, not a bid received after posting.
  "Supplier Quotation",
  "Purchase Request",
  "Certificate of Availability of Funds",
  // Requirements
  "Terms of Reference (TOR)",
  "Technical Specifications",
  "Detailed Cost Breakdown",
  // Bidding
  "Bidding Documents",
  "Invitation to Bid",
  "Abstract of Bids",
  // BAC action
  "BAC Resolution",
  "Minutes of BAC Meeting",
  "Post-Qualification Report",
  // Award. The tool reviews before posting, so these arrive only when a
  // procurement is uploaded after the fact — but the dimensions cite them
  // when they are there, so they need to be nameable.
  "Notice of Award",
  "Notice to Proceed",
  "Contract",
  "Purchase Order",
  // Delivery and acceptance — what T5 cross-checks against the contract.
  "Delivery Receipt",
  "Sales Invoice",
  "Inspection and Acceptance Report",
  "Property Acknowledgement Receipt",
  "Inventory Custodian Slip",
  "Warranty Certificate",
  // Payment — what T1 checks and T4 compares back to the contract.
  "Obligation Request and Status",
  "Disbursement Voucher",
  "Official Receipt",
  "Certificate of Tax Withheld",
  "Other",
] as const;

export const PROCUREMENT_MODES = [
  "Competitive Bidding",
  "Limited Source Bidding",
  "Competitive Dialogue",
  "Unsolicited Offer with Bid Matching",
  "Direct Contracting",
  "Direct Acquisition",
  "Repeat Order",
  "Small Value Procurement",
  "Negotiated Procurement",
  "Direct Sales",
  "Direct Procurement for Science, Technology and Innovation",
] as const;

export const PROCUREMENT_TYPES = [
  "Goods",
  "Infrastructure",
  "Consulting Services",
] as const;
