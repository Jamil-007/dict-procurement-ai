"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  CheckCircle2,
  Download,
  Hash,
  Pencil,
  Printer,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { Modal, ModalFooter, inputCls } from "@/components/shell/modal";
import { btnPrimary } from "@/components/shell/page-header";
import {
  SEVERITY_KEYS,
  SeverityPill,
  severityLabel,
} from "@/components/shell/status-pill";
import {
  finalizeProcurement,
  listFindings,
  patchProcurement,
  runReview,
} from "@/lib/records-client";
import { formatDate, formatPeso } from "@/lib/format";
import type { Finding, Procurement, Severity } from "@/types/records";

/** The report toolbar's secondary actions — one row, same weight as each other. */
const toolBtn =
  "inline-flex items-center gap-2 rounded-lg border border-line bg-white px-4 py-2.5 text-[13px] font-semibold text-navy transition-colors hover:bg-sky disabled:opacity-60";

const DECISION_PAST: Record<string, string> = {
  accepted: "Accepted",
  modified: "Modified",
  further: "Further review requested",
  rejected: "Rejected",
};

/** Severity fills for the donut, matching the `sev` scale in tailwind.config. */
const SEV_HEX: Record<Severity, string> = {
  critical: "#B42318",
  medium: "#A16207",
  low: "#1E5AA8",
  info: "#64748B",
  compliant: "#067647",
};

const WORDS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
  "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
  "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
];

/** "five (5)" — the register the BAC uses in its own resolutions. */
const spelled = (n: number) => (WORDS[n] ? `${WORDS[n]} (${n})` : `${n}`);

/** PR-2026-001 → DICT-BAC-2026-RR-001. Falls back to the record's own ref. */
function reportRef(ref: string) {
  const match = ref.match(/(\d{4})\D+(\d+)/);
  return match ? `DICT-BAC-${match[1]}-RR-${match[2]}` : `DICT-BAC-${ref}`;
}

