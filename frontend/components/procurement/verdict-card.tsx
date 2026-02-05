'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, AlertTriangle, Info, ChevronRight } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { VerdictData, FindingSeverity } from '@/types/procurement';
import { cn } from '@/lib/utils';

interface VerdictCardProps {
  verdict: VerdictData;
  onGenerateReport: () => void;
  onDeclineReport: () => void;
  isGenerating?: boolean;
  showCTA?: boolean;
}

const cardVariants = {
  hidden: { opacity: 0, scale: 0.95 },
  show: {
    opacity: 1,
    scale: 1,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 30,
    },
  },
};

const getSeverityIcon = (severity: FindingSeverity) => {
  switch (severity) {
    case 'high':
      return <XCircle className="h-4 w-4 text-black" />;
    case 'medium':
      return <AlertTriangle className="h-4 w-4 text-gray-700" />;
    case 'low':
      return <Info className="h-4 w-4 text-gray-500" />;
  }
};

const getSeverityColor = (severity: FindingSeverity): string => {
  switch (severity) {
    case 'high':
      return 'bg-black text-white border-black';
    case 'medium':
      return 'bg-gray-700 text-white border-gray-700';
    case 'low':
      return 'bg-gray-300 text-black border-gray-300';
  }
};

const getSeverityLabel = (severity: FindingSeverity): string => {
  switch (severity) {
    case 'high':
      return 'Critical Risk';
    case 'medium':
      return 'Moderate Risk';
    case 'low':
      return 'Minor Issue';
  }
};

export function VerdictCard({
  verdict,
  onGenerateReport,
  onDeclineReport,
  isGenerating,
  showCTA = true,
}: VerdictCardProps) {
  const isPassing = verdict.status === 'PASS';

  return (
    <motion.div variants={cardVariants} initial="hidden" animate="show" className="w-full my-4">
      <Card className="shadow-lg border-2 border-gray-200 rounded-3xl">
        {/* Header Section */}
        <CardHeader className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                {isPassing ? (
                  <CheckCircle className="h-8 w-8 text-black" />
                ) : (
                  <XCircle className="h-8 w-8 text-black" />
                )}
                <Badge
                  variant="outline"
                  className={cn(
                    'text-base font-bold px-4 py-1.5 rounded-full',
                    isPassing
                      ? 'bg-black text-white border-black'
                      : 'bg-gray-700 text-white border-gray-700'
                  )}
                >
                  {verdict.status}
                </Badge>
              </div>
              <CardTitle className="text-2xl mb-2 text-black">{verdict.title}</CardTitle>
              <CardDescription className="text-base text-gray-600">
                Analysis completed with{' '}
                <span className="font-semibold text-black">{verdict.confidence}% confidence</span>
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        {/* Findings Section */}
        <CardContent className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Detailed Findings
            </h3>
            <Accordion type="multiple" defaultValue={verdict.findings.map((_, i) => `finding-${i}`)} className="w-full">
              {verdict.findings.map((finding, index) => (
                <AccordionItem key={index} value={`finding-${index}`} className="border-2 border-gray-200 rounded-2xl mb-2">
                  <AccordionTrigger className="px-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      {getSeverityIcon(finding.severity)}
                      <span className="font-medium text-black">{finding.category}</span>
                      <Badge variant="outline" className={cn('ml-2 border rounded-full', getSeverityColor(finding.severity))}>
                        {getSeverityLabel(finding.severity)}
                      </Badge>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-4 pb-4">
                    <ul className="space-y-2">
                      {finding.items.map((item, itemIndex) => (
                        <li key={itemIndex} className="flex items-start gap-2 text-sm text-black">
                          <ChevronRight className="h-4 w-4 mt-0.5 text-gray-500 shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </CardContent>

        {showCTA && (
          <>
            <Separator className="bg-gray-200" />

            {/* CTA Section */}
            <CardFooter className="flex-col items-stretch space-y-4 pt-6">
              <div className="space-y-2">
                <h3 className="text-base font-semibold text-black">
                  Generate Formal PDF Report?
                </h3>
                <p className="text-sm text-gray-600">
                  Create a comprehensive PDF report.
                </p>
              </div>

              <div className="flex gap-3 w-full">
                <Button
                  onClick={onGenerateReport}
                  disabled={isGenerating}
                  className="flex-1 bg-black hover:bg-gray-800 smooth-transition rounded-full"
                  size="lg"
                >
                  {isGenerating ? (
                    <>
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        className="mr-2"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </motion.div>
                      Generating...
                    </>
                  ) : (
                    'Yes, Generate Report'
                  )}
                </Button>
                <Button
                  onClick={onDeclineReport}
                  disabled={isGenerating}
                  variant="secondary"
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-black smooth-transition rounded-full"
                  size="lg"
                >
                  No, Save Tokens
                </Button>
              </div>
            </CardFooter>
          </>
        )}
      </Card>
    </motion.div>
  );
}
