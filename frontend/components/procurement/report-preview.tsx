'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, ChevronRight, AlertTriangle, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ReportSkeleton } from './report-skeleton';
import { FindingDetailCard } from './finding-detail';
import { VerdictData } from '@/types/procurement';
import { cn } from '@/lib/utils';
import { jsPDF } from 'jspdf';

// Format text with bold markdown
const formatText = (text: string) => {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
};

// Node names as the router emits them, in the user's words.
const CHECKER_LABELS: Record<string, string> = {
  rule_checks: 'Rule compliance',
  consistency_checks: 'Cross-document consistency',
  spec_validator: 'Specification review',
  lcca_analyzer: 'Life-cycle cost',
  market_researcher: 'Market research',
  sustainability_analyst: 'Sustainability',
  domestic_preference_checker: 'Tatak Pinoy preference',
  modality_advisor: 'Modality advisory',
};

const checkerLabel = (name: string) =>
  CHECKER_LABELS[name] ?? name.replace(/_/g, ' ');

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

  const handleDownloadPDF = () => {
    if (!verdictData) return;

    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 20;
    let yPos = 20;

    // Title
    doc.setFontSize(20);
    doc.setFont('helvetica', 'bold');
    doc.text('PROCUREMENT DOCUMENT ANALYSIS', margin, yPos);
    yPos += 10;

    // Metadata
    doc.setFontSize(12);
    doc.setFont('helvetica', 'normal');
    doc.text(`Status: ${verdictData.status}`, margin, yPos);
    yPos += 7;
    doc.text(`Confidence: ${verdictData.confidence}%`, margin, yPos);
    yPos += 7;
    doc.text(`Analysis Date: ${new Date().toLocaleDateString()}`, margin, yPos);
    yPos += 7;
    if (verdictData.summary) {
      const s = verdictData.summary;
      doc.text(
        `Checks: ${s.total} run, ${s.passed} passed, ${s.failed} flagged, ${s.skipped} not verified`,
        margin,
        yPos
      );
      yPos += 7;
    }
    yPos += 5;

    // Which documents this verdict is about -- a report that names its inputs
    // can be re-run and disputed; one that does not, cannot.
    if (verdictData.documents?.length) {
      doc.setFontSize(14);
      doc.setFont('helvetica', 'bold');
      doc.text('Documents Reviewed', margin, yPos);
      yPos += 8;
      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      verdictData.documents.forEach((d) => {
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
        const lines = doc.splitTextToSize(
          `• ${d.file} — ${d.label || d.doc_type} (${Math.round((d.confidence ?? 0) * 100)}% match)`,
          pageWidth - margin * 2 - 5
        );
        lines.forEach((line: string) => {
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(line, margin + 5, yPos);
          yPos += 6;
        });
      });
      yPos += 6;
    }

    // Title of report
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    const titleLines = doc.splitTextToSize(verdictData.title, pageWidth - margin * 2);
    titleLines.forEach((line: string) => {
      doc.text(line, margin, yPos);
      yPos += 7;
    });
    yPos += 8;

    // Executive Summary
    doc.setFontSize(16);
    doc.text('Executive Summary', margin, yPos);
    yPos += 10;

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    const summaryText = `This procurement document has been analyzed using our multi-agent AI system, which evaluated compliance across multiple dimensions including budget alignment, regulatory requirements, and risk assessment. The analysis resulted in a ${verdictData.status} verdict with ${verdictData.confidence}% confidence, based on comprehensive evaluation of ${verdictData.findings.length} major categories.`;
    const summaryLines = doc.splitTextToSize(summaryText, pageWidth - margin * 2);
    summaryLines.forEach((line: string) => {
      if (yPos > 270) {
        doc.addPage();
        yPos = 20;
      }
      doc.text(line, margin, yPos);
      yPos += 6;
    });
    yPos += 12;

    // Findings
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.text('Detailed Findings', margin, yPos);
    yPos += 10;

    verdictData.findings.forEach((finding, index) => {
      if (yPos > 270) {
        doc.addPage();
        yPos = 20;
      }

      doc.setFontSize(12);
      doc.setFont('helvetica', 'bold');
      doc.text(`${index + 1}. ${finding.category} [${finding.severity.toUpperCase()}]`, margin, yPos);
      yPos += 7;

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);

      // The downloaded report is what gets attached to a COA response, so it
      // carries the citation and the page reference, not just the sentence.
      const bullets: string[] =
        finding.details && finding.details.length > 0
          ? finding.details.map((d) => {
              const where = d.evidence
                ?.map((e) => `${e.document}${e.page ? ` p.${e.page}` : ''}`)
                .join('; ');
              const authority = d.authority
                ? ` [${d.authority.citation}${d.authority.unverified ? ' — unverified' : ''}]`
                : '';
              return `${d.detail}${where ? ` (${where})` : ''}${authority}`;
            })
          : finding.items;

      bullets.forEach((item) => {
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
        const lines = doc.splitTextToSize(`• ${item}`, pageWidth - margin * 2 - 5);
        lines.forEach((line: string) => {
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(line, margin + 5, yPos);
          yPos += 6;
        });
        yPos += 2; // Extra spacing between items
      });
      yPos += 3;
    });

    // Recommendations
    if (yPos > 250) {
      doc.addPage();
      yPos = 20;
    }
    yPos += 10;
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.text('Recommendations', margin, yPos);
    yPos += 10;

    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    if (verdictData.status === 'PASS') {
      const passRecommendations = [
        'This procurement document meets all compliance requirements.',
        'No critical issues were identified during the analysis.',
        'The document is ready to proceed to the next stage.'
      ];
      passRecommendations.forEach(rec => {
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
        const lines = doc.splitTextToSize(`• ${rec}`, pageWidth - margin * 2);
        lines.forEach((line: string) => {
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(line, margin, yPos);
          yPos += 6;
        });
        yPos += 2;
      });
    } else {
      const failRecommendations = [
        'Address all high-severity findings before proceeding.',
        'Review medium-severity items for potential improvements.',
        'Consider re-submission after corrections are made.'
      ];
      failRecommendations.forEach(rec => {
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
        const lines = doc.splitTextToSize(`• ${rec}`, pageWidth - margin * 2);
        lines.forEach((line: string) => {
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
          doc.text(line, margin, yPos);
          yPos += 6;
        });
        yPos += 2;
      });
    }

    // Footer
    if (yPos > 260) {
      doc.addPage();
      yPos = 20;
    }
    yPos += 15;
    doc.setFontSize(9);
    doc.setFont('helvetica', 'italic');
    doc.text('Report generated by Procurement AI Analyst', margin, yPos);
    yPos += 5;
    doc.text('Powered by Multi-Agent AI Technology', margin, yPos);

    doc.save(`procurement-analysis-${new Date().toISOString().split('T')[0]}.pdf`);
  };

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

  const documents = verdictData.documents ?? [];
  const checkersRun = verdictData.checkers_run ?? [];
  const summary = verdictData.summary;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="h-full flex flex-col bg-white"
    >
      {/* Header */}
      {onReset && (
        <div className="flex items-center justify-between p-4 bg-white border-b border-gray-200 sticky top-0 z-10">
          <Button
            variant="outline"
            size="sm"
            className="rounded-full border-gray-300 hover:bg-gray-100 text-black"
            onClick={handleDownloadPDF}
          >
            <Download className="h-4 w-4 mr-2" />
            Download Report
          </Button>
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
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-bold text-black break-words">{verdictData.title}</h1>
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

        {/* Documents reviewed. The detected type is shown per file because the
            router picks its checkers from it -- if a document was misread, the
            user needs to see that here rather than wonder why a check is
            missing. */}
        <Card className="border-2 border-gray-200 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-lg text-black">
              Documents Reviewed
              {documents.length > 0 && (
                <span className="ml-2 text-sm font-normal text-gray-500">
                  {documents.length}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {documents.length > 0 ? (
              documents.map((doc, index) => (
                <div
                  key={index}
                  className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-gray-100 pb-2 last:border-0 last:pb-0"
                >
                  <span className="min-w-0 break-all font-medium text-black">
                    {doc.file}
                  </span>
                  <span className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-800">
                      {doc.label || doc.doc_type}
                    </span>
                    <span>{Math.round((doc.confidence ?? 0) * 100)}% match</span>
                    {doc.total_pages ? (
                      <span>
                        {doc.pages_read ?? doc.total_pages}/{doc.total_pages} pp
                      </span>
                    ) : null}
                    {doc.ingest_source === 'ocr' && (
                      <span className="text-gray-500">scanned · OCR</span>
                    )}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-gray-600">
                No document details were recorded for this analysis.
              </p>
            )}
            <div className="flex justify-between pt-1">
              <span className="text-gray-600">Analysis Date:</span>
              <span className="font-medium text-black">{new Date().toLocaleDateString()}</span>
            </div>
            {checkersRun.length > 0 && (
              <div className="flex flex-wrap justify-between gap-2">
                <span className="text-gray-600">Checks Applied:</span>
                <span className="text-right font-medium text-black">
                  {checkersRun.map(checkerLabel).join(', ')}
                </span>
              </div>
            )}
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
            {/* How much was actually checked. "No findings" over 3 checks and
                "no findings" over 169 checks are not the same result, and the
                verdict alone cannot tell them apart. */}
            {summary && (
              <div className="flex flex-wrap gap-2 pt-1">
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-800">
                  {summary.total} check{summary.total === 1 ? '' : 's'} run
                </span>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-800">
                  {summary.passed} passed
                </span>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-800">
                  {summary.failed} flagged
                </span>
                {summary.skipped > 0 && (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs text-amber-900">
                    {summary.skipped} not verified
                  </span>
                )}
              </div>
            )}
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
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-semibold text-black break-words">{finding.category}</h3>
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
                {/* Rule and consistency findings carry evidence, citations and
                    a comparison. The advisory agents carry prose only, so they
                    keep the plain list. */}
                {finding.details && finding.details.length > 0 ? (
                  <div className="space-y-2">
                    {finding.details.map((detail, detailIndex) => (
                      <FindingDetailCard
                        key={detail.rule_id ?? detailIndex}
                        finding={detail}
                      />
                    ))}
                  </div>
                ) : (
                  <ul className="list-disc list-inside space-y-1 text-sm text-gray-700 pl-4">
                    {finding.items.map((item, itemIndex) => (
                      <li key={itemIndex} className="break-words">{formatText(item)}</li>
                    ))}
                  </ul>
                )}
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
                  Generate Action Items
                </h3>
                <p className="text-sm text-gray-600">
                  Get concise steps to fix HIGH severity issues and pass procurement compliance.
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
                      Preparing Action Items...
                    </>
                  ) : (
                    'Generate Action Items'
                  )}
                </Button>
                <Button
                  onClick={onDeclineReport}
                  disabled={isGenerating}
                  variant="secondary"
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-black rounded-full"
                  size="lg"
                >
                  Skip for Now
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
