"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CircleCheck,
  CircleSlash,
  GitCompareArrows,
  ListChecks,
  RefreshCw,
  ScrollText,
} from "lucide-react";
import { toast } from "sonner";

import { FindingCard } from "./finding-card";
import { ChecksProgress } from "./checks-progress";
import { Modal, ModalFooter } from "@/components/shell/modal";
import { btnGhost, btnPrimary } from "@/components/shell/page-header";
import {
  SEVERITY_BAR,
  SEVERITY_KEYS,
  severityLabel,
  severityMeaning,
} from "@/components/shell/status-pill";
import {
  listCheckers,
  listCheckFindings,
  runChecks,
} from "@/lib/records-client";
import type {
  CheckerInfo,
  CheckerOutcome,
  Finding,
  Procurement,
  Severity,
} from "@/types/records";
import { cn } from "@/lib/utils";

const SEVERITY_ORDER = SEVERITY_KEYS;

/**
 * A run produces a compliant finding for every requirement that passed, which
 * is the point — the BAC needs to see what was checked, not only what broke.
 * It also means the raw total is a poor headline, so the counts that lead are
 * the ones that need acting on.
 */
const ISSUE_SEVERITIES: Severity[] = ["critical", "medium", "low"];

const isIssue = (finding: Finding) => ISSUE_SEVERITIES.includes(finding.severity);

