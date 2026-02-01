import { useState, useCallback, useMemo } from 'react';
import type { ConfigParameter, ConfigParameterUpdate } from '../types/config';

interface EditedParameter {
  value?: string;
  notes?: string | null;
}

interface UseConfigEditorProps {
  original: Record<string, ConfigParameter[]> | undefined;
}

interface UseConfigEditorReturn {
  editedValues: Map<string, EditedParameter>;
  updateValue: (name: string, value: string) => void;
  updateNotes: (name: string, notes: string) => void;
  validationErrors: string[];
  hasChanges: boolean;
  canSave: boolean;
  getUpdates: () => ConfigParameterUpdate[];
  reset: () => void;
}

const WEIGHT_CATEGORIES = [
  'Global Weights',
  'Quality Weights',
  'Time Weights',
  'Cost Weights',
  'Value Weights',
  'Satisfaction Weights',
  'Satisfaction Handsoff Weights',
  'Efficiency Weights',
  'Engineering Weights',
  'Risk Weights',
  'Test Maturity Weights',
];

const TOLERANCE = 0.001;

function validateWeights(
  original: Record<string, ConfigParameter[]> | undefined,
  changes: Map<string, EditedParameter>,
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
      const edited = changes.get(param.name);
      const value = edited?.value !== undefined ? Number.parseFloat(edited.value) : Number.parseFloat(param.value);

      if (Number.isNaN(value)) {
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
  const [editedValues, setEditedValues] = useState<Map<string, EditedParameter>>(new Map());

  const updateValue = useCallback((name: string, value: string): void => {
    setEditedValues((prev) => {
      const next = new Map(prev);
      const existing = next.get(name) || {};
      next.set(name, { ...existing, value });
      return next;
    });
  }, []);

  const updateNotes = useCallback((name: string, notes: string): void => {
    setEditedValues((prev) => {
      const next = new Map(prev);
      const existing = next.get(name) || {};
      next.set(name, { ...existing, notes });
      return next;
    });
  }, []);

  const validationErrors = useMemo(
    () => validateWeights(original, editedValues),
    [original, editedValues],
  );

  const hasChanges = editedValues.size > 0;
  const canSave = hasChanges && validationErrors.length === 0;

  const getUpdates = useCallback((): ConfigParameterUpdate[] => {
    if (!original) return [];

    const updates: ConfigParameterUpdate[] = [];

    editedValues.forEach((edited, name) => {
      // Find original parameter to get current value/notes if not edited
      let originalParam: ConfigParameter | undefined;
      for (const params of Object.values(original)) {
        originalParam = params.find(p => p.name === name);
        if (originalParam) break;
      }

      if (originalParam) {
        // Always include value (required by backend)
        const update: ConfigParameterUpdate = {
          name,
          value: edited.value ?? originalParam.value,
        };

        // Include notes if they were edited
        if (edited.notes !== undefined) {
          update.notes = edited.notes;
        }

        updates.push(update);
      }
    });

    return updates;
  }, [editedValues, original]);

  const reset = useCallback((): void => {
    setEditedValues(new Map());
  }, []);

  return {
    editedValues,
    updateValue,
    updateNotes,
    validationErrors,
    hasChanges,
    canSave,
    getUpdates,
    reset,
  };
}
