"use client";

import {
  CheckCircle2Icon,
  FileDiffIcon,
  Loader2Icon,
  XIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type ChangeProposal,
  listChangeProposals,
} from "@/features/changes/change-api";
import { ChangeApprovalPanel } from "@/features/changes/change-approval-panel";
import { VerificationDialog } from "@/features/verification";

const POLL_INTERVAL_MS = 1500;

export function ChangeProposalDock() {
  const [proposals, setProposals] = useState<ChangeProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastApproved, setLastApproved] = useState<ChangeProposal | null>(null);

  const refresh = useCallback(async () => {
    try {
      const nextProposals = await listChangeProposals("pending");
      setProposals(nextProposals);
      setError(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Pending changes could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoadId = window.setTimeout(() => {
      void refresh();
    }, 0);

    const intervalId = window.setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearTimeout(initialLoadId);
      window.clearInterval(intervalId);
    };
  }, [refresh]);

  function handleResolved(resolvedProposal: ChangeProposal) {
    if (resolvedProposal.status === "pending") {
      return;
    }

    setProposals((current) =>
      current.filter(
        (proposal) => proposal.proposal_id !== resolvedProposal.proposal_id,
      ),
    );

    if (resolvedProposal.status === "approved") {
      setLastApproved(resolvedProposal);
      setCollapsed(false);
    }
  }

  if (!loading && proposals.length === 0 && !error && !lastApproved) {
    return null;
  }

  return (
    <aside className="fixed inset-x-3 bottom-3 z-50 mx-auto w-auto max-w-[90rem] sm:inset-x-5 sm:bottom-5">
      <div className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900/95 shadow-2xl shadow-black/50 backdrop-blur">
        <header className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-zinc-100">
            {loading ? (
              <Loader2Icon className="size-4 shrink-0 animate-spin" />
            ) : lastApproved && proposals.length === 0 ? (
              <CheckCircle2Icon className="size-4 shrink-0 text-emerald-400" />
            ) : (
              <FileDiffIcon className="size-4 shrink-0 text-sky-400" />
            )}
            <span className="truncate">
              {proposals.length > 0
                ? `Pending file changes (${proposals.length})`
                : "File change approved"}
            </span>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed((current) => !current)}
          >
            {collapsed ? "Show changes" : "Hide"}
          </Button>
        </header>

        {!collapsed ? (
          <div className="max-h-[82vh] space-y-3 overflow-y-auto border-t border-zinc-800 p-3 sm:p-4">
            {error ? (
              <div className="rounded-lg border border-red-900/70 bg-red-950/40 px-3 py-2 text-xs text-red-300">
                Could not load the change approval queue: {error}
              </div>
            ) : null}

            {lastApproved ? (
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-900/70 bg-emerald-950/35 px-3 py-3">
                <CheckCircle2Icon className="size-5 shrink-0 text-emerald-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-emerald-200">
                    Change written successfully
                  </p>
                  <p
                    className="truncate text-xs text-emerald-300/70"
                    title={lastApproved.file_path}
                  >
                    {lastApproved.file_path}
                  </p>
                </div>

                <VerificationDialog
                  relatedProposalId={lastApproved.proposal_id}
                  triggerLabel="Run checks"
                />

                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label="Dismiss approved change message"
                  onClick={() => setLastApproved(null)}
                >
                  <XIcon className="size-4" />
                </Button>
              </div>
            ) : null}

            {proposals.map((proposal) => (
              <ChangeApprovalPanel
                key={proposal.proposal_id}
                proposal={proposal}
                onResolved={handleResolved}
              />
            ))}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
