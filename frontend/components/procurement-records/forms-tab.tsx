"use client";

import { useState } from "react";
import { ArrowLeft, Check, FileText, Info } from "lucide-react";
import { toast } from "sonner";

import { FormGenerator } from "@/components/procurement/form-generator";
import { FormReview } from "@/components/procurement/form-review";
import { apiClient } from "@/lib/api-client";
import { formatPeso } from "@/lib/format";
import type { Procurement } from "@/types/records";
import type { FormKey } from "@/types/forms";

// The Procurement record only exposes already-uploaded document *metadata*
// (gcs_path, doc_type, etc.) — there are no local `File` blobs to hand to
// `apiClient.uploadForms()`, which is what `/forms/detect` needs to run
// against. Seeding detection straight from the record isn't possible without
// a backend change, so this tab falls back to the generator's manual
// selection mode (an empty/omitted `detectResult`) and surfaces the record's
// own fields as a reference panel so the officer can copy them into the
// generated form while reviewing.
const CONTEXT_FIELDS = [
  { label: "Title", value: (p: Procurement) => p.title },
  { label: "Reference No.", value: (p: Procurement) => p.ref },
  { label: "ABC", value: (p: Procurement) => formatPeso(p.abc) },
  { label: "Mode", value: (p: Procurement) => p.mode },
  { label: "End-User", value: (p: Procurement) => p.end_user },
];

export function FormsTab({ procurement }: { procurement: Procurement }) {
  const [starting, setStarting] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [formKeys, setFormKeys] = useState<FormKey[] | null>(null);

  const handleGenerate = async (selectedKeys: FormKey[]) => {
    if (selectedKeys.length === 0) return;
    try {
      setStarting(true);
      // No documents to seed the session with — create an empty one so the
      // selected forms can be generated and filled in on review.
      const res = await apiClient.uploadForms([]);
      setThreadId(res.thread_id);
      setFormKeys(selectedKeys);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start generation");
    } finally {
      setStarting(false);
    }
  };

  const reset = () => {
    setThreadId(null);
    setFormKeys(null);
  };

  if (threadId && formKeys) {
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

  return (
    <div className="max-w-[1100px] space-y-5">
      <div className="flex items-center gap-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-sky">
          <FileText className="h-5 w-5 text-brand" />
        </span>
        <div>
          <h2 className="text-[19px] font-bold leading-tight text-navy">
            Form Generator
          </h2>
          <p className="mt-0.5 text-[13px] text-subtle">
            Draft standard GPPB procurement forms for {procurement.ref}.
          </p>
        </div>
      </div>

      <div className="rounded-lg bg-sky px-4 py-3.5">
        <div className="flex items-start gap-2.5">
          <span className="mt-px grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand text-white">
            <Info className="h-3 w-3" />
          </span>
          <div className="min-w-0">
            <div className="text-[12.5px] font-bold text-navy">
              Use these details while filling in fields
            </div>
            <p className="mt-1 text-[12px] text-ink/70">
              This record&apos;s documents aren&apos;t detected automatically here —
              choose forms below, then copy these details into the generated
              fields on the review step.
            </p>
            <ul className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {CONTEXT_FIELDS.map(({ label, value }) => (
                <li
                  key={label}
                  className="flex items-start gap-2 text-[12.5px] text-ink"
                >
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />
                  <span>
                    <span className="font-semibold">{label}:</span>{" "}
                    {value(procurement) || "—"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <section className="rounded-xl border border-line bg-white p-6">
        <FormGenerator detectResult={null} onGenerate={handleGenerate} />
      </section>

      {starting && (
        <p className="text-[13px] text-subtle">Starting form generation…</p>
      )}
    </div>
  );
}
