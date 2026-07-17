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
  approveChangeSet,
  rejectChangeSet,
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
  const [setAction, setSetAction] = useState<string | null>(null);

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

  const groupedProposals = proposals.reduce<
    Array<{ id: string; proposals: ChangeProposal[] }>
  >((groups, proposal) => {
    const id = proposal.change_set_id ?? proposal.proposal_id;
    const existing = groups.find((group) => group.id === id);
    if (existing) existing.proposals.push(proposal);
    else groups.push({ id, proposals: [proposal] });
    return groups;
  }, []);

  async function resolveSet(
    group: { id: string; proposals: ChangeProposal[] },
    action: "approve" | "reject",
  ) {
    if (!group.proposals[0]?.change_set_id) return;
    setSetAction(`${action}:${group.id}`);
    try {
      const resolved = action === "approve"
        ? await approveChangeSet(group.id)
        : await rejectChangeSet(group.id);
      resolved.forEach(handleResolved);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The change set could not be resolved.");
    } finally {
      setSetAction(null);
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

            {groupedProposals.map((group) => (
              <section key={group.id} className="space-y-3">
                {group.proposals.length > 1 ? (
                  <div className="flex flex-wrap items-center gap-2 rounded-lg border border-violet-900/60 bg-violet-950/25 px-3 py-2">
                    <p className="mr-auto text-xs text-violet-200">
                      One agent turn proposed {group.proposals.length} related files.
                    </p>
                    <Button type="button" size="sm" variant="outline" disabled={setAction !== null} onClick={() => void resolveSet(group, "reject")}>
                      Reject set
                    </Button>
                    <Button type="button" size="sm" disabled={setAction !== null} onClick={() => void resolveSet(group, "approve")}>
                      {setAction === `approve:${group.id}` ? <Loader2Icon className="size-4 animate-spin" /> : null}
                      Approve set
                    </Button>
                  </div>
                ) : null}
                {group.proposals.map((proposal) => (
                  <ChangeApprovalPanel
                    key={proposal.proposal_id}
                    proposal={proposal}
                    onResolved={handleResolved}
                  />
                ))}
              </section>
            ))}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
