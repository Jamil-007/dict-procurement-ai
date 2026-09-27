import { render, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'fs';
import path from 'path';
import { DocumentPreview } from '@/components/procurement/document-preview';
import type { FormKey } from '@/types/forms';

vi.mock('@/lib/api-client', () => ({
  apiClient: { generateForms: vi.fn() },
}));

const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

// Real generated templates live in the backend; feeding them through the
// component exercises the exact SheetJS / docx-preview code paths.
function templateBlob(rel: string, type: string): Blob {
  const buf = readFileSync(
    path.resolve(process.cwd(), '../backend/templates/forms', rel)
  );
  return new Blob([buf], { type });
}

describe('DocumentPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a real .xlsx template as an HTML table', async () => {
    const { apiClient } = await import('@/lib/api-client');
    vi.mocked(apiClient.generateForms).mockResolvedValue({
      blob: templateBlob('ppmp.xlsx', XLSX_MIME),
      filename: 'ppmp.xlsx',
    });

    const { container } = render(
      <DocumentPreview
        threadId="t1"
        formKey={'ppmp' as FormKey}
        ext="xlsx"
        overrides={{}}
      />
    );

    await waitFor(
      () => {
        expect(
          container.querySelector('.docx-preview-host .xlsx-sheet table')
        ).toBeTruthy();
      },
      { timeout: 5000 }
    );
  });

  it('renders a real .docx template with docx-preview', async () => {
    const { apiClient } = await import('@/lib/api-client');
    vi.mocked(apiClient.generateForms).mockResolvedValue({
      blob: templateBlob('market.docx', DOCX_MIME),
      filename: 'market.docx',
    });

    const { container } = render(
      <DocumentPreview
        threadId="t2"
        formKey={'market' as FormKey}
        ext="docx"
        overrides={{}}
      />
    );

    await waitFor(
      () => {
        expect(container.querySelector('.docx-wrapper')).toBeTruthy();
      },
      { timeout: 5000 }
    );
  });

  it('shows the annex draft badge', async () => {
    const { apiClient } = await import('@/lib/api-client');
    vi.mocked(apiClient.generateForms).mockResolvedValue({
      blob: templateBlob('market.docx', DOCX_MIME),
      filename: 'oss.docx',
    });

    const { getByText } = render(
      <DocumentPreview
        threadId="t3"
        formKey={'oss' as FormKey}
        ext="docx"
        overrides={{}}
        isAnnex
      />
    );

    expect(getByText(/FOR BIDDER COMPLETION/i)).toBeTruthy();
  });
});
