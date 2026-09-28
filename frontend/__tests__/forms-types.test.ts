import { describe, it, expect } from 'vitest';
import type { FormCatalogItem } from '@/types/forms';

describe('forms types', () => {
  it('FormCatalogItem type-checks correctly', () => {
    const item: FormCatalogItem = {
      key: 'ppmp',
      name: 'Project Procurement Management Plan',
      group: 'A_rich',
      ext: '.xlsx',
      fill_level: 'rich',
    };

    expect(item.key).toBe('ppmp');
    expect(item.group).toBe('A_rich');
  });
});
