import { useQuery } from '@tanstack/react-query';
import { integrationsApi } from '@/core/services/integrations';
import { queryKeys } from '@/core/hooks/queryKeys';
import JiraCard from './JiraCard';
import ISOConfig from '@/modules/iso/pages/ISOConfig';
import GitHubCard from './GitHubCard';
import SlackTab from './SlackTab';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

export default function IntegrationsTab(): JSX.Element {
  const { data: status, isLoading } = useQuery({
    queryKey: queryKeys.integrations.status,
    queryFn: integrationsApi.getStatus,
  });

  if (isLoading) {
    return <LoadingSpinner className="py-12" />;
  }

  return (
    <div className="space-y-6">
      <JiraCard status={status?.jira} />
      <ISOConfig />
      <GitHubCard status={status?.github} />
      <SlackTab
        status={status?.slack}
        slackSettings={status?.slack_settings}
      />
    </div>
  );
}
