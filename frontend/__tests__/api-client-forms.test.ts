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

  it('detectFormsForRef posts to the ref-based endpoint and returns the parsed body', async () => {
    const body = {
      doc_types: ['Market Study'],
      forms: {
        ppmp: {
          available: true,
          recommended: true,
          reason: 'Market study on file',
          source_doc_types: ['Market Study'],
          present: ['Market Study'],
          missing: [],
        },
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), { status: 200 })
    );
    global.fetch = fetchMock;

    const result = await apiClient.detectFormsForRef('PR-2026-001');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/procurements/PR-2026-001/forms/detect'),
      expect.objectContaining({ method: 'POST' })
    );
    expect(result).toEqual(body);
  });

  it('generateFormsForRef posts form_keys/overrides and reads blob + filename like generateForms', async () => {
    const blob = new Blob([new Uint8Array([80, 75])]);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="PPMP.xlsx"' },
      })
    );
    global.fetch = fetchMock;

    const result = await apiClient.generateFormsForRef('PR-2026-001', ['ppmp'], {});

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/procurements/PR-2026-001/forms/generate');
    expect(JSON.parse(init.body)).toEqual({ form_keys: ['ppmp'], overrides: {} });
    expect(result.filename).toBe('PPMP.xlsx');
  });

  it('generateFormsForRef surfaces the server error detail on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Unknown form key: bogus' }), { status: 400 })
    );

    await expect(
      apiClient.generateFormsForRef('PR-2026-001', ['bogus' as any], {})
    ).rejects.toThrow('Unknown form key: bogus');
  });
});
