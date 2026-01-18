import { useScoringConfig, useConfigValidation } from '../hooks/useScores';
import { CheckCircle, XCircle } from 'lucide-react';

export default function Settings(): JSX.Element {
  const { data: config, isLoading: configLoading } = useScoringConfig();
  const { data: validation } = useConfigValidation();

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!config) {
    return <div className="text-red-500">Failed to load configuration</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Targets</h2>
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
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Global Weights</h2>
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
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Constants</h2>
          <dl className="space-y-3">
            <ConfigItem label="Sev1 Cap" value={config.constants.sev1_cap} unit="points" />
            <ConfigItem label="Grace Days" value={config.constants.grace_days} unit="days" />
          </dl>
        </div>

        {validation && (
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Weight Validation</h2>
            <div className="flex items-center gap-2 mb-4">
              {validation.valid ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <span className="text-green-700">All weight groups are valid</span>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-red-500" />
                  <span className="text-red-700">Some weight groups are invalid</span>
                </>
              )}
            </div>
            <dl className="space-y-2">
              {Object.entries(validation.groups).map(([group, valid]) => (
                <div key={group} className="flex items-center justify-between">
                  <span className="text-gray-600 capitalize">{group}</span>
                  {valid ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                </div>
              ))}
            </dl>
          </div>
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
    <div className="flex items-center justify-between py-1 border-b border-gray-100 last:border-0">
      <dt className="text-gray-600">{label}</dt>
      <dd className="font-medium">
        {value}
        {unit && <span className="text-gray-400 ml-1">{unit}</span>}
      </dd>
    </div>
  );
}
