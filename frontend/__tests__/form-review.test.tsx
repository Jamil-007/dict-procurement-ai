import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FormReview } from '@/components/procurement/form-review';
import type { ExtractResponse } from '@/lib/api-client';

vi.mock('@/lib/api-client');
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const mockExtractResponse: ExtractResponse = {
  ppmp: {
    fields: {
      fiscal_year: '2026',
      estimated_budget: '[TBD]',
    },
    warning: false,
    group: 'A_rich',
  },
  bidform: {
    fields: {
      project_title: 'GECS Equipment',
    },
    warning: false,
    group: 'B_annex',
  },
};

describe('FormReview', () => {
  beforeEach(async () => {
    const { apiClient } = await import('@/lib/api-client');
    vi.mocked(apiClient.extractForms).mockResolvedValue(mockExtractResponse);
  });

  it('renders tabs for each form', async () => {
    render(<FormReview threadId="test-thread" formKeys={['ppmp', 'bidform']} />);

    await waitFor(() => {
      const ppmpElements = screen.getAllByText(/ppmp/i);
      expect(ppmpElements.length).toBeGreaterThan(0);
    });
  });

  it('shows disclaimer for annex forms', async () => {
    render(<FormReview threadId="test-thread" formKeys={['bidform']} />);

    await waitFor(() => {
      const disclaimers = screen.getAllByText(/DRAFT/i);
      expect(disclaimers.length).toBeGreaterThan(0);
    });
  });
});
