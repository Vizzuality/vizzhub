import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Lock, Pin } from 'lucide-react';

interface AccrualCellProps {
  readonly amount: string;
  readonly eurAmount: string | null;
  readonly isOverride: boolean;
  readonly isFrozen: boolean;
  readonly canEdit: boolean;
  readonly onChange: (newAmount: string) => void;
  readonly onError?: boolean;
}

function formatAmount(value: string): string {
  const num = parseFloat(value);
  if (Number.isNaN(num)) return value;
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num);
}

export function AccrualCell({
  amount,
  eurAmount,
  isOverride,
  isFrozen,
  canEdit,
  onChange,
  onError,
}: AccrualCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(amount);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.select();
    }
  }, [editing]);

  const commit = (): void => {
    setEditing(false);
    if (draft !== amount) {
      onChange(draft);
    }
  };

  const cancel = (): void => {
    setDraft(amount);
    setEditing(false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      cancel();
    }
  };

  const ringClass = onError ? 'ring-2 ring-inset ring-destructive' : '';

  if (editing) {
    return (
      <div className={`relative flex h-full w-full items-center justify-center ${ringClass}`}>
        <input
          ref={inputRef}
          type="text"
          className="w-full h-full border-0 bg-transparent text-right text-xs outline-none px-1"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={handleKeyDown}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      title={eurAmount !== null ? `EUR ${eurAmount}` : undefined}
      className={`flex h-full w-full items-center justify-end gap-1 px-1 text-xs bg-transparent border-0 select-none ${canEdit && !isFrozen ? 'cursor-pointer' : 'cursor-default'} ${ringClass}`}
      onClick={() => {
        if (canEdit && !isFrozen) {
          setDraft(amount);
          setEditing(true);
        }
      }}
    >
      {isOverride && <Pin data-testid="cell-override-pin" className="h-3 w-3 shrink-0" />}
      {isFrozen && <Lock data-testid="cell-frozen-lock" className="h-3 w-3 shrink-0" />}
      <span>{formatAmount(amount)}</span>
    </button>
  );
}
