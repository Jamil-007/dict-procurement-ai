'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiClient } from '@/lib/api-client';
import type { FormKey } from '@/types/forms';

interface DocumentPreviewProps {
  threadId: string;
  formKey: FormKey;
  ext: 'docx' | 'xlsx';
  filename: string;
  /** The form's edited field values; drives what the generated document contains. */
  overrides: Record<string, string>;
  isAnnex?: boolean;
  /** True when this form's tab is the visible one. Generation is lazy on first activation. */
  active: boolean;
  onDownload?: () => void;
  downloading?: boolean;
}

type Status = 'loading' | 'idle' | 'error';

// Debounce (ms) for refreshes triggered by field edits. First build is immediate.
const REFRESH_DEBOUNCE_MS = 800;
const STAGE_PAD = 36; // horizontal padding inside the scroll stage
const ZOOM_MIN = 0.3;
const ZOOM_MAX = 2;
// Floor for fit-to-width so a very wide spreadsheet never collapses to an
// unreadable few-percent thumbnail; the stage scrolls horizontally instead.
const FIT_FLOOR = 0.45;

// Module-level cache so switching form tabs never re-hits the backend for an
// unchanged document. Keyed by threadId + formKey + serialized overrides.
const blobCache = new Map<string, Blob>();

/**
 * Renders the *real* generated document (same bytes the user downloads) as a
 * live preview with zoom / fit-width / maximize controls. DOCX renders with
 * docx-preview; XLSX is rebuilt into a clean spreadsheet grid from the SheetJS
 * data model. Both libraries load dynamically (out of the main bundle, no SSR).
 *
 * Retention: the component stays mounted per tab (see form-review forceMount),
 * generates lazily on first activation, and updates silently in the background
 * on edits — so switching tabs never flashes a "building" state again.
 */
