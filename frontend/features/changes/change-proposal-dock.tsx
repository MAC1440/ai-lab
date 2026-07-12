"use client";

import { FileDiffIcon, Loader2Icon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
    type ChangeProposal,
    listChangeProposals,
} from "@/features/changes/change-api";
import { ChangeApprovalPanel } from "@/features/changes/change-approval-panel";


const POLL_INTERVAL_MS = 1500;


export function ChangeProposalDock() {
    const [proposals, setProposals] = useState<ChangeProposal[]>([]);
    const [loading, setLoading] = useState(true);
    const [collapsed, setCollapsed] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
        void refresh();

        const intervalId = window.setInterval(() => {
            void refresh();
        }, POLL_INTERVAL_MS);

        return () => window.clearInterval(intervalId);
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
    }

    if (!loading && proposals.length === 0 && !error) {
        return null;
    }

    return (
        <aside className="fixed bottom-4 right-4 z-50 w-[min(42rem,calc(100vw-2rem))]">
            <div className="overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900/95 shadow-2xl backdrop-blur">
                <header className="flex items-center justify-between gap-3 px-4 py-3">
                    <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-zinc-100">
                        {loading ? (
                            <Loader2Icon className="size-4 shrink-0 animate-spin" />
                        ) : (
                            <FileDiffIcon className="size-4 shrink-0" />
                        )}
                        <span className="truncate">
                            Pending file changes
                            {proposals.length > 0 ? ` (${proposals.length})` : ""}
                        </span>
                    </div>

                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setCollapsed((current) => !current)}
                    >
                        {collapsed ? "Show" : "Hide"}
                    </Button>
                </header>

                {!collapsed ? (
                    <div className="max-h-[75vh] space-y-3 overflow-y-auto border-t border-zinc-800 p-3">
                        {error ? (
                            <div className="rounded-lg border border-red-900/70 bg-red-950/40 px-3 py-2 text-xs text-red-300">
                                Could not load the change approval queue: {error}
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