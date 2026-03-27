import { useCallback, useRef, useState } from 'react';

export interface CellCoord {
  projectId: string;
  userId: string;
  week: string;
}

function cellKey(c: CellCoord): string {
  return `${c.projectId}:${c.userId}:${c.week}`;
}

function buildRange(
  a: CellCoord,
  b: CellCoord,
  allCoords: CellCoord[],
): Set<string> {
  const weeks = [...new Set(allCoords.map((c) => c.week))].sort();
  const rowKeys = [...new Set(allCoords.map((c) => `${c.projectId}:${c.userId}`))];

  const w1 = weeks.indexOf(a.week);
  const w2 = weeks.indexOf(b.week);
  const wMin = Math.min(w1, w2);
  const wMax = Math.max(w1, w2);

  const r1 = rowKeys.indexOf(`${a.projectId}:${a.userId}`);
  const r2 = rowKeys.indexOf(`${b.projectId}:${b.userId}`);
  const rMin = Math.min(r1, r2);
  const rMax = Math.max(r1, r2);

  const result = new Set<string>();
  for (let ri = rMin; ri <= rMax; ri++) {
    const [pId, uId] = rowKeys[ri].split(':');
    for (let wi = wMin; wi <= wMax; wi++) {
      result.add(`${pId}:${uId}:${weeks[wi]}`);
    }
  }
  return result;
}

export interface CellSelection {
  selected: Set<string>;
  anchorRef: React.RefObject<CellCoord | null>;
  isDragging: React.RefObject<boolean>;
  handleCellMouseDown: (coord: CellCoord, shiftKey: boolean) => void;
  handleCellMouseEnter: (coord: CellCoord) => void;
  handleMouseUp: () => void;
  clearSelection: () => void;
  allCoordsRef: React.MutableRefObject<CellCoord[]>;
  isSelected: (coord: CellCoord) => boolean;
}

export function useCellSelection(): CellSelection {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const anchorRef = useRef<CellCoord | null>(null);
  const isDragging = useRef(false);
  const allCoordsRef = useRef<CellCoord[]>([]);

  const isSelected = useCallback(
    (coord: CellCoord): boolean => selected.has(cellKey(coord)),
    [selected],
  );

  const handleCellMouseDown = useCallback(
    (coord: CellCoord, shiftKey: boolean): void => {
      if (shiftKey && anchorRef.current) {
        const range = buildRange(anchorRef.current, coord, allCoordsRef.current);
        setSelected(range);
      } else {
        anchorRef.current = coord;
        setSelected(new Set([cellKey(coord)]));
      }
      isDragging.current = true;
    },
    [],
  );

  const handleCellMouseEnter = useCallback(
    (coord: CellCoord): void => {
      if (!isDragging.current || !anchorRef.current) return;
      const range = buildRange(anchorRef.current, coord, allCoordsRef.current);
      setSelected(range);
    },
    [],
  );

  const handleMouseUp = useCallback((): void => {
    isDragging.current = false;
  }, []);

  const clearSelection = useCallback((): void => {
    setSelected(new Set());
    anchorRef.current = null;
  }, []);

  return {
    selected,
    anchorRef,
    isDragging,
    handleCellMouseDown,
    handleCellMouseEnter,
    handleMouseUp,
    clearSelection,
    allCoordsRef,
    isSelected,
  };
}
