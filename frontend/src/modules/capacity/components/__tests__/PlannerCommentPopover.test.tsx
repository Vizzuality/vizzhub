import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PlannerCommentPopover } from '@/modules/capacity/components/PlannerCommentPopover';

function renderOpen(props: Partial<React.ComponentProps<typeof PlannerCommentPopover>> = {}) {
  const onSave = vi.fn();
  const onDelete = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <PlannerCommentPopover
      open
      onOpenChange={onOpenChange}
      comment={props.comment}
      onSave={onSave}
      onDelete={onDelete}
      anchor={<button>anchor</button>}
    />,
  );
  return { onSave, onDelete, onOpenChange };
}

describe('PlannerCommentPopover', () => {
  it('shows Delete only when editing an existing comment', () => {
    renderOpen({ comment: 'Existing' });
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  it('hides Delete when creating a new comment', () => {
    renderOpen({ comment: undefined });
    expect(screen.queryByRole('button', { name: /delete/i })).toBeNull();
  });

  it('calls onSave with trimmed text', () => {
    const { onSave } = renderOpen();
    const ta = screen.getByRole('textbox');
    fireEvent.change(ta, { target: { value: '  hello  ' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith('hello');
  });

  it('ignores save when text is empty after trim', () => {
    const { onSave, onOpenChange } = renderOpen();
    const ta = screen.getByRole('textbox');
    fireEvent.change(ta, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('enforces 500 char max in the textarea', () => {
    renderOpen();
    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(ta.maxLength).toBe(500);
  });
});
