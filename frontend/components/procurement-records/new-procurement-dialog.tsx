"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Field, Modal, ModalFooter } from "@/components/shell/modal";
import {
  SectionLabel,
  areaCls,
  inputCls,
} from "@/components/shell/page-header";
import {
  PROCUREMENT_MODES,
  PROCUREMENT_TYPES,
  type ProcurementCreate,
} from "@/types/records";

const FUNDS = ["GAA", "Trust Fund", "Special Account", "Continuing Appropriation"];

const EMPTY: ProcurementCreate = {
  title: "",
  abc: 0,
  mode: PROCUREMENT_MODES[0],
  fund: FUNDS[0],
  category: PROCUREMENT_TYPES[0],
  end_user: "",
};

export function NewProcurementDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (data: ProcurementCreate) => Promise<void>;
}) {
  const [form, setForm] = useState<ProcurementCreate>(EMPTY);
  const [abc, setAbc] = useState("");
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof ProcurementCreate>(
    key: K,
    value: ProcurementCreate[K]
  ) => setForm((prev) => ({ ...prev, [key]: value }));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.title.trim()) {
      toast.error("Give the procurement a title");
      return;
    }
    setSaving(true);
    try {
      await onCreate({
        ...form,
        title: form.title.trim(),
        // Accept "17,339,609.00" as typed.
        abc: Number(abc.replace(/[^\d.]/g, "")) || 0,
        category: form.category,
        end_user: form.end_user?.trim() || "Not specified",
      });
      setForm(EMPTY);
      setAbc("");
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create it");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New Procurement"
      description="Create a procurement record, then upload its documents."
      width="max-w-2xl"
    >
      <form onSubmit={handleSubmit}>
        <div className="space-y-4 px-6 py-5">
          <SectionLabel>PROCUREMENT INFORMATION</SectionLabel>

          <Field label="Procurement Title">
            <textarea
              rows={2}
              required
              className={areaCls}
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="Procurement of One (1) Year Subscription of the Cyber Risk Assessment and Baseline Scoring Tool"
              autoFocus
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="ABC">
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] text-subtle">
                  &#8369;
                </span>
                <input
                  required
                  inputMode="decimal"
                  className={`${inputCls} pl-7`}
                  value={abc}
                  onChange={(e) => setAbc(e.target.value)}
                  placeholder="17,339,609.00"
                />
              </div>
            </Field>

            <Field label="Procurement Mode">
              <select
                className={inputCls}
                value={form.mode}
                onChange={(e) => set("mode", e.target.value)}
              >
                {PROCUREMENT_MODES.map((mode) => (
                  <option key={mode}>{mode}</option>
                ))}
              </select>
            </Field>

            <Field label="Source of Fund">
              <select
                className={inputCls}
                value={form.fund}
                onChange={(e) => set("fund", e.target.value)}
              >
                {FUNDS.map((fund) => (
                  <option key={fund}>{fund}</option>
                ))}
              </select>
            </Field>

            <Field label="Procurement Type">
              <select
                className={inputCls}
                value={form.category}
                onChange={(e) => set("category", e.target.value)}
              >
                {PROCUREMENT_TYPES.map((type) => (
                  <option key={type}>{type}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="End-User / Requesting Office">
            <input
              className={inputCls}
              value={form.end_user}
              onChange={(e) => set("end_user", e.target.value)}
              placeholder="Emerging Technologies Group"
            />
          </Field>
        </div>

        <ModalFooter
          submitLabel={saving ? "Creating…" : "Create Procurement"}
          onCancel={onClose}
          disabled={saving}
        />
      </form>
    </Modal>
  );
}
