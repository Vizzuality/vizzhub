import { ChevronLeft, ChevronRight } from 'lucide-react';

const DEFAULT_PAGE_SIZE = 6;

interface ChartPaginationProps<T> {
  readonly data: T[];
  readonly page: number;
  readonly onPageChange: (page: number) => void;
  readonly pageSize?: number;
}

/**
 * Total number of pages for `dataLength` items at the given window size.
 * Exposed so consumers can seed `useState` with a lazy initializer.
 */
export function chartPageCount(dataLength: number, pageSize: number = DEFAULT_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(dataLength / pageSize));
}

/**
 * Lazy-initializer helper: returns the index of the last page, i.e. the
 * window containing the most recent items in an ascending-chronological
 * data array. Pass to `useState(() => latestChartPage(data.length))` so
 * the snap happens exactly once on mount and the user's subsequent
 * clicks stick.
 */
export function latestChartPage(dataLength: number, pageSize: number = DEFAULT_PAGE_SIZE): number {
  return chartPageCount(dataLength, pageSize) - 1;
}

export function useChartPagination<T>(
  data: T[],
  page: number,
  pageSize: number = DEFAULT_PAGE_SIZE,
): {
  visible: T[];
  totalPages: number;
  safePage: number;
} {
  const totalPages = chartPageCount(data.length, pageSize);
  const safePage = Math.min(Math.max(page, 0), totalPages - 1);
  const start = safePage * pageSize;
  const visible = data.slice(start, start + pageSize);
  return { visible, totalPages, safePage };
}

export function ChartPagination<T>({
  data,
  page,
  onPageChange,
  pageSize = DEFAULT_PAGE_SIZE,
}: ChartPaginationProps<T>): JSX.Element | null {
  const { totalPages, safePage } = useChartPagination(data, page, pageSize);
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
