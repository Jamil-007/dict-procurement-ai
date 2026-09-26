"use client";

import { useEffect, useState } from "react";
import { Info, X } from "lucide-react";

import { Modal, ModalFooter, areaCls } from "@/components/shell/modal";
import { severityLabel } from "@/components/shell/status-pill";
import type { Finding, RejectionReason } from "@/types/records";
import { cn } from "@/lib/utils";

/**
 * The reasons the BAC can give for rejecting a finding.
 *
 * Fixed rather than free text because a rejected finding never reaches the
 * final report: the reason is the only thing left to audit, and a countable
 * one says something across procurements that a paragraph cannot.
 */
export const REJECTION_REASONS: {
  value: RejectionReason;
  label: string;
  blurb: string;
}[] = [
  {
    value: "not_applicable",
    label: "Not Applicable",
    blurb: "This analysis is not applicable to this procurement.",
  },
  {
    value: "insufficient_evidence",
    label: "Insufficient Evidence",
    blurb: "The analysis is based on insufficient or incorrect evidence.",
  },
  {
    value: "misinterpreted",
    label: "Misinterpreted Information",
    blurb: "The analysis misinterprets the document(s) or context.",
  },
  {
    value: "duplicate",
    label: "Duplicate / Already Addressed",
    blurb: "This issue is already reported in another finding.",
  },
  {
    value: "acceptable",
    label: "Acceptable as Is",
    blurb: "This is not a material concern or is acceptable based on procurement context.",
  },
  { value: "other", label: "Other", blurb: "Provide a custom reason." },
];

export const REJECTION_LABEL = Object.fromEntries(
  REJECTION_REASONS.map((r) => [r.value, r.label])
) as Record<RejectionReason, string>;

const NOTE_LIMIT = 500;

const CONFIDENCE_LABEL = { high: "High", medium: "Medium", low: "Low" };

/**
 * Confirms a rejection and captures why.
 *
 * Rejecting hides the finding from the review list and drops it from the
 * final report, so the dialog restates what is being rejected before asking
 * for the reason — the committee should not have to trust that it clicked the
 * right card.
 */
export function RejectFindingDialog({
  open,
  finding,
  dimensionLabel,
  busy,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  finding: Finding;
  dimensionLabel: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (reason: RejectionReason, note: string) => void;
}) {
  const [reason, setReason] = useState<RejectionReason | null>(null);
  const [note, setNote] = useState("");

  // Each opening starts clean — a reason left over from the last card is the
  // one mistake this dialog exists to prevent.
  useEffect(() => {
    if (open) {
      setReason(null);
      setNote("");
    }
  }, [open]);

  const noteRequired = reason === "other";
  const canConfirm =
    !!reason && !busy && (!noteRequired || note.trim().length > 0);

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Reject Analysis"
      description="Provide a reason for rejecting this analysis. The analysis will be marked as Rejected and will not be included in the final report."
      width="sm:w-[65vw] sm:max-w-[65vw]"
      height="max-h-[80vh]"
      icon={
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-critical/10">
          <X className="h-[18px] w-[18px] text-critical" aria-hidden />
        </span>
      }
    >
      {/* The scroller: the header and the Confirm Reject footer stay visible
          however long the analysis being rejected runs. */}
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
        {/* What is being rejected, restated from the card. */}
        <div className="rounded-lg border border-line bg-sky/60 px-4 py-3.5">
          <p className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-brand">
            <Info className="h-3.5 w-3.5" aria-hidden />
            Analysis being rejected
          </p>
          <p className="mt-2 text-[13px] font-semibold text-navy">
            <span className="mr-2 text-subtle">{finding.id}</span>
            {finding.title}
          </p>
          <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-subtle">
            <span>Agent: {dimensionLabel}</span>
            <span>Severity: {severityLabel(finding.severity)}</span>
            {finding.confidence && (
              <span>Confidence: {CONFIDENCE_LABEL[finding.confidence]}</span>
            )}
          </p>
          <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink">
            <span className="font-semibold">Summary: </span>
            {finding.analysis}
          </p>
        </div>

        <fieldset>
          <legend className="text-[12.5px] font-semibold text-ink">
            Reason for rejection <span className="text-critical">*</span>
          </legend>
          <p className="mt-0.5 text-[12px] text-subtle">
            Select a reason that best describes why this analysis is being
            rejected.
          </p>

          <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
            {REJECTION_REASONS.map((option) => (
              <label
                key={option.value}
                className={cn(
                  "flex cursor-pointer gap-2.5 rounded-lg border px-3.5 py-3 transition-colors",
                  reason === option.value
                    ? "border-brand bg-sky"
                    : "border-line bg-white hover:border-brand/50"
                )}
              >
                <input
                  type="radio"
                  name="rejection-reason"
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-brand"
                  checked={reason === option.value}
                  onChange={() => setReason(option.value)}
                />
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-semibold text-navy">
                    {option.label}
                  </span>
                  <span className="mt-0.5 block text-[11.5px] leading-relaxed text-subtle">
                    {option.blurb}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <p className="text-[12.5px] font-semibold text-ink">
            Additional comments{" "}
            <span className="font-normal text-subtle">
              {noteRequired ? "(required)" : "(optional)"}
            </span>
          </p>
          <p className="mt-0.5 text-[12px] text-subtle">
            Provide more details to explain why this analysis is being rejected.
          </p>
          <textarea
            className={cn(areaCls, "mt-2 min-h-[92px]")}
            maxLength={NOTE_LIMIT}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Type your comments here..."
          />
          <p className="mt-1 text-right text-[11px] text-subtle">
            {note.length}/{NOTE_LIMIT}
          </p>
        </div>
      </div>

      <ModalFooter
        submitLabel={busy ? "Rejecting…" : "Confirm Reject"}
        tone="danger"
        disabled={!canConfirm}
        onCancel={onCancel}
        onSubmit={() => reason && onConfirm(reason, note.trim())}
      />
    </Modal>
  );
}
