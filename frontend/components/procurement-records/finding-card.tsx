"use client";

import { useState } from "react";
import {
  Check,
  Clock,
  GitCompareArrows,
  MessageSquare,
  MessageSquarePlus,
  Pencil,
  X,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";

import { SeverityPill, SEVERITY_BAR, SEVERITY_TEXT } from "@/components/shell/status-pill";
import { AutoTextarea } from "@/components/shell/auto-textarea";
import { inputCls } from "@/components/shell/modal";
import { addComment, patchFinding } from "@/lib/records-client";
import type { Decision, Finding, FindingFeedback } from "@/types/records";
import { cn } from "@/lib/utils";

/**
 * The BAC decides by rejecting, modifying or accepting. `further` is no longer
 * offered but stays mapped here so a finding decided before it was dropped
 * still renders its chip.
 */
const DECISION_CHIP: Record<
  Decision,
  { label: string; className: string; icon: LucideIcon }
> = {
  accepted: {
    label: "Accepted",
    className: "border-compliant/25 bg-compliant/10 text-compliant",
    icon: Check,
  },
  modified: {
    label: "Modified",
    className: "border-line bg-sky text-brand",
    icon: Pencil,
  },
  further: {
    label: "Further review requested",
    className: "border-line bg-sky text-brand",
    icon: Clock,
  },
  rejected: {
    label: "Rejected",
    className: "border-critical/25 bg-critical/10 text-critical",
    icon: X,
  },
};

const FEEDBACK: { value: FindingFeedback; label: string }[] = [
  { value: "correct", label: "Correct" },
  { value: "incorrect", label: "Incorrect" },
  { value: "irrelevant", label: "Irrelevant" },
  { value: "incomplete", label: "Incomplete" },
];

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold tracking-[0.13em] text-subtle">
      {children}
    </p>
  );
}

/** "Page 11 · Section 4" — drops whichever part the model could not place. */
function locator(page?: number | null, section?: string) {
  return [page ? `Page ${page}` : null, section || null].filter(Boolean).join(" · ");
}

/** A text link in the action bar. Edit and Comment read as secondary to a decision. */
const actionLink =
  "inline-flex items-center gap-2 text-[13px] font-semibold text-brand transition-colors hover:text-navy";

/**
 * Renders any finding conforming to the review contract, whichever dimension
 * produced it. Dimension owners add analyzers, never UI.
 *
 * The severity accent appears twice and only twice: the bar down the left edge
 * and the chip in the header. Everything else stays neutral so a wall of cards
 * still scans by colour.
 */
