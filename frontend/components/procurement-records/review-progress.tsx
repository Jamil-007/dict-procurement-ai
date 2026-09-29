"use client";

import { useMemo } from "react";
import { FileText, Search, Sparkles } from "lucide-react";

import { SteppedProgress, type Step } from "./stepped-progress";
import type { Dimension } from "@/types/records";

/**
 * The checklist shown while an AI Review is in flight.
 *
 * The panel itself is in stepped-progress.tsx, shared with the Compliance
 * Checks tab. What lives here is what is specific to the review: the steps it
 * walks and how long each is expected to take.
 */

/** Rough cost of reading the documents, before any dimension runs. */
const INTAKE_MS = (documents: number) => 6_000 + 1_800 * documents;

/**
 * Rough cost of one dimension. The per-index offset keeps the steps from
 * ticking over on a metronome, which is the thing that reads as fake.
 */
const DIMENSION_MS = (documents: number, index: number) =>
  13_000 + 1_100 * documents + ((index * 2_800) % 7_000);

export function ReviewProgress({
  reference,
  documentCount,
  dimensions,
}: {
  reference: string;
  documentCount: number;
  dimensions: Dimension[];
}) {
  const steps = useMemo<Step[]>(
    () => [
      {
        label: "Documents analyzed",
        detail: `Processed and extracted text from ${documentCount} document${
          documentCount === 1 ? "" : "s"
        }.`,
        budget: INTAKE_MS(documentCount),
      },
      ...dimensions.map((dimension, index) => ({
        label: `${dimension.label} review`,
        detail: dimension.blurb,
        budget: DIMENSION_MS(documentCount, index),
      })),
    ],
    [dimensions, documentCount]
  );

  return (
    <SteppedProgress
      title="Reviewing procurement documents"
      subtitle={`Reading ${documentCount} document${
        documentCount === 1 ? "" : "s"
      } for ${reference}.`}
      steps={steps}
      icon={FileText}
      footerIcon={Search}
      footerNote="This usually takes a few minutes. Keep this page open."
      badgeIcon={Sparkles}
      badgeLabel="Processing with AI"
    />
  );
}
