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
// component exercises the exact grid / docx-preview code paths.
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

  it('renders a real .xlsx template as a clean grid with A/B/C headers', async () => {
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
        filename="PPMP.xlsx"
        overrides={{}}
        active
      />
    );

    await waitFor(
      () => {
        // The data-model grid renders column-letter headers.
        expect(container.querySelector('table.xl .xl-colh')).toBeTruthy();
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
        filename="Market.docx"
        overrides={{}}
        active
      />
    );

    await waitFor(
      () => {
        expect(container.querySelector('.docx-wrapper')).toBeTruthy();
      },
      { timeout: 5000 }
    );
  });

  it('does not generate while inactive (retention: lazy build)', async () => {
    const { apiClient } = await import('@/lib/api-client');
    const gen = vi.mocked(apiClient.generateForms).mockResolvedValue({
      blob: templateBlob('market.docx', DOCX_MIME),
      filename: 'market.docx',
    });

    render(
      <DocumentPreview
        threadId="t3"
        formKey={'market' as FormKey}
        ext="docx"
        filename="Market.docx"
        overrides={{}}
        active={false}
      />
    );

    // Give any pending effects a chance to run.
    await new Promise((r) => setTimeout(r, 50));
    expect(gen).not.toHaveBeenCalled();
  });

  it('shows the annex draft badge', () => {
    const { getByText } = render(
      <DocumentPreview
        threadId="t4"
        formKey={'oss' as FormKey}
        ext="docx"
        filename="Omnibus Sworn Statement.docx"
        overrides={{}}
        isAnnex
        active
      />
    );

    expect(getByText(/FOR BIDDER COMPLETION/i)).toBeTruthy();
  });
});
