"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowRight, CheckCircle2, FileText, Printer } from "lucide-react";
import { toast } from "sonner";

import { Modal, ModalFooter, inputCls } from "@/components/shell/modal";
import { btnGhost, btnPrimary } from "@/components/shell/page-header";
import { severityLabel } from "@/components/shell/status-pill";
import {
  finalizeProcurement,
  listFindings,
  patchProcurement,
} from "@/lib/records-client";
import { formatDate, formatPeso } from "@/lib/format";
import type { Finding, Procurement, Severity } from "@/types/records";

const DECISION_PAST: Record<string, string> = {
  accepted: "Accepted",
  modified: "Modified",
  further: "Further review requested",
  rejected: "Rejected",
};

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
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listFindings(procurement.ref)
      .then(setFindings)
      .catch(() => setFindings([]));
  }, [procurement.ref]);

  const counts = useMemo(() => {
    const out: Record<Severity, number> = { critical: 0, warning: 0, compliant: 0 };
    findings.forEach((f) => (out[f.severity] += 1));
    return out;
  }, [findings]);

  const undecided = findings.filter((f) => !f.decision).length;
  const finalized = procurement.status === "finalized";

  async function saveNotes() {
    setBusy(true);
    try {
      onChange(await patchProcurement(procurement.ref, { report_notes: notes }));
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
      setConfirming(false);
      toast.success("Review finalized");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not finalize");
    } finally {
      setBusy(false);
    }
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
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-white px-5 py-4 print:hidden">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-sky">
          <FileText className="h-5 w-5 text-brand" />
        </span>
        <div className="min-w-0">
          <h2 className="text-[17px] font-bold leading-tight text-navy">
            Final Procurement Review Report
          </h2>
          <p className="mt-0.5 text-[12.5px] text-subtle">
            {findings.length - undecided} of {findings.length} findings reviewed
            {undecided ? ` · ${undecided} pending` : ""}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <button
            onClick={() => window.print()}
            className={`${btnGhost} flex items-center gap-2`}
          >
            <Printer className="h-4 w-4" />
            Print Report
          </button>
          {finalized ? (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-compliant/20 bg-compliant/10 px-3 py-2 text-[12.5px] font-semibold text-compliant">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Finalized
            </span>
          ) : (
            <button onClick={() => setConfirming(true)} className={btnPrimary}>
              Finalize Review
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
              These findings will appear in the report as pending.
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

      <article className="rounded-lg border border-line bg-white px-8 py-8 font-serif text-ink print:border-0">
        <header className="border-b border-line pb-4 text-center">
          <p className="text-[12px] font-sans uppercase tracking-[0.14em] text-subtle">
            Department of Information and Communications Technology
          </p>
          <h1 className="mt-2 text-[22px] font-semibold text-navy">
            Procurement Review Report
          </h1>
          <p className="mt-1 text-[14px] text-subtle">
            {procurement.ref} · {formatDate(procurement.updated)}
          </p>
        </header>

        <section className="mt-6">
          <h2 className="text-[15px] font-semibold text-navy">
            {procurement.title}
          </h2>
          <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-1.5 text-[14px]">
            <Row label="Approved Budget" value={formatPeso(procurement.abc)} />
            <Row label="Mode of Procurement" value={procurement.mode} />
            <Row label="Fund Source" value={procurement.fund || "—"} />
            <Row label="End User" value={procurement.end_user || "—"} />
            <Row
              label="Documents Reviewed"
              value={`${procurement.documents.length}`}
            />
            <Row label="Findings Raised" value={`${findings.length}`} />
          </dl>
        </section>

        <section className="mt-6">
          <h3 className="border-b border-line pb-1 text-[14px] font-semibold text-navy">
            Summary
          </h3>
          <p className="mt-2 text-[14px] leading-relaxed">
            The review raised {counts.critical} item
            {counts.critical === 1 ? "" : "s"} requiring BAC review,{" "}
            {counts.warning} potential issue
            {counts.warning === 1 ? "" : "s"}, and {counts.compliant} area
            {counts.compliant === 1 ? "" : "s"} where no issue was found. Every
            finding below is a point for the committee to verify, not a
            determination.
          </p>
        </section>

        <section className="mt-6">
          <h3 className="border-b border-line pb-1 text-[14px] font-semibold text-navy">
            Findings and Committee Action
          </h3>
          {findings.length === 0 ? (
            <p className="mt-2 text-[14px] text-subtle">
              No findings have been recorded for this procurement.
            </p>
          ) : (
            <ol className="mt-3 space-y-4">
              {findings.map((finding) => (
                <li key={finding.id}>
                  <p className="text-[14px] font-semibold">
                    {finding.id} — {finding.title}
                  </p>
                  <p className="text-[13px] text-subtle">
                    {severityLabel(finding.severity)} ·{" "}
                    {finding.dimension.replace(/_/g, " ")} ·{" "}
                    {finding.source.doc}
                    {finding.source.page ? `, page ${finding.source.page}` : ""}
                  </p>
                  <p className="mt-1 text-[14px] leading-relaxed">
                    {finding.analysis}
                  </p>
                  {finding.recommendation && (
                    <p className="mt-1 text-[14px] leading-relaxed">
                      <span className="font-semibold">Suggested action: </span>
                      {finding.recommendation}
                    </p>
                  )}
                  <p className="mt-1 text-[13px] text-subtle">
                    Committee action:{" "}
                    {finding.decision
                      ? `${DECISION_PAST[finding.decision]} by ${finding.decided_by} on ${formatDate(finding.decided_at)}`
                      : "Pending"}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>

        {(notes || !finalized) && (
          <section className="mt-6">
            <h3 className="border-b border-line pb-1 text-[14px] font-semibold text-navy">
              Committee Notes
            </h3>
            {finalized ? (
              <p className="mt-2 whitespace-pre-wrap text-[14px] leading-relaxed">
                {notes || "—"}
              </p>
            ) : (
              <div className="mt-2 font-sans print:hidden">
                <textarea
                  className={`${inputCls} min-h-[110px] leading-relaxed`}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Anything the committee wants on the record alongside the findings"
                />
                <button
                  onClick={saveNotes}
                  disabled={busy}
                  className={`${btnGhost} mt-2`}
                >
                  Save notes
                </button>
              </div>
            )}
          </section>
        )}

        <footer className="mt-8 border-t border-line pt-4 text-center text-[12px] font-sans text-subtle">
          {finalized
            ? `Finalized by ${procurement.finalized_by} on ${formatDate(procurement.finalized_at)}`
            : "Draft — not yet finalized"}
          <br />
          Prepared through AI Analyst · DICT
        </footer>
      </article>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Finalize review"
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
                recorded action. You can finalize anyway, and they will be listed
                as pending.
              </span>
            </div>
          )}
          <p className="text-subtle">
            The report stays available to print after finalizing.
          </p>
        </div>
        <ModalFooter
          submitLabel={busy ? "Finalizing…" : "Finalize Review"}
          disabled={busy}
          onCancel={() => setConfirming(false)}
          onSubmit={handleFinalize}
        />
      </Modal>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-subtle">{label}:</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}
