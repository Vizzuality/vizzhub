import { Button } from '@/components/ui/button';

export interface RatingOption<T extends string | number> {
  value: T;
  label?: string;
}

interface RatingButtonsProps<T extends string | number> {
  options: readonly T[] | readonly RatingOption<T>[];
  selected: T | undefined;
  onSelect: (value: T) => void;
  className?: string;
  buttonClassName?: string;
  'aria-labelledby'?: string;
}

function isOptionObject<T extends string | number>(
  opt: T | RatingOption<T>
): opt is RatingOption<T> {
  return typeof opt === 'object' && opt !== null && 'value' in opt;
}

export function RatingButtons<T extends string | number>({
  options,
  selected,
  onSelect,
  className = 'flex gap-2',
  buttonClassName,
  'aria-labelledby': ariaLabelledBy,
}: RatingButtonsProps<T>): JSX.Element {
  return (
    <div className={className} role="group" aria-labelledby={ariaLabelledBy}>
      {options.map((opt) => {
        const value = isOptionObject(opt) ? opt.value : opt;
        const label = isOptionObject(opt) ? (opt.label ?? String(value)) : String(value);
        return (
          <Button
            key={String(value)}
            size="sm"
            variant={selected === value ? 'default' : 'outline'}
            onClick={() => onSelect(value)}
            className={buttonClassName}
          >
            {label}
          </Button>
        );
      })}
    </div>
  );
}
