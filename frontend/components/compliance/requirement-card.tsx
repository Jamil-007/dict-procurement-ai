'use client';

import React, { useState } from 'react';
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

/** One assigned requirement: what it is, and what the last run found. */

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
  if (!stats || stats.total === 0) {
    return checkerRan ? 'not_applicable' : 'not_applicable';
  }
  if (stats.failed > 0) return 'issues';
  if (stats.passed > 0) return 'clean';
  return 'not_verified';
}

function StatusPill({ status, stats }: { status: Status; stats?: TaskStats }) {
  const base =
    'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium ring-1 ring-inset';
  switch (status) {
    case 'ready':
      return (
        <span className={cn(base, 'bg-slate-50 text-slate-500 ring-slate-200')}>
          <CircleDashed className="h-3.5 w-3.5" />
          Awaiting documents
        </span>
      );
    case 'issues':
      return (
        <span className={cn(base, 'bg-red-50 text-red-700 ring-red-200')}>
          <AlertTriangle className="h-3.5 w-3.5" />
          {stats!.failed} issue{stats!.failed === 1 ? '' : 's'} found
          {stats!.high > 0 ? ` · ${stats!.high} critical` : ''}
        </span>
      );
    case 'clean':
      return (
        <span
          className={cn(base, 'bg-emerald-50 text-emerald-700 ring-emerald-200')}
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          All {stats!.passed} check{stats!.passed === 1 ? '' : 's'} passed
          {stats!.skipped > 0 ? ` · ${stats!.skipped} not verified` : ''}
        </span>
      );
    case 'not_verified':
      return (
        <span className={cn(base, 'bg-amber-50 text-amber-700 ring-amber-200')}>
          <MinusCircle className="h-3.5 w-3.5" />
          Could not be verified
        </span>
      );
    case 'not_applicable':
      return (
        <span className={cn(base, 'bg-slate-50 text-slate-400 ring-slate-200')}>
          <MinusCircle className="h-3.5 w-3.5" />
          Not applicable to this upload
        </span>
      );
  }
}

export function RequirementCard({
  info,
  stats,
  findings,
  checkerRan,
  hasVerdict,
}: RequirementCardProps) {
  const [showFindings, setShowFindings] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const status = deriveStatus(hasVerdict, checkerRan, stats);

  return (
    <div
      className={cn(
        'group flex flex-col rounded-2xl bg-white p-5 ring-1 transition-all hover:shadow-lg hover:shadow-slate-200/60',
        status === 'issues'
          ? 'ring-red-200'
          : status === 'clean'
          ? 'ring-emerald-200'
          : 'ring-slate-200 hover:ring-slate-300'
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          {info.task} · {info.category}
        </p>
        <span className="shrink-0 text-[11px] text-slate-400">
          {info.owner}
        </span>
      </div>
      <h3 className="mt-1.5 text-[15px] font-semibold leading-snug text-slate-900">
        {info.name}
      </h3>

      <p className="mt-2.5 text-sm leading-relaxed text-slate-500">
        {info.description}
      </p>

      <div className="mt-4 flex items-center justify-between gap-2">
        <StatusPill status={status} stats={stats} />
        <span className="text-[11px] text-slate-400">{info.stage}</span>
      </div>

      {findings.length > 0 && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setShowFindings((v) => !v)}
            className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100"
          >
            <span>
              {findings.length} finding{findings.length === 1 ? '' : 's'}
            </span>
            <ChevronDown
              className={cn(
                'h-4 w-4 text-slate-400 transition-transform',
                showFindings && 'rotate-180'
              )}
            />
          </button>
          {showFindings && (
            <div className="mt-3 space-y-3">
              {findings.map((finding, i) => (
                <FindingDetailCard key={`${finding.rule_id}-${i}`} finding={finding} />
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 border-t border-slate-100 pt-3">
        <button
          type="button"
          onClick={() => setShowDetails((v) => !v)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 transition-colors hover:text-slate-700"
        >
          How this is checked
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 transition-transform',
              showDetails && 'rotate-180'
            )}
          />
        </button>

        {showDetails && (
          <dl className="mt-3 space-y-2.5 text-xs text-slate-500">
            <div>
              <dt className="font-semibold text-slate-700">Engine</dt>
              <dd>{info.engine}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-700">Checks</dt>
              <dd>{info.checks}</dd>
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
        )}
      </div>
    </div>
  );
}
