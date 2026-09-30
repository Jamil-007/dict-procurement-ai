import type { Finding } from "@/types/records";

/** Bucket for cross-document findings (a comparison spanning 2+ documents), which
 *  don't belong to any single source document. */
export const CROSS_DOCUMENT = "Cross-document";

/**
 * Group findings by the document they pertain to, so a reviewer can check
 * findings document-by-document. A finding whose comparison spans more than one
 * document (data-integrity cross-checks) goes in the Cross-document group, which
 * always sorts last; the rest sort alphabetically by document name.
 */
export function groupByDocument(
  findings: Finding[]
): { doc: string; items: Finding[] }[] {
  const map = new Map<string, Finding[]>();
  for (const finding of findings) {
    const isCross = (finding.comparison?.length ?? 0) > 1;
    const doc = isCross ? CROSS_DOCUMENT : finding.source?.doc || "Unattributed";
    const bucket = map.get(doc) ?? [];
    bucket.push(finding);
    map.set(doc, bucket);
  }
  return [...map.entries()]
    .sort(([a], [b]) =>
      a === CROSS_DOCUMENT ? 1 : b === CROSS_DOCUMENT ? -1 : a.localeCompare(b)
    )
    .map(([doc, items]) => ({ doc, items }));
}
