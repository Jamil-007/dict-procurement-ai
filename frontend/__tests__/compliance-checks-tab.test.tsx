import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ComplianceChecksTab } from '@/components/procurement-records/compliance-checks-tab';
import type {
  CheckerInfo,
  Finding,
  Procurement,
  Severity,
} from '@/types/records';

vi.mock('@/lib/records-client', () => ({
  listCheckers: vi.fn(),
  listCheckFindings: vi.fn(),
  runChecks: vi.fn(),
  patchFinding: vi.fn(),
  addComment: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  }),
}));

import {
  listCheckers,
  listCheckFindings,
} from '@/lib/records-client';

const CHECKERS: CheckerInfo[] = [
  {
    key: 'dv_payment',
    task: 'T1',
    label: 'Payment Document & DV Checker',
    blurb: 'Checks a disbursement voucher and its supporting attachments.',
    owner: 'Jerald',
    engine: 'rule',
    doc_types: ['Disbursement Voucher'],
  },
  {
    key: 'contract_to_payment',
    task: 'T4',
    label: 'Contract-to-Payment Consistency Checker',
    blurb: 'Compares the contract against the payment packet.',
    owner: 'PCMD',
    engine: 'consistency',
    doc_types: ['Contract', 'Disbursement Voucher'],
  },
];

function finding(id: string, severity: Severity, title: string): Finding {
  return {
    id,
    dimension: 'dv_payment',
    severity,
    title,
    analysis: 'Analysis text.',
    recommendation: '',
    source: { doc: 'DV.pdf', page: 1, section: '' },
    policy_basis: '',
    quote: '',
    comparison: [],
    delta: null,
    confidence: null,
    external_sources: [],
    policy_sources: [],
    procurement_ref: 'PROC-1',
    decision: null,
    decided_by: null,
    decided_at: null,
    rejection_reason: null,
    rejection_note: '',
    edited: false,
    ai_analysis: 'Analysis text.',
    ai_recommendation: '',
    comments: [],
    feedback: null,
  };
}

const EMPTY_COUNTS: Record<Severity, number> = {
  critical: 0,
  medium: 0,
  low: 0,
  info: 0,
  compliant: 0,
};

function procurement(overrides: Partial<Procurement> = {}): Procurement {
  return {
    ref: 'PROC-1',
    title: 'Supply and delivery of network switches',
    abc: 1_000_000,
    mode: 'Competitive Bidding',
    fund: 'GAA',
    category: 'Goods',
    end_user: 'ICTMS',
    status: 'ongoing',
    created: '2026-01-01',
    updated: '2026-01-01',
    documents: [
      {
        id: 'doc-1',
        name: 'DV.pdf',
        doc_type: 'Disbursement Voucher',
        pages: 2,
        uploaded: '2026-01-01',
        gcs_path: 'gs://bucket/DV.pdf',
        status: 'Ready',
      },
    ],
    review_status: 'none',
    check_status: 'none',
    report_notes: '',
    finalized_at: null,
    finalized_by: null,
    finding_counts: { ...EMPTY_COUNTS },
    check_counts: { ...EMPTY_COUNTS },
    decided_count: 0,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(listCheckers).mockResolvedValue(CHECKERS);
  vi.mocked(listCheckFindings).mockResolvedValue([]);
});

describe('ComplianceChecksTab', () => {
  it('lists what each checker needs before anything has run', async () => {
    render(
      <ComplianceChecksTab
        procurement={procurement()}
        onProcurementChange={() => {}}
        onGoToDocuments={() => {}}
      />
    );

    expect(
      await screen.findByText('No compliance checks have been run')
    ).toBeInTheDocument();
    // The catalogue is what tells the committee why a checker later stays
    // silent, so it has to name both the checker and the documents it needs.
    expect(
      screen.getByText('Payment Document & DV Checker')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Needs: Contract, Disbursement Voucher')
    ).toBeInTheDocument();
  });

  it('counts only failures in the headline, not the requirements that passed', async () => {
    vi.mocked(listCheckFindings).mockResolvedValue([
      finding('chk-dv_payment.amount', 'critical', 'Not met — amounts agree'),
      finding('chk-dv_payment.payee', 'compliant', 'Payee is named'),
      finding('chk-dv_payment.ors', 'compliant', 'Obligation reference present'),
    ]);

    render(
      <ComplianceChecksTab
        procurement={procurement({ check_status: 'done' })}
        onProcurementChange={() => {}}
        onGoToDocuments={() => {}}
      />
    );

    expect(
      await screen.findByText('1 requirement not met')
    ).toBeInTheDocument();
    expect(
      screen.getByText('2 other requirements were checked and raised nothing.')
    ).toBeInTheDocument();

    // A compliant finding is real and retrievable, but it is not what the
    // committee opens this tab to read, so it stays behind the toggle.
    await waitFor(() =>
      expect(screen.getByText('Not met — amounts agree')).toBeInTheDocument()
    );
    expect(screen.queryByText('Payee is named')).not.toBeInTheDocument();
  });
});
