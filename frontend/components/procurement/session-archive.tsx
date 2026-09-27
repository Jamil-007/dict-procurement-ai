'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, History, Loader2, Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { FindingDetailCard } from './finding-detail';
import { apiClient } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type { ArchivedSession, SessionSummary } from '@/types/procurement';

/**
 * Past reviews, read back from the backend archive.
 *
 * A compliance finding is only useful if it can be produced again when
 * someone questions it weeks later. The analysis itself is already persisted
 * server-side; this is the window onto it.
 */

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function SessionArchive() {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selected, setSelected] = useState<ArchivedSession | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setIsLoading(true);
    try {
      setSessions(await apiClient.getSessions());
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not load past reviews'
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen, loadSessions]);

  const openSession = useCallback(async (threadId: string) => {
    setIsLoadingDetail(true);
    try {
      setSelected(await apiClient.getSession(threadId));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not open that review'
      );
    } finally {
      setIsLoadingDetail(false);
    }
  }, []);

  const removeSession = useCallback(
    async (threadId: string) => {
      try {
        await apiClient.deleteSession(threadId);
        setSessions((prev) => prev.filter((s) => s.thread_id !== threadId));
        setSelected((prev) => (prev?.thread_id === threadId ? null : prev));
        toast.success('Review deleted');
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : 'Could not delete that review'
        );
      } finally {
        setPendingDelete(null);
      }
    },
    []
  );

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(true)}
        className="fixed left-4 top-4 z-30 rounded-full border-gray-300 bg-white text-black hover:bg-gray-100"
      >
        <History className="mr-2 h-4 w-4" />
        Past Reviews
      </Button>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/40"
              onClick={() => setIsOpen(false)}
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 34 }}
              className="fixed inset-y-0 left-0 z-50 flex w-full max-w-xl flex-col border-r border-gray-200 bg-white shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-gray-200 p-4">
                <div className="flex min-w-0 items-center gap-2">
                  {selected && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="rounded-full"
                      onClick={() => setSelected(null)}
                    >
                      <ArrowLeft className="h-4 w-4" />
                    </Button>
                  )}
                  <h2 className="truncate text-lg font-semibold text-black">
                    {selected ? selected.title : 'Past Reviews'}
                  </h2>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="rounded-full"
                  onClick={() => setIsOpen(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex-1 overflow-y-auto p-4">
                {isLoading || isLoadingDetail ? (
                  <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading…
                  </div>
                ) : selected ? (
                  <SessionDetail session={selected} />
                ) : sessions.length === 0 ? (
                  <p className="py-16 text-center text-sm text-gray-500">
                    No reviews have been archived yet. Every analysis you run is
                    saved here automatically.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {sessions.map((session) => (
                      <li
                        key={session.thread_id}
                        className="rounded-xl border border-gray-200 p-3 transition-colors hover:bg-gray-50"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <button
                            type="button"
                            onClick={() => openSession(session.thread_id)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge
                                variant="outline"
                                className={cn(
                                  'rounded-full text-[10px]',
                                  session.status === 'PASS'
                                    ? 'border-black bg-black text-white'
                                    : 'border-gray-700 bg-gray-700 text-white'
                                )}
                              >
                                {session.status}
                              </Badge>
                              <span className="text-xs text-gray-500">
                                {formatTimestamp(session.updated_at)}
                              </span>
                            </div>
                            <p className="mt-1 break-words text-sm font-medium text-black">
                              {session.title}
                            </p>
                            <p className="mt-1 text-xs text-gray-500">
                              {session.file_count} document
                              {session.file_count === 1 ? '' : 's'} ·{' '}
                              {session.finding_count} finding
                              {session.finding_count === 1 ? '' : 's'}
                              {session.high_count > 0 &&
                                ` · ${session.high_count} high severity`}
                            </p>
                          </button>

                          {pendingDelete === session.thread_id ? (
                            <div className="flex shrink-0 gap-1">
                              <Button
                                size="sm"
                                className="h-7 rounded-full bg-black px-3 text-xs hover:bg-gray-800"
                                onClick={() => removeSession(session.thread_id)}
                              >
                                Delete
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 rounded-full px-3 text-xs"
                                onClick={() => setPendingDelete(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 shrink-0 rounded-full text-gray-400 hover:text-black"
                              onClick={() => setPendingDelete(session.thread_id)}
                              aria-label={`Delete review ${session.title}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

function SessionDetail({ session }: { session: ArchivedSession }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className={cn(
            'rounded-full',
            session.status === 'PASS'
              ? 'border-black bg-black text-white'
              : 'border-gray-700 bg-gray-700 text-white'
          )}
        >
          {session.status}
        </Badge>
        <span className="text-sm text-gray-600">
          {session.confidence}% confidence
        </span>
        <span className="text-xs text-gray-500">
          {formatTimestamp(session.created_at)}
        </span>
      </div>

      {session.documents.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Documents
          </h3>
          <ul className="space-y-1 text-sm">
            {session.documents.map((doc, i) => (
              <li
                key={i}
                className="flex flex-wrap items-baseline justify-between gap-2"
              >
                <span className="min-w-0 break-all text-black">
                  {doc.filename}
                </span>
                <span className="text-xs text-gray-500">
                  {doc.doc_type}
                  {doc.total_pages ? ` · ${doc.pages_read}/${doc.total_pages} pp` : ''}
                  {doc.ingest_source === 'ocr' ? ' · OCR' : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Separator className="bg-gray-200" />

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Findings
        </h3>
        {session.findings.length === 0 ? (
          <p className="text-sm text-gray-500">
            No findings were recorded for this review.
          </p>
        ) : (
          <div className="space-y-2">
            {session.findings.map((finding, i) => (
              <FindingDetailCard key={finding.rule_id ?? i} finding={finding} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
