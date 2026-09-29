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
      return `${stats!.failed} issue${stats!.failed === 1 ? '' : 's'}${
        stats!.high > 0 ? ` · ${stats!.high} critical` : ''
      }`;
    case 'clean':
      return `${stats!.passed} check${stats!.passed === 1 ? '' : 's'} passed${
        stats!.skipped > 0 ? ` · ${stats!.skipped} not verified` : ''
      }`;
    case 'not_verified':
      return 'Not verified';
    case 'not_applicable':
      return 'Not applicable';
  }
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
        <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-300">
          {info.task}
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-slate-400 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3">
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
