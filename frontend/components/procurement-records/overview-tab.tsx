"use client";

import { useState } from "react";
import { FileText, UserCheck } from "lucide-react";
import { toast } from "sonner";

import { Field, inputCls } from "@/components/shell/modal";
import { btnGhost, btnPrimary } from "@/components/shell/page-header";
import {
  SEVERITY_BAR,
  SEVERITY_KEYS,
  severityLabel,
  totalFindings,
} from "@/components/shell/status-pill";
import { patchProcurement } from "@/lib/records-client";
import { formatDate, formatPeso } from "@/lib/format";
import {
  PROCUREMENT_MODES,
  PROCUREMENT_TYPES,
  type Procurement,
} from "@/types/records";

export function OverviewTab({
  procurement,
  onChange,
  onRunReview,
  onOpenReview,
}: {
  procurement: Procurement;
  onChange: (updated: Procurement) => void;
  onRunReview: () => void;
  onOpenReview: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(procurement);
  const [saving, setSaving] = useState(false);

  const finalized = procurement.status === "finalized";
  const reviewed = procurement.review_status === "done";
  const counts = procurement.finding_counts;
  const total = totalFindings(counts);

  async function save() {
    setSaving(true);
    try {
      onChange(
        await patchProcurement(procurement.ref, {
          title: form.title,
          abc: form.abc,
          mode: form.mode,
          fund: form.fund,
          category: form.category,
          end_user: form.end_user,
        })
      );
      setEditing(false);
      toast.success("Details saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  const rows: { label: string; value: string }[] = [
    { label: "Reference Number", value: procurement.ref },
    { label: "Procurement Title", value: procurement.title },
    { label: "ABC", value: formatPeso(procurement.abc) },
    { label: "Procurement Mode", value: procurement.mode },
    { label: "Source of Fund", value: procurement.fund || "—" },
    { label: "Procurement Type", value: procurement.category || "—" },
    { label: "End-User", value: procurement.end_user || "—" },
    { label: "Created", value: formatDate(procurement.created) },
    { label: "Last Updated", value: formatDate(procurement.updated) },
  ];

  return (
    <div className="grid items-start gap-5 lg:grid-cols-3">
      <section className="rounded-xl border border-line bg-white lg:col-span-2">
        <h2 className="flex items-center gap-3 rounded-t-xl border-b border-line bg-page px-5 py-3 text-[13px] font-semibold text-navy">
          Procurement Details
          {!finalized && !editing && (
            <button
              onClick={() => {
                setForm(procurement);
                setEditing(true);
              }}
              className="ml-auto text-[12px] font-semibold text-brand hover:text-navy"
            >
              Edit
            </button>
          )}
        </h2>

        {editing ? (
          <div className="space-y-4 px-5 py-5">
            <Field label="Procurement Title">
              <input
                className={inputCls}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="ABC">
                <input
                  className={inputCls}
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.abc}
                  onChange={(e) => setForm({ ...form, abc: Number(e.target.value) })}
                />
              </Field>
              <Field label="Procurement Mode">
                <select
                  className={inputCls}
                  value={form.mode}
                  onChange={(e) => setForm({ ...form, mode: e.target.value })}
                >
                  {PROCUREMENT_MODES.map((mode) => (
                    <option key={mode}>{mode}</option>
                  ))}
                </select>
              </Field>
              <Field label="Source of Fund">
                <input
                  className={inputCls}
                  value={form.fund}
                  onChange={(e) => setForm({ ...form, fund: e.target.value })}
                />
              </Field>
              <Field label="Procurement Type">
                <select
                  className={inputCls}
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                >
                  {PROCUREMENT_TYPES.map((type) => (
                    <option key={type}>{type}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="End-User">
              <input
                className={inputCls}
                value={form.end_user}
                onChange={(e) => setForm({ ...form, end_user: e.target.value })}
              />
            </Field>
            <div className="flex gap-2">
              <button onClick={save} disabled={saving} className={btnPrimary}>
                {saving ? "Saving…" : "Save changes"}
              </button>
              <button onClick={() => setEditing(false)} className={btnGhost}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <dl className="px-5 py-2">
            {rows.map((row) => (
              <div
                key={row.label}
                className="flex flex-col border-b border-line py-2.5 last:border-0 sm:flex-row sm:gap-6"
              >
                <dt className="shrink-0 text-[12px] font-semibold text-subtle sm:w-52">
                  {row.label}
                </dt>
                <dd className="text-[13px] leading-relaxed">{row.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="rounded-xl border border-line bg-white">
        <h2 className="rounded-t-xl border-b border-line bg-page px-5 py-3 text-[13px] font-semibold text-navy">
          Review Summary
        </h2>
        <div className="px-5 py-5">
          {reviewed ? (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-[30px] font-bold leading-none tabular-nums text-navy">
                  {total}
                </span>
                <span className="text-[13px] text-subtle">
                  finding{total === 1 ? "" : "s"} identified
                </span>
              </div>

              <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-line">
                {SEVERITY_KEYS.map((key) => (
                  <div
                    key={key}
                    className={SEVERITY_BAR[key]}
                    style={{ width: `${(counts[key] / (total || 1)) * 100}%` }}
                  />
                ))}
              </div>

              <dl className="mt-4 space-y-2.5">
                {SEVERITY_KEYS.map((key) => (
                  <div key={key} className="flex items-center gap-2.5 text-[13px]">
                    <span
                      className={`h-2 w-2 rounded-full ${SEVERITY_BAR[key]}`}
                    />
                    {severityLabel(key)}
                    <span className="ml-auto font-semibold tabular-nums">
                      {counts[key]}
                    </span>
                  </div>
                ))}
                <div className="flex items-center gap-2.5 border-t border-line pt-2.5 text-[13px]">
                  <FileText className="h-3.5 w-3.5 text-subtle" />
                  Documents
                  <span className="ml-auto font-semibold tabular-nums">
                    {procurement.documents.length}
                  </span>
                </div>
                <div className="flex items-center gap-2.5 text-[13px]">
                  <UserCheck className="h-3.5 w-3.5 text-subtle" />
                  Reviewed by BAC
                  <span className="ml-auto font-semibold tabular-nums">
                    {procurement.decided_count}
                  </span>
                </div>
              </dl>

              <button
                onClick={onOpenReview}
                className={`${btnGhost} mt-5 w-full`}
              >
                Open AI Review
              </button>
            </>
          ) : (
            <>
              <p className="text-[13px] leading-relaxed text-subtle">
                No AI review has been run for this procurement. The review reads
                the uploaded documents and lists points for the BAC to verify
                across five dimensions.
              </p>
              <dl className="mt-4 space-y-2 text-[13px]">
                <div className="flex">
                  <dt className="text-subtle">Documents uploaded</dt>
                  <dd className="ml-auto font-semibold tabular-nums">
                    {procurement.documents.length}
                  </dd>
                </div>
              </dl>
              <button
                onClick={onRunReview}
                disabled={procurement.documents.length === 0}
                className={`${btnPrimary} mt-5 w-full`}
              >
                Run AI Review
              </button>
              {procurement.documents.length === 0 && (
                <p className="mt-2 text-center text-[11.5px] text-subtle">
                  Upload documents first.
                </p>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
