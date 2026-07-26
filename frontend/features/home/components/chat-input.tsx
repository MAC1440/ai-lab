"use client";

import { ArrowUpIcon, SquareIcon } from "lucide-react";
import { type FormEvent, useRef } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ChatInput({
    value,
    onChange,
    onSubmit,
    disabled = false,
    placeholder = "Message your local model…",
    streaming = false,
    onStop,
}: {
    value: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
    disabled?: boolean;
    placeholder?: string;
    streaming?: boolean;
    onStop?: () => void;
}) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    function handleSubmit(event: FormEvent) {
        event.preventDefault();
        if (!value.trim() || disabled) return;
        onSubmit();
    }

    function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!value.trim() || disabled) return;
            onSubmit();
        }
    }

    return (
        <form
            onSubmit={handleSubmit}
            className="border-t border-border bg-surface p-4 dark:border-border dark:bg-surface-raised"
        >
            <div
                className={cn(
                    "flex items-end gap-2 rounded-2xl border border-border bg-surface-hover p-2",
                    "focus-within:border-border focus-within:ring-2 focus-within:ring-accent",
                    "dark:border-border dark:bg-surface-raised dark:focus-within:border-border dark:focus-within:ring-accent",
                )}
            >
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={disabled}
                    rows={1}
                    className={cn(
                        "max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none",
                        "placeholder:text-muted-foreground disabled:opacity-50",
                        "dark:placeholder:text-muted-foreground",
                    )}
                />
                <Button
                    type={streaming ? "button" : "submit"}
                    size="icon"
                    disabled={streaming ? false : disabled || !value.trim()}
                    className="size-9 shrink-0 rounded-xl"
                    aria-label={streaming ? "Stop response" : "Send message"}
                    onClick={streaming ? onStop : undefined}
                >
                    {streaming ? <SquareIcon className="size-3.5 fill-current" /> : <ArrowUpIcon className="size-4" />}
                </Button>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground dark:text-muted-foreground">
                {streaming ? "Stop closes the active Ollama stream" : "Press Enter to send · Shift+Enter for a new line"}
            </p>
        </form>
    );
}
