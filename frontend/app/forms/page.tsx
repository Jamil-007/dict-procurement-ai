'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { FileUpload } from '@/components/procurement/file-upload';
import { FormGenerator } from '@/components/procurement/form-generator';
import { apiClient } from '@/lib/api-client';
import type { FormKey } from '@/types/forms';

export default function FormsPage() {
  const router = useRouter();
  const [threadId, setThreadId] = useState<string | null>(null);
  const [hasDocs, setHasDocs] = useState(false);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const startSession = async (files: File[]) => {
    setBusy(true);
    try {
      const res = await apiClient.uploadForms(files);
      setThreadId(res.thread_id);
      setHasDocs(res.has_docs);
      setFileNames(files.map((f) => f.name));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  const handleGenerate = (selectedKeys: FormKey[]) => {
    if (!threadId) {
      toast.error('No session available');
      return;
    }
    router.push(
      `/forms/review?session=${threadId}&forms=${selectedKeys.join(',')}`
    );
  };

  const reset = () => {
    setThreadId(null);
    setHasDocs(false);
    setFileNames([]);
  };

  return (
    <main className="mx-auto max-w-2xl px-5 py-16 pb-24">
      <h1 className="text-2xl font-bold tracking-tight text-zinc-900">
        Generate procurement forms
      </h1>
      <p className="mt-2 text-sm text-zinc-500">
        Upload your procurement documents to auto-fill GPPB forms — or continue
        without documents and fill a form in manually.
      </p>

      {/* Step 1: upload / start session */}
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-7">
        <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-zinc-100 text-[11px] font-bold text-zinc-700">
            1
          </span>
          Upload documents
        </div>

        {!threadId ? (
          <>
            <FileUpload onFilesSelect={startSession} disabled={busy} />
            <div className="mt-4">
              <button
                onClick={() => startSession([])}
                disabled={busy}
                className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-50 disabled:opacity-40"
              >
                Continue without documents
              </button>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-zinc-600">
              {hasDocs
                ? `Session ready with ${fileNames.length} document${
                    fileNames.length === 1 ? '' : 's'
                  }: ${fileNames.join(', ')}`
                : 'Session ready (no documents — fill fields manually in the next step).'}
            </p>
            <button
              onClick={reset}
              className="shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium text-zinc-500 transition-colors hover:text-zinc-900"
            >
              Change
            </button>
          </div>
        )}
      </section>

      {/* Step 2: choose + generate */}
      {threadId && (
        <section className="mt-5">
          <FormGenerator
            threadId={threadId}
            hasDocs={hasDocs}
            onGenerate={handleGenerate}
          />
        </section>
      )}
    </main>
  );
}
