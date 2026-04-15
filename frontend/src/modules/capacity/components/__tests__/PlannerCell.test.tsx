import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlannerCell } from '@/modules/capacity/components/PlannerCell';

describe('PlannerCell (comments)', () => {
  it('renders the comment icon when comment exists and canComment is true', () => {
    render(
      <PlannerCell
        value={50}
        isOwnRow
        canComment
        comment="hello"
        onChange={() => {}}
        onCommentChange={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: /comment/i })).toBeInTheDocument();
  });

  it('does not render the comment icon when canComment is false', () => {
    render(
      <PlannerCell
        value={50}
        isOwnRow
        canComment={false}
        comment="hello"
        onChange={() => {}}
        onCommentChange={() => {}}
      />,
    );
    expect(screen.queryByRole('button', { name: /comment/i })).toBeNull();
  });

  it('does not render the comment icon when the cell has no value', () => {
    render(
      <PlannerCell
        value={undefined}
        isOwnRow
        canComment
        onChange={() => {}}
        onCommentChange={() => {}}
      />,
    );
    expect(screen.queryByRole('button', { name: /comment/i })).toBeNull();
  });
});
