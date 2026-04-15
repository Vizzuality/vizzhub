import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTheme } from 'next-themes';
import { getPlannerCellColors } from '@/modules/capacity/utils/plannerColors';
import { PlannerCommentPopover } from '@/modules/capacity/components/PlannerCommentPopover';

interface PlannerCellProps {
  readonly value: number | undefined;
  readonly onChange: (value: number | null) => void;
  readonly isOwnRow: boolean;
  readonly selected?: boolean;
  readonly absence?: boolean;
  readonly canComment?: boolean;
  readonly comment?: string;
  readonly onCommentChange?: (value: string | null) => void;
  readonly onMouseDown?: (e: React.MouseEvent) => void;
  readonly onMouseEnter?: () => void;
}

const STRIPED_BG = {
  dark: 'repeating-linear-gradient(135deg, transparent, transparent 3px, rgba(255,255,255,0.06) 3px, rgba(255,255,255,0.06) 6px)',
  light: 'repeating-linear-gradient(135deg, transparent, transparent 3px, rgba(0,0,0,0.06) 3px, rgba(0,0,0,0.06) 6px)',
} as const;

export function PlannerCell({
  value,
  onChange,
  isOwnRow,
  selected,
  absence,
  canComment,
  comment,
  onCommentChange,
  onMouseDown,
  onMouseEnter,
}: PlannerCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [popoverOpen, setPopoverOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const showIcon = Boolean(canComment && value !== undefined && onCommentChange);
  const hasComment = comment !== undefined && comment !== '';

  const cellColors = getPlannerCellColors(value, isDark);

  const startEditing = (): void => {
    setDraft(value?.toString() ?? '');
    setEditing(true);
  };

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const commit = (): void => {
    setEditing(false);
    const num = Number.parseInt(draft, 10);
    if (draft === '' || Number.isNaN(num) || num <= 0) {
      if (value !== undefined) onChange(null);
    } else if (num !== value) {
      onChange(Math.min(num, 200));
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="w-full h-full border-0 bg-transparent text-center text-xs outline-none"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={handleKeyDown}
        type="number"
        min={0}
        max={200}
      />
    );
  }

  const cellStyle = absence
    ? { background: STRIPED_BG[isDark ? 'dark' : 'light'], color: cellColors?.text }
    : { backgroundColor: cellColors?.bg, color: cellColors?.text };

  return (
    <div className="relative h-full w-full">
      <button
        type="button"
        className={`flex h-full w-full cursor-pointer items-center justify-center text-xs select-none border-0 bg-transparent p-0 ${
          !isOwnRow && value !== undefined ? 'ring-1 ring-inset ring-yellow-400/30' : ''
        } ${selected ? 'ring-2 ring-inset ring-primary' : ''}`}
        style={cellStyle}
        onDoubleClick={startEditing}
        onMouseDown={onMouseDown}
        onMouseEnter={onMouseEnter}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') startEditing();
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
            <button
              type="button"
              aria-label={hasComment ? 'Edit comment' : 'Add comment'}
              onClick={(e) => { e.stopPropagation(); setPopoverOpen((v) => !v); }}
              onMouseDown={(e) => e.stopPropagation()}
              className={`absolute right-0 top-0 transition-opacity ${
                hasComment
                  ? 'opacity-100'
                  : 'opacity-0 hover:opacity-100 group-hover/cell:opacity-100'
              }`}
              style={{
                width: 9,
                height: 9,
                clipPath: 'polygon(100% 0, 0 0, 100% 100%)',
                backgroundColor: hasComment
                  ? 'hsl(var(--primary))'
                  : isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.35)',
              }}
            />
          }
        />
      )}
    </div>
  );
}
