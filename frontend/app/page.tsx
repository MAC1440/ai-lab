import { ChangeProposalDock } from "@/features/changes";
import { ChatPanel } from "@/features/home";

export default function Home() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ChatPanel />
      <ChangeProposalDock />
    </div>
  );
}
