import type { Metadata } from "next";
import { SettingsSystemWorkspace } from "@/features/settings/settings-system-workspace";

export const metadata: Metadata = { title: "Settings and System" };

export default function SettingsPage() {
  return <SettingsSystemWorkspace />;
}
