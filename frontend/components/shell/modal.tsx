"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

import { btnDanger, btnGhost, btnPrimary } from "@/components/shell/page-header";

/**
 * Plain modal matching `openModal()` in html-proto/ai-analyst.html. The project
 * has no dialog primitive and the MVP needs several, so keep it small rather
 * than pulling in another dependency.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  icon,
  width = "max-w-lg",
  height,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  /** Optional glyph to the left of the title, for dialogs that carry weight. */
  icon?: React.ReactNode;
  width?: string;
  /**
   * Caps the dialog's height, e.g. "max-h-[80vh]". The header and footer stay
   * put and the body between them scrolls, so a long dialog never runs past
   * the viewport. The body has to opt in with `flex-1 overflow-y-auto`.
   */
  height?: string;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:items-center">
      <div className="fixed inset-0 bg-navy/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`relative my-8 w-full ${width} ${
          height ? `flex flex-col ${height}` : ""
        } rounded-xl border border-line bg-white shadow-xl`}
      >
        <div className="flex shrink-0 items-start gap-4 border-b border-line px-6 pb-4 pt-5">
          {icon}
          <div className="min-w-0">
            <h2 className="text-[16px] font-semibold text-navy">{title}</h2>
            {description && (
              <p className="mt-0.5 text-[12.5px] text-subtle">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="ml-auto text-subtle hover:text-ink"
          >
            <X className="h-[18px] w-[18px]" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Footer bar: Cancel on the left of the primary action, tinted background. */
export function ModalFooter({
  submitLabel,
  tone = "primary",
  onCancel,
  onSubmit,
  disabled,
}: {
  submitLabel: string;
  tone?: "primary" | "danger";
  onCancel: () => void;
  onSubmit?: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex shrink-0 justify-end gap-2 rounded-b-xl border-t border-line bg-page px-6 py-4">
      <button type="button" onClick={onCancel} className={btnGhost}>
        Cancel
      </button>
      <button
        type={onSubmit ? "button" : "submit"}
        onClick={onSubmit}
        disabled={disabled}
        className={tone === "danger" ? btnDanger : btnPrimary}
      >
        {submitLabel}
      </button>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-semibold text-ink">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[12px] text-subtle">{hint}</span>}
    </label>
  );
}

export { inputCls, areaCls } from "@/components/shell/page-header";