export function DocumentPreview({
  threadId,
  formKey,
  ext,
  filename,
  overrides,
  isAnnex,
  active,
  onDownload,
  downloading,
}: DocumentPreviewProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const mStageRef = useRef<HTMLDivElement>(null);
  const mContainerRef = useRef<HTMLDivElement>(null);

  const mountedRef = useRef(true);
  const reqIdRef = useRef(0);
  const lastKeyRef = useRef<string | null>(null);
  const renderedRef = useRef(false);
  const lastBlobRef = useRef<Blob | null>(null);
  const naturalWidthRef = useRef(0);

  const [status, setStatus] = useState<Status>('loading');
  const [hasContent, setHasContent] = useState(false);
  const [fit, setFit] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [pct, setPct] = useState(100);
  const [showModal, setShowModal] = useState(false);

  const serialized = JSON.stringify(overrides);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fitScaleFor = useCallback((stage: HTMLDivElement | null, cap: number) => {
    if (!stage) return 1;
    const avail = stage.clientWidth - STAGE_PAD;
    const natural = naturalWidthRef.current || avail;
    return Math.min(cap, avail / natural);
  }, []);

  const applyScale = useCallback(() => {
    const stage = stageRef.current;
    const host = containerRef.current;
    if (!stage || !host) return;
    const scale = fit ? Math.max(FIT_FLOOR, fitScaleFor(stage, 1)) : zoom;
    (host.style as CSSStyleDeclaration & { zoom?: string }).zoom = String(scale);
    setPct(Math.round(scale * 100));
  }, [fit, zoom, fitScaleFor]);

  // Recompute scale on state/visibility changes and on container resize.
  useEffect(() => {
    if (active && hasContent) applyScale();
  }, [active, hasContent, applyScale]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const ro = new ResizeObserver(() => applyScale());
    ro.observe(stage);
    return () => ro.disconnect();
  }, [applyScale]);

  const renderInto = useCallback(
    async (el: HTMLDivElement | null, blob: Blob) => {
      if (!el) return;
      if (ext === 'xlsx') {
        const XLSX = await import('xlsx');
        const buffer = await blob.arrayBuffer();
        const workbook = XLSX.read(buffer, { type: 'array' });
        el.innerHTML = workbook.SheetNames.map((name) =>
          renderSheetGrid(XLSX, workbook.Sheets[name], name)
        ).join('');
      } else {
        const { renderAsync } = await import('docx-preview');
        el.innerHTML = '';
        await renderAsync(blob, el, undefined, {
          className: 'docx',
          inWrapper: true,
          breakPages: true,
        });
      }
    },
    [ext]
  );

  const measureNatural = useCallback(
    (el: HTMLDivElement | null): number => {
      if (!el) return 0;
      const target =
        ext === 'xlsx'
          ? el.querySelector<HTMLElement>('table.xl')
          : el.querySelector<HTMLElement>('.docx-wrapper section, section.docx, .docx');
      return target?.offsetWidth || el.scrollWidth || 0;
    },
    [ext]
  );

  const run = useCallback(
    async (cacheKey: string) => {
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
        if (!mountedRef.current || id !== reqIdRef.current) return;

        lastBlobRef.current = blob;
        await renderInto(containerRef.current, blob);
        if (!mountedRef.current || id !== reqIdRef.current) return;

        naturalWidthRef.current = measureNatural(containerRef.current);
        lastKeyRef.current = cacheKey;
        renderedRef.current = true;
        setHasContent(true);
        setStatus('idle');
        applyScale();
      } catch (error) {
        console.error('Failed to render document preview:', error);
        if (!mountedRef.current || id !== reqIdRef.current) return;
        setStatus('error');
      }
    },
    [threadId, formKey, overrides, renderInto, measureNatural, applyScale]
  );

  // Generation: lazy on first activation, debounced silent refresh on edits,
  // and a no-op (just rescale) when re-showing an already-rendered tab.
  useEffect(() => {
    if (!active) return;
    const cacheKey = `${threadId}::${formKey}::${serialized}`;
    if (cacheKey === lastKeyRef.current && renderedRef.current) {
      applyScale();
      return;
    }
    const delay = renderedRef.current ? REFRESH_DEBOUNCE_MS : 0;
    const timer = setTimeout(() => void run(cacheKey), delay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, threadId, formKey, serialized]);

  // ----- modal -----
  const [mFit, setMFit] = useState(true);
  const [mZoom, setMZoom] = useState(1);
  const [mPct, setMPct] = useState(100);
  const mNaturalRef = useRef(0);

  const applyScaleM = useCallback(() => {
    const stage = mStageRef.current;
    const host = mContainerRef.current;
    if (!stage || !host) return;
    const avail = stage.clientWidth - STAGE_PAD;
    const natural = mNaturalRef.current || avail;
    const scale = mFit ? Math.max(FIT_FLOOR, Math.min(1.6, avail / natural)) : mZoom;
    (host.style as CSSStyleDeclaration & { zoom?: string }).zoom = String(scale);
    setMPct(Math.round(scale * 100));
  }, [mFit, mZoom]);

  useEffect(() => {
    if (!showModal || !lastBlobRef.current) return;
    let cancelled = false;
    (async () => {
      await renderInto(mContainerRef.current, lastBlobRef.current!);
      if (cancelled) return;
      mNaturalRef.current = measureNatural(mContainerRef.current);
      setMFit(true);
      applyScaleM();
    })();
    return () => {
      cancelled = true;
    };
  }, [showModal, renderInto, measureNatural, applyScaleM]);

  useEffect(() => {
    if (showModal) applyScaleM();
  }, [mFit, mZoom, showModal, applyScaleM]);

  useEffect(() => {
    if (!showModal) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowModal(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showModal]);

  const zoomBy = (delta: number) => {
    setFit(false);
    setZoom((z) => clampZoom((z || fitScaleFor(stageRef.current, 1)) + delta));
  };
  const zoomByM = (delta: number) => {
    setMFit(false);
    setMZoom((z) => clampZoom((z || 1) + delta));
  };

  return (
    <div className="rounded-xl border border-zinc-200 overflow-hidden bg-white">
      <Toolbar
        filename={filename}
        ext={ext}
        pct={pct}
        fit={fit}
        onZoomOut={() => zoomBy(-0.15)}
        onZoomIn={() => zoomBy(0.15)}
        onToggleFit={() => setFit((f) => !f)}
        onMaximize={() => setShowModal(true)}
        onDownload={onDownload}
        downloading={downloading}
      />

      <div ref={stageRef} className="relative bg-zinc-100 h-[520px] overflow-auto">
        {isAnnex && (
          <div className="sticky top-0 z-10 text-center text-[9px] tracking-widest text-amber-700 bg-amber-50 border-b border-amber-200 py-1">
            DRAFT · FOR BIDDER COMPLETION · NOT NOTARIZED
          </div>
        )}

        {status === 'loading' && !hasContent && (
          <div className="flex items-center justify-center py-20 text-sm text-zinc-400 gap-2">
            <Spinner /> Building preview…
          </div>
        )}
        {status === 'loading' && hasContent && (
          <div className="absolute top-2 right-2 z-20 flex items-center gap-1.5 bg-white/90 border border-zinc-200 rounded-full px-2.5 py-1 text-[11px] text-zinc-500 shadow-sm">
            <Spinner /> Updating…
          </div>
        )}
        {status === 'error' && !hasContent && (
          <div className="flex flex-col items-center justify-center py-20 text-sm text-zinc-500 gap-3">
            <span>Couldn&apos;t build the preview.</span>
            <button
              onClick={() => run(`${threadId}::${formKey}::${serialized}`)}
              className="px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-300 bg-white hover:bg-zinc-50 transition-all"
            >
              Retry
            </button>
          </div>
        )}

        <div className="flex justify-center p-[18px]">
          <div ref={containerRef} className="docx-preview-host origin-top" />
        </div>
      </div>

      {showModal &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            className="fixed inset-0 z-50 bg-zinc-900/60 backdrop-blur-[2px] flex items-center justify-center p-7"
            onClick={(e) => {
              if (e.target === e.currentTarget) setShowModal(false);
            }}
          >
            <div className="w-[min(1100px,96vw)] h-[min(88vh,900px)] bg-white rounded-2xl overflow-hidden flex flex-col shadow-2xl">
              <Toolbar
                filename={filename}
                ext={ext}
                pct={mPct}
                fit={mFit}
                onZoomOut={() => zoomByM(-0.15)}
                onZoomIn={() => zoomByM(0.15)}
                onToggleFit={() => setMFit((f) => !f)}
                onDownload={onDownload}
                downloading={downloading}
                onClose={() => setShowModal(false)}
              />
              <div ref={mStageRef} className="relative bg-zinc-100 flex-1 overflow-auto">
                <div className="flex justify-center p-6">
                  <div ref={mContainerRef} className="docx-preview-host origin-top" />
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

function Toolbar({
  filename,
  ext,
  pct,
  fit,
  onZoomOut,
  onZoomIn,
  onToggleFit,
  onMaximize,
  onDownload,
  downloading,
  onClose,
}: {
  filename: string;
  ext: string;
  pct: number;
  fit: boolean;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onToggleFit: () => void;
  onMaximize?: () => void;
  onDownload?: () => void;
  downloading?: boolean;
  onClose?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 bg-white border-b border-zinc-200 px-2.5 py-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[12.5px] font-medium text-zinc-600 truncate">{filename}</span>
        <span className="text-[9.5px] font-semibold text-zinc-400 bg-zinc-100 rounded px-1.5 py-0.5 uppercase tracking-wide">
          {ext}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="flex items-center bg-zinc-100 rounded-lg p-0.5">
          <IconButton label="Zoom out" onClick={onZoomOut}>
            −
          </IconButton>
          <span className="text-[11.5px] text-zinc-600 min-w-[42px] text-center tabular-nums select-none">
            {pct}%
          </span>
          <IconButton label="Zoom in" onClick={onZoomIn}>
            +
          </IconButton>
        </div>
        <button
          onClick={onToggleFit}
          title="Fit to width"
          className={`rounded-lg px-2.5 py-1.5 text-[11.5px] font-semibold border transition-all ${
            fit
              ? 'bg-black text-white border-black'
              : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-50'
          }`}
        >
          Fit width
        </button>
        <div className="w-px h-5 bg-zinc-200 mx-0.5" />
        {onMaximize && (
          <IconButton label="Maximize" onClick={onMaximize} size="lg">
            ⛶
          </IconButton>
        )}
        {onDownload && (
          <button
            onClick={onDownload}
            disabled={downloading}
            className="rounded-lg px-3 py-1.5 text-[12px] font-semibold border border-zinc-300 bg-white hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {downloading ? 'Downloading…' : 'Download'}
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            title="Close (Esc)"
            className="rounded-lg w-[30px] h-[30px] grid place-items-center bg-zinc-100 hover:bg-zinc-200 text-zinc-600"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

function IconButton({
  children,
  onClick,
  label,
  size,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  label: string;
  size?: 'lg';
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className={`grid place-items-center rounded-md text-zinc-600 hover:bg-zinc-200/70 transition-colors ${
        size === 'lg' ? 'w-[30px] h-[30px] text-[15px]' : 'w-[26px] h-[26px] text-[15px] leading-none'
      }`}
    >
      {children}
    </button>
  );
}

function Spinner() {
  return (
    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-500" />
  );
}

function clampZoom(n: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, n));
}

/**
 * Rebuilds a worksheet into a clean, Excel-like HTML grid from the SheetJS data
 * model: A/B/C column letters, a row-number gutter, merged cells, and trimmed
 * empty rows. This replaces sheet_to_html, which rendered every blank template
 * row as a bordered strip.
 */
function renderSheetGrid(
  XLSX: typeof import('xlsx'),
  ws: import('xlsx').WorkSheet,
  name: string
): string {
  const ref = ws['!ref'];
  if (!ref) return `<div class="xl-empty">Empty sheet</div>`;
  const range = XLSX.utils.decode_range(ref);
  const merges = ws['!merges'] || [];

  const masters = new Map<string, { rs: number; cs: number }>();
  const covered = new Set<string>();
  for (const m of merges) {
    masters.set(`${m.s.r}:${m.s.c}`, {
      rs: m.e.r - m.s.r + 1,
      cs: m.e.c - m.s.c + 1,
    });
    for (let r = m.s.r; r <= m.e.r; r++) {
      for (let c = m.s.c; c <= m.e.c; c++) {
        if (r === m.s.r && c === m.s.c) continue;
        covered.add(`${r}:${c}`);
      }
    }
  }
  const inMerge = (r: number) => merges.some((m) => r >= m.s.r && r <= m.e.r);
  const cellVal = (r: number, c: number): string => {
    const cell = ws[XLSX.utils.encode_cell({ r, c })];
    if (!cell) return '';
    const v = cell.w ?? cell.v ?? '';
    return v == null ? '' : String(v);
  };

  // Keep rows that have content or are part of a merge (spacer rows dropped).
  const keptRows: number[] = [];
  for (let r = range.s.r; r <= range.e.r; r++) {
    let hasVal = false;
    for (let c = range.s.c; c <= range.e.c; c++) {
      if (cellVal(r, c).trim() !== '') {
        hasVal = true;
        break;
      }
    }
    if (hasVal || inMerge(r)) keptRows.push(r);
  }
  if (keptRows.length === 0) return `<div class="xl-empty">Empty sheet</div>`;

  // Trim trailing empty columns.
  let lastCol = range.s.c;
  for (const r of keptRows) {
    for (let c = range.s.c; c <= range.e.c; c++) {
      if (cellVal(r, c).trim() !== '') lastCol = Math.max(lastCol, c);
    }
  }
  for (const m of merges) lastCol = Math.max(lastCol, m.e.c);
  const colCount = lastCol - range.s.c + 1;

  let head = '<tr><th class="xl-corner"></th>';
  for (let c = range.s.c; c <= lastCol; c++) {
    head += `<th class="xl-colh">${XLSX.utils.encode_col(c)}</th>`;
  }
  head += '</tr>';

  let body = '';
  keptRows.forEach((r, idx) => {
    body += `<tr><td class="xl-rowh">${idx + 1}</td>`;
    for (let c = range.s.c; c <= lastCol; c++) {
      const key = `${r}:${c}`;
      if (covered.has(key)) continue;
      const m = masters.get(key);
      const rs = m && m.rs > 1 ? ` rowspan="${m.rs}"` : '';
      const cs = m && m.cs > 1 ? ` colspan="${m.cs}"` : '';
      const span = m ? m.cs : 1;
      const val = cellVal(r, c);

      let cls = 'xl-cell';
      if (val && span >= colCount) cls += ' xl-title';
      else if (val && span > 1 && val === val.toUpperCase() && /[A-Z]/.test(val)) cls += ' xl-section';
      if (/\[TBD\]/.test(val)) cls += ' xl-tbd';

      body += `<td class="${cls}"${rs}${cs}>${escapeHtml(val)}</td>`;
    }
    body += '</tr>';
  });

  return `<div class="xl-sheet"><div class="xl-sheet-name">${escapeHtml(
    name
  )}</div><table class="xl"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
}

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string)
  );
}
