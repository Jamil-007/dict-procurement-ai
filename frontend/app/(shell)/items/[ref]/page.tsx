"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { StatusPill, totalFindings } from "@/components/shell/status-pill";
import { OverviewTab } from "@/components/procurement-records/overview-tab";
import { DocumentsTab } from "@/components/procurement-records/documents-tab";
import { AiReviewTab } from "@/components/procurement-records/ai-review-tab";
import { ComplianceChecksTab } from "@/components/procurement-records/compliance-checks-tab";
import { FinalReportTab } from "@/components/procurement-records/final-report-tab";
import { FormsTab } from "@/components/procurement-records/forms-tab";
import { getProcurement } from "@/lib/records-client";
import { formatPeso } from "@/lib/format";
import type { Procurement, Severity } from "@/types/records";
import { cn } from "@/lib/utils";

// Compliance Checks sits beside AI Review rather than inside it: the two read
// the same documents and produce the same kind of finding, but one is an LLM
// opinion and the other is a deterministic rule and consistency engine. They
// run independently, and a re-run of either leaves the other's findings alone.
const TABS = [
  "Overview",
  "Documents",
  "AI Review",
  "Compliance Checks",
  "Forms",
  "Final Report",
] as const;
export type WorkspaceTab = (typeof TABS)[number];

/** Severities that mean a requirement was not met. See checkIssueTotal below. */
const CHECK_ISSUE_LEVELS: Severity[] = ["critical", "medium", "low"];

export default function WorkspacePage() {
  const { ref } = useParams<{ ref: string }>();
  const [procurement, setProcurement] = useState<Procurement | null>(null);
  const [tab, setTab] = useState<WorkspaceTab>("Overview");
  const [error, setError] = useState<string | null>(null);

  // Overview, Documents and Final Report all offer "Run AI Review", but the
  // review itself lives in the AI Review tab. They switch tabs and bump this
  // counter; the review tab watches it and starts a run.
  const [runRequest, setRunRequest] = useState(0);

  const requestReview = useCallback(() => {
    setTab("AI Review");
    setRunRequest((n) => n + 1);
  }, []);

  useEffect(() => {
    getProcurement(ref)
      .then(setProcurement)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Could not load this item")
      );
  }, [ref]);

  if (error) {
    return (
      <div className="px-7 py-10">
        <p className="text-[14px] text-critical">{error}</p>
        <Link href="/items" className="mt-2 inline-block text-[13px] text-brand underline">
          Back to Procurements
        </Link>
      </div>
    );
  }

  if (!procurement) {
    return <p className="px-7 py-10 text-[13px] text-subtle">Loading…</p>;
  }

  const findingTotal = totalFindings(procurement.finding_counts);

  // Deliberately not totalFindings: a checker run records a compliant finding
  // for every requirement it tested and passed, so the full total would badge
  // a clean packet with a large number. The badge counts what needs acting on.
  const checkIssueTotal = CHECK_ISSUE_LEVELS.reduce(
    (sum, level) => sum + (procurement.check_counts?.[level] ?? 0),
    0
  );

  return (
    <div className="w-full px-7 py-6 print:px-0 print:py-0">
      <div className="sticky top-0 z-10 -mx-7 -mt-6 bg-page px-7 pt-6 print:hidden">
        <Link
          href="/items"
          className="mb-4 inline-flex items-center gap-1.5 text-[12px] font-medium text-subtle hover:text-brand"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Procurements
        </Link>

        <h1 className="max-w-3xl text-[19px] font-bold leading-snug text-navy">
          {procurement.title}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px]">
          <span className="font-semibold tracking-wide text-brand">
            {procurement.ref}
          </span>
          <span className="font-semibold tabular-nums">
            {formatPeso(procurement.abc)}
          </span>
          <span className="text-subtle">{procurement.mode}</span>
          <StatusPill status={procurement.status} />
        </div>

        <nav className="mt-6 flex gap-7 overflow-x-auto border-b border-line">
          {TABS.map((name) => (
            <button
              key={name}
              onClick={() => setTab(name)}
              className={cn(
                "whitespace-nowrap border-b-2 pb-2.5 text-[13px] transition-colors",
                tab === name
                  ? "border-brand font-semibold text-navy"
                  : "border-transparent text-subtle hover:text-navy"
              )}
            >
              {name}
              {name === "AI Review" && procurement.review_status === "done" && (
                <span className="ml-1.5 text-[11px] font-normal text-subtle">
                  {findingTotal}
                </span>
              )}
              {name === "Compliance Checks" &&
                procurement.check_status === "done" && (
                  <span className="ml-1.5 text-[11px] font-normal text-subtle">
                    {checkIssueTotal}
                  </span>
                )}
            </button>
          ))}
        </nav>
      </div>

      <div className="mt-6">
        {tab === "Overview" && (
          <OverviewTab
            procurement={procurement}
            onChange={setProcurement}
            onRunReview={requestReview}
            onOpenReview={() => setTab("AI Review")}
          />
        )}
        {tab === "Documents" && (
          <DocumentsTab
            procurement={procurement}
            onChange={setProcurement}
            onRunReview={requestReview}
          />
        )}
        {tab === "AI Review" && (
          <AiReviewTab
            procurement={procurement}
            onProcurementChange={setProcurement}
            runRequest={runRequest}
            onGoToDocuments={() => setTab("Documents")}
          />
        )}
        {tab === "Compliance Checks" && (
          <ComplianceChecksTab
            procurement={procurement}
            onProcurementChange={setProcurement}
            onGoToDocuments={() => setTab("Documents")}
          />
        )}
        {tab === "Forms" && (
          <FormsTab procurement={procurement} onChange={setProcurement} />
        )}
        {tab === "Final Report" && (
          <FinalReportTab
            procurement={procurement}
            onChange={setProcurement}
            onGoToDocuments={() => setTab("Documents")}
            onGoToReview={() => setTab("AI Review")}
          />
        )}
      </div>
    </div>
  );
}
