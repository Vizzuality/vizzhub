import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTheme } from 'next-themes';
import { getPlannerCellColors } from '@/modules/capacity/utils/plannerColors';

interface PlannerCellProps {
  readonly value: number | undefined;
  readonly onChange: (value: number | null) => void;
  readonly isOwnRow: boolean;
}

export function PlannerCell({
  value,
  onChange,
  isOwnRow,
}: PlannerCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();
  const isDark = theme === 'dark';

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
    const num = parseInt(draft, 10);
    if (draft === '' || isNaN(num) || num <= 0) {
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

  return (
    <div
      className={`flex h-full w-full cursor-pointer items-center justify-center text-xs ${
        !isOwnRow && value !== undefined ? 'ring-1 ring-inset ring-yellow-400/30' : ''
      }`}
      style={{ backgroundColor: cellColors?.bg, color: cellColors?.text }}
      onClick={startEditing}
      role="gridcell"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') startEditing();
      }}
    >
      {value ?? ''}
    </div>
  );
}
