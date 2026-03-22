import { ChevronLeft, ChevronRight } from 'lucide-react';

const MAX_VISIBLE = 6;

interface ChartPaginationProps<T> {
  readonly data: T[];
  readonly page: number;
  readonly onPageChange: (page: number) => void;
}

export function useChartPagination<T>(data: T[], page: number): {
  visible: T[];
  totalPages: number;
  safePage: number;
} {
  const totalPages = Math.max(1, Math.ceil(data.length / MAX_VISIBLE));
  const safePage = Math.min(page, totalPages - 1);
  const start = safePage * MAX_VISIBLE;
  const visible = data.slice(start, start + MAX_VISIBLE);
  return { visible, totalPages, safePage };
}

export function ChartPagination<T>({
  data,
  page,
  onPageChange,
}: ChartPaginationProps<T>): JSX.Element | null {
  const { totalPages, safePage } = useChartPagination(data, page);
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
      <button
        type="button"
        disabled={safePage === 0}
        onClick={() => onPageChange(safePage - 1)}
        className="rounded p-1 hover:bg-muted disabled:opacity-30"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <span>
        {safePage + 1} / {totalPages}
      </span>
      <button
        type="button"
        disabled={safePage >= totalPages - 1}
        onClick={() => onPageChange(safePage + 1)}
        className="rounded p-1 hover:bg-muted disabled:opacity-30"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
