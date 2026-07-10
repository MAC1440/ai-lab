"use client";

import {
    ArrowLeftIcon,
    FolderIcon,
    HardDriveIcon,
    Loader2Icon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    browseWorkspace,
    getAvailableDrives,
    selectWorkspace,
} from "@/features/workspaces/workspace-api";
import type { WorkspaceItem } from "@/features/workspaces/types";

type WorkspacePickerProps = {
    activeWorkspace: string | null;
    onWorkspaceSelected: (workspace: string) => void;
};

function getParentPath(path: string): string | null {
    const normalized = path.replace(/[\\/]+$/, "");

    // Windows drive root such as C:
    if (/^[A-Za-z]:$/.test(normalized)) {
        return null;
    }

    const lastSeparator = Math.max(
        normalized.lastIndexOf("\\"),
        normalized.lastIndexOf("/"),
    );

    if (lastSeparator < 0) {
        return null;
    }

    const parent = normalized.slice(0, lastSeparator);

    // Preserve C:\ instead of returning C:
    if (/^[A-Za-z]:$/.test(parent)) {
        return `${parent}\\`;
    }

    return parent || null;
}

export function WorkspacePicker({
    activeWorkspace,
    onWorkspaceSelected,
}: WorkspacePickerProps) {
    const [drives, setDrives] = useState<string[]>([]);
    const [currentPath, setCurrentPath] = useState<string | null>(null);
    const [items, setItems] = useState<WorkspaceItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isSelecting, setIsSelecting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const folders = useMemo(
        () => items.filter((item) => item.type === "folder"),
        [items],
    );

    useEffect(() => {
        async function loadDrives() {
            setIsLoading(true);
            setError(null);

            try {
                const result = await getAvailableDrives();
                setDrives(result.drives);

                // Reopen the active workspace when the dialog is opened.
                if (activeWorkspace) {
                    await openFolder(activeWorkspace);
                }
            } catch (requestError) {
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Could not load drives.",
                );
            } finally {
                setIsLoading(false);
            }
        }

        void loadDrives();
        // We only need the initial active workspace here.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    async function openFolder(path: string) {
        setIsLoading(true);
        setError(null);

        try {
            const result = await browseWorkspace(path);
            setCurrentPath(result.path);
            setItems(result.items);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Could not open folder.",
            );
        } finally {
            setIsLoading(false);
        }
    }

    async function handleSelectWorkspace() {
        if (!currentPath) {
            return;
        }

        setIsSelecting(true);
        setError(null);

        try {
            const result = await selectWorkspace(currentPath);
            onWorkspaceSelected(result.workspace);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Could not select workspace.",
            );
        } finally {
            setIsSelecting(false);
        }
    }

    const parentPath = currentPath ? getParentPath(currentPath) : null;

    return (
        <div className="space-y-4">
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
                <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    Current folder
                </p>
                <p className="mt-1 break-all font-mono text-sm text-zinc-900 dark:text-zinc-100">
                    {currentPath ?? "Choose a drive"}
                </p>
            </div>

            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
                    {error}
                </div>
            )}

            {!currentPath ? (
                <div className="grid gap-2 sm:grid-cols-2">
                    {drives.map((drive) => (
                        <Button
                            key={drive}
                            type="button"
                            variant="outline"
                            className="h-auto justify-start gap-3 p-4"
                            onClick={() => void openFolder(drive)}
                            disabled={isLoading}
                        >
                            <HardDriveIcon className="size-5" />
                            <span className="font-mono">{drive}</span>
                        </Button>
                    ))}
                </div>
            ) : (
                <>
                    <div className="flex items-center gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                                if (parentPath) {
                                    void openFolder(parentPath);
                                } else {
                                    setCurrentPath(null);
                                    setItems([]);
                                }
                            }}
                            disabled={isLoading}
                        >
                            <ArrowLeftIcon className="mr-2 size-4" />
                            Back
                        </Button>

                        <Button
                            type="button"
                            onClick={() => void handleSelectWorkspace()}
                            disabled={isLoading || isSelecting}
                        >
                            {isSelecting && (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                            )}
                            Use this folder
                        </Button>
                    </div>

                    <ScrollArea className="h-72 rounded-lg border border-zinc-200 dark:border-zinc-800">
                        <div className="space-y-1 p-2">
                            {isLoading ? (
                                <div className="flex h-40 items-center justify-center text-sm text-zinc-500">
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    Loading folders…
                                </div>
                            ) : folders.length > 0 ? (
                                folders.map((folder) => (
                                    <button
                                        key={folder.path}
                                        type="button"
                                        onClick={() => void openFolder(folder.path)}
                                        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900"
                                    >
                                        <FolderIcon className="size-4 shrink-0 text-amber-500" />
                                        <span className="truncate">{folder.name}</span>
                                    </button>
                                ))
                            ) : (
                                <div className="flex h-40 items-center justify-center text-sm text-zinc-500">
                                    No subfolders found. You may select this folder.
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                </>
            )}
        </div>
    );
}