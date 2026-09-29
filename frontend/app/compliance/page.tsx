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
    { label: 'Compliance', category: 'COMPLIANCE' },
    { label: 'Data integrity', category: 'DATA INTEGRITY' },
  ] as const;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white">
      <SessionArchive />

      <div className="mx-auto w-full max-w-7xl flex-1 overflow-y-auto px-6 py-6">
        <div className="mb-6">
          <h1 className="text-lg font-bold tracking-tight text-gray-900">
            Compliance &amp; Data Integrity
          </h1>
          <p className="mt-0.5 max-w-xl text-sm text-gray-500">
            Upload your procurement documents to review them against the six
            assigned compliance checks.
          </p>
        </div>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          {/* Left: upload */}
          <div className="space-y-4">
            <section className="rounded-xl border border-gray-200 bg-white p-6">
              <div className="mb-4 flex items-center gap-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500">
                  1
                </span>
                <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                  Upload documents
                </h2>
              </div>

              {!isRunning && (
                <FileUpload onFilesSelect={handleFilesSelect} disabled={isRunning} />
              )}

              {pendingFiles.length > 0 && !isRunning && (
                <ul className="mt-3 space-y-1.5">
                  {pendingFiles.map((file, i) => (
                    <li
                      key={`${file.name}-${i}`}
                      className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-xs text-gray-700"
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

              <div className="mt-4 flex flex-col gap-2">
                <Button
                  onClick={handleRun}
                  disabled={!pendingFiles.length || isRunning}
                  className="w-full rounded-lg bg-black text-white hover:bg-gray-800"
                >
                  {isRunning ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  {isRunning
                    ? state === 'uploading'
                      ? 'Uploading…'
                      : 'Reviewing…'
                    : `Run review${
                        pendingFiles.length ? ` (${pendingFiles.length})` : ''
                      }`}
                </Button>
                {(hasVerdict || error) && !isRunning && (
                  <Button
                    variant="outline"
                    onClick={handleReset}
                    className="w-full rounded-lg border-gray-200 text-gray-600 hover:bg-gray-50"
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    New review
                  </Button>
                )}
              </div>

              {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
            </section>

            {isRunning && thinkingLogs.length > 0 && (
              <ThinkingWidget logs={thinkingLogs} isComplete={!isRunning} />
            )}

            {verdictData?.documents && verdictData.documents.length > 0 && (
              <section className="overflow-hidden rounded-xl border border-gray-200 bg-white">
                <div className="border-b border-gray-100 px-4 py-2.5">
                  <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                    Documents ({verdictData.documents.length})
                  </h2>
                </div>
                <ul className="divide-y divide-gray-100">
                  {verdictData.documents.map((doc) => (
                    <li key={doc.file} className="px-4 py-3">
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

          {/* Right: results */}
          <section className="rounded-xl border border-gray-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-2.5">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500">
                2
              </span>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
                Review results
              </h2>
            </div>

            {verdictData && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-5 rounded-lg border border-gray-200 p-4"
              >
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                      verdictData.status === 'PASS'
                        ? 'bg-emerald-100 text-emerald-600'
                        : 'bg-red-100 text-red-600'
                    }`}
                  >
                    {verdictData.status === 'PASS' ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : (
                      <XCircle className="h-5 w-5" />
                    )}
                  </div>
                  <p
                    className={`min-w-0 flex-1 text-base font-semibold ${
                      verdictData.status === 'PASS'
                        ? 'text-emerald-700'
                        : 'text-red-700'
                    }`}
                  >
                    {verdictData.status === 'PASS'
                      ? 'Looks compliant'
                      : 'Needs attention'}
                    <span className="ml-2 text-xs font-normal text-gray-400">
                      {verdictData.confidence}% confidence
                    </span>
                  </p>
                  {verdictData.summary && (
                    <div className="flex divide-x divide-gray-100 text-center text-[11px] text-gray-400">
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
                        <div key={label} className="px-3">
                          <p
                            className={`text-base font-semibold leading-none ${color}`}
                          >
                            {value}
                          </p>
                          <p className="mt-0.5">{label}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {groups.map((group) => {
              const reqs = REQUIREMENTS.filter(
                (req) => req.category === group.category
              );
              if (!reqs.length) return null;
              return (
                <div key={group.category} className="mb-5 last:mb-0">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-gray-400">
                    {group.label}
                  </p>
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
                  Not verified ({notVerified.length})
                </h3>
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
        </div>
      </div>
    </div>
  );
}
