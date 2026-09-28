import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import userEvent from '@testing-library/user-event';
import { FormHint } from '@/components/procurement/form-hint';

describe('FormHint', () => {
  it('renders collapsed by default (rows not visible)', () => {
    render(<FormHint />);

    // Trigger should be visible
    const trigger = screen.getByRole('button', { name: /which document produces which form/i });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    // Table content should not be visible
    expect(screen.queryByText('Terms of Reference')).not.toBeInTheDocument();
  });

  it('expands when trigger is clicked', async () => {
    render(<FormHint />);
    const user = userEvent.setup();

    const trigger = screen.getByRole('button', { name: /which document produces which form/i });
    await user.click(trigger);

    // Should expand
    expect(trigger).toHaveAttribute('aria-expanded', 'true');

    // Table content should now be visible
    expect(screen.getByText('Terms of Reference')).toBeInTheDocument();
  });

  it('displays all expected content when expanded', async () => {
    render(<FormHint />);
    const user = userEvent.setup();

    const trigger = screen.getByRole('button', { name: /which document produces which form/i });
    await user.click(trigger);

    // Check for document types
    expect(screen.getByText('Terms of Reference')).toBeInTheDocument();
    expect(screen.getByText('Market Study')).toBeInTheDocument();
    expect(screen.getByText('Cost Breakdown')).toBeInTheDocument();
    expect(screen.getByText('Signed Contract')).toBeInTheDocument();

    // Check for forms
    expect(screen.getByText('Market Scoping Form')).toBeInTheDocument();

    // Check for bidding annexes footer row
    expect(screen.getByText('Bidding annexes')).toBeInTheDocument();
    expect(screen.getByText(/Any upload — issued blank, project header stamped/)).toBeInTheDocument();
  });

  it('toggles aria-expanded attribute', async () => {
    render(<FormHint />);
    const user = userEvent.setup();

    const trigger = screen.getByRole('button', { name: /which document produces which form/i });

    // Initially collapsed
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    // Expand
    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');

    // Collapse again
    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });
});
