import { DashboardShell } from '@/components/dashboard-shell';
import { RoutePlaceholder } from '@/components/route-placeholder';

export default function FavoritesPage() {
  return (
    <DashboardShell>
      <main className="p-6 md:p-8">
        <RoutePlaceholder
          accentLabel="Favorites"
          title="Saved circuits and references"
          description="This page will hold bookmarked projects, sources, and recurring circuit references."
        />
      </main>
    </DashboardShell>
  );
}
