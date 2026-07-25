import type { Metadata } from "next";

import { ModelsRuntimeWorkspace } from "@/features/model-settings/models-runtime-workspace";

export const metadata: Metadata = {
  title: "Models and Runtime",
};

export default function ModelsPage() {
  return <ModelsRuntimeWorkspace />;
}
