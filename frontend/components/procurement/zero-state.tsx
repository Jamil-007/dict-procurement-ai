'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { FileUpload } from './file-upload';
import { VerdictData } from '@/types/procurement';

interface ZeroStateProps {
  onFilesSelect: (files: File[]) => void;
  onScenarioSelect: (verdict: VerdictData, scenarioName: string) => void;
}

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
    </motion.div>
  );
}
