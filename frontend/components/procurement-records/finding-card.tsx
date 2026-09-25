"use client";

import { useState } from "react";
import { MessageSquarePlus, Pencil } from "lucide-react";
import { toast } from "sonner";

import { SeverityPill } from "@/components/shell/status-pill";
import { inputCls } from "@/components/shell/modal";
import { addComment, patchFinding } from "@/lib/records-client";
import type { Decision, Finding, FindingFeedback } from "@/types/records";
import { cn } from "@/lib/utils";

const DECISIONS: { value: Decision; label: string }[] = [
  { value: "accepted", label: "Accept" },
  { value: "modified", label: "Modify" },
  { value: "further", label: "Request Further Review" },
  { value: "rejected", label: "Reject" },
];

const DECISION_PAST: Record<Decision, string> = {
  accepted: "Accepted",
  modified: "Modified",
  further: "Further review requested",
  rejected: "Rejected",
};

const FEEDBACK: { value: FindingFeedback; label: string }[] = [
  { value: "correct", label: "Correct" },
  { value: "incorrect", label: "Incorrect" },
  { value: "irrelevant", label: "Irrelevant" },
  { value: "incomplete", label: "Incomplete" },
];

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold tracking-[0.08em] text-subtle">
      {children}
    </p>
  );
}

function sourceLine(doc: string, page?: number | null, section?: string) {
  return [doc, page ? `page ${page}` : null, section || null]
    .filter(Boolean)
    .join(" · ");
}

/**
 * Renders any finding conforming to the review contract, whichever dimension
 * produced it. Dimension owners add analyzers, never UI.
 */
