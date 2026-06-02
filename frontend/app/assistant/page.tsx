import { DashboardShell } from '@/components/dashboard-shell';
import { RoutePlaceholder } from '@/components/route-placeholder';

export default function AssistantPage() {
  return (
    <DashboardShell>
      <main className="p-6 md:p-8">
        <RoutePlaceholder
          accentLabel="AI Assistant"
          title="Circuit guidance and generation"
          description="Use this space for AI-assisted circuit suggestions, reasoning, and iterative refinement."
        />
      </main>
    </DashboardShell>
  );
}
