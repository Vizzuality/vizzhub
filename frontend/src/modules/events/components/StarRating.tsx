import { Star } from 'lucide-react';

interface StarRatingProps {
  readonly value: number | null;
  readonly onChange?: (value: number) => void;
  readonly size?: number;
}

export function StarRating({ value, onChange, size = 16 }: StarRatingProps): JSX.Element {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={!onChange}
          onClick={() => onChange?.(star)}
          className={
            onChange
              ? 'cursor-pointer hover:scale-110 transition-transform'
              : 'cursor-default'
          }
        >
          <Star
            size={size}
            className={
              value !== null && star <= value
                ? 'fill-amber-400 text-amber-400'
                : 'text-muted-foreground/30'
            }
          />
        </button>
      ))}
    </div>
  );
}
