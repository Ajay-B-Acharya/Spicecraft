import { DashboardShell } from "@/components/dashboard-shell";

export default function DashboardPage() {
  return (
    <DashboardShell>
      <main className="p-6 md:p-8">
        <div className="rounded-[28px] border border-white/6 bg-[linear-gradient(180deg,rgba(13,18,33,0.96),rgba(5,9,20,0.96))] p-8 shadow-[0_30px_80px_rgba(0,0,0,0.35)]">
          <p className="text-sm uppercase tracking-[0.3em] text-violet-300/75">
            Dashboard
          </p>
          <h1 className="mt-4 text-4xl font-semibold text-white">
            Welcome back to SpiceCraft
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-white/65">
            Your authenticated workspace is now using the new top navigation and
            sidebar structure. From here we can wire the actual editor,
            discovery, projects, and simulations screens into the shell.
          </p>
        </div>
      </main>
    </DashboardShell>
  );
}
