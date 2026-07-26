import { Toggle as TogglePrimitive } from "radix-ui";
import { type ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Toggle({
  className,
  variant = "default",
  size = "default",
  ...props
}: ComponentProps<typeof TogglePrimitive.Root> & {
  variant?: "default" | "outline";
  size?: "default" | "sm" | "lg";
}) {
  return (
    <TogglePrimitive.Root
      data-slot="toggle"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        "data-[state=on]:bg-surface-hover data-[state=on]:text-foreground",
        "dark:data-[state=on]:bg-surface-hover dark:data-[state=on]:text-foreground",
        variant === "default" && "bg-transparent hover:bg-surface-hover dark:hover:bg-surface-hover",
        variant === "outline" &&
          "border border-border bg-transparent hover:bg-surface-hover dark:border-border dark:hover:bg-surface-hover",
        size === "default" && "h-9 px-3",
        size === "sm" && "h-8 px-2",
        size === "lg" && "h-10 px-4",
        className,
      )}
      {...props}
    />
  );
}
