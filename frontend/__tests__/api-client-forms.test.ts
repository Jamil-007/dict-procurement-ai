import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiClient } from '@/lib/api-client';

describe('API Client - Forms', () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('generateForms reads blob + Content-Disposition, not json', async () => {
    const blob = new Blob([new Uint8Array([80, 75])]);
    global.fetch = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="PPMP.xlsx"' },
      })
    );

    const result = await apiClient.generateForms('t', ['ppmp'], {});

    expect(result.filename).toBe('PPMP.xlsx');
    expect(result.blob.size).toBeGreaterThan(0);
  });

  it('generateForms extracts filename with quotes', async () => {
    const blob = new Blob([new Uint8Array([80, 75])]);
    global.fetch = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="Contract_GECS.docx"' },
      })
    );

    const result = await apiClient.generateForms('t', ['contract'], {});

    expect(result.filename).toBe('Contract_GECS.docx');
  });

  it('generateForms handles missing Content-Disposition', async () => {
    const blob = new Blob([new Uint8Array([80, 75])]);
    global.fetch = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: {},
      })
    );

    const result = await apiClient.generateForms('t', ['ppmp'], {});

    expect(result.filename).toBe('download');
  });
});
