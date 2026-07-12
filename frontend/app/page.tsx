import { ChangeProposalDock } from "@/features/changes";
import { ChatPanel } from "@/features/home";


export default function Home() {
  return (
    <>
      <ChatPanel />
      <ChangeProposalDock />
    </>
  );
}