import { useState } from 'react';
import { useScoringConfig } from '../hooks/useScores';
import { Pencil, Save, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function Settings(): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const { data: config, isLoading: configLoading } = useScoringConfig();

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
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <Button
                variant="ghost"
                onClick={() => setIsEditing(false)}
                className="border"
              >
                <X className="h-4 w-4 mr-2" />
                Cancel
              </Button>
              <Button onClick={() => setIsEditing(false)}>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </>
          ) : (
            <Button onClick={() => setIsEditing(true)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit Configuration
            </Button>
          )}
        </div>
      </div>

      <Tabs defaultValue="config">
        <TabsList>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
        </TabsList>

        <TabsContent value="config">
          <Card className="p-6">
            <p className="text-muted-foreground">Configuration content coming soon...</p>
          </Card>
        </TabsContent>

        <TabsContent value="validation">
          <Card className="p-6">
            <p className="text-muted-foreground">Validation content coming soon...</p>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

