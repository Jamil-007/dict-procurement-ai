"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BarChart3,
  FileText,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Briefcase,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";

import { FindingCard } from "./finding-card";
import { ReviewProgress } from "./review-progress";
import { Modal, ModalFooter } from "@/components/shell/modal";
import { btnGhost, btnPrimary } from "@/components/shell/page-header";
import {
  SEVERITY_BAR,
  SEVERITY_KEYS,
  severityLabel,
  severityMeaning,
} from "@/components/shell/status-pill";
import { listDimensions, listFindings, runReview } from "@/lib/records-client";
import type {
  Dimension,
  DimensionOutcome,
  Finding,
  Procurement,
  Severity,
} from "@/types/records";
import { cn } from "@/lib/utils";

const SEVERITY_ORDER = SEVERITY_KEYS;

/**
 * Chip icons, keyed by the registry's dimension key. A dimension with no entry
 * simply gets a text-only chip, so adding one to the backend never breaks here.
 */
const DIMENSION_ICONS: Record<string, LucideIcon> = {
  compliance: AlertTriangle,
  document_consistency: FileText,
  document_quality: ShieldCheck,
  procurement_market: BarChart3,
  requirements_risk: Briefcase,
};

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

  const counts = useMemo(() => {
    const out = Object.fromEntries(
      SEVERITY_KEYS.map((key) => [key, 0])
    ) as Record<Severity, number>;
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
  const activeDimension = dimensions.find((d) => d.key === active);

  // Findings carry a dimension key; the card shows the registry's label for it.
  const labelFor = (key: string) =>
    dimensions.find((d) => d.key === key)?.label ?? key.replace(/_/g, " ");

  if (loading) {
    return <p className="text-[13px] text-subtle">Loading review…</p>;
  }

  // --- in progress ---
  if (running) {
    return (
      <ReviewProgress
        reference={procurement.ref}
        documentCount={procurement.documents.length}
        dimensions={dimensions}
      />
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
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle">
            AI Review
          </p>
          <h2 className="mt-1 text-[26px] font-bold leading-tight tracking-tight text-navy">
            {findings.length} finding{findings.length === 1 ? "" : "s"} identified
          </h2>
          <p className="mt-1.5 text-[13px] text-subtle">
            Issues, risks, and areas for improvement identified across your
            procurement documents.
          </p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-3 pt-5">
          <span className="text-[13px] text-subtle">
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

      <div className="flex items-start gap-3 rounded-xl border border-line bg-sky/60 px-4 py-4">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white">
          <Sparkles className="h-4 w-4 text-brand" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-navy">
            These findings come from an AI review of the uploaded documents.
          </p>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-brand">
            They flag potential issues, compliance gaps and recommendations
            against RA 12009, its IRR and related issuances. Every finding can be
            edited, commented on, accepted, modified or rejected — the BAC
            decides.
          </p>
        </div>
      </div>

      {/* Severity legend. The dot colour here is the same fill as the bar down
          the left edge of each card, so the two read as one scale. */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {SEVERITY_KEYS.map((key) => (
          <span
            key={key}
            title={severityMeaning(key)}
            className="inline-flex items-center gap-1.5 text-[12.5px]"
          >
            <span className={cn("h-2 w-2 rounded-full", SEVERITY_BAR[key])} />
            <span className="font-medium text-ink">{severityLabel(key)}</span>
            <span className="text-subtle">({counts[key]})</span>
          </span>
        ))}
      </div>

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
              icon={DIMENSION_ICONS[dimension.key]}
              count={perDimension[dimension.key] ?? 0}
              activeChip={active === dimension.key}
              onClick={() => setActive(dimension.key)}
            />
          ))}
        </div>
      )}

      {activeDimension && (
        <p className="text-[12.5px] text-subtle">{activeDimension.blurb}</p>
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
            dimensionLabel={labelFor(finding.dimension)}
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
  icon: Icon,
  onClick,
}: {
  label: string;
  count: number;
  activeChip: boolean;
  title?: string;
  icon?: LucideIcon;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-pressed={activeChip}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-4 py-2 text-[13px] font-medium transition-colors",
        activeChip
          ? "border-navy bg-navy text-white"
          : "border-line bg-white text-ink hover:border-brand hover:text-brand"
      )}
    >
      {Icon && <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />}
      {label}
      <span className={activeChip ? "text-white/70" : "text-subtle"}>
        ({count})
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
