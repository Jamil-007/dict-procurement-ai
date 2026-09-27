'use client';

import React, { useState } from 'react';
import { BookOpen, ChevronDown, FileWarning, MapPin } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { Comparison, FindingDetail } from '@/types/procurement';

/**
 * One finding, rendered so a reviewer can act on it without opening the
 * source documents first.
 *
 * Three things have to be visible: what is wrong, where it was seen, and
 * what says so. A finding shown as a bare sentence is an assertion — the
 * reviewer has no way to check it and no way to defend it to an auditor.
 */

const ACTION_LABELS: Record<string, string> = {
  amendment_to_order: 'Requires an Amendment to Order',
  variation_order: 'Requires a Variation Order',
};

function severityClass(severity: string): string {
  switch (severity) {
    case 'high':
      return 'bg-black text-white border-black';
    case 'medium':
      return 'bg-gray-700 text-white border-gray-700';
    case 'low':
      return 'bg-gray-300 text-black border-gray-300';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

/** The retrieved legal provision, with its verbatim text on demand. */
function AuthorityChip({
  authority,
}: {
  authority: NonNullable<FindingDetail['authority']>;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasText = Boolean(authority.quoted_text);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => hasText && setExpanded((v) => !v)}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1',
          'text-xs text-left transition-colors',
          authority.unverified
            ? 'border-amber-300 bg-amber-50 text-amber-900'
            : 'border-gray-300 bg-gray-50 text-gray-800 hover:bg-gray-100',
          !hasText && 'cursor-default'
        )}
      >
        {authority.unverified ? (
          <FileWarning className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <BookOpen className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="break-words">{authority.citation}</span>
        {hasText && (
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 shrink-0 transition-transform',
              expanded && 'rotate-180'
            )}
          />
        )}
      </button>

      {/* A named provision that is not in the indexed corpus is reported as
          unverified rather than quietly swapped for a nearby one. */}
      {authority.unverified && (
        <p className="mt-1 text-xs text-amber-800">
          This provision is not in the indexed corpus — the citation has not
          been verified against source text.
        </p>
      )}

      {expanded && authority.quoted_text && (
        <blockquote className="mt-2 border-l-2 border-gray-300 bg-gray-50 px-3 py-2 text-xs italic text-gray-700">
          {authority.quoted_text}
          {authority.page ? (
            <span className="ml-1 not-italic text-gray-500">
              (p. {authority.page})
            </span>
          ) : null}
        </blockquote>
      )}
    </div>
  );
}

/** Where the finding was observed: document, page, field. */
function EvidenceChips({ evidence }: { evidence: FindingDetail['evidence'] }) {
  if (!evidence?.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {evidence.map((e, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-700"
        >
          <MapPin className="h-3 w-3 shrink-0 text-gray-500" />
          <span className="break-all">
            {e.document || 'document'}
            {e.page ? `, p. ${e.page}` : ''}
            {e.field ? ` · ${e.field}` : ''}
          </span>
        </span>
      ))}
    </div>
  );
}

/**
 * The two sides of a cross-document disagreement, side by side.
 *
 * The reference row is the document the others are measured against — the
 * contract for a payment check, the delivery receipt for a receiving check,
 * the TOR for a planning check. Showing it inline is what turns "these
 * disagree" into something a reviewer can reconcile.
 */
function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const rows = comparison.rows ?? [];
  if (!rows.length) return null;

  // Line items are the one shape where the reference value changes per row,
  // so it gets a column of its own instead of a single header row.
  const perRowReference = comparison.kind === 'line_items';

  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-left text-xs">
        <thead className="bg-gray-50 text-gray-600">
          <tr>
            {perRowReference && <th className="px-3 py-2 font-medium">Item</th>}
            {perRowReference && (
              <th className="px-3 py-2 font-medium">
                {comparison.reference?.document ?? 'Reference'}
              </th>
            )}
            <th className="px-3 py-2 font-medium">Document</th>
            <th className="px-3 py-2 font-medium">Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {!perRowReference && comparison.reference && (
            <tr className="bg-gray-50/60">
              <td className="px-3 py-2 font-medium text-black">
                {comparison.reference.document}
                <span className="ml-1 text-[10px] uppercase tracking-wide text-gray-500">
                  reference
                </span>
              </td>
              <td className="px-3 py-2 text-gray-800">
                {comparison.reference.value ?? comparison.reference.detail ?? '—'}
              </td>
            </tr>
          )}
          {rows.map((row, i) => (
            <tr key={i}>
              {perRowReference && (
                <td className="px-3 py-2 text-gray-700">{row.item ?? '—'}</td>
              )}
              {perRowReference && (
                <td className="px-3 py-2 text-gray-700">
                  {row.reference_value || '—'}
                </td>
              )}
              <td className="px-3 py-2 text-gray-700">
                {/* Coverage rows describe a missing line rather than a
                    document's value, so they carry no document name. */}
                {row.document || '—'}
                {row.page ? (
                  <span className="text-gray-400"> · p. {row.page}</span>
                ) : null}
              </td>
              <td className="px-3 py-2 font-medium text-black">
                {row.value || row.detail || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FindingDetailCard({ finding }: { finding: FindingDetail }) {
  return (
    <div className="rounded-xl border border-gray-200 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <Badge
          variant="outline"
          className={cn('rounded-full text-[10px]', severityClass(finding.severity))}
        >
          {finding.severity.toUpperCase()}
        </Badge>
        {finding.task && (
          <Badge
            variant="outline"
            className="rounded-full border-gray-300 text-[10px] text-gray-600"
          >
            {finding.task}
          </Badge>
        )}
        {finding.action_hint && (
          <Badge
            variant="outline"
            className="rounded-full border-gray-800 text-[10px] text-gray-900"
          >
            {ACTION_LABELS[finding.action_hint] ?? finding.action_hint}
          </Badge>
        )}
        {finding.title && (
          <span className="text-sm font-medium text-black">{finding.title}</span>
        )}
      </div>

      {finding.detail && (
        <p className="mt-2 break-words text-sm text-gray-700">{finding.detail}</p>
      )}

      {finding.comparison && <ComparisonTable comparison={finding.comparison} />}
      <EvidenceChips evidence={finding.evidence} />
      {finding.authority && <AuthorityChip authority={finding.authority} />}
    </div>
  );
}
