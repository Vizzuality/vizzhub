import { useState } from 'react';
import { useConfigParameters, useUpdateConfigParameters } from '../../hooks/useConfig';
import { useConfigEditor } from '../../hooks/useConfigEditor';
import { Pencil, Save, X, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ParameterSection } from '../ParameterSection';
import { ErrorHandler } from '../../utils/errorHandler';
import { logger } from '../../utils/logger';

const CONFIG_SECTIONS = [
  { key: 'Targets', showSumValidation: false },
  { key: 'Gates & Constants', showSumValidation: false },
  { key: 'Global Weights', showSumValidation: true },
  { key: 'Quality Weights', showSumValidation: true },
  { key: 'Time Weights', showSumValidation: true },
  { key: 'Cost Weights', showSumValidation: true },
  { key: 'Value Weights', showSumValidation: true },
  { key: 'Satisfaction Weights', showSumValidation: true },
  { key: 'Satisfaction Handsoff Weights', showSumValidation: true },
  { key: 'Efficiency Weights', showSumValidation: true },
  { key: 'Engineering Weights', showSumValidation: true },
  { key: 'Risk Weights', showSumValidation: true },
  { key: 'Test Maturity Weights', showSumValidation: true },
] as const;

export default function ConfigurationTab(): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [saveError, setSaveError] = useState<{ title: string; message: string } | null>(null);
  const { data: parameters, isLoading: configLoading, error } = useConfigParameters();
  const { mutateAsync: updateConfig } = useUpdateConfigParameters();

  logger.debug('ConfigurationTab state:', { parameters, configLoading, error });

  const {
    editedValues,
    updateValue,
    updateNotes,
    validationErrors,
    canSave,
    getUpdates,
    reset,
  } = useConfigEditor({ original: parameters });

  const handleSave = async (): Promise<void> => {
    setSaveError(null);
    try {
      const updates = getUpdates();
      logger.debug('Sending updates:', updates);
      await updateConfig(updates);
      setIsEditing(false);
      reset();
      setSaveError(null);
    } catch (err: unknown) {
      logger.error('Failed to save configuration:', err);
      const { title, message } = ErrorHandler.formatForDisplay(err);
      setSaveError({ title, message });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleCancel = (): void => {
    setIsEditing(false);
    reset();
    setSaveError(null);
  };

  if (configLoading) {
    return <LoadingSpinner />;
  }

  if (!parameters) {
    return (
      <div className="text-destructive p-6">
        <h2 className="text-xl font-semibold mb-2">Failed to load configuration</h2>
        {error && <p className="text-sm">Error: {error.toString()}</p>}
        <p className="text-sm mt-2">Check browser console for details</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <Button variant="ghost" onClick={handleCancel} className="border">
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={!canSave}>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </>
          ) : (
            <Button onClick={() => setIsEditing(true)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit Configuration
            </Button>
          )}
        </div>
      </div>

      {saveError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{saveError.title}</AlertTitle>
          <AlertDescription className="whitespace-pre-wrap mt-2">
            {saveError.message}
          </AlertDescription>
        </Alert>
      )}

      {isEditing && validationErrors.length > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Validation Errors</AlertTitle>
          <AlertDescription>
            <ul className="list-disc list-inside space-y-1 mt-2">
              {validationErrors.map((validationError) => (
                <li key={validationError} className="text-sm">
                  {validationError}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-6">
        {CONFIG_SECTIONS.map(({ key, showSumValidation }) =>
          parameters[key] ? (
            <ParameterSection
              key={key}
              title={key}
              parameters={parameters[key]}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
              showSumValidation={showSumValidation}
            />
          ) : null
        )}
      </div>
    </div>
  );
}
