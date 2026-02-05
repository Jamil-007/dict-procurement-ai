'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { FileUpload } from './file-upload';
import { VerdictData } from '@/types/procurement';

interface ZeroStateProps {
  onFileSelect: (file: File) => void;
  onScenarioSelect: (verdict: VerdictData, scenarioName: string) => void;
}

export function ZeroState({ onFileSelect, onScenarioSelect }: ZeroStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="flex flex-col items-center justify-center min-h-[60vh] space-y-8"
    >
      <div className="text-center space-y-3 mb-4">
        <h2 className="text-3xl font-bold text-black">
          Procurement Document Analysis
        </h2>
      </div>

      <div className="w-full max-w-lg">
        <FileUpload onFileSelect={onFileSelect} />
      </div>
    </motion.div>
  );
}
