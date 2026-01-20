import type { ConfigParameter } from '../types/config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface EditedParameter {
  value?: string;
  notes?: string | null;
}

interface WeightsSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, EditedParameter>;
  onValueChange: (name: string, value: string) => void;
  onNotesChange: (name: string, notes: string) => void;
}

export function WeightsSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
  onNotesChange,
}: WeightsSectionProps): JSX.Element {
  const calculateSum = (): number => {
    return parameters.reduce((sum, param) => {
      const edited = editedValues.get(param.name);
      const value = edited?.value ?? param.value;
      return sum + parseFloat(value || '0');
    }, 0);
  };

  const sum = calculateSum();
  const isValid = Math.abs(sum - 1.0) <= 0.001;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{title}</span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-normal text-muted-foreground">
              Sum: {sum.toFixed(2)}
            </span>
            <span
              className={`text-sm font-semibold ${
                isValid ? 'text-green-600' : 'text-destructive'
              }`}
            >
              {isValid ? '✓' : '✗ Must equal 1.0'}
            </span>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {parameters.map((param) => {
            const edited = editedValues.get(param.name);
            // Format initial value to 2 decimals, but keep edited value as-is (user might be typing)
            const displayValue = edited?.value ?? parseFloat(param.value).toFixed(2);
            const currentNotes = edited?.notes ?? param.notes;

            return (
              <div key={param.name} className="grid grid-cols-3 gap-4 items-start">
                <div className="font-medium">
                  {param.name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </div>
                <div>
                  {isEditing ? (
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={displayValue}
                      onChange={(e) => onValueChange(param.name, e.target.value)}
                      className="max-w-xs"
                    />
                  ) : (
                    <span className="text-muted-foreground">
                      {parseFloat(param.value).toFixed(2)}
                    </span>
                  )}
                </div>
                <div>
                  {isEditing ? (
                    <Textarea
                      value={currentNotes || ''}
                      onChange={(e) => onNotesChange(param.name, e.target.value)}
                      placeholder="Add notes..."
                      className="text-sm resize-none"
                      rows={2}
                    />
                  ) : (
                    currentNotes && (
                      <div className="text-sm text-muted-foreground">
                        {currentNotes}
                      </div>
                    )
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
