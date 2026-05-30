"use client";

import Link from "next/link";
import {
  Bell,
  ChevronDown,
  CirclePlus,
  Clock3,
  FileCode2,
  FolderKanban,
  Gauge,
  Home,
  LibraryBig,
  Menu,
  Moon,
  PenTool,
  Search,
  Sparkles,
  UserCircle2,
  WandSparkles,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Switch } from "@/components/ui/switch";

const primaryLinks = [
  { title: "Dashboard", icon: Home, href: "/dashboard", active: true },
  { title: "Discover Circuits", icon: Search, href: "#" },
  { title: "My Projects", icon: FolderKanban, href: "#" },
  { title: "Recent Circuits", icon: Clock3, href: "#" },
  { title: "Favorites", icon: Sparkles, href: "#" },
];

const workspaceLinks = [
  { title: "Editor", icon: PenTool, href: "#" },
  { title: "AI Assistant", icon: WandSparkles, href: "#" },
  { title: "Simulations", icon: Gauge, href: "#" },
  { title: "Exports", icon: FileCode2, href: "#" },
];

const toolLinks = [
  { title: "Component Library", icon: LibraryBig, href: "#" },
  { title: "Source Manager", icon: FolderKanban, href: "#" },
  { title: "Conversion History", icon: Clock3, href: "#" },
];

function DashboardSidebar() {
  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-white/6 bg-[#060b18]"
    >
      <SidebarHeader className="gap-3 px-3 pb-2 pt-3">
        <Link
          href="#"
          className="flex items-center justify-center rounded-xl bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 px-4 py-3 text-sm font-semibold text-white shadow-[0_14px_35px_rgba(99,102,241,0.35)] transition hover:brightness-110"
        >
          <CirclePlus className="mr-2 h-4 w-4" />
          New Circuit
        </Link>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <SidebarGroup className="px-0">
          <SidebarGroupContent>
            <SidebarMenu>
              {primaryLinks.map((item) => {
                const Icon = item.icon;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={item.active}
                      className="h-10 rounded-xl px-3 text-[13px] text-white/80 data-[active=true]:bg-white/6 data-[active=true]:text-white hover:bg-white/6 hover:text-white"
                    >
                      <Link href={item.href}>
                        <Icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="mt-4 border-t border-white/6 px-0 pt-4">
          <SidebarGroupLabel className="px-3 text-[11px] uppercase tracking-[0.22em] text-white/35">
            Workspace
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {workspaceLinks.map((item) => {
                const Icon = item.icon;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      className="h-10 rounded-xl px-3 text-[13px] text-white/72 hover:bg-white/6 hover:text-white"
                    >
                      <Link href={item.href}>
                        <Icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="mt-4 border-t border-white/6 px-0 pt-4">
          <SidebarGroupLabel className="px-3 text-[11px] uppercase tracking-[0.22em] text-white/35">
            Tools
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {toolLinks.map((item) => {
                const Icon = item.icon;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      className="h-10 rounded-xl px-3 text-[13px] text-white/72 hover:bg-white/6 hover:text-white"
                    >
                      <Link href={item.href}>
                        <Icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="mt-auto px-3 pb-4">
        <div className="rounded-2xl border border-violet-400/18 bg-gradient-to-br from-violet-600/28 to-indigo-500/20 p-4 text-white">
          <p className="text-sm font-semibold">Upgrade to Pro</p>
          <p className="mt-2 text-xs leading-5 text-white/65">
            Unlock more searches, exports and advanced AI features.
          </p>
          <button className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-gradient-to-r from-violet-500 to-indigo-500 px-3 py-2 text-sm font-semibold text-white">
            Upgrade Now
            <ChevronDown className="ml-2 h-4 w-4 -rotate-90" />
          </button>
        </div>

        <div className="mt-4 flex items-center justify-between rounded-xl border border-white/6 bg-white/[0.02] px-3 py-3">
          <div className="flex items-center gap-2 text-sm text-white/75">
            <Moon className="h-4 w-4" />
            Dark Mode
          </div>
          <Switch checked aria-label="Dark mode enabled" />
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

function DashboardTopbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/6 bg-[#050914]/95 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-4 px-4 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-400/30 bg-violet-500/10 text-violet-300">
              <WandSparkles className="h-4 w-4" />
            </div>
            <span className="text-2xl font-semibold tracking-tight text-white">
              Spice<span className="text-violet-400">Craft</span>
            </span>
          </Link>
          <SidebarTrigger className="ml-2 rounded-lg border border-white/6 bg-white/[0.02] text-white/75 hover:bg-white/[0.06] hover:text-white" />
        </div>

        <div className="hidden flex-1 md:flex">
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
            <input
              readOnly
              value=""
              placeholder="Search circuits, components, sources..."
              className="h-11 w-full rounded-xl border border-white/6 bg-white/[0.03] pl-10 pr-14 text-sm text-white placeholder:text-white/35 outline-none"
            />
            <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded-md border border-violet-400/20 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-200">
              <span>⌘</span>
              <span>K</span>
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <button className="hidden items-center gap-2 rounded-xl border border-white/8 bg-white/[0.03] px-4 py-2 text-sm text-white/85 transition hover:bg-white/[0.06] md:inline-flex">
            <CirclePlus className="h-4 w-4" />
            New Project
          </button>
          <button className="relative rounded-xl border border-white/8 bg-white/[0.03] p-2.5 text-white/80 transition hover:bg-white/[0.06] hover:text-white">
            <Bell className="h-4 w-4" />
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-violet-500" />
          </button>
          <button className="flex items-center gap-2 rounded-xl px-1 py-1 text-white/85 transition hover:bg-white/[0.04]">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 text-sm font-semibold text-white">
              A
            </div>
            <span className="hidden text-sm md:inline">Aditya</span>
            <ChevronDown className="hidden h-4 w-4 text-white/60 md:inline" />
          </button>
        </div>
      </div>
    </header>
  );
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider defaultOpen>
      <DashboardSidebar />
      <SidebarInset className="min-h-screen bg-[#030712]">
        <DashboardTopbar />
        <div className="flex-1">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
