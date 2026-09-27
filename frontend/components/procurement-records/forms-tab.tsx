"use client";

import { useState } from "react";
import { Check, ChevronDown, FileText, Info, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { btnPrimary } from "@/components/shell/page-header";
import type { Procurement } from "@/types/records";

const FORMS = [
  "GPPB Standard Form — Invitation to Bid (ITB)",
  "GPPB Standard Form — Bid Data Sheet (BDS)",
  "BAC Resolution (Recommending Award)",
  "Notice of Award",
  "Post-Qualification Checklist",
  "Abstract of Bids",
];

const PREFILL = [
  "Procurement title and reference number",
  "ABC / Budget",
  "Procurement mode",
  "End-User / Requesting Office",
  "Other available details from the record",
];

function StepNumber({ n }: { n: number }) {
  return (
    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sky text-[12.5px] font-bold text-brand">
      {n}
    </span>
  );
}

export function FormsTab({ procurement }: { procurement: Procurement }) {
  const [form, setForm] = useState(FORMS[0]);

  return (
    <div className="max-w-[1000px] space-y-5">
      <div className="flex items-center gap-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-sky">
          <FileText className="h-5 w-5 text-brand" />
        </span>
        <div>
          <h2 className="text-[19px] font-bold leading-tight text-navy">
            Form Generator
          </h2>
          <p className="mt-0.5 text-[13px] text-subtle">
            Draft standard procurement forms from the details on record for{" "}
            {procurement.ref}.
          </p>
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-line bg-white">
        <div className="px-6 py-5">
          <div className="flex items-start gap-3">
            <StepNumber n={1} />
            <div>
              <h3 className="text-[14px] font-bold text-navy">Select a Form</h3>
              <p className="mt-0.5 text-[12.5px] text-subtle">
                Choose a standard form to generate. The form will be pre-filled
                with this procurement&apos;s details.
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-5 lg:grid-cols-[1fr_340px] lg:pl-10">
            <label className="block self-start">
              <span className="sr-only">Select Form</span>
              <span className="relative block">
                <FileText className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-brand" />
                <select
                  value={form}
                  onChange={(event) => setForm(event.target.value)}
                  className="w-full appearance-none rounded-lg border border-line bg-white py-3 pl-10 pr-10 text-[13.5px] text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15"
                >
                  {FORMS.map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
              </span>
            </label>

            <div className="rounded-lg bg-sky px-4 py-3.5">
              <div className="flex items-start gap-2.5">
                <span className="mt-px grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand text-white">
                  <Info className="h-3 w-3" />
                </span>
                <div className="min-w-0">
                  <div className="text-[12.5px] font-bold text-navy">
                    Form will be pre-filled with:
                  </div>
                  <ul className="mt-2 space-y-1.5">
                    {PREFILL.map((item) => (
                      <li
                        key={item}
                        className="flex items-start gap-2 text-[12.5px] text-ink"
                      >
                        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t border-line px-6 py-5">
          <div className="flex items-start gap-3">
            <StepNumber n={2} />
            <div>
              <h3 className="text-[14px] font-bold text-navy">Generate</h3>
              <p className="mt-0.5 text-[12.5px] text-subtle">
                Click generate to create a draft form. Review the generated
                document before use.
              </p>
            </div>
          </div>
          <button
            onClick={() =>
              toast.info("Form generation is not available yet", {
                description: `${form} · ${procurement.ref}`,
              })
            }
            className={`${btnPrimary} ml-auto flex items-center gap-2 px-5 py-2.5`}
          >
            <Sparkles className="h-4 w-4" />
            Generate Form
          </button>
        </div>
      </section>
    </div>
  );
}
