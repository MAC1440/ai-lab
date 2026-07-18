"use client";

import {
  ArchiveIcon,
  MessageSquareIcon,
  MoreHorizontalIcon,
  PlusIcon,
  PencilIcon,
  RotateCcwIcon,
  Trash2Icon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ConversationSummary } from "@/features/sessions/session-api";
import { cn } from "@/lib/utils";

export function SessionSidebar({
  sessions,
  selectedId,
  loading,
  disabled,
  showArchived,
  onShowArchivedChange,
  onNew,
  onSelect,
  onArchive,
  onRename,
  onRestore,
  onDelete,
}: {
  sessions: ConversationSummary[];
  selectedId: string | null;
  loading: boolean;
  disabled: boolean;
  showArchived: boolean;
  onShowArchivedChange: (value: boolean) => void;
  onNew: () => void;
  onSelect: (session: ConversationSummary) => void;
  onArchive: (session: ConversationSummary) => void;
  onRename: (session: ConversationSummary) => void;
  onRestore: (session: ConversationSummary) => void;
  onDelete: (session: ConversationSummary) => void;
}) {
  return (
    <aside className="hidden h-screen w-72 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 lg:flex dark:border-zinc-800 dark:bg-zinc-950">
      <div className="space-y-3 border-b border-zinc-200 p-3 dark:border-zinc-800">
        <Button type="button" className="w-full justify-start" onClick={onNew} disabled={disabled}>
          <PlusIcon className="size-4" /> New conversation
        </Button>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-zinc-500">
          <input type="checkbox" checked={showArchived} onChange={(event) => onShowArchivedChange(event.target.checked)} />
          Show archived
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {loading ? <p className="p-3 text-xs text-zinc-500">Loading conversations…</p> : null}
        <div className="space-y-1">
          {sessions.map((session) => (
            <div key={session.session_id} className={cn("group flex items-center rounded-lg", selectedId === session.session_id ? "bg-violet-100 dark:bg-violet-950/50" : "hover:bg-zinc-100 dark:hover:bg-zinc-900")}>
              <button type="button" className="min-w-0 flex-1 px-3 py-2 text-left" onClick={() => onSelect(session)} disabled={disabled}>
                <span className="flex items-center gap-2">
                  <MessageSquareIcon className="size-3.5 shrink-0" />
                  <span className="truncate text-sm">{session.title}</span>
                </span>
                <span className="mt-1 block truncate text-[10px] text-zinc-500">
                  {session.agent_id} · {session.message_count} messages
                </span>
              </button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button type="button" size="sm" variant="ghost" className="mr-1 size-7 p-0 opacity-0 group-hover:opacity-100">
                    <MoreHorizontalIcon className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onRename(session)}><PencilIcon className="size-4" /> Rename</DropdownMenuItem>
                  {session.status === "active" ? (
                    <DropdownMenuItem onClick={() => onArchive(session)}><ArchiveIcon className="size-4" /> Archive</DropdownMenuItem>
                  ) : (
                    <DropdownMenuItem onClick={() => onRestore(session)}><RotateCcwIcon className="size-4" /> Restore</DropdownMenuItem>
                  )}
                  <DropdownMenuItem className="text-red-600" onClick={() => onDelete(session)}><Trash2Icon className="size-4" /> Delete permanently</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </div>
        {!loading && sessions.length === 0 ? <p className="p-3 text-xs text-zinc-500">No saved conversations.</p> : null}
      </div>
    </aside>
  );
}