export function FindingCard({
  finding,
  onChange,
}: {
  finding: Finding;
  onChange: (updated: Finding) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [analysis, setAnalysis] = useState(finding.analysis);
  const [recommendation, setRecommendation] = useState(finding.recommendation);
  const [commenting, setCommenting] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

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
    <article className="rounded-lg border border-line bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-medium text-subtle">
              {finding.id}
            </span>
            <SeverityPill severity={finding.severity} />
            <span className="rounded-full bg-page px-2 py-0.5 text-[12px] text-subtle">
              {finding.dimension.replace(/_/g, " ")}
            </span>
            {finding.edited && (
              <span className="rounded-full bg-sky px-2 py-0.5 text-[12px] text-brand">
                Edited by BAC
              </span>
            )}
          </div>
          <h3 className="text-[14.5px] font-semibold leading-snug text-navy">
            {finding.title}
          </h3>
        </div>
      </div>

      <div className="space-y-4 px-4 py-4">
        <div>
          <Label>AI ANALYSIS</Label>
          {editing ? (
            <textarea
              className={cn(inputCls, "mt-1 min-h-[96px] leading-relaxed")}
              value={analysis}
              onChange={(e) => setAnalysis(e.target.value)}
            />
          ) : (
            <p className="mt-1 text-[13.5px] leading-relaxed text-ink">
              {finding.analysis}
            </p>
          )}
          {finding.edited && finding.ai_analysis !== finding.analysis && (
            <details className="mt-1.5">
              <summary className="cursor-pointer text-[12px] text-subtle hover:text-ink">
                Show original wording
              </summary>
              <p className="mt-1 border-l-2 border-line pl-3 text-[13px] leading-relaxed text-subtle">
                {finding.ai_analysis}
              </p>
            </details>
          )}
        </div>

        {(finding.recommendation || editing) && (
          <div>
            <Label>SUGGESTED ACTION</Label>
            {editing ? (
              <textarea
                className={cn(inputCls, "mt-1 min-h-[64px] leading-relaxed")}
                value={recommendation}
                onChange={(e) => setRecommendation(e.target.value)}
              />
            ) : (
              <p className="mt-1 text-[13.5px] leading-relaxed text-ink">
                {finding.recommendation}
              </p>
            )}
          </div>
        )}

        {finding.quote && finding.comparison.length === 0 && (
          <blockquote className="border-l-2 border-brand/40 bg-page px-3 py-2 text-[13px] italic leading-relaxed text-ink">
            “{finding.quote}”
          </blockquote>
        )}

        {finding.comparison.length > 0 && (
          <div>
            <Label>COMPARED TEXT</Label>
            <div className="mt-1.5 grid gap-2 md:grid-cols-2">
              {finding.comparison.map((side, index) => (
                <div
                  key={`${side.doc}-${index}`}
                  className="rounded border border-line bg-page p-3"
                >
                  <p className="text-[12px] text-subtle">
                    {sourceLine(side.doc, side.page)}
                    {side.label && ` — ${side.label}`}
                  </p>
                  <p className="mt-1 text-[13px] italic leading-relaxed text-ink">
                    “{side.quote}”
                  </p>
                </div>
              ))}
            </div>
            {finding.delta && (
              <p className="mt-2 text-[13px] font-medium text-warning">
                {finding.delta}
              </p>
            )}
          </div>
        )}

        <div className="grid gap-3 border-t border-line pt-3 text-[12.5px] sm:grid-cols-2">
          <div>
            <Label>SOURCE</Label>
            <p className="mt-0.5 text-ink">
              {sourceLine(
                finding.source.doc,
                finding.source.page,
                finding.source.section
              )}
            </p>
          </div>
          {finding.policy_basis && (
            <div>
              <Label>POLICY BASIS</Label>
              <p className="mt-0.5 text-ink">{finding.policy_basis}</p>
            </div>
          )}
        </div>

        {finding.comments.length > 0 && (
          <div className="space-y-2 border-t border-line pt-3">
            <Label>COMMENTS</Label>
            {finding.comments.map((entry, index) => (
              <div key={index} className="rounded bg-page px-3 py-2">
                <p className="text-[13px] leading-relaxed text-ink">
                  {entry.text}
                </p>
                <p className="mt-1 text-[12px] text-subtle">
                  {entry.author} · {new Date(entry.at).toLocaleString("en-PH")}
                </p>
              </div>
            ))}
          </div>
        )}

        {commenting && (
          <div className="space-y-2">
            <textarea
              className={cn(inputCls, "min-h-[72px]")}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a note for the committee"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={saveComment}
                disabled={busy}
                className="rounded bg-brand px-3 py-1.5 text-[12.5px] font-medium text-white hover:bg-navy disabled:opacity-60"
              >
                Save comment
              </button>
              <button
                onClick={() => setCommenting(false)}
                className="rounded border border-line px-3 py-1.5 text-[12.5px] hover:bg-page"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <footer className="space-y-3 border-t border-line bg-page px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <button
                onClick={saveEdit}
                disabled={busy}
                className="rounded bg-brand px-3 py-1.5 text-[12.5px] font-medium text-white hover:bg-navy disabled:opacity-60"
              >
                Save changes
              </button>
              <button
                onClick={() => {
                  setAnalysis(finding.analysis);
                  setRecommendation(finding.recommendation);
                  setEditing(false);
                }}
                className="rounded border border-line bg-white px-3 py-1.5 text-[12.5px] hover:bg-page"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1.5 rounded border border-line bg-white px-3 py-1.5 text-[12.5px] hover:bg-sky"
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit Analysis
              </button>
              <button
                onClick={() => setCommenting(true)}
                className="inline-flex items-center gap-1.5 rounded border border-line bg-white px-3 py-1.5 text-[12.5px] hover:bg-sky"
              >
                <MessageSquarePlus className="h-3.5 w-3.5" />
                Add Comment
              </button>

              <span className="mx-1 h-4 w-px bg-line" />

              {DECISIONS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => apply({ decision: value })}
                  disabled={busy}
                  className={cn(
                    "rounded border px-3 py-1.5 text-[12.5px] transition-colors disabled:opacity-60",
                    finding.decision === value
                      ? "border-brand bg-brand text-white"
                      : "border-line bg-white hover:bg-sky"
                  )}
                >
                  {label}
                </button>
              ))}
            </>
          )}
        </div>

        {finding.decision && finding.decided_by && (
          <p className="text-[12px] text-subtle">
            {DECISION_PAST[finding.decision]} by {finding.decided_by} on{" "}
            {new Date(finding.decided_at ?? "").toLocaleString("en-PH")}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-subtle">
          <span>Was this finding useful?</span>
          {FEEDBACK.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => apply({ feedback: value })}
              disabled={busy}
              className={cn(
                "rounded-full px-2 py-0.5 transition-colors disabled:opacity-60",
                finding.feedback === value
                  ? "bg-sky font-medium text-brand"
                  : "hover:bg-sky hover:text-brand"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </footer>
    </article>
  );
}
