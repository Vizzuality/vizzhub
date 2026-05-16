import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

  it('paints the destructive ring when hasError is true', () => {
    const { container } = render(
      <PlannerCell value={50} isOwnRow hasError onChange={() => {}} />,
    );
    const cellButton = container.querySelector('button');
    expect(cellButton?.className).toContain('ring-destructive');
  });

  it('does not paint the destructive ring when hasError is false', () => {
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={() => {}} />,
    );
    const cellButton = container.querySelector('button');
    expect(cellButton?.className ?? '').not.toContain('ring-destructive');
  });
});

describe('PlannerCell (edit lifecycle)', () => {
  it('commits a new value with Enter and calls onChange', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={onChange} />,
    );

    await act(async () => {
      fireEvent.doubleClick(container.querySelector('button')!);
    });
    const input = container.querySelector('input');
    if (!input) throw new Error('input not rendered after double-click');
    await userEvent.clear(input);
    await userEvent.type(input, '80');
    await userEvent.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith(80);
  });

  it('clamps values above 200 down to 200', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={onChange} />,
    );

    await act(async () => {
      fireEvent.doubleClick(container.querySelector('button')!);
    });
    const input = container.querySelector('input')!;
    await userEvent.clear(input);
    await userEvent.type(input, '500');
    await userEvent.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith(200);
  });

  it('clears the cell (onChange null) when committed empty', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={onChange} />,
    );

    await act(async () => {
      fireEvent.doubleClick(container.querySelector('button')!);
    });
    const input = container.querySelector('input')!;
    await userEvent.clear(input);
    await userEvent.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('clears the cell (onChange null) when committed zero', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={onChange} />,
    );

    await act(async () => {
      fireEvent.doubleClick(container.querySelector('button')!);
    });
    const input = container.querySelector('input')!;
    await userEvent.clear(input);
    await userEvent.type(input, '0');
    await userEvent.keyboard('{Enter}');

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('does not call onChange when the committed value equals the current value', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={onChange} />,
    );

    await act(async () => {
      fireEvent.doubleClick(container.querySelector('button')!);
    });
    const input = container.querySelector('input')!;
    await userEvent.clear(input);
    await userEvent.type(input, '50');
    await userEvent.keyboard('{Enter}');

    expect(onChange).not.toHaveBeenCalled();
  });

  it('Escape cancels the edit without calling onChange', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PlannerCell value={50} isOwnRow onChange={onChange} />,
    );

    await act(async () => {
      fireEvent.doubleClick(container.querySelector('button')!);
    });
    const input = container.querySelector('input')!;
    await userEvent.clear(input);
    await userEvent.type(input, '99');
    await userEvent.keyboard('{Escape}');

    expect(onChange).not.toHaveBeenCalled();
  });
});
