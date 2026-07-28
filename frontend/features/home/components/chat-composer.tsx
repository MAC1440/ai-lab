"use client";

import { AlertCircleIcon } from "lucide-react";

import { ChatInput } from "./chat-input";

export function ChatComposer({
    error,
    value,
    disabled,
    streaming,
    placeholder,
    onChange,
    onSubmit,
    onStop,
}: {
    error: string | null;
    value: string;
    disabled: boolean;
    streaming: boolean;
    placeholder: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
    onStop: () => void;
}) {
    return (
        <footer className="border-t border-border bg-surface p-4 dark:border-border dark:bg-surface-raised">
            <div className="mx-auto max-w-5xl">
                {error ? (
                    <div className="mb-3 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger dark:border-danger/30 dark:bg-danger/10 dark:text-danger">
                        <AlertCircleIcon className="mt-0.5 size-4 shrink-0" />
                        <span>{error}</span>
                    </div>
                ) : null}
                <ChatInput
                    value={value}
                    onChange={onChange}
                    onSubmit={onSubmit}
                    disabled={disabled}
                    streaming={streaming}
                    onStop={onStop}
                    placeholder={placeholder}
                />
                <p className="mt-2 text-center text-[11px] text-muted-foreground">
                    RAG progress, tool execution, and answer tokens are streamed
                    from the backend as newline-delimited JSON events.
                </p>
            </div>
        </footer>
    );
}
