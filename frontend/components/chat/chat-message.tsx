"use client";

import { BotIcon, UserIcon } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function ChatMessageBubble({
  message,
  isStreaming = false,
}: {
  message: ChatMessage;
  isStreaming?: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-3",
        isUser ? "bg-transparent" : "bg-surface-hover/80 dark:bg-surface-raised/50",
      )}
    >
      <Avatar className="size-8">
        <AvatarFallback
          className={cn(
            isUser
              ? "bg-pending/15 text-pending dark:bg-pending/15 dark:text-pending"
              : "bg-success/10 text-success dark:bg-success/10 dark:text-success",
          )}
        >
          {isUser ? (
            <UserIcon className="size-4" />
          ) : (
            <BotIcon className="size-4" />
          )}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-xs font-medium text-muted-foreground dark:text-muted-foreground">
          {isUser ? "You" : "Assistant"}
        </p>
        <div className="text-sm leading-relaxed text-foreground dark:text-foreground">
          {message.content || (isStreaming ? "…" : "")}
          {isStreaming && message.content && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-success" />
          )}
        </div>
      </div>
    </div>
  );
}
