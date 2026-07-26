"use client";

import { unstable_PasswordToggleField as PasswordToggleFieldPrimitive } from "radix-ui";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import { type ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function PasswordToggleField({
  className,
  ...props
}: ComponentProps<typeof PasswordToggleFieldPrimitive.Root> & {
  className?: string;
}) {
  return (
    <div data-slot="password-toggle-field" className={cn("relative", className)}>
      <PasswordToggleFieldPrimitive.Root {...props} />
    </div>
  );
}

export function PasswordToggleFieldInput({
  className,
  ...props
}: ComponentProps<typeof PasswordToggleFieldPrimitive.Input>) {
  return (
    <PasswordToggleFieldPrimitive.Input
      data-slot="password-toggle-field-input"
      className={cn(
        "flex h-9 w-full rounded-lg border border-border bg-surface px-3 py-1 pr-10 text-sm shadow-xs",
        "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "dark:border-border dark:bg-surface-raised dark:placeholder:text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function PasswordToggleFieldToggle({
  className,
  ...props
}: ComponentProps<typeof PasswordToggleFieldPrimitive.Toggle>) {
  return (
    <PasswordToggleFieldPrimitive.Toggle
      data-slot="password-toggle-field-toggle"
      className={cn(
        "absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-muted-foreground hover:text-foreground dark:hover:text-foreground",
        className,
      )}
      {...props}
    >
      <PasswordToggleFieldPrimitive.Icon
        visible={<EyeIcon className="size-4" />}
        hidden={<EyeOffIcon className="size-4" />}
      />
    </PasswordToggleFieldPrimitive.Toggle>
  );
}
