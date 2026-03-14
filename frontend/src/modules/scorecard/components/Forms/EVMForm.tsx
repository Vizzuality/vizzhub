import { useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { Info, Calculator, DollarSign, TrendingUp, Clock } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import {
  formatCurrency,
  getPerformanceColor,
  getPerformanceLabel,
} from '@/shared/utils/evmCalculations';
import type { EVMData } from '../../types';

interface EVMFormData {
  budget_total: string;
  cost_to_date: string;
  percent_completed: string;
  percent_planned: string;
}

interface EVMFormProps {
  initialData?: EVMData;
  onSubmit: (data: EVMData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

interface FieldConfig {
  name: keyof EVMFormData;
  label: string;
  icon: typeof DollarSign;
  tooltip: string;
  placeholder: string;
  suffix?: string;
  max?: number;
}

const FIELDS: FieldConfig[] = [
  {
    name: 'budget_total',
    label: 'Total Budget',
    icon: DollarSign,
    tooltip: 'The total planned budget for the entire project (Planned Value)',
    placeholder: 'e.g., 100000',
  },
  {
    name: 'cost_to_date',
    label: 'Actual Cost',
    icon: TrendingUp,
    tooltip: 'The actual expenses incurred to date (Actual Cost)',
    placeholder: 'e.g., 45000',
  },
  {
    name: 'percent_completed',
    label: 'Work Completed',
    icon: Calculator,
    tooltip: 'Estimated percentage of the total work completed (0-100%)',
    placeholder: 'e.g., 50',
    suffix: '%',
    max: 100,
  },
  {
    name: 'percent_planned',
    label: 'Expected Progress',
    icon: Clock,
    tooltip: 'Percentage of work that should be done by now according to schedule (0-100%)',
    placeholder: 'e.g., 45',
    suffix: '%',
    max: 100,
  },
];

export default function EVMForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: EVMFormProps): JSX.Element {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<EVMFormData>({
    defaultValues: {
      budget_total: initialData?.budget_total?.toString() ?? '',
      cost_to_date: initialData?.cost_to_date?.toString() ?? '',
      percent_completed: initialData?.percent_completed
        ? (initialData.percent_completed * 100).toString()
        : '',
      percent_planned: initialData?.percent_planned
        ? (initialData.percent_planned * 100).toString()
        : '',
    },
  });

  const watchedValues = watch();

  const calculatedValues = useMemo(() => {
    const budget = Number.parseFloat(watchedValues.budget_total) || 0;
    const cost = Number.parseFloat(watchedValues.cost_to_date) || 0;
    const completed = (Number.parseFloat(watchedValues.percent_completed) || 0) / 100;
    const planned = (Number.parseFloat(watchedValues.percent_planned) || 0) / 100;

    const ev = budget * completed;
    const spi = planned > 0 ? completed / planned : null;
    const cpi = cost > 0 ? ev / cost : null;

    return { ev, spi, cpi, hasData: budget > 0 };
  }, [watchedValues]);

  const handleFormSubmit = (data: EVMFormData): void => {
    const payload: EVMData = {
      budget_total: Number.parseFloat(data.budget_total),
      cost_to_date: Number.parseFloat(data.cost_to_date),
      percent_completed: Number.parseFloat(data.percent_completed) / 100,
      percent_planned: Number.parseFloat(data.percent_planned) / 100,
    };
    onSubmit(payload);
  };

  return (
    <TooltipProvider>
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FIELDS.map((field) => {
            const Icon = field.icon;
            return (
              <div key={field.name} className="space-y-2">
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <Label htmlFor={field.name}>{field.label}</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs">
                      <p className="text-sm">{field.tooltip}</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="relative">
                  <Input
                    id={field.name}
                    type="number"
                    step="any"
                    min="0"
                    max={field.max}
                    placeholder={field.placeholder}
                    {...register(field.name, {
                      required: `${field.label} is required`,
                      min: { value: 0, message: 'Must be positive' },
                      max: field.max
                        ? { value: field.max, message: `Max ${field.max}%` }
                        : undefined,
                    })}
                    className={field.suffix ? 'pr-8' : ''}
                  />
                  {field.suffix && (
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                      {field.suffix}
                    </span>
                  )}
                </div>
                {errors[field.name] && (
                  <p className="text-sm text-destructive">{errors[field.name]?.message}</p>
                )}
              </div>
            );
          })}
        </div>

        {calculatedValues.hasData && (
          <Card className="bg-muted/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Calculator className="w-4 h-4" />
                Calculated Values
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-3 bg-background rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-muted-foreground">Earned Value (EV)</p>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button type="button" className="text-muted-foreground">
                          <Info className="h-3 w-3" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-sm">Budget × Work Completed</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <p className="text-lg font-semibold">{formatCurrency(calculatedValues.ev)}</p>
                </div>

                <div className="p-3 bg-background rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-muted-foreground">Schedule Performance (SPI)</p>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button type="button" className="text-muted-foreground">
                          <Info className="h-3 w-3" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-sm">Work Completed / Expected Progress</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          &gt;1 = ahead, 1 = on track, &lt;1 = behind
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  {calculatedValues.spi !== null ? (
                    <>
                      <p className={`text-lg font-semibold ${getPerformanceColor(calculatedValues.spi)}`}>
                        {calculatedValues.spi.toFixed(2)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {getPerformanceLabel(calculatedValues.spi, 'spi')}
                      </p>
                    </>
                  ) : (
                    <p className="text-lg font-semibold text-muted-foreground">—</p>
                  )}
                </div>

                <div className="p-3 bg-background rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs text-muted-foreground">Cost Performance (CPI)</p>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button type="button" className="text-muted-foreground">
                          <Info className="h-3 w-3" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-sm">Earned Value / Actual Cost</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          &gt;1 = under budget, 1 = on budget, &lt;1 = over budget
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  {calculatedValues.cpi !== null ? (
                    <>
                      <p className={`text-lg font-semibold ${getPerformanceColor(calculatedValues.cpi)}`}>
                        {calculatedValues.cpi.toFixed(2)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {getPerformanceLabel(calculatedValues.cpi, 'cpi')}
                      </p>
                    </>
                  ) : (
                    <p className="text-lg font-semibold text-muted-foreground">—</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="flex justify-end gap-2 pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={isLoading}
            className="border border-input"
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save EVM Data'}
          </Button>
        </div>
      </form>
    </TooltipProvider>
  );
}
