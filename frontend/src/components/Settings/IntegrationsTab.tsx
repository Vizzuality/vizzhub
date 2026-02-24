import ISOConfig from '@/pages/ISOConfig';
import SlackTab from './SlackTab';

export default function IntegrationsTab(): JSX.Element {
  return (
    <div className="space-y-6">
      <ISOConfig />
      <SlackTab />
    </div>
  );
}
