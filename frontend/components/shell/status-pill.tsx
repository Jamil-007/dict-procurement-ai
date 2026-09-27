import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  CircleCheck,
  Info,
  type LucideIcon,
} from "lucide-react";

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
 * The severity scale, mirroring review/schema.py. `meaning` is the tooltip and
 * matches SEVERITY_MEANING on the backend, so the legend and the prompt
 * describe a level the same way.
 *
 * A finding is a point for the BAC to verify, never a determination — the
 * level says how much attention it wants, not that anything is unlawful.
 */
const SEVERITY: Record<
  Severity,
  {
    label: string;
    meaning: string;
    chip: string;
    bar: string;
    text: string;
    icon: LucideIcon;
  }
> = {
  critical: {
    label: "Critical",
    meaning: "Potentially material issue requiring prompt BAC attention",
    chip: "bg-sev-critical/10 text-sev-critical border-sev-critical/25",
    bar: "bg-sev-critical",
    text: "text-sev-critical",
    icon: AlertOctagon,
  },
  medium: {
    label: "Medium",
    meaning:
      "Meaningful issue but generally does not by itself prevent continuation",
    chip: "bg-sev-medium/10 text-sev-medium border-sev-medium/25",
    bar: "bg-sev-medium",
    text: "text-sev-medium",
    icon: AlertTriangle,
  },
  low: {
    label: "Low",
    meaning: "Minor quality or completeness issue",
    chip: "bg-sev-low/10 text-sev-low border-sev-low/25",
    bar: "bg-sev-low",
    text: "text-sev-low",
    icon: AlertCircle,
  },
  info: {
    label: "Informational",
    meaning: "Observation rather than an identified deficiency",
    chip: "bg-sev-info/10 text-sev-info border-sev-info/25",
    bar: "bg-sev-info",
    text: "text-sev-info",
    icon: Info,
  },
  compliant: {
    label: "Compliant",
    meaning: "Checked and no issue found",
    chip: "bg-sev-compliant/10 text-sev-compliant border-sev-compliant/25",
    bar: "bg-sev-compliant",
    text: "text-sev-compliant",
    icon: CircleCheck,
  },
};

export function SeverityPill({ severity }: { severity: Severity }) {
  const { label, meaning, chip, icon: Icon } = SEVERITY[severity];
  return (
    <span
      title={meaning}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10.5px] font-bold tracking-wide",
        chip
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {label.toUpperCase()}
    </span>
  );
}

export const severityLabel = (severity: Severity) => SEVERITY[severity].label;
export const severityMeaning = (severity: Severity) => SEVERITY[severity].meaning;

/** Most concern first. Drives sort order, the legend and the count summary. */
export const SEVERITY_KEYS: Severity[] = [
  "critical",
  "medium",
  "low",
  "info",
  "compliant",
];

/** Solid fill, for the card's left bar and the legend dot. */
export const SEVERITY_BAR: Record<Severity, string> = Object.fromEntries(
  SEVERITY_KEYS.map((key) => [key, SEVERITY[key].bar])
) as Record<Severity, string>;

/**
 * Total across every level. Use this rather than adding named levels together,
 * so adding a level to the scale does not silently undercount everywhere.
 */
export const totalFindings = (counts: Partial<Record<Severity, number>>) =>
  SEVERITY_KEYS.reduce((sum, key) => sum + (counts[key] ?? 0), 0);

/** Text colour, for the delta line that restates a finding's discrepancy. */
export const SEVERITY_TEXT: Record<Severity, string> = Object.fromEntries(
  SEVERITY_KEYS.map((key) => [key, SEVERITY[key].text])
) as Record<Severity, string>;
