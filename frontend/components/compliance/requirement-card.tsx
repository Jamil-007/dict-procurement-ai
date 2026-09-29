'use client';

import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  MinusCircle,
} from 'lucide-react';
import { FindingDetailCard } from '@/components/procurement/finding-detail';
import { cn } from '@/lib/utils';
import type { RequirementInfo } from '@/lib/requirements';
import type { FindingDetail, TaskStats } from '@/types/procurement';

/** One assigned requirement, rendered as an expandable row. */

interface RequirementCardProps {
  info: RequirementInfo;
  /** Per-task counts from the verdict; undefined until a review has run. */
  stats?: TaskStats;
  findings: FindingDetail[];
  /** Whether the checker node covering this task was routed at all. */
  checkerRan: boolean;
  hasVerdict: boolean;
}

type Status =
  | 'ready'
  | 'issues'
  | 'clean'
  | 'not_verified'
  | 'not_applicable';

function deriveStatus(
  hasVerdict: boolean,
  checkerRan: boolean,
  stats?: TaskStats
): Status {
  if (!hasVerdict) return 'ready';
  if (!stats || stats.total === 0) return 'not_applicable';
  if (stats.failed > 0) return 'issues';
  if (stats.passed > 0) return 'clean';
  return 'not_verified';
}

function statusIcon(status: Status) {
  switch (status) {
    case 'ready':
      return <CircleDashed className="h-5 w-5 text-slate-300" />;
    case 'issues':
      return <AlertTriangle className="h-5 w-5 text-red-500" />;
    case 'clean':
      return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
    case 'not_verified':
      return <MinusCircle className="h-5 w-5 text-amber-500" />;
    case 'not_applicable':
      return <MinusCircle className="h-5 w-5 text-slate-300" />;
  }
}

function statusText(status: Status, stats?: TaskStats): string {
  switch (status) {
    case 'ready':
      return 'Waiting for documents';
    case 'issues':
      return `Found ${stats!.failed} problem${
        stats!.failed === 1 ? '' : 's'
      } out of ${stats!.total} checks`;
    case 'clean':
      return stats!.skipped > 0
        ? `All ${stats!.passed} checks passed · ${stats!.skipped} could not be confirmed`
        : `All ${stats!.passed} checks passed — no problems found`;
    case 'not_verified':
      return 'Ran, but the documents did not contain the data needed to confirm';
    case 'not_applicable':
      return 'Skipped — none of the uploaded documents are the kind this check reviews';
  }
}

/** Count badges shown on the row header once a review has run. */
function StatusBadges({ status, stats }: { status: Status; stats?: TaskStats }) {
  if (status === 'ready') return null;
  const badges: { label: string; className: string }[] = [];
  if (status === 'not_applicable') {
    badges.push({
      label: 'Not applicable',
      className: 'bg-gray-100 text-gray-500',
    });
  } else if (stats) {
    if (stats.failed > 0)
      badges.push({
        label: `${stats.failed} issue${stats.failed === 1 ? '' : 's'}`,
        className: 'bg-red-100 text-red-700',
      });
    if (stats.high > 0)
      badges.push({ label: `${stats.high} critical`, className: 'bg-black text-white' });
    if (stats.passed > 0)
      badges.push({
        label: `${stats.passed} passed`,
        className: 'bg-emerald-100 text-emerald-700',
      });
    if (stats.skipped > 0)
      badges.push({
        label: `${stats.skipped} not verified`,
        className: 'bg-amber-100 text-amber-800',
      });
  }
  if (!badges.length) return null;
  return (
    <span className="hidden shrink-0 items-center gap-1 sm:flex">
      {badges.map((b) => (
        <span
          key={b.label}
          className={cn(
            'whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold',
            b.className
          )}
        >
          {b.label}
        </span>
      ))}
    </span>
  );
}

export function RequirementCard({
  info,
  stats,
  findings,
  checkerRan,
  hasVerdict,
}: RequirementCardProps) {
  const [open, setOpen] = useState(false);
  const status = deriveStatus(hasVerdict, checkerRan, stats);

  // Rows with issues open themselves when a verdict lands.
  useEffect(() => {
    if (hasVerdict && (stats?.failed ?? 0) > 0) setOpen(true);
  }, [hasVerdict, stats?.failed]);

  return (
    <div
      className={cn(
        'rounded-lg border bg-white transition-colors',
        status === 'issues'
          ? 'border-red-200'
          : status === 'clean'
          ? 'border-emerald-200'
          : 'border-gray-200 hover:border-gray-300'
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className="shrink-0">{statusIcon(status)}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">
            {info.name}
          </span>
          <span
            className={cn(
              'block text-xs',
              status === 'issues'
                ? 'text-red-600'
                : status === 'clean'
                ? 'text-emerald-600'
                : 'text-slate-400'
            )}
          >
            {statusText(status, stats)}
          </span>
        </span>
        <StatusBadges status={status} stats={stats} />
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-slate-400 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3">
          {status === 'not_applicable' && (
            <div className="rounded-lg bg-gray-50 px-3 py-2.5 text-xs text-gray-600">
              <p className="font-semibold text-gray-700">
                Why was this skipped?
              </p>
              <p className="mt-1">
                This check only applies to certain document types, and none of
                the files you uploaded match them. To run it, include:{' '}
                {info.documents.join(', ')}.
              </p>
            </div>
          )}

          {status === 'clean' && findings.length === 0 && (
            <div className="rounded-lg bg-emerald-50 px-3 py-2.5 text-xs text-emerald-800">
              Everything this check looks for was present and correct in your
              documents.
            </div>
          )}

          {status === 'not_verified' && (
            <div className="rounded-lg bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
              The check ran, but the uploaded documents did not contain the
              data it needs to confirm a pass or a fail. This is not a
              failure — it just could not be verified.
            </div>
          )}

          {findings.map((finding, i) => (
            <FindingDetailCard key={`${finding.rule_id}-${i}`} finding={finding} />
          ))}

          <dl className="space-y-2 text-xs text-slate-500">
            <div>
              <dt className="font-semibold text-slate-700">What it checks</dt>
              <dd>{info.description}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-700">Owner</dt>
              <dd>{info.owner}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-700">Documents</dt>
              <dd className="mt-1 flex flex-wrap gap-1">
                {info.documents.map((doc) => (
                  <span
                    key={doc}
                    className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"
                  >
                    {doc}
                  </span>
                ))}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-700">Legal basis</dt>
              <dd className="mt-1 space-y-1">
                {info.authorities.map((a) => (
                  <span key={a} className="block text-slate-600">
                    {a}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
