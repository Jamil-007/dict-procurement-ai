"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Check, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { FindingCard } from "./finding-card";
import { Modal, ModalFooter } from "@/components/shell/modal";
import { btnGhost, btnPrimary } from "@/components/shell/page-header";
import { severityLabel } from "@/components/shell/status-pill";
import { listDimensions, listFindings, runReview } from "@/lib/records-client";
import type {
  Dimension,
  DimensionOutcome,
  Finding,
  Procurement,
  Severity,
} from "@/types/records";
import { cn } from "@/lib/utils";

const SEVERITY_ORDER: Severity[] = ["critical", "warning", "compliant"];

/** Roughly how long each step is left on screen while the run is in flight. */
const STEP_MS = 620;

export function AiReviewTab({
  procurement,
  onProcurementChange,
  runRequest,
  onGoToDocuments,
}: {
  procurement: Procurement;
  onProcurementChange: (updated: Procurement) => void;
  runRequest: number;
  onGoToDocuments: () => void;
}) {
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [outcomes, setOutcomes] = useState<DimensionOutcome[]>([]);
  const [active, setActive] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [confirmRerun, setConfirmRerun] = useState(false);

  // The dimension list comes from the backend registry, so a new dimension
  // appears here without a frontend change.
  useEffect(() => {
    Promise.all([listDimensions(), listFindings(procurement.ref)])
      .then(([dims, existing]) => {
        setDimensions(dims);
        setFindings(existing);
      })
      .catch((err: unknown) =>
        toast.error(err instanceof Error ? err.message : "Could not load the review")
      )
      .finally(() => setLoading(false));
  }, [procurement.ref]);

  const steps = useMemo(
    () => ["Documents analyzed", ...dimensions.map((d) => `${d.label} review`)],
    [dimensions]
  );

  // Walks the checklist while the request is in flight. It is a progress
  // indicator, not a report of which dimension the backend is on — the run
  // returns all dimensions at once.
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(
      () => setStep((current) => Math.min(current + 1, steps.length)),
      STEP_MS
    );
    return () => clearInterval(timer);
  }, [running, steps.length]);

  const counts = useMemo(() => {
    const out: Record<Severity, number> = { critical: 0, warning: 0, compliant: 0 };
    findings.forEach((f) => (out[f.severity] += 1));
    return out;
  }, [findings]);

  const perDimension = useMemo(() => {
    const out: Record<string, number> = {};
    findings.forEach((f) => (out[f.dimension] = (out[f.dimension] ?? 0) + 1));
    return out;
  }, [findings]);

  const visible = useMemo(() => {
    const list = active ? findings.filter((f) => f.dimension === active) : findings;
    return [...list].sort(
      (a, b) =>
        SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
    );
  }, [findings, active]);

  async function start() {
    if (procurement.documents.length === 0) {
      toast.warning("No documents to review", {
        description: "Upload documents first.",
      });
      return;
    }
    setRunning(true);
    setStep(0);
    onProcurementChange({ ...procurement, review_status: "processing" });
    try {
      const result = await runReview(procurement.ref);
      setFindings(result.findings);
      setOutcomes(result.dimensions);
      onProcurementChange({
        ...procurement,
        review_status: "done",
        finding_counts: result.counts,
        decided_count: 0,
      });
      toast.success("AI Review complete", {
        description: `${result.findings.length} findings identified`,
      });
    } catch (err) {
      onProcurementChange({ ...procurement, review_status: "none" });
      toast.error(err instanceof Error ? err.message : "The review did not finish");
    } finally {
      setRunning(false);
    }
  }

  function handleRun() {
    if (findings.length > 0) {
      setConfirmRerun(true);
      return;
    }
    void start();
  }

  // A sibling tab asked for a run. Ignore the initial render.
  const lastRequest = useRef(runRequest);
  useEffect(() => {
    if (runRequest === lastRequest.current) return;
    lastRequest.current = runRequest;
    handleRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runRequest]);

  const unavailable = outcomes.filter((o) => o.status !== "ok");
  const decided = findings.filter((f) => f.decision).length;

  if (loading) {
    return <p className="text-[13px] text-subtle">Loading review…</p>;
  }

  // --- in progress ---
  if (running) {
    return (
      <div className="max-w-xl rounded-xl border border-line bg-white px-6 py-8 sm:px-8">
        <h2 className="text-[16px] font-semibold text-navy">
          Reviewing Procurement Documents
        </h2>
        <p className="mb-6 mt-1 text-[13px] text-subtle">
          Reading {procurement.documents.length} document
          {procurement.documents.length === 1 ? "" : "s"} for {procurement.ref}.
        </p>
        <ul className="space-y-3.5">
          {steps.map((label, index) => {
            const state =
              index < step ? "done" : index === step ? "active" : "idle";
            return (
              <li
                key={label}
                className={cn(
                  "flex items-center gap-3 text-[13px]",
                  state === "idle"
                    ? "text-subtle"
                    : state === "active"
                      ? "font-semibold text-navy"
                      : "text-ink"
                )}
              >
                <span className="grid w-4 place-items-center">
                  {state === "done" ? (
                    <Check className="h-4 w-4 text-compliant" />
                  ) : state === "active" ? (
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand border-t-transparent" />
                  ) : (
                    <span className="h-3.5 w-3.5 rounded-full border border-line" />
                  )}
                </span>
                {label}
              </li>
            );
          })}
        </ul>
        <p className="mt-6 text-[12.5px] text-subtle">
          {step >= steps.length ? "Consolidating findings…" : "Analyzing…"}
        </p>
      </div>
    );
  }

  // --- never run ---
  if (procurement.review_status !== "done") {
    return (
      <>
        <div className="rounded-xl border border-line bg-white px-6 py-16 text-center">
          <h2 className="text-[15px] font-semibold">No AI review has been run</h2>
          <p className="mx-auto mt-1 max-w-md text-[13px] text-subtle">
            The review examines the uploaded documents across compliance,
            consistency, quality, market and risk, and lists findings for the
            BAC to verify.
          </p>
          {procurement.documents.length > 0 ? (
            <button onClick={() => void start()} className={`${btnPrimary} mt-5`}>
              Run AI Review
            </button>
          ) : (
            <button onClick={onGoToDocuments} className={`${btnPrimary} mt-5`}>
              Go to Documents
            </button>
          )}
        </div>

        {unavailable.length > 0 && (
          <UnavailableNotice outcomes={unavailable} />
        )}
      </>
    );
  }

  // --- results ---
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h2 className="text-[16px] font-semibold text-navy">AI Review</h2>
          <p className="mt-1 text-[13px] text-subtle">
            <span className="font-semibold text-ink">
              {findings.length} finding{findings.length === 1 ? "" : "s"} identified
            </span>
            {SEVERITY_ORDER.filter((key) => counts[key]).map((key) => (
              <span key={key}>
                {" · "}
                {counts[key]} {severityLabel(key).toLowerCase()}
              </span>
            ))}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[12px] text-subtle">
            {decided} of {findings.length} acted on
          </span>
          <button
            onClick={handleRun}
            className={`${btnGhost} flex items-center gap-1.5`}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Re-run
          </button>
        </div>
      </div>

      {unavailable.length > 0 && <UnavailableNotice outcomes={unavailable} />}

      {dimensions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <DimensionChip
            label="All"
            count={findings.length}
            activeChip={active === ""}
            onClick={() => setActive("")}
          />
          {dimensions.map((dimension) => (
            <DimensionChip
              key={dimension.key}
              label={dimension.label}
              title={dimension.blurb}
              count={perDimension[dimension.key] ?? 0}
              activeChip={active === dimension.key}
              onClick={() => setActive(dimension.key)}
            />
          ))}
        </div>
      )}

      {visible.length === 0 && (
        <p className="rounded-xl border border-line bg-white px-6 py-10 text-center text-[13px] text-subtle">
          {findings.length === 0
            ? "The review completed without raising anything for the committee to verify."
            : "Nothing raised under this dimension."}
        </p>
      )}

      <div className="space-y-3">
        {visible.map((finding) => (
          <FindingCard
            key={finding.id}
            finding={finding}
            onChange={(updated) =>
              setFindings((prev) =>
                prev.map((f) => (f.id === updated.id ? updated : f))
              )
            }
          />
        ))}
      </div>

      <Modal
        open={confirmRerun}
        onClose={() => setConfirmRerun(false)}
        title="Run the review again"
        description={procurement.ref}
      >
        <div className="px-6 py-5 text-[13px] leading-relaxed">
          Running the review again replaces the current findings, including the{" "}
          {decided} action{decided === 1 ? "" : "s"} already recorded against
          them.
        </div>
        <ModalFooter
          submitLabel="Run AI Review again"
          tone="danger"
          onCancel={() => setConfirmRerun(false)}
          onSubmit={() => {
            setConfirmRerun(false);
            void start();
          }}
        />
      </Modal>
    </div>
  );
}

function DimensionChip({
  label,
  count,
  activeChip,
  title,
  onClick,
}: {
  label: string;
  count: number;
  activeChip: boolean;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        "whitespace-nowrap rounded-full border px-3.5 py-1.5 text-[12px] font-medium transition-colors",
        activeChip
          ? "border-navy bg-navy text-white"
          : "border-line bg-white text-subtle hover:border-brand hover:text-brand"
      )}
    >
      {label}
      <span className={cn("ml-1.5", activeChip ? "text-white/60" : "text-subtle/60")}>
        {count}
      </span>
    </button>
  );
}

function UnavailableNotice({ outcomes }: { outcomes: DimensionOutcome[] }) {
  return (
    <div className="flex gap-2.5 rounded-xl border border-warning/30 bg-warning/5 px-4 py-3">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
      <div className="text-[13px] text-ink">
        <p className="font-medium">
          Some dimensions could not be completed in this run.
        </p>
        <p className="mt-0.5 text-subtle">
          {outcomes.map((o) => o.label).join(", ")} returned no results. The rest
          of the review is unaffected — run it again to retry.
        </p>
      </div>
    </div>
  );
}