export function FindingCard({
  finding,
  dimensionLabel,
  onChange,
}: {
  finding: Finding;
  dimensionLabel: string;
  onChange: (updated: Finding) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [analysis, setAnalysis] = useState(finding.analysis);
  const [recommendation, setRecommendation] = useState(finding.recommendation);
  const [commenting, setCommenting] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const decision = finding.decision ? DECISION_CHIP[finding.decision] : null;

  async function apply(patch: Parameters<typeof patchFinding>[2]) {
    setBusy(true);
    try {
      onChange(await patchFinding(finding.procurement_ref, finding.id, patch));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit() {
    await apply({ analysis, recommendation });
    setEditing(false);
    toast.success("Analysis updated");
  }

  async function saveComment() {
    if (!comment.trim()) return;
    setBusy(true);
    try {
      onChange(
        await addComment(finding.procurement_ref, finding.id, comment.trim())
      );
      setComment("");
      setCommenting(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add comment");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      id={`f-${finding.id}`}
      className="scroll-mt-6 overflow-hidden rounded-xl border border-line bg-white"
    >
      <div className="flex">
        <div className={cn("w-1 shrink-0", SEVERITY_BAR[finding.severity])} />
        <div className="min-w-0 flex-1">
          <div className="px-5 pb-4 pt-4">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityPill severity={finding.severity} />
              <span className="text-[11px] font-semibold tracking-wide text-subtle">
                {dimensionLabel.toUpperCase()}
              </span>
              <span className="text-[11px] text-subtle/70">{finding.id}</span>
              {decision && (
                <span
                  className={cn(
                    "ml-auto inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
                    decision.className
                  )}
                >
                  <decision.icon className="h-3 w-3" aria-hidden />
                  {decision.label}
                </span>
              )}
            </div>

            <h3 className="mt-2.5 text-[15px] font-semibold leading-snug text-navy">
              {finding.title}
            </h3>

            <div className="mt-4 space-y-3.5">
              <div>
                <Label>{finding.edited ? "ANALYSIS · EDITED" : "AI ANALYSIS"}</Label>
                {editing ? (
                  <AutoTextarea
                    className={cn(inputCls, "mt-1.5 leading-relaxed")}
                    minRows={4}
                    value={analysis}
                    onChange={(e) => setAnalysis(e.target.value)}
                  />
                ) : (
                  <p className="mt-1.5 whitespace-pre-line text-[13px] leading-relaxed text-ink">
                    {finding.analysis}
                  </p>
                )}
                {finding.edited && finding.ai_analysis !== finding.analysis && (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-[11.5px] text-brand hover:text-navy">
                      Show original AI analysis
                    </summary>
                    <p className="mt-1.5 whitespace-pre-line border-l-2 border-line pl-3 text-[12.5px] leading-relaxed text-subtle">
                      {finding.ai_analysis}
                    </p>
                  </details>
                )}
              </div>

              {(finding.recommendation || editing) && (
                <div>
                  <Label>RECOMMENDATION</Label>
                  {editing ? (
                    <AutoTextarea
                      className={cn(inputCls, "mt-1.5 leading-relaxed")}
                      minRows={2}
                      value={recommendation}
                      onChange={(e) => setRecommendation(e.target.value)}
                    />
                  ) : (
                    <p className="mt-1.5 whitespace-pre-line text-[13px] leading-relaxed text-ink">
                      {finding.recommendation}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Evidence — where the finding came from, and the text it rests on. */}
            <div className="mt-4 rounded-lg border border-line bg-page px-4 py-3.5">
              <div className="mb-3 flex flex-wrap gap-x-8 gap-y-2.5 border-b border-line pb-3">
                <div>
                  <Label>SOURCE</Label>
                  <div className="mt-1 text-[12.5px] font-medium text-ink">
                    {finding.source.doc}
                  </div>
                  {locator(finding.source.page, finding.source.section) && (
                    <div className="text-[11.5px] text-subtle">
                      {locator(finding.source.page, finding.source.section)}
                    </div>
                  )}
                </div>
                {finding.policy_basis && (
                  <div>
                    <Label>POLICY BASIS</Label>
                    <div className="mt-1 text-[12.5px] font-medium text-ink">
                      {finding.policy_basis}
                    </div>
                  </div>
                )}
              </div>

              {finding.comparison.length > 0 ? (
                <>
                  <Label>COMPARED TEXT</Label>
                  <div
                    className={cn(
                      "mt-2 grid gap-3",
                      finding.comparison.length > 2
                        ? "sm:grid-cols-3"
                        : "sm:grid-cols-2"
                    )}
                  >
                    {finding.comparison.map((side, index) => (
                      <div
                        key={`${side.doc}-${index}`}
                        className="rounded-lg border border-line bg-white px-3.5 py-3"
                      >
                        <div className="text-[11px] font-semibold text-navy">
                          {side.doc}
                        </div>
                        {locator(side.page, side.label) && (
                          <div className="mt-0.5 text-[10.5px] text-subtle">
                            {locator(side.page, side.label)}
                          </div>
                        )}
                        <p className="mt-2 text-[12.5px] italic leading-relaxed text-ink">
                          “{side.quote}”
                        </p>
                      </div>
                    ))}
                  </div>
                  {finding.delta && (
                    <div
                      className={cn(
                        "mt-3 flex items-center gap-2 text-[12px] font-semibold",
                        SEVERITY_TEXT[finding.severity]
                      )}
                    >
                      <GitCompareArrows className="h-3.5 w-3.5" aria-hidden />
                      {finding.delta}
                    </div>
                  )}
                </>
              ) : (
                finding.quote && (
                  <>
                    <Label>CITED TEXT</Label>
                    <p className="mt-2 text-[12.5px] italic leading-relaxed text-ink">
                      “{finding.quote}”
                    </p>
                  </>
                )
              )}
            </div>

            {finding.comments.length > 0 && (
              <div className="mt-4 space-y-2.5">
                {finding.comments.map((entry, index) => (
                  <div key={index} className="border-l-2 border-navy pl-3.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <MessageSquare className="h-3.5 w-3.5 text-navy" aria-hidden />
                      <span className="text-[12px] font-semibold text-navy">
                        {entry.author}
                      </span>
                      <span className="text-[11px] text-subtle">
                        {new Date(entry.at).toLocaleString("en-PH")}
                      </span>
                    </div>
                    <p className="mt-1.5 whitespace-pre-line text-[13px] leading-relaxed text-ink">
                      {entry.text}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {commenting && (
              <div className="mt-4 space-y-2">
                <AutoTextarea
                  className={cn(inputCls, "leading-relaxed")}
                  minRows={3}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Add a note for the committee"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={saveComment}
                    disabled={busy}
                    className="rounded-md bg-brand px-3 py-1.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-navy disabled:opacity-60"
                  >
                    Save comment
                  </button>
                  <button
                    onClick={() => setCommenting(false)}
                    className="rounded-md border border-line px-3 py-1.5 text-[12.5px] transition-colors hover:bg-page"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {finding.decision && finding.decided_by && (
              <p className="mt-4 text-[11.5px] text-subtle">
                {DECISION_CHIP[finding.decision].label} by {finding.decided_by} ·{" "}
                {new Date(finding.decided_at ?? "").toLocaleString("en-PH")}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line bg-white px-5 py-3">
            {editing ? (
              <>
                <button
                  onClick={saveEdit}
                  disabled={busy}
                  className="rounded-md border border-brand bg-brand px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:border-navy hover:bg-navy disabled:opacity-60"
                >
                  Save changes
                </button>
                <button
                  onClick={() => {
                    setAnalysis(finding.analysis);
                    setRecommendation(finding.recommendation);
                    setEditing(false);
                  }}
                  className="rounded-md border border-line bg-white px-4 py-2 text-[13px] font-semibold transition-colors hover:bg-page"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button onClick={() => setEditing(true)} className={actionLink}>
                  <Pencil className="h-4 w-4" aria-hidden />
                  Edit Analysis
                </button>
                <span className="h-5 w-px bg-line" />
                <button onClick={() => setCommenting(true)} className={actionLink}>
                  <MessageSquarePlus className="h-4 w-4" aria-hidden />
                  Add Comment
                </button>

                <div className="ml-auto flex flex-wrap gap-2">
                  <button
                    onClick={() => apply({ decision: "rejected" })}
                    disabled={busy}
                    className={cn(
                      "rounded-md border px-4 py-2 text-[13px] font-semibold transition-colors disabled:opacity-60",
                      finding.decision === "rejected"
                        ? "border-critical bg-critical text-white"
                        : "border-critical bg-white text-critical hover:bg-critical/5"
                    )}
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => apply({ decision: "modified" })}
                    disabled={busy}
                    className={cn(
                      "rounded-md border px-4 py-2 text-[13px] font-semibold transition-colors disabled:opacity-60",
                      finding.decision === "modified"
                        ? "border-navy bg-navy text-white"
                        : "border-brand bg-white text-navy hover:bg-sky"
                    )}
                  >
                    Modify
                  </button>
                  <button
                    onClick={() => apply({ decision: "accepted" })}
                    disabled={busy}
                    className={cn(
                      "rounded-md border px-4 py-2 text-[13px] font-semibold transition-colors disabled:opacity-60",
                      finding.decision === "accepted"
                        ? "border-navy bg-navy text-white"
                        : "border-brand bg-brand text-white hover:border-navy hover:bg-navy"
                    )}
                  >
                    Accept
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-line bg-page px-5 py-2.5">
            <span className="mr-1 text-[12.5px] text-subtle">
              Was this finding useful?
            </span>
            {FEEDBACK.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => apply({ feedback: value })}
                disabled={busy}
                className={cn(
                  "rounded px-2 py-0.5 text-[12.5px] transition-colors disabled:opacity-60",
                  finding.feedback === value
                    ? "bg-sky font-semibold text-brand"
                    : "text-subtle hover:text-brand"
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </article>
  );
}
