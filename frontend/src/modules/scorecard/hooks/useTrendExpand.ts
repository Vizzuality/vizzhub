import { useState, useCallback } from 'react';

interface UseTrendExpandReturn {
  showTrend: boolean;
  expanded: boolean;
  toggleTrend: () => void;
  toggleExpand: () => void;
  setExpanded: (value: boolean) => void;
}

/**
 * Hook for managing trend chart visibility and expansion state.
 * Used in metric cards to show/hide historical trend charts and expand them to full view.
 *
 * @returns Object containing:
 *   - showTrend: Whether the inline trend chart is visible
 *   - expanded: Whether the full-screen trend dialog is open
 *   - toggleTrend: Toggle trend visibility (closes expanded if hiding)
 *   - toggleExpand: Toggle expanded state
 *   - setExpanded: Set expanded state directly (for dialog onOpenChange)
 */
export function useTrendExpand(): UseTrendExpandReturn {
  const [showTrend, setShowTrend] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const toggleTrend = useCallback((): void => {
    setShowTrend((prev) => {
      if (prev) {
        setExpanded(false);
      }
      return !prev;
    });
  }, []);

  const toggleExpand = useCallback((): void => {
    setExpanded((prev) => !prev);
  }, []);

  return {
    showTrend,
    expanded,
    toggleTrend,
    toggleExpand,
    setExpanded,
  };
}
