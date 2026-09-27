import { renderHook } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useProcurementAnalysis } from '@/hooks/use-procurement-analysis';

describe('useProcurementAnalysis hook', () => {
  it('exposes threadId in returned object', () => {
    const { result } = renderHook(() => useProcurementAnalysis());

    // threadId should be present in the return type
    expect(result.current).toHaveProperty('threadId');
    // Initially it should be null
    expect(result.current.threadId).toBeNull();
  });
});
