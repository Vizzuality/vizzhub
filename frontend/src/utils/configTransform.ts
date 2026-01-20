import type { ScoringConfig } from '../types';
import type { ConfigParameter } from '../types/config';

export function transformConfigToParameters(
  config: ScoringConfig | undefined,
): Record<string, ConfigParameter[]> {
  if (!config) {
    return {};
  }

  return {
    targets: [
      { name: 'defect_density', value: String(config.targets.defect_density), notes: 'Bugs per 100 tasks' },
      { name: 'escaped_rate', value: String(config.targets.escaped_rate), notes: 'Escaped defects ratio' },
      { name: 'mttr_hours', value: String(config.targets.mttr_hours), unit: 'hours', notes: 'Mean time to resolve' },
      { name: 'spi', value: String(config.targets.spi), notes: 'Schedule performance index' },
      { name: 'cpi', value: String(config.targets.cpi), notes: 'Cost performance index' },
      { name: 'lead_time_days', value: String(config.targets.lead_time_days), unit: 'days', notes: 'Lead time target' },
      { name: 'flow_efficiency', value: String(config.targets.flow_efficiency), notes: 'Flow efficiency ratio' },
      { name: 'high_vuln_count', value: String(config.targets.high_vuln_count), notes: 'Max high severity vulnerabilities' },
      { name: 'gov_exceptions', value: String(config.targets.gov_exceptions), notes: 'Governance exceptions allowed' },
      { name: 'pr_no_review_ratio', value: String(config.targets.pr_no_review_ratio), notes: 'PRs without review ratio' },
    ],
    constants: [
      { name: 'sev1_cap', value: String(config.constants.sev1_cap), notes: 'Quality score cap for Sev1 incidents' },
      { name: 'grace_days', value: String(config.constants.grace_days), unit: 'days', notes: 'Milestone grace period' },
    ],
    global_weights: [
      { name: 'time', value: String(config.global_weights.time) },
      { name: 'cost', value: String(config.global_weights.cost) },
      { name: 'quality', value: String(config.global_weights.quality) },
      { name: 'value', value: String(config.global_weights.value) },
      { name: 'satisfaction', value: String(config.global_weights.satisfaction) },
      { name: 'flow', value: String(config.global_weights.flow) },
      { name: 'engineering', value: String(config.global_weights.engineering) },
      { name: 'risk', value: String(config.global_weights.risk) },
    ],
  };
}
