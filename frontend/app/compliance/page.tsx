'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CheckCircle2,
  FileText,
  Loader2,
  Play,
  RotateCcw,
  X,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { FileUpload } from '@/components/procurement/file-upload';
import { ThinkingWidget } from '@/components/procurement/thinking-widget';
import { SessionArchive } from '@/components/procurement/session-archive';
import { RequirementCard } from '@/components/compliance/requirement-card';
import { useProcurementAnalysis } from '@/hooks/use-procurement-analysis';
import { REQUIREMENTS } from '@/lib/requirements';
import { MAX_UPLOAD_FILES } from '@/lib/uploads';
import type { FindingDetail } from '@/types/procurement';

/**
 * The Compliance Suite tab: the six assigned requirements (T1..T6), each
 * visible as its own card, with a review run mapped back onto them.
 *
 * This is deliberately requirement-centric rather than chat-centric — the
 * point of the tab is that anyone can open it and see what was assigned,
 * what implements it, and what the last run found for each item.
 */

export default function CompliancePage() {
  const {
    state,
    thinkingLogs,
    verdictData,
    error,
    uploadFiles,
    reset,
  } = useProcurementAnalysis();

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  const isRunning = state === 'uploading' || state === 'thinking';
  const hasVerdict = Boolean(verdictData);

  const handleFilesSelect = useCallback((files: File[]) => {
    setPendingFiles((prev) => {
      const merged = [...prev, ...files];
      if (merged.length > MAX_UPLOAD_FILES) {
        toast.error(
          `Up to ${MAX_UPLOAD_FILES} documents can be reviewed in one run.`
        );
      }
      return merged.slice(0, MAX_UPLOAD_FILES);
    });
  }, []);

  const handleRun = useCallback(() => {
    if (!pendingFiles.length) return;
    uploadFiles(pendingFiles);
    setPendingFiles([]);
  }, [pendingFiles, uploadFiles]);

  const handleReset = useCallback(() => {
    reset();
    setPendingFiles([]);
  }, [reset]);

  // Every structured finding, keyed by the requirement that produced it.
  const findingsByTask = useMemo(() => {
    const map: Record<string, FindingDetail[]> = {};
    for (const group of verdictData?.findings ?? []) {
      for (const detail of group.details ?? []) {
        const task = detail.task || 'other';
        (map[task] ??= []).push(detail);
      }
    }
    return map;
  }, [verdictData]);

  const notVerified = useMemo(
    () =>
      verdictData?.findings.find((g) => g.category === 'Not Verified')?.items ??
      [],
    [verdictData]
  );

  const checkersRun = verdictData?.checkers_run ?? [];

  const groups = [
    {
      label: 'Compliance',
      category: 'COMPLIANCE',
      blurb: 'Each document is checked against procurement rules',
    },
    {
      label: 'Data integrity',
      category: 'DATA INTEGRITY',
      blurb: 'Documents are cross-checked against each other for mismatches',
    },
  ] as const;

  // Once a run starts, swap the upload card for a compact status row.
  const focusMode = isRunning || hasVerdict;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-gray-50">
      <SessionArchive />

      <div className="w-full flex-1 overflow-y-auto px-4 py-6 md:px-6">
        {/* Page header: title on the left, primary action on the right */}
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
              Compliance &amp; Data Integrity
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Upload procurement documents and review them against the six
              assigned checks.
            </p>
          </div>
          {hasVerdict && !isRunning && (
            <Button
              onClick={handleReset}
              className="rounded-lg bg-black text-white hover:bg-gray-800"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              New review
            </Button>
          )}
        </div>

        <div className="space-y-5">
          {!focusMode && (
            <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-baseline justify-between gap-3">
                <h2 className="text-sm font-semibold text-gray-900">
                  Upload documents
                </h2>
                <span className="text-xs text-gray-400">
                  Up to {MAX_UPLOAD_FILES} files · PDF, Word, Excel or text
                </span>
              </div>

              <FileUpload onFilesSelect={handleFilesSelect} disabled={isRunning} />

              {pendingFiles.length > 0 && (
                <ul className="mt-3 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                  {pendingFiles.map((file, i) => (
                    <li
                      key={`${file.name}-${i}`}
                      className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-700"
                    >
                      <FileText className="h-3.5 w-3.5 shrink-0 text-gray-400" />
                      <span className="min-w-0 flex-1 truncate">{file.name}</span>
                      <button
                        type="button"
                        onClick={() =>
                          setPendingFiles((prev) => prev.filter((_, j) => j !== i))
                        }
                        className="text-gray-400 hover:text-gray-900"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
                <p className="text-xs text-gray-400">
                  {pendingFiles.length
                    ? `${pendingFiles.length} document${
                        pendingFiles.length === 1 ? '' : 's'
                      } ready for review`
                    : 'Add documents to start a review'}
                </p>
                <div className="flex gap-2">
                  {error && (
                    <Button
                      variant="outline"
                      onClick={handleReset}
                      className="rounded-lg border-gray-200 text-gray-600 hover:bg-gray-50"
                    >
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Start over
                    </Button>
                  )}
                  <Button
                    onClick={handleRun}
                    disabled={!pendingFiles.length}
                    className="rounded-lg bg-black px-6 text-white hover:bg-gray-800"
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Run review
                  </Button>
                </div>
              </div>

              {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
            </section>
          )}

          {isRunning && (
            <div className="space-y-4">
              <section className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-gray-400" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900">
                    {state === 'uploading'
                      ? 'Uploading your documents…'
                      : 'Review in progress'}
                  </p>
                  <p className="text-xs text-gray-500">
                    Your documents are being checked against the six compliance
                    and data-integrity checks.
                  </p>
                </div>
              </section>

              {thinkingLogs.length > 0 && (
                <ThinkingWidget logs={thinkingLogs} isComplete={!isRunning} />
              )}
            </div>
          )}

          {verdictData && (
            <motion.section
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`rounded-xl border p-6 shadow-sm ${
                verdictData.status === 'PASS'
                  ? 'border-emerald-200 bg-emerald-50/70'
                  : 'border-red-200 bg-red-50/70'
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-5">
                <div className="min-w-[260px] flex-1">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${
                        verdictData.status === 'PASS'
                          ? 'bg-emerald-100 text-emerald-600'
                          : 'bg-red-100 text-red-600'
                      }`}
                    >
                      {verdictData.status === 'PASS' ? (
                        <CheckCircle2 className="h-6 w-6" />
                      ) : (
                        <XCircle className="h-6 w-6" />
                      )}
                    </div>
                    <div>
                      <p
                        className={`text-lg font-bold ${
                          verdictData.status === 'PASS'
                            ? 'text-emerald-800'
                            : 'text-red-800'
                        }`}
                      >
                        {verdictData.status === 'PASS'
                          ? 'Looks compliant'
                          : 'Needs attention'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {verdictData.confidence}% confidence ·{' '}
                        {verdictData.documents?.length ?? 0} document
                        {(verdictData.documents?.length ?? 0) === 1 ? '' : 's'}{' '}
                        reviewed
                      </p>
                    </div>
                  </div>
                  {verdictData.summary && (
                    <p className="mt-3 max-w-2xl text-sm leading-relaxed text-gray-600">
                      We ran {verdictData.summary.total} automated checks:{' '}
                      {verdictData.summary.passed} passed,{' '}
                      {verdictData.summary.failed} found problems that need
                      fixing
                      {verdictData.summary.skipped > 0 &&
                        `, and ${verdictData.summary.skipped} could not be confirmed from the documents provided`}
                      . Open a check below to see exactly what was caught and
                      where.
                    </p>
                  )}
                </div>

                {verdictData.summary && (
                  <div className="grid shrink-0 grid-cols-4 gap-2">
                    {(
                      [
                        ['Checks', verdictData.summary.total, 'text-gray-900'],
                        ['Passed', verdictData.summary.passed, 'text-emerald-600'],
                        ['Failed', verdictData.summary.failed, 'text-red-600'],
                        [
                          'Not verified',
                          verdictData.summary.skipped,
                          'text-amber-600',
                        ],
                      ] as const
                    ).map(([label, value, color]) => (
                      <div
                        key={label}
                        className="min-w-[76px] rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-center"
                      >
                        <p className={`text-xl font-bold leading-none ${color}`}>
                          {value}
                        </p>
                        <p className="mt-1 text-[10px] font-medium uppercase tracking-wide text-gray-400">
                          {label}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.section>
          )}

          {hasVerdict ? (
            <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold text-gray-900">
                Results by check
              </h2>

              {groups.map((group) => {
                const reqs = REQUIREMENTS.filter(
                  (req) => req.category === group.category
                );
                if (!reqs.length) return null;
                return (
                  <div key={group.category} className="mb-5 last:mb-0">
                    <div className="mb-2">
                      <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
                        {group.label}
                      </p>
                      <p className="text-[11px] text-gray-400">{group.blurb}</p>
                    </div>
                    <div className="space-y-2">
                      {reqs.map((req) => (
                        <RequirementCard
                          key={req.task}
                          info={req}
                          stats={verdictData?.tasks?.[req.task]}
                          findings={findingsByTask[req.task] ?? []}
                          checkerRan={checkersRun.includes(req.checkerNode)}
                          hasVerdict={hasVerdict}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}

              {notVerified.length > 0 && (
                <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4">
                  <h3 className="text-xs font-semibold text-amber-900">
                    Could not be confirmed ({notVerified.length})
                  </h3>
                  <p className="mt-1 text-xs text-amber-800">
                    These checks ran, but the uploaded documents did not contain
                    the data needed to confirm them either way:
                  </p>
                  <ul className="mt-2 space-y-1 text-xs text-amber-900">
                    {notVerified.map((item, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="select-none">•</span>
                        <span className="break-words">{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          ) : (
            !isRunning && (
              /* Pre-run: a static preview of the six checks instead of empty result rows. */
              <div className="space-y-5">
                {groups.map((group) => {
                  const reqs = REQUIREMENTS.filter(
                    (req) => req.category === group.category
                  );
                  if (!reqs.length) return null;
                  return (
                    <section key={group.category}>
                      <div className="mb-2.5">
                        <h2 className="text-sm font-semibold text-gray-900">
                          {group.label}
                        </h2>
                        <p className="text-xs text-gray-400">{group.blurb}</p>
                      </div>
                      <div className="grid gap-3 md:grid-cols-3">
                        {reqs.map((req) => (
                          <div
                            key={req.task}
                            className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
                          >
                            <p className="text-sm font-medium text-gray-900">
                              {req.name}
                            </p>
                            <p className="mt-1 flex-1 text-xs leading-relaxed text-gray-500">
                              {req.description}
                            </p>
                            <div className="mt-3 flex flex-wrap gap-1">
                              {req.documents.slice(0, 3).map((doc) => (
                                <span
                                  key={doc}
                                  className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600"
                                >
                                  {doc}
                                </span>
                              ))}
                              {req.documents.length > 3 && (
                                <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] text-gray-400">
                                  +{req.documents.length - 3} more
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  );
                })}
              </div>
            )
          )}

          {/* Documents reviewed */}
          {verdictData?.documents && verdictData.documents.length > 0 && (
            <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-100 px-5 py-3">
                <h2 className="text-sm font-semibold text-gray-900">
                  Documents reviewed ({verdictData.documents.length})
                </h2>
              </div>
              <ul className="grid divide-y divide-gray-100 sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-3">
                {verdictData.documents.map((doc) => (
                  <li key={doc.file} className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-gray-400" />
                      <span className="min-w-0 flex-1 truncate text-xs font-medium text-gray-900">
                        {doc.file}
                      </span>
                    </div>
                    <p className="mt-1 pl-6 text-[11px] text-gray-500">
                      {doc.label || doc.doc_type} ·{' '}
                      {Math.round(doc.confidence * 100)}%
                      {doc.pages_read != null &&
                        ` · ${doc.pages_read}${
                          doc.total_pages ? `/${doc.total_pages}` : ''
                        } pages`}
                    </p>
                    {doc.error && (
                      <p className="mt-1 pl-6 text-[11px] text-red-600">
                        {doc.error}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
