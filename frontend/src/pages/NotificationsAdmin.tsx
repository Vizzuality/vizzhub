import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AlertLogTab from '../components/NotificationsAdmin/AlertLogTab';
import SilencesTab from '../components/NotificationsAdmin/SilencesTab';
import AlertConfigTab from '../components/NotificationsAdmin/AlertConfigTab';
import StatisticsTab from '../components/NotificationsAdmin/StatisticsTab';

export default function NotificationsAdmin(): JSX.Element {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Notifications</h1>

      <Tabs defaultValue="log">
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
    </div>
  );
}
