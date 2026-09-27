import React from 'react';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import type { FormCatalogItem } from '@/types/forms';

interface FormChoiceProps {
  form: FormCatalogItem;
  isSelected: boolean;
  isRecommended: boolean;
  onToggle: () => void;
}

export function FormChoice({ form, isSelected, isRecommended, onToggle }: FormChoiceProps) {
  const isAnnex = form.group === 'B_annex';

  return (
    <div
      className={`flex gap-3 items-start border rounded-lg p-4 cursor-pointer transition-all bg-white hover:bg-zinc-50 ${
        isSelected ? 'border-black' : 'border-zinc-200 hover:border-zinc-300'
      }`}
      onClick={onToggle}
    >
      <div
        className={`w-[18px] h-[18px] rounded border flex-shrink-0 mt-0.5 grid place-items-center text-[11px] text-white transition-all ${
          isSelected
            ? 'bg-black border-black'
            : 'border-zinc-300'
        }`}
      >
        {isSelected && '✓'}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-sm">{form.name}</span>
          <span className="text-[11px] text-zinc-400 tracking-wide">
            {form.ext.replace('.', '').toUpperCase()}
          </span>
          {isRecommended && (
            <span className="text-[10.5px] font-semibold px-2 py-0.5 rounded-full bg-black text-white tracking-wide">
              Recommended
            </span>
          )}
          {isAnnex && (
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="inline-flex w-[15px] h-[15px] border border-zinc-300 rounded-full text-zinc-500 text-[10px] font-semibold items-center justify-center hover:text-black hover:border-zinc-500 transition-all"
                    onClick={(e) => e.stopPropagation()}
                  >
                    ?
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="max-w-[220px]">
                    Issued as a BLANK annex for the bidding documents. Only the project header is
                    stamped; the bidder completes, signs and notarizes it.
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
        <div className="text-zinc-600 text-[12.5px] mt-0.5">
          {getFormDescription(form.key)}
        </div>
      </div>
    </div>
  );
}

function getFormDescription(key: string): string {
  const descriptions: Record<string, string> = {
    ppmp: 'Project plan from the TOR — description, mode, schedule and budget.',
    market: 'Scoping checklist from the Market Study; reuses the Market Researcher agent.',
    app: 'Adds this project as a line in the agency-wide Annual Procurement Plan.',
    contract: 'Draft from the TOR — parties, scope and reference (price & supplier added post-award).',
    bidform: 'Blank annex for the bidding documents; only the project header is stamped.',
    price_local: 'Blank annex for the bidding documents; issued for bidder completion.',
    price_abroad: 'Blank annex for the bidding documents; issued for bidder completion.',
    bsd: 'Blank annex for the bidding documents; only the project header is stamped.',
    oss: 'Blank annex for the bidding documents; only the project header is stamped.',
    psd: 'Blank annex for the bidding documents; only the project header is stamped.',
  };
  return descriptions[key] || '';
}
