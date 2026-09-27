'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Check, FileText, Loader2 } from 'lucide-react';
import { FileUpload } from '@/components/procurement/file-upload';
import { FormGenerator } from '@/components/procurement/form-generator';
import { FormHint } from '@/components/procurement/form-hint';
import { apiClient } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import type { DetectResult, FormKey } from '@/types/forms';

// Replicate the backend's sanitize_filename so a locally-selected File can be
// matched to the server's saved (sanitized) name for size display.
function sanitizeName(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, '_').replace(/^\.+/, '');
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function FormsPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [, setHasDocs] = useState(false);
  const [serverFiles, setServerFiles] = useState<string[]>([]);
  const [detecting, setDetecting] = useState(false);
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);
  const [selectedCount, setSelectedCount] = useState(0);
  const [busy, setBusy] = useState(false);

  const startSession = async (selected: File[]) => {
    setBusy(true);
    setFiles(selected);
    try {
      const res = await apiClient.uploadForms(selected);
      setThreadId(res.thread_id);
      setHasDocs(res.has_docs);
      setServerFiles(res.filenames);
      setDetecting(true);
      const det = await apiClient.detectForms(res.thread_id);
      setDetectResult(det);
      setDetecting(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed');
      setDetecting(false);
    } finally {
      setBusy(false);
    }
  };

  const handleGenerate = async (selectedKeys: FormKey[]) => {
    if (selectedKeys.length === 0) return;
    try {
      // If the officer didn't upload anything, create an empty session so the
      // selected forms can be generated blank and filled in on the review page.
      let tid = threadId;
      if (!tid) {
        setBusy(true);
        const res = await apiClient.uploadForms([]);
        tid = res.thread_id;
        setThreadId(tid);
      }
      router.push(`/forms/review?session=${tid}&forms=${selectedKeys.join(',')}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start generation');
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setFiles([]);
    setThreadId(null);
    setHasDocs(false);
    setServerFiles([]);
    setDetecting(false);
    setDetectResult(null);
  };

  // Size lookup: match a local File to a server (sanitized) filename.
  const sizeFor = (serverName: string): string | null => {
    const match = files.find((f) => sanitizeName(f.name) === serverName);
    return match ? formatSize(match.size) : null;
  };

  // First detected doc type for a given server filename.
  const typeFor = (serverName: string): string => {
    const doc = detectResult?.documents?.find((d) => d.filename === serverName);
    return doc?.doc_types?.[0] || 'Other';
  };

  const step1Done = Boolean(detectResult) && !detecting;

  return (
    <main className="mx-auto max-w-2xl px-5 py-16 pb-24">
      <h1 className="text-2xl font-bold tracking-tight text-zinc-900">
        Generate procurement forms
      </h1>
      <p className="mt-2 text-sm text-zinc-500">
        Upload your procurement documents to auto-fill the matching GPPB forms — or
        pick a form below to fill in manually.
      </p>

      {/* Step 1: upload / detection */}
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-7">
        <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          <span
            className={cn(
              'inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold transition-colors duration-300',
              step1Done
                ? 'bg-zinc-900 text-white'
                : 'bg-zinc-100 text-zinc-700'
            )}
          >
            1
          </span>
          Upload documents
        </div>

        {!threadId ? (
          <>
            <FileUpload onFilesSelect={startSession} disabled={busy} />
            <FormHint />
          </>
        ) : (
          <div className="animate-in fade-in duration-300">
            <div className="flex flex-col gap-2">
              {serverFiles.map((name) => {
                const size = sizeFor(name);
                return (
                  <div
                    key={name}
                    className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 animate-in fade-in duration-300"
                  >
                    <div className="grid h-[30px] w-[30px] flex-shrink-0 place-items-center rounded-lg bg-zinc-100 text-zinc-500">
                      <FileText className="h-[15px] w-[15px]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-medium text-zinc-900">
                        {name}
                      </div>
                      <div className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-zinc-400">
                        {size && <span>{size} ·</span>}
                        {detecting ? (
                          <span className="flex items-center gap-1.5">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            detecting…
                          </span>
                        ) : (
                          <span className="flex items-center gap-1.5">
                            <Check className="h-3 w-3 text-[#16a34a]" strokeWidth={3} />
                            <span className="font-medium text-zinc-600">
                              {typeFor(name)}
                            </span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {detecting && (
              <div className="mt-4 flex items-center gap-2 border-t border-zinc-100 pt-4 text-[13px] text-zinc-500 animate-in fade-in duration-300">
                <Loader2 className="h-3 w-3 animate-spin" />
                Detecting document types…
              </div>
            )}

            <div className="mt-4">
              <button
                onClick={reset}
                className="text-[13px] font-medium text-zinc-500 underline underline-offset-2 transition-colors hover:text-zinc-900"
              >
                Change
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Step 2: choose + generate — always available */}
      <section className="mt-5 rounded-2xl border border-zinc-200 bg-white p-7">
        <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          <span
            className={cn(
              'inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold transition-colors duration-300',
              selectedCount > 0
                ? 'bg-zinc-900 text-white'
                : 'bg-zinc-100 text-zinc-700'
            )}
          >
            2
          </span>
          Choose forms to generate
        </div>
        <FormGenerator
          detectResult={detectResult}
          onGenerate={handleGenerate}
          onSelectionChange={setSelectedCount}
        />
      </section>
    </main>
  );
}
