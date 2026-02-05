'use client';

import React from 'react';
import { FileCheck, AlertTriangle, DollarSign, CheckSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { VerdictData } from '@/types/procurement';

interface StarterChipsProps {
  onScenarioSelect: (verdict: VerdictData, scenarioName: string) => void;
}

// Starter scenarios removed - using real backend now
const STARTER_SCENARIOS: any[] = [];

const CHIP_ICONS = {
  'tor-compliance': FileCheck,
  'budget-risk': DollarSign,
  'liability-issues': AlertTriangle,
  'validate-requirements': CheckSquare,
};

export function StarterChips({ onScenarioSelect }: StarterChipsProps) {
  return (
    <div className="grid grid-cols-2 gap-3 w-full max-w-md mx-auto mb-8">
      {STARTER_SCENARIOS.map((scenario: any) => {
        const Icon = CHIP_ICONS[scenario.id as keyof typeof CHIP_ICONS];
        return (
          <Button
            key={scenario.id}
            variant="outline"
            className="h-auto py-4 px-4 flex flex-col items-start gap-2 border-2 border-gray-300 hover:border-black hover:bg-gray-50 smooth-transition rounded-xl"
            onClick={() => onScenarioSelect(scenario.verdict, scenario.label)}
          >
            <Icon className="h-5 w-5 text-black" />
            <span className="text-sm font-medium text-left text-black">{scenario.label}</span>
          </Button>
        );
      })}
    </div>
  );
}
