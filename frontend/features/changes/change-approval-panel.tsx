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


type ChangeApprovalPanelProps = {
  proposal: ChangeProposal;
  onResolved?: (proposal: ChangeProposal) => void;
};


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
      <header className="flex items-start justify-between gap-4 border-b border-zinc-800 px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <FileDiffIcon className="size-4 shrink-0" />
            <span className="truncate">
              Proposed {proposal.operation}: {proposal.file_path}
            </span>
          </div>

          {proposal.summary ? (
            <p className="mt-1 text-xs leading-5 text-zinc-400">
              {proposal.summary}
            </p>
          ) : null}
        </div>

        <span className="shrink-0 rounded-full border border-zinc-700 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-zinc-300">
          {proposal.status}
        </span>
      </header>

      <pre className="max-h-72 overflow-auto bg-black/40 p-4 font-mono text-xs leading-5 text-zinc-200">
        {proposal.diff || "No textual diff was produced."}
      </pre>

      {error ? (
        <p className="border-t border-red-900/60 bg-red-950/40 px-4 py-2 text-xs text-red-300">
          {error}
        </p>
      ) : null}

      {proposal.status === "pending" ? (
        <footer className="flex justify-end gap-2 border-t border-zinc-800 px-4 py-3">
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