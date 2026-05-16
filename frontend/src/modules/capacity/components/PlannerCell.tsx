import { forwardRef, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTheme } from 'next-themes';
import { getPlannerCellColors } from '@/modules/capacity/utils/plannerColors';
import { PlannerCommentPopover } from '@/modules/capacity/components/PlannerCommentPopover';

interface PlannerCellProps {
  readonly value: number | undefined;
  readonly onChange: (value: number | null) => void;
  readonly isOwnRow: boolean;
  readonly selected?: boolean;
  readonly hasError?: boolean;
  readonly canComment?: boolean;
  readonly comment?: string;
  readonly onCommentChange?: (value: string | null) => void;
  readonly onMouseDown?: (e: React.MouseEvent) => void;
  readonly onMouseEnter?: () => void;
}

const HOVER_TRIANGLE_DARK = 'rgba(255,255,255,0.45)';
const HOVER_TRIANGLE_LIGHT = 'rgba(0,0,0,0.35)';
const COMMENT_TRIANGLE = '#ef4444';

function triangleColor(hasComment: boolean, isDark: boolean): string {
  if (hasComment) return COMMENT_TRIANGLE;
  return isDark ? HOVER_TRIANGLE_DARK : HOVER_TRIANGLE_LIGHT;
}

function EditingInput({
  initial,
  onCommit,
}: {
  readonly initial: string;
  readonly onCommit: (draft: string) => void;
}): JSX.Element {
  const [draft, setDraft] = useState(initial);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.select();
  }, []);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      onCommit(draft);
    } else if (e.key === 'Escape') {
      onCommit(initial);
    }
  };

  return (
    <input
      ref={inputRef}
      className="w-full h-full border-0 bg-transparent text-center text-xs outline-none"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => onCommit(draft)}
      onKeyDown={handleKeyDown}
      type="number"
      min={0}
      max={200}
    />
  );
}

interface CommentAnchorProps {
  readonly hasComment: boolean;
  readonly isDark: boolean;
  readonly onToggle: () => void;
}

const CommentAnchor = forwardRef<HTMLButtonElement, CommentAnchorProps>(
  function CommentAnchor({ hasComment, isDark, onToggle, ...rest }, ref) {
    const visibilityClass = hasComment
      ? 'opacity-100'
      : 'opacity-0 hover:opacity-100 group-hover/cell:opacity-100';
    return (
      <button
        ref={ref}
        type="button"
        aria-label={hasComment ? 'Edit comment' : 'Add comment'}
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        onMouseDown={(e) => e.stopPropagation()}
        className={`absolute right-0 top-0 h-3.5 w-3.5 bg-transparent p-0 transition-opacity ${visibilityClass}`}
        {...rest}
      >
        <span
          className="block"
          style={{
            width: 10,
            height: 10,
            marginLeft: 'auto',
            clipPath: 'polygon(100% 0, 0 0, 100% 100%)',
            backgroundColor: triangleColor(hasComment, isDark),
          }}
        />
      </button>
    );
  },
);

export function PlannerCell({
  value,
  onChange,
  isOwnRow,
  selected,
  hasError,
  canComment,
  comment,
  onCommentChange,
  onMouseDown,
  onMouseEnter,
}: PlannerCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const showIcon = Boolean(canComment && value !== undefined && onCommentChange);
  const hasComment = comment !== undefined && comment !== '';

  const cellColors = getPlannerCellColors(value, isDark);

  const commitDraft = (draft: string): void => {
    setEditing(false);
    const num = Number.parseInt(draft, 10);
    if (draft === '' || Number.isNaN(num) || num <= 0) {
      if (value !== undefined) onChange(null);
    } else if (num !== value) {
      onChange(Math.min(num, 200));
    }
  };

  if (editing) {
    return <EditingInput initial={value?.toString() ?? ''} onCommit={commitDraft} />;
  }

  const cellStyle = { backgroundColor: cellColors?.bg, color: cellColors?.text };

  const ringClass = [
    !isOwnRow && value !== undefined ? 'ring-1 ring-inset ring-yellow-400/30' : '',
    selected ? 'ring-2 ring-inset ring-primary' : '',
    hasError ? 'ring-2 ring-inset ring-destructive' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className="relative h-full w-full">
      <button
        type="button"
        className={`flex h-full w-full cursor-pointer items-center justify-center text-xs select-none border-0 bg-transparent p-0 ${ringClass}`}
        style={cellStyle}
        onDoubleClick={() => setEditing(true)}
        onMouseDown={onMouseDown}
        onMouseEnter={onMouseEnter}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') setEditing(true);
        }}
      >
        {value ?? ''}
      </button>
      {showIcon && (
        <PlannerCommentPopover
          open={popoverOpen}
          onOpenChange={setPopoverOpen}
          comment={hasComment ? comment : undefined}
          onSave={(text) => onCommentChange?.(text)}
          onDelete={hasComment ? () => onCommentChange?.(null) : undefined}
          anchor={
            <CommentAnchor
              hasComment={hasComment}
              isDark={isDark}
              onToggle={() => setPopoverOpen((v) => !v)}
            />
          }
        />
      )}
    </div>
  );
}
