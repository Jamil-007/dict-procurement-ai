"use client";

import { useMemo } from "react";
import { ListChecks, ScanLine, ShieldCheck } from "lucide-react";

import { SteppedProgress, type Step } from "./stepped-progress";
import type { CheckerInfo } from "@/types/records";

/**
 * The checklist shown while the compliance checks are in flight.
 *
 * The steps are the pipeline the backend actually walks, in order, rather than
 * one step per checker: the six checkers run in two parallel graph nodes and
 * finish together, so listing them individually would be inventing a sequence
 * that does not exist. What does take real, visibly different amounts of time
 * is reading the documents, pulling the facts out of them, and testing those
 * facts — so those are the steps.
 *
 * Reading dominates. Every DICT procurement document is a scan, so each page
 * goes through vision OCR on the first run; a second run over an unchanged
 * packet hits the cache and is far quicker than the estimate here.
 */

const READ_MS = (documents: number) => 8_000 + 14_000 * documents;
const EXTRACT_MS = (documents: number) => 6_000 + 5_000 * documents;

export function ChecksProgress({
  reference,
  documentCount,
  checkers,
}: {
  reference: string;
  documentCount: number;
  checkers: CheckerInfo[];
}) {
  const ruleCount = checkers.filter((c) => c.engine === "rule").length;
  const consistencyCount = checkers.length - ruleCount;

  const steps = useMemo<Step[]>(
    () => [
      {
        label: "Documents read",
        detail: `Reading ${documentCount} document${
          documentCount === 1 ? "" : "s"
        }. Scanned pages go through OCR, which is most of the wait.`,
        budget: READ_MS(documentCount),
      },
      {
        label: "Figures and dates extracted",
        detail:
          "Amounts, quantities, line items, signatures and dates pulled out of each document, each one anchored to the page it came from.",
        budget: EXTRACT_MS(documentCount),
      },
      {
        label: "Checkers selected",
        detail:
          "Working out which checks the uploaded document types can support. A check with nothing to read is reported as skipped, never as passed.",
        budget: 2_500,
      },
      {
        label: "Requirements tested",
        detail: `${ruleCount} rule check${
          ruleCount === 1 ? "" : "s"
        } over single documents, ${consistencyCount} consistency check${
          consistencyCount === 1 ? "" : "s"
        } comparing documents against each other.`,
        budget: 9_000,
      },
      {
        label: "Citations retrieved",
        detail:
          "Each finding matched to the provision it rests on, quoted from the reference library rather than written by a model.",
        budget: 7_000,
      },
    ],
    [documentCount, ruleCount, consistencyCount]
  );

  return (
    <SteppedProgress
      title="Running compliance checks"
      subtitle={`Checking ${documentCount} document${
        documentCount === 1 ? "" : "s"
      } for ${reference}.`}
      steps={steps}
      icon={ScanLine}
      footerIcon={ListChecks}
      footerNote="Reading scanned pages is the slow part. Keep this page open."
      badgeIcon={ShieldCheck}
      badgeLabel="Rule and consistency engines"
    />
  );
}