export function ComplianceChecksTab({
  procurement,
  onProcurementChange,
  onGoToDocuments,
}: {
  procurement: Procurement;
  onProcurementChange: (updated: Procurement) => void;
  onGoToDocuments: () => void;
}) {
  const [checkers, setCheckers] = useState<CheckerInfo[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [outcomes, setOutcomes] = useState<CheckerOutcome[]>([]);
  const [detected, setDetected] = useState<string[]>([]);
  const [active, setActive] = useState<string>("");
  const [showPassed, setShowPassed] = useState(false);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [confirmRerun, setConfirmRerun] = useState(false);

  // The checker list comes from the backend, which reads it from the rulepack
  // and profile YAML. A seventh checker appears here without a frontend change.
  useEffect(() => {
    Promise.all([listCheckers(), listCheckFindings(procurement.ref)])
      .then(([catalogue, existing]) => {
        setCheckers(catalogue);
        setFindings(existing);
      })
      .catch((err: unknown) =>
        toast.error(err instanceof Error ? err.message : "Could not load the checks")
      )
      .finally(() => setLoading(false));
  }, [procurement.ref]);

  /** A rejected finding is off the list, exactly as on the AI Review. */
  const live = useMemo(
    () => findings.filter((f) => f.decision !== "rejected"),
    [findings]
  );

  const counts = useMemo(() => {
    const out = Object.fromEntries(
      SEVERITY_KEYS.map((key) => [key, 0])
    ) as Record<Severity, number>;
    live.forEach((f) => (out[f.severity] += 1));
    return out;
  }, [live]);

  const issueCount = useMemo(() => live.filter(isIssue).length, [live]);

  // Findings carry the pack or profile id in `dimension`, which is the same
  // string as CheckerInfo.key — so the chips filter on it directly.
  const perChecker = useMemo(() => {
    const out: Record<string, number> = {};
    live.forEach((f) => (out[f.dimension] = (out[f.dimension] ?? 0) + 1));
    return out;
  }, [live]);

  const visible = useMemo(() => {
    const pool = showPassed ? live : live.filter(isIssue);
    const list = active ? pool.filter((f) => f.dimension === active) : pool;
    return [...list].sort(
      (a, b) =>
        SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
    );
  }, [live, active, showPassed]);

  const passedCount = live.length - issueCount;

  async function start() {
    if (procurement.documents.length === 0) {
      toast.warning("No documents to check", {
        description: "Upload documents first.",
      });
      return;
    }
    setRunning(true);
    onProcurementChange({ ...procurement, check_status: "processing" });
    try {
      const result = await runChecks(procurement.ref);
      setFindings(result.findings);
      setOutcomes(result.checkers);
      setDetected(result.detected_types);
      onProcurementChange({
        ...procurement,
        check_status: "done",
        check_counts: result.counts,
      });
      const failed = result.checkers.reduce((sum, c) => sum + c.failed, 0);
      toast.success("Compliance checks complete", {
        description:
          failed === 0
            ? "Every requirement that could be checked was met."
            : `${failed} requirement${failed === 1 ? "" : "s"} not met`,
      });
    } catch (err) {
      onProcurementChange({ ...procurement, check_status: "none" });
      toast.error(err instanceof Error ? err.message : "The checks did not finish");
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

  const labelFor = (key: string) =>
    checkers.find((c) => c.key === key)?.label ?? key.replace(/_/g, " ");

  if (loading) {
    return <p className="text-[13px] text-subtle">Loading checks…</p>;
  }

  // --- in progress ---
  if (running) {
    return (
      <ChecksProgress
        reference={procurement.ref}
        documentCount={procurement.documents.length}
        checkers={checkers}
      />
    );
  }

  // --- never run ---
  if (procurement.check_status !== "done") {
    return (
      <div className="space-y-5">
        <div className="rounded-xl border border-line bg-white px-6 py-14 text-center">
          <h2 className="text-[15px] font-semibold">
            No compliance checks have been run
          </h2>
          <p className="mx-auto mt-1 max-w-lg text-[13px] text-subtle">
            These are deterministic checks, not an AI opinion. They read the
            figures, dates, signatures and line items out of each document and
            test them against RA 12009, its IRR, the COA circulars and the GAM
            — and against each other, where two documents should agree.
          </p>
          {procurement.documents.length > 0 ? (
            <button onClick={() => void start()} className={`${btnPrimary} mt-5`}>
              Run Compliance Checks
            </button>
          ) : (
            <button onClick={onGoToDocuments} className={`${btnPrimary} mt-5`}>
              Go to Documents
            </button>
          )}
        </div>

        <CheckerCatalogue checkers={checkers} />
      </div>
    );
  }

  // --- results ---
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle">
            Compliance Checks
          </p>
          <h2 className="mt-1 text-[26px] font-bold leading-tight tracking-tight text-navy">
            {issueCount === 0
              ? "No requirement failed"
              : `${issueCount} requirement${issueCount === 1 ? "" : "s"} not met`}
          </h2>
          <p className="mt-1.5 text-[13px] text-subtle">
            {passedCount} other requirement{passedCount === 1 ? " was" : "s were"}{" "}
            checked and raised nothing.
          </p>
        </div>
        <div className="ml-auto shrink-0 pt-5">
          <button
            onClick={handleRun}
            className={`${btnGhost} flex items-center gap-1.5`}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Re-run
          </button>
        </div>
      </div>

      {detected.length > 0 && (
        <p className="text-[12.5px] text-subtle">
          Read as: {detected.join(", ")}. A document typed wrongly is checked
          against the wrong requirements — correct it on the Documents tab and
          run again.
        </p>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-line bg-sky/60 px-4 py-4">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white">
          <ListChecks className="h-4 w-4 text-brand" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-navy">
            Every citation below was retrieved from the reference library, not
            written by a model.
          </p>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-brand">
            Where a check names a provision that is not in the library, it says
            so rather than quoting one. “Not verified” means the check could not
            run — usually a field the document does not state — and is never the
            same as compliant. Findings can be accepted, rejected or commented
            on like any other; the accepted ones reach the final report.
          </p>
        </div>
      </div>

      {outcomes.length > 0 && <CheckerOutcomes outcomes={outcomes} />}

      {/* Same scale, same colours as the AI Review, so the two tabs read as
          one severity vocabulary. */}
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

      {checkers.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <CheckerChip
            label="All"
            count={live.length}
            activeChip={active === ""}
            onClick={() => setActive("")}
          />
          {checkers
            .filter((checker) => (perChecker[checker.key] ?? 0) > 0)
            .map((checker) => (
              <CheckerChip
                key={checker.key}
                label={checker.label}
                title={checker.blurb}
                count={perChecker[checker.key] ?? 0}
                activeChip={active === checker.key}
                onClick={() => setActive(checker.key)}
              />
            ))}
        </div>
      )}

      {passedCount > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-subtle">
          <span>
            {passedCount} requirement{passedCount === 1 ? " was" : "s were"}{" "}
            checked and met, or could not be verified.
          </span>
          <button
            onClick={() => setShowPassed((on) => !on)}
            className="font-semibold text-brand transition-colors hover:text-navy"
          >
            {showPassed ? "Hide them" : "Show them"}
          </button>
        </div>
      )}

      {visible.length === 0 && (
        <p className="rounded-xl border border-line bg-white px-6 py-10 text-center text-[13px] text-subtle">
          {live.length === 0
            ? "No checker was applicable to the uploaded documents."
            : active
              ? "Nothing raised by this checker."
              : "Nothing was raised — every requirement that could be checked was met."}
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
        title="Run the checks again"
        description={procurement.ref}
      >
        <div className="px-6 py-5 text-[13px] leading-relaxed">
          Running the checks again replaces the current findings, including any
          actions already recorded against them. The AI Review’s findings are
          left alone.
        </div>
        <ModalFooter
          submitLabel="Run checks again"
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

function CheckerChip({
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
      aria-pressed={activeChip}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-4 py-2 text-[13px] font-medium transition-colors",
        activeChip
          ? "border-navy bg-navy text-white"
          : "border-line bg-white text-ink hover:border-brand hover:text-brand"
      )}
    >
      {label}
      <span className={activeChip ? "text-white/70" : "text-subtle"}>
        ({count})
      </span>
    </button>
  );
}

const ENGINE_LABEL: Record<CheckerInfo["engine"], string> = {
  rule: "Checks one document against the rules",
  consistency: "Compares documents against each other",
};

/**
 * The six checkers, before anything has run.
 *
 * Shown on the empty state so the committee knows what the run will cover and
 * what it needs to upload for each — a checker that stays silent afterwards is
 * then recognisably one of these rather than an unexplained absence.
 */
function CheckerCatalogue({ checkers }: { checkers: CheckerInfo[] }) {
  if (checkers.length === 0) return null;

  return (
    <div className="rounded-xl border border-line bg-white">
      <div className="border-b border-line px-5 py-3.5">
        <p className="text-[13px] font-semibold text-navy">
          What gets checked
        </p>
        <p className="mt-0.5 text-[12.5px] text-subtle">
          Each one runs only when the documents it needs are attached.
        </p>
      </div>
      <ul className="divide-y divide-line">
        {checkers.map((checker) => (
          <li key={checker.key} className="px-5 py-4">
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
              {checker.engine === "rule" ? (
                <ScrollText className="h-3.5 w-3.5 shrink-0 text-brand" aria-hidden />
              ) : (
                <GitCompareArrows
                  className="h-3.5 w-3.5 shrink-0 text-brand"
                  aria-hidden
                />
              )}
              <p className="text-[13px] font-semibold text-ink">{checker.label}</p>
              <span
                title={ENGINE_LABEL[checker.engine]}
                className="rounded-full border border-line px-2 py-0.5 text-[10.5px] font-semibold tracking-wide text-subtle"
              >
                {checker.task}
              </span>
              {checker.owner && (
                <span className="text-[12px] text-subtle">{checker.owner}</span>
              )}
            </div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-subtle">
              {checker.blurb}
            </p>
            {checker.doc_types.length > 0 && (
              <p className="mt-1 text-[12px] text-subtle">
                Needs: {checker.doc_types.join(", ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * What each checker did, including the ones that did nothing.
 *
 * A checker reporting no findings is ambiguous on its own: it reads the same
 * whether it tested the documents and found them in order or never ran at all.
 * The committee is signing off on a procurement, so the difference has to be on
 * the page rather than inferred from an empty list.
 */
function CheckerOutcomes({ outcomes }: { outcomes: CheckerOutcome[] }) {
  const ran = outcomes.filter((o) => o.status === "ran");
  const skipped = outcomes.filter((o) => o.status === "skipped");

  return (
    <details className="group rounded-xl border border-line bg-white px-4 py-3" open>
      <summary className="cursor-pointer list-none text-[13px] font-semibold text-navy marker:hidden">
        Coverage — {ran.length} of {outcomes.length} checkers ran
        <span className="ml-1.5 font-normal text-subtle group-open:hidden">
          — show
        </span>
      </summary>

      <ul className="mt-3 space-y-3">
        {ran.map((outcome) => (
          <li key={outcome.key} className="flex gap-2.5">
            <CircleCheck
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sev-compliant"
              aria-hidden
            />
            <div className="min-w-0">
              <p className="text-[12.5px] font-semibold text-ink">
                {outcome.label}
                <span className="ml-1.5 font-normal text-subtle">
                  {outcome.task} · {outcome.owner}
                </span>
              </p>
              <p className="mt-0.5 flex flex-wrap gap-x-4 text-[12px] text-subtle">
                <span className={outcome.failed > 0 ? "font-semibold text-sev-critical" : ""}>
                  {outcome.failed} not met
                </span>
                <span>{outcome.passed} met</span>
                {outcome.not_verified > 0 && (
                  <span>{outcome.not_verified} could not be verified</span>
                )}
              </p>
            </div>
          </li>
        ))}

        {skipped.map((outcome) => (
          <li key={outcome.key} className="flex gap-2.5">
            <CircleSlash
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-subtle"
              aria-hidden
            />
            <div className="min-w-0">
              <p className="text-[12.5px] font-semibold text-subtle">
                {outcome.label}
                <span className="ml-1.5 font-normal">
                  {outcome.task} · did not run
                </span>
              </p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-subtle">
                {outcome.reason}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
