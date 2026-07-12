"use client";

import {
  CheckIcon,
  FileDiffIcon,
  Loader2Icon,
  XIcon,
} from "lucide-react";
import { useEffect, useState } from "react";

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
};

function statusClasses(status: ChangeProposal["status"]) {
  return cn(
    "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
    status === "pending" &&
      "border-amber-700/70 bg-amber-950/50 text-amber-300",
    status === "approved" &&
      "border-emerald-700/70 bg-emerald-950/50 text-emerald-300",
    status === "rejected" &&
      "border-red-700/70 bg-red-950/50 text-red-300",
  );
}

export function ChangeApprovalPanel({
  proposal: initialProposal,
  onResolved,
}: ChangeApprovalPanelProps) {
  const [proposal, setProposal] = useState(initialProposal);
  const [action, setAction] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProposal(initialProposal);
  }, [initialProposal]);

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

      setProposal(result);
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
    <article className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-950 shadow-xl">
      <header className="flex items-start justify-between gap-4 bg-zinc-900/70 px-4 py-3.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <FileDiffIcon className="size-4 shrink-0 text-sky-400" />
            <span className="truncate" title={proposal.file_path}>
              Proposed {proposal.operation}: {proposal.file_path}
            </span>
          </div>

          {proposal.summary ? (
            <p className="mt-1.5 text-xs leading-5 text-zinc-400">
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
        <p className="border-t border-red-900/60 bg-red-950/40 px-4 py-2.5 text-xs text-red-300">
          {error}
        </p>
      ) : null}

      {proposal.status === "pending" ? (
        <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-zinc-800 bg-zinc-900/70 px-4 py-3">
          <p className="mr-auto text-xs text-zinc-500">
            Review every changed line before writing it to disk.
          </p>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={action !== null}
            className="border-red-900/70 text-red-300 hover:bg-red-950/50"
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
            className="bg-emerald-600 text-white hover:bg-emerald-500"
            onClick={() => void resolve("approve")}
          >
            {action === "approve" ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <CheckIcon className="size-4" />
            )}
            Approve and write
          </Button>
        </footer>
      ) : null}
    </article>
  );
}
