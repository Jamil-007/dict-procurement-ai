/**
 * The six assigned requirements this suite implements, as stated in the
 * DICT task matrix. Task ids match the `task` field the backend stamps on
 * every finding ("T1".."T6"), which is what lets the UI anchor each run's
 * results to the requirement that produced them.
 */

export type RequirementCategory = 'COMPLIANCE' | 'DATA INTEGRITY';

export interface RequirementInfo {
  task: string;
  name: string;
  owner: string;
  stage: string;
  category: RequirementCategory;
  description: string;
  /** Which engine implements it, and with how many checks. */
  engine: string;
  checks: string;
  /** Which backend checker node covers it, to tell "ran" from "not run". */
  checkerNode: 'rule_checks' | 'consistency_checks';
  documents: string[];
  authorities: string[];
}

export const REQUIREMENTS: RequirementInfo[] = [
  {
    task: 'T1',
    name: 'Payment Document and DV Checker',
    owner: 'Jerald · PCMD',
    stage: 'Contract Implementation',
    category: 'COMPLIANCE',
    description: 'Checks Disbursement Vouchers and payment documents for completeness before processing.',
    engine: 'Rule engine · dv_payment pack',
    checks: '17 deterministic rules (fields, signatories, arithmetic, attachments, date order)',
    checkerNode: 'rule_checks',
    documents: [
      'Disbursement Voucher',
      'ORS',
      'Invoice',
      'Delivery Receipt',
      'IAR',
      'PAR / ICS',
      'Warranty Certificate',
    ],
    authorities: [
      'GAM Volume I',
      'COA Circular No. 2023-004 §9.3.1',
      'IRR of RA 12009 §61.2.3',
    ],
  },
  {
    task: 'T2',
    name: 'AI Procurement Compliance Checker',
    owner: 'Michelle',
    stage: 'Planning',
    category: 'COMPLIANCE',
    description: 'Flags compliance issues with citations from RA 12009, its IRR and GPPB/COA issuances.',
    engine: 'Rule engine · ra12009_planning pack + legal knowledge base',
    checks: '17 rules — every finding carries a citation retrieved verbatim from the indexed corpus',
    checkerNode: 'rule_checks',
    documents: [
      'PPMP',
      'PR',
      'TOR',
      'Market Study',
      'DCB',
      'Bidding Documents',
      'BAC Resolution',
      'Contract',
    ],
    authorities: [
      'RA 12009',
      'IRR of RA 12009',
      'GPPB manuals, circulars & resolutions',
      'COA circulars',
    ],
  },
  {
    task: 'T3',
    name: 'Procurement Document Review and Compliance Engine',
    owner: 'OUPCO',
    stage: 'Others',
    category: 'COMPLIANCE',
    description: 'Checks any procurement document for completeness and missing provisions.',
    engine: 'Rule engine · completeness_by_doctype pack + document classifier',
    checks: '30 completeness rules across 25 recognised document types',
    checkerNode: 'rule_checks',
    documents: ['All 25 supported document types'],
    authorities: ['COA Circular No. 2023-004', 'GAM Volume I'],
  },
  {
    task: 'T4',
    name: 'Contract-to-Payment Document Consistency Checker',
    owner: 'PCMD',
    stage: 'Contract Implementation',
    category: 'DATA INTEGRITY',
    description: 'Compares the contract against payment documents and flags changes needing a variation order.',
    engine: 'Consistency engine · contract_to_payment profile',
    checks: '11 cross-document comparisons with amendment / variation-order hints',
    checkerNode: 'consistency_checks',
    documents: [
      'Contract / NOA / NTP',
      'vs DV',
      'ORS',
      'Invoice',
      'Delivery Receipt',
      'IAR',
      'PAR / ICS',
      'Warranty',
    ],
    authorities: [
      'IRR of RA 12009 §71.1.1 & §71.2.1',
      'GAM Volume I',
      'COA Circular No. 2009-001',
    ],
  },
  {
    task: 'T5',
    name: 'Automated Document and Data Cross-Checker',
    owner: 'PCMD',
    stage: 'Contract Implementation',
    category: 'DATA INTEGRITY',
    description: 'Cross-checks serials, quantities and dates across delivery and acceptance documents.',
    engine: 'Consistency engine · delivery_acceptance profile',
    checks: '10 comparisons, including serial-number set matching',
    checkerNode: 'consistency_checks',
    documents: [
      'Delivery Receipt',
      'vs IAR',
      'Inspection Report',
      'PAR / ICS',
      'Warranty Certificate',
    ],
    authorities: ['COA Circular No. 2023-004 §9.3.1'],
  },
  {
    task: 'T6',
    name: 'Cross-Document Inconsistency Detection (Planning)',
    owner: 'Jen L.',
    stage: 'Planning',
    category: 'DATA INTEGRITY',
    description: 'Detects mismatches between the TOR, Market Study, cost breakdown and bidding documents.',
    engine: 'Consistency engine · planning_alignment profile',
    checks: '14+ comparisons measured against the TOR',
    checkerNode: 'consistency_checks',
    documents: [
      'TOR',
      'vs Market Study',
      'DCB',
      'Bidding Documents',
      'RFQ',
      'PR',
      'PPMP / APP',
    ],
    authorities: ['IRR of RA 12009 (Schedule of Requirements, §61.2.3)'],
  },
];
