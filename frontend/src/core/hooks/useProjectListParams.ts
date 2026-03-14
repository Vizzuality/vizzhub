import { useCallback, useMemo } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import type { ProjectListParams, ProjectStatus } from '@/core/types/project';

export type StatusFilter = 'all' | ProjectStatus;
export type SortField = 'name' | 'created_at' | 'status';
export type SortOrder = 'asc' | 'desc';

const listParamsSchema = {
  page: { defaultValue: 1 },
  search: { defaultValue: '' },
  status: { defaultValue: 'all' },
  from: { defaultValue: '' },
  to: { defaultValue: '' },
  sort: { defaultValue: 'created_at' },
  order: { defaultValue: 'desc' },
};

export interface UseProjectListParamsReturn {
  params: ProjectListParams;
  page: number;
  searchName: string;
  statusFilter: StatusFilter;
  startDateFrom: string;
  startDateTo: string;
  sortField: SortField;
  sortOrder: SortOrder;
  hasActiveFilters: boolean;
  setSearchName: (value: string) => void;
  setStatusFilter: (value: StatusFilter) => void;
  setStartDateFrom: (value: string) => void;
  setStartDateTo: (value: string) => void;
  setPage: (value: number) => void;
  handleSort: (field: SortField) => void;
  clearFilters: () => void;
}

export function useProjectListParams(): UseProjectListParamsReturn {
  const { state, setState, resetState } = useUrlState(listParamsSchema);

  const page = state.page as number;
  const searchName = state.search as string;
  const statusFilter = state.status as StatusFilter;
  const startDateFrom = state.from as string;
  const startDateTo = state.to as string;
  const sortField = state.sort as SortField;
  const sortOrder = state.order as SortOrder;

  const params: ProjectListParams = useMemo(() => {
    const p: ProjectListParams = { page };
    if (searchName) p.search = searchName;
    if (statusFilter !== 'all') p.status = statusFilter;
    if (startDateFrom) p.start_date_from = startDateFrom;
    if (startDateTo) p.start_date_to = startDateTo;
    p.sort = sortField;
    p.order = sortOrder;
    return p;
  }, [page, searchName, statusFilter, startDateFrom, startDateTo, sortField, sortOrder]);

  const setSearchName = useCallback(
    (value: string) => setState({ search: value, page: 1 }),
    [setState],
  );

  const setStatusFilter = useCallback(
    (value: StatusFilter) => setState({ status: value, page: 1 }),
    [setState],
  );

  const setStartDateFrom = useCallback(
    (value: string) => setState({ from: value, page: 1 }),
    [setState],
  );

  const setStartDateTo = useCallback(
    (value: string) => setState({ to: value, page: 1 }),
    [setState],
  );

  const setPage = useCallback(
    (value: number) => setState({ page: value }),
    [setState],
  );

  const handleSort = useCallback((field: SortField): void => {
    if (sortField === field) {
      setState({ order: sortOrder === 'asc' ? 'desc' : 'asc', page: 1 });
    } else {
      setState({ sort: field, order: field === 'name' ? 'asc' : 'desc', page: 1 });
    }
  }, [sortField, sortOrder, setState]);

  const hasActiveFilters = useMemo(
    () => Boolean(searchName || statusFilter !== 'all' || startDateFrom || startDateTo),
    [searchName, statusFilter, startDateFrom, startDateTo],
  );

  return {
    params,
    page,
    searchName,
    statusFilter,
    startDateFrom,
    startDateTo,
    sortField,
    sortOrder,
    hasActiveFilters,
    setSearchName,
    setStatusFilter,
    setStartDateFrom,
    setStartDateTo,
    setPage,
    handleSort,
    clearFilters: resetState,
  };
}
