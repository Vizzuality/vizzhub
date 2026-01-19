import { useScoringConfig, useConfigValidation } from '../hooks/useScores';
import { CheckCircle, XCircle } from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

export default function Settings(): JSX.Element {
  const { data: config, isLoading: configLoading } = useScoringConfig();
  const { data: validation } = useConfigValidation();

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!config) {
    return <div className="text-destructive">Failed to load configuration</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Targets</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
            <ConfigItem label="Defect Density" value={config.targets.defect_density} unit="/100 tasks" />
            <ConfigItem label="Escaped Rate" value={config.targets.escaped_rate} unit="/100 tasks" />
            <ConfigItem label="MTTR" value={config.targets.mttr_hours} unit="hours" />
            <ConfigItem label="SPI Target" value={config.targets.spi} />
            <ConfigItem label="CPI Target" value={config.targets.cpi} />
            <ConfigItem label="Lead Time" value={config.targets.lead_time_days} unit="days" />
            <ConfigItem label="Flow Efficiency" value={config.targets.flow_efficiency} />
            <ConfigItem label="High Vulns (max)" value={config.targets.high_vuln_count} />
            <ConfigItem label="Gov Exceptions (max)" value={config.targets.gov_exceptions} />
            <ConfigItem label="PR No Review (max)" value={config.targets.pr_no_review_ratio} />
          </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Global Weights</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
            <ConfigItem label="Time" value={`${config.global_weights.time * 100}%`} />
            <ConfigItem label="Cost" value={`${config.global_weights.cost * 100}%`} />
            <ConfigItem label="Quality" value={`${config.global_weights.quality * 100}%`} />
            <ConfigItem label="Value" value={`${config.global_weights.value * 100}%`} />
            <ConfigItem label="Satisfaction" value={`${config.global_weights.satisfaction * 100}%`} />
            <ConfigItem label="Flow" value={`${config.global_weights.flow * 100}%`} />
            <ConfigItem label="Engineering" value={`${config.global_weights.engineering * 100}%`} />
            <ConfigItem label="Risk" value={`${config.global_weights.risk * 100}%`} />
          </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Constants</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
            <ConfigItem label="Sev1 Cap" value={config.constants.sev1_cap} unit="points" />
            <ConfigItem label="Grace Days" value={config.constants.grace_days} unit="days" />
          </dl>
          </CardContent>
        </Card>

        {validation && (
          <Card>
            <CardHeader>
              <CardTitle>Weight Validation</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2 mb-4">
              {validation.valid ? (
                <>
                  <CheckCircle className="w-5 h-5 text-primary" />
                  <span className="text-primary">All weight groups are valid</span>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-destructive" />
                  <span className="text-destructive">Some weight groups are invalid</span>
                </>
              )}
            </div>
            <dl className="space-y-2">
              {Object.entries(validation.groups).map(([group, valid]) => (
                <div key={group} className="flex items-center justify-between">
                  <span className="text-muted-foreground capitalize">{group}</span>
                  {valid ? (
                    <CheckCircle className="w-4 h-4 text-primary" />
                  ) : (
                    <XCircle className="w-4 h-4 text-destructive" />
                  )}
                </div>
              ))}
            </dl>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

interface ConfigItemProps {
  label: string;
  value: string | number;
  unit?: string;
}

function ConfigItem({ label, value, unit }: ConfigItemProps): JSX.Element {
  return (
    <div className="flex items-center justify-between py-1 border-b border-border last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">
        {value}
        {unit && <span className="text-muted-foreground ml-1">{unit}</span>}
      </dd>
    </div>
  );
}
