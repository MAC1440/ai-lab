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
  icon: LucideIcon;
  active?: boolean;
  available?: boolean;
};

export const primaryNavigation: NavigationItem[] = [
  {
    id: "chat",
    label: "Chat",
    description: "Talk with local agents",
    icon: MessageSquareIcon,
    active: true,
    available: true,
  },
  {
    id: "tasks",
    label: "Tasks",
    description: "Bounded coding work",
    icon: FolderKanbanIcon,
  },
  {
    id: "changes",
    label: "Changes",
    description: "Review proposed files",
    icon: FileDiffIcon,
  },
  {
    id: "verification",
    label: "Verification",
    description: "Checks and repair runs",
    icon: CheckCircle2Icon,
  },
  {
    id: "knowledge",
    label: "Knowledge",
    description: "Local indexed sources",
    icon: LibraryIcon,
  },
];

export const secondaryNavigation: NavigationItem[] = [
  {
    id: "models",
    label: "Models",
    description: "Providers and runtime fit",
    icon: BotIcon,
  },
  {
    id: "performance",
    label: "Performance",
    description: "Runtime history",
    icon: GaugeIcon,
  },
  {
    id: "settings",
    label: "Settings",
    description: "Workspace configuration",
    icon: SettingsIcon,
  },
];
