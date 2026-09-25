"use client";

import { useRef, useState } from "react";
import { Check, FileText, Plus, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";

import { Modal, ModalFooter, inputCls } from "@/components/shell/modal";
import { btnGhost, btnPrimary } from "@/components/shell/page-header";
import { deleteDocument, uploadDocuments } from "@/lib/records-client";
import { formatDate } from "@/lib/format";
import {
  DOC_TYPES,
  type Procurement,
  type ProcurementDocument,
} from "@/types/records";

type Staged = { file: File; type: string };

export function DocumentsTab({
  procurement,
  onChange,
  onRunReview,
}: {
  procurement: Procurement;
  onChange: (updated: Procurement) => void;
  onRunReview: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [staged, setStaged] = useState<Staged[]>([]);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<ProcurementDocument | null>(null);
  const [removing, setRemoving] = useState<ProcurementDocument | null>(null);

  const finalized = procurement.status === "finalized";
  const documents = procurement.documents;
  const pageTotal = documents.reduce((sum, doc) => sum + doc.pages, 0);

  function openUpload() {
    setStaged([]);
    setUploadOpen(true);
  }

  function addFiles(files: FileList | null) {
    if (!files) return;
    const pdfs = Array.from(files).filter((file) =>
      file.name.toLowerCase().endsWith(".pdf")
    );
    if (pdfs.length !== files.length) {
      toast.error("Only PDF files can be attached");
    }
    setStaged((prev) => [
      ...prev,
      ...pdfs.map((file) => ({ file, type: "Other" })),
    ]);
  }

  async function commitUpload() {
    if (staged.length === 0) return;
    setBusy(true);
    try {
      onChange(
        await uploadDocuments(
          procurement.ref,
          staged.map((item) => item.file),
          staged.map((item) => item.type)
        )
      );
      const count = staged.length;
      setStaged([]);
      setUploadOpen(false);
      toast.success(`${count} document${count === 1 ? "" : "s"} uploaded`, {
        description: "Ready for AI review.",
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmRemove() {
    if (!removing) return;
    setBusy(true);
    try {
      onChange(await deleteDocument(procurement.ref, removing.id));
      toast.success("Document removed", { description: removing.name });
      setRemoving(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove it");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h2 className="text-[16px] font-semibold text-navy">
            Procurement Documents
          </h2>
          <p className="mt-1 text-[13px] text-subtle">
            Upload the documents associated with this procurement.
          </p>
        </div>
        {!finalized && (
          <button
            onClick={openUpload}
            className={`${btnPrimary} ml-auto flex items-center gap-2`}
          >
            <Plus className="h-4 w-4" />
            Upload Documents
          </button>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-line bg-white">
        {documents.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] text-left">
                <thead>
                  <tr className="border-b border-line bg-page text-[11px] font-semibold text-subtle">
                    <th className="px-5 py-3">Document Name</th>
                    <th className="px-5 py-3">Type</th>
                    <th className="px-5 py-3">Pages</th>
                    <th className="px-5 py-3">Uploaded</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      className="border-b border-line last:border-0 hover:bg-sky/40"
                    >
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-sky">
                            <FileText className="h-4 w-4 text-brand" />
                          </span>
                          <span className="text-[13px] font-medium">
                            {doc.name}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-[12.5px] text-subtle">
                        {doc.doc_type}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3.5 text-[12.5px] text-subtle">
                        {doc.pages} pages
                      </td>
                      <td className="whitespace-nowrap px-5 py-3.5 text-[12.5px] text-subtle">
                        {formatDate(doc.uploaded)}
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-compliant">
                          <Check className="h-3.5 w-3.5" />
                          Ready
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-3.5 text-right">
                        <button
                          onClick={() => setPreview(doc)}
                          className="text-[12px] font-semibold text-brand hover:text-navy"
                        >
                          Preview
                        </button>
                        {!finalized && (
                          <>
                            <span className="mx-2 text-line">·</span>
                            <button
                              onClick={() => setRemoving(doc)}
                              className="text-[12px] font-semibold text-critical hover:opacity-80"
                            >
                              Remove
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center gap-4 border-t border-line bg-page px-5 py-4">
              <p className="text-[12.5px] text-subtle">
                {documents.length} document{documents.length === 1 ? "" : "s"} ·{" "}
                {pageTotal} pages total
              </p>
              {!finalized && (
                <button onClick={onRunReview} className={`${btnPrimary} ml-auto`}>
                  {procurement.review_status === "done"
                    ? "Run AI Review again"
                    : "Run AI Review"}
                </button>
              )}
            </div>
          </>
        ) : (
          <div className="px-5 py-16 text-center">
            <UploadCloud className="mx-auto h-8 w-8 text-line" />
            <div className="mt-3 text-[14px] font-semibold">
              No documents uploaded
            </div>
            <p className="mt-1 text-[13px] text-subtle">
              Add the market study, TOR, specifications and supporting records.
            </p>
            {!finalized && (
              <button onClick={openUpload} className={`${btnPrimary} mt-4`}>
                Upload Documents
              </button>
            )}
          </div>
        )}
      </div>

      {/* --- upload --- */}
      <Modal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Upload Documents"
        description="PDF files, up to 25MB each."
      >
        <div className="px-6 py-5">
          <button
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              addFiles(event.dataTransfer.files);
            }}
            className="w-full rounded-lg border-2 border-dashed border-line bg-page px-6 py-8 text-center transition-colors hover:border-brand/40 hover:bg-sky"
          >
            <UploadCloud className="mx-auto h-7 w-7 text-brand" />
            <div className="mt-2 text-[13px] font-semibold">Select files</div>
            <div className="mt-0.5 text-[12px] text-subtle">
              Click to browse, or drop PDFs here
            </div>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            multiple
            hidden
            onChange={(event) => {
              addFiles(event.target.files);
              event.target.value = "";
            }}
          />

          {staged.length > 0 && (
            <div className="mt-4 space-y-2">
              <div className="text-[11px] font-semibold text-subtle">
                {staged.length} file{staged.length === 1 ? "" : "s"} selected
              </div>
              {staged.map((item, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3 rounded-md border border-line px-3 py-2"
                >
                  <FileText className="h-4 w-4 shrink-0 text-brand" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-medium">
                      {item.file.name}
                    </div>
                    <div className="text-[11px] text-subtle">
                      {Math.round(item.file.size / 1024)} KB
                    </div>
                  </div>
                  <select
                    value={item.type}
                    onChange={(event) =>
                      setStaged((prev) =>
                        prev.map((entry, i) =>
                          i === index
                            ? { ...entry, type: event.target.value }
                            : entry
                        )
                      )
                    }
                    className={`${inputCls} w-auto px-2 py-1 text-[12px]`}
                  >
                    {DOC_TYPES.map((type) => (
                      <option key={type}>{type}</option>
                    ))}
                  </select>
                  <button
                    onClick={() =>
                      setStaged((prev) => prev.filter((_, i) => i !== index))
                    }
                    aria-label={`Remove ${item.file.name}`}
                    className="text-subtle hover:text-critical"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <ModalFooter
          submitLabel={
            busy
              ? "Uploading…"
              : staged.length
                ? `Upload ${staged.length} document${staged.length === 1 ? "" : "s"}`
                : "Upload"
          }
          disabled={busy || staged.length === 0}
          onCancel={() => setUploadOpen(false)}
          onSubmit={commitUpload}
        />
      </Modal>

      {/* --- preview --- */}
      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={preview?.name ?? ""}
        description={
          preview
            ? `${preview.doc_type} · ${preview.pages} pages · uploaded ${formatDate(preview.uploaded)}`
            : undefined
        }
      >
        <div className="px-6 py-5">
          <div className="rounded-lg border border-line bg-page px-4 py-16 text-center">
            <FileText className="mx-auto h-7 w-7 text-line" />
            <p className="mt-2 text-[12.5px] text-subtle">
              A document viewer is not available yet.
            </p>
          </div>
        </div>
        <div className="flex justify-end rounded-b-xl border-t border-line bg-page px-6 py-4">
          <button onClick={() => setPreview(null)} className={btnGhost}>
            Close
          </button>
        </div>
      </Modal>

      {/* --- remove --- */}
      <Modal
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title="Remove document"
        description={removing?.name}
      >
        <div className="px-6 py-5 text-[13px] leading-relaxed">
          This removes {removing?.name} from {procurement.ref}. Findings that
          cite it will remain until the review is run again.
        </div>
        <ModalFooter
          submitLabel={busy ? "Removing…" : "Remove document"}
          tone="danger"
          disabled={busy}
          onCancel={() => setRemoving(null)}
          onSubmit={confirmRemove}
        />
      </Modal>
    </div>
  );
}
