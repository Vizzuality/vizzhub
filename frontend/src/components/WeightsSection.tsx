import type { ConfigParameter } from '../types/config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

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
  const calculateSum = (): number => {
    return parameters.reduce((sum, param) => {
      const value = editedValues.get(param.name) ?? param.value;
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
          <span
            className={`text-sm font-normal ${
              isValid ? 'text-green-600' : 'text-destructive'
            }`}
          >
            Sum: {sum.toFixed(4)} {isValid ? '✓' : '✗'}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {parameters.map((param) => {
            const currentValue = editedValues.get(param.name) ?? param.value;
            return (
              <div key={param.name} className="grid grid-cols-3 gap-4 items-center">
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
                      value={currentValue}
                      onChange={(e) => onValueChange(param.name, e.target.value)}
                      className="max-w-xs"
                    />
                  ) : (
                    <span className="text-muted-foreground">{currentValue}</span>
                  )}
                </div>
                {param.notes && (
                  <div className="text-sm text-muted-foreground">{param.notes}</div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
