"use client";

import { useEffect, useState } from "react";
import { BookMarked, FileText, Search } from "lucide-react";
import { toast } from "sonner";

import { PageHeader, btnGhost, btnPrimary } from "@/components/shell/page-header";
import { Modal } from "@/components/shell/modal";
import { listKnowledge } from "@/lib/records-client";
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
  }, []);

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
  }, [category, query]);

  const chips = [
    { key: "all", label: "All", count: total },
    ...categories.map((c) => ({ key: c, label: c, count: counts[c] ?? 0 })),
  ];

  return (
    <div className="max-w-[1160px] px-7 py-6">
      <PageHeader
        title="Knowledge Hub"
        subtitle="Central repository of procurement laws, policies, issuances, forms, and reference materials."
      />

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

              <div className="mt-4 rounded-lg border border-line bg-page px-4 py-8 text-center">
                <FileText className="mx-auto h-6 w-6 text-line" />
                <p className="mt-2 text-[12.5px] text-subtle">
                  A document viewer is not available yet.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 rounded-b-xl border-t border-line bg-page px-6 py-4">
              <button onClick={() => setPreview(null)} className={btnGhost}>
                Close
              </button>
              <button
                onClick={() =>
                  toast.info("Download not available yet", {
                    description: `${preview.title}.pdf`,
                  })
                }
                className={btnPrimary}
              >
                Download
              </button>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
