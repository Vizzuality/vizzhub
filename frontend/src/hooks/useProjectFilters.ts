import { useState, useCallback } from 'react';
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

export function useProjectFilters(): UseProjectFiltersReturn {
  const [searchName, setSearchName] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [startDateFrom, setStartDateFrom] = useState('');
  const [startDateTo, setStartDateTo] = useState('');

  const hasActiveFilters = Boolean(
    searchName || statusFilter !== 'all' || startDateFrom || startDateTo,
  );

  const clearFilters = useCallback((): void => {
    setSearchName('');
    setStatusFilter('all');
    setStartDateFrom('');
    setStartDateTo('');
  }, []);

  return {
    filters: {
      searchName,
      statusFilter,
      startDateFrom,
      startDateTo,
    },
    setSearchName,
    setStatusFilter,
    setStartDateFrom,
    setStartDateTo,
    hasActiveFilters,
    clearFilters,
  };
}
