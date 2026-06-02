import { DashboardShell } from '@/components/dashboard-shell';
import { RoutePlaceholder } from '@/components/route-placeholder';

export default function EditorPage() {
  return (
    <DashboardShell>
      <main className="p-6 md:p-8">
        <RoutePlaceholder
          accentLabel="Editor"
          title="Circuit editor workspace"
          description="This is the workspace for building, arranging, and refining circuit designs."
        />
      </main>
    </DashboardShell>
  );
}
