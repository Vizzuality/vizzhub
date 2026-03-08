import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useIsoConfig, useGitHubIsoConfig, useJiraIsoConfig } from '@/modules/iso/hooks/useIso';
import ProviderSnapshotTab from '@/modules/iso/components/ProviderSnapshotTab';

const snapshotsUrlSchema = {
  provider: { defaultValue: 'google_workspace' },
  page: { defaultValue: 1 },
};

export default function ISOSnapshots(): JSX.Element {
  const { state, setState } = useUrlState(snapshotsUrlSchema);
  const { data: gwConfig } = useIsoConfig();
  const { data: ghConfig } = useGitHubIsoConfig();
  const { data: jiraConfig } = useJiraIsoConfig();

  const gwConnected = gwConfig?.connected ?? false;
  const ghConnected = (ghConfig?.connected ?? false) && !!ghConfig?.org_name;
  const jiraConnected = jiraConfig?.connected ?? false;

  return (
    <Tabs
      value={state.provider}
      onValueChange={(provider) => setState({ provider, page: 1 })}
    >
      <TabsList>
        <TabsTrigger value="google_workspace">Google Workspace</TabsTrigger>
        <TabsTrigger value="github">GitHub</TabsTrigger>
        <TabsTrigger value="jira">Jira</TabsTrigger>
      </TabsList>

      <TabsContent value="google_workspace" className="mt-4">
        <ProviderSnapshotTab
          provider="google_workspace"
          providerLabel="Google Workspace"
          isConnected={gwConnected}
          page={state.provider === 'google_workspace' ? state.page : 1}
          onPageChange={(page) => setState({ page })}
        />
      </TabsContent>

      <TabsContent value="github" className="mt-4">
        <ProviderSnapshotTab
          provider="github"
          providerLabel="GitHub"
          isConnected={ghConnected}
          page={state.provider === 'github' ? state.page : 1}
          onPageChange={(page) => setState({ page })}
        />
      </TabsContent>

      <TabsContent value="jira" className="mt-4">
        <ProviderSnapshotTab
          provider="jira"
          providerLabel="Jira"
          isConnected={jiraConnected}
          page={state.provider === 'jira' ? state.page : 1}
          onPageChange={(page) => setState({ page })}
        />
      </TabsContent>
    </Tabs>
  );
}
