"use client";

import { useEffect, useRef, useState } from "react";
import { BookMarked, FileText, Search, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageHeader, btnGhost, btnPrimary, inputCls } from "@/components/shell/page-header";
import { Modal, ModalFooter, Field } from "@/components/shell/modal";
import { knowledgeUrl, listKnowledge } from "@/lib/records-client";
import { apiClient, APIError } from "@/lib/api-client";
import type { KnowledgeEntry } from "@/types/records";
import { cn } from "@/lib/utils";

export default function KnowledgeHubPage() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [total, setTotal] = useState(0);
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<KnowledgeEntry | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  // Bumped after a successful upload so both fetch effects below re-run and
  // the new entry shows up without a full page reload.
  const [refreshKey, setRefreshKey] = useState(0);

  // Per-category counts come from one unfiltered fetch, so the chips keep
  // showing the full library size while a filter is applied.
  useEffect(() => {
    listKnowledge()
      .then((data) => {
        setCategories(data.categories);
        setTotal(data.total);
        const tally: Record<string, number> = {};
        data.entries.forEach((entry) => {
          tally[entry.category] = (tally[entry.category] ?? 0) + 1;
        });
        setCounts(tally);
      })
      .catch(() => undefined);
  }, [refreshKey]);

  // Filtering happens on the server, so keystrokes are debounced.
  const [query, setQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listKnowledge({
      category: category === "all" ? undefined : category,
      search: query || undefined,
    })
      .then((data) => {
        if (cancelled) return;
        setEntries(data.entries);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Could not load references"
          );
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [category, query, refreshKey]);

  const chips = [
    { key: "all", label: "All", count: total },
    ...categories.map((c) => ({ key: c, label: c, count: counts[c] ?? 0 })),
  ];

  return (
    <div className="w-full px-7 py-6">
      <PageHeader
        title="Knowledge Hub"
        subtitle="Central repository of procurement laws, policies, issuances, forms, and reference materials."
      >
        <button
          onClick={() => setUploadOpen(true)}
          className={cn(btnPrimary, "inline-flex items-center gap-1.5")}
        >
          <Upload className="h-4 w-4" />
          Upload
        </button>
      </PageHeader>

      <div className="mb-5 flex flex-col gap-3 lg:flex-row">
        <label className="relative block w-full lg:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search the Knowledge Hub"
            className="w-full rounded-md border border-line bg-white py-2 pl-9 pr-3 text-[13px] focus:border-brand focus:outline-none"
          />
        </label>

        <div className="flex-1 overflow-x-auto">
          <div className="flex min-w-max gap-2 pb-1">
            {chips.map((chip) => (
              <button
                key={chip.key}
                onClick={() => setCategory(chip.key)}
                className={cn(
                  "whitespace-nowrap rounded-full border px-3.5 py-1.5 text-[12px] font-medium transition-colors",
                  category === chip.key
                    ? "border-navy bg-navy text-white"
                    : "border-line bg-white text-subtle hover:border-brand hover:text-brand"
                )}
              >
                {chip.label}
                <span
                  className={cn(
                    "ml-1.5",
                    category === chip.key ? "text-white/60" : "text-subtle/60"
                  )}
                >
                  {chip.count}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-white">
        {loading && (
          <div className="px-5 py-14 text-center text-[13px] text-subtle">
            Loading references…
          </div>
        )}

        {!loading && error && (
          <div className="px-5 py-14 text-center text-[13px] text-red-600">
            {error}
          </div>
        )}

        {!loading && !error && entries.length === 0 && (
          <div className="px-5 py-14 text-center text-[13px] text-subtle">
            No reference material matches this search.
          </div>
        )}

        {!loading &&
          !error &&
          entries.map((entry) => (
            <div
              key={entry.id}
              className="flex flex-col gap-3 px-5 py-4 hover:bg-sky/40 sm:flex-row sm:items-center"
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-sky">
                <BookMarked className="h-4 w-4 text-brand" />
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2.5">
                  <span className="text-[13.5px] font-semibold text-ink">
                    {entry.title}
                  </span>
                  <span className="text-[12px] text-subtle">
                    {entry.subtitle}
                  </span>
                </div>
                <div className="mt-1 text-[11.5px] text-subtle">
                  {[
                    entry.category,
                    entry.doc_type,
                    entry.pages ? `${entry.pages} pages` : null,
                    entry.date,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              </div>

              <button
                onClick={() => setPreview(entry)}
                className={cn(btnGhost, "shrink-0 self-start sm:self-auto")}
              >
                View document
              </button>
            </div>
          ))}
      </div>

      <p className="mt-3 text-[12px] text-subtle">
        {entries.length} of {total} references
      </p>

      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={preview?.title ?? ""}
        description={preview?.subtitle}
        width="max-w-xl"
      >
        {preview && (
          <>
            <div className="px-6 py-5">
              <div className="flex flex-wrap gap-x-6 gap-y-2 border-b border-line pb-4 text-[12px] text-subtle">
                <span>
                  <span className="font-medium text-ink">Category</span> ·{" "}
                  {preview.category}
                </span>
                <span>
                  <span className="font-medium text-ink">Type</span> ·{" "}
                  {preview.doc_type || "—"}
                </span>
                <span>
                  <span className="font-medium text-ink">Date</span> ·{" "}
                  {preview.date || "—"}
                </span>
                <span>
                  <span className="font-medium text-ink">Pages</span> ·{" "}
                  {preview.pages || "—"}
                </span>
              </div>

              <p className="mt-4 text-[13.5px] leading-relaxed">
                {preview.excerpt}
              </p>

              {preview.gcs_path ? (
                <iframe
                  src={knowledgeUrl(preview.id, true)}
                  title={preview.title}
                  className="mt-4 h-[55vh] w-full rounded-lg border border-line bg-page"
                />
              ) : (
                <div className="mt-4 rounded-lg border border-line bg-page px-4 py-8 text-center">
                  <FileText className="mx-auto h-6 w-6 text-line" />
                  <p className="mt-2 text-[12.5px] text-subtle">
                    The full text of this reference has not been added to the
                    library yet.
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 rounded-b-xl border-t border-line bg-page px-6 py-4">
              <button onClick={() => setPreview(null)} className={btnGhost}>
                Close
              </button>
              {preview.gcs_path ? (
                <a
                  href={knowledgeUrl(preview.id)}
                  download={`${preview.id}.pdf`}
                  className={btnPrimary}
                >
                  Download
                </a>
              ) : (
                <button
                  onClick={() =>
                    toast.info("Not in the library yet", {
                      description: `${preview.title} has no document attached.`,
                    })
                  }
                  className={btnPrimary}
                >
                  Download
                </button>
              )}
            </div>
          </>
        )}
      </Modal>

      <UploadKnowledgeModal
        open={uploadOpen}
        categories={categories}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => setRefreshKey((key) => key + 1)}
      />
    </div>
  );
}

function UploadKnowledgeModal({
  open,
  categories,
  onClose,
  onUploaded,
}: {
  open: boolean;
  categories: string[];
  onClose: () => void;
  onUploaded: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset the form each time the modal opens so a previous upload's values
  // don't linger, and default the category to the first one on the page.
  useEffect(() => {
    if (!open) return;
    setFile(null);
    setTitle("");
    setCategory(categories[0] ?? "");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [open, categories]);

  const canSubmit = Boolean(file) && title.trim().length > 0 && category.length > 0;

  async function handleSubmit() {
    if (!file || !canSubmit || submitting) return;
    setSubmitting(true);
    try {
      const result = await apiClient.uploadKnowledge({
        file,
        title: title.trim(),
        category,
      });
      onClose();
      onUploaded();
      toast.success("Reference uploaded", {
        description: result.searchable
          ? `${result.entry.title} is now searchable by the AI.`
          : `${result.entry.title} was added, but no text could be extracted — it won't be used by the AI yet.`,
      });
    } catch (err) {
      toast.error("Upload failed", {
        description:
          err instanceof APIError || err instanceof Error
            ? err.message
            : "Could not upload the document.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Upload reference"
      description="Add a document to the Knowledge Hub. It's indexed for AI Review immediately."
      width="max-w-lg"
    >
      <div className="space-y-4 px-6 py-5">
        <Field label="File" hint="PDF only.">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className={inputCls}
          />
        </Field>

        <Field label="Title">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. RA 12009 Implementing Rules and Regulations"
            className={inputCls}
          />
        </Field>

        <Field label="Category">
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className={inputCls}
          >
            {categories.length === 0 && <option value="">No categories yet</option>}
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <ModalFooter
        submitLabel={submitting ? "Uploading…" : "Upload"}
        onCancel={onClose}
        onSubmit={handleSubmit}
        disabled={!canSubmit || submitting}
      />
    </Modal>
  );
}
