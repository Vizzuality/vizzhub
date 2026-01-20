import { CheckCircle, XCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { ParameterRow } from './ParameterRow';
import { ConfigParameter } from '../../types/config';

interface WeightsSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, string>;
  onValueChange: (name: string, value: string) => void;
}

export function WeightsSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
}: WeightsSectionProps): JSX.Element {
  const sum = parameters.reduce((total, param) => {
    const value = editedValues.get(param.name) || param.value;
    return total + parseFloat(value);
  }, 0);

  const isValid = Math.abs(sum - 1.0) < 0.001;

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <CardTitle>{title}</CardTitle>
          {isEditing && (
            <div className="flex gap-2 items-center">
              <span className="text-sm text-muted-foreground">
                Sum: {sum.toFixed(4)}
              </span>
              {isValid ? (
                <CheckCircle className="w-5 h-5 text-primary" />
              ) : (
                <XCircle className="w-5 h-5 text-destructive" />
              )}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {parameters.map((param) => (
            <ParameterRow
              key={param.name}
              parameter={param}
              isEditing={isEditing}
              value={editedValues.get(param.name) || param.value}
              onValueChange={onValueChange}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
