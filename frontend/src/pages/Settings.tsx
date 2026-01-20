import { useState } from 'react';
import { useConfigParameters, useConfigValidation, useUpdateConfigParameters } from '../hooks/useConfig';
import { useConfigEditor } from '../hooks/useConfigEditor';
import { Pencil, Save, X, CheckCircle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ConfigSection } from '../components/ConfigSection';
import { WeightsSection } from '../components/WeightsSection';

export default function Settings(): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const { data: parameters, isLoading: configLoading } = useConfigParameters();
  const { data: validation } = useConfigValidation();
  const { mutateAsync: updateConfig } = useUpdateConfigParameters();

  const {
    editedValues,
    updateValue,
    validationErrors,
    canSave,
    getUpdates,
    reset,
  } = useConfigEditor({ original: parameters });

  const handleSave = async (): Promise<void> => {
    try {
      const updates = getUpdates();
      await updateConfig(updates);
      setIsEditing(false);
      reset();
    } catch (error) {
      console.error('Failed to save configuration:', error);
    }
  };

  const handleCancel = (): void => {
    setIsEditing(false);
    reset();
  };

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!parameters) {
    return <div className="text-destructive">Failed to load configuration</div>;
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

      {isEditing && validationErrors.length > 0 && (
        <Card className="bg-destructive/10 border-destructive">
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-2">Validation Errors:</h3>
            <ul className="list-disc list-inside space-y-1">
              {validationErrors.map((error, idx) => (
                <li key={idx} className="text-sm text-destructive">
                  {error}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="config">
        <TabsList>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
        </TabsList>

        <TabsContent value="config" className="space-y-6">
          {parameters.targets && (
            <ConfigSection
              title="Targets"
              parameters={parameters.targets}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
            />
          )}

          {parameters.constants && (
            <ConfigSection
              title="Gates & Constants"
              parameters={parameters.constants}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
            />
          )}

          {parameters.global_weights && (
            <WeightsSection
              title="Global Weights"
              parameters={parameters.global_weights}
              isEditing={isEditing}
              editedValues={editedValues}
              onValueChange={updateValue}
            />
          )}
        </TabsContent>

        <TabsContent value="validation">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {validation?.valid ? (
                  <>
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    <span>Configuration Valid</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-5 w-5 text-destructive" />
                    <span>Validation Issues Found</span>
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {validation?.groups && (
                <div className="space-y-2">
                  {Object.entries(validation.groups).map(([group, isValid]) => (
                    <div key={group} className="flex items-center gap-2">
                      {isValid ? (
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      ) : (
                        <XCircle className="h-4 w-4 text-destructive" />
                      )}
                      <span className="capitalize">
                        {group.replace(/_/g, ' ')}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

