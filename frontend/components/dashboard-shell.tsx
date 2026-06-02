"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  ChevronDown,
  CircleHelp,
  CirclePlus,
  Clock3,
  FileCode2,
  FolderKanban,
  Home,
  LogOut,
  Moon,
  PenTool,
  Search,
  Settings,
  Sparkles,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import { auth } from "@/lib/firebase";
import { onAuthStateChanged, signOut, type User } from "firebase/auth";
import { useTheme } from "next-themes";

const primaryLinks = [
  { title: "Dashboard", icon: Home, href: "/dashboard" },
  { title: "My Projects", icon: FolderKanban, href: "/dashboard" },
  { title: "Search Circuits", icon: Search, href: "/search" },
  { title: "Recent Circuits", icon: Clock3, href: "#" },
  { title: "Favorites", icon: Sparkles, href: "/favorites" },
];

const workspaceLinks = [
  { title: "Editor", icon: PenTool, href: "/editor" },
  { title: "AI Assistant", icon: WandSparkles, href: "/assistant" },
  { title: "Exports", icon: FileCode2, href: "/exports" },
];

const toolLinks: Array<{
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}> = [];

const DEMO_USER_STORAGE_KEY = "spicecraft-demo-user";

function getDisplayName(
  user: User | null,
  fallbackName?: string | null,
  fallbackEmail?: string | null,
) {
  if (user?.displayName?.trim()) {
    return user.displayName.trim();
  }

  if (fallbackName?.trim()) {
    return fallbackName.trim();
  }

  if (user?.email) {
    return user.email.split("@")[0];
  }

  if (fallbackEmail) {
    return fallbackEmail.split("@")[0];
  }

  return "User";
}

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean).slice(0, 2);

  if (parts.length === 0) {
    return "U";
  }

  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("");
}

function DashboardSidebar() {
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = !mounted || resolvedTheme === "dark";

  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-sidebar-border bg-sidebar text-sidebar-foreground"
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
                const isActive =
                  item.href !== "#" &&
                  (pathname === item.href ||
                    (item.href === "/dashboard" && pathname.startsWith("/projects/")));
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
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
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
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

        {toolLinks.length > 0 ? (
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
        ) : null}
      </SidebarContent>

      <SidebarFooter className="mt-auto px-3 pb-4">
        <div className="mt-4 flex items-center justify-between rounded-xl border border-sidebar-border bg-background/40 px-3 py-3">
          <div className="flex items-center gap-2 text-sm text-sidebar-foreground/75">
            <Moon className="h-4 w-4" />
            Dark Mode
          </div>
          <Switch
            checked={isDark}
            onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
            aria-label="Toggle dark mode"
          />
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

function DashboardTopbar() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(auth.currentUser);
  const [fallbackUser, setFallbackUser] = useState<{
    name?: string;
    email?: string;
  } | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, setUser);

    try {
      const stored = window.localStorage.getItem(DEMO_USER_STORAGE_KEY);
      if (stored) {
        setFallbackUser(
          JSON.parse(stored) as { name?: string; email?: string },
        );
      }
    } catch {
      setFallbackUser(null);
    }

    return unsubscribe;
  }, []);

  const displayName = useMemo(
    () => getDisplayName(user, fallbackUser?.name, fallbackUser?.email),
    [fallbackUser?.email, fallbackUser?.name, user],
  );
  const initials = useMemo(() => getInitials(displayName), [displayName]);

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } finally {
      try {
        window.localStorage.removeItem(DEMO_USER_STORAGE_KEY);
      } catch {
        // Ignore localStorage failures on logout.
      }

      setFallbackUser(null);
      router.push("/login");
    }
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-xl">
      <div className="flex h-16 items-center gap-4 px-4 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-400/30 bg-violet-500/10 text-violet-300">
              <WandSparkles className="h-4 w-4" />
            </div>
            <span className="text-2xl font-semibold tracking-tight text-foreground">
              Spice<span className="text-violet-400">Craft</span>
            </span>
          </Link>
          <SidebarTrigger className="ml-2 rounded-lg border border-border bg-background/60 text-foreground/75 hover:bg-muted hover:text-foreground" />
          <button className="hidden items-center gap-2 rounded-xl border border-border bg-background/70 px-4 py-2 text-sm text-foreground/85 transition hover:bg-muted md:inline-flex">
            <CirclePlus className="h-4 w-4" />
            New Project
          </button>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <button className="relative rounded-xl border border-border bg-background/70 p-2.5 text-foreground/80 transition hover:bg-muted hover:text-foreground">
            <Bell className="h-4 w-4" />
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-violet-500" />
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 rounded-xl px-1 py-1 text-foreground/85 transition hover:bg-muted/70">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 text-sm font-semibold text-white">
                  {initials}
                </div>
                <span className="hidden text-sm md:inline">{displayName}</span>
                <ChevronDown className="hidden h-4 w-4 text-foreground/60 md:inline" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem>
                <Settings className="h-4 w-4" />
                <span>Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem>
                <CircleHelp className="h-4 w-4" />
                <span>Help</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={handleLogout}>
                <LogOut className="h-4 w-4" />
                <span>Logout</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider defaultOpen>
      <DashboardSidebar />
      <SidebarInset className="min-h-screen bg-background">
        <DashboardTopbar />
        <div className="flex-1">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
