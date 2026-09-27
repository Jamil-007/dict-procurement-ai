'use client';

import React, { useEffect, useRef, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import type { FormKey } from '@/types/forms';

interface DocumentPreviewProps {
  threadId: string;
  formKey: FormKey;
  ext: 'docx' | 'xlsx';
  /** The form's edited field values; drives what the generated document contains. */
  overrides: Record<string, string>;
  isAnnex?: boolean;
}

type Status = 'loading' | 'idle' | 'error';

// Debounce window (ms) applied to preview refreshes triggered by field edits.
// The first render for a freshly-opened form fires immediately (delay 0).
const REFRESH_DEBOUNCE_MS = 800;

// Module-level cache so switching between form tabs (which unmount this
// component) doesn't re-generate an unchanged document on the backend.
// Keyed by threadId + formKey + serialized overrides.
const blobCache = new Map<string, Blob>();

/**
 * Renders the *real* generated document (the same bytes the user downloads)
 * as a live preview. DOCX is rendered with docx-preview; XLSX with SheetJS.
 * Both libraries are imported dynamically so they stay out of the main bundle
 * and never execute during server-side rendering.
 */
export function DocumentPreview({
  threadId,
  formKey,
  ext,
  overrides,
  isAnnex,
}: DocumentPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);
  const firstRunRef = useRef(true);
  const reqIdRef = useRef(0);
  const [status, setStatus] = useState<Status>('loading');
  const [hasContent, setHasContent] = useState(false);

  const serialized = JSON.stringify(overrides);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const cacheKey = `${threadId}::${formKey}::${serialized}`;
    const delay = firstRunRef.current ? 0 : REFRESH_DEBOUNCE_MS;
    firstRunRef.current = false;

    const timer = setTimeout(() => {
      void run(cacheKey);
    }, delay);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, formKey, serialized]);

  async function run(cacheKey: string) {
    const id = ++reqIdRef.current;
    setStatus('loading');

    try {
      let blob = blobCache.get(cacheKey);
      if (!blob) {
        const result = await apiClient.generateForms(threadId, [formKey], {
          [formKey]: overrides,
        });
        blob = result.blob;
        blobCache.set(cacheKey, blob);
      }
      if (!mountedRef.current || id !== reqIdRef.current) return; // stale

      await renderBlob(blob);
      if (!mountedRef.current || id !== reqIdRef.current) return;

      setHasContent(true);
      setStatus('idle');
    } catch (error) {
      console.error('Failed to render document preview:', error);
      if (!mountedRef.current || id !== reqIdRef.current) return;
      setStatus('error');
    }
  }

  async function renderBlob(blob: Blob) {
    const el = containerRef.current;
    if (!el) return;

    if (ext === 'xlsx') {
      const XLSX = await import('xlsx');
      const buffer = await blob.arrayBuffer();
      const workbook = XLSX.read(buffer, { type: 'array' });
      el.innerHTML = workbook.SheetNames.map((name) => {
        const table = XLSX.utils.sheet_to_html(workbook.Sheets[name]);
        return `<div class="xlsx-sheet"><div class="xlsx-sheet-name">${escapeHtml(
          name
        )}</div>${table}</div>`;
      }).join('');
    } else {
      const { renderAsync } = await import('docx-preview');
      el.innerHTML = '';
      await renderAsync(blob, el, undefined, {
        className: 'docx',
        inWrapper: true,
        breakPages: true,
      });
    }
  }

  return (
    <div className="relative">
      {isAnnex && (
        <div className="text-center text-[9px] tracking-widest text-zinc-400 border border-zinc-300 rounded p-1 mb-3">
          DRAFT · FOR BIDDER COMPLETION · NOT NOTARIZED
        </div>
      )}

      {/* Overlay indicators */}
      {status === 'loading' && !hasContent && (
        <div className="flex items-center justify-center py-16 text-sm text-zinc-400 gap-2">
          <Spinner /> Building preview…
        </div>
      )}
      {status === 'loading' && hasContent && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-1.5 bg-white/90 border border-zinc-200 rounded-full px-2.5 py-1 text-[11px] text-zinc-500 shadow-sm">
          <Spinner /> Updating…
        </div>
      )}
      {status === 'error' && (
        <div className="flex flex-col items-center justify-center py-16 text-sm text-zinc-500 gap-3">
          <span>Couldn&apos;t build the preview.</span>
          <button
            onClick={() => run(`${threadId}::${formKey}::${serialized}`)}
            className="px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-300 bg-white hover:bg-zinc-50 transition-all"
          >
            Retry
          </button>
        </div>
      )}

      <div
        ref={containerRef}
        className={`docx-preview-host ${
          status === 'error' && !hasContent ? 'hidden' : ''
        }`}
      />
    </div>
  );
}

function Spinner() {
  return (
    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-500" />
  );
}

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string)
  );
}
