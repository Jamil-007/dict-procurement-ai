import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { FormGenerator } from '@/components/procurement/form-generator';
import type { FormCatalogItem, DetectResult } from '@/types/forms';

vi.mock('@/lib/api-client');

const mockCatalog: FormCatalogItem[] = [
  { key: 'ppmp', name: 'PPMP', group: 'A_rich', ext: '.xlsx', fill_level: 'rich' },
  { key: 'market', name: 'Market Scoping', group: 'A_rich', ext: '.docx', fill_level: 'rich' },
  { key: 'bidform', name: 'Bid Form', group: 'B_annex', ext: '.docx', fill_level: 'annex' },
];

const mockDetectResult: DetectResult = {
  doc_types: ['Terms of Reference'],
  documents: [{ filename: 'TOR.pdf', doc_types: ['Terms of Reference'] }],
  forms: {
    ppmp: { available: true, recommended: true, reason: 'TOR present' },
    market: { available: true, recommended: false, reason: 'No market study' },
    app: { available: true, recommended: false, reason: '' },
    contract: { available: true, recommended: true, reason: 'TOR present' },
    bidform: { available: true, recommended: false, reason: 'Blank annex' },
    price_local: { available: true, recommended: false, reason: 'Blank annex' },
    price_abroad: { available: true, recommended: false, reason: 'Blank annex' },
    bsd: { available: true, recommended: false, reason: 'Blank annex' },
    oss: { available: true, recommended: false, reason: 'Blank annex' },
    psd: { available: true, recommended: false, reason: 'Blank annex' },
  },
};

describe('FormGenerator', () => {
  beforeEach(async () => {
    const { apiClient } = await import('@/lib/api-client');
    vi.mocked(apiClient.getFormCatalog).mockResolvedValue(mockCatalog);
  });

  it('renders and loads forms', async () => {
    render(<FormGenerator detectResult={mockDetectResult} onGenerate={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('PPMP')).toBeInTheDocument();
    });
  });

  it('shows Recommended pill for recommended forms', async () => {
    render(<FormGenerator detectResult={mockDetectResult} onGenerate={() => {}} />);

    await waitFor(() => {
      // PPMP should be recommended
      const ppmpElement = screen.getByText('PPMP').closest('div');
      expect(ppmpElement?.textContent).toContain('Recommended');
    });
  });

  it('pre-selects recommended forms from detectResult', async () => {
    render(<FormGenerator detectResult={mockDetectResult} onGenerate={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('PPMP')).toBeInTheDocument();
    });

    // ppmp + contract are recommended -> 2 pre-selected
    expect(screen.getByText('2 selected')).toBeInTheDocument();
  });

  it('shows no Recommended pills and nothing pre-selected without detectResult', async () => {
    render(<FormGenerator detectResult={null} onGenerate={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('PPMP')).toBeInTheDocument();
    });

    expect(screen.getByText('0 selected')).toBeInTheDocument();
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument();
  });

  it('calls onGenerate with selected keys', async () => {
    const onGenerate = vi.fn();
    render(<FormGenerator detectResult={mockDetectResult} onGenerate={onGenerate} />);

    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByText('PPMP')).toBeInTheDocument();
    });

    const generateBtn = screen.getByRole('button', { name: /generate/i });
    await user.click(generateBtn);

    expect(onGenerate).toHaveBeenCalled();
    const calledKeys = onGenerate.mock.calls[0][0];
    expect(Array.isArray(calledKeys)).toBe(true);
  });
});
