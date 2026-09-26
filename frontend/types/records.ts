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
  report_notes: string;
  finalized_at: string | null;
  finalized_by: string | null;
  /** Derived server-side on every read — the list page shows it per record. */
  finding_counts: Record<Severity, number>;
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
export type Decision = "accepted" | "modified" | "further" | "rejected";
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

export interface DimensionOutcome {
  key: string;
  label: string;
  status: "ok" | "failed" | "timeout";
  findings: number;
  error: string | null;
  duration_ms: number;
}

export interface RunReviewResponse {
  ref: string;
  dimensions: DimensionOutcome[];
  findings: Finding[];
  counts: Record<Severity, number>;
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
