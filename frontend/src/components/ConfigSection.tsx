import type { ConfigParameter } from '../types/config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface ConfigSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, string>;
  onValueChange: (name: string, value: string) => void;
}

export function ConfigSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
}: ConfigSectionProps): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
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
                      type="text"
                      value={currentValue}
                      onChange={(e) => onValueChange(param.name, e.target.value)}
                      className="max-w-xs"
                    />
                  ) : (
                    <span className="text-muted-foreground">
                      {currentValue}
                      {param.unit && ` ${param.unit}`}
                    </span>
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
