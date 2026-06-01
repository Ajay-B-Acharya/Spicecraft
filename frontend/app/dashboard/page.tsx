import { DashboardShell } from "@/components/dashboard-shell";
import { ProjectsView } from "@/components/projects/ProjectsView";

export default function DashboardPage() {
  return (
    <DashboardShell>
      <main className="p-6 md:p-8">
        <ProjectsView />
      </main>
    </DashboardShell>
  );
}
