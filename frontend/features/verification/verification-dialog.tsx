"use client";

import { ShieldCheckIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { VerificationPanel } from "@/features/verification/verification-panel";


type VerificationDialogProps = {
  disabled?: boolean;
  relatedProposalId?: string | null;
  relatedRepairTaskId?: string | null;
  triggerLabel?: string;
};

export function VerificationDialog({
  disabled = false,
  relatedProposalId = null,
  relatedRepairTaskId = null,
  triggerLabel = "Verify workspace",
}: VerificationDialogProps) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <ShieldCheckIcon className="size-4" />
          {triggerLabel}
        </Button>
      </DialogTrigger>

      <DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto">
        <DialogTitle>Workspace verification</DialogTitle>
        <DialogDescription>
          Run predefined local checks inside the selected workspace. Commands
          are selected by AI Lab, not supplied by the model.
        </DialogDescription>

        <VerificationPanel
          key={`${relatedProposalId ?? "manual"}:${relatedRepairTaskId ?? "no-repair"}:${String(open)}`}
          relatedProposalId={relatedProposalId}
          relatedRepairTaskId={relatedRepairTaskId}
          onRequestAgentFix={() => setOpen(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
