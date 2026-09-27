'use client';

import React, { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { apiClient, triggerDownload, ExtractResponse } from '@/lib/api-client';
import type { FormKey } from '@/types/forms';
import type { FeedbackItem } from '@/types/feedback';
import { FeedbackControl } from './feedback-control';
import { DocumentPreview } from './document-preview';
import { useFeedbackCapture } from '@/hooks/use-feedback-capture';

interface FormReviewProps {
  threadId: string;
  formKeys: FormKey[];
}

const ANNEX_DISCLAIMER =
  'DRAFT — issued blank for completion by the bidder. Not an executed or notarized document.';

export function FormReview({ threadId, formKeys }: FormReviewProps) {
  const [extractedData, setExtractedData] = useState<ExtractResponse | null>(null);
  const [editedFields, setEditedFields] = useState<Record<FormKey, Record<string, string>>>({} as any);
  const { ratings, setRating, setNote, submit } = useFeedbackCapture();
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<FormKey | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    async function loadExtractedData() {
      try {
        setLoading(true);
        const data = await apiClient.extractForms(threadId, formKeys);
        setExtractedData(data);

        // Initialize edited fields. Composite/object fields (e.g. market activity_flags,
        // result_rows) are intentionally excluded from the editable overrides so they can
        // never render as "[object Object]" or be corrupted into invalid values.
        const initial: Record<string, Record<string, string>> = {};
        Object.entries(data).forEach(([key, formData]) => {
          const primitives: Record<string, string> = {};
          Object.entries(formData.fields || {}).forEach(([fieldName, value]) => {
            if (value === null || typeof value !== 'object') {
              primitives[fieldName] = value == null ? '' : String(value);
            }
          });
          initial[key] = primitives;
        });
        setEditedFields(initial as any);

        if (formKeys.length > 0 && !activeTab) {
          setActiveTab(formKeys[0]);
        }
      } catch (error) {
        console.error('Failed to extract forms:', error);
      } finally {
        setLoading(false);
      }
    }

    if (threadId && formKeys.length > 0) {
      loadExtractedData();
    }
  }, [threadId, formKeys]);

  const handleFieldChange = (formKey: FormKey, fieldName: string, value: string) => {
    setEditedFields((prev) => ({
      ...prev,
      [formKey]: {
        ...prev[formKey],
        [fieldName]: value,
      },
    }));
  };

  const captureFeedback = (keys: FormKey[]) => {
    const items: FeedbackItem[] = [];
    keys.forEach((key) => {
      const extracted = extractedData?.[key]?.fields || {};
      const edited = editedFields[key] || {};
      Object.entries(edited).forEach(([field, value]) => {
        const ai = extracted[field] == null ? '' : String(extracted[field]);
        if (value && value !== '[TBD]' && value !== ai) {
          items.push({ feature: 'forms', context_key: key, field_path: field,
            thread_id: threadId, signal_type: 'implicit', ai_value: ai, corrected_value: value });
        }
      });
      Object.entries(ratings[key] || {}).forEach(([field, r]) => {
        if (r.rating) {
          const ai = extracted[field] == null ? '' : String(extracted[field]);
          items.push({ feature: 'forms', context_key: key, field_path: field,
            thread_id: threadId, signal_type: 'explicit', rating: r.rating,
            note: r.note || null, ai_value: ai });
        }
      });
    });
    submit(items);
  };

  const downloadForm = async (formKey: FormKey) => {
    try {
      setDownloading(true);
      const overrides = {
        [formKey]: editedFields[formKey],
      };
      const result = await apiClient.generateForms(threadId, [formKey], overrides as any);
      captureFeedback([formKey]);
      triggerDownload(result.blob, result.filename);
    } catch (error) {
      console.error('Failed to download form:', error);
    } finally {
      setDownloading(false);
    }
  };

  const downloadAll = async () => {
    try {
      setDownloading(true);
      const overrides: any = {};
      formKeys.forEach((key) => {
        overrides[key] = editedFields[key];
      });
      const result = await apiClient.generateForms(threadId, formKeys, overrides);
      captureFeedback(formKeys);
      triggerDownload(result.blob, result.filename);
    } catch (error) {
      console.error('Failed to download all forms:', error);
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return <div className="text-zinc-500 text-sm py-4">Loading forms...</div>;
  }

  if (!extractedData || formKeys.length === 0) {
    return <div className="text-zinc-500 text-sm py-4">No forms to review</div>;
  }

  const currentFormData = activeTab && extractedData[activeTab];
  const isAnnex = currentFormData?.group === 'B_annex';
  const fields = activeTab && editedFields[activeTab];

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-500">Step 2 of 2</span>
        </div>
        <button
          onClick={downloadAll}
          disabled={downloading}
          className="px-[18px] py-[9px] text-sm font-medium rounded-md bg-black text-white hover:bg-zinc-900 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {downloading ? 'Downloading...' : 'Download all'}
        </button>
      </div>

      <Tabs value={activeTab || undefined} onValueChange={(v) => setActiveTab(v as FormKey)}>
        <TabsList className="w-full justify-start mb-6 overflow-x-auto flex-nowrap">
          {formKeys.map((key) => (
            <TabsTrigger key={key} value={key} className="capitalize">
              <span className={`w-[5px] h-[5px] rounded-full border ${
                editedFields[key] && Object.values(editedFields[key]).some((v) => v && v !== '[TBD]')
                  ? 'bg-zinc-600 border-zinc-600'
                  : 'border-zinc-400'
              } mr-2`} />
              {getFormDisplayName(key)}
            </TabsTrigger>
          ))}
        </TabsList>

        {formKeys.map((key) => (
          <TabsContent key={key} value={key}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="text-[11px] font-semibold tracking-wider uppercase text-zinc-400">
                      Edit fields
                    </div>
                    <span className="text-[11px] text-zinc-400">hover a field, or tap ⋯</span>
                  </div>
                </div>

                {isAnnex && (
                  <div className="text-xs text-zinc-600 bg-zinc-50 border border-zinc-200 border-l-[3px] border-l-zinc-400 rounded-lg p-3 mb-5">
                    {ANNEX_DISCLAIMER}
                  </div>
                )}

                {fields && Object.keys(fields).length > 0 ? (
                  <div className="flex flex-col">
                    {Object.entries(fields).map(([fieldName, value]) => (
                      <div key={fieldName} className="group mb-4">
                        <div className="flex items-start justify-between mb-2">
                          <label className="block text-[11px] font-semibold text-zinc-600 tracking-wide">
                            {formatFieldName(fieldName)}
                          </label>
                          <FeedbackControl
                            rating={ratings[key]?.[fieldName]?.rating || null}
                            note={ratings[key]?.[fieldName]?.note || ''}
                            onRate={(r) => setRating(key, fieldName, r)}
                            onNote={(n) => setNote(key, fieldName, n)}
                          />
                        </div>
                        <input
                          type="text"
                          value={value || ''}
                          onChange={(e) => handleFieldChange(key, fieldName, e.target.value)}
                          placeholder="[TBD]"
                          className={`w-full border rounded-md px-[11px] py-[9px] text-sm transition-all ${
                            value === '[TBD]' || !value
                              ? 'bg-zinc-50 text-zinc-600 border-zinc-200'
                              : 'bg-white text-black border-zinc-300'
                          } focus:outline-none focus:border-black`}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-zinc-600 py-5 border border-dashed border-zinc-300 rounded-lg text-center">
                    This form is issued as a blank annex — no fields to fill. Download and provide to
                    bidders.
                  </div>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="text-[11px] font-semibold tracking-wider uppercase text-zinc-400">
                    Preview
                  </div>
                  <button
                    onClick={() => downloadForm(key)}
                    disabled={downloading}
                    className="px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-300 bg-white hover:bg-zinc-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    Download this
                  </button>
                </div>

                <div className="border border-zinc-200 rounded-xl overflow-hidden bg-zinc-50 sticky top-32">
                  <div className="bg-white border-b border-zinc-200 px-4 py-3 text-xs font-medium flex items-center justify-between text-zinc-600">
                    <span>{getFormDisplayName(key)}.{getFormExtension(key)}</span>
                  </div>
                  <div className="p-4 max-h-[520px] overflow-auto">
                    <DocumentPreview
                      threadId={threadId}
                      formKey={key}
                      ext={getFormExtension(key) as 'docx' | 'xlsx'}
                      overrides={editedFields[key] || {}}
                      isAnnex={extractedData[key]?.group === 'B_annex'}
                    />
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function getFormDisplayName(key: string): string {
  const names: Record<string, string> = {
    ppmp: 'PPMP',
    market: 'Market Scoping',
    app: 'APP',
    contract: 'Contract',
    bidform: 'Bid Form',
    price_local: 'Price Schedule (PH)',
    price_abroad: 'Price Schedule (Abroad)',
    bsd: 'Bid Securing Declaration',
    oss: 'Omnibus Sworn Statement',
    psd: 'Performance Securing Declaration',
  };
  return names[key] || key;
}

function getFormExtension(key: string): string {
  const exts: Record<string, string> = {
    ppmp: 'xlsx',
    app: 'xlsx',
  };
  return exts[key] || 'docx';
}

function formatFieldName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}
