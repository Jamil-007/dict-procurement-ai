"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader, btnPrimary } from "@/components/shell/page-header";
import { NewProcurementDialog } from "@/components/procurement-records/new-procurement-dialog";
import { DeleteProcurementDialog } from "@/components/procurement-records/delete-procurement-dialog";
import { createProcurement, listProcurements } from "@/lib/records-client";
import { formatPeso } from "@/lib/format";
import type { Procurement, ProcurementCreate } from "@/types/records";
import { cn } from "@/lib/utils";

const statusChip = (status: Procurement["status"]) =>
  status === "finalized"
    ? "bg-green-50 text-green-700 border-green-200"
    : "bg-sky text-brand border-line";

/** "ICT / Software · 4 documents · 14 findings (2 critical · 7 warnings)" */
function metaLine(item: Procurement) {
  const parts = [
    item.category || "Uncategorised",
    `${item.documents.length} document${item.documents.length === 1 ? "" : "s"}`,
  ];

  if (item.review_status === "done") {
    const { critical, warning } = item.finding_counts;
    const total = critical + warning + item.finding_counts.compliant;
    parts.push(
      `${total} finding${total === 1 ? "" : "s"} (${critical} critical · ${warning} warning${warning === 1 ? "" : "s"})`
    );
  } else if (item.review_status === "processing") {
    parts.push("review in progress");
  } else {
    parts.push("review not yet run");
  }

  return parts.join(" · ");
}

export default function AllItemsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Procurement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Procurement | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await listProcurements());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load items");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate(data: ProcurementCreate) {
    const created = await createProcurement(data);
    toast.success("Procurement created", { description: created.ref });
    router.push(`/items/${created.ref}`);
  }

  const open = (ref: string) => router.push(`/items/${ref}`);

  return (
    <div className="max-w-[1160px] px-7 py-6">
      <PageHeader
        title="All Items"
        subtitle="Manage procurement records and review their documents using AI."
      >
        <button
          onClick={() => setCreating(true)}
          className={cn(btnPrimary, "flex items-center gap-2")}
        >
          <Plus className="h-4 w-4" />
          New Procurement
        </button>
      </PageHeader>

      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-left">
            <thead>
              <tr className="border-b border-line bg-page text-[11px] font-semibold text-subtle">
                <th className="px-5 py-3">Reference</th>
                <th className="px-5 py-3">Procurement</th>
                <th className="px-5 py-3 text-right">ABC</th>
                <th className="px-5 py-3">Mode</th>
                <th className="px-5 py-3">Status</th>
                <th className="whitespace-nowrap px-5 py-3">Last Updated</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="px-5 py-14 text-center text-[13px] text-subtle">
                    Loading procurements…
                  </td>
                </tr>
              )}

              {!loading && error && (
                <tr>
                  <td colSpan={7} className="px-5 py-14 text-center text-[13px] text-red-600">
                    {error}{" "}
                    <button onClick={load} className="underline underline-offset-2">
                      Try again
                    </button>
                  </td>
                </tr>
              )}

              {!loading && !error && items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-14 text-center text-[13px] text-subtle">
                    No procurement records yet. Create one to start attaching
                    documents.
                  </td>
                </tr>
              )}

              {items.map((item) => (
                <tr
                  key={item.ref}
                  onClick={() => open(item.ref)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") open(item.ref);
                  }}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-sky/50 focus:bg-sky/50 focus:outline-none"
                >
                  <td className="whitespace-nowrap px-5 py-4 align-top text-[12.5px] font-semibold text-brand">
                    {item.ref}
                  </td>
                  <td className="px-5 py-4 align-top">
                    <div className="max-w-[420px] text-[13px] font-medium leading-snug">
                      {item.title}
                    </div>
                    <div className="mt-1 text-[11.5px] text-subtle">
                      {metaLine(item)}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-right align-top text-[13px] tabular-nums">
                    {formatPeso(item.abc)}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 align-top text-[13px] text-subtle">
                    {item.mode}
                  </td>
                  <td className="px-5 py-4 align-top">
                    <span
                      className={cn(
                        "inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize",
                        statusChip(item.status)
                      )}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 align-top text-[13px] text-subtle">
                    {item.updated}
                  </td>
                  <td className="px-5 py-4 text-right align-top">
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        setDeleting(item);
                      }}
                      aria-label={`Delete ${item.ref}`}
                      title="Delete"
                      className="inline-grid h-8 w-8 place-items-center rounded-md text-subtle transition-colors hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <NewProcurementDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreate={handleCreate}
      />

      <DeleteProcurementDialog
        procurement={deleting}
        onClose={() => setDeleting(null)}
        onDeleted={(ref) => {
          setItems((prev) => prev.filter((p) => p.ref !== ref));
          setDeleting(null);
          toast.success("Procurement deleted", { description: ref });
        }}
      />
    </div>
  );
}
