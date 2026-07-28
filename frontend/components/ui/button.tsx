import { Slot } from "radix-ui";
import { type ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: ComponentProps<"button"> & {
  asChild?: boolean;
  variant?: "default" | "secondary" | "ghost" | "outline";
  size?: "default" | "sm" | "icon";
}) {
  const Comp = asChild ? Slot.Root : "button";

  return (
    <Comp
      data-slot="button"
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:pointer-events-none disabled:opacity-50",
        variant === "default" &&
          "bg-accent text-accent-foreground hover:bg-accent-hover",
        variant === "secondary" &&
          "bg-surface-hover text-foreground hover:bg-border-strong/40",
        variant === "ghost" &&
          "text-foreground hover:bg-surface-hover",
        variant === "outline" &&
          "border border-border bg-transparent text-foreground hover:bg-surface-hover",
        size === "default" && "h-10 px-4 py-2",
        size === "sm" && "h-8 rounded-md px-3 text-xs",
        size === "icon" && "size-10",
        className,
      )}
      {...props}
    />
  );
}
