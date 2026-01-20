import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { ParameterRow } from './ParameterRow';
import { ConfigParameter } from '../../types/config';

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
