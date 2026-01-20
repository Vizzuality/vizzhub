import { useState, useCallback, useMemo } from 'react';
import type { ConfigParameter } from '../types/config';

interface UseConfigEditorProps {
  original: Record<string, ConfigParameter[]> | undefined;
}

interface UseConfigEditorReturn {
  editedValues: Map<string, string>;
  updateValue: (name: string, value: string) => void;
  validationErrors: string[];
  hasChanges: boolean;
  canSave: boolean;
  getUpdates: () => Array<{ name: string; value: string }>;
  reset: () => void;
}

const WEIGHT_CATEGORIES = [
  'global_weights',
  'quality_weights',
  'time_weights',
  'cost_weights',
  'value_weights',
  'satisfaction_weights',
  'flow_weights',
  'engineering_weights',
  'risk_weights',
  'test_maturity_weights',
];

const TOLERANCE = 0.001;

function validateWeights(
  original: Record<string, ConfigParameter[]> | undefined,
  changes: Map<string, string>,
): string[] {
  if (!original) {
    return [];
  }

  const errors: string[] = [];

  WEIGHT_CATEGORIES.forEach((category) => {
    const parameters = original[category];
    if (!parameters || parameters.length === 0) {
      return;
    }

    let sum = 0;
    parameters.forEach((param) => {
      const editedValue = changes.get(param.name);
      const value = editedValue !== undefined ? parseFloat(editedValue) : parseFloat(param.value);

      if (isNaN(value)) {
        errors.push(`Invalid number for ${param.name}`);
        return;
      }

      sum += value;
    });

    if (Math.abs(sum - 1.0) > TOLERANCE) {
      const categoryName = category.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
      errors.push(`${categoryName} must sum to 1.0 (currently ${sum.toFixed(4)})`);
    }
  });

  return errors;
}

export function useConfigEditor({ original }: UseConfigEditorProps): UseConfigEditorReturn {
  const [editedValues, setEditedValues] = useState<Map<string, string>>(new Map());

  const updateValue = useCallback((name: string, value: string): void => {
    setEditedValues((prev) => {
      const next = new Map(prev);
      next.set(name, value);
      return next;
    });
  }, []);

  const validationErrors = useMemo(
    () => validateWeights(original, editedValues),
    [original, editedValues],
  );

  const hasChanges = editedValues.size > 0;
  const canSave = hasChanges && validationErrors.length === 0;

  const getUpdates = useCallback((): Array<{ name: string; value: string }> => {
    return Array.from(editedValues.entries()).map(([name, value]) => ({ name, value }));
  }, [editedValues]);

  const reset = useCallback((): void => {
    setEditedValues(new Map());
  }, []);

  return {
    editedValues,
    updateValue,
    validationErrors,
    hasChanges,
    canSave,
    getUpdates,
    reset,
  };
}
