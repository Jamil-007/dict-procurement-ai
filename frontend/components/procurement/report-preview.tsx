'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, ChevronRight, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ReportSkeleton } from './report-skeleton';
import { VerdictData } from '@/types/procurement';
import { cn } from '@/lib/utils';

interface ReportPreviewProps {
  isLoading: boolean;
  verdictData: VerdictData | null;
  gammaLink: string | null;
  onGenerateReport?: () => void;
  onDeclineReport?: () => void;
  isGenerating?: boolean;
  showCTA?: boolean;
  onReset?: () => void;
}

export function ReportPreview({ isLoading, verdictData, gammaLink, onGenerateReport, onDeclineReport, isGenerating, showCTA, onReset }: ReportPreviewProps) {
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  if (isLoading) {
    return (
      <div className="h-full flex flex-col bg-white">
        {/* Header */}
        <div className="flex items-center justify-between p-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-black" />
            <div>
              <h2 className="font-semibold text-lg text-black">Generating Report</h2>
              <p className="text-sm text-gray-500">Please wait...</p>
            </div>
          </div>
        </div>

        {/* Loading Content */}
        <ReportSkeleton />
      </div>
    );
  }

  // If Gamma link is available, show iframe
  if (gammaLink) {
    return (
      <div className="h-full flex flex-col bg-white">
        {/* Header */}
        <div className="flex items-center justify-between p-4 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-black" />
            <div>
              <h2 className="font-semibold text-lg text-black">Gamma Report</h2>
              <p className="text-sm text-gray-500">Interactive Presentation</p>
            </div>
          </div>
        </div>

        {/* Gamma Iframe */}
        <div className="flex-1 overflow-hidden">
          <iframe
            src={gammaLink}
            className="w-full h-full border-0"
            title="Gamma Presentation"
            sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
          />
        </div>
      </div>
    );
  }

  if (!verdictData) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="h-full flex flex-col bg-white"
    >
      {/* Header */}
      {onReset && (
        <div className="flex items-center justify-end p-4 bg-white border-b border-gray-200 sticky top-0 z-10">
          <Button
            variant="outline"
            size="sm"
            className="rounded-full border-gray-300 hover:bg-gray-100 text-black"
            onClick={() => setShowResetConfirm(true)}
          >
            Analyze Another Document
          </Button>
        </div>
      )}

      {/* Report Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Title Section */}
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-black">{verdictData.title}</h1>
            <Badge
              variant="outline"
              className={cn(
                'text-base px-3 py-1 rounded-full',
                verdictData.status === 'PASS'
                  ? 'bg-black text-white border-black'
                  : 'bg-gray-700 text-white border-gray-700'
              )}
            >
              {verdictData.status}
            </Badge>
          </div>
          <p className="text-gray-600">
            Confidence Level: <span className="font-semibold text-black">{verdictData.confidence}%</span>
          </p>
        </div>

        <Separator className="bg-gray-200" />

        {/* Document Information */}
        <Card className="border-2 border-gray-200 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-lg text-black">Document Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Analysis Date:</span>
              <span className="font-medium text-black">{new Date().toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Document Type:</span>
              <span className="font-medium text-black">Procurement Terms of Reference</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Analysis Model:</span>
              <span className="font-medium text-black">Multi-Agent AI System v1.0</span>
            </div>
          </CardContent>
        </Card>

        {/* Executive Summary */}
        <Card className="border-2 border-gray-200 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-lg text-black">Executive Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-gray-700">
            <p>
              This procurement document has been analyzed using our multi-agent AI system,
              which evaluated compliance across multiple dimensions including budget alignment,
              regulatory requirements, and risk assessment.
            </p>
            <p>
              The analysis resulted in a <strong className="text-black">{verdictData.status}</strong> verdict with{' '}
              <strong className="text-black">{verdictData.confidence}% confidence</strong>, based on comprehensive
              evaluation of {verdictData.findings.length} major categories.
            </p>
          </CardContent>
        </Card>

        {/* Detailed Findings */}
        <Card className="border-2 border-gray-200 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-lg text-black">Detailed Findings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {verdictData.findings.map((finding, index) => (
              <div key={index} className="space-y-2">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-black">{finding.category}</h3>
                  <Badge
                    variant="outline"
                    className={cn(
                      'text-xs rounded-full',
                      finding.severity === 'high' && 'bg-black text-white border-black',
                      finding.severity === 'medium' && 'bg-gray-700 text-white border-gray-700',
                      finding.severity === 'low' && 'bg-gray-300 text-black border-gray-300'
                    )}
                  >
                    {finding.severity.toUpperCase()}
                  </Badge>
                </div>
                <ul className="list-disc list-inside space-y-1 text-sm text-gray-700 pl-4">
                  {finding.items.map((item, itemIndex) => (
                    <li key={itemIndex}>{item}</li>
                  ))}
                </ul>
                {index < verdictData.findings.length - 1 && <Separator className="mt-4 bg-gray-200" />}
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card className="border-2 border-gray-200 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-lg text-black">Recommendations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-700">
            {verdictData.status === 'PASS' ? (
              <>
                <p>✓ This procurement document meets all compliance requirements.</p>
                <p>✓ No critical issues were identified during the analysis.</p>
                <p>✓ The document is ready to proceed to the next stage.</p>
              </>
            ) : (
              <>
                <p>⚠ Address all high-severity findings before proceeding.</p>
                <p>⚠ Review medium-severity items for potential improvements.</p>
                <p>⚠ Consider re-submission after corrections are made.</p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Generate Report CTA */}
        {showCTA && onGenerateReport && onDeclineReport && (
          <Card className="border-2 border-gray-200 rounded-2xl">
            <CardContent className="pt-6 space-y-4">
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
                  className="flex-1 bg-black hover:bg-gray-800 rounded-full"
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
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-black rounded-full"
                  size="lg"
                >
                  No, Save Tokens
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Footer */}
        <div className="text-center text-xs text-gray-500 pt-6">
          <p>This report was generated by Procurement AI Analyst</p>
          <p>Powered by Multi-Agent AI Technology</p>
        </div>
      </div>

      {/* Reset Confirmation Modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowResetConfirm(false)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl"
          >
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="h-8 w-8 text-black" />
              </div>
              <h3 className="text-2xl font-bold text-black">Are you sure?</h3>
              <p className="text-gray-600">
                The current analysis results will not be stored. This action cannot be undone.
              </p>
              <div className="flex gap-3 w-full pt-2">
                <Button
                  onClick={() => {
                    setShowResetConfirm(false);
                    onReset?.();
                  }}
                  className="flex-1 bg-black hover:bg-gray-800 text-white rounded-full"
                  size="lg"
                >
                  Yes, Start Over
                </Button>
                <Button
                  onClick={() => setShowResetConfirm(false)}
                  variant="secondary"
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-black rounded-full"
                  size="lg"
                >
                  Cancel
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </motion.div>
  );
}
