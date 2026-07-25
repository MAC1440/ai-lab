import {
  BotIcon,
  CheckCircle2Icon,
  FileDiffIcon,
  FolderKanbanIcon,
  GaugeIcon,
  LibraryIcon,
  MessageSquareIcon,
  SettingsIcon,
  type LucideIcon,
} from "lucide-react";

export type NavigationItem = {
  id: string;
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
  available?: boolean;
};

export const primaryNavigation: NavigationItem[] = [
  {
    id: "chat",
    label: "Chat",
    description: "Talk with local agents",
    href: "/",
    icon: MessageSquareIcon,
    available: true,
  },
  {
    id: "tasks",
    label: "Tasks",
    description: "Bounded coding work",
    href: "/tasks",
    icon: FolderKanbanIcon,
  },
  {
    id: "changes",
    label: "Changes",
    description: "Review proposed files",
    href: "/changes",
    icon: FileDiffIcon,
  },
  {
    id: "verification",
    label: "Verification",
    description: "Checks and repair runs",
    href: "/verification",
    icon: CheckCircle2Icon,
  },
  {
    id: "knowledge",
    label: "Knowledge",
    description: "Local indexed sources",
    href: "/knowledge",
    icon: LibraryIcon,
  },
];

export const secondaryNavigation: NavigationItem[] = [
  {
    id: "models",
    label: "Models",
    description: "Providers and runtime fit",
    href: "/models",
    icon: BotIcon,
    available: true,
  },
  {
    id: "performance",
    label: "Performance",
    description: "Runtime history",
    href: "/performance",
    icon: GaugeIcon,
    available: true,
  },
  {
    id: "settings",
    label: "Settings",
    description: "Workspace configuration",
    href: "/settings",
    icon: SettingsIcon,
  },
];

export function isNavigationItemActive(
  pathname: string,
  item: NavigationItem,
): boolean {
  if (item.href === "/") {
    return pathname === "/";
  }

  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
