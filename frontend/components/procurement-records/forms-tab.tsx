"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, FileText, Loader2, UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { FormGenerator } from "@/components/procurement/form-generator";
import { FormReview } from "@/components/procurement/form-review";
import { apiClient } from "@/lib/api-client";
import { documentUrl, uploadDocuments } from "@/lib/records-client";
import type { Procurement, ProcurementDocument } from "@/types/records";
import type { FormKey, RefDetectResult } from "@/types/forms";

type Phase = "loading" | "select" | "upload-missing" | "preparing" | "review";

function computeMissing(detectResult: RefDetectResult | null, keys: FormKey[]): string[] {
  if (!detectResult) return [];
  const missing = new Set<string>();
  keys.forEach((key) => {
    (detectResult.forms[key]?.missing || []).forEach((docType) => missing.add(docType));
  });
  return Array.from(missing);
}

/** Re-downloads an already-uploaded procurement document as a `File` so it can
 * seed a forms session (`apiClient.uploadForms`) the same way a fresh upload
 * would, letting the record's Forms tab reuse the existing FormReview /
 * DocumentPreview extract-and-edit flow instead of a read-only dump. */
async function toFile(ref: string, doc: ProcurementDocument): Promise<File> {
  const response = await fetch(documentUrl(ref, doc.id, true));
  if (!response.ok) {
    throw new Error(`Could not read ${doc.name}`);
  }
  const blob = await response.blob();
  return new File([blob], doc.name, { type: blob.type || "application/pdf" });
}

