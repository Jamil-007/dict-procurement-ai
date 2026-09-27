'use client';

import React, { useState, useEffect } from 'react';
import { FormChoice } from './form-choice';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api-client';
import type { FormCatalogItem, DetectResult, FormKey } from '@/types/forms';

interface FormGeneratorProps {
  threadId: string | null;
  hasDocs: boolean;
  onGenerate: (selectedKeys: FormKey[]) => void;
}

export function FormGenerator({ threadId, hasDocs, onGenerate }: FormGeneratorProps) {
  const [catalog, setCatalog] = useState<FormCatalogItem[]>([]);
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<FormKey>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadForms() {
      try {
        setLoading(true);
        const catalogData = await apiClient.getFormCatalog();
        setCatalog(catalogData);

        if (threadId) {
          const detection = await apiClient.detectForms(threadId);
          setDetectResult(detection);

          // Pre-select recommended forms
          const recommended = new Set<FormKey>();
          Object.entries(detection.forms).forEach(([key, info]) => {
            if (info.recommended) {
              recommended.add(key as FormKey);
            }
          });
          setSelectedKeys(recommended);
        }
      } catch (error) {
        console.error('Failed to load forms:', error);
      } finally {
        setLoading(false);
      }
    }

    loadForms();
  }, [threadId]);

  const toggleForm = (key: FormKey) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleGenerate = () => {
    onGenerate(Array.from(selectedKeys));
  };

  if (loading) {
    return (
      <div className="text-zinc-500 text-sm py-4">Loading form catalog...</div>
    );
  }

  // Group forms
  const groupA = catalog.filter((f) => f.group === 'A_rich');
  const groupB = catalog.filter((f) => f.group === 'B_annex');

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <span className="text-xs font-medium text-zinc-500">Step 1 of 2</span>
      </div>
      <div className="h-[3px] bg-zinc-100 rounded-full overflow-hidden mb-6">
        <span className="block h-full bg-black rounded-full transition-all duration-400" style={{ width: '50%' }} />
      </div>

      <div className="text-[19px] font-semibold tracking-tight flex items-center mb-6">
        Which forms do you want to generate?
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex w-[15px] h-[15px] border border-zinc-300 rounded-full text-zinc-500 text-[10px] font-semibold items-center justify-center hover:text-black hover:border-zinc-500 transition-all ml-2"
              >
                ?
              </button>
            </TooltipTrigger>
            <TooltipContent>
              <p className="max-w-[220px]">
                Forms matched to your uploads are pre-selected. You can generate any form and fill
                remaining fields on the next page.
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {groupA.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold tracking-wider uppercase text-zinc-400 mb-3 mt-6">
            Planning & contract
          </div>
          <div className="flex flex-col gap-2">
            {groupA.map((form) => (
              <FormChoice
                key={form.key}
                form={form}
                isSelected={selectedKeys.has(form.key)}
                isRecommended={detectResult?.forms[form.key]?.recommended || false}
                onToggle={() => toggleForm(form.key)}
              />
            ))}
          </div>
        </div>
      )}

      {groupB.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold tracking-wider uppercase text-zinc-400 mb-3 mt-6">
            Bidding-document annexes (issued blank)
          </div>
          <div className="flex flex-col gap-2">
            {groupB.map((form) => (
              <FormChoice
                key={form.key}
                form={form}
                isSelected={selectedKeys.has(form.key)}
                isRecommended={detectResult?.forms[form.key]?.recommended || false}
                onToggle={() => toggleForm(form.key)}
              />
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-between items-center mt-6 pt-5 border-t border-zinc-200">
        <span className="text-sm text-zinc-600">{selectedKeys.size} selected</span>
        <button
          onClick={handleGenerate}
          disabled={selectedKeys.size === 0}
          className="px-[18px] py-[9px] text-sm font-medium rounded-md bg-black text-white hover:bg-zinc-900 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          Generate
        </button>
      </div>
    </div>
  );
}