export function FinalReportTab({
  procurement,
  onChange,
  onGoToDocuments,
  onGoToReview,
}: {
  procurement: Procurement;
  onChange: (updated: Procurement) => void;
  onGoToDocuments: () => void;
  onGoToReview: () => void;
}) {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [notes, setNotes] = useState(procurement.report_notes);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState<"finalize" | "regenerate" | null>(
    null
  );
  const [busy, setBusy] = useState(false);

  // Rejected findings never reach the report. The committee ruled them out in
  // the review, so they are dropped on the way in rather than filtered at each
  // place the report counts or lists findings.
  useEffect(() => {
    listFindings(procurement.ref)
      .then((all) => setFindings(all.filter((f) => f.decision !== "rejected")))
      .catch(() => setFindings([]));
  }, [procurement.ref]);

  const finalized = procurement.status === "finalized";

  // The draft shows every finding still in play (rejected are already dropped
  // above). The finalized report is the official record: it lists only the
  // findings the committee confirmed — accepted, or accepted with edits
  // (modified). Pending and further-review findings are left out; the pending
  // count is noted separately so the exclusion is on the record.
  const reportFindings = useMemo(
    () =>
      finalized
        ? findings.filter(
            (f) => f.decision === "accepted" || f.decision === "modified"
          )
        : findings,
    [finalized, findings]
  );

  const counts = useMemo(() => {
    const out = Object.fromEntries(
      SEVERITY_KEYS.map((key) => [key, 0])
    ) as Record<Severity, number>;
    reportFindings.forEach((f) => (out[f.severity] += 1));
    return out;
  }, [reportFindings]);

  /** The document types the engine actually read, in the order they appear. */
  const docTypes = useMemo(() => {
    const seen: string[] = [];
    procurement.documents.forEach((doc) => {
      if (doc.doc_type && !seen.includes(doc.doc_type)) seen.push(doc.doc_type);
    });
    return seen;
  }, [procurement.documents]);

  const dimensionCount = useMemo(
    () => new Set(reportFindings.map((f) => f.dimension)).size,
    [reportFindings]
  );

  const undecided = findings.filter((f) => !f.decision).length;

  async function saveNotes() {
    setBusy(true);
    try {
      onChange(await patchProcurement(procurement.ref, { report_notes: notes }));
      setEditing(false);
      toast.success("Notes saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save notes");
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalize() {
    setBusy(true);
    try {
      const result = await finalizeProcurement(procurement.ref);
      onChange({
        ...procurement,
        status: "finalized",
        finalized_at: result.finalized_at,
        finalized_by: result.finalized_by,
        report_notes: notes,
      });
      setConfirming(null);
      setEditing(false);
      toast.success("Review finalized");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not finalize");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate() {
    setBusy(true);
    try {
      const result = await runReview(procurement.ref);
      setFindings(result.findings.filter((f) => f.decision !== "rejected"));
      setConfirming(null);
      toast.success("Report regenerated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not regenerate");
    } finally {
      setBusy(false);
    }
  }

  function printReport(asPdf = false) {
    if (asPdf) toast.info("Choose “Save as PDF” as the destination.");
    window.print();
  }

  if (procurement.review_status !== "done") {
    return (
      <div className="rounded-xl border border-line bg-white px-6 py-16 text-center">
        <h2 className="text-[15px] font-semibold">
          The report becomes available after the AI review
        </h2>
        <p className="mt-1 text-[13px] text-subtle">
          Run the review to consolidate findings into a report.
        </p>
        <button onClick={onGoToDocuments} className={`${btnPrimary} mt-5`}>
          Go to Documents
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar — screen only. The sheet below is what prints. */}
      <div className="rounded-xl border border-line bg-white px-5 py-4 print:hidden">
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sky">
            <BadgeCheck className="h-[19px] w-[19px] text-brand" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-[15px] font-bold leading-tight text-navy">
                Final Procurement Compliance &amp; Review Report
              </h2>
              <span className="rounded border border-line bg-page px-1.5 py-0.5 text-[10.5px] font-semibold text-subtle">
                {finalized ? "Final 1.0" : "Draft 1.0"}
              </span>
            </div>
            <p className="mt-0.5 text-[12.5px] text-subtle">
              {findings.length - undecided} of {findings.length} findings reviewed
              {undecided ? ` · ${undecided} pending` : ""}
            </p>
          </div>
        </div>

        <div className="mt-3.5 flex flex-wrap items-center gap-2">
          {!finalized && (
            <button onClick={() => setEditing((on) => !on)} className={toolBtn}>
              <Pencil className="h-4 w-4 text-brand" />
              {editing ? "Done editing" : "Edit Content"}
            </button>
          )}
          <button onClick={() => printReport()} className={toolBtn}>
            <Printer className="h-4 w-4 text-brand" />
            Print Document
          </button>
          <button onClick={() => printReport(true)} className={toolBtn}>
            <Download className="h-4 w-4 text-brand" />
            Download PDF
          </button>
          {!finalized && (
            <button
              onClick={() => setConfirming("regenerate")}
              disabled={busy}
              className={toolBtn}
            >
              <RefreshCw
                className={`h-4 w-4 text-brand ${busy ? "animate-spin" : ""}`}
              />
              Regenerate
            </button>
          )}
          {finalized ? (
            <span className="inline-flex items-center gap-2 rounded-lg border border-compliant/20 bg-compliant/10 px-4 py-2.5 text-[13px] font-semibold text-compliant">
              <CheckCircle2 className="h-4 w-4" />
              Finalized
            </span>
          ) : (
            <button
              onClick={() => setConfirming("finalize")}
              className="inline-flex items-center gap-2 rounded-lg bg-navy px-4 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-brand"
            >
              <CheckCircle2 className="h-4 w-4" />
              Finalize Report
            </button>
          )}
        </div>
      </div>

      {!finalized && undecided > 0 && (
        <div className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-white px-5 py-4 print:hidden">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-warning/10">
            <AlertCircle className="h-4 w-4 text-warning" />
          </span>
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-navy">
              {undecided} finding{undecided === 1 ? "" : "s"} pending BAC action
            </div>
            <p className="mt-0.5 text-[12.5px] text-subtle">
              They show in the draft as pending — record an action to include them
              in the finalized report.
            </p>
          </div>
          <button
            onClick={onGoToReview}
            className="ml-auto flex items-center gap-2 rounded-md border border-brand bg-white px-4 py-2 text-[12.5px] font-semibold text-brand transition-colors hover:bg-sky"
          >
            Review pending findings
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* The document sheet. */}
      <article className="overflow-hidden rounded-xl border border-line bg-white print:overflow-visible print:rounded-none print:border-0">
        <div className="h-1.5 bg-gradient-to-r from-navy via-brand to-sky print:hidden" />

        <div className="px-6 py-8 sm:px-10 sm:py-10">
          <header className="text-center">
            <p className="text-[10px] font-semibold tracking-[0.2em] text-subtle">
              REPUBLIC OF THE PHILIPPINES
            </p>
            <h1 className="mt-1.5 text-[17px] font-bold tracking-tight text-navy sm:text-[19px]">
              DEPARTMENT OF INFORMATION AND COMMUNICATIONS TECHNOLOGY
            </h1>
            <p className="mt-1 text-[11.5px] text-sev-medium">
              DICT Central Office, C.P. Garcia Ave., Diliman, Quezon City 1101
            </p>
          </header>

          <div className="mt-6 rounded-lg bg-sky px-6 py-5 text-center">
            <h2 className="text-[16px] font-bold tracking-[0.02em] text-brand sm:text-[19px]">
              PROCUREMENT COMPLIANCE &amp; AI REVIEW REPORT
            </h2>
            <p className="mt-2 flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-[11.5px] text-brand/80">
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="h-3.5 w-3.5" />
                Report Date: {formatDate(procurement.finalized_at ?? procurement.updated)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Hash className="h-3.5 w-3.5" />
                Ref No: {reportRef(procurement.ref)}
              </span>
            </p>
          </div>

          {/* I — Particulars */}
          <SectionHead numeral="I" title="Procurement Particulars" tag="Project specification" />
          <div className="mt-3 space-y-3">
            <Field label="Project title" value={procurement.title} size="lg" />
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-3">
                <Field label="Purchase request reference" value={procurement.ref} />
                <Field
                  label="Approved budget for the contract (ABC)"
                  value={formatPeso(procurement.abc)}
                  size="lg"
                />
              </div>
              <div className="space-y-3">
                <Field label="Mode of procurement" value={procurement.mode} />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Funding source" value={procurement.fund || "—"} />
                  <Field label="End-user unit" value={procurement.end_user || "—"} />
                </div>
              </div>
            </div>
          </div>

          {/* II — Executive summary */}
          <SectionHead numeral="II" title="Executive Summary" tag="Automated intelligence scope" />
          <div className="mt-3 rounded-lg bg-sky px-5 py-4">
            <p className="text-justify text-[13px] leading-[1.8] text-brand">
              Under Republic Act No. 9184 and its 2016 Revised Implementing Rules
              and Regulations, the DICT Procurement AI Engine checked the
              pre-procurement documentation submitted for {procurement.ref}.{" "}
              <strong className="font-bold">
                {spelled(procurement.documents.length)}
              </strong>{" "}
              document{procurement.documents.length === 1 ? "" : "s"}
              {docTypes.length > 0 ? ` — ${docTypes.join(", ")} — ` : " "}
              {procurement.documents.length === 1 ? "was" : "were"}{" "}
              cross-referenced across{" "}
              <strong className="font-bold">
                {spelled(dimensionCount)}
              </strong>{" "}
              review dimension{dimensionCount === 1 ? "" : "s"}, raising{" "}
              <strong className="font-bold">{spelled(reportFindings.length)}</strong>{" "}
              finding{reportFindings.length === 1 ? "" : "s"}
              {finalized ? " confirmed by the BAC" : " for the BAC to verify"}.
              Each finding is a point for the committee to confirm, not a
              determination.
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Stat value={procurement.documents.length} label="Documents analyzed" />
              <Stat value={reportFindings.length} label="Audit findings" />
              <SeverityBreakdown counts={counts} total={reportFindings.length} />
            </div>
          </div>

          {/* III — Findings */}
          <SectionHead numeral="III" title="Findings & Resolutions" tag="Audit matrix" />
          {finalized && undecided > 0 && (
            <p className="mt-3 rounded-lg border border-warning/30 bg-warning/5 px-5 py-3 text-[12.5px] leading-relaxed text-ink">
              {undecided} finding{undecided === 1 ? " was" : "s were"} left pending
              (no committee action recorded) at finalization and{" "}
              {undecided === 1 ? "is" : "are"} not included below.
            </p>
          )}
          {reportFindings.length === 0 ? (
            <p className="mt-3 rounded-lg bg-page px-5 py-4 text-[13px] text-subtle">
              {finalized
                ? "No findings were accepted by the committee for this procurement."
                : "No findings were recorded for this procurement."}
            </p>
          ) : (
            <ol className="mt-3 space-y-3">
              {reportFindings.map((finding, index) => (
                <li
                  key={finding.id}
                  className="overflow-hidden rounded-lg border border-line break-inside-avoid"
                >
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2 bg-sky px-4 py-2.5">
                    <span className="rounded bg-brand px-2 py-0.5 text-[10.5px] font-bold tracking-wide text-white">
                      ITEM {String(index + 1).padStart(2, "0")}
                    </span>
                    <h4 className="text-[13.5px] font-bold text-navy">
                      {finding.title}
                    </h4>
                    <span className="ml-auto">
                      <SeverityPill severity={finding.severity} />
                    </span>
                  </div>

                  <div className="grid gap-3 px-4 py-4 sm:grid-cols-2">
                    <Field
                      label="AI findings / analysis"
                      value={finding.analysis}
                      body
                    />
                    <Field
                      label="Suggested action"
                      value={finding.recommendation || "No action suggested."}
                      body
                    />
                  </div>

                  <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-line px-4 py-2.5 text-[11.5px] text-subtle">
                    <span>
                      Source: {finding.source.doc}
                      {finding.source.page ? `, page ${finding.source.page}` : ""}
                    </span>
                    <span>Dimension: {finding.dimension.replace(/_/g, " ")}</span>
                    <span>
                      Committee action:{" "}
                      {finding.decision ? (
                        <span className="font-semibold text-compliant">
                          {DECISION_PAST[finding.decision]} by {finding.decided_by} on{" "}
                          {formatDate(finding.decided_at)}
                        </span>
                      ) : (
                        <span className="font-semibold text-warning">Pending</span>
                      )}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          )}

          {/* IV — Committee notes */}
          {(notes || editing) && (
            <>
              <SectionHead numeral="IV" title="Committee Remarks" tag="On the record" />
              {editing ? (
                <div className="mt-3 print:hidden">
                  <textarea
                    className={`${inputCls} min-h-[110px] leading-relaxed`}
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="Anything the committee wants on the record alongside the findings"
                  />
                  <button
                    onClick={saveNotes}
                    disabled={busy}
                    className={`${btnPrimary} mt-2`}
                  >
                    Save notes
                  </button>
                </div>
              ) : (
                <p className="mt-3 whitespace-pre-wrap rounded-lg bg-page px-5 py-4 text-[13px] leading-relaxed text-ink">
                  {notes}
                </p>
              )}
            </>
          )}

          <footer className="mt-7 border-t border-line pt-4 text-center text-[11px] leading-relaxed text-subtle">
            {finalized
              ? `Finalized by ${procurement.finalized_by} on ${formatDate(procurement.finalized_at)}`
              : "Draft — not yet finalized"}
            <br />
            Generated by the DICT Procurement AI Engine for BAC verification
            under RA 9184 and RA 12009.
          </footer>
        </div>
      </article>

      <Modal
        open={confirming === "finalize"}
        onClose={() => setConfirming(null)}
        title="Finalize report"
        description={procurement.ref}
      >
        <div className="space-y-3 px-6 py-5 text-[13px] leading-relaxed">
          <p>
            Finalizing sets the status of {procurement.ref} to{" "}
            <span className="font-semibold">finalized</span> and marks the report
            as the record of this review. Documents can no longer be attached or
            removed.
          </p>
          {undecided > 0 && (
            <div className="flex items-start gap-2.5 rounded-md border border-warning/30 bg-warning/5 px-3 py-2.5">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <span className="text-[12.5px] text-ink">
                {undecided} finding{undecided === 1 ? " has" : "s have"} no
                recorded action. You can finalize anyway; findings without a
                committee action are excluded from the finalized report, and
                their count is noted.
              </span>
            </div>
          )}
          <p className="text-subtle">
            The report stays available to print after finalizing.
          </p>
        </div>
        <ModalFooter
          submitLabel={busy ? "Finalizing…" : "Finalize Report"}
          disabled={busy}
          onCancel={() => setConfirming(null)}
          onSubmit={handleFinalize}
        />
      </Modal>

      <Modal
        open={confirming === "regenerate"}
        onClose={() => setConfirming(null)}
        title="Regenerate report"
        description={procurement.ref}
      >
        <div className="space-y-3 px-6 py-5 text-[13px] leading-relaxed">
          <p>
            Running the review again replaces the current findings with a fresh
            set.
          </p>
          <div className="flex items-start gap-2.5 rounded-md border border-warning/30 bg-warning/5 px-3 py-2.5">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <span className="text-[12.5px] text-ink">
              Committee actions and comments recorded against the current
              findings are not carried over.
            </span>
          </div>
        </div>
        <ModalFooter
          submitLabel={busy ? "Regenerating…" : "Regenerate"}
          disabled={busy}
          onCancel={() => setConfirming(null)}
          onSubmit={handleRegenerate}
        />
      </Modal>
    </div>
  );
}

/** Numbered section rule: roman badge on the left, scope tag on the right. */
function SectionHead({
  numeral,
  title,
  tag,
}: {
  numeral: string;
  title: string;
  tag: string;
}) {
  return (
    <div className="mt-7 flex items-center gap-3">
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-navy text-[10.5px] font-bold text-white">
        {numeral}
      </span>
      <h3 className="text-[13.5px] font-bold uppercase tracking-[0.06em] text-navy">
        {title}
      </h3>
      <span className="ml-auto text-right text-[10px] font-semibold uppercase tracking-[0.14em] text-sev-medium">
        {tag}
      </span>
    </div>
  );
}

function Field({
  label,
  value,
  size = "md",
  body = false,
}: {
  label: string;
  value: string;
  size?: "md" | "lg";
  /** Prose rather than a data point: regular weight, roomier line-height. */
  body?: boolean;
}) {
  return (
    <div className="rounded-lg bg-page px-4 py-3">
      <div className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-subtle">
        {label}
      </div>
      <div
        className={
          body
            ? "mt-1.5 text-[12.5px] leading-relaxed text-ink"
            : `mt-1 font-bold text-navy ${size === "lg" ? "text-[15px]" : "text-[13.5px]"}`
        }
      >
        {value}
      </div>
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-lg bg-white px-4 py-4 text-center">
      <div className="text-[30px] font-bold leading-none text-brand">{value}</div>
      <div className="mt-2 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-subtle">
        {label}
      </div>
    </div>
  );
}

/** Donut of the severity mix, with the total in the hole and a keyed legend. */
function SeverityBreakdown({
  counts,
  total,
}: {
  counts: Record<Severity, number>;
  total: number;
}) {
  const present = SEVERITY_KEYS.filter((key) => counts[key] > 0);
  let offset = 0;

  return (
    <div className="flex items-center gap-4 rounded-lg bg-white px-4 py-4">
      <svg viewBox="0 0 36 36" className="h-[68px] w-[68px] shrink-0 -rotate-90">
        <circle
          cx="18"
          cy="18"
          r="15.915"
          fill="none"
          stroke="#EAF3FB"
          strokeWidth="4"
        />
        {present.map((key) => {
          const length = (counts[key] / total) * 100;
          const dash = `${length} ${100 - length}`;
          const segment = (
            <circle
              key={key}
              cx="18"
              cy="18"
              r="15.915"
              fill="none"
              stroke={SEV_HEX[key]}
              strokeWidth="4"
              strokeDasharray={dash}
              strokeDashoffset={-offset}
            />
          );
          offset += length;
          return segment;
        })}
        <text
          x="18"
          y="18"
          transform="rotate(90 18 18)"
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-navy text-[9px] font-bold"
        >
          {total}
        </text>
      </svg>

      <div className="min-w-0">
        <div className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-subtle">
          Severity breakdown
        </div>
        <ul className="mt-1.5 space-y-0.5">
          {present.length === 0 && (
            <li className="text-[11.5px] text-subtle">No findings</li>
          )}
          {present.map((key) => (
            <li key={key} className="flex items-center gap-2 text-[11.5px] text-ink">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: SEV_HEX[key] }}
              />
              {severityLabel(key)}: {counts[key]}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
