"use client";

import {
  CheckIcon,
  FileDiffIcon,
  Loader2Icon,
  XIcon,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  approveChangeProposal,
  type ChangeProposal,
  rejectChangeProposal,
} from "@/features/changes/change-api";
import { UnifiedDiffView } from "@/features/changes/unified-diff-view";
import { cn } from "@/lib/utils";

type ChangeApprovalPanelProps = {
  proposal: ChangeProposal;
  onResolved?: (proposal: ChangeProposal) => void;
  reviewOnly?: boolean;
};

function statusClasses(status: ChangeProposal["status"]) {
  return cn(
    "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
    status === "pending" &&
      "border-pending/30 bg-pending/10 text-pending",
    status === "approved" &&
      "border-success/30 bg-success/10 text-success",
    status === "rejected" &&
      "border-danger/30 bg-danger/10 text-danger",
  );
}

export function ChangeApprovalPanel({
  proposal,
  onResolved,
  reviewOnly = false,
}: ChangeApprovalPanelProps) {
  const [action, setAction] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function resolve(nextAction: "approve" | "reject") {
    if (proposal.status !== "pending" || action) {
      return;
    }

    setAction(nextAction);
    setError(null);

    try {
      const result =
        nextAction === "approve"
          ? await approveChangeProposal(proposal.proposal_id)
          : await rejectChangeProposal(proposal.proposal_id);

      onResolved?.(result);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The proposal could not be resolved.",
      );
    } finally {
      setAction(null);
    }
  }

  return (
    <article className="overflow-hidden rounded-xl border border-border bg-surface-raised shadow-xl">
      <header className="flex items-start justify-between gap-4 bg-surface-raised/70 px-4 py-3.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <FileDiffIcon className="size-4 shrink-0 text-pending" />
            <span className="truncate" title={proposal.file_path}>
              Proposed {proposal.operation}: {proposal.file_path}
              {proposal.destination_path
                ? ` → ${proposal.destination_path}`
                : ""}
            </span>
          </div>

          {proposal.summary ? (
            <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
              {proposal.summary}
            </p>
          ) : null}
        </div>

        <span className={statusClasses(proposal.status)}>
          {proposal.status}
        </span>
      </header>

      <UnifiedDiffView diff={proposal.diff} />

      {error ? (
        <p className="border-t border-danger/30 bg-danger/10 px-4 py-2.5 text-xs text-danger">
          {error}
        </p>
      ) : null}

      {proposal.status === "pending" && !reviewOnly ? (
        <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border bg-surface-raised/70 px-4 py-3">
          <p className="mr-auto text-xs text-muted-foreground">
            Review this operation before changing the workspace.
          </p>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={action !== null}
            className="border-danger/30 text-danger hover:bg-danger/10"
            onClick={() => void resolve("reject")}
          >
            {action === "reject" ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <XIcon className="size-4" />
            )}
            Reject
          </Button>

          <Button
            type="button"
            size="sm"
            disabled={action !== null}
            className="bg-success/10 text-accent-foreground hover:bg-success"
            onClick={() => void resolve("approve")}
          >
            {action === "approve" ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <CheckIcon className="size-4" />
            )}
            Approve operation
          </Button>
        </footer>
      ) : reviewOnly && proposal.status === "pending" ? (
        <footer className="border-t border-border bg-surface-raised/70 px-4 py-3 text-xs text-muted-foreground">
          This file belongs to one atomic task change set. Approve or reject the
          complete set below.
        </footer>
      ) : null}
    </article>
  );
}
