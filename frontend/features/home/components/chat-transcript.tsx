"use client";

import { FolderCogIcon, SparklesIcon } from "lucide-react";
import type { RefObject } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AgentProfile } from "@/features/agents/agent-api";
import { ChatMessageBubble } from "./chat-message-bubble";
import type { HomeChatMessage } from "@/features/home/types";

export function ChatTranscript({
    messages,
    isSending,
    selectedAgent,
    selectedAgentUsesWorkspaceTools,
    activeWorkspace,
    onSelectWorkspace,
    bottomRef,
}: {
    messages: HomeChatMessage[];
    isSending: boolean;
    selectedAgent: AgentProfile | null;
    selectedAgentUsesWorkspaceTools: boolean;
    activeWorkspace: string | null;
    onSelectWorkspace: () => void;
    bottomRef: RefObject<HTMLDivElement | null>;
}) {
    return (
        <main className="min-h-0 flex-1">
            <ScrollArea className="h-full">
                <div className="mx-auto max-w-5xl">
                    {messages.length === 0 ? (
                        <div className="flex min-h-[55vh] items-center justify-center px-6 py-16 text-center">
                            <div className="max-w-xl space-y-3">
                                <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-success/10 text-success dark:bg-success/10 dark:text-success">
                                    <SparklesIcon className="size-6" />
                                </div>
                                <h2 className="text-lg font-semibold text-foreground dark:text-foreground">
                                    {selectedAgent
                                        ? `Chat with ${selectedAgent.name}`
                                        : "Select an agent"}
                                </h2>
                                <p className="text-sm leading-relaxed text-muted-foreground dark:text-muted-foreground">
                                    {selectedAgent?.description ??
                                        "Choose an agent to begin."}
                                </p>
                                {selectedAgentUsesWorkspaceTools &&
                                !activeWorkspace ? (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={onSelectWorkspace}
                                    >
                                        <FolderCogIcon className="mr-2 size-4" />
                                        Select a workspace for tools
                                    </Button>
                                ) : null}
                            </div>
                        </div>
                    ) : (
                        <div className="divide-y divide-border dark:divide-border">
                            {messages.map((message, index) => (
                                <ChatMessageBubble
                                    key={message.id}
                                    message={message}
                                    isStreaming={
                                        isSending &&
                                        index === messages.length - 1 &&
                                        message.role === "assistant"
                                    }
                                />
                            ))}
                        </div>
                    )}
                    <div ref={bottomRef} />
                </div>
            </ScrollArea>
        </main>
    );
}
