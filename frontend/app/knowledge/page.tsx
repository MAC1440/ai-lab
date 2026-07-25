import type { Metadata } from "next";

import { KnowledgeContextWorkspace } from "@/features/knowledge/knowledge-context-workspace";

export const metadata: Metadata = {
  title: "Knowledge and Context",
};

export default function KnowledgePage() {
  return <KnowledgeContextWorkspace />;
}
