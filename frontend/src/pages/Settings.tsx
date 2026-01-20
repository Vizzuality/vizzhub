import { useState } from 'react';
import { useConfigParameters, useUpdateConfigParameters } from '../hooks/useConfig';
import { useConfigEditor } from '../hooks/useConfigEditor';
import { Pencil, Save, X, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ConfigSection } from '../components/ConfigSection';
import { WeightsSection } from '../components/WeightsSection';
import { ErrorHandler } from '../utils/errorHandler';

export default function Settings(): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [saveError, setSaveError] = useState<{ title: string; message: string } | null>(null);
  const { data: parameters, isLoading: configLoading, error } = useConfigParameters();
  const { mutateAsync: updateConfig } = useUpdateConfigParameters();

  console.log('Settings Debug:', { parameters, configLoading, error });

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
      console.log('Sending updates:', updates);
      await updateConfig(updates);
      setIsEditing(false);
      reset();
      setSaveError(null);
    } catch (error: any) {
      console.error('Failed to save configuration:', error);

      const { title, message } = ErrorHandler.formatForDisplay(error);
      setSaveError({ title, message });

      // Scroll to top to show error
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleCancel = (): void => {
    setIsEditing(false);
    reset();
    setSaveError(null);
  };

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
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
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
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
              {validationErrors.map((error, idx) => (
                <li key={idx} className="text-sm">
                  {error}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-6">
          {parameters['Targets'] && (
            <ConfigSection
              title="Targets"
              parameters={parameters['Targets']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Gates & Constants'] && (
            <ConfigSection
              title="Gates & Constants"
              parameters={parameters['Gates & Constants']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Global Weights'] && (
            <WeightsSection
              title="Global Weights"
              parameters={parameters['Global Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Quality Weights'] && (
            <WeightsSection
              title="Quality Weights"
              parameters={parameters['Quality Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Time Weights'] && (
            <WeightsSection
              title="Time Weights"
              parameters={parameters['Time Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Cost Weights'] && (
            <WeightsSection
              title="Cost Weights"
              parameters={parameters['Cost Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Value Weights'] && (
            <WeightsSection
              title="Value Weights"
              parameters={parameters['Value Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Satisfaction Weights'] && (
            <WeightsSection
              title="Satisfaction Weights"
              parameters={parameters['Satisfaction Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Satisfaction Handsoff Weights'] && (
            <WeightsSection
              title="Satisfaction Handsoff Weights"
              parameters={parameters['Satisfaction Handsoff Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Efficiency Weights'] && (
            <WeightsSection
              title="Efficiency Weights"
              parameters={parameters['Efficiency Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Engineering Weights'] && (
            <WeightsSection
              title="Engineering Weights"
              parameters={parameters['Engineering Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Risk Weights'] && (
            <WeightsSection
              title="Risk Weights"
              parameters={parameters['Risk Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}

          {parameters['Test Maturity Weights'] && (
            <WeightsSection
              title="Test Maturity Weights"
              parameters={parameters['Test Maturity Weights']}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
              onNotesChange={updateNotes}
            />
          )}
      </div>
    </div>
  );
}

