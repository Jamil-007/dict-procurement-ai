'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { FileText, Info, ListChecks, ScanSearch, Sparkles } from 'lucide-react';
import { FileUpload } from './file-upload';
import { VerdictData } from '@/types/procurement';

interface ZeroStateProps {
  onFilesSelect: (files: File[]) => void;
  onScenarioSelect: (verdict: VerdictData, scenarioName: string) => void;
}

const STEPS = [
  { icon: FileText, label: 'Extract key information from the document' },
  { icon: ScanSearch, label: 'Check compliance with RA 12009, IRR, and issuances' },
  { icon: ListChecks, label: 'Identify inconsistencies and potential issues' },
  { icon: Sparkles, label: 'Generate a detailed analysis and recommendations' },
];

export function ZeroState({ onFilesSelect, onScenarioSelect }: ZeroStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="mx-auto flex w-full max-w-2xl flex-col items-center justify-center py-10"
    >
      <div className="text-center">
        <h2 className="text-2xl font-bold text-navy">
          Procurement Document Analysis
        </h2>
        <p className="mx-auto mt-2 max-w-md text-[13.5px] leading-relaxed text-subtle">
          Upload a procurement document to get an AI-powered analysis. The
          system will identify key information, check compliance, and flag
          potential issues.
        </p>
      </div>

      <div className="mt-8 w-full">
        <FileUpload onFilesSelect={onFilesSelect} />
      </div>

      <div className="mt-6 w-full rounded-xl border border-line bg-sky/60 px-5 py-4">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-navy">
          <Info className="h-4 w-4 text-brand" />
          What happens next?
        </div>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">
          {STEPS.map((step, index) => (
            <div key={step.label} className="flex items-start gap-2.5">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand text-[11px] font-semibold text-white">
                {index + 1}
              </span>
              <p className="text-[12px] leading-snug text-subtle">
                {step.label}
              </p>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
