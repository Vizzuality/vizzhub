import { Input } from '../ui/input';
import { ConfigParameter } from '../../types/config';

interface ParameterRowProps {
  parameter: ConfigParameter;
  isEditing: boolean;
  value: string;
  onValueChange: (name: string, value: string) => void;
}

export function ParameterRow({
  parameter,
  isEditing,
  value,
  onValueChange,
}: ParameterRowProps): JSX.Element {
  return (
    <div className="flex justify-between py-2 border-b last:border-0">
      <div className="flex flex-col">
        <span className="font-medium">{parameter.name}</span>
        {parameter.notes && (
          <span className="text-sm text-muted-foreground">
            {parameter.notes}
          </span>
        )}
      </div>
      <div className="flex gap-2 items-center">
        {isEditing ? (
          <Input
            type="number"
            step="0.01"
            className="w-24"
            value={value}
            onChange={(e) => onValueChange(parameter.name, e.target.value)}
          />
        ) : (
          <span className="font-medium">{parameter.value}</span>
        )}
        {parameter.unit && (
          <span className="text-sm text-muted-foreground min-w-[120px]">
            {parameter.unit}
          </span>
        )}
      </div>
    </div>
  );
}
