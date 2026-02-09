import { useCallback, useMemo } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import type { ProjectStatus } from '../types';

export type StatusFilter = 'all' | ProjectStatus;

export interface ProjectFilters {
  searchName: string;
  statusFilter: StatusFilter;
  startDateFrom: string;
  startDateTo: string;
}

export interface UseProjectFiltersReturn {
  filters: ProjectFilters;
  setSearchName: (value: string) => void;
  setStatusFilter: (value: StatusFilter) => void;
  setStartDateFrom: (value: string) => void;
  setStartDateTo: (value: string) => void;
  hasActiveFilters: boolean;
  clearFilters: () => void;
}

const filterSchema = {
  search: { defaultValue: '' },
  status: { defaultValue: 'all' },
  from: { defaultValue: '' },
  to: { defaultValue: '' },
};

export function useProjectFilters(): UseProjectFiltersReturn {
  const { state, setState, resetState } = useUrlState(filterSchema);

  const filters: ProjectFilters = useMemo(() => ({
    searchName: state.search,
    statusFilter: state.status as StatusFilter,
    startDateFrom: state.from,
    startDateTo: state.to,
  }), [state.search, state.status, state.from, state.to]);

  const setSearchName = useCallback(
    (value: string) => setState({ search: value }),
    [setState],
  );

  const setStatusFilter = useCallback(
    (value: StatusFilter) => setState({ status: value }),
    [setState],
  );

  const setStartDateFrom = useCallback(
    (value: string) => setState({ from: value }),
    [setState],
  );

  const setStartDateTo = useCallback(
    (value: string) => setState({ to: value }),
    [setState],
  );

  const hasActiveFilters = Boolean(
    state.search || state.status !== 'all' || state.from || state.to,
  );

  const clearFilters = useCallback((): void => {
    resetState();
  }, [resetState]);

  return {
    filters,
    setSearchName,
    setStatusFilter,
    setStartDateFrom,
    setStartDateTo,
    hasActiveFilters,
    clearFilters,
  };
}
