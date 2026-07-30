import type { Metadata } from "next";

import { WorkspaceTerminal } from "@/features/terminal";

export const metadata: Metadata = {
  title: "Workspace Terminal",
};

export default function TerminalPage() {
  return <WorkspaceTerminal />;
}
