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

export function ChangeApprovalPanel({
  proposal: initialProposal,
}: {
  proposal: ChangeProposal;
}) {
  const [proposal, setProposal] = useState(initialProposal);
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
      setProposal(result);
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
    <section className="overflow-hidden rounded-lg border border-violet-200 bg-white text-xs dark:border-violet-900/60 dark:bg-zinc-950">
      <header className="flex flex-wrap items-center gap-2 border-b border-violet-100 px-3 py-2 dark:border-violet-900/40">
        <FileDiffIcon className="size-4 text-violet-600 dark:text-violet-400" />
        <span className="font-semibold text-zinc-800 dark:text-zinc-100">
          Proposed {proposal.operation}
        </span>
        <code className="break-all text-zinc-600 dark:text-zinc-300">
          {proposal.file_path}
        </code>
        <span className="ml-auto rounded-full bg-zinc-100 px-2 py-0.5 capitalize text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          {proposal.status}
        </span>
      </header>

      {proposal.summary ? (
        <p className="border-b border-zinc-100 px-3 py-2 text-zinc-600 dark:border-zinc-900 dark:text-zinc-300">
          {proposal.summary}
        </p>
      ) : null}

      <pre className="max-h-96 overflow-auto whitespace-pre p-3 font-mono text-[11px] leading-5 text-zinc-700 dark:text-zinc-200">
        {proposal.diff || "No textual diff was produced."}
      </pre>

      {error ? (
        <p className="border-t border-red-200 bg-red-50 px-3 py-2 text-red-700 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-300">
          {error}
        </p>
      ) : null}

      {proposal.status === "pending" ? (
        <footer className="flex justify-end gap-2 border-t border-zinc-200 px-3 py-2 dark:border-zinc-800">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={Boolean(action)}
            onClick={() => void resolve("reject")}
          >
            {action === "reject" ? (
              <Loader2Icon className="mr-2 size-3.5 animate-spin" />
            ) : (
              <XIcon className="mr-2 size-3.5" />
            )}
            Reject
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={Boolean(action)}
            onClick={() => void resolve("approve")}
          >
            {action === "approve" ? (
              <Loader2Icon className="mr-2 size-3.5 animate-spin" />
            ) : (
              <CheckIcon className="mr-2 size-3.5" />
            )}
            Approve and write
          </Button>
        </footer>
      ) : null}
    </section>
  );
}
