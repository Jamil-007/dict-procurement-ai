import { cn } from "@/lib/utils";
import type { ProcurementStatus, ReviewStatus, Severity } from "@/types/records";

const STATUS: Record<ProcurementStatus, string> = {
  ongoing: "bg-sky text-brand border-brand/20",
  finalized: "bg-compliant/10 text-compliant border-compliant/20",
};

export function StatusPill({ status }: { status: ProcurementStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[12px] font-medium capitalize",
        STATUS[status]
      )}
    >
      {status}
    </span>
  );
}

const REVIEW_LABEL: Record<ReviewStatus, string> = {
  none: "Not yet reviewed",
  processing: "Review in progress",
  done: "Review complete",
};

export function ReviewPill({ status }: { status: ReviewStatus }) {
  return (
    <span className="inline-flex items-center rounded-full border border-line bg-white px-2.5 py-0.5 text-[12px] text-subtle">
      {REVIEW_LABEL[status]}
    </span>
  );
}

/**
 * Severity wording is deliberately neutral: findings are points for the BAC to
 * verify, never a determination.
 */
const SEVERITY: Record<Severity, { label: string; className: string }> = {
  critical: {
    label: "Requires BAC Review",
    className: "bg-critical/10 text-critical border-critical/20",
  },
  warning: {
    label: "Potential Issue",
    className: "bg-warning/10 text-warning border-warning/20",
  },
  compliant: {
    label: "No Issue Found",
    className: "bg-compliant/10 text-compliant border-compliant/20",
  },
};

export function SeverityPill({ severity }: { severity: Severity }) {
  const { label, className } = SEVERITY[severity];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[12px] font-medium",
        className
      )}
    >
      {label}
    </span>
  );
}

export const severityLabel = (severity: Severity) => SEVERITY[severity].label;

/** Severity order and the solid fill used for bars and dots. */
export const SEVERITY_KEYS: Severity[] = ["critical", "warning", "compliant"];

export const SEVERITY_BAR: Record<Severity, string> = {
  critical: "bg-critical",
  warning: "bg-warning",
  compliant: "bg-compliant",
};
