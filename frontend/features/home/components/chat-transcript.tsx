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
    selectedAgentUsesTools,
    activeWorkspace,
    onSelectWorkspace,
    bottomRef,
}: {
    messages: HomeChatMessage[];
    isSending: boolean;
    selectedAgent: AgentProfile | null;
    selectedAgentUsesTools: boolean;
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
                                <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                                    <SparklesIcon className="size-6" />
                                </div>
                                <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                                    {selectedAgent
                                        ? `Chat with ${selectedAgent.name}`
                                        : "Select an agent"}
                                </h2>
                                <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
                                    {selectedAgent?.description ??
                                        "Choose an agent to begin."}
                                </p>
                                {selectedAgentUsesTools && !activeWorkspace ? (
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
                        <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
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
