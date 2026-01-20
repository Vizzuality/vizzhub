import type { ConfigParameter } from '../types/config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface EditedParameter {
  value?: string;
  notes?: string | null;
}

interface ConfigSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, EditedParameter>;
  onValueChange: (name: string, value: string) => void;
  onNotesChange: (name: string, notes: string) => void;
}

export function ConfigSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
  onNotesChange,
}: ConfigSectionProps): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {parameters.map((param) => {
            const edited = editedValues.get(param.name);
            // Format initial value to 2 decimals if numeric, but keep edited value as-is
            const displayValue = edited?.value ?? (
              !isNaN(parseFloat(param.value))
                ? parseFloat(param.value).toFixed(2)
                : param.value
            );
            const currentNotes = edited?.notes ?? param.notes;

            return (
              <div key={param.name} className="grid grid-cols-3 gap-4 items-start">
                <div className="font-medium">
                  {param.name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </div>
                <div>
                  {isEditing ? (
                    <Input
                      type="text"
                      value={displayValue}
                      onChange={(e) => onValueChange(param.name, e.target.value)}
                      className="max-w-xs"
                    />
                  ) : (
                    <span className="text-muted-foreground">
                      {!isNaN(parseFloat(param.value))
                        ? parseFloat(param.value).toFixed(2)
                        : param.value}
                      {param.unit && ` ${param.unit}`}
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
