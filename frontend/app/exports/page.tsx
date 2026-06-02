import { DashboardShell } from '@/components/dashboard-shell';
import { RoutePlaceholder } from '@/components/route-placeholder';

export default function ExportsPage() {
  return (
    <DashboardShell>
      <main className="p-6 md:p-8">
        <RoutePlaceholder
          accentLabel="Exports"
          title="Export generated circuits"
          description="This page will eventually collect LTspice exports, netlists, and other output formats."
        />
      </main>
    </DashboardShell>
  );
}