export function FormsTab({
  procurement,
  onChange,
}: {
  procurement: Procurement;
  onChange: (updated: Procurement) => void;
}) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [detectResult, setDetectResult] = useState<RefDetectResult | null>(null);
  const [pendingKeys, setPendingKeys] = useState<FormKey[]>([]);
  const [missingDocTypes, setMissingDocTypes] = useState<string[]>([]);
  const [uploadingMissing, setUploadingMissing] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [formKeys, setFormKeys] = useState<FormKey[] | null>(null);

  // Run detection against the record's own (already-persisted) documents as
  // soon as the tab opens, so recommendations reflect what's really on file.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await apiClient.detectFormsForRef(procurement.ref);
        if (!cancelled) {
          setDetectResult(result);
          setPhase("select");
        }
      } catch (err) {
        if (!cancelled) {
          toast.error(
            err instanceof Error ? err.message : "Could not detect forms for this record"
          );
          setDetectResult(null);
          setPhase("select");
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [procurement.ref]);

  const prepareAndGenerate = async (keys: FormKey[], docs: ProcurementDocument[]) => {
    setPhase("preparing");
    try {
      const files = docs.length > 0 ? await Promise.all(docs.map((doc) => toFile(procurement.ref, doc))) : [];
      const res = await apiClient.uploadForms(files);
      setThreadId(res.thread_id);
      setFormKeys(keys);
      setPhase("review");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start generation");
      setPhase(missingDocTypes.length > 0 ? "upload-missing" : "select");
    }
  };

  const handleGenerate = (selectedKeys: FormKey[]) => {
    if (selectedKeys.length === 0) return;
    setPendingKeys(selectedKeys);
    const missing = computeMissing(detectResult, selectedKeys);
    if (missing.length === 0) {
      void prepareAndGenerate(selectedKeys, procurement.documents);
    } else {
      setMissingDocTypes(missing);
      setPhase("upload-missing");
    }
  };

  const handleMissingUpload = async (files: File[]) => {
    if (files.length === 0) return;
    setUploadingMissing(true);
    try {
      const updated = await uploadDocuments(procurement.ref, files);
      onChange(updated);
      const refreshed = await apiClient.detectFormsForRef(procurement.ref);
      setDetectResult(refreshed);
      const stillMissing = computeMissing(refreshed, pendingKeys);
      setMissingDocTypes(stillMissing);
      if (stillMissing.length === 0) {
        await prepareAndGenerate(pendingKeys, updated.documents);
      } else {
        toast.info(`Still missing: ${stillMissing.join(", ")}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadingMissing(false);
    }
  };

  const generateAnyway = () => {
    void prepareAndGenerate(pendingKeys, procurement.documents);
  };

  const reset = () => {
    setPhase("select");
    setPendingKeys([]);
    setMissingDocTypes([]);
    setThreadId(null);
    setFormKeys(null);
  };

  if (phase === "review" && threadId && formKeys) {
    return (
      <div className="max-w-[1200px] space-y-4">
        <button
          onClick={reset}
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-subtle hover:text-brand"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Choose different forms
        </button>
        <FormReview threadId={threadId} formKeys={formKeys} />
      </div>
    );
  }

  if (phase === "loading" || phase === "preparing") {
    return (
      <div className="flex max-w-[1100px] items-center gap-2.5 rounded-xl border border-line bg-white px-6 py-10 text-[13px] text-subtle">
        <Loader2 className="h-4 w-4 animate-spin" />
        {phase === "loading"
          ? "Checking this record's documents…"
          : "Preparing your documents for generation…"}
      </div>
    );
  }

  if (phase === "upload-missing") {
    return (
      <div className="max-w-[1100px] space-y-5">
        <button
          onClick={() => setPhase("select")}
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-subtle hover:text-brand"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to form selection
        </button>

        <div className="flex items-center gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-sky">
            <UploadCloud className="h-5 w-5 text-brand" />
          </span>
          <div>
            <h2 className="text-[19px] font-bold leading-tight text-navy">
              A few documents are missing
            </h2>
            <p className="mt-0.5 text-[13px] text-subtle">
              The selected form{pendingKeys.length === 1 ? "" : "s"} usually draw from documents
              this record doesn&apos;t have yet.
            </p>
          </div>
        </div>

        <div className="rounded-lg bg-sky px-4 py-3.5">
          <div className="text-[12.5px] font-bold text-navy">Missing document types</div>
          <ul className="mt-2 flex flex-wrap gap-2">
            {missingDocTypes.map((docType) => (
              <li
                key={docType}
                className="rounded-full bg-white px-3 py-1 text-[12px] font-medium text-ink"
              >
                {docType}
              </li>
            ))}
          </ul>
        </div>

        <MissingUploadDropzone
          disabled={uploadingMissing}
          onFilesSelect={(files) => void handleMissingUpload(files)}
        />

        {uploadingMissing && (
          <p className="flex items-center gap-2 text-[13px] text-subtle">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Uploading and re-checking…
          </p>
        )}

        <div className="flex items-center justify-between border-t border-line pt-4">
          <p className="text-[12.5px] text-subtle">
            Uploaded documents are saved to this record and appear on the Documents tab.
          </p>
          <button
            onClick={generateAnyway}
            disabled={uploadingMissing}
            className="text-[13px] font-semibold text-brand hover:text-navy disabled:opacity-50"
          >
            Generate anyway (leave fields blank)
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1100px] space-y-5">
      <div className="flex items-center gap-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-sky">
          <FileText className="h-5 w-5 text-brand" />
        </span>
        <div>
          <h2 className="text-[19px] font-bold leading-tight text-navy">Form Generator</h2>
          <p className="mt-0.5 text-[13px] text-subtle">
            Draft standard GPPB procurement forms for {procurement.ref}, matched to this
            record&apos;s own documents.
          </p>
        </div>
      </div>

      <section className="rounded-xl border border-line bg-white p-6">
        <FormGenerator detectResult={detectResult} onGenerate={handleGenerate} />
      </section>
    </div>
  );
}

function MissingUploadDropzone({
  onFilesSelect,
  disabled,
}: {
  onFilesSelect: (files: File[]) => void;
  disabled?: boolean;
}) {
  return (
    <label
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-line bg-sky/40 px-6 py-8 text-center transition-colors hover:border-brand/40 hover:bg-sky ${
        disabled ? "pointer-events-none opacity-50" : ""
      }`}
    >
      <UploadCloud className="h-6 w-6 text-brand" />
      <div className="text-[13px] font-semibold text-navy">Click to browse for the missing documents</div>
      <div className="text-[12px] text-subtle">PDF files only</div>
      <input
        type="file"
        accept="application/pdf"
        multiple
        hidden
        disabled={disabled}
        onChange={(event) => {
          const files = event.target.files ? Array.from(event.target.files) : [];
          event.target.value = "";
          if (files.length > 0) onFilesSelect(files);
        }}
      />
    </label>
  );
}
