import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ConfigurationTab from '../components/Settings/ConfigurationTab';
import SlackTab from '../components/Settings/SlackTab';
import AlertLogTab from '../components/NotificationsAdmin/AlertLogTab';
import SilencesTab from '../components/NotificationsAdmin/SilencesTab';
import AlertConfigTab from '../components/NotificationsAdmin/AlertConfigTab';
import StatisticsTab from '../components/NotificationsAdmin/StatisticsTab';
import JobsContent from '../components/Admin/JobsContent';

export default function Admin(): JSX.Element {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Admin</h1>

      <Tabs defaultValue="configuration">
        <TabsList>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="slack">Slack</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
        </TabsList>

        <TabsContent value="configuration">
          <ConfigurationTab />
        </TabsContent>

        <TabsContent value="slack">
          <SlackTab />
        </TabsContent>

        <TabsContent value="notifications">
          <Tabs defaultValue="log" className="mt-4">
            <TabsList>
              <TabsTrigger value="log">Alert Log</TabsTrigger>
              <TabsTrigger value="silences">Active Silences</TabsTrigger>
              <TabsTrigger value="config">Alert Configuration</TabsTrigger>
              <TabsTrigger value="stats">Statistics</TabsTrigger>
            </TabsList>

            <TabsContent value="log">
              <AlertLogTab />
            </TabsContent>

            <TabsContent value="silences">
              <SilencesTab />
            </TabsContent>

            <TabsContent value="config">
              <AlertConfigTab />
            </TabsContent>

            <TabsContent value="stats">
              <StatisticsTab />
            </TabsContent>
          </Tabs>
        </TabsContent>

        <TabsContent value="jobs">
          <JobsContent />
        </TabsContent>
      </Tabs>
    </div>
  );
}
