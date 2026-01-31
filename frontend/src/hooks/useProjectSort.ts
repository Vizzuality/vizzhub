import { useState, useCallback } from 'react';

export type SortField = 'name' | 'created_at' | 'status' | 'score';
export type SortOrder = 'asc' | 'desc';

export interface UseProjectSortReturn {
  sortField: SortField;
  sortOrder: SortOrder;
  handleSort: (field: SortField) => void;
}

export function useProjectSort(): UseProjectSortReturn {
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const handleSort = useCallback((field: SortField): void => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder(field === 'name' ? 'asc' : 'desc');
    }
  }, [sortField]);

  return {
    sortField,
    sortOrder,
    handleSort,
  };
}
