import { NavigationPane } from "@/components/NavigationPane";
import { QueuePane } from "@/components/QueuePane";
import { InspectorPane } from "@/components/InspectorPane";

const Index = () => {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      <NavigationPane />
      <QueuePane />
      <InspectorPane />
    </div>
  );
};

export default Index;
