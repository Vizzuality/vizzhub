import { useCallback } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';

export type SortField = 'name' | 'created_at' | 'status' | 'score';
export type SortOrder = 'asc' | 'desc';

export interface UseProjectSortReturn {
  sortField: SortField;
  sortOrder: SortOrder;
  handleSort: (field: SortField) => void;
}

const sortSchema = {
  sort: { defaultValue: 'created_at' },
  order: { defaultValue: 'desc' },
};

export function useProjectSort(): UseProjectSortReturn {
  const { state, setState } = useUrlState(sortSchema);

  const sortField = state.sort as SortField;
  const sortOrder = state.order as SortOrder;

  const handleSort = useCallback((field: SortField): void => {
    if (sortField === field) {
      setState({ order: sortOrder === 'asc' ? 'desc' : 'asc' });
    } else {
      setState({ sort: field, order: field === 'name' ? 'asc' : 'desc' });
    }
  }, [sortField, sortOrder, setState]);

  return {
    sortField,
    sortOrder,
    handleSort,
  };
}
