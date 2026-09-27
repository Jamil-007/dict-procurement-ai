"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Modal, ModalFooter } from "@/components/shell/modal";
import { totalFindings } from "@/components/shell/status-pill";
import { deleteProcurement } from "@/lib/records-client";
import type { Procurement } from "@/types/records";

export function DeleteProcurementDialog({
  procurement,
  onClose,
  onDeleted,
}: {
  procurement: Procurement | null;
  onClose: () => void;
  onDeleted: (ref: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  if (!procurement) return null;

  const documentCount = procurement.documents.length;
  const findingCount = totalFindings(procurement.finding_counts);

  async function handleDelete() {
    if (!procurement) return;
    setBusy(true);
    try {
      await deleteProcurement(procurement.ref);
      onDeleted(procurement.ref);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete it");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Delete procurement?"
      description={procurement.ref}
    >
      <div className="space-y-3 px-6 py-5 text-[13px] leading-relaxed">
        <p className="font-semibold">{procurement.title}</p>
        <p>
          This removes the record together with its {documentCount} document
          {documentCount === 1 ? "" : "s"}
          {procurement.review_status === "done" && findingCount > 0
            ? `, its ${findingCount} finding${findingCount === 1 ? "" : "s"} and the final report`
            : ""}
          .
        </p>
        <p className="text-subtle">
          The uploaded files are deleted too. This cannot be undone.
        </p>
      </div>
      <ModalFooter
        submitLabel={busy ? "Deleting…" : "Delete procurement"}
        tone="danger"
        onCancel={onClose}
        onSubmit={handleDelete}
        disabled={busy}
      />
    </Modal>
  );
}
