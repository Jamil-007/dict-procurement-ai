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

  return (
    <div className="h-full overflow-y-auto bg-slate-50">
      <SessionArchive />

      <div className="mx-auto max-w-5xl space-y-6 px-6 py-10">
        {/* Header */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-blue-600">
              DICT · Procurement
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">
              Compliance Suite
            </h1>
            <p className="mt-1.5 text-sm text-slate-500">
              Upload documents — each requirement below shows what the review
              found.
            </p>
          </div>
          <div className="flex divide-x divide-slate-200 rounded-2xl bg-white ring-1 ring-slate-200">
            {(
              [
                ['6', 'Requirements'],
                ['64', 'Rules'],
                ['35', 'Cross-checks'],
              ] as const
            ).map(([value, label]) => (
              <div key={label} className="px-5 py-3 text-center">
                <p className="text-lg font-semibold leading-none text-slate-900">
                  {value}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Run panel */}
        <section className="rounded-2xl bg-white p-5 ring-1 ring-slate-200">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-900">
              Run a review
            </h2>
            <p className="text-xs text-slate-400">
              PDF, Word, Excel or text · up to {MAX_UPLOAD_FILES} files
            </p>
          </div>

          {!isRunning && (
            <div className="mt-4">
              <FileUpload onFilesSelect={handleFilesSelect} disabled={isRunning} />
            </div>
          )}

          {pendingFiles.length > 0 && !isRunning && (
            <div className="mt-3 flex flex-wrap gap-2">
              {pendingFiles.map((file, i) => (
                <span
                  key={`${file.name}-${i}`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-700"
                >
                  <FileText className="h-3.5 w-3.5 text-slate-400" />
                  <span className="max-w-[220px] truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() =>
                      setPendingFiles((prev) => prev.filter((_, j) => j !== i))
                    }
                    className="text-slate-400 hover:text-slate-900"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <Button
              onClick={handleRun}
              disabled={!pendingFiles.length || isRunning}
              className="rounded-xl bg-blue-600 text-white shadow-sm hover:bg-blue-700"
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
                : `Run compliance review${
                    pendingFiles.length
                      ? ` (${pendingFiles.length} file${
                          pendingFiles.length === 1 ? '' : 's'
                        })`
                      : ''
                  }`}
            </Button>
            {(hasVerdict || error) && !isRunning && (
              <Button
                variant="outline"
                onClick={handleReset}
                className="rounded-xl border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                New review
              </Button>
            )}
          </div>

          {isRunning && thinkingLogs.length > 0 && (
            <div className="mt-4">
              <ThinkingWidget logs={thinkingLogs} isComplete={!isRunning} />
            </div>
          )}

          {error && (
            <p className="mt-3 text-sm text-red-600">{error}</p>
          )}
        </section>

        {/* Verdict banner */}
        {verdictData && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl bg-white p-5 ring-1 ring-slate-200"
          >
            <div className="flex flex-wrap items-center gap-4">
              <div
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${
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
              <div className="min-w-0 flex-1">
                <p
                  className={`text-lg font-semibold ${
                    verdictData.status === 'PASS'
                      ? 'text-emerald-700'
                      : 'text-red-700'
                  }`}
                >
                  {verdictData.status === 'PASS'
                    ? 'Looks compliant'
                    : 'Needs attention'}
                  <span className="ml-2 text-sm font-normal text-slate-400">
                    {verdictData.confidence}% confidence
                  </span>
                </p>
                <p className="mt-0.5 text-sm text-slate-500">
                  {verdictData.title}
                </p>
              </div>
              {verdictData.summary && (
                <div className="flex divide-x divide-slate-100 text-center text-xs text-slate-400">
                  {(
                    [
                      ['Checks', verdictData.summary.total, 'text-slate-900'],
                      ['Passed', verdictData.summary.passed, 'text-emerald-600'],
                      ['Failed', verdictData.summary.failed, 'text-red-600'],
                      [
                        'Not verified',
                        verdictData.summary.skipped,
                        'text-amber-600',
                      ],
                    ] as const
                  ).map(([label, value, color]) => (
                    <div key={label} className="px-4">
                      <p
                        className={`text-lg font-semibold leading-none ${color}`}
                      >
                        {value}
                      </p>
                      <p className="mt-1">{label}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.section>
        )}

        {/* Documents reviewed */}
        {verdictData?.documents && verdictData.documents.length > 0 && (
          <section className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
            <div className="border-b border-slate-100 px-5 py-3">
              <h2 className="text-sm font-semibold text-slate-900">
                Documents reviewed ({verdictData.documents.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/70 text-[11px] uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-5 py-2 font-medium">File</th>
                    <th className="px-5 py-2 font-medium">Detected type</th>
                    <th className="px-5 py-2 font-medium">Confidence</th>
                    <th className="px-5 py-2 font-medium">Pages read</th>
                    <th className="px-5 py-2 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {verdictData.documents.map((doc) => (
                    <React.Fragment key={doc.file}>
                      <tr>
                        <td className="max-w-[260px] truncate px-5 py-2 font-medium text-black">
                          {doc.file}
                        </td>
                        <td className="px-5 py-2 text-gray-700">
                          {doc.label || doc.doc_type}
                        </td>
                        <td className="px-5 py-2 text-gray-700">
                          {Math.round(doc.confidence * 100)}%
                        </td>
                        <td className="px-5 py-2 text-gray-700">
                          {doc.pages_read ?? '—'}
                          {doc.total_pages ? ` / ${doc.total_pages}` : ''}
                        </td>
                        <td className="px-5 py-2 text-gray-700">
                          {doc.ingest_source || '—'}
                        </td>
                      </tr>
                      {doc.error && (
                        <tr>
                          <td colSpan={5} className="bg-red-50 px-5 py-2 text-red-700">
                            {doc.error}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* The six requirements */}
        <section>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold text-slate-900">
              Assigned requirements
            </h2>
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
              <span className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Passed
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-500" />
                Issues
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                Not verified
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-slate-300" />
                Not applicable
              </span>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {REQUIREMENTS.map((req) => (
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
        </section>

        {/* Checks that could not run */}
        {notVerified.length > 0 && (
          <section className="rounded-2xl bg-amber-50 p-5 ring-1 ring-amber-200">
            <h2 className="text-sm font-semibold text-amber-900">
              Not verified ({notVerified.length})
            </h2>
            <p className="mt-0.5 text-xs text-amber-800">
              These checks could not run on this upload.
            </p>
            <ul className="mt-3 space-y-1.5 text-xs text-amber-900">
              {notVerified.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="select-none">•</span>
                  <span className="break-words">{item}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
