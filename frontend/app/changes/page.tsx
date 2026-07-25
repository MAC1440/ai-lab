import type { Metadata } from "next";

import { ChangesWorkspace } from "@/features/changes/changes-workspace";

export const metadata: Metadata = {
  title: "Changes",
};

export default function ChangesPage() {
  return <ChangesWorkspace />;
}
