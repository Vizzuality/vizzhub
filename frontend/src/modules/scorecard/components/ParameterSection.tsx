import type { ConfigParameter } from '../types/config';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';

interface EditedParameter {
  value?: string;
  notes?: string | null;
}

interface ParameterSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, EditedParameter>;
  onValueChange: (name: string, value: string) => void;
  onNotesChange: (name: string, notes: string) => void;
  showSumValidation?: boolean;
}

function formatDisplayValue(value: string, edited: EditedParameter | undefined): string {
  if (edited?.value !== undefined) return edited.value;
  const num = Number.parseFloat(value);
  return !Number.isNaN(num) ? num.toFixed(2) : value;
}

function formatReadonlyValue(value: string, unit?: string | null): string {
  const num = Number.parseFloat(value);
  const formatted = !Number.isNaN(num) ? num.toFixed(2) : value;
  return unit ? `${formatted} ${unit}` : formatted;
}

function formatParamName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
}

export function ParameterSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
  onNotesChange,
  showSumValidation = false,
}: Readonly<ParameterSectionProps>): JSX.Element {
  const sum = showSumValidation
    ? parameters.reduce((acc, param) => {
        const edited = editedValues.get(param.name);
        const value = edited?.value ?? param.value;
        return acc + Number.parseFloat(value || '0');
      }, 0)
    : 0;

  const isValid = Math.abs(sum - 1.0) <= 0.001;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{title}</span>
          {showSumValidation && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-normal text-muted-foreground">
                Sum: {sum.toFixed(2)}
              </span>
              <span
                className={`text-sm font-semibold ${
                  isValid ? 'text-score-green' : 'text-destructive'
                }`}
              >
                {isValid ? '✓' : '✗ Must equal 1.0'}
              </span>
            </div>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {parameters.map((param) => {
            const edited = editedValues.get(param.name);
            const displayValue = formatDisplayValue(param.value, edited);
            const currentNotes = edited?.notes ?? param.notes;

            return (
              <div key={param.name} className="grid grid-cols-3 gap-4 items-start">
                <div className="text-sm">{formatParamName(param.name)}</div>
                <div>
                  {isEditing ? (
                    <Input
                      type={showSumValidation ? 'number' : 'text'}
                      step={showSumValidation ? '0.01' : undefined}
                      min={showSumValidation ? '0' : undefined}
                      max={showSumValidation ? '1' : undefined}
                      value={displayValue}
                      onChange={(e) => onValueChange(param.name, e.target.value)}
                      className="max-w-xs"
                    />
                  ) : (
                    <span className="text-muted-foreground">
                      {formatReadonlyValue(param.value, param.unit)}
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
                      <div className="text-sm text-muted-foreground">{currentNotes}</div>
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
