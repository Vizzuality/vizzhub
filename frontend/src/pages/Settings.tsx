import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ConfigurationTab from '../components/Settings/ConfigurationTab';
import JobsTab from '../components/Settings/JobsTab';
import SlackTab from '../components/Settings/SlackTab';

export default function Settings(): JSX.Element {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>

      <Tabs defaultValue="configuration">
        <TabsList>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="slack">Slack</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
        </TabsList>

        <TabsContent value="configuration">
          <ConfigurationTab />
        </TabsContent>

        <TabsContent value="slack">
          <SlackTab />
        </TabsContent>

        <TabsContent value="jobs">
          <JobsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
