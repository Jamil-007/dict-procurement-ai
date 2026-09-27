import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

function Hi() {
  return <p>hi</p>;
}

describe('tooling', () => {
  it('renders', () => {
    render(<Hi />);
    expect(screen.getByText('hi')).toBeInTheDocument();
  });
});
